"""결측치 보간 정적 검사 (T040) — 헌법 원칙 V, 004 FR-012, FR-015.

**기준일 결측은 값이 아니라 날짜를 옮겨 푼다.** 금요일에 고시가 없으면 목요일의 값을
금요일 자리에 놓는 것이 아니라, 목요일이라는 **실제 날짜와 그날의 값**을 보여준다.

값을 채우는 코드는 오류를 내지 않는다. 표는 매끄러워 보이고 차트는 끊기지 않는다 —
그래서 정적으로 막는다. 004가 주·월 단위를 더하면서 "구간에 값이 없으면 앞 구간에서
가져오자"는 유혹이 새로 생겼다.
"""
from __future__ import annotations

import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

# 값을 만들어 채우는 관용구. 라이브러리 API와 한국어 표현을 함께 본다.
FILL_TOKENS = (
    "fillna", "ffill", "bfill", "forward_fill", "backfill",
    "interpolate", "전일 값", "이전 값", "직전 값",
)


def _sources() -> list[pathlib.Path]:
    return [p for p in SRC.rglob("*.py") if "migrations" not in p.parts]


def test_값을_채우는_코드가_없다() -> None:
    offenders: list[str] = []
    for path in _sources():
        body = path.read_text(encoding="utf-8")
        for token in FILL_TOKENS:
            if token in body:
                offenders.append(f"{path.relative_to(SRC)}: {token}")
    assert offenders == [], f"결측치 보간 흔적 (헌법 원칙 V): {offenders}"


def test_기준일_선정이_행을_만들어내지_않는다() -> None:
    """FR-015 — 빈 구간에 행을 만드는 경로가 애초에 없어야 한다.

    `period_page`는 저장된 고시일을 훑어 **그중에서 고른다**. 구간 목록을 먼저 만들고
    각 구간에 값을 채우는 구조였다면 빈 구간을 만났을 때 채울 자리가 생긴다.

    행을 직접 생성하는 것이 그 구조의 서명이다. 빈 구간에 행이 생기지 않는다는
    동작 자체는 `tests/integration/test_period_page.py`가 검증한다.
    """
    body = (SRC / "api" / "services" / "period_rows.py").read_text(encoding="utf-8")
    assert "FxRate(" not in body, (
        "기준일 선정이 행을 직접 만든다 — 저장된 고시일에서 고를 것 (헌법 원칙 V)")


# ─────────────────────────── 005: 주식 시뮬레이션 ───────────────────────────


def test_시뮬레이터가_시세를_만들어내지_않는다() -> None:
    """T101 — 헌법 원칙 V, 005 FR-042, SC-010.

    `reinvest.py`는 **받아 둔 일봉에서만** 행을 만든다. 일봉을 직접 생성하는 경로가
    있으면 휴장일·상장 이전 구간·거래 정지 구간에 값을 채울 자리가 생긴다.

    행을 직접 만드는 것이 그 구조의 서명이다 — `period_rows.py`에 `FxRate(`가 없어야
    하는 것과 같은 검사다.
    """
    body = (SRC / "simulation" / "reinvest.py").read_text(encoding="utf-8")
    assert "DayBar(" not in body, (
        "시뮬레이터가 일봉을 직접 만든다 — 받아 둔 것에서만 고를 것 (헌법 원칙 V)")


def test_주식_경로에_값을_채우는_코드가_없다() -> None:
    """상장폐지·거래정지 구간을 마지막 값으로 메우면 손실이 통째로 가려진다."""
    paths = [
        SRC / "simulation" / "reinvest.py",
        SRC / "api" / "services" / "stock_simulation.py",
        SRC / "api" / "services" / "stock_series.py",
        SRC / "repository" / "stock_price.py",
    ]
    offenders: list[str] = []
    for path in paths:
        assert path.exists(), f"{path.name}이 없다 — 검사가 조용히 비어 버린다"
        body = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {t}" for t in FILL_TOKENS if t in body]
    assert offenders == [], f"주식 경로에 보간 흔적 (헌법 원칙 V): {offenders}"


# ─────────────────────────── 006: 검색용 목록·환율 판정 ───────────────────────────

LISTING_PATHS = [
    SRC / "repository" / "stock_listing.py",
    SRC / "api" / "services" / "listing_refresh.py",
    SRC / "api" / "services" / "listing_index.py",
    SRC / "api" / "services" / "stock_collect.py",
    SRC / "api" / "services" / "collection_gate.py",
]


def test_목록과_환율_판정에_값을_채우는_코드가_없다() -> None:
    """T083 — 헌법 원칙 V, FR-043a, FR-047. 빠진 종목·환율이 없는 구간을 값으로 메우지 않는다."""
    offenders: list[str] = []
    for path in LISTING_PATHS:
        assert path.exists(), f"{path.name}이 없다 — 검사가 조용히 비어 버린다"
        body = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {t}" for t in FILL_TOKENS if t in body]
    assert offenders == [], f"006 경로의 보간 흔적: {offenders}"


def test_종목_목록과_원본을_지우는_질의가_없다() -> None:
    """T083 — FR-019, FR-061, 헌법 원칙 V(원본 보존).

    빠진 종목은 `missing`으로 표시하고 원본 응답은 지우지 않는다. 지우는 경로가 생기면 005가 받아 둔
    시세와 이력이 가리키는 대상이 사라지고, 무엇이 잘못 왔는지 되짚을 근거도 사라진다. 점유는 지워야
    하는 것이라 다른 모듈(`stock_listing_lock.py`)에 둔다 — 한 파일에 섞으면 이 검사를 할 수 없다.
    """
    import ast

    body = (SRC / "repository" / "stock_listing.py").read_text(encoding="utf-8")
    assert "delete(" not in body and ".delete(" not in body
    tree = ast.parse(body)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "delete" not in names
