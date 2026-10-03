"""KRW 평가 공용 함수 (T005) — 007 FR-035, research R7-8, 006 FR-068.

006(T142)이 주식 서비스 안에 둔 KRW 평가식을 **순수 함수 하나**로 옮겨 주식·가상자산이 함께 쓴다. 두
벌 두면 한쪽만 고쳐질 때 이력 비교의 기준이 갈라진다.

투자 수익 = (잔고 + 예수금) × 그 행의 매매기준율(KRW 자릿수로 맞춤) − KRW 원금, 수익율 = 투자 수익 ÷
KRW 원금(소수 6자리), 잔고 KRW = 잔고 × 매매기준율(KRW 자릿수).
"""
from __future__ import annotations

from decimal import Decimal

from src.simulation.fx_convert import evaluate_krw


def test_수익과_수익율과_잔고_KRW() -> None:
    # 잔고 1,100달러 + 예수금 76.35달러 = 1,176.35달러 × 1,190 = 1,399,856.5
    # → KRW 0자리(짝수 반올림) 1,399,856
    got = evaluate_krw(Decimal("1100"), Decimal("76.35"), Decimal("1190"), Decimal("1150000"))
    assert got.profit == Decimal("249856")
    assert got.return_rate == Decimal("0.217266")
    assert got.balance_krw == Decimal("1309000")


def test_원금이_0이면_수익율은_0이다() -> None:
    """0으로 나누는 경로를 만들지 않는다(005와 같다)."""
    got = evaluate_krw(Decimal("10"), Decimal("0"), Decimal("1000"), Decimal("0"))
    assert got.return_rate == Decimal("0")


def test_손실은_음수다() -> None:
    got = evaluate_krw(Decimal("500"), Decimal("0"), Decimal("1000"), Decimal("1000000"))
    assert got.profit == Decimal("-500000")
    assert got.return_rate == Decimal("-0.500000")
