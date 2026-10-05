"""공공데이터포털 응답 고유 이름의 경계 (T008) — 009 FR-013, 헌법 원칙 II·IV.

출처의 필드 이름·결과 코드·게이트웨이 형식은 `src/ingestion/datagokr/` 밖에 나오면 안 된다 — 출처를
바꾸면 도메인이 함께 무너진다. `simulation/apt_*.py`가 상위 계층을 임포트하지 않는 것은 기존
`test_layer_boundaries.py`가 검사한다.

저장 계층의 짝짓기 열(`apt_seq`·`kapt_code` — 스네이크 표기)은 도메인 이름이라 검사하지 않는다. 낙타
표기의 출처 필드명만 본다.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"
ADAPTER = SRC / "ingestion" / "datagokr"

TOKENS = ("aptSeq", "excluUseAr", "dealAmount", "cdealType", "dealingGbn", "kaptCode", "kaptdaCnt",
          "region_cd", "locatadd_nm", "resultCode", "returnReasonCode", "serviceKey",
          "OpenAPI_ServiceResponse")


def _strings(path: pathlib.Path) -> list[tuple[int, str]]:
    """코드의 문자열 상수(docstring 제외)와 이름."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
    }
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            found.append((node.lineno, node.value))
        elif isinstance(node, ast.Name):
            found.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            found.append((node.lineno, node.attr))
    return found


def test_출처_필드명이_어댑터_밖에_없다() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if ADAPTER in path.parents or "migrations" in path.parts:
            continue
        for line, value in _strings(path):
            for token in TOKENS:
                if token in value:
                    offenders.append(f"{path.relative_to(SRC)}:{line} {token}")
    assert offenders == [], f"공공데이터포털 형식이 어댑터 밖에 있다(헌법 원칙 II): {offenders}"


def test_어댑터는_있다() -> None:
    """빈 디렉터리로 위 검사가 헛돌지 않게 한다."""
    assert (ADAPTER / "client.py").exists()
    assert any("serviceKey" in v for _, v in _strings(ADAPTER / "client.py"))
