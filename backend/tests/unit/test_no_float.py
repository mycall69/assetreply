"""부동소수점 사용 정적 검사 (T106).

헌법 원칙 VI: 금융 계산에 `float`을 금지하고, DB 컬럼과 **ORM 필드 매핑** 모두
`FLOAT`/`DOUBLE`을 금지한다.

조용히 어겨지기 쉬운 규칙이라 코드와 메타데이터 양쪽에서 기계적으로 검사한다.
"""
from __future__ import annotations

import ast
import pathlib

from sqlalchemy import Float

from src.db.models import Base

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

# 금융 값을 다루는 계층 — 여기서 float이 나오면 원칙 VI 위반이다
FINANCIAL_LAYERS = ("simulation", "repository", "db")

# 선택 기준으로만 float을 쓰고 출력에는 넣지 않는 곳 (근거는 해당 파일 docstring 참조)
ALLOWED = {"downsample.py"}


def _python_files(layer: str) -> list[pathlib.Path]:
    return [p for p in (SRC / layer).rglob("*.py") if "migrations" not in p.parts]


def test_금융_계층에_float_호출이_없다() -> None:
    offenders: list[str] = []
    for layer in FINANCIAL_LAYERS:
        for path in _python_files(layer):
            if path.name in ALLOWED:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "float":
                        offenders.append(f"{layer}/{path.name}:{node.lineno}")
    assert offenders == [], f"금융 계층에서 float() 호출: {offenders}"


def test_금융_계층에_float_타입_주석이_없다() -> None:
    offenders: list[str] = []
    for layer in FINANCIAL_LAYERS:
        for path in _python_files(layer):
            if path.name in ALLOWED:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name):
                    if node.annotation.id == "float":
                        offenders.append(f"{layer}/{path.name}:{node.lineno}")
    assert offenders == [], f"금융 계층에 float 타입 주석: {offenders}"


def test_ORM_메타데이터에_Float_컬럼이_없다() -> None:
    offenders = [
        f"{t.name}.{c.name}"
        for t in Base.metadata.tables.values()
        for c in t.columns
        if isinstance(c.type, Float)
    ]
    assert offenders == [], f"부동소수점 컬럼: {offenders}"


def test_예외_허용_파일이_근거를_남긴다() -> None:
    """면제된 파일은 왜 원칙을 위반하지 않는지 docstring에 밝혀야 한다."""
    for name in ALLOWED:
        matches = list(SRC.rglob(name))
        assert matches, f"{name}을 찾지 못했다"
        body = matches[0].read_text(encoding="utf-8")
        assert "원칙 VI" in body, f"{name}에 면제 근거가 없다"
