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
