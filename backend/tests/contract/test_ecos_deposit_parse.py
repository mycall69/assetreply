"""예금 금리 응답 파싱 계약 테스트 (T003) — 008 FR-008, FR-016, FR-017, research R8-1·R8-3·R8-5.

T001이 받은 **실제 응답**으로 검증한다(헌법 원칙 III — 네트워크 없이).

- 월 시계열 → `MonthlyRate(그 달 1일, Decimal 연 %)`. 값은 `"3.2"`처럼 끝의 0이 빠져 온다
- `INFO-200`(구간에 값 없음)은 **미발표**다 — 오류가 아니다.
  받은 구간으로 기록하면 그 달이 영영 빈다(FR-010)
- 숫자가 아닌 값이 하나라도 있으면 **응답 전체가 형식 오류**다.
  읽지 못한 달만 버리면 결측으로 위장된다(FR-017)
- 투자처 ↔ 항목 코드는 이름 패턴으로 확정한다 — 코드가 바뀌어도 다시 찾고, 못 찾으면 형식 오류(R8-1)
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import pytest

from src.ingestion.ecos.deposit_items import INSTITUTIONS, TABLE_OF, resolve_deposit_items
from src.ingestion.ecos.deposit_parse import deposit_failure_kind, parse_monthly
from src.ingestion.ecos.errors import (
    ItemMappingChanged,
    SourceAuthError,
    SourceError,
    SourceRateLimited,
    SourceUnavailable,
)
from src.ingestion.protocols import FetchOutcome

from .conftest import load

SERIES = {
    "commercial_bank": ("deposit/series_commercial_bank.json", dt.date(2012, 1, 1), 176),
    "savings_bank": ("deposit/series_savings_bank.json", dt.date(1997, 8, 1), 349),
    "credit_union": ("deposit/series_credit_union.json", dt.date(1997, 8, 1), 349),
    "mutual_finance": ("deposit/series_mutual_finance.json", dt.date(1997, 8, 1), 349),
    "saemaul": ("deposit/series_saemaul.json", dt.date(2012, 1, 1), 176),
}
LAST = dt.date(2026, 8, 1)


def _kind(exc: BaseException) -> str:
    assert isinstance(exc, SourceError)
    return deposit_failure_kind(exc)


class Test월_시계열:
    @pytest.mark.parametrize("institution", list(SERIES))
    def test_실제_시계열의_첫_달_마지막_달_행_수(self, institution: str) -> None:
        name, first, count = SERIES[institution]
        result = parse_monthly(load(name), status=200)
        assert result.outcome is FetchOutcome.OK
        months = [r.month for r in result.rates]
        assert (months[0], months[-1], len(months)) == (first, LAST, count)
        assert months == sorted(months)
        assert all(m.day == 1 for m in months)

    def test_금리는_Decimal이고_끝의_0이_없어도_읽는다(self) -> None:
        rates = {r.month: r.rate for r in parse_monthly(
            load("deposit/series_credit_union.json"), status=200).rates}
        assert rates[dt.date(2026, 4, 1)] == Decimal("3.2")
        assert isinstance(rates[dt.date(2026, 4, 1)], Decimal)
        assert rates[dt.date(2026, 8, 1)] == Decimal("3.62")

    def test_원본을_함께_돌려준다(self) -> None:
        body = load("deposit/series_saemaul.json")
        result = parse_monthly(body, status=200)
        assert (result.raw_body, result.raw_status, result.raw_result_code) == (body, 200, None)

    def test_쉼표를_지운다(self) -> None:
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["row"][0]["DATA_VALUE"] = "1,000.5"
        result = parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert result.rates[0].rate == Decimal("1000.5")


class Test미발표와_오류:
    def test_INFO_200은_미발표다_오류가_아니다(self) -> None:
        result = parse_monthly(load("deposit/unpublished_info200.json"), status=200)
        assert result.outcome is FetchOutcome.NO_DATA
        assert result.rates == ()
        assert result.raw_result_code == "INFO-200"

    def test_인증_실패(self) -> None:
        with pytest.raises(SourceAuthError) as info:
            parse_monthly(load("info_100_bad_key.json"), status=200)
        assert _kind(info.value) == "auth"
        assert info.value.retryable is False

    def test_한도_초과(self) -> None:
        with pytest.raises(SourceRateLimited) as info:
            parse_monthly(load("info_300_rate_limit.json"), status=200)
        assert _kind(info.value) == "rate_limited"
        assert info.value.retryable is True

    def test_ERROR_코드는_형식_오류이고_다시_시도하지_않는다(self) -> None:
        body = json.dumps({"RESULT": {"CODE": "ERROR-101", "MESSAGE": "주기와 다른 형식의 날짜"}})
        with pytest.raises(SourceError) as info:
            parse_monthly(body, status=200)
        assert _kind(info.value) == "format"
        assert info.value.retryable is False

    def test_JSON이_아니면_연결_오류다(self) -> None:
        with pytest.raises(SourceUnavailable) as info:
            parse_monthly("<html>점검 중</html>", status=200)
        assert _kind(info.value) == "network"

    def test_HTTP_상태가_실패면_연결_오류다(self) -> None:
        with pytest.raises(SourceUnavailable):
            parse_monthly("", status=503)

    def test_잘린_응답은_형식_오류다(self) -> None:
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["list_total_count"] = 999
        with pytest.raises(SourceError) as info:
            parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert _kind(info.value) == "format"

    @pytest.mark.parametrize("bad", ["", "-", "N/A", None])
    def test_숫자가_아닌_값이_하나라도_있으면_응답_전체가_형식_오류다(self, bad: object) -> None:
        """읽지 못한 달만 버리면 그 달이 결측으로 위장된다(FR-017)."""
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["row"][10]["DATA_VALUE"] = bad
        with pytest.raises(SourceError) as info:
            parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert _kind(info.value) == "format"
        assert "2012-11" in str(info.value) or "201211" in str(info.value)

    def test_소수_4자리를_넘는_금리는_응답_전체가_형식_오류다(self) -> None:
        """저장 자릿수(연 % 소수 4자리)를 넘으면 조용히 반올림되어 출처 값과 달라진다(FR-017·FR-029,
        반복 #2)."""
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["row"][10]["DATA_VALUE"] = "3.12345"
        with pytest.raises(SourceError) as info:
            parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert _kind(info.value) == "format"
        assert "201211" in str(info.value) or "2012-11" in str(info.value)

    @pytest.mark.parametrize("value", ["3.1234", "3.2", "3", "-0.5"])
    def test_소수_4자리까지는_그대로_읽는다(self, value: str) -> None:
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["row"][10]["DATA_VALUE"] = value
        result = parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert result.rates[10].rate == Decimal(value)

    def test_달_형식이_아니면_형식_오류다(self) -> None:
        payload = json.loads(load("deposit/series_saemaul.json"))
        payload["StatisticSearch"]["row"][0]["TIME"] = "2012"
        with pytest.raises(SourceError) as info:
            parse_monthly(json.dumps(payload, ensure_ascii=False), status=200)
        assert _kind(info.value) == "format"


class Test투자처_항목:
    def test_투자처는_다섯이고_화면_순서다(self) -> None:
        assert INSTITUTIONS == (
            "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul")

    def test_시중은행은_예금은행_정기예금_1년(self) -> None:
        items = resolve_deposit_items(
            load("deposit/items_121Y002.json"), TABLE_OF["commercial_bank"])
        item = items["commercial_bank"]
        assert (item.item_code, item.item_name, item.start_month) == (
            "BEABAA2118", "정기예금(1년)", dt.date(2012, 1, 1))
        assert set(items) == {"commercial_bank"}

    def test_비은행_넷(self) -> None:
        items = resolve_deposit_items(load("deposit/items_121Y004.json"), "121Y004")
        got = {k: (v.item_code, v.start_month) for k, v in items.items()}
        assert got == {
            "savings_bank": ("BEBBBE01", dt.date(1997, 8, 1)),
            "credit_union": ("BEBBBG01", dt.date(1997, 8, 1)),
            "mutual_finance": ("BEBBBI01", dt.date(1997, 8, 1)),
            "saemaul": ("BEBBA000", dt.date(2012, 1, 1)),
        }

    def test_상호금융은_정기예탁금_1년만기_하나만_맞는다(self) -> None:
        """상위 항목 "정기예탁금"(BEBB0100)이 걸리면 1년이 아닌 금리를 저장한다(R8-1)."""
        items = resolve_deposit_items(load("deposit/items_121Y004.json"), "121Y004")
        assert items["mutual_finance"].item_name == "정기예탁금(1년만기)"

    def test_코드가_바뀌어도_이름으로_다시_찾는다(self) -> None:
        payload = json.loads(load("deposit/items_121Y004.json"))
        for row in payload["StatisticItemList"]["row"]:
            if row["ITEM_CODE"] == "BEBBBG01":
                row["ITEM_CODE"] = "BEBBBG99"
        items = resolve_deposit_items(json.dumps(payload, ensure_ascii=False), "121Y004")
        assert items["credit_union"].item_code == "BEBBBG99"

    def test_이름으로도_못_찾으면_형식_오류다(self) -> None:
        payload = json.loads(load("deposit/items_121Y004.json"))
        payload["StatisticItemList"]["row"] = [
            r for r in payload["StatisticItemList"]["row"] if "새마을금고" not in r["ITEM_NAME"]]
        with pytest.raises(ItemMappingChanged) as info:
            resolve_deposit_items(json.dumps(payload, ensure_ascii=False), "121Y004")
        assert _kind(info.value) == "format"

    def test_모르는_통계표(self) -> None:
        with pytest.raises(ItemMappingChanged):
            resolve_deposit_items(load("deposit/items_121Y004.json"), "731Y001")
