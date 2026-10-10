"""일자별 표의 값 (014 반복 2026-10-10b T104) — FR-013, FR-029, SC-012, research R14-21.

순수 함수다. 기준일은 012 `period_table`의 규칙이다(주 = 금요일 이하의 마지막 거래일, 월 = 말일
이하의 마지막 거래일).

- 주·월 행: 시가 = 그 기간 첫 거래일 시가(비었으면 비움 — 다음 날로 메우지 않는다), 고가·저가 =
  기간의 최댓값·최솟값,
  종가 = 대표일 종가, 대비 = 앞 기간 대표 종가와의 차이
- 일 행의 대비는 직전 거래일 종가와의 차이다. 앞 행이 없으면 비운다. 앞 종가가 0 이하면 등락률을
  비운다
- 값의 열쇠는 `period_table.build_table`이 고르는 대표일과 같다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.indicator_table import TableBar, table_values
from src.simulation.period_table import build_table

D = dt.date


def bar(day: str, o: str | None, h: str | None, low: str | None, c: str) -> TableBar:
    def dec(v: str | None) -> Decimal | None:
        return None if v is None else Decimal(v)

    return TableBar(D.fromisoformat(day), dec(o), dec(h), dec(low), Decimal(c))


# 2026-09-28(월) ~ 10-09(금) 두 주. 10-09(금)은 휴장이라 둘째 주 대표일은 10-08(목)이다.
BARS = [
    bar("2026-09-28", "100", "105", "99", "104"),
    bar("2026-09-29", "104", "110", "103", "108"),
    bar("2026-09-30", "108", "109", "101", "102"),
    bar("2026-10-01", "102", "103", "95", "96"),
    bar("2026-10-02", "96", "100", "94", "99"),
    bar("2026-10-05", None, "101", "97", "100"),
    bar("2026-10-06", "100", "120", "100", "118"),
    bar("2026-10-07", "118", "119", "90", "92"),
    bar("2026-10-08", "92", "95", "91", "94"),
]


def test_일_행의_대비는_직전_거래일이다() -> None:
    values = table_values(BARS, "daily", provisional=set())
    first, second = values[D(2026, 9, 28)], values[D(2026, 9, 29)]
    assert (first.change, first.change_rate) == (None, None)
    assert second.change == Decimal("4")
    assert second.change_rate == (Decimal("4") / Decimal("104")).quantize(Decimal("0.000001"))
    assert (second.open, second.high, second.low, second.close) == (
        Decimal("104"),
        Decimal("110"),
        Decimal("103"),
        Decimal("108"),
    )


def test_주_행은_첫_시가_최고_최저_대표_종가다() -> None:
    values = table_values(BARS, "weekly", provisional=set())
    week1 = values[D(2026, 10, 2)]
    assert (week1.open, week1.high, week1.low, week1.close, week1.change) == (
        Decimal("100"),
        Decimal("110"),
        Decimal("94"),
        Decimal("99"),
        None,
    )
    week2 = values[D(2026, 10, 8)]  # 금요일 휴장 — 목요일이 대표일
    assert week2.open is None  # 첫 거래일(월) 시가가 비었다 — 화요일 시가로 메우지 않는다
    assert (week2.high, week2.low, week2.close) == (Decimal("120"), Decimal("90"), Decimal("94"))
    assert week2.change == Decimal("94") - Decimal("99")


def test_월_행() -> None:
    values = table_values(BARS, "monthly", provisional=set())
    sep, octo = values[D(2026, 9, 30)], values[D(2026, 10, 8)]
    assert (sep.open, sep.high, sep.low, sep.close) == (
        Decimal("100"),
        Decimal("110"),
        Decimal("99"),
        Decimal("102"),
    )
    assert (octo.open, octo.high, octo.low, octo.close) == (
        Decimal("102"),
        Decimal("120"),
        Decimal("90"),
        Decimal("94"),
    )
    assert octo.change == Decimal("94") - Decimal("102")


def test_값의_열쇠는_표의_대표일과_같다() -> None:
    days = [b.date for b in BARS]
    for unit in ("daily", "weekly", "monthly"):
        reps = {e.date for e in build_table(days, (), unit, D(2026, 10, 10))}  # type: ignore[arg-type]
        assert set(table_values(BARS, unit, provisional=set())) == reps  # type: ignore[arg-type]


def test_잠정_날이_든_행은_잠정이다() -> None:
    values = table_values(BARS, "weekly", provisional={D(2026, 10, 8)})
    assert values[D(2026, 10, 8)].provisional is True
    assert values[D(2026, 10, 2)].provisional is False


def test_앞_종가가_0_이하면_등락률을_비운다() -> None:
    bars = [
        bar("2020-04-20", "17.73", "17.85", "-40.32", "-37.63"),
        bar("2020-04-21", "-14", "1", "-16", "10.01"),
    ]
    second = table_values(bars, "daily", provisional=set())[D(2020, 4, 21)]
    assert second.change == Decimal("10.01") - Decimal("-37.63")
    assert second.change_rate is None
