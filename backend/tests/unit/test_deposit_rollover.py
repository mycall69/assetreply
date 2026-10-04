"""예금 재예치 계산 (T011) — 008 FR-007, FR-018, FR-019, FR-021~FR-029, SC-003~SC-006,
research R8-7·R8-8.

DB·HTTP 없는 순수 함수다(헌법 원칙 IV). 참조값은 research R8-7 — 실측 금리(시중은행 정기예금(1년))로
손계산했다. **원 미만 버림은 두 곳뿐**이다:

    이자  I = 0 쪽 절사(P × r / 100)                   (만기분 — 1년이 365일이든 366일이든 같다)
    경과  a = 0 쪽 절사(P × r / 100 × 경과 일수 / 회차 일수)
    세금  T = 0 쪽 절사(I × 세율), 이자가 0 이하이면 0
    재예치 원금 = P + (I − T)

예) 회차 2: P = 10,137,052, r = 0.97 → P × r / 100 = 98,329.4044 → I = 98,329,
    T = 98,329 × 0.154 = 15,142.666 → 15,142, 세후 83,187, 재예치 10,220,239.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.deposit_rollover import (
    RateMissing,
    accrued_interest,
    add_one_year,
    maturity_interest,
    simulate_deposit,
)

D = dt.date.fromisoformat
P = Decimal
TAX = P("0.154")
FIRST = D("2012-01-01")
LATEST = D("2026-08-01")
TODAY = D("2026-10-04")

# 시중은행 정기예금(1년) 실측(research R8-7) — 나머지 달은 2.00(이 계산이 쓰지 않는 달).
REAL = {"2020-01": "1.62", "2021-01": "0.97", "2022-01": "1.83", "2023-01": "4.15",
        "2024-01": "3.65", "2025-01": "3.06", "2026-01": "2.84", "2024-02": "3.63",
        "2025-09": "2.54", "2026-08": "3.39"}


def months(first: dt.date, last: dt.date) -> list[dt.date]:
    out, cur = [], first
    while cur <= last:
        out.append(cur)
        cur = cur.replace(year=cur.year + cur.month // 12, month=cur.month % 12 + 1)
    return out


def rates(*, latest: dt.date = LATEST, drop: tuple[str, ...] = (),
          override: dict[str, str] | None = None) -> dict[dt.date, Decimal]:
    table = {m: P(REAL.get(m.strftime("%Y-%m"), "2.00")) for m in months(FIRST, latest)}
    for k, v in (override or {}).items():
        table[D(k + "-01")] = P(v)
    for k in drop:
        del table[D(k + "-01")]
    return table


def run(start: str, *, principal: str = "10000000", end: dt.date = TODAY,
        latest: dt.date = LATEST, tax: Decimal = TAX, **kw):  # type: ignore[no-untyped-def]
    return simulate_deposit(principal=P(principal), start=D(start), end=end,
                            rates=rates(latest=latest, **kw), first_month=FIRST,
                            latest_month=latest, tax_rate=tax)


class Test참조값_1_재예치_여러_번:
    """시중은행, 2020-01-15, 10,000,000원, 세율 15.4%, 오늘 2026-10-04."""

    def test_회차_여섯과_진행_중_회차(self) -> None:
        result = run("2020-01-15")
        got = [(str(t.joined_on), str(t.matures_on), str(t.rate), str(t.principal),
                str(t.interest), str(t.tax), str(t.after_tax)) for t in result.terms]
        assert got == [
            ("2020-01-15", "2021-01-15", "1.62", "10000000", "162000", "24948", "137052"),
            ("2021-01-15", "2022-01-15", "0.97", "10137052", "98329", "15142", "83187"),
            ("2022-01-15", "2023-01-15", "1.83", "10220239", "187030", "28802", "158228"),
            ("2023-01-15", "2024-01-15", "4.15", "10378467", "430706", "66328", "364378"),
            ("2024-01-15", "2025-01-15", "3.65", "10742845", "392113", "60385", "331728"),
            ("2025-01-15", "2026-01-15", "3.06", "11074573", "338881", "52187", "286694"),
        ]
        current = result.summary.current_term
        assert current is not None
        assert (str(current.joined_on), str(current.matures_on), str(current.rate),
                str(current.rate_month), str(current.principal), current.provisional) == (
            "2026-01-15", "2027-01-15", "2.84", "2026-01-01", "11361267", False)

    def test_오늘의_잔고와_수익률(self) -> None:
        """경과 262/365일 → 231,607, 세금 35,667, 잔고 11,557,207."""
        s = run("2020-01-15").summary
        assert (str(s.balance), str(s.profit), str(s.return_rate)) == (
            "11557207", "1557207", "0.155721")
        assert (s.as_of, s.is_final, s.provisional_from, s.stopped) == (TODAY, True, None, None)

    def test_행은_가입_매달_1일_만기_재예치이고_최신순이다(self) -> None:
        rows = run("2020-01-15").rows
        kinds = [r.kind for r in rows]
        assert kinds.count("join") == 1 and kinds.count("maturity") == 6
        assert kinds.count("reinvest") == 6 and kinds.count("month") == 81
        assert [r.date for r in rows] == sorted((r.date for r in rows), reverse=True)
        assert rows[-1].kind == "join" and rows[-1].date == D("2020-01-15")

    def test_월_행은_그날까지의_경과분이다(self) -> None:
        """2026-10-01: 259/365일 → 228,955, 세금 35,259, 세후 193,696, 잔고 11,554,963."""
        row = run("2020-01-15").rows[0]
        assert (row.kind, row.date) == ("month", D("2026-10-01"))
        assert (str(row.principal), str(row.interest), str(row.tax), str(row.after_tax),
                str(row.balance), str(row.profit)) == (
            "11361267", "228955", "35259", "193696", "11554963", "1554963")

    def test_첫_월_행은_윤년_회차_366일로_나눈다(self) -> None:
        """2020-02-01: 17/366일 → 7,524, 세금 1,158, 잔고 10,006,366."""
        row = next(r for r in run("2020-01-15").rows if r.date == D("2020-02-01"))
        assert (str(row.interest), str(row.tax), str(row.balance)) == ("7524", "1158", "10006366")

    def test_같은_날의_재예치가_만기보다_앞이고_원금이_이어진다(self) -> None:
        """재예치 원금 = 만기 원금 + 세후 이자(SC-004)."""
        rows = [r for r in run("2020-01-15").rows if r.date == D("2021-01-15")]
        assert [r.kind for r in rows] == ["reinvest", "maturity"]
        reinvest, maturity = rows
        assert maturity.principal + maturity.after_tax == reinvest.principal == P("10137052")
        assert (str(maturity.interest), str(maturity.tax), str(maturity.rate)) == (
            "162000", "24948", "1.62")
        assert (str(reinvest.interest), str(reinvest.rate), reinvest.rate_month) == (
            "0", "0.97", D("2021-01-01"))
        assert reinvest.balance == maturity.balance == P("10137052")


class Test참조값_2_2월_29일:
    def test_다음_해_만기는_2월_28일이고_이자는_일수와_무관하다(self) -> None:
        result = run("2024-02-29", end=D("2025-03-10"))
        first = result.terms[0]
        assert (first.matures_on, str(first.interest)) == (D("2025-02-28"), "363000")
        assert add_one_year(D("2024-02-29")) == D("2025-02-28")
        assert add_one_year(D("2023-03-31")) == D("2024-03-31")


class Test참조값_3_잠정:
    def test_시작_달이_미발표면_마지막_발표_달_금리로_잠정_가입한다(self) -> None:
        result = run("2026-09-15")
        current = result.summary.current_term
        assert current is not None
        assert (str(current.rate), current.rate_month, current.provisional) == (
            "3.39", D("2026-08-01"), True)
        assert result.summary.provisional_from == D("2026-09-15")
        assert all(r.provisional for r in result.rows)

    def test_확정_회차_뒤의_재예치가_미발표면_그_회차부터_잠정이다(self) -> None:
        result = run("2025-09-15")
        assert result.terms[0].provisional is False
        assert result.summary.provisional_from == D("2026-09-15")
        current = result.summary.current_term
        assert current is not None and current.provisional
        by_kind = {r.kind: r for r in result.rows if r.date == D("2026-09-15")}
        assert by_kind["maturity"].provisional is False
        assert by_kind["reinvest"].provisional is True
        assert by_kind["reinvest"].rate_month == D("2026-08-01")

    def test_잠정_회차_뒤는_모두_잠정이다(self) -> None:
        result = run("2024-09-15", latest=D("2024-08-01"))
        assert all(t.provisional for t in result.terms)
        assert result.summary.provisional_from == D("2024-09-15")
        assert all(t.rate_month == D("2024-08-01") for t in result.terms)


class Test참조값_4_5_6_경계:
    def test_세율_0이면_세금_0이고_세후는_이자다(self) -> None:
        result = run("2020-01-15", tax=P("0"))
        assert all(t.tax == 0 and t.after_tax == t.interest for t in result.terms)

    def test_원금_1원이면_이자_0이고_원금이_그대로다(self) -> None:
        result = run("2020-01-15", principal="1")
        assert all(t.interest == 0 for t in result.terms)
        assert result.summary.balance == P("1")

    def test_음수_금리는_0_쪽으로_절사하고_세금은_0이다(self) -> None:
        result = run("2020-01-15", end=D("2021-02-01"), override={"2020-01": "-0.5"})
        first = result.terms[0]
        assert (str(first.interest), str(first.tax), str(first.after_tax)) == (
            "-50000", "0", "-50000")
        assert result.terms[0].principal + first.after_tax == P("9950000")

    def test_1원_미만_음수_이자는_0이다(self) -> None:
        interest = maturity_interest(P("1000"), P("-0.004"))
        assert str(interest) == "0"


class Test만기일과_달_첫날:
    def test_만기일의_경과_이자는_만기_이자와_같다(self) -> None:
        joined, matures = D("2020-01-15"), D("2021-01-15")
        assert accrued_interest(P("10000000"), P("1.62"), joined, matures, matures) == \
            maturity_interest(P("10000000"), P("1.62"))

    def test_가입일과_만기일이_1일이면_그날_월_행이_없다(self) -> None:
        rows = run("2020-01-01", end=D("2021-03-10")).rows
        jan = [r.kind for r in rows if r.date in (D("2020-01-01"), D("2021-01-01"))]
        assert sorted(jan) == ["join", "maturity", "reinvest"]

    def test_시작일이_오늘이면_경과_0이다(self) -> None:
        s = run("2026-07-15", end=D("2026-07-15")).summary
        assert (s.balance, s.profit, str(s.return_rate)) == (P("10000000"), P("0"), "0.000000")

    def test_오늘이_만기일이면_만기와_재예치가_오늘이다(self) -> None:
        """2025-01 금리 3.06 → 이자 306,000, 세금 47,124, 세후 258,876 → 잔고 10,258,876."""
        result = run("2025-01-15", end=D("2026-01-15"))
        assert [r.kind for r in result.rows[:2]] == ["reinvest", "maturity"]
        assert result.summary.balance == P("10258876")
        current = result.summary.current_term
        assert current is not None and current.joined_on == D("2026-01-15")


class Test결측:
    def test_재예치_달이_결측이면_그_만기일에서_멈춘다(self) -> None:
        result = run("2020-01-15", drop=("2021-01",))
        s = result.summary
        assert s.stopped is not None
        assert (s.stopped.date, s.stopped.reason, s.stopped.month) == (
            D("2021-01-15"), "rate_missing", D("2021-01-01"))
        assert (s.is_final, s.as_of, s.current_term, s.balance) == (
            False, D("2021-01-15"), None, P("10137052"))
        assert result.rows[0].date == D("2021-01-15") and result.rows[0].kind == "maturity"
        assert len(result.terms) == 1

    def test_가입_달이_결측이면_막는다(self) -> None:
        with pytest.raises(RateMissing) as info:
            run("2020-01-15", drop=("2020-01",))
        assert info.value.month == D("2020-01-01")


class Test재현성:
    def test_같은_입력은_같은_결과다(self) -> None:
        assert run("2020-01-15") == run("2020-01-15")
