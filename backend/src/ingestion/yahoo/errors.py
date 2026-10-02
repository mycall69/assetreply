"""시세 출처 오류 타입 (T011) — 005 contracts/rest-api 오류표.

001의 `ingestion/ecos/errors.py`와 같은 모양이다. 오류를 **종류별로 나누는** 이유는
사용자가 할 일이 다르기 때문이다 — 없는 종목은 다시 고르면 되고, 호출 한도는 기다려야
하고, 장애는 우리가 할 수 있는 것이 없다.

**"결과 없음"과 "출처가 죽음"을 같게 다루면** 사용자는 그 종목이 존재하지 않는다고
읽는다. 할 일이 정반대인데 화면이 같은 말을 하게 된다.
"""

from __future__ import annotations


class StockSourceError(Exception):
    """시세 출처 오류의 뿌리."""


class StockSymbolNotFound(StockSourceError):
    """출처가 그 종목을 모른다 (404)."""


class StockSourceUnavailable(StockSourceError):
    """출처가 응답하지 않거나 본문이 유효하지 않다 (502)."""


class StockSourceRateLimited(StockSourceError):
    """출처의 호출 한도를 소진했다 (503).

    출처가 한도를 공개하지 않으므로 상태 코드가 유일한 신호다. 공격적 폴링이 차단의
    주된 원인이라, 설정의 호출 간격을 보수적으로 둔다 (005 research R5-1).
    """


class StockSourceAuthError(StockSourceError):
    """인증이 거절됐다 (502)."""


#: 시세가 시작되기 전 구간을 요청했을 때의 오류 표지 (006 T090 실측). `error.code`와 설명의 앞부분.
_NO_DATA_CODE = "Bad Request"
_NO_DATA_PREFIX = "Data doesn't exist for startDate"


def _is_no_data_in_range(body: object) -> bool:
    """**구간에 시세가 없다**는 응답인가 — 오류가 아니라 빈 구간이다.

    실측(2026-10-02): 시세가 시작되기 전 구간을 요청하면 HTTP 400과 `chart.error`
    `{"code": "Bad Request", "description": "Data doesn't exist for startDate = …"}`가 온다.
    005는 빈 결과로 온다고 가정하고 출처 장애로 올렸다. 그러면 수집 작업이 실패하고 커버리지가
    남지 않아 요청할 때마다 같은 실패를 되풀이한다.
    """
    chart = body.get("chart") if isinstance(body, dict) else None
    error = chart.get("error") if isinstance(chart, dict) else None
    if not isinstance(error, dict) or error.get("code") != _NO_DATA_CODE:
        return False
    description = error.get("description")
    return isinstance(description, str) and description.startswith(_NO_DATA_PREFIX)


def raise_for_response(status: int, body: object) -> None:
    """상태 코드와 본문을 함께 보고 오류를 구별한다.

    **상태 코드만 보면 놓치는 경로가 있다.** 200인데 본문의 `error`가 채워진 경우가
    그것이며, 그대로 두면 조용히 빈 결과가 되어 사용자는 데이터가 없다고 읽는다.

    출처 응답 본문을 메시지에 그대로 싣지 않는다 — 내부 사정이 사용자 화면에 새어
    나가면 안 되고, 출처가 문구를 바꾸면 우리 화면이 따라 바뀐다.
    """
    if status in (200, 400) and _is_no_data_in_range(body):
        # 빈 구간 — 받으러 갔고 값이 없었다. 커버리지에 남겨 다시 받으러 가지 않는다.
        return
    if status == 429:
        raise StockSourceRateLimited("시세 출처의 호출 한도를 소진했습니다.")
    if status in (401, 403):
        raise StockSourceAuthError("시세 출처가 요청을 거절했습니다.")
    if status == 404:
        raise StockSymbolNotFound("시세 출처가 그 종목을 알지 못합니다.")
    if status >= 500:
        raise StockSourceUnavailable("시세 출처가 응답하지 않습니다.")

    if not isinstance(body, dict):
        raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")

    chart = body.get("chart")
    if isinstance(chart, dict) and chart.get("error") is not None:  # noqa: SIM102
        # 빈 결과(`result`에 메타만 있는 경우)는 오류가 아니다. 상장 이전 구간을
        # 요청하면 정상적으로 그렇게 온다.
        raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")
