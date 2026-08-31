"""오늘 수집 경로의 커버리지 격리 정적 검사 (T077).

FR-037b / research R2-2: 잠정 저장이 커버리지를 전진시키면 다음 증분 수집이 그 날짜를
건너뛰고, **잠정값이 영원히 확정되지 않는다.** 오류가 나지 않아 며칠 뒤에야 드러난다.

`test_coverage_provisional.py`가 동작으로 검증하지만, 여기서는 **호출 자체가 없음**을
정적으로 막는다. 미래에 누군가 "편의를 위해" 커버리지 갱신을 넣는 것을 코드 리뷰가
아니라 테스트가 잡게 한다.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

# 커버리지를 전진시키는 함수들
FORBIDDEN = {"_record_coverage", "record_coverage", "update_coverage"}


def _called_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_오늘_수집_경로가_커버리지를_갱신하지_않는다() -> None:
    called = _called_names(SRC / "ingestion" / "today.py")
    offenders = called & FORBIDDEN
    assert offenders == set(), (
        f"ingestion/today.py가 커버리지를 갱신한다: {offenders}. "
        "잠정 저장이 커버리지를 전진시키면 확정 전환이 영원히 일어나지 않는다 (FR-037b)")


def test_오늘_수집_경로가_커버리지_모듈을_임포트하지_않는다() -> None:
    tree = ast.parse((SRC / "ingestion" / "today.py").read_text(encoding="utf-8"))
    imported = {
        n.module for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not any("coverage" in m for m in imported), (
        "커버리지 모듈을 임포트할 이유가 없다. 임포트 자체를 막아 경계를 분명히 한다.")


def test_새로고침_서비스도_커버리지를_갱신하지_않는다() -> None:
    called = _called_names(SRC / "api" / "services" / "today_refresh.py")
    assert called & FORBIDDEN == set()
