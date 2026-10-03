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

    @pytest.mark.parametrize(("numerator", "denominator"), [
        (3.0, 0.0), (-2.0, 1.0), (0.0, 1.0), ("NaN", 1.0), ("abc", 1.0),
        # 기약 분수가 저장 열(`INT`)을 넘는다 — 줄이거나 반올림하지 않고 거절한다.
        (1.0526315789, 1.0),
    ])
    def test_쓸_수_없는_비율은_거절한다(
            self, numerator: object, denominator: object) -> None:
        """비율을 반올림해 받으면 보유 수량이 조용히 틀린다(헌법 원칙 V·VI).

        버그 `fractional-split-ratio`(2026-10-03) 전에는 `2.5:1`도 여기서 거절했다. 정수가 아닌
        비율도 정확한 분수로 다루면 반올림 없이 받을 수 있어, 거절은 쓸 수 없는 값으로 좁혔다
        (아래 `Test분수_비율`).
        """
        from src.ingestion.yahoo.errors import StockSourceUnavailable

        body = load("chart_split_float.json")
        events = body["chart"]["result"][0]["events"]["splits"]  # type: ignore[index]
        for item in events.values():
            item["numerator"], item["denominator"] = numerator, denominator
        with pytest.raises(StockSourceUnavailable):
            parse_chart(body)


class Test분수_비율:
    """버그 `fractional-split-ratio` — 006 FR-034, 005 FR-010a. 2026-10-03.

    출처는 정수가 아닌 비율도 준다 — 삼성물산(`028260.KS`) 2020-05-13 `0.985:1`. T103의 "양의
    정수만" 규칙에 걸려 그 날짜를 포함한 수집이 매번 실패했다. 비율을 **정확한 기약 정수 쌍**으로
    받는다(`0.985:1` → `197:200`). 픽스처는 실제 응답이다(2026-10-03 받음, 2020-01-01~2021-12-30).
    """

    def test_실제_응답의_분수_비율을_기약_정수_쌍으로_읽는다(self) -> None:
        parsed = parse_chart(load("chart_split_fractional.json"))
        assert [(s.effective_date, s.numerator, s.denominator) for s in parsed.splits] == [
            (dt.date(2020, 5, 13), 197, 200)]

    def test_되살린_원주가가_정확히_호가_단위다(self) -> None:
        """출처는 이벤트 이전 시세를 0.985로 나눠 두었다. 정확한 분수로 곱하면 실제 호가가 된다."""
        from src.ingestion.yahoo.parse import restore_unadjusted

        chart = parse_chart(load("chart_split_fractional.json"))
        restored = {p.quote_date: p.open_raw for p in restore_unadjusted(chart, []).prices}
        assert restored[dt.date(2020, 5, 8)] == Decimal("104500.000000")
        assert restored[dt.date(2020, 5, 12)] == Decimal("102000.000000")
        # 이벤트 날부터는 출처 값 그대로다.
        assert restored[dt.date(2020, 5, 13)] == Decimal("98000.0")

    @pytest.mark.parametrize(("numerator", "denominator", "expected"), [
        (5.0, 1.0, (5, 1)),
        (2.5, 1.0, (5, 2)),
        (1.5, 1.0, (3, 2)),
        (1.0, 10.0, (1, 10)),
        (0.985, 1.0, (197, 200)),
        (4.0, 2.0, (2, 1)),
    ])
    def test_비율을_반올림하지_않고_기약_정수_쌍으로(
            self, numerator: float, denominator: float, expected: tuple[int, int]) -> None:
        body = load("chart_split_float.json")
        events = body["chart"]["result"][0]["events"]["splits"]  # type: ignore[index]
        for item in events.values():
            item["numerator"], item["denominator"] = numerator, denominator
        [split] = parse_chart(body).splits
        assert (split.numerator, split.denominator) == expected


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


