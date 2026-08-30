"""축적 시작일 하드코딩 정적 검사 (T115).

헌법 v4.1.0: 기준 시작일은 고정 상수가 아니다. 출처가 실제로 제공하는 최초 시점을
수집 중 발견해 기록해야 하며(MUST), **특정 날짜를 코드나 스키마에 하드코딩해서는
안 된다(MUST NOT)**.

이 검사가 존재하는 이유는 실제 사고 때문이다. 축적 시작일을 `1995-01-01`로 못박은
결과 USD는 31년, JPY는 18년치 데이터가 조용히 잘렸다. 출처는 그 이전부터 값을
제공하고 있었지만 아무도 알아채지 못했다 — 잘린 구간은 오류를 내지 않고 그냥 없다.

`float` 검사(T106)나 계층 경계 검사(T107)와 같은 부류다. 사람이 리뷰로 잡기 어렵고,
어겨져도 조용하기 때문에 기계적으로 막는다.
"""
from __future__ import annotations

import ast
import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

# 연도로 볼 만한 범위. 이보다 크면 날짜가 아니라 다른 상수다.
_YEAR_MIN, _YEAR_MAX = 1000, 2999

# "1995-01-01" 같은 ISO 날짜 문자열
_ISO_DATE = re.compile(r"\b[12]\d{3}-\d{2}-\d{2}\b")


def _python_files() -> list[pathlib.Path]:
    """마이그레이션도 포함한다 — 헌법이 금지하는 대상은 '코드나 **스키마**'다."""
    return sorted(SRC.rglob("*.py"))


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(SRC))


def test_날짜_생성자에_연도_리터럴이_없다() -> None:
    """`dt.date(1995, 1, 1)` 형태를 잡는다."""
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None)
            if name not in ("date", "datetime"):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, int):
                if _YEAR_MIN <= first.value <= _YEAR_MAX:
                    offenders.append(f"{_rel(path)}:{node.lineno}")
    assert offenders == [], (
        f"날짜가 코드에 하드코딩되어 있다 (헌법 v4.1.0): {offenders}. "
        "축적 시작일은 설정값으로 선언하고 실제 최초 제공일은 수집 중 발견해 기록한다."
    )


def test_ISO_날짜_문자열_리터럴이_없다() -> None:
    """`"1995-01-01"` 형태를 잡는다. docstring·주석은 설명이므로 제외한다."""
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(n.body[0].value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and n.body
            and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstrings:
                continue
            if _ISO_DATE.search(node.value):
                offenders.append(f"{_rel(path)}:{node.lineno}")
    assert offenders == [], (
        f"날짜 문자열이 코드에 하드코딩되어 있다 (헌법 v4.1.0): {offenders}"
    )
