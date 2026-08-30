"""계층 경계 정적 검사 (T107).

헌법 원칙 IV: 도메인 계산 계층은 DB·HTTP에 의존하지 않는 순수 함수여야 한다.
헌법 원칙 II: ECOS 고유 개념은 `ingestion/ecos/` 밖으로 나가지 않는다.

계층이 섞이면 원칙 II(어댑터 교체)와 원칙 III(단독 테스트)이 동시에 무력화된다.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

# ECOS 응답 고유 필드명 — 어댑터 밖에서 등장하면 원칙 II 위반
ECOS_TOKENS = ("ITEM_CODE", "ITEM_NAME", "DATA_VALUE", "STAT_CODE",
               "StatisticSearch", "StatisticItemList", "INFO-100", "INFO-200", "INFO-300")


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def test_simulation은_상위_계층을_임포트하지_않는다() -> None:
    """DB와 HTTP 없이 단독 테스트가 가능해야 한다."""
    forbidden = ("src.repository", "src.api", "src.db", "src.ingestion")
    offenders: list[str] = []
    for path in (SRC / "simulation").rglob("*.py"):
        for module in _imports(path):
            if module.startswith(forbidden):
                offenders.append(f"{path.name} → {module}")
    assert offenders == [], f"simulation 계층 위반: {offenders}"


def test_repository는_api를_임포트하지_않는다() -> None:
    """예외 타입만 예외적으로 허용한다 (`src.api.errors`)."""
    offenders: list[str] = []
    for path in (SRC / "repository").rglob("*.py"):
        for module in _imports(path):
            if module.startswith("src.api") and module != "src.api.errors":
                offenders.append(f"{path.name} → {module}")
    assert offenders == [], f"repository 계층 위반: {offenders}"


def test_ECOS_필드명이_어댑터_밖에_없다() -> None:
    """헌법 원칙 II: 벤더 응답 형식이 도메인 계층에 노출되면 안 된다."""
    adapter = SRC / "ingestion" / "ecos"
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if adapter in path.parents or "migrations" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        for token in ECOS_TOKENS:
            if token in body:
                offenders.append(f"{path.relative_to(SRC)}: {token}")
    assert offenders == [], f"ECOS 고유 개념 노출: {offenders}"


def test_도메인_타입에_벤더_필드명이_없다() -> None:
    body = (SRC / "ingestion" / "protocols.py").read_text(encoding="utf-8")
    for token in ECOS_TOKENS:
        assert token not in body, f"protocols.py에 벤더 필드명: {token}"


def test_ingestion은_api를_임포트하지_않는다() -> None:
    offenders: list[str] = []
    for path in (SRC / "ingestion").rglob("*.py"):
        for module in _imports(path):
            if module.startswith("src.api"):
                offenders.append(f"{path.name} → {module}")
    assert offenders == [], f"ingestion 계층 위반: {offenders}"
