"""주식 적립식 응답의 금액 문자열 (011 T030 실측에서 찾은 결함) — contracts/rest-api 공통 규약.

재투자일에 배당을 옮기고 나면 배당 현금이 `Decimal("0E-12")`(지수 표기의 0)가 된다. `str()`이 그대로 내보내면 화면이 "0E12"로 보인다(T030 브라우저 실측).
금액·비율 문자열은 **지수 표기가 없어야** 한다 — 0은 "0", 나머지는 고정 소수점이다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.stock_recurring import RecurringView, row_json
from src.simulation.recurring_stock import RecurringRow

D = dt.date.fromisoformat
M = Decimal


def view(**over: Decimal) -> RecurringView:
    row = RecurringRow(
        date=D("2026-09-30"), kind="reinvest", open_price=M("10000.000000"), close_price=M("10000.000000"),
        bought_shares=0, held_shares=5, pending=over.get("pending", M("846.000")),
        dividend_cash=over.get("dividend_cash", M("0E-12")), contributed=M("50000"), basis_krw=M("50000"),
        contributions=5, balance=M("50000.000000"), total=M("50846.000"), profit=M("846.000"),
        return_rate=M("0.016920"))
    return RecurringView(row=row, contribution=None, contributed=M("50000"), profit=M("846.000"),
                         return_rate=M("0.016920"), total_krw=M("50846.000"))


def test_지수_표기의_0은_0이다() -> None:
    body = row_json(view())
    assert body["dividendCash"] == "0"
    assert "E" not in "".join(str(v) for v in body.values())


def test_아주_작은_값도_고정_소수점이다() -> None:
    body = row_json(view(pending=M("1E-7")))
    assert body["pending"] == "0.0000001"
