"""수정주가 미사용 (T027) — 005 FR-011, SC-005, 헌법 원칙 V·VI.

수정주가는 배당·분할을 **소급 반영한** 값이다. 거기에 배당을 또 더하면 같은 배당이 두
번 들어간다. 값은 그럴듯하고 차트도 매끄러워 **잘못을 알아챌 신호가 없다.**

수정주가는 나중에 배당·분할이 생기면 과거 값이 바뀐다. 원주가는 바뀌지 않는다 —
재현성(FR-014)이 원주가에 기대는 근거이기도 하다.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

#: 수정주가를 가리키는 이름. 시뮬레이션 경로에 나오면 FR-011 위반이다.
ADJUSTED_NAMES = ("close_adjusted", "adjclose", "adjusted_close")


def test_시뮬레이터가_수정주가를_읽지_않는다() -> None:
    body = (SRC / "simulation" / "reinvest.py").read_text(encoding="utf-8")
    for name in ADJUSTED_NAMES:
        assert name not in body, f"시뮬레이터가 수정주가를 참조한다: {name}"


def test_시뮬레이션_계층_전체에_수정주가가_없다() -> None:
    offenders: list[str] = []
    for path in (SRC / "simulation").rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        for name in ADJUSTED_NAMES:
            if name in body:
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"시뮬레이션 계층에 수정주가 참조: {offenders}"


def test_시뮬레이터는_순수_함수다() -> None:
    """헌법 원칙 IV — DB·HTTP 없이 단독 테스트가 가능해야 한다.

    이 경계가 원칙 VI 이식의 안전장치다. DB에 묶이면 참조 구현과의 대조가 통합
    테스트가 되고, 정밀도 차이가 다른 실패에 묻힌다.
    """
    tree = ast.parse((SRC / "simulation" / "reinvest.py").read_text(encoding="utf-8"))
    forbidden = ("src.repository", "src.api", "src.db", "src.ingestion")
    offenders = [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and node.module.startswith(forbidden)
    ]
    assert offenders == [], f"시뮬레이터가 상위 계층을 임포트한다: {offenders}"


def test_시뮬레이터에_float이_없다() -> None:
    """헌법 원칙 VI — 참조 구현이 JS `number`를 쓰므로 이식 전체가 위험 구간이다."""
    tree = ast.parse((SRC / "simulation" / "reinvest.py").read_text(encoding="utf-8"))
    offenders = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "float"
    ]
    assert offenders == [], f"시뮬레이터에 float 호출: {offenders}"
