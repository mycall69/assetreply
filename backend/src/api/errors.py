"""API 계층 도메인 예외.

앱 팩토리(`main.py`)와 라우터가 모두 참조하므로 별도 모듈에 둔다. `main.py`에 두면
라우터 → main → 라우터 순환 임포트가 생긴다.

contracts/rest-api.md의 공통 오류표와 1:1로 대응한다.
"""

from __future__ import annotations


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
