"""정기 적금 → 정기예금 사다리 (011 T041) — FR-024~FR-028, FR-030, SC-001, SC-005, research R11-8.

**순수 함수다** — DB·HTTP 없이 돈다(헌법 원칙 IV). 금리는 시중은행 실측(T003·008 T001 픽스처)의
일부를 상수로 둔다.

손계산(월 1,000,000원, 세율 15.4%, 2015-01-15 시작):

- 적금 1: 2015-01-15 가입, 2015-01 정기적금(1-2년) 2.32%, 만기 2016-01-15
  - 회차 이자 = 1,000,000 × 2.32 × (12 − i) ÷ 1200
  - 만기 이자 = trunc(Σ) = 1,000,000 × 2.32 × 78 ÷ 1200 = 150,800
    (모든 회차에 12개월을 붙이면 278,400 — 약 두 배, FR-025 실패 양상)
  - 세금 trunc(150,800 × 0.154) = 23,223, 세후 127,577, 만기 금액 12,127,577
- 2016-01-15 — 정기예금 1 가입(원금 12,127,577 = 적금 1 만기 금액, 2016-01 정기예금(1년) 1.72%),
  같은 날 적금 2 첫 회(2016-01 1.79%)
- 2017-01-15
  - 적금 2 만기: 이자 1,000,000 × 1.79 × 78 ÷ 1200 = 116,350, 세금 17,917, 만기 금액 12,098,433
  - 정기예금 1 만기: 이자 trunc(12,127,577 × 1.72 ÷ 100) = 208,594, 세금 32,123,
    만기 금액 12,304,048
  - 정기예금 2 가입: 원금 12,304,048 + 12,098,433 = 24,402,481(2017-01 1.58%)
  - 적금 3 첫 회(2017-01 1.5%)
- 2018-01-15
  - 적금 3 만기: 이자 97,500, 세금 15,015, 만기 금액 12,082,485
  - 정기예금 2 만기: 이자 trunc(24,402,481 × 1.58 ÷ 100) = 385,559, 세금 59,376,
    만기 금액 24,728,664
  - 정기예금 3 가입: 원금 24,728,664 + 12,082,485 = 36,811,149(2018-01 1.93%)
  - 적금 4 첫 회(2018-01 1.82%)
- 2018-01-15 기준 보드
  - 납입 37회 = 37,000,000
  - 평가 = 적금 4(1,000,000, 경과 이자 0) + 정기예금 3(36,811,149) = 37,811,149
  - 수익 811,149, 수익률 0.021923
  - 이자 합 958,803, 세금 합 147,654, 세후 합 811,149
- 경과 평가(R11-8 — 경과 이자 합을 한 번 버린 뒤 세금)
  - 2015-07-01: 낸 6회(6,000,000)
    - 경과 이자 = trunc(Σᵢ 1,000,000 × 2.32 × (12 − i) × 경과ᵢ ÷ (1200 × 기간ᵢ)) = 34,948
      - 기간ᵢ·경과ᵢ(일) = (365, 167)·(334, 136)·(306, 108)·(275, 77)·(245, 47)·(214, 16)
    - 세금 5,381 → 6,029,567
  - 2016-07-01
    - 적금 2: 6,000,000 + 27,020 − 4,161 = 6,022,859
    - 정기예금 1: 경과 이자 trunc(12,127,577 × 1.72 × 168 ÷ (100 × 366)) = 95,748, 세금 14,745
      → 12,208,580
    - 합 18,231,439, 납입 18,000,000, 수익률 0.012858
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.deposit_rollover import BeforeFirstMonth, RateMissing, Stopped
from src.simulation.installment_ladder import (
    LadderOutcome,
    LadderRow,
    simulate_installment_ladder,
)

D = dt.date.fromisoformat
M = Decimal
TAX = M("0.154")

ISAV = {D("2015-01-01"): M("2.32"), D("2016-01-01"): M("1.79"), D("2017-01-01"): M("1.5"),
        D("2017-12-01"): M("1.75"), D("2018-01-01"): M("1.82")}
DEP = {D("2016-01-01"): M("1.72"), D("2017-01-01"): M("1.58"), D("2017-12-01"): M("1.91"),
       D("2018-01-01"): M("1.93")}


def run(**over: object) -> LadderOutcome:
    args: dict[str, object] = dict(
        monthly=M("1000000"), start=D("2015-01-15"), end=D("2018-01-15"),
        installment_rates=ISAV, installment_first=D("2003-01-01"),
        installment_latest=D("2018-01-01"), deposit_rates=DEP, deposit_first=D("2012-01-01"),
        deposit_latest=D("2018-01-01"), tax_rate=TAX)
    args.update(over)
    return simulate_installment_ladder(**args)  # type: ignore[arg-type]


def without(rates: dict[dt.date, Decimal], month: str) -> dict[dt.date, Decimal]:
    return {k: v for k, v in rates.items() if k != D(month)}


def installment_dates(outcome: LadderOutcome, contract_no: int) -> list[dt.date]:
    return sorted(r.date for r in outcome.rows
                  if r.kind == "installment" and r.contract_no == contract_no)


def on(outcome: LadderOutcome, day: str) -> list[LadderRow]:
    """그날의 행 — 표 순서(최신순, 같은 날은 나중 사건이 위)."""
    return [r for r in outcome.rows if r.date == D(day)]


class Test세_주기:
    def test_만기된_적금은_회차마다_단리다(self) -> None:
        contracts = run().contracts
        assert [(c.no, c.joined_on, c.matures_on, c.rate, c.paid, c.interest, c.tax, c.after_tax,
                 c.amount) for c in contracts] == [
            (1, D("2015-01-15"), D("2016-01-15"), M("2.32"), 12, M(150800), M(23223), M(127577),
             M(12127577)),
            (2, D("2016-01-15"), D("2017-01-15"), M("1.79"), 12, M(116350), M(17917), M(98433),
             M(12098433)),
            (3, D("2017-01-15"), D("2018-01-15"), M("1.5"), 12, M(97500), M(15015), M(82485),
             M(12082485)),
        ]
        assert all(c.monthly == M(1000000) and not c.provisional for c in contracts)
        assert contracts[0].rate_month == D("2015-01-01")

    def test_정기예금_원금은_앞_정기예금_만기_금액과_적금_만기_금액의_합이다(self) -> None:
        deposits = run().deposits
        assert [(d.no, d.joined_on, d.matures_on, d.rate, d.principal, d.from_deposit,
                 d.from_installment, d.interest, d.tax, d.after_tax) for d in deposits] == [
            (1, D("2016-01-15"), D("2017-01-15"), M("1.72"), M(12127577), M(0), M(12127577),
             M(208594), M(32123), M(176471)),
            (2, D("2017-01-15"), D("2018-01-15"), M("1.58"), M(24402481), M(12304048),
             M(12098433), M(385559), M(59376), M(326183)),
        ]

    def test_보드(self) -> None:
        s = run().summary
        assert (s.contributed, s.installment_value, s.deposit_value, s.balance) == (
            M(37000000), M(1000000), M(36811149), M(37811149))
        assert (s.profit, s.return_rate) == (M(811149), M("0.021923"))
        assert (s.interest_total, s.tax_total, s.after_tax_total) == (M(958803), M(147654),
                                                                      M(811149))
        assert (s.as_of, s.is_final, s.provisional_from, s.stopped) == (
            D("2018-01-15"), True, None, None)

    def test_진행_중인_적금과_정기예금(self) -> None:
        s = run().summary
        assert s.current_installment is not None and s.current_deposit is not None
        i, d = s.current_installment, s.current_deposit
        assert (i.no, i.joined_on, i.matures_on, i.rate, i.rate_month, i.provisional, i.paid) == (
            4, D("2018-01-15"), D("2019-01-15"), M("1.82"), D("2018-01-01"), False, 1)
        assert (d.no, d.joined_on, d.matures_on, d.rate, d.principal, d.provisional) == (
            3, D("2018-01-15"), D("2019-01-15"), M("1.93"), M(36811149), False)


class Test만기일:
    def test_같은_날의_행은_따로이고_나중_사건이_위다(self) -> None:
        outcome = run()
        assert [r.kind for r in on(outcome, "2016-01-15")] == [
            "installment", "deposit_join", "installment_maturity"]
        assert [r.kind for r in on(outcome, "2017-01-15")] == [
            "installment", "deposit_join", "deposit_maturity", "installment_maturity"]

    def test_만기_행은_이자·세금·만기_금액이다(self) -> None:
        rows = {r.kind: r for r in on(run(), "2017-01-15")}
        saving, deposit = rows["installment_maturity"], rows["deposit_maturity"]
        assert (saving.contract_no, saving.interest, saving.tax, saving.after_tax,
                saving.amount) == (2, M(116350), M(17917), M(98433), M(12098433))
        assert (deposit.contract_no, deposit.interest, deposit.tax, deposit.amount) == (
            1, M(208594), M(32123), M(12304048))
        # 만기일의 평가는 실제로 받는 만기 금액의 합이다(FR-028)
        assert saving.balance == deposit.balance == M(12098433) + M(12304048)

    def test_가입_행은_구성을_싣고_노는_돈이_없다(self) -> None:
        rows = {r.kind: r for r in on(run(), "2017-01-15")}
        join = rows["deposit_join"]
        assert (join.contract_no, join.amount, join.from_deposit, join.from_installment,
                join.rate) == (2, M(24402481), M(12304048), M(12098433), M("1.58"))
        assert (join.installment_value, join.deposit_value, join.balance) == (
            M(0), M(24402481), M(24402481))
        first = rows["installment"]
        assert (first.contract_no, first.installment_no, first.amount, first.rate) == (
            3, 1, M(1000000), M("1.5"))
        assert (first.installment_value, first.deposit_value, first.balance, first.contributed) == (
            M(1000000), M(24402481), M(25402481), M(25000000))

    def test_첫_만기에는_정기예금_만기가_없다(self) -> None:
        join = next(r for r in on(run(), "2016-01-15") if r.kind == "deposit_join")
        assert (join.from_deposit, join.from_installment, join.amount) == (
            M(0), M(12127577), M(12127577))


class Test경과_평가:
    def test_적금_쪽은_낸_회차_합과_경과_세후_이자다(self) -> None:
        row = on(run(), "2015-07-01")
        assert [r.kind for r in row] == ["month"]
        month = row[0]
        assert (month.contributed, month.installment_value, month.deposit_value, month.balance) == (
            M(6000000), M(6029567), M(0), M(6029567))
        assert (month.profit, month.return_rate) == (M(29567), M("0.004928"))
        assert (month.rate, month.amount, month.contract_no) == (None, None, None)

    def test_정기예금_쪽은_원금과_경과_세후_이자다(self) -> None:
        month = on(run(), "2016-07-01")[0]
        assert (month.installment_value, month.deposit_value, month.balance, month.contributed) == (
            M(6022859), M(12208580), M(18231439), M(18000000))
        assert month.return_rate == M("0.012858")

    def test_매달_1일_행은_그날_다른_사건이_없을_때만이다(self) -> None:
        outcome = run(start=D("2015-01-01"), end=D("2015-06-15"))
        # 1일 가입이면 납입이 늘 1일이라 월 행이 없다
        assert {r.kind for r in outcome.rows} == {"installment"}
        months = [r.date for r in run(end=D("2015-06-15")).rows if r.kind == "month"]
        assert months == [D(f"2015-0{m}-01") for m in (6, 5, 4, 3, 2)]

    def test_납입_행의_평가는_그날까지_낸_회차와_경과_이자다(self) -> None:
        row = on(run(), "2015-02-15")[0]
        assert (row.kind, row.contract_no, row.installment_no, row.amount, row.rate) == (
            "installment", 1, 2, M(1000000), M("2.32"))
        assert row.contributed == M(2000000)
        assert row.installment_value > M(2000000)


class Test납입_날짜:
    def test_31일_시작은_없는_달에_말일이다(self) -> None:
        outcome = run(start=D("2015-01-31"), end=D("2016-02-01"))
        dates = installment_dates(outcome, 1)
        assert dates == [D(d) for d in (
            "2015-01-31", "2015-02-28", "2015-03-31", "2015-04-30", "2015-05-31", "2015-06-30",
            "2015-07-31", "2015-08-31", "2015-09-30", "2015-10-31", "2015-11-30", "2015-12-31")]
        assert outcome.contracts[0].matures_on == D("2016-01-31")

    def test_2월_29일_시작은_평년에_28일이다(self) -> None:
        rates = {D("2016-02-01"): M("1.77"), D("2017-02-01"): M("1.52")}
        outcome = run(start=D("2016-02-29"), end=D("2017-03-31"), installment_rates=rates,
                      installment_latest=D("2017-02-01"),
                      deposit_rates={D("2017-02-01"): M("1.56")}, deposit_latest=D("2017-02-01"))
        assert outcome.contracts[0].matures_on == D("2017-02-28")
        first = installment_dates(outcome, 1)
        assert (first[0], first[1], first[-1]) == (
            D("2016-02-29"), D("2016-03-29"), D("2017-01-29"))
        second = installment_dates(outcome, 2)
        # 둘째 적금은 앞 적금의 만기일(2-28)에 가입한다 — 그 뒤 매달 28일
        assert second == [D("2017-02-28"), D("2017-03-28")]


class Test계산_끝:
    def test_계산_끝_뒤의_회차는_내지_않는다(self) -> None:
        outcome = run(end=D("2015-07-01"))
        assert len([r for r in outcome.rows if r.kind == "installment"]) == 6
        s = outcome.summary
        assert (s.contributed, s.balance, s.return_rate) == (M(6000000), M(6029567), M("0.004928"))
        assert s.current_installment is not None and s.current_installment.paid == 6
        assert (s.current_deposit, outcome.contracts, outcome.deposits) == (None, [], [])

    def test_계산_끝이_첫_만기_전이면_정기예금_금리가_없어도_된다(self) -> None:
        outcome = run(end=D("2015-12-31"), deposit_rates={}, deposit_first=None,
                      deposit_latest=None)
        assert outcome.summary.deposit_value == M(0)


class Test잠정:
    def test_새_가입_달이_미발표면_그_계약부터_잠정이다(self) -> None:
        outcome = run(installment_latest=D("2017-12-01"), deposit_latest=D("2017-12-01"))
        s = outcome.summary
        assert s.provisional_from == D("2018-01-15")
        assert s.current_installment is not None and s.current_deposit is not None
        assert (s.current_installment.rate, s.current_installment.rate_month,
                s.current_installment.provisional) == (M("1.75"), D("2017-12-01"), True)
        assert (s.current_deposit.rate, s.current_deposit.provisional) == (M("1.91"), True)
        assert not any(c.provisional for c in outcome.contracts)
        today = {r.kind: r for r in on(outcome, "2018-01-15")}
        assert today["installment"].provisional and today["deposit_join"].provisional
        assert not today["installment_maturity"].provisional

    def test_정기예금만_미발표여도_그날부터_잠정이다(self) -> None:
        s = run(deposit_latest=D("2017-12-01")).summary
        assert s.provisional_from == D("2018-01-15")


class Test결측과_시작_가능_날짜:
    def test_첫_적금_가입_달이_결측이면_계산하지_않는다(self) -> None:
        with pytest.raises(RateMissing) as info:
            run(installment_rates=without(ISAV, "2015-01-01"))
        assert info.value.month == D("2015-01-01")

    def test_둘째_적금_가입_달이_결측이면_그_만기일에서_멈춘다(self) -> None:
        outcome = run(installment_rates=without(ISAV, "2016-01-01"))
        s = outcome.summary
        assert s.stopped == Stopped(date=D("2016-01-15"), reason="rate_missing",
                                    month=D("2016-01-01"))
        assert (s.as_of, s.is_final, s.balance, s.contributed) == (
            D("2016-01-15"), False, M(12127577), M(12000000))
        assert (s.current_installment, s.current_deposit, outcome.deposits) == (None, None, [])
        assert [r.kind for r in on(outcome, "2016-01-15")] == ["installment_maturity"]

    def test_정기예금_가입_달이_결측이면_두_만기_뒤에서_멈춘다(self) -> None:
        outcome = run(deposit_rates=without(DEP, "2017-01-01"))
        s = outcome.summary
        assert s.stopped is not None and s.stopped.date == D("2017-01-15")
        assert s.balance == M(12098433) + M(12304048)
        assert (len(outcome.contracts), len(outcome.deposits)) == (2, 1)
        assert [r.kind for r in on(outcome, "2017-01-15")] == [
            "deposit_maturity", "installment_maturity"]

    @pytest.mark.parametrize(("start", "installment_first", "deposit_first", "startable"), [
        # 시중은행 — 정기예금(1년)이 2012-01부터라 첫 만기가 그 뒤여야 한다
        ("2010-12-15", "2003-01-01", "2012-01-01", "2011-01-01"),
        # 상호금융 — 적금 통계가 늦게 시작한다
        ("2011-12-15", "2012-01-01", "1997-08-01", "2012-01-01"),
    ])
    def test_시작_가능_날짜는_적금_첫_달과_정기예금_첫_달_1년_전_중_늦은_날이다(
        self, start: str, installment_first: str, deposit_first: str, startable: str
    ) -> None:
        with pytest.raises(BeforeFirstMonth) as info:
            run(start=D(start), installment_first=D(installment_first),
                deposit_first=D(deposit_first))
        assert info.value.first_month == D(startable)
