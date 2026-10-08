"""정기예금 진행 중 회차의 경과 이자 소득세 (013 T007) — FR-011, SC-001, data-model 4.

`simulate_deposit`은 계산 끝이 회차 안이면 경과 이자의 세금을 평가액에서 뺀다. 그 값을
`Summary.accrued_tax`로 내놓는다 — 비교 표의 비용(이미 반영된 몫)이 평가액과 같은 수에서 나온다.
기존 값(`balance`·`profit`·`return_rate`·`terms`)은 바뀌지 않는다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.deposit_rollover import accrued_interest, interest_tax, simulate_deposit

D = dt.date.fromisoformat
P = Decimal
TAX = P("0.154")
FIRST = D("2012-01-01")
LATEST = D("2026-08-01")

# test_deposit_rollover와 같은 실측 금리(research R8-7). 나머지 달은 2.00이다.
REAL = {"2020-01": "1.62", "2021-01": "0.97", "2022-01": "1.83", "2023-01": "4.15",
        "2024-01": "3.65", "2025-01": "3.06", "2026-01": "2.84"}


def months(first: dt.date, last: dt.date) -> list[dt.date]:
    out, cur = [], first
    while cur <= last:
        out.append(cur)
        cur = cur.replace(year=cur.year + cur.month // 12, month=cur.month % 12 + 1)
    return out


def rates(drop: tuple[str, ...] = ()) -> dict[dt.date, Decimal]:
    table = {m: P(REAL.get(m.strftime("%Y-%m"), "2.00")) for m in months(FIRST, LATEST)}
    for k in drop:
        del table[D(k + "-01")]
    return table


def run(end: str, drop: tuple[str, ...] = ()):  # type: ignore[no-untyped-def]
    return simulate_deposit(principal=P("10000000"), start=D("2020-01-15"), end=D(end),
                            rates=rates(drop), first_month=FIRST, latest_month=LATEST,
                            tax_rate=TAX)


class Test진행_중_회차:
    def test_경과_이자의_세금이다(self) -> None:
        outcome = run("2026-10-04")
        s = outcome.summary
        term = s.current_term
        assert term is not None
        accrued = accrued_interest(term.principal, term.rate, term.joined_on, term.matures_on,
                                   s.as_of)
        assert accrued > 0
        assert s.accrued_tax == interest_tax(accrued, TAX)
        assert s.accrued_tax > 0

    def test_평가액은_회차_원금_더하기_경과_이자_빼기_세금이다(self) -> None:
        s = run("2026-10-04").summary
        term = s.current_term
        assert term is not None
        accrued = accrued_interest(term.principal, term.rate, term.joined_on, term.matures_on,
                                   s.as_of)
        assert s.balance == term.principal + accrued - s.accrued_tax
        assert s.profit == s.balance - P("10000000")


class Test없는_경우:
    def test_계산_끝이_만기일이면_0이다(self) -> None:
        assert run("2021-01-15").summary.accrued_tax == 0

    def test_재예치_달이_결측으로_멈추면_0이다(self) -> None:
        # 2023-01 금리가 없으면 2023-01-15 만기의 재예치에서 멈춘다(FR-019).
        outcome = run("2026-10-04", drop=("2023-01",))
        assert outcome.summary.stopped is not None
        assert outcome.summary.accrued_tax == 0


class Test기존_값_불변:
    def test_끝난_회차의_세금과_평가액이_그대로다(self) -> None:
        outcome = run("2026-10-04")
        # 회차 원금은 앞 회차의 (원금 + 세후 이자)다 — 끝난 회차 여섯의 사슬이 그대로다.
        assert [t.joined_on for t in outcome.terms] == [
            D(f"{y}-01-15") for y in range(2020, 2026)]
        held = P("10000000")
        for term in outcome.terms:
            assert term.principal == held
            assert term.after_tax == term.interest - term.tax
            held = term.principal + term.after_tax
        assert outcome.summary.current_term is not None
        assert outcome.summary.current_term.principal == held
