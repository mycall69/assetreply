"""DB 방언 격리 정적 검사 (T108).

헌법 v4.0.0: 특정 DB에만 존재하는 문법에 도메인·저장 계층이 직접 의존해서는 안 되며,
필요하면 ORM의 방언 추상화 뒤에 격리해야 한다. 원시 SQL은 사유 주석을 남겨야 한다.

DB 교체 시 손댈 지점이 한 곳으로 모이는지를 기계적으로 확인한다 (research R12).
"""
from __future__ import annotations

import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

DIALECT_APIS = ("on_duplicate_key_update", "on_conflict_do_update",
                "sqlalchemy.dialects", "GENERATED ALWAYS", "Computed",
                "postgresql_where", "mysql_engine")

# 방언이 존재해도 되는 유일한 곳
DIALECT_HOME = "dialect.py"


def _source_files() -> list[pathlib.Path]:
    return [p for p in SRC.rglob("*.py") if "migrations" not in p.parts]


def test_방언_API가_dialect_모듈에만_있다() -> None:
    offenders: list[str] = []
    for path in _source_files():
        if path.name == DIALECT_HOME:
            continue
        body = path.read_text(encoding="utf-8")
        for api in DIALECT_APIS:
            if api in body:
                offenders.append(f"{path.relative_to(SRC)}: {api}")
    assert offenders == [], f"방언 API가 격리를 벗어남: {offenders}"


def test_dialect_모듈이_두_방언을_모두_지원한다() -> None:
    """한 방언만 지원하면 교체 가능성이라는 전제가 성립하지 않는다."""
    body = (SRC / "db" / DIALECT_HOME).read_text(encoding="utf-8")
    assert "on_duplicate_key_update" in body, "MySQL 분기가 없다"
    assert "on_conflict_do_update" in body, "PostgreSQL 분기가 없다"


def test_미지원_방언은_명시적으로_실패한다() -> None:
    """조용히 잘못된 SQL을 만드는 것보다 낫다."""
    body = (SRC / "db" / DIALECT_HOME).read_text(encoding="utf-8")
    assert "NotImplementedError" in body


# SQLAlchemy `text()` 호출만 잡는다. `response.text()` 같은 메서드 호출은 제외한다.
_RAW_SQL = re.compile(r"(?<![\w.])text\s*\(")


def test_원시_SQL에_사유_주석이_있다() -> None:
    """`text()` 사용처는 ORM으로 표현할 수 없는 이유를 남겨야 한다 (헌법 v4.0.0)."""
    offenders: list[str] = []
    for path in _source_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not _RAW_SQL.search(line) or "import" in line:
                continue
            window = "\n".join(lines[max(0, i - 6):i + 1])
            if not any(k in window for k in ("#", '"""', "ORM", "테스트 전용")):
                offenders.append(f"{path.relative_to(SRC)}:{i + 1}")
    assert offenders == [], f"사유 없는 원시 SQL: {offenders}"
