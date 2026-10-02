"""미국 목록 파싱 (T065) — 006 FR-011, FR-018, research R6-2.

T005의 **실제 응답**으로 검증한다. 미국 12,745건 모두 한글 종목명(`stk_nm`)이 있다(`AAPL` → 애플).
`isEtf`는 `Y`·`N`·빈 값이며 빈 값은 주식으로 둔다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.kiwoom.errors import KiwoomInvalidResponse, KiwoomRateLimited
from src.ingestion.kiwoom.parse import ListingRow, parse_listing, parse_us, source_of

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "kiwoom"


def body(unit: str) -> str:
    return (FIXTURES / f"{unit}_p01.json").read_text(encoding="utf-8")


def by_code(unit: str) -> dict[str, ListingRow]:
    return {r.code: r for r in parse_us(unit, [body(unit)])}


def edited(unit: str, edit) -> str:  # type: ignore[no-untyped-def]
    data = json.loads(body(unit))
    edit(data["list"])
    return json.dumps(data, ensure_ascii=False)


class Test실제_응답:
    @pytest.mark.parametrize(("unit", "count"), [("NYSE", 5581), ("NASDAQ", 5211),
                                                   ("AMEX", 1953)])
    def test_전부_남긴다(self, unit: str, count: int) -> None:
        rows = parse_us(unit, [body(unit)])
        assert len(rows) == count
        assert {r.unit for r in rows} == {unit}
        assert {r.country for r in rows} == {"US"}

    def test_애플(self) -> None:
        assert by_code("NASDAQ")["AAPL"] == ListingRow(
            country="US", code="AAPL", unit="NASDAQ", name_ko="애플", name_en="APPLE INC",
            kind="stock", listed_on=None)

    def test_ETF_여부(self) -> None:
        rows = parse_us("NYSE", [body("NYSE")])
        assert sum(r.kind == "etf" for r in rows) == 2797
        # isEtf가 빈 4건은 주식으로 둔다
        assert sum(r.kind == "stock" for r in rows) == 2780 + 4
        assert by_code("NYSE")["SPY"].kind == "etf"

    def test_티커를_출처_표기_그대로_둔다(self) -> None:
        """시세 출처 표기로 옮기는 것은 price_symbol의 일이다 (research R6-6)."""
        rows = by_code("NYSE")
        for code in ("BRKb", "BH.A", "ABR-D", "BAC_pe"):
            assert code in rows

    def test_상장일이_없다(self) -> None:
        assert {r.listed_on for r in parse_us("AMEX", [body("AMEX")])} == {None}

    def test_단위로_파서를_고른다(self) -> None:
        assert len(parse_listing("AMEX", [body("AMEX")])) == 1953
        assert source_of("NYSE") == "kiwoom:usa10099"
        assert source_of("KOSPI") == "kiwoom:ka10099"


class Test단위_전체의_실패:
    def test_다른_거래소의_목록이면(self) -> None:
        """NYSE를 요청했는데 NASDAQ 행이 오면 단위가 뒤바뀐다."""
        with pytest.raises(KiwoomInvalidResponse):
            parse_us("NASDAQ", [body("NYSE")])

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_티커가_비면(self, bad: str) -> None:
        def corrupt(rows: list[dict[str, str]]) -> None:
            rows[3]["stk_cd"] = bad

        with pytest.raises(KiwoomInvalidResponse):
            parse_us("AMEX", [edited("AMEX", corrupt)])

    def test_같은_티커가_두_번_오면(self) -> None:
        def duplicate(rows: list[dict[str, str]]) -> None:
            rows.append(dict(rows[0]))

        with pytest.raises(KiwoomInvalidResponse):
            parse_us("AMEX", [edited("AMEX", duplicate)])

    def test_국내_단위는_거절한다(self) -> None:
        with pytest.raises(ValueError):
            parse_us("KOSPI", [body("NYSE")])


class Test부가_필드:
    def test_이름이_비면_None(self) -> None:
        def blank(rows: list[dict[str, str]]) -> None:
            rows[0]["stk_nm"] = " "

        rows = parse_us("AMEX", [edited("AMEX", blank)])
        assert rows[0].name_ko is None and rows[0].name_en

    def test_여러_쪽을_잇는다(self) -> None:
        data = json.loads(body("AMEX"))
        first = dict(data, list=data["list"][:900])
        second = dict(data, list=data["list"][900:])
        assert len(parse_us("AMEX", [json.dumps(first), json.dumps(second)])) == 1953


class Test한도_초과_중간_쪽:
    async def test_받은_쪽을_돌려주지_않고_rate_limit으로_끝난다(
            self, no_sleep: list[float]) -> None:
        """FR-018 — 반쯤 받은 목록을 돌려주면 뒤쪽 종목이 사라진다. 한도는 그 자리에서 다시
        시도하지 않는다(간격을 두고 다음 갱신에서)."""
        from tests.contract.test_kiwoom_client import TOKEN, TOKEN_OK, US, Resp, Session, client

        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     US: [Resp(body("NYSE"), headers={"cont-yn": "Y", "next-key": "K"}),
                          Resp((FIXTURES / "error_rate_limit.json").read_text(encoding="utf-8"))]})
        async with client(s) as c:
            with pytest.raises(KiwoomRateLimited):
                await c.fetch_unit("NYSE")
        assert s.count(US) == 2
