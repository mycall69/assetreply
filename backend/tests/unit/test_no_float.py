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


def test_기간_단위_경로에_float이_없다() -> None:
    """T042 — 헌법 원칙 VI, 004 FR-009.

    주·월 단위는 구간의 평균·시가·고가·저가를 산출하지 않는다. 집계가 없으므로
    `float`이 필요할 자리도 없다 — 생겼다면 어딘가에서 값을 계산하고 있다는 뜻이다.
    """
    paths = [
        SRC / "api" / "services" / "period_rows.py",
        SRC / "api" / "services" / "daily_query.py",
        SRC / "repository" / "fx_rate.py",
    ]
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "float"):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"기간 단위 경로에 float (원칙 VI): {offenders}"


# ─────────────────────────── 005: 주식 시뮬레이션 ───────────────────────────

#: 금액을 다루는 **api 계층** 모듈. `FINANCIAL_LAYERS`에 `api`가 없는 것은 의도된
#: 것이다 — 그 계층 대부분은 금액을 만지지 않는다. 만지는 곳만 이름으로 묶는다.
STOCK_MONEY_MODULES = (
    "api/services/stock_simulation.py",
    "api/services/stock_series.py",
    "api/services/stock_fx.py",
    "api/routes/stock_simulation.py",
    "api/routes/stock_series.py",
    "simulation/reinvest.py",
    "simulation/money.py",
    "simulation/fx_convert.py",
)


def test_주식_금액_경로에_float이_없다() -> None:
    """T100 — 헌법 원칙 VI.

    **참조 구현이 JS `number`를 쓰므로 이식 과정 전체가 위험 구간이다.** 옮겨 적다가
    `float()` 하나가 섞이면 수수료·세율 곱셈에서 끝자리가 흔들리는데, 표는 멀쩡해
    보이고 테스트도 근사 비교라면 통과한다.
    """
    offenders: list[str] = []
    for rel in STOCK_MONEY_MODULES:
        path = SRC / rel
        assert path.exists(), f"{rel}이 없다 — 경로가 바뀌면 검사가 조용히 비어 버린다"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "float"):
                offenders.append(f"{rel}:{node.lineno}")
    assert offenders == [], f"주식 금액 경로에 float (원칙 VI): {offenders}"


def test_주식_금액_경로에_float_주석이_없다() -> None:
    offenders: list[str] = []
    for rel in STOCK_MONEY_MODULES:
        tree = ast.parse((SRC / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.AnnAssign)
                    and isinstance(node.annotation, ast.Name)
                    and node.annotation.id == "float"):
                offenders.append(f"{rel}:{node.lineno}")
    assert offenders == [], f"주식 금액 경로에 float 주석: {offenders}"


# ─────────────────────────── 006: 검색용 목록·환율 판정 ───────────────────────────

#: 006이 더한 경로 (T082). 목록에는 가격을 담지 않지만, 축소 비율·환율 판정이 금액과 비율을 다룬다.
PATHS_006 = [
    *sorted((SRC / "search").rglob("*.py")),
    *sorted((SRC / "ingestion" / "kiwoom").rglob("*.py")),
    *sorted((SRC / "api" / "services").glob("listing_*.py")),
    SRC / "api" / "services" / "stock_collect.py",
]


def test_006_경로에_float이_없다() -> None:
    """T082 — 헌법 원칙 VI. 축소 검사의 비율(`LISTING_SHRINK_THRESHOLD`)은 `Decimal`이다."""
    assert len(PATHS_006) >= 8, "검사 대상이 비었다 — 경로가 바뀌면 조용히 통과한다"
    offenders: list[str] = []
    for path in PATHS_006:
        assert path.exists(), path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "float":
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
            if isinstance(node, ast.Name) and node.id == "float" \
                    and isinstance(node.ctx, ast.Load):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno} (타입)")
    assert offenders == [], f"006 경로의 float: {offenders}"
