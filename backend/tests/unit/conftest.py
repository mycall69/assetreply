"""단위 테스트 공용 픽스처.

로깅은 프로세스 전역 상태다. 통합 테스트가 앱을 띄우면서 수집 로거를 구성하면
(`propagate=False`, 파일 핸들러 부착) 그 상태가 단위 테스트까지 따라온다. 실제로
`tests/unit`만 돌릴 때는 통과하고 전체를 돌릴 때는 실패하는 순서 의존이 발생했다.

여기서 매 테스트마다 수집 로거를 원래대로 되돌려 그 의존을 끊는다.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from src.observability.logging_config import COLLECTION_LOGGER_NAME


@pytest.fixture(autouse=True)
def _isolate_collection_logger() -> Iterator[None]:
    logger = logging.getLogger(COLLECTION_LOGGER_NAME)
    saved = (list(logger.handlers), logger.level, logger.propagate, logger.disabled)

    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    logger.disabled = False
    try:
        yield
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logger.handlers, logger.level, logger.propagate, logger.disabled = saved


@pytest.fixture
def captured_logs() -> Iterator[list[logging.LogRecord]]:
    """수집 로거에 직접 핸들러를 붙여 기록을 모은다.

    `caplog`를 쓰지 않는 이유는 그것이 루트 핸들러에 의존하기 때문이다. 수집 로거는
    전파하지 않는 것이 요구사항이라(R3-10), 전파에 기대는 검증은 요구사항과 모순된다.
    """
    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(COLLECTION_LOGGER_NAME)
    handler = _Collect()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
