"""시세 출처 정규화 계약 (T008) — 005 FR-011, FR-012, 헌법 원칙 II·III.

**저장된 응답 픽스처로만 검증한다.** 테스트가 실제 API를 호출하면 원칙 III 위반이다.

출처 고유 필드명(`adjclose`·`gmtoffset` 등)이 `ingestion/yahoo/` 밖으로 나가면 원칙 II
위반이다. 이 테스트는 어댑터가 돌려주는 **도메인 타입**만 본다.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.ingestion.yahoo.parse import parse_chart, parse_search

FIXTURES = Path(__file__).parent / "fixtures" / "stock"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def full():
    return parse_chart(load("chart_full.json"))


class Test일봉:
    def test_거래일마다_한_행이다(self, full) -> None:
        assert [p.quote_date for p in full.prices] == [
            dt.date(2021, 8, 2), dt.date(2021, 8, 3), dt.date(2021, 8, 4),
            dt.date(2021, 12, 29), dt.date(2022, 3, 30)]

    def test_원주가와_수정주가를_구분한다(self, full) -> None:
        """FR-012 — 섞으면 배당이 이중 계산되는데 값은 그럴듯하다."""
        first = full.prices[0]
        assert first.open_raw == Decimal("113500.0")
        assert first.close_raw == Decimal("113000.0")
        assert first.close_adjusted == Decimal("110000.0")
        assert first.close_raw != first.close_adjusted

    def test_값이_Decimal이다(self, full) -> None:
        """헌법 원칙 VI — float이 들어오면 정밀도가 경계에서 무너진다."""
        for p in full.prices:
            assert isinstance(p.open_raw, Decimal)
            assert isinstance(p.close_raw, Decimal)

    def test_거래소_현지_날짜로_환산한다(self, full) -> None:
        """UTC로 두면 한국 장 시작이 전날로 밀린다."""
        assert full.prices[0].quote_date == dt.date(2021, 8, 2)


class Test배당:
    def test_배당락일과_주당_금액을_돌려준다(self, full) -> None:
        assert [(d.ex_date, d.amount_per_share) for d in full.dividends] == [
            (dt.date(2021, 12, 29), Decimal("1540.0")),
            (dt.date(2022, 3, 30), Decimal("300.0"))]

    def test_배당이_없으면_빈_목록이다(self) -> None:
        """0원 배당을 만들어내지 않는다."""
        assert parse_chart(load("chart_split_only.json")).dividends == []


class Test분할:
    def test_분자와_분모를_정수로_돌려준다(self, full) -> None:
        """소수로 주면 3:1 분할이 0.333…이 되어 오차가 들어간다."""
        split = full.splits[0]
        assert (split.effective_date, split.numerator, split.denominator) == (
            dt.date(2021, 8, 4), 50, 1)
        assert isinstance(split.numerator, int)

    def test_배당_없이_분할만_있어도_읽는다(self) -> None:
        parsed = parse_chart(load("chart_split_only.json"))
        assert [(s.numerator, s.denominator) for s in parsed.splits] == [(4, 1)]


class Test실수로_온_분할_비율:
    """006 T102 — T090에서 발견. **실제 응답은 분할 비율을 실수로 준다.**

    픽스처 `chart_split_float.json`은 실제 응답이다(2026-10-03 받음, 토요타 `7203.T`,
    2021-09~10 — 2021-09-29 5:1 분할). `numerator: 5.0`, `denominator: 1.0`이다.
    005는 `int(str(…))`로 읽어 `'5.0'`에서 실패했고, 구간에 분할이 있는 종목의 시세
    수집이 매번 실패했다. 005의 픽스처는 정수라 테스트가 통과했다.
    """

    def test_실제_응답의_분할을_정수로_읽는다(self) -> None:
        parsed = parse_chart(load("chart_split_float.json"))
        assert [(s.effective_date, s.numerator, s.denominator) for s in parsed.splits] == [
            (dt.date(2021, 9, 29), 5, 1)]
        assert all(isinstance(s.numerator, int) and isinstance(s.denominator, int)
                   for s in parsed.splits)

    def test_같은_응답의_일봉과_배당도_읽는다(self) -> None:
        parsed = parse_chart(load("chart_split_float.json"))
        assert len(parsed.prices) == 41
        assert [(d.ex_date, d.amount_per_share) for d in parsed.dividends] == [
            (dt.date(2021, 9, 29), Decimal("24.0"))]

    @pytest.mark.parametrize(("numerator", "denominator"), [(2.5, 1.0), (3.0, 0.0), (-2.0, 1.0)])
    def test_정수가_아닌_비율은_반올림하지_않고_거절한다(
            self, numerator: float, denominator: float) -> None:
        """2.5:1을 2:1이나 3:1로 바꾸면 보유 수량이 조용히 틀린다(헌법 원칙 V·VI)."""
        from src.ingestion.yahoo.errors import StockSourceUnavailable

        body = load("chart_split_float.json")
        events = body["chart"]["result"][0]["events"]["splits"]  # type: ignore[index]
        for item in events.values():
            item["numerator"], item["denominator"] = numerator, denominator
        with pytest.raises(StockSourceUnavailable):
            parse_chart(body)


class Test메타:
    def test_통화와_최초_거래일을_돌려준다(self, full) -> None:
        assert full.currency == "KRW"
        assert full.first_trade_date == dt.date(1975, 6, 11)

    def test_미국_종목의_통화도_읽는다(self) -> None:
        assert parse_chart(load("chart_split_only.json")).currency == "USD"


class Test빈_응답:
    def test_값이_없으면_빈_목록이고_오류가_아니다(self) -> None:
        """상장 이전 구간을 요청하면 빈 결과가 온다. 그것은 실패가 아니다."""
        parsed = parse_chart(load("chart_empty.json"))
        assert parsed.prices == []
        assert parsed.dividends == []
        assert parsed.splits == []
        assert parsed.currency == "KRW"


class Test검색:
    def test_시장과_통화를_함께_돌려준다(self) -> None:
        """FR-002b — 같은 이름이 여러 시장에 있고 통화가 다르면 환전 여부가 달라진다."""
        results = parse_search(load("search_samsung.json"))
        first = results[0]
        assert first.symbol == "005930.KS"
        assert first.market == "KRX"
        assert first.currency == "KRW"
        assert "삼성" in first.name or "Samsung" in first.name

    def test_주식이_아닌_항목을_거른다(self) -> None:
        """ETF·GDR은 이번 범위가 아니다 (spec Out of Scope)."""
        symbols = [r.symbol for r in parse_search(load("search_samsung.json"))]
        assert "SMSN.IL" not in symbols

    def test_결과가_없으면_빈_목록이다(self) -> None:
        assert parse_search(load("search_empty.json")) == []
