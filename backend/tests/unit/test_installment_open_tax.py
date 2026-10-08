"""정기 적금 진행 중 계약의 경과 이자 소득세 (013 T040) — FR-011, SC-001, data-model 4.

`simulate_installment_ladder`는 기준일에 진행 중인 적금·정기예금의 경과 이자에서 세금을 빼 평가한다.
그 세금 합을 `LadderSummary.open_tax`로 내놓는다 — 비교 표의 비용(이미 반영된 몫)이 평가액과 같은
수에서 나온다. 메뉴의 "이자 소득세 합계"(`tax_total`)는 만기분만이라 그대로다.

참조값은 `test_installment_ladder`의 손계산(research R11-8)이다 — 2016-07-01: 적금 2 경과 세금
4,161(평가 6,022,859), 정기예금 1 경과 세금 14,745(평가 12,208,580).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.installment_ladder import LadderOutcome, simulate_installment_ladder

D = dt.date.fromisoformat
M = Decimal
TAX = M("0.154")
ISAV = {D("2015-01-01"): M("2.32"), D("2016-01-01"): M("1.79"), D("2017-01-01"): M("1.5"),
        D("2017-12-01"): M("1.75"), D("2018-01-01"): M("1.82")}
DEP = {D("2016-01-01"): M("1.72"), D("2017-01-01"): M("1.58"), D("2017-12-01"): M("1.91"),
       D("2018-01-01"): M("1.93")}


def run(end: str, **over: object) -> LadderOutcome:
    args: dict[str, object] = dict(
        monthly=M("1000000"), start=D("2015-01-15"), end=D(end),
        installment_rates=ISAV, installment_first=D("2003-01-01"),
        installment_latest=D("2018-01-01"), deposit_rates=DEP, deposit_first=D("2012-01-01"),
        deposit_latest=D("2018-01-01"), tax_rate=TAX)
    args.update(over)
    return simulate_installment_ladder(**args)  # type: ignore[arg-type]


class Test진행_중_계약:
    def test_적금과_정기예금의_경과_세금_합이다(self) -> None:
        s = run("2016-07-01").summary
        assert s.open_tax == M("4161") + M("14745")

    def test_평가액은_그대로다(self) -> None:
        s = run("2016-07-01").summary
        assert (s.installment_value, s.deposit_value) == (M("6022859"), M("12208580"))
        assert s.balance == M("18231439")

    def test_첫_해는_적금만이다(self) -> None:
        # 2015-07-01: 낸 6회, 경과 이자 34,948 → 세금 5,381(정기예금은 아직 없다).
        s = run("2015-07-01").summary
        assert s.open_tax == M("5381")
        assert s.installment_value == M("6029567")


class Test만기분과_따로:
    def test_tax_total은_만기분만이다(self) -> None:
        s = run("2016-07-01").summary
        # 첫 적금(2015-01-15 → 2016-01-15)의 만기 세금만 — 진행 중 계약의 경과 세금은 들지 않는다.
        assert s.tax_total == sum((c.tax for c in run("2016-07-01").contracts), M(0))
        assert s.open_tax not in (M(0), s.tax_total)

    def test_멈추면_0이다(self) -> None:
        # 2016-01 정기예금 금리가 없으면 첫 만기(2016-01-15)에서 멈춘다.
        outcome = run("2016-07-01", deposit_rates={k: v for k, v in DEP.items()
                                                    if k != D("2016-01-01")})
        assert outcome.summary.stopped is not None
        assert outcome.summary.open_tax == 0
