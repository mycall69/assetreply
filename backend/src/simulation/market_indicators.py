"""대시보드 지표 목록 (014 T012) — FR-003, FR-015, FR-018, data-model 2.

지표는 **고정된 15개**다(FR-003 — 사용자가 더하거나 빼지 않는다). 지수는 도메인 범위 자산군
4(주식·ETF·지수)의 지수
시계열, 환율 셋은 자산군 1(외환)의 데이터, 원자재·변동성은 조회 지표다(헌법 원칙 IX — 새 자산군이
아니다).

**출처 심볼을 담지 않는다** — 심볼 대응은 수집 계층 `ingestion/yahoo/market_symbols.py` 한 곳에만
있다(헌법 원칙 II). 이 모듈이
심볼을 알면 출처를 바꿀 때 도메인 쪽이 함께 바뀐다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Group = Literal["korea", "us", "asia", "fx", "commodity"]
Kind = Literal["index", "fx", "future", "volatility"]
#: 이력의 원천 — 대시보드 표(`market`) 또는 외환 메뉴의 고시 이력(`fx` — 명확화 2).
History = Literal["market", "fx"]

GROUP_LABELS: Final[dict[str, str]] = {
    "korea": "한국",
    "us": "미국",
    "asia": "일본·중국",
    "fx": "환율",
    "commodity": "원자재·변동성",
}


@dataclass(frozen=True, slots=True)
class Indicator:
    """지표 하나. `market`은 거래 시간표의 키다(`simulation/market_session`)."""

    id: str
    name: str
    group: Group
    order: int
    market: str
    unit: str
    kind: Kind
    history: History
    #: 외환 이력의 통화 코드 — 환율 셋만.
    fx_currency: str | None
    #: 결측 판정의 같은 시장 묶음(research R14-5) — 묶음이 없으면 이웃 판정만 한다.
    gap_group: str | None
    #: 카드·그래프의 주석 — `future_roll`(근월물 연속, FR-015), `market_fx`(시장 환율, FR-018).
    notes: tuple[str, ...]


def _index(
    id_: str, name: str, group: Group, order: int, market: str, gap_group: str | None
) -> Indicator:
    return Indicator(
        id_, name, group, order, market, "포인트", "index", "market", None, gap_group, ()
    )


def _fx(id_: str, name: str, order: int, unit: str, currency: str) -> Indicator:
    return Indicator(id_, name, "fx", order, "fx", unit, "fx", "fx", currency, None, ("market_fx",))


INDICATORS: Final[tuple[Indicator, ...]] = (
    _index("kospi", "KOSPI", "korea", 1, "krx", "krx"),
    _index("kosdaq", "KOSDAQ", "korea", 2, "krx", "krx"),
    _index("dow", "다우존스 산업평균", "us", 3, "us_equity", "us_equity"),
    _index("nasdaq", "나스닥 종합", "us", 4, "us_equity", "us_equity"),
    _index("sp500", "S&P 500", "us", 5, "us_equity", "us_equity"),
    _index("sox", "필라델피아 반도체", "us", 6, "us_equity", "us_equity"),
    _index("nikkei225", "니케이 225", "asia", 7, "tse", None),
    _index("hangseng", "항셍", "asia", 8, "hkex", None),
    _index("shanghai", "상해 종합", "asia", 9, "sse", None),
    _fx("usd", "달러", 10, "원", "USD"),
    _fx("jpy", "엔(100엔)", 11, "원(100엔당)", "JPY"),
    _fx("eur", "유로", 12, "원", "EUR"),
    Indicator(
        "wti",
        "WTI 원유",
        "commodity",
        13,
        "cme",
        "USD/배럴",
        "future",
        "market",
        None,
        "cme",
        ("future_roll",),
    ),
    Indicator(
        "gold",
        "금",
        "commodity",
        14,
        "cme",
        "USD/트로이온스",
        "future",
        "market",
        None,
        "cme",
        ("future_roll",),
    ),
    Indicator(
        "vix", "VIX", "commodity", 15, "cboe", "포인트", "volatility", "market", None, None, ()
    ),
)

_BY_ID: Final[dict[str, Indicator]] = {i.id: i for i in INDICATORS}


def get(indicator_id: str) -> Indicator | None:
    """id의 지표. 없는 id면 `None`이다(화면의 "없는 지표" — FR-010)."""
    return _BY_ID.get(indicator_id)


def market_indicators() -> tuple[Indicator, ...]:
    """이력을 대시보드 표에 받는 지표(환율 셋을 뺀 12개 — FR-017)."""
    return tuple(i for i in INDICATORS if i.history == "market")


def siblings(indicator: Indicator) -> tuple[Indicator, ...]:
    """같은 결측 묶음의 다른 지표(research R14-5)."""
    if indicator.gap_group is None:
        return ()
    return tuple(
        i for i in INDICATORS if i.gap_group == indicator.gap_group and i.id != indicator.id
    )
