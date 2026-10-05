"""계층 경계 정적 검사 (T107).

헌법 원칙 IV: 도메인 계산 계층은 DB·HTTP에 의존하지 않는 순수 함수여야 한다.
헌법 원칙 II: ECOS 고유 개념은 `ingestion/ecos/` 밖으로 나가지 않는다.

계층이 섞이면 원칙 II(어댑터 교체)와 원칙 III(단독 테스트)이 동시에 무력화된다.
"""
from __future__ import annotations

import ast
import pathlib
import re

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


def test_일자별_조회_서비스가_계산을_직접_하지_않는다() -> None:
    """T078 — 헌법 원칙 IV.

    `api/services/daily_query.py`는 `simulation/`의 순수 함수를 **호출만** 한다.
    표와 단일 날짜 조회가 다른 계산 경로를 타면 같은 입력에 다른 결과가 나올 수 있고,
    FR-027과 001의 재현성 보장이 함께 깨진다.
    """
    import ast

    path = SRC / "api" / "services" / "daily_query.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # 곱셈·나눗셈이 나오면 이 모듈이 직접 계산하고 있다는 뜻이다
    arithmetic = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult | ast.Div)
    ]
    assert arithmetic == [], "daily_query가 파생 환율을 직접 계산한다 (헌법 원칙 IV)"

    imported = {
        n.module for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module
    }
    assert any("simulation" in m for m in imported), "순수 함수를 재사용하지 않는다"


def test_기간_단위_서비스가_라우트를_임포트하지_않는다() -> None:
    """T041 — 헌법 원칙 IV.

    `api/services/period_rows.py`는 조회와 표현 **사이**에 있다. 라우트를 알게 되면
    구간 판정을 HTTP 없이 단독으로 테스트할 수 없어 원칙 III도 함께 무너진다.
    """
    path = SRC / "api" / "services" / "period_rows.py"
    offenders = [m for m in _imports(path) if m.startswith("src.api.routes")]
    assert offenders == [], f"period_rows 계층 위반: {offenders}"


def test_리포지토리가_구간_정의를_갖지_않는다() -> None:
    """T041, 004 — 주·월의 정의는 `period_rows.py` 한 곳에만 있어야 한다.

    SQL에 두면 DB마다 주 정의가 달라(MySQL은 일요일 시작, PostgreSQL은 ISO 월요일
    시작) 같은 질의가 **오류 없이 다른 묶음**을 돌려준다 (헌법 DB 운영 규약).
    """
    body = (SRC / "repository" / "fx_rate.py").read_text(encoding="utf-8")
    for token in ("YEARWEEK", "WEEKDAY", "DAYOFWEEK", "DATEDIFF", 'extract("week"',
                  "extract('week'", "monthrange"):
        assert token not in body, f"리포지토리에 구간 정의: {token}"


# ─────────────────────────── 005: 주식 시세 출처 ───────────────────────────

#: 시세 출처 응답의 고유 필드명. 어댑터 밖에서 등장하면 원칙 II 위반이다.
STOCK_SOURCE_TOKENS = ("adjclose", "gmtoffset", "chartPreviousClose",
                       "quoteType", "splitRatio", "firstTradeDate")


def test_시세_출처_필드명이_어댑터_밖에_없다() -> None:
    """T013 — 헌법 원칙 II.

    출처를 교체할 때 손댈 지점이 한곳으로 모여야 한다. **출처가 막히는 것은 "언젠가"가
    아니라 "언제"의 문제로 전제한다** (005 research R5-1).
    """
    adapter = SRC / "ingestion" / "yahoo"
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if adapter in path.parents or "migrations" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        for token in STOCK_SOURCE_TOKENS:
            if token in body:
                offenders.append(f"{path.relative_to(SRC)}: {token}")
    assert offenders == [], f"시세 출처 고유 개념 노출: {offenders}"


def test_재투자_시뮬레이터가_단독으로_선다() -> None:
    """T102 — 헌법 원칙 IV.

    `simulation/reinvest.py`가 DB·HTTP를 모르기 때문에 **참조 구현(Apps Script)과
    같은 입력을 넣어 같은 출력이 나오는지 단위 테스트로 확인할 수 있다**(research
    R5-4). 임포트가 하나라도 생기면 그 대조가 통합 테스트가 되고, 정밀도 차이가 다른
    실패에 묻힌다 — 원칙 III도 함께 무너진다.
    """
    path = SRC / "simulation" / "reinvest.py"
    forbidden = ("src.repository", "src.api", "src.db", "src.ingestion")
    offenders = [m for m in _imports(path) if m.startswith(forbidden)]
    assert offenders == [], f"reinvest 계층 위반: {offenders}"


# ─────────────────────────── 006: 검색용 종목 목록 ───────────────────────────

#: 키움 응답의 고유 필드명. 어댑터 밖에서 등장하면 원칙 II 위반이다.
KIWOOM_TOKENS = ("stk_cd", "stk_nm", "stk_enm", "stex_tp", "mrkt_tp", "regDay",
                 "listCount", "lastPrice", "marketName")


def test_키움_필드명이_어댑터_밖에_없다() -> None:
    """T011 — 헌법 원칙 II. 출처를 교체할 때 손댈 지점이 한곳으로 모여야 한다."""
    adapter = SRC / "ingestion" / "kiwoom"
    assert adapter.is_dir(), "ingestion/kiwoom이 없다 — 없는 경계를 검사하면 조용히 통과한다"
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if adapter in path.parents or "migrations" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        for token in KIWOOM_TOKENS:
            # 낱말 단위 — 009 응답 키 `lastPricedMonth`가 `lastPrice`를 품는다(2026-10-05 D2 승인)
            if re.search(rf"\b{re.escape(token)}\b", body):
                offenders.append(f"{path.relative_to(SRC)}: {token}")
    assert offenders == [], f"키움 고유 개념 노출: {offenders}"


def test_검색_모듈이_단독으로_선다() -> None:
    """T011 — 헌법 원칙 IV. 일치 판정·시세 식별자 변환은 DB·HTTP 없이 단독 테스트돼야 한다."""
    package = SRC / "search"
    assert package.is_dir(), "src/search가 없다 — 없는 모듈을 검사하면 조용히 통과한다"
    forbidden = ("src.repository", "src.api", "src.db", "src.ingestion")
    offenders = [
        f"{path.name} → {module}"
        for path in package.rglob("*.py")
        for module in _imports(path)
        if module.startswith(forbidden)
    ]
    assert offenders == [], f"search 계층 위반: {offenders}"
