"""API 계층 도메인 예외.

앱 팩토리(`main.py`)와 라우터가 모두 참조하므로 별도 모듈에 둔다. `main.py`에 두면
라우터 → main → 라우터 순환 임포트가 생긴다.

contracts/rest-api.md의 공통 오류표와 1:1로 대응한다.
"""

from __future__ import annotations

import datetime as dt


class UnknownCurrency(Exception):
    """지원하지 않는 통화 (404)."""


class OutOfRange(Exception):
    """조회 가능한 범위 밖 (FR-019, 400)."""


class InvalidSpread(Exception):
    """스프레드가 허용 범위를 벗어남 (FR-025, 422)."""


class CollectionInProgress(Exception):
    """다른 통화의 수집이 진행 중 (003 FR-029, 409).

    조용히 무시하지 않고 예외로 올리는 이유는, 사용자에게 **어느 통화가 진행 중인지**
    알려야 하기 때문이다. 버튼만 반응이 없으면 고장으로 여긴다.
    """


class InvalidQuery(Exception):
    """필수 질의 매개변수가 없거나 조합이 잘못됨 (003, 400)."""


class InvalidSetting(Exception):
    """주식 설정 값이 허용 범위를 벗어남 (005 FR-015, FR-016, 422).

    조용히 기본값으로 떨어뜨리지 않는다 — 수수료·세금이 사라진 결과가 나오는데
    값은 그럴듯하고 오류도 없다.
    """


class UnknownStock(Exception):
    """우리 DB에 없고 검색용 목록으로도 등록할 수 없는 종목 (006 FR-030b, 404).

    시세 출처가 심볼을 모르는 것(`price_symbol_unknown`)과 다르다 — 이쪽은 **검색에서 다시 고르면**
    풀린다. 그래서 응답에 할 일(`action: reselect`)을 싣는다.
    """


class UnknownListing(Exception):
    """검색용 목록에 없는 행 (006 contracts `POST /api/stocks/selection`, 404)."""


class CurrencyPairNotAllowed(Exception):
    """원금 통화가 원화도 종목 통화도 아니다 (006 FR-050, 400).

    005는 이 조합을 원화를 경유하지 않고 계산해 오류 없이 틀린 수익률을 냈다(원금 1,000 EUR이
    0.77 USD). 막는 이유와 **고를 수 있는 통화**를 함께 싣는다.
    """

    def __init__(self, message: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.allowed = allowed


class UnknownCoin(Exception):
    """코인을 찾을 수 없다 (007, 404 `unknown_coin`). 검색에서 다시 고르면 풀린다 — 할 일을 함께
    싣는다.

    이력(브라우저)은 DB와 따로 산다. 지운 적은 없지만(FR-005a) DB를 새로 만들었으면 이력의 코인 id가
    없다.
    """


class StartAfterEnd(Exception):
    """시작일이 계산 끝(UTC 어제)보다 늦다 (007 FR-009, 400 `start_after_end`). 계산할 일봉이
    없다. 008 — 예금은 계산 끝이 오늘(한국 시간)이라 문구를 따로 준다(FR-005)."""

    def __init__(self, last_day: dt.date, message: str | None = None) -> None:
        super().__init__(message or (
            f"{last_day.isoformat()}(UTC 어제)까지의 일봉만 있습니다. "
            "시작일을 그 이전으로 고르세요."))
        self.last_day = last_day


class UnknownInstitution(Exception):
    """예금 투자처 키가 다섯 밖이다 (008 FR-003, 400 `unknown_institution`). 고를 수 있는 키를 함께
    싣는다."""

    def __init__(self, message: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.allowed = allowed


class InstallmentNotAvailable(Exception):
    """출처에 그 투자처의 정기적금 금리 통계가 없다 (011 FR-029, 400 `installment_not_available`).
    적금을 고를 수 있는 투자처를 함께 싣는다 — 정기예금 금리로 대신 계산하지 않는다."""

    def __init__(self, message: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.allowed = allowed


class CurrencyNotAllowed(Exception):
    """예금 원금 통화가 원화가 아니다 (008 FR-004, 400 `currency_not_allowed`). 화면에는 통화 칸이
    없지만 이력·직접 요청이 다른 통화를 실어 올 수 있다 — 조용히 원화로 읽지 않는다."""

    def __init__(self, message: str, allowed: list[str]) -> None:
        super().__init__(message)
        self.allowed = allowed


class NoRateData(Exception):
    """수집을 마쳤는데 그 투자처의 금리가 하나도 없다 (008, 404 `no_rate_data`). 빈 표를 보이면
    사용자는 수익이 0이라고 읽는다."""


class UnknownRegion(Exception):
    """행정구역 코드가 없거나 사라졌다 (009 FR-002, 400 `unknown_region`). 개편으로 사라진 코드는
    출처가 0건을 정상으로 주므로 "거래 없음"이 아니라 거절로 알린다."""


class UnknownComplex(Exception):
    """모르는 단지 id다 (009 FR-003, 400 `unknown_complex`)."""


class RegionRetired(Exception):
    """단지의 시·군·구 코드가 개편으로 사라졌고 새 코드로 아직 받지 않았다 (009 FR-002, 409
    `region_retired`). 받을 수 없는 옛 코드를 기다리거나 "거래 없음"으로 보이지 않게 한다."""

    def __init__(self, message: str, lawd_cd: str) -> None:
        super().__init__(message)
        self.lawd_cd = lawd_cd


class UnknownAsset(Exception):
    """모르는 자산군이다 (012, 404 `unknown_asset`). 이력 경로의 `{asset}`은 stock · crypto ·
    deposit · realestate뿐이다."""


class InvalidHistory(Exception):
    """이력 조건이 틀렸다 (012, 422 `invalid_history`). 메시지가 어느 칸인지 말한다 — 빠진 칸을
    기본값으로 채워 저장하면 다시 실행이 다른 조건으로
    돈다."""
