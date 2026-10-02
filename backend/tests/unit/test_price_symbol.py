"""목록 → 005 시세 식별자 (T016) — 006 FR-010a, FR-030, FR-030b, FR-031, research R6-6.

**시장을 틀리면** 시세 출처가 그 종목을 찾지 못해 "시세 없음"이 되고, 사용자는 그 종목에
데이터가 없다고 읽는다. 역변환이 정방향과 왕복하지 않으면 검색에서 고른 종목은 되는데 같은
종목의 이력 재실행만 "알 수 없는 종목"이 된다 (SC-007a).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search.price_symbol import PriceSymbol, listing_candidates, to_price_symbol

FIXTURES = Path(__file__).resolve().parent.parent / "contract" / "fixtures" / "kiwoom"


class Test국내_정방향:
    @pytest.mark.parametrize(("unit", "code", "expected"), [
        ("KOSPI", "005930", PriceSymbol("KRX", "005930.KS", "KRW")),   # 주식
        ("KOSPI", "069500", PriceSymbol("KRX", "069500.KS", "KRW")),   # ETF
        ("KOSPI", "0030R0", PriceSymbol("KRX", "0030R0.KS", "KRW")),   # 리츠
        ("KOSDAQ", "247540", PriceSymbol("KRX", "247540.KQ", "KRW")),
    ])
    def test_표(self, unit: str, code: str, expected: PriceSymbol) -> None:
        assert to_price_symbol(unit, code) == expected

    def test_ETF_리츠는_상품_구분이_아니라_거래_시장을_따른다(self) -> None:
        """FR-010a — ETF·리츠는 유가증권시장에서 거래된다. 함수가 상품 구분을 받지 않는다."""
        assert to_price_symbol("KOSPI", "069500").symbol.endswith(".KS")

    def test_코스닥을_코스피로_옮기지_않는다(self) -> None:
        """FR-031."""
        assert to_price_symbol("KOSDAQ", "091990").symbol == "091990.KQ"

    def test_모르는_단위는_거절한다(self) -> None:
        with pytest.raises(ValueError):
            to_price_symbol("KONEX", "123456")


class Test국내_역변환:
    @pytest.mark.parametrize(("market", "symbol", "code"), [
        ("KRX", "005930.KS", "005930"),
        ("KRX", "247540.KQ", "247540"),
        ("KRX", "0030R0.KS", "0030R0"),
    ])
    def test_접미사를_떼어_국내_코드로(self, market: str, symbol: str, code: str) -> None:
        key = listing_candidates(market, symbol)
        assert key is not None
        assert key.country == "KR"
        assert key.codes == (code,)

    @pytest.mark.parametrize(("market", "symbol"), [
        ("KRX", "005930"),        # 접미사 없음
        ("KRX", "005930.T"),
        ("TSE", "7203.T"),        # 일본은 목록이 없다
        ("LSE", "VOD.L"),
    ])
    def test_찾을_수_없는_식별자(self, market: str, symbol: str) -> None:
        assert listing_candidates(market, symbol) is None


@pytest.mark.parametrize("unit", ["KOSPI", "KOSDAQ"])
def test_실제_목록_전부가_왕복한다(unit: str) -> None:
    """목록 → 시세 식별자 → 목록이 같은 종목이어야 한다 (SC-007a, research R6-6)."""
    body = json.loads((FIXTURES / f"{unit}_p01.json").read_text(encoding="utf-8"))
    codes = [row["code"] for row in body["list"]]
    assert codes
    symbols = set()
    for code in codes:
        ps = to_price_symbol(unit, code)
        symbols.add(ps.symbol)
        key = listing_candidates(ps.market, ps.symbol)
        assert key is not None and key.country == "KR" and key.codes[0] == code, code
    # 정방향 결과가 서로 겹치지 않는다
    assert len(symbols) == len(set(codes))


# ── 미국 (T066) ──────────────────────────────────────────────────────

US_FORWARD = [
    # 기호 없음 — 대부분
    ("NASDAQ", "AAPL", "AAPL"),
    # BASE.SUF — 클래스·유닛
    ("NYSE", "BH.A", "BH-A"),
    ("NYSE", "AAC.UN", "AAC-UN"),
    # BASE + 소문자 — 클래스
    ("NYSE", "BRKb", "BRK-B"),
    ("NYSE", "BFa", "BF-A"),
    # BASE-SER — 우선주(시리즈)
    ("NYSE", "ABR-D", "ABR-PD"),
    ("AMEX", "PHXE-", "PHXE-P"),
    # BASE_p + 소문자 — 우선주(시리즈)
    ("NYSE", "BAC_pe", "BAC-PE"),
    ("NYSE", "AHT_pd", "AHT-PD"),
]


class Test미국_정방향:
    @pytest.mark.parametrize(("unit", "code", "symbol"), US_FORWARD)
    def test_표(self, unit: str, code: str, symbol: str) -> None:
        """research R6-6 — 시세 출처 표기는 실제 조회로 확인했다(2026-10-02)."""
        assert to_price_symbol(unit, code) == PriceSymbol(unit, symbol, "USD")

    def test_규칙에_없는_기호는_그대로_보낸다(self) -> None:
        """시세 출처가 모르면 "시세 출처에서 찾지 못함"으로 알린다(FR-032)."""
        assert to_price_symbol("NYSE", "AB$C").symbol == "AB$C"

    def test_거래소를_다른_거래소로_옮기지_않는다(self) -> None:
        """FR-031."""
        assert to_price_symbol("NASDAQ", "AAPL").market == "NASDAQ"


class Test미국_역변환:
    @pytest.mark.parametrize(("market", "symbol", "codes"), [
        ("NASDAQ", "AAPL", ("AAPL",)),
        ("NYSE", "BRK-B", ("BRK.B", "BRKb", "BRK-B")),
        ("NYSE", "BH-A", ("BH.A", "BHa", "BH-A")),
        ("NYSE", "ABR-PD", ("ABR-D", "ABR_pd", "ABR.PD", "ABRpd", "ABR-PD")),
        ("AMEX", "PHXE-P", ("PHXE-", "PHXE_p", "PHXE.P", "PHXEp", "PHXE-P")),
        ("NYSE", "BAC-PE", ("BAC-E", "BAC_pe", "BAC.PE", "BACpe", "BAC-PE")),
    ])
    def test_후보(self, market: str, symbol: str, codes: tuple[str, ...]) -> None:
        key = listing_candidates(market, symbol)
        assert key is not None and key.country == "US"
        assert key.codes == codes

    def test_거래소는_보지_않는다(self) -> None:
        """FR-030a — 같은 티커면 거래소가 달라도 같은 종목이다."""
        for market in ("NYSE", "NASDAQ", "AMEX"):
            key = listing_candidates(market, "SPY")
            assert key is not None and key.codes == ("SPY",)


def _us_codes() -> dict[str, list[str]]:
    return {unit: [row["stk_cd"] for row in json.loads(
        (FIXTURES / f"{unit}_p01.json").read_text(encoding="utf-8"))["list"]]
        for unit in ("NYSE", "NASDAQ", "AMEX")}


def test_미국_목록_전부가_왕복하고_겹치지_않는다() -> None:
    """research R6-6 — 12,745건에서 정방향 결과가 겹치지 않고, 역변환 후보 중 **목록에 있는 첫
    것**이 원래 기호다(SC-007a, SC-008)."""
    codes = _us_codes()
    every = {c for unit_codes in codes.values() for c in unit_codes}
    symbols: set[str] = set()
    total = 0
    for unit, unit_codes in codes.items():
        for code in unit_codes:
            ps = to_price_symbol(unit, code)
            symbols.add(ps.symbol)
            key = listing_candidates(ps.market, ps.symbol)
            assert key is not None, code
            found = next(c for c in key.codes if c in every)
            assert found == code, (code, ps.symbol, found)
            total += 1
    assert total == 12745
    assert len(symbols) == total