class Test분할_반영가를_원주가로_되살린다:
    """006 T104 — FR-034, research R6-18. T090 결함 5.

    **출처의 시가·종가·배당은 분할을 소급 반영한 값이다.** 005는 그것을 바뀌지 않는 원주가로
    보고 분할 날 주식 수를 다시 늘려, 분할이 두 번 들어갔다(토요타 2021-08 시작이 580%).
    어댑터가 **그날 이후의 분할 비율을 곱해** 원주가로 되살린다.

    픽스처는 모두 실제 응답이다(2026-10-03 받음). 분할 기록(`splits_*`)은 월봉 요청이라 이벤트
    키가 월 시작이지만 `date`는 실제 분할일이다. 되살린 값은 그날의 실제 시가·배당과 출처의
    소수점 오차 안에서 같다 — 애플 2000-01-03 시가 104.87달러, 2012-08-09 배당 2.65달러.
    """

    def test_분할_기록을_읽는다(self) -> None:
        from src.ingestion.yahoo.parse import parse_splits

        assert [(s.effective_date, s.numerator, s.denominator)
                for s in parse_splits(load("splits_aapl_since_2000.json"))] == [
            (dt.date(2000, 6, 21), 2, 1), (dt.date(2005, 2, 28), 2, 1),
            (dt.date(2014, 6, 9), 7, 1), (dt.date(2020, 8, 31), 4, 1)]

    def test_토요타는_분할_전날까지_5배로_되살린다(self) -> None:
        from src.ingestion.yahoo.parse import parse_splits, restore_unadjusted

        chart = parse_chart(load("chart_split_float.json"))
        restored = restore_unadjusted(
            chart, parse_splits(load("splits_toyota_since_2021_09.json")))
        prices = {p.quote_date: p for p in restored.prices}
        assert (prices[dt.date(2021, 9, 1)].open_raw,
                prices[dt.date(2021, 9, 1)].close_raw) == (
            Decimal("9700.999756"), Decimal("9652.000122"))
        assert (prices[dt.date(2021, 9, 28)].open_raw,
                prices[dt.date(2021, 9, 28)].close_raw) == (
            Decimal("10420.000000"), Decimal("10385.000000"))

    def test_분할_날부터는_그대로다(self) -> None:
        """분할 날의 시세는 이미 분할 뒤 값이다 — 그날 이후의 분할만 곱한다."""
        from src.ingestion.yahoo.parse import parse_splits, restore_unadjusted

        chart = parse_chart(load("chart_split_float.json"))
        restored = restore_unadjusted(
            chart, parse_splits(load("splits_toyota_since_2021_09.json")))
        after = [(p.quote_date, p.open_raw, p.close_raw) for p in restored.prices
                 if p.quote_date >= dt.date(2021, 9, 29)]
        assert after == [(p.quote_date, p.open_raw, p.close_raw) for p in chart.prices
                         if p.quote_date >= dt.date(2021, 9, 29)]
        assert after[0][1] == Decimal("2052.0")
        # 분할 날의 배당은 분할 뒤 주식에 붙는다(005 spec Assumptions) — 그대로다.
        assert restored.dividends == chart.dividends
        assert restored.splits == chart.splits

    def test_수정종가는_출처가_준_그대로_둔다(self) -> None:
        """수정종가는 계산에 쓰지 않는다(005 FR-011). 되살리면 그 열의 뜻이 바뀐다."""
        from src.ingestion.yahoo.parse import parse_splits, restore_unadjusted

        chart = parse_chart(load("chart_split_float.json"))
        restored = restore_unadjusted(
            chart, parse_splits(load("splits_toyota_since_2021_09.json")))
        assert [p.close_adjusted for p in restored.prices] == [
            p.close_adjusted for p in chart.prices]

    def test_애플_2000년_시가는_이후_네_번의_분할로_112배다(self) -> None:
        from src.ingestion.yahoo.parse import parse_splits, restore_unadjusted

        chart = parse_chart(load("chart_aapl_2000_01.json"))
        restored = restore_unadjusted(chart, parse_splits(load("splits_aapl_since_2000.json")))
        first = restored.prices[0]
        assert first.quote_date == dt.date(2000, 1, 3)
        assert (first.open_raw, first.close_raw) == (
            Decimal("104.875010"), Decimal("111.937502"))
        # 그날의 실제 시가·종가(104.87·111.94)와 출처의 소수점 오차 안에서 같다.
        assert abs(first.open_raw - Decimal("104.87")) < Decimal("0.01")
        assert abs(first.close_raw - Decimal("111.94")) < Decimal("0.01")

    def test_배당도_이후의_분할로_되살린다(self) -> None:
        from src.ingestion.yahoo.parse import parse_splits, restore_unadjusted

        chart = parse_chart(load("chart_aapl_2012_08.json"))
        restored = restore_unadjusted(chart, parse_splits(load("splits_aapl_since_2000.json")))
        assert [(d.ex_date, d.amount_per_share) for d in restored.dividends] == [
            (dt.date(2012, 8, 9), Decimal("2.650004"))]
        assert restored.prices[0].open_raw == Decimal("615.910011")

    def test_뒤의_분할이_없으면_값을_바꾸지_않는다(self) -> None:
        from src.ingestion.yahoo.parse import restore_unadjusted

        chart = parse_chart(load("chart_aapl_2012_08.json"))
        assert restore_unadjusted(chart, []) == chart

    @pytest.mark.parametrize(("numerator", "denominator", "expected"), [
        (1, 10, Decimal("10.000000")),
        (1, 3, Decimal("33.333333")),
        (3, 2, Decimal("150.000000")),
    ])
    def test_병합은_나누고_정수가_아닌_배율도_그대로_곱한다(
            self, numerator: int, denominator: int, expected: Decimal) -> None:
        """병합(1:10)이면 과거 원주가는 반영가보다 작다. 나눗셈은 저장 자릿수(6)로 맞춘다."""
        from src.ingestion.yahoo.parse import ChartData, DailyPrice, SplitEvent, restore_unadjusted

        chart = ChartData(currency="USD", first_trade_date=None, prices=[
            DailyPrice(dt.date(2020, 1, 2), Decimal("100"), Decimal("100"), Decimal("100"))])
        restored = restore_unadjusted(
            chart, [SplitEvent(dt.date(2020, 6, 1), numerator, denominator)])
        assert restored.prices[0].open_raw == expected

    def test_같은_날의_비율이_어긋나면_거절한다(self) -> None:
        """두 응답이 같은 분할을 다르게 말하면 어느 쪽으로 되살려도 틀릴 수 있다."""
        from src.ingestion.yahoo.errors import StockSourceUnavailable
        from src.ingestion.yahoo.parse import SplitEvent, restore_unadjusted

        chart = parse_chart(load("chart_split_float.json"))
        with pytest.raises(StockSourceUnavailable):
            restore_unadjusted(chart, [SplitEvent(dt.date(2021, 9, 29), 4, 1)])
