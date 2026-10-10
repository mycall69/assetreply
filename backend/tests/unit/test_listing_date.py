"""상장일 고르기 규칙 (014 반복 2026-10-10f T159) — FR-033, data-model §12, research R14-26.

주식은 키움 국내 상장일이 먼저고, 없으면 Yahoo 첫 거래일(출처가 시세를 가진 첫 날), 둘 다 없으면
없음이다. 코인은 출처가 상장일을 주지 않아 수집으로 알게 된 첫 일봉이다. 모르면 지어내지 않는다(헌법
원칙 V).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.comparison_metrics import comparison_block
from src.simulation.comparison_costs import stock_costs
from src.simulation.listing_date import ListingDate, coin_listing_date, stock_listing_date

D = dt.date.fromisoformat


class Test주식:
    def test_키움_상장일이_먼저다(self) -> None:
        """국내는 Yahoo 첫 거래일이 출처의 시세 시작일(2000-01-04)이다.

        상장일(1975-06-11)이 먼저다(T158).
        """
        assert stock_listing_date(D("1975-06-11"), D("2000-01-04")) == ListingDate(
            D("1975-06-11"), "listing")

    def test_키움이_없으면_Yahoo_첫_거래일이다(self) -> None:
        assert stock_listing_date(None, D("2010-09-09")) == ListingDate(
            D("2010-09-09"), "first_trade")

    def test_둘_다_없으면_없음이다(self) -> None:
        assert stock_listing_date(None, None) is None


class Test코인:
    def test_첫_일봉이다(self) -> None:
        assert coin_listing_date(D("2010-07-18")) == ListingDate(D("2010-07-18"), "first_bar")

    def test_모르면_없음이다(self) -> None:
        assert coin_listing_date(None) is None


class Test비교_블록:
    SUMMARY: dict[str, object] = {
        "principal": "10000000", "profit": "1000000", "returnRate": "0.100000",
        "asOf": "2026-10-07", "isFinal": True, "totalKrw": "11000000"}
    COSTS = stock_costs(buy_fee=Decimal("100"), dividend_tax=Decimal("0"), sale_fee=None,
                        sale_tax=None, tax_kind=None)

    def test_넘기지_않으면_null이다(self) -> None:
        """예금·부동산 경로는 넘기지 않는다 — 대상에 상장일이 없다."""
        assert comparison_block("deposit", self.SUMMARY, self.COSTS)["listing"] is None

    def test_날짜와_기준을_싣는다(self) -> None:
        block = comparison_block("stock_lump", self.SUMMARY, self.COSTS,
                                 listing=ListingDate(D("2010-09-09"), "first_trade"))
        assert block["listing"] == {"date": "2010-09-09", "basis": "first_trade"}
