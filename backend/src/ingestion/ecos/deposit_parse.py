"""ECOS 월 시계열 → 예금 금리 (008 T009, FR-016, FR-017, research R8-3·R8-5).

**출처는 오류도 HTTP 200으로 준다.** 본문 `RESULT.CODE`를 반드시 본다(001 parser와 같다).

- `INFO-200`(구간에 값 없음)은 **미발표**다 — 오류가 아니고, 상위 계층은 받은 구간으로
  기록하지 않는다(FR-010)
- 값을 읽을 수 없는 달이 하나라도 있으면 **응답 전체가 형식 오류**다 — 읽지 못한 달만 버리면
  결측(FR-019)으로 위장된다(FR-017)
- 실패는 네 종류로만 바깥에 알린다(`auth`·`rate_limited`·`format`·`network`, FR-016)
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation
from typing import Final

from src.ingestion.ecos.errors import (
    SourceAuthError,
    SourceError,
    SourceFormatError,
    SourceRateLimited,
    SourceUnavailable,
)
from src.ingestion.protocols import FetchOutcome, MonthlyFetchResult, MonthlyRate

_NO_DATA: Final = "INFO-200"


def fail_for(code: str, message: str) -> SourceError:
    """출처의 결과 코드를 오류로 옮긴다. `ERROR-*`와 모르는 코드는 형식 오류다(재시도해도 같다)."""
    if code == "INFO-100":
        return SourceAuthError(f"인증키 오류: {message}")
    if code == "INFO-300":
        return SourceRateLimited(f"호출 한도 초과: {message}")
    return SourceFormatError(f"출처 오류 {code}: {message}")


def deposit_failure_kind(exc: SourceError) -> str:
    """수집 실패의 종류(FR-016). 화면 문구와 할 일이 이 넷으로 갈린다(ui-wireframes D8)."""
    if isinstance(exc, SourceAuthError):
        return "auth"
    if isinstance(exc, SourceRateLimited):
        return "rate_limited"
    if isinstance(exc, SourceUnavailable):
        return "network"
    return "format"


def _rate(raw: object) -> Decimal | None:
    """`"3.2"`·`"3.39"`처럼 온다(끝의 0이 없을 수 있다). 쉼표는 지운다."""
    if raw is None:
        return None
    text = str(raw).replace(",", "").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


#: 금리의 저장 자릿수(연 %, `DECIMAL(7,4)`). 실측 최대 소수 2자리(research R8-11).
RATE_PLACES = 4


def _places(value: Decimal) -> int:
    """소수 자릿수. 끝의 0은 세지 않는다(`"3.20"` → 1)."""
    exponent = value.normalize().as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def _month(raw: str) -> dt.date | None:
    if len(raw) != 6 or not raw.isdigit():
        return None
    year, month = int(raw[:4]), int(raw[4:])
    return dt.date(year, month, 1) if 1 <= month <= 12 else None


def parse_monthly(body: str, *, status: int) -> MonthlyFetchResult:
    """월 시계열 응답을 읽는다. 오류면 도메인 예외를 던진다."""
    if status < 200 or status >= 300:
        raise SourceUnavailable(f"HTTP {status}: {body[:200]}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceUnavailable(f"응답이 JSON이 아닙니다(점검·차단 가능성): {body[:200]}") from exc
    if not isinstance(payload, dict):
        raise SourceUnavailable(f"예상하지 못한 응답 구조: {body[:200]}")

    result = payload.get("RESULT")
    if isinstance(result, dict):
        code = str(result.get("CODE", ""))
        if code == _NO_DATA:
            return MonthlyFetchResult((), FetchOutcome.NO_DATA, body, status, code)
        raise fail_for(code, str(result.get("MESSAGE", "")))

    container = payload.get("StatisticSearch")
    if not isinstance(container, dict):
        raise SourceFormatError(f"StatisticSearch 컨테이너가 없습니다: {body[:200]}")
    rows = container.get("row", [])
    if not isinstance(rows, list):
        raise SourceFormatError("StatisticSearch.row가 목록이 아닙니다")

    rates: list[MonthlyRate] = []
    for row in rows:
        if not isinstance(row, dict):
            raise SourceFormatError(f"행이 객체가 아닙니다: {row!r}")
        raw_time = str(row.get("TIME") or "")
        month = _month(raw_time)
        rate = _rate(row.get("DATA_VALUE"))
        if month is None or rate is None:
            # 한 달이라도 못 읽으면 응답 전체를 버린다 — 그 달만 버리면 결측으로 위장된다(FR-017).
            raise SourceFormatError(
                f"금리를 읽을 수 없습니다: TIME={raw_time!r} DATA_VALUE={row.get('DATA_VALUE')!r}")
        if _places(rate) > RATE_PLACES:
            # 저장 자릿수를 넘으면 조용히 반올림되어 출처 값과 달라진다(FR-017·FR-029, 반복 #2).
            raise SourceFormatError(
                f"금리가 소수 {RATE_PLACES}자리를 넘습니다: TIME={raw_time!r} "
                f"DATA_VALUE={row.get('DATA_VALUE')!r}")
        rates.append(MonthlyRate(month, rate))

    # 1회 요청 행 한도에 걸려 일부만 왔는지 — 잘린 구간을 받은 것으로 기록하면 뒤쪽 달이 결측이
    # 된다.
    total = container.get("list_total_count")
    if isinstance(total, int | str) and str(total).isdigit() and int(total) > len(rows):
        raise SourceFormatError(
            f"응답이 잘렸습니다: 전체 {total}건 중 {len(rows)}건만 받았습니다.")

    rates.sort(key=lambda r: r.month)
    outcome = FetchOutcome.OK if rates else FetchOutcome.NO_DATA
    return MonthlyFetchResult(tuple(rates), outcome, body, status, None)
