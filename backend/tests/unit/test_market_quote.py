"""카드의 현재 값·전일 대비 (014 T020) — FR-004, FR-005, FR-007, SC-003, research R14-8·R14-9,
data-model 4.

- "전일"은 **그 시장의 직전 거래일 종가**다 — 저장된 이력에서 읽는다(카드 = 그래프의 같은 날 값 —
  SC-003)
- 이력이 그 날까지 닿지 않으면 출처 값으로 물러나고 그 사실을 밝힌다(`from = "source"`)
- 출처의 전일 값은 깨져 있을 수 있다 — 상해 `chartPreviousClose = 0.0002050505`(실측). 그래서
  `fulldayChange`가 먼저다
- 환율은 늘 출처(시장 환율 — 명확화 2), 엔은 100엔당(×100 — 정확)
- 휴장 카드의 차이는 마지막 거래일 − 그 전 거래일이다 — 0%가 아니다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

from src.simulation.market_indicators import Indicator, get
from src.simulation.market_quote import MarketQuote, SourceQuote, compose_quote

UTC = dt.UTC
KST = dt.timezone(dt.timedelta(hours=9))
D = dt.date


def ind(indicator_id: str) -> Indicator:
    found = get(indicator_id)
    assert found is not None
    return found


def kst(*parts: int) -> dt.datetime:
    return dt.datetime(*parts, tzinfo=KST).astimezone(UTC)


def compose(
    indicator_id: str,
    quote: SourceQuote,
    *,
    now: dt.datetime,
    history: tuple[dt.date, Decimal] | None = None,
    through: dt.date | None = None,
    fetched: dt.datetime | None = None,
    multiplier: Decimal = Decimal(1),
) -> MarketQuote:
    return compose_quote(
        ind(indicator_id),
        quote,
        multiplier=multiplier,
        history_previous=history,
        coverage_through=through,
        now=now,
        fetched_at=fetched or now,
        delay_notice_seconds=180,
        holiday_detect_seconds=3600,
    )


KS11_HOLIDAY = SourceQuote(
    price=Decimal("6625.93"),
    market_time=kst(2026, 10, 8, 20, 5, 40),
    full_day_change=Decimal("-177.97"),
    chart_previous_close=Decimal("6803.9"),
    session_start=kst(2026, 10, 8, 9, 0),
)


def test_휴장_KOSPI는_마지막_거래일과_그_전_거래일의_차이다() -> None:
    q = compose(
        "kospi",
        KS11_HOLIDAY,
        now=kst(2026, 10, 9, 14, 30),
        history=(D(2026, 10, 7), Decimal("6803.900000")),
        through=D(2026, 10, 8),
    )
    assert (q.state, q.session_date, q.provisional) == ("holiday", D(2026, 10, 8), False)
    assert q.value == Decimal("6625.930000")
    assert q.previous is not None
    assert (q.previous.close, q.previous.date, q.previous.source) == (
        Decimal("6803.900000"),
        D(2026, 10, 7),
        "history",
    )
    assert q.change == Decimal("-177.970000")
    assert q.change_rate == Decimal("-0.026157")
    assert q.change_rate != 0 and q.direction == "down"


def test_장중은_세션_날짜_앞의_이력_종가와_견준다() -> None:
    quote = SourceQuote(
        price=Decimal("6700"),
        market_time=kst(2026, 10, 8, 10, 0),
        full_day_change=Decimal("-103.9"),
        chart_previous_close=Decimal("6803.9"),
        session_start=kst(2026, 10, 8, 9, 0),
    )
    q = compose(
        "kospi",
        quote,
        now=kst(2026, 10, 8, 10, 0),
        history=(D(2026, 10, 7), Decimal("6800.000000")),
        through=D(2026, 10, 7),
    )
    assert (q.state, q.provisional) == ("open", True)
    assert q.previous is not None and q.previous.source == "history"
    assert q.change == Decimal("-100.000000")  # 출처 값(−103.9)이 아니라 이력


def test_이력이_닿지_않으면_출처의_전일로_물러난다() -> None:
    q = compose(
        "kospi",
        KS11_HOLIDAY,
        now=kst(2026, 10, 9, 14, 30),
        history=(D(2026, 10, 5), Decimal("6650")),
        through=D(2026, 10, 5),
    )
    assert q.previous is not None
    assert (q.previous.source, q.previous.date) == ("source", None)
    assert q.previous.close == Decimal("6803.900000")  # 값 − fulldayChange


def test_상해의_깨진_전일은_fulldayChange로_역산한다() -> None:
    quote = SourceQuote(
        price=Decimal("3813.7913"),
        market_time=dt.datetime(2026, 10, 9, 7, 0, tzinfo=UTC),
        full_day_change=Decimal("1.8869629"),
        chart_previous_close=Decimal("0.0002050505"),
        session_start=None,
    )
    q = compose("shanghai", quote, now=dt.datetime(2026, 10, 9, 8, 0, tzinfo=UTC))
    assert q.previous is not None and q.previous.close == Decimal("3811.904337")
    assert q.change == Decimal("1.886963")


def test_fulldayChange가_없으면_chartPreviousClose() -> None:
    quote = SourceQuote(
        price=Decimal("100"),
        market_time=dt.datetime(2026, 10, 9, 7, 0, tzinfo=UTC),
        full_day_change=None,
        chart_previous_close=Decimal("98"),
        session_start=None,
    )
    q = compose("shanghai", quote, now=dt.datetime(2026, 10, 9, 8, 0, tzinfo=UTC))
    assert q.previous is not None and q.previous.close == Decimal("98.000000")


def test_전일을_알_수_없으면_차이를_비운다() -> None:
    quote = SourceQuote(
        price=Decimal("100"),
        market_time=dt.datetime(2026, 10, 9, 7, 0, tzinfo=UTC),
        full_day_change=None,
        chart_previous_close=None,
        session_start=None,
    )
    q = compose("shanghai", quote, now=dt.datetime(2026, 10, 9, 8, 0, tzinfo=UTC))
    assert (q.previous, q.change, q.change_rate, q.direction) == (None, None, None, None)
    assert q.change_rate_blank == "no_previous"


def test_환율은_늘_출처이고_엔은_100엔당() -> None:
    quote = SourceQuote(
        price=Decimal("8.449"),
        market_time=kst(2026, 10, 9, 14, 24),
        full_day_change=Decimal("-0.012"),
        chart_previous_close=Decimal("8.461"),
        session_start=None,
    )
    q = compose(
        "jpy",
        quote,
        now=kst(2026, 10, 9, 14, 30),
        multiplier=Decimal(100),
        history=(D(2026, 10, 8), Decimal("900")),
        through=D(2026, 10, 8),
    )
    assert q.value == Decimal("844.900000")
    assert q.previous is not None
    assert (q.previous.close, q.previous.date, q.previous.source) == (
        Decimal("846.100000"),
        None,
        "source_fx",
    )
    assert q.change == Decimal("-1.200000")
    assert (q.state, q.provisional) == ("open", True)


def test_전일이_0_이하이면_등락률을_비우고_차이는_낸다() -> None:
    quote = SourceQuote(
        price=Decimal("10.01"),
        market_time=dt.datetime(2020, 4, 21, 19, 0, tzinfo=UTC),
        full_day_change=None,
        chart_previous_close=None,
        session_start=None,
    )
    q = compose(
        "wti",
        quote,
        now=dt.datetime(2020, 4, 22, 3, 0, tzinfo=UTC),
        history=(D(2020, 4, 20), Decimal("-37.630000")),
        through=D(2020, 4, 21),
    )
    assert q.change == Decimal("47.640000")
    assert (q.change_rate, q.change_rate_blank, q.direction) == (None, "non_positive_base", "up")


def test_변화가_없으면_flat() -> None:
    q = compose(
        "kospi",
        KS11_HOLIDAY,
        now=kst(2026, 10, 9, 14, 30),
        history=(D(2026, 10, 7), Decimal("6625.93")),
        through=D(2026, 10, 8),
    )
    assert (q.change, q.change_rate, q.direction) == (Decimal("0E-6"), Decimal("0E-6"), "flat")


def test_오늘_마감은_확정_전이고_지난_거래일_마감은_확정이다() -> None:
    ny = dt.timezone(dt.timedelta(hours=-4))
    quote = SourceQuote(
        price=Decimal("7765.36"),
        market_time=dt.datetime(2026, 10, 8, 16, 46, tzinfo=ny),
        full_day_change=Decimal("-36.41"),
        chart_previous_close=Decimal("7801.77"),
        session_start=dt.datetime(2026, 10, 8, 9, 30, tzinfo=ny),
    )
    tonight = compose("sp500", quote, now=dt.datetime(2026, 10, 8, 19, 0, tzinfo=ny))
    assert (tonight.state, tonight.session_date, tonight.provisional) == (
        "closed",
        D(2026, 10, 8),
        True,
    )
    # 다음 날 장 전 — 출처는 오늘 세션을 가리킨다(실측). 지난 거래일 종가는 확정이다
    today = dataclasses.replace(quote, session_start=dt.datetime(2026, 10, 9, 9, 30, tzinfo=ny))
    morning = compose("sp500", today, now=dt.datetime(2026, 10, 9, 8, 0, tzinfo=ny))
    assert (morning.state, morning.provisional) == ("pre_open", False)


def test_지연은_장중에만_시각_차이로() -> None:
    quote = SourceQuote(
        price=Decimal("90.80"),
        market_time=dt.datetime(2026, 10, 9, 13, 4, tzinfo=UTC),
        full_day_change=Decimal("-0.69"),
        chart_previous_close=Decimal("91.49"),
        session_start=None,
    )
    now = dt.datetime(2026, 10, 9, 13, 14, tzinfo=UTC)
    assert compose("wti", quote, now=now).delay_minutes == 10
    assert (
        compose(
            "wti", quote, now=now, fetched=dt.datetime(2026, 10, 9, 13, 6, tzinfo=UTC)
        ).delay_minutes
        is None
    )
    closed = compose("kospi", KS11_HOLIDAY, now=kst(2026, 10, 9, 14, 30))
    assert closed.delay_minutes is None


def test_값은_모두_Decimal이다() -> None:
    q = compose(
        "kospi",
        KS11_HOLIDAY,
        now=kst(2026, 10, 9, 14, 30),
        history=(D(2026, 10, 7), Decimal("6803.9")),
        through=D(2026, 10, 8),
    )
    assert q.previous is not None
    for value in (q.value, q.change, q.change_rate, q.previous.close):
        assert isinstance(value, Decimal)
