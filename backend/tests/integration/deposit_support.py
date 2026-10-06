"""예금 통합 테스트 공용 — 가짜 ECOS 예금 출처와 금리 심기(008).

가짜 출처는 T001의 **실제 응답 픽스처**를 읽어 돌려준다(헌법 원칙 III — 네트워크 없이). 요청한
구간만 잘라 준다 — 출처가 실제로 그렇게 답한다.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from src.ingestion.ecos.deposit_client import ItemsFetch, ItemsLookup
from src.ingestion.ecos.deposit_items import TABLE_OF, DepositItem, resolve_deposit_items
from src.ingestion.ecos.deposit_parse import parse_monthly
from src.ingestion.ecos.errors import SourceError
from src.ingestion.protocols import FetchOutcome, MonthlyFetchResult, MonthlyRate
from src.repository import deposit_rate

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "deposit"
D = dt.date.fromisoformat

# 실행 날짜를 고정한다 — 픽스처의 마지막 발표 달이 2026-08이고 오늘은 2026-10-04(한국 시간)다.
TODAY = D("2026-10-04")
NOW_UTC = dt.datetime(2026, 10, 4, 3, 0, 0)  # 한국 시간 12:00
LATEST = D("2026-08-01")
SERIES = {"commercial_bank": "series_commercial_bank.json",
          "savings_bank": "series_savings_bank.json",
          "credit_union": "series_credit_union.json",
          "mutual_finance": "series_mutual_finance.json",
          "saemaul": "series_saemaul.json",
          # 011 — 정기적금 계열(금리 계열 키, research R11-2). 008의 다섯 값은 그대로다.
          "commercial_bank_isav": "series_commercial_bank_isav.json",
          "mutual_finance_isav": "series_mutual_finance_isav.json"}


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def real_rates(institution: str) -> list[MonthlyRate]:
    return list(parse_monthly(fixture(SERIES[institution]), status=200).rates)


class StubDepositSource:
    """`EcosDepositClient`와 같은 모양. 요청을 기록하고, 원하면 오류를 던지거나 값을 바꿔 준다."""

    def __init__(self, *, error: SourceError | None = None,
                 override: dict[str, dict[str, str]] | None = None) -> None:
        self.error = error
        self.override = override or {}
        self.items_calls: list[str] = []
        self.series_calls: list[tuple[str, dt.date, dt.date]] = []
        self._items: dict[str, ItemsFetch] = {}

    async def items_for(self, institution: str) -> ItemsLookup:
        if self.error is not None:
            raise self.error
        table = TABLE_OF.get(institution)
        if table is None:
            # 011 — 적금 계열은 같은 통계표의 항목 목록을 함께 쓴다(클라이언트와 같다). 008 테스트가
            # 이 갈래를 지나지 않게 안에서 가져온다.
            from src.ingestion.ecos.installment_items import SERIES_TABLE

            table = SERIES_TABLE[institution]
        cached = self._items.get(table)
        fetched: ItemsFetch | None = None
        if cached is None:
            self.items_calls.append(table)
            body = fixture(f"items_{table}.json")
            fetched = cached = ItemsFetch(table, resolve_deposit_items(body, table), body, 200)
            self._items[table] = fetched
        if institution in cached.items:
            return ItemsLookup(cached.items[institution], fetched)
        from src.ingestion.ecos.installment_items import resolve_installment_items

        return ItemsLookup(resolve_installment_items(cached.raw_body, table)[institution], fetched)

    async def fetch_series(
        self, item: DepositItem, from_month: dt.date, to_month: dt.date
    ) -> MonthlyFetchResult:
        self.series_calls.append((item.institution, from_month, to_month))
        if self.error is not None:
            raise self.error
        payload = json.loads(fixture(SERIES[item.institution]))
        rows = [r for r in payload["StatisticSearch"]["row"]
                if from_month.strftime("%Y%m") <= r["TIME"] <= to_month.strftime("%Y%m")]
        for row in rows:
            changed = self.override.get(item.institution, {}).get(row["TIME"])
            if changed is not None:
                row["DATA_VALUE"] = changed
        if not rows:
            body = fixture("unpublished_info200.json")
            return MonthlyFetchResult((), FetchOutcome.NO_DATA, body, 200, "INFO-200")
        payload["StatisticSearch"]["row"] = rows
        payload["StatisticSearch"]["list_total_count"] = len(rows)
        return parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)


async def seed_rates(session_factory, institution: str = "commercial_bank", *,  # type: ignore[no-untyped-def]
                     through: dt.date = LATEST, checked_on: dt.date = TODAY,
                     drop: tuple[str, ...] = ()) -> None:
    """실측 금리를 그대로 심고 커버리지를 기록한다. `drop`의 달(YYYY-MM)은 빼서 결측을 만든다."""
    rates = [r for r in real_rates(institution)
             if r.month <= through and r.month.strftime("%Y-%m") not in drop]
    async with session_factory() as s:
        await deposit_rate.store_rates(s, institution, rates, ingested_at=NOW_UTC)
        await deposit_rate.record_coverage(
            s, institution, first_month=min(r.month for r in real_rates(institution)),
            latest_month=through, checked_on=checked_on)
        await s.commit()


def rate_of(institution: str, month: str) -> Decimal:
    return next(r.rate for r in real_rates(institution) if r.month == D(month + "-01"))
