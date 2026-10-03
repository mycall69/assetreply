"""가상자산 출처(investing.com) 응답 파싱 계약 (T003) — 007 FR-006, FR-012, FR-012a, FR-021, FR-022,
research R7-3·R7-4.

**실제 응답 픽스처**(T001, 2026-10-03)로 검증한다. 공식 문서가 없는 내부 API라 픽스처가 그 시점의
형식을 고정한다.

- **화면용 문자열을 쓰지 않는다.** `last_open` 같은 값은 코인의 자릿수로 반올림되어 작은 값이
  `0.0`이 된다 — 원값(`…Raw`)을
  `float` 없이 `Decimal`로 읽는다
- **마감 전 일봉을 버린다.** 출처는 UTC 오늘의 일봉도 준다. 계산 끝(UTC 어제)보다 뒤의 행은
  정규화에서 버린다
- **가격을 읽지 못한 행이 하나라도 있으면 청크 전체가 형식 오류다.** 그 행만 버리면 그날이 출처
  결측으로 위장된다(analyze M2)
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.ingestion.investing.errors import InvestingFormatError
from src.ingestion.investing.parse import (
    ROW_LIMIT_GUARD,
    korean_names,
    parse_coin_page,
    parse_daily,
)

FIXTURES = Path(__file__).parent / "fixtures" / "crypto"
D = dt.date.fromisoformat
LAST = D("2026-10-02")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Test코인_목록:
    def test_첫_쪽을_코인_행으로_읽는다(self) -> None:
        page = parse_coin_page(fixture("coins_en_p1.json"))
        assert len(page.coins) == 100
        btc = page.coins[0]
        # 식별자는 출처의 instrument_id를 **문자열**로 — 출처 형식(정수)에 묶이지 않게 한다
        assert (btc.source_id, btc.symbol, btc.name, btc.rank, btc.slug) == (
            "1057391", "BTC", "Bitcoin", 1, "bitcoin")
        assert page.next_cursor is not None

    def test_마지막_쪽은_커서가_없다(self) -> None:
        page = parse_coin_page(fixture("coins_en_last.json"))
        assert page.next_cursor is None
        assert len(page.coins) == 54

    def test_한국어_판은_같은_식별자를_준다(self) -> None:
        en = parse_coin_page(fixture("coins_en_p1.json")).coins
        ko = parse_coin_page(fixture("coins_ko_p1.json")).coins
        assert [c.source_id for c in en[:10]] == [c.source_id for c in ko[:10]]

    def test_한글_이름은_영문과_다르고_한글일_때만이다(self) -> None:
        """FR-006 — BNB·XRP처럼 한국어 판도 영문 그대로면 한글 이름이 아니다."""
        en = parse_coin_page(fixture("coins_en_p1.json")).coins
        ko = parse_coin_page(fixture("coins_ko_p1.json")).coins
        names = korean_names(en, ko)
        assert names["1057391"] == "비트코인"
        assert names["1061443"] == "이더리움"
        assert "1061448" not in names   # BNB
        assert "1057392" not in names   # XRP

    def test_짝짓기는_식별자로만_한다(self) -> None:
        """이름·심볼로 짝지으면 같은 심볼의 다른 코인과 섞인다(FR-004)."""
        en = parse_coin_page(fixture("coins_en_p1.json")).coins
        ko = list(reversed(parse_coin_page(fixture("coins_ko_p1.json")).coins))
        assert korean_names(en, ko)["1057391"] == "비트코인"

    @pytest.mark.parametrize("body", ["<html>blocked</html>", '{"items": []}',
                                      '{"coins": [{"symbol": "X"}]}'])
    def test_형식이_다르면_형식_오류다(self, body: str) -> None:
        with pytest.raises(InvestingFormatError):
            parse_coin_page(body)


class Test일봉:
    def test_원값을_Decimal로_읽는다(self) -> None:
        bars = {b.day: b for b in parse_daily(fixture("btc_2020_2021.json"), last_day=LAST)}
        b = bars[D("2020-01-01")]
        assert (b.open, b.high, b.low, b.close) == (
            Decimal("7196.39111328125000"), Decimal("7259.38085937500000"),
            Decimal("7179.97753906250000"), Decimal("7199.78955078125000"))
        assert b.volume == Decimal("420278")

    def test_날짜는_UTC_하루이고_오름차순이다(self) -> None:
        bars = parse_daily(fixture("btc_2020_2021.json"), last_day=LAST)
        assert len(bars) == 731
        assert bars[0].day == D("2020-01-01") and bars[-1].day == D("2021-12-31")
        assert all(a.day < b.day for a, b in zip(bars, bars[1:], strict=False))

    def test_아주_작은_가격도_자르지_않는다(self) -> None:
        """화면용 문자열은 SHIB을 `0.00000530`처럼 반올림한다. 원값은 14자리다."""
        bars = parse_daily(fixture("shib_recent.json"), last_day=LAST)
        assert bars[0].open == Decimal("0.00000529999988")
        assert bars[0].volume == Decimal("1181698883584")

    def test_빈_거래량은_None이다(self) -> None:
        """FR-012a — 출처가 `volume: ""`·`volumeRaw: 0`으로 준 날은 0이 아니라 값 없음이다."""
        bars = {b.day: b for b in parse_daily(fixture("btc_2011_06.json"), last_day=LAST)}
        assert bars[D("2011-06-20")].volume is None
        assert bars[D("2011-06-25")].volume is None
        assert bars[D("2011-06-19")].volume == Decimal("30177")
        # 거래량이 없어도 가격은 있다
        assert bars[D("2011-06-20")].open == Decimal("17.51000022888184")

    def test_계산_끝보다_뒤의_행은_버린다(self) -> None:
        """FR-022 — 출처는 마감 전인 UTC 오늘(2026-10-03)의 일봉도 준다."""
        bars = parse_daily(fixture("btc_recent.json"), last_day=LAST)
        assert bars[-1].day == D("2026-10-02")
        assert len(bars) == 20

    def test_요청보다_늦게_시작하는_코인(self) -> None:
        bars = parse_daily(fixture("eth_first.json"), last_day=LAST)
        assert bars[0].day == D("2016-03-10")
        assert len(bars) == 448

    def test_일봉이_없으면_빈_목록이다(self) -> None:
        """Doge Killer는 `"data": null`로 온다 — 빈 배열이 아니다."""
        assert parse_daily(fixture("leash_empty.json"), last_day=LAST) == []

    @pytest.mark.parametrize(
        "field", ["last_openRaw", "last_maxRaw", "last_minRaw", "last_closeRaw"])
    def test_가격을_읽지_못한_행이_있으면_청크_전체가_형식_오류다(self, field: str) -> None:
        """analyze M2 — 그 행만 버리면 그날이 출처 결측으로 표시된다."""
        body = json.loads(fixture("btc_2011_06.json"))
        body["data"][3][field] = "-"
        with pytest.raises(InvestingFormatError) as err:
            parse_daily(json.dumps(body), last_day=LAST)
        assert field in str(err.value)
        assert body["data"][3]["rowDateTimestamp"][:10] in str(err.value)

    def test_가격이_빠져도_형식_오류다(self) -> None:
        body = json.loads(fixture("btc_2011_06.json"))
        del body["data"][0]["last_closeRaw"]
        with pytest.raises(InvestingFormatError):
            parse_daily(json.dumps(body), last_day=LAST)

    def test_같은_날짜가_두_번이면_형식_오류다(self) -> None:
        body = json.loads(fixture("btc_2011_06.json"))
        body["data"].append(body["data"][0])
        with pytest.raises(InvestingFormatError):
            parse_daily(json.dumps(body), last_day=LAST)

    def test_상한_근처_행_수는_형식_오류다(self) -> None:
        """출처는 약 5,000행에서 표시 없이 자른다 — 잘린 구간을 받은 것으로 기록하지 않는다."""
        body = json.loads(fixture("btc_2011_06.json"))
        row = body["data"][0]
        start = D("2000-01-01")
        body["data"] = [dict(row, rowDateTimestamp=f"{start + dt.timedelta(days=i)}T00:00:00Z")
                        for i in range(ROW_LIMIT_GUARD)]
        with pytest.raises(InvestingFormatError):
            parse_daily(json.dumps(body), last_day=LAST)

    @pytest.mark.parametrize("body", ["403", "<html></html>", '{"result": []}'])
    def test_형식이_다르면_형식_오류다(self, body: str) -> None:
        with pytest.raises(InvestingFormatError):
            parse_daily(body, last_day=LAST)
