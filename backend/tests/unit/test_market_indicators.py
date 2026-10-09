"""대시보드 지표 목록 (014 T006) — FR-003, FR-015, FR-018, data-model 2.

지표는 **고정된 15개**다(FR-003). 이 모듈은 도메인 쪽이라 출처 심볼을 담지 않는다 — 심볼 대응은 수집
계층
(`ingestion/yahoo/market_symbols.py`) 한 곳에만 있다(헌법 원칙 II).
"""

from __future__ import annotations

import inspect

from src.simulation import market_indicators
from src.simulation.market_indicators import GROUP_LABELS, INDICATORS, get

ORDER = [
    "kospi",
    "kosdaq",
    "dow",
    "nasdaq",
    "sp500",
    "sox",
    "nikkei225",
    "hangseng",
    "shanghai",
    "usd",
    "jpy",
    "eur",
    "wti",
    "gold",
    "vix",
]


def test_고정된_15개를_차례대로_둔다() -> None:
    assert [i.id for i in INDICATORS] == ORDER
    assert [i.order for i in INDICATORS] == list(range(1, 16))


def test_묶음의_구성과_이름표() -> None:
    groups: dict[str, list[str]] = {}
    for i in INDICATORS:
        groups.setdefault(i.group, []).append(i.id)
    assert groups == {
        "korea": ["kospi", "kosdaq"],
        "us": ["dow", "nasdaq", "sp500", "sox"],
        "asia": ["nikkei225", "hangseng", "shanghai"],
        "fx": ["usd", "jpy", "eur"],
        "commodity": ["wti", "gold", "vix"],
    }
    assert GROUP_LABELS == {
        "korea": "한국",
        "us": "미국",
        "asia": "일본·중국",
        "fx": "환율",
        "commodity": "원자재·변동성",
    }


def test_이름과_단위() -> None:
    names = {i.id: i.name for i in INDICATORS}
    assert names["dow"] == "다우존스 산업평균"
    assert names["sox"] == "필라델피아 반도체"
    assert names["jpy"] == "엔(100엔)"
    units = {i.id: i.unit for i in INDICATORS}
    assert {units[k] for k in ORDER[:9]} == {"포인트"}
    assert (units["usd"], units["jpy"], units["eur"]) == ("원", "원(100엔당)", "원")
    assert (units["wti"], units["gold"], units["vix"]) == ("USD/배럴", "USD/트로이온스", "포인트")


def test_종류와_시장() -> None:
    kinds = {i.id: i.kind for i in INDICATORS}
    assert {kinds[k] for k in ORDER[:9]} == {"index"}
    assert {kinds[k] for k in ("usd", "jpy", "eur")} == {"fx"}
    assert (kinds["wti"], kinds["gold"], kinds["vix"]) == ("future", "future", "volatility")
    markets = {i.id: i.market for i in INDICATORS}
    assert markets == {
        "kospi": "krx",
        "kosdaq": "krx",
        "dow": "us_equity",
        "nasdaq": "us_equity",
        "sp500": "us_equity",
        "sox": "us_equity",
        "nikkei225": "tse",
        "hangseng": "hkex",
        "shanghai": "sse",
        "usd": "fx",
        "jpy": "fx",
        "eur": "fx",
        "wti": "cme",
        "gold": "cme",
        "vix": "cboe",
    }


def test_결측_묶음() -> None:
    gap = {i.id: i.gap_group for i in INDICATORS}
    assert {k for k, v in gap.items() if v == "krx"} == {"kospi", "kosdaq"}
    assert {k for k, v in gap.items() if v == "us_equity"} == {"dow", "nasdaq", "sp500", "sox"}
    assert {k for k, v in gap.items() if v == "cme"} == {"wti", "gold"}
    assert {k for k, v in gap.items() if v is None} == {
        "nikkei225",
        "hangseng",
        "shanghai",
        "usd",
        "jpy",
        "eur",
        "vix",
    }


def test_이력_원천과_주석() -> None:
    fx = [i for i in INDICATORS if i.history == "fx"]
    assert [(i.id, i.fx_currency) for i in fx] == [("usd", "USD"), ("jpy", "JPY"), ("eur", "EUR")]
    assert {i.history for i in INDICATORS if i.kind != "fx"} == {"market"}
    notes = {i.id: i.notes for i in INDICATORS}
    assert notes["wti"] == ("future_roll",) and notes["gold"] == ("future_roll",)
    assert {notes[k] for k in ("usd", "jpy", "eur")} == {("market_fx",)}
    assert notes["kospi"] == () and notes["vix"] == ()


def test_get은_없는_id에_None() -> None:
    sp500 = get("sp500")
    assert sp500 is not None and sp500.name == "S&P 500"
    assert get("kospii") is None


def test_출처_심볼을_담지_않는다() -> None:
    """원칙 II — 출처 심볼은 수집 계층에만 있다."""
    source = inspect.getsource(market_indicators)
    for token in ("^", "=F", "=X", ".SS"):
        assert token not in source, token
