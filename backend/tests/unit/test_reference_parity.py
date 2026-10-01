"""참조 구현 대조 (T108) — 005 research R5-4, quickstart 시나리오 22.

사용자가 쓰던 Google Apps Script(`YF_REINVEST_TABLE`)와 **같은 조건에서 같은 수를
내는가**를 본다. 시뮬레이터가 순수 함수라 이 대조가 단위 테스트로 가능하다 —
DB에 묶여 있었다면 통합 테스트가 되고 정밀도 차이가 다른 실패에 묻힌다 (헌법 원칙 IV).

**수수료를 0%로 두고 대조한다.** 참조 구현은 수수료를 다루지 않는다(주석 "수수료 X").
그 차이를 전제하지 않으면 모든 행이 조금씩 어긋나 어디가 진짜 불일치인지 가려진다.

대조에서 빼는 것이 하나 있다. **분할 적용 조건**이다 — 참조 구현은 가격 점프가 있을
때만 분할을 적용하는 휴리스틱을 쓰고, 이 기능은 제공처를 그대로 믿기로 했다
(FR-010a, spec Assumptions). 의도된 차이이므로 분할이 없는 입력으로 대조한다.

기대값은 참조 구현의 계산을 손으로 따라가 적은 것이다 (각 테스트의 주석 참조).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import (
    Condition,
    DayBar,
    DividendOn,
    Row,
    simulate,
)

D = dt.date.fromisoformat

#: 참조 구현의 기본 배당세율 (`RI_parseTax`의 DEFAULT).
TAX = Decimal("0.154")
#: 참조 구현은 수수료를 다루지 않는다.
NO_FEE = Decimal("0")


def bars(*pairs: tuple[str, str]) -> list[DayBar]:
    return [DayBar(D(day), Decimal(price)) for day, price in pairs]


def condition(start: str, principal: str, *, reinvest: bool = True) -> Condition:
    return Condition(
        start=D(start), principal=Decimal(principal), currency="USD",
        reinvest=reinvest, fee_rate=NO_FEE, tax_rate=TAX)


def by_date(rows: list[Row], day: str, kind: str) -> Row:
    return next(r for r in rows if r.date == D(day) and r.kind == kind)


class Test기본_흐름:
    """참조 구현의 손계산.

    | 날짜 | 시가 | 사건 | 보유 | 예수금 | 잔고 |
    |------|------|------|------|--------|------|
    | 08-02 | 100 | 초기 매수 ⌊1000/100⌋=10 | 10 | 0 | 1000 |
    | 09-01 | 110 | 스냅샷 | 10 | 0 | 1100 |
    | 09-15 | 120 | 배당 1.0 → 세후 10×1×0.846=8.46, ⌊8.46/120⌋=0 | 10 | 8.46 | 1200 |
    | 10-01 | 130 | 스냅샷 | 10 | 8.46 | 1300 |
    """

    ROWS = simulate(
        bars(("2021-08-02", "100"), ("2021-09-01", "110"),
             ("2021-09-15", "120"), ("2021-10-01", "130")),
        [DividendOn(D("2021-09-15"), Decimal("1.0"))],
        [],
        condition("2021-08-01", "1000"),
    )

    def test_초기_매수_수량이_같다(self) -> None:
        row = by_date(self.ROWS, "2021-08-02", "month_first")
        assert row.bought_shares == 10
        assert row.held_shares == 10
        assert row.cash == Decimal("0")

    def test_초기_매수_이후의_달은_사지_않는다(self) -> None:
        """참조 구현은 초기 1회만 매수한다 — 적립식이 아니다."""
        row = by_date(self.ROWS, "2021-09-01", "month_first")
        assert row.bought_shares == 0
        assert row.held_shares == 10

    def test_세후_배당이_같다(self) -> None:
        """10주 × 1.0 × (1 − 0.154) = 8.46."""
        row = by_date(self.ROWS, "2021-09-15", "dividend")
        assert row.cash == Decimal("8.460")

    def test_배당금으로_살_수_없으면_예수금에_남는다(self) -> None:
        """⌊8.46 / 120⌋ = 0. 소수점 주식을 만들지 않는다 (FR-007)."""
        row = by_date(self.ROWS, "2021-09-15", "dividend")
        assert row.bought_shares == 0
        assert row.held_shares == 10

    def test_배당율이_같다(self) -> None:
        """참조 구현의 `yld = dps / pxOpen`을 소수 6자리로. 1/120 = 0.008333."""
        row = by_date(self.ROWS, "2021-09-15", "dividend")
        assert row.dividend_yield == Decimal("0.008333")

    def test_잔고가_예수금을_빼고_계산된다(self) -> None:
        """참조 구현의 `bal = shares × pxOpen`. 총자산이 아니다 (FR-013)."""
        row = by_date(self.ROWS, "2021-10-01", "month_first")
        assert row.balance == Decimal("1300")

    def test_수익이_총자산_기준이다(self) -> None:
        """참조 구현의 `profit = (bal + cash) − principal` = 1300 + 8.46 − 1000."""
        row = by_date(self.ROWS, "2021-10-01", "month_first")
        assert row.profit == Decimal("308.460")

    def test_수익률이_같다(self) -> None:
        """308.46 / 1000 = 0.308460."""
        row = by_date(self.ROWS, "2021-10-01", "month_first")
        assert row.return_rate == Decimal("0.308460")


class Test배당락일_매수:
    """**배당락일에 산 주식은 그 배당을 받지 못한다.**

    참조 구현은 세후 배당을 `sharesAtDiv`(그날 **시작 시점**의 보유 수)로 계산한 뒤에
    초기 매수를 집행한다. 현실도 같다 — 배당락일은 배당 권리 없이 거래가 시작되는 날이다.

    매수 뒤의 보유 수로 계산하면 **처음부터 있던 주식처럼 배당이 붙는다.** 값은
    그럴듯하고 오류도 나지 않는데, 시작 월이 배당 달인 조건에서 수익이 부풀려진다.

    손계산: 08-02에 10주 매수, 그날의 배당은 0주에 대해 0.
    """

    ROWS = simulate(
        bars(("2021-08-02", "100"), ("2021-09-01", "110")),
        [DividendOn(D("2021-08-02"), Decimal("2.0"))],
        [],
        condition("2021-08-01", "1000"),
    )

    def test_그날_산_주식에는_배당이_붙지_않는다(self) -> None:
        row = by_date(self.ROWS, "2021-08-02", "dividend")
        assert row.cash == Decimal("0")
        assert row.bought_shares == 0

    def test_수익이_0이다(self) -> None:
        row = by_date(self.ROWS, "2021-08-02", "dividend")
        assert row.profit == Decimal("0")

    def test_다음_달에도_배당이_없던_것과_같다(self) -> None:
        row = by_date(self.ROWS, "2021-09-01", "month_first")
        assert row.held_shares == 10
        assert row.cash == Decimal("0")


class Test재투자_매수:
    """배당금이 한 주 값을 넘으면 그날 시가로 정수 매수한다.

    손계산: 08-02에 ⌊1000/10⌋=100주. 09-01 배당 1.0 → 세후 100×1×0.846=84.6,
    시가 10 → ⌊84.6/10⌋=8주 매수, 예수금 84.6−80=4.6, 보유 108주.
    """

    ROWS = simulate(
        bars(("2021-08-02", "10"), ("2021-09-01", "10")),
        [DividendOn(D("2021-09-01"), Decimal("1.0"))],
        [],
        condition("2021-08-01", "1000"),
    )

    def test_예수금_전액으로_산다(self) -> None:
        """참조 구현은 배당금만이 아니라 **예수금 전체**를 쓴다 (FR-008)."""
        row = by_date(self.ROWS, "2021-09-01", "dividend")
        assert row.bought_shares == 8
        assert row.held_shares == 108
        assert row.cash == Decimal("4.600")

    def test_배당락_행이_재투자까지_반영한다(self) -> None:
        """FR-027 — 매수 전 상태를 보이면 사용자는 재투자가 안 됐다고 읽는다."""
        row = by_date(self.ROWS, "2021-09-01", "dividend")
        assert row.balance == Decimal("1080")

    def test_월_행이_같은_상태를_보인다(self) -> None:
        """같은 날의 월 행은 배당락 행 **뒤의** 상태다."""
        row = by_date(self.ROWS, "2021-09-01", "month_first")
        assert row.held_shares == 108


class Test재투자_끔:
    """FR-009 — 세후 배당금이 예수금에 쌓이기만 한다."""

    ROWS = simulate(
        bars(("2021-08-02", "10"), ("2021-09-01", "10")),
        [DividendOn(D("2021-09-01"), Decimal("1.0"))],
        [],
        condition("2021-08-01", "1000", reinvest=False),
    )

    def test_사지_않고_쌓인다(self) -> None:
        row = by_date(self.ROWS, "2021-09-01", "dividend")
        assert row.bought_shares == 0
        assert row.held_shares == 100
        assert row.cash == Decimal("84.600")

    def test_총자산은_재투자와_같은_금액에서_출발한다(self) -> None:
        """재투자는 **그 뒤의 복리**로 갈린다. 배당을 받은 직후 총자산은 같다."""
        row = by_date(self.ROWS, "2021-09-01", "dividend")
        assert row.balance + row.cash == Decimal("1084.600")
