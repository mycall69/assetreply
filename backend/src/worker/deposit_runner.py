"""예금 금리 수집 (T019) — 008 FR-009, FR-010, FR-020, research R8-3·R8-4.

투자처 하나의 월 시계열을 받는다. **요청은 하나다** — 처음은 항목의 시작 달(`START_TIME`)부터 이번
달까지 한 번에, 다시 확인은 마지막 받은 달의 `DEPOSIT_RECHECK_OVERLAP_MONTHS`개월 전부터다. 겹쳐
받는 까닭은 출처가 과거 값을 고치는지 보기 위해서다 — 바뀌었으면 **덮어쓰지 않고** 사건만
남긴다(research R8-4).

- 원본을 먼저 남긴다 — 정규화와 따로, 본문만(URL에는 인증키가 있다, FR-014)
- 미발표(구간에 값 없음)는 실패가 아니다 — 마지막 발표 달은 그대로이고 확인한 날은 오늘이다(FR-010)
- 확인한 날(`checked_on`)은 **성공했을 때만** 갱신한다 — 실패한 날 갱신하면 다음 날까지 다시
  확인하지 않는다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.ecos.deposit_client import ItemsLookup
from src.ingestion.ecos.deposit_items import DepositItem
from src.ingestion.protocols import MonthlyFetchResult
from src.observability.logging_config import collection_logger
from src.repository import deposit_rate

_KST = dt.timezone(dt.timedelta(hours=9))


class DepositSource(Protocol):
    """예금 금리 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    async def items_for(self, institution: str) -> ItemsLookup: ...

    async def fetch_series(
        self, item: DepositItem, from_month: dt.date, to_month: dt.date
    ) -> MonthlyFetchResult: ...


@dataclass(frozen=True, slots=True)
class Collected:
    first_month: dt.date
    latest_month: dt.date


def kst_date(now_utc: dt.datetime) -> dt.date:
    """UTC 시각(시간대 없는 값)의 한국 시간 날짜 — 확인한 날의 기준이다(FR-018)."""
    return now_utc.replace(tzinfo=dt.UTC).astimezone(_KST).date()


def months_between(first: dt.date, last: dt.date) -> int:
    """두 달(각 1일) 사이의 달 수, 양끝 포함. 순서가 거꾸로면 0."""
    count = (last.year - first.year) * 12 + last.month - first.month + 1
    return max(count, 0)


def shift_months(month: dt.date, months: int) -> dt.date:
    index = month.year * 12 + month.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def _event(event: str, **fields: object) -> None:
    collection_logger().info(event, extra={"event": event, **fields})


async def collect_institution(
    session: AsyncSession, source: DepositSource, *, institution: str, to_month: dt.date,
    overlap_months: int, now: dt.datetime,
) -> Collected:
    """그 투자처의 금리를 받아 저장하고 커버리지를 기록한다. 커밋은 부르는 쪽이 한다."""
    lookup = await source.items_for(institution)
    if lookup.fetched is not None:
        fetched = lookup.fetched
        # 항목 목록은 통계표 하나가 여러 투자처를 덮는다 — 투자처를 비운다(data-model 2절).
        await deposit_rate.store_raw(
            session, institution=None, endpoint="item_list", source_ref=fetched.source_ref,
            requested_from=None, requested_to=None, status_code=fetched.raw_status,
            result_code=None, body=fetched.raw_body, received_at=now)
    item = lookup.item

    coverage = await deposit_rate.get_coverage(session, institution)
    if coverage is None:
        from_month = item.start_month
    else:
        from_month = max(item.start_month,
                         shift_months(coverage.latest_month, -overlap_months))
    result = await source.fetch_series(item, from_month, to_month)
    await deposit_rate.store_raw(
        session, institution=institution, endpoint="search", source_ref=item.source_ref,
        requested_from=from_month, requested_to=to_month, status_code=result.raw_status,
        result_code=result.raw_result_code, body=result.raw_body, received_at=now)

    revisions = await deposit_rate.store_rates(session, institution, result.rates,
                                               ingested_at=now)
    for revision in revisions:
        _event("deposit_rate_revised", institution=institution,
               month=f"{revision.month:%Y-%m}", old=deposit_rate.rate_text(revision.old),
               new=deposit_rate.rate_text(revision.new))

    # 구간은 넓히기만 한다. 처음 받았는데 금리가 하나도 없으면 항목의 시작 달로 둔다 — 화면은 금리
    # 0행을 `no_rate_data`로 알린다.
    months = [r.month for r in result.rates]
    known = [coverage.first_month, coverage.latest_month] if coverage else []
    first = min([*months, *known], default=item.start_month)
    latest = max([*months, *known], default=item.start_month)
    await deposit_rate.record_coverage(session, institution, first_month=first,
                                       latest_month=latest, checked_on=kst_date(now))
    return Collected(first_month=first, latest_month=latest)
