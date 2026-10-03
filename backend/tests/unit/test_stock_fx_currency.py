"""환율 판정 통화 (T005) — 007 FR-036, research R7-8.

`fx_currency_for`는 **통화 문자열**을 받는다 — 주식과 가상자산이 함께 쓴다. 원금 통화를 보지
않는다(006 FR-068): 시세 통화가 KRW가 아니면 원금 통화와 관계없이 KRW 평가에 환율이 필요하다.
"""
from __future__ import annotations

import pytest

from src.api.services.stock_fx import fx_currency_for


@pytest.mark.parametrize(("currency", "expected"), [
    ("KRW", None), ("USD", "USD"), ("JPY", "JPY"), ("EUR", "EUR"), ("GBP", None)])
def test_시세_통화로_판정한다(currency: str, expected: str | None) -> None:
    assert fx_currency_for(currency) == expected
