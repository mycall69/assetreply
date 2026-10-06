"""정기적금 항목 계약 테스트 (011 T040) — FR-029, research R11-1·R11-2.

T003·008 T001이 받은 **실제 응답**으로 검증한다(헌법 원칙 III — 네트워크 없이).

- 적금은 **금리 계열 키**로 담는다 — 시중은행 `commercial_bank_isav`(예금은행 「정기적금(1-2년)」),
  상호금융 `mutual_finance_isav`(「정기적금」 — 만기 구분 없음)
- 항목은 008처럼 **알려진 코드 + 이름 패턴**으로 확정한다. 코드가 바뀌어도 이름으로 다시 찾고, 못
  찾으면 형식 오류다
- 이웃 항목이 걸리면 안 된다 — 「정기적금」(예금은행 전체, 3~4년 섞임)·「정기적금(3-4년)」·
  「정기적금(3년만기)」. 걸리면 다른 상품의 금리로 계산되는데 결과에 드러나지 않는다(FR-029 실패
  양상)
- 008의 투자처 항목(`resolve_deposit_items`)은 그대로다 —
  `test_ecos_deposit_parse.py::Test투자처_항목`
- 클라이언트는 적금 계열도 통계표 항목 목록을 **함께** 쓴다 — 항목 목록 호출이 늘지 않는다
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json

import pytest

from src.config.settings import Settings, _Secret, load_settings
from src.ingestion.ecos.deposit_client import EcosDepositClient
from src.ingestion.ecos.deposit_items import DepositItem
from src.ingestion.ecos.deposit_parse import parse_monthly
from src.ingestion.ecos.errors import ItemMappingChanged
from src.ingestion.ecos.installment_items import (
    INSTALLMENT_SERIES,
    SERIES_TABLE,
    resolve_installment_items,
)
from src.ingestion.protocols import FetchOutcome

from .conftest import StubResponse, StubSession, load

D = dt.date.fromisoformat
FAKE_KEY = "TESTKEY1234567890abcd"


def _settings() -> Settings:
    return dataclasses.replace(load_settings(), ecos_api_key=_Secret(FAKE_KEY))


def _without(table: str, code: str) -> str:
    """항목 목록에서 그 코드의 행을 뺀다 — 출처가 항목을 없앤 경우."""
    payload = json.loads(load(f"deposit/items_{table}.json"))
    rows = payload["StatisticItemList"]["row"]
    payload["StatisticItemList"]["row"] = [r for r in rows if r["ITEM_CODE"] != code]
    return json.dumps(payload, ensure_ascii=False)


def _recoded(table: str, code: str, new_code: str) -> str:
    payload = json.loads(load(f"deposit/items_{table}.json"))
    for row in payload["StatisticItemList"]["row"]:
        if row["ITEM_CODE"] == code:
            row["ITEM_CODE"] = new_code
    return json.dumps(payload, ensure_ascii=False)


class Test적금_항목:
    def test_계열은_둘이고_통계표가_정해져_있다(self) -> None:
        assert INSTALLMENT_SERIES == ("commercial_bank_isav", "mutual_finance_isav")
        assert SERIES_TABLE == {"commercial_bank_isav": "121Y002", "mutual_finance_isav": "121Y004"}
        # 008의 `institution` 열(String(24))에 들어간다
        assert all(len(key) <= 24 for key in INSTALLMENT_SERIES)

    def test_시중은행은_정기적금_1_2년이다(self) -> None:
        items = resolve_installment_items(load("deposit/items_121Y002.json"), "121Y002")
        assert items == {"commercial_bank_isav": DepositItem(
            "commercial_bank_isav", "121Y002", "BEABAA2122", "정기적금(1-2년)", D("2003-01-01"))}

    def test_상호금융은_만기_구분_없는_정기적금이다(self) -> None:
        items = resolve_installment_items(load("deposit/items_121Y004.json"), "121Y004")
        assert items == {"mutual_finance_isav": DepositItem(
            "mutual_finance_isav", "121Y004", "BEBB0200", "정기적금", D("2012-01-01"))}

    def test_코드가_바뀌면_이름으로_다시_찾는다(self) -> None:
        bank = resolve_installment_items(_recoded("121Y002", "BEABAA2122", "BEABAA9999"), "121Y002")
        assert bank["commercial_bank_isav"].item_code == "BEABAA9999"
        mutual = resolve_installment_items(_recoded("121Y004", "BEBB0200", "BEBB9999"), "121Y004")
        assert mutual["mutual_finance_isav"].item_code == "BEBB9999"

    def test_이웃_항목은_걸리지_않는다_시중은행(self) -> None:
        """「정기적금」(전체)·「정기적금(3-4년)」은 남아 있어도 걸리지 않는다."""
        with pytest.raises(ItemMappingChanged):
            resolve_installment_items(_without("121Y002", "BEABAA2122"), "121Y002")

    def test_이웃_항목은_걸리지_않는다_상호금융(self) -> None:
        """「정기적금(3년만기)」가 남아 있어도 걸리지 않는다 — 3년 상품의 금리다."""
        with pytest.raises(ItemMappingChanged):
            resolve_installment_items(_without("121Y004", "BEBB0200"), "121Y004")

    def test_적금_계열이_없는_통계표는_막는다(self) -> None:
        with pytest.raises(ItemMappingChanged):
            resolve_installment_items(load("deposit/items_121Y002.json"), "121Y999")


class Test적금_시계열:
    @pytest.mark.parametrize(("name", "first", "count"), [
        ("deposit/series_commercial_bank_isav.json", D("2003-01-01"), 284),
        ("deposit/series_mutual_finance_isav.json", D("2012-01-01"), 176),
    ])
    def test_실제_시계열을_008_파서로_읽는다(self, name: str, first: dt.date, count: int) -> None:
        result = parse_monthly(load(name), status=200)
        assert result.outcome is FetchOutcome.OK
        months = [r.month for r in result.rates]
        assert (months[0], months[-1], len(months)) == (first, D("2026-08-01"), count)


class Test클라이언트:
    async def test_적금_계열도_통계표_항목_목록을_함께_쓴다(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y002.json")),
                              StubResponse(load("deposit/series_commercial_bank_isav.json")))
        client = EcosDepositClient(_settings(), session=session)  # type: ignore[arg-type]
        deposit = await client.items_for("commercial_bank")
        installment = await client.items_for("commercial_bank_isav")
        assert len(session.calls) == 1
        assert deposit.fetched is not None and installment.fetched is None
        assert (deposit.item.item_code, installment.item.item_code) == ("BEABAA2118", "BEABAA2122")
        result = await client.fetch_series(installment.item, D("2003-01-01"), D("2026-10-01"))
        assert session.calls[1] == (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{FAKE_KEY}/json/kr/1/10000/"
            "121Y002/M/200301/202610/BEABAA2122")
        assert len(result.rates) == 284

    async def test_적금_계열을_먼저_부르면_항목_목록을_받는다(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y004.json")))
        client = EcosDepositClient(_settings(), session=session)  # type: ignore[arg-type]
        first = await client.items_for("mutual_finance_isav")
        second = await client.items_for("mutual_finance")
        assert len(session.calls) == 1
        assert first.fetched is not None and second.fetched is None
        # 항목 목록 결과(원본 저장용)의 투자처 항목은 008 그대로다
        assert set(first.fetched.items) == {"savings_bank", "credit_union", "mutual_finance",
                                            "saemaul"}
        assert (first.item.item_code, second.item.item_code) == ("BEBB0200", "BEBBBI01")
