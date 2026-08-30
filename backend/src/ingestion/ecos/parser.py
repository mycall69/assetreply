"""ECOS 응답 → 도메인 타입 변환 (T045).

**출처는 오류도 HTTP 200으로 반환한다.** 본문 `RESULT` 코드를 반드시 검사한다.
상태 코드만 보면 오류를 성공으로 오인해 빈 데이터를 저장하게 된다 —
기존 Apps Script 구현이 실제로 밟았던 함정이다 (contracts/ecos-adapter.md).
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation

from src.ingestion.ecos.errors import (
    SourceAuthError,
    SourceError,
    SourceRateLimited,
    SourceResponseTruncated,
    SourceUnavailable,
)
from src.ingestion.protocols import DailyQuote, FetchOutcome, FetchResult

# 매매기준율만 취한다. 응답에 장중평균환율·종가가 섞여 온다.
_BASE_RATE_ITEM = "매매기준율"
# 100엔당으로 고시되는 통화를 판별한다 (FR-007).
#
# **주의**: 단위는 `UNIT_NAME`이 아니라 `ITEM_NAME1`에 있다. 실측 확인 결과 JPY의
# `UNIT_NAME`은 그냥 '원'이고, '원/일본엔(100엔)'처럼 항목명에만 단위가 드러난다.
# `UNIT_NAME`만 보면 JPY가 1엔당으로 오인되어 값이 100배 틀어진다.
_HUNDRED_UNIT_MARKER = "100"


def _fail(code: str, message: str) -> SourceError:
    """출처의 상태 코드를 도메인 오류로 옮긴다 (contracts/ecos-adapter.md 분류표)."""
    if code == "INFO-100":
        return SourceAuthError(f"인증키 오류: {message}")
    if code == "INFO-300":
        return SourceRateLimited(f"호출 한도 초과: {message}")
    if code.startswith("ERROR"):
        return SourceError(f"출처 오류 {code}: {message}")
    return SourceError(f"알 수 없는 출처 응답 {code}: {message}")


def _to_decimal(raw: object) -> Decimal | None:
    """`DATA_VALUE`는 '1,012.30'처럼 쉼표를 포함해 온다."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _quote_unit(item_name: object, unit_name: object) -> int:
    """고시 단위를 판별한다. 항목명을 우선 보고 단위명을 보조로 쓴다."""
    text = f"{item_name or ''} {unit_name or ''}"
    return 100 if _HUNDRED_UNIT_MARKER in text else 1


def parse_search_response(body: str, *, status: int) -> FetchResult:
    """조회 응답을 파싱한다. 오류면 도메인 예외를 던진다."""
    if status < 200 or status >= 300:
        raise SourceUnavailable(f"HTTP {status}: {body[:200]}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        # 차단 페이지 또는 점검 안내 HTML — JSON 파싱 실패와 구분해 기록한다
        raise SourceUnavailable(
            f"응답이 JSON이 아닙니다(차단·점검 가능성): {body[:200]}") from exc

    if not isinstance(payload, dict):
        raise SourceUnavailable(f"예상하지 못한 응답 구조: {body[:200]}")

    result = payload.get("RESULT")
    if isinstance(result, dict):
        code = str(result.get("CODE", ""))
        message = str(result.get("MESSAGE", ""))
        if code == "INFO-200":
            # 해당 구간에 고시가 없다 — 오류가 아니다
            return FetchResult((), FetchOutcome.NO_DATA, body, status, code)
        raise _fail(code, message)

    container = payload.get("StatisticSearch")
    if not isinstance(container, dict):
        raise SourceUnavailable(f"StatisticSearch 컨테이너가 없습니다: {body[:200]}")

    quotes: list[DailyQuote] = []
    for row in container.get("row", []):
        if not isinstance(row, dict):
            continue
        item_name2 = str(row.get("ITEM_NAME2") or "")
        if item_name2 and _BASE_RATE_ITEM not in item_name2:
            continue
        raw_time = str(row.get("TIME") or "")
        value = _to_decimal(row.get("DATA_VALUE"))
        if len(raw_time) != 8 or value is None:
            continue
        quotes.append(DailyQuote(
            quote_date=dt.date(int(raw_time[:4]), int(raw_time[4:6]), int(raw_time[6:8])),
            base_rate=value,
            quote_unit=_quote_unit(row.get("ITEM_NAME1"), row.get("UNIT_NAME")),
        ))

    # 1회 요청 행 한도에 걸려 일부만 왔는지 확인한다.
    # 감지하지 않으면 데이터가 빠진 채 커버리지만 갱신되어 영영 메워지지 않는다.
    total = container.get("list_total_count")
    received = len(container.get("row", []))
    if isinstance(total, int | str) and str(total).isdigit() and int(total) > received:
        raise SourceResponseTruncated(
            f"응답이 잘렸습니다: 전체 {total}건 중 {received}건만 수신했습니다. "
            f"청크 크기(ecos.chunk_days)를 줄이세요.")

    quotes.sort(key=lambda q: q.quote_date)
    outcome = FetchOutcome.OK if quotes else FetchOutcome.NO_DATA
    return FetchResult(tuple(quotes), outcome, body, status, None)

