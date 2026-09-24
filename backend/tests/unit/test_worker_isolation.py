"""계층 경계 정적 검사 (T076) — 헌법 원칙 IV.

수집 로직은 이벤트를 **발행만** 하고 어디에 남는지 모른다. 싱크를 아는 것은
`observability`뿐이며, 그것을 조립하는 것은 `worker`다.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
    return out


def test_ingestion은_싱크를_모른다() -> None:
    """수집이 기록 경로를 알면 수명 로직과 기록 포맷이 엉킨다."""
    offenders = [
        f"{p.relative_to(SRC)}"
        for p in (SRC / "ingestion").rglob("*.py")
        if any(m.startswith("src.observability.sinks") for m in _imports(p))
    ]
    assert offenders == [], f"ingestion이 싱크를 임포트한다: {offenders}"


def test_observability는_ingestion을_모른다() -> None:
    offenders = [
        f"{p.relative_to(SRC)}"
        for p in (SRC / "observability").rglob("*.py")
        if any(m.startswith("src.ingestion") for m in _imports(p))
    ]
    assert offenders == [], f"observability가 ingestion을 임포트한다: {offenders}"


def test_observability는_worker를_모른다() -> None:
    """의존 방향은 worker → observability 한쪽이어야 한다."""
    offenders = [
        f"{p.relative_to(SRC)}"
        for p in (SRC / "observability").rglob("*.py")
        if any(m.startswith("src.worker") for m in _imports(p))
    ]
    assert offenders == [], f"observability가 worker를 임포트한다: {offenders}"


def test_worker는_api_라우트를_모른다() -> None:
    offenders = [
        f"{p.relative_to(SRC)}"
        for p in (SRC / "worker").rglob("*.py")
        if any(m.startswith("src.api.routes") for m in _imports(p))
    ]
    assert offenders == [], f"worker가 라우트를 임포트한다: {offenders}"
