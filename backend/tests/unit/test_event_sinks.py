"""이벤트 싱크 검증 (T011) — research R3-4, FR-018a·018b.

핵심은 **싱크 실패가 서로 전파되지 않고, 호출자에게도 전파되지 않는다**는 것이다.
기록은 수집의 목적이 아니라 관찰 수단이므로, 관찰에 실패했다고 이미 한도를 써 가며
받고 있는 수집을 되돌리면 안 된다.

다만 불완전하다는 사실 자체는 남아야 한다. 조용히 넘기면 나중에 기록을 근거로
"수집이 정상이었다"는 잘못된 결론을 내린다.
"""
from __future__ import annotations

import pytest

from src.observability.events import CHUNK_STORED, LOG_SINK_FAILED, CollectionEvent
from src.observability.sinks import EventPublisher


class 실패싱크:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, event: CollectionEvent) -> None:
        self.calls += 1
        raise RuntimeError("싱크 고장")


class 성공싱크:
    def __init__(self) -> None:
        self.events: list[CollectionEvent] = []

    async def __call__(self, event: CollectionEvent) -> None:
        self.events.append(event)


def _event(kind: str = CHUNK_STORED) -> CollectionEvent:
    return CollectionEvent(job_id=1, currency="USD", kind=kind, rows_stored=261)


class Test실패_격리:
    async def test_DB가_실패해도_파일에_남는다(self) -> None:
        db, file = 실패싱크(), 성공싱크()
        pub = EventPublisher(db_sink=db, file_sink=file)
        await pub.publish(_event())
        assert len(file.events) == 1

    async def test_파일이_실패해도_DB에_남는다(self) -> None:
        db, file = 성공싱크(), 실패싱크()
        pub = EventPublisher(db_sink=db, file_sink=file)
        await pub.publish(_event())
        assert len(db.events) >= 1

    async def test_둘_다_실패해도_예외가_전파되지_않는다(self) -> None:
        """호출자는 수집 루프다. 여기서 예외가 올라가면 수집이 멈춘다 (FR-018a)."""
        pub = EventPublisher(db_sink=실패싱크(), file_sink=실패싱크())
        await pub.publish(_event())  # 예외 없이 끝나야 한다

    async def test_한쪽_실패가_다른쪽_호출을_막지_않는다(self) -> None:
        db, file = 실패싱크(), 성공싱크()
        pub = EventPublisher(db_sink=db, file_sink=file)
        await pub.publish(_event())
        assert db.calls == 1 and len(file.events) == 1


class Test불완전함_노출:
    async def test_DB_실패_건수를_센다(self) -> None:
        """DB 적재 실패는 DB에 남길 수 없다. 건수로 순환을 끊는다 (FR-018b)."""
        pub = EventPublisher(db_sink=실패싱크(), file_sink=성공싱크())
        await pub.publish(_event())
        await pub.publish(_event())
        assert pub.dropped == 2

    async def test_성공하면_건수가_늘지_않는다(self) -> None:
        pub = EventPublisher(db_sink=성공싱크(), file_sink=성공싱크())
        await pub.publish(_event())
        assert pub.dropped == 0

    async def test_파일_실패는_DB에_사건으로_남는다(self) -> None:
        """반대편 경로에 사실을 남긴다 (research R3-4)."""
        db = 성공싱크()
        pub = EventPublisher(db_sink=db, file_sink=실패싱크())
        await pub.publish(_event())
        kinds = [e.kind for e in db.events]
        assert LOG_SINK_FAILED in kinds

    async def test_파일_실패_사건이_또_실패해도_무한히_돌지_않는다(self) -> None:
        """`log_sink_failed`를 남기다 실패해 다시 남기려 들면 재귀가 된다."""
        pub = EventPublisher(db_sink=실패싱크(), file_sink=실패싱크())
        await pub.publish(_event())
        assert pub.dropped <= 2


class Test파일_싱크:
    """`caplog` 대신 수집 로거에 직접 붙은 핸들러로 검증한다.

    `caplog`는 루트 핸들러에 의존하는데, 수집 로거는 **전파하지 않는 것이 요구사항**
    이다(R3-10). 전파에 기대는 검증은 요구사항과 모순되고, 구성 순서에 따라 통과 여부가
    갈린다.
    """

    async def test_수집_로거로_한_줄을_쓴다(self, captured_logs) -> None:
        from src.observability.sinks import log_sink

        await log_sink(_event())
        assert any("USD" in r.getMessage() for r in captured_logs)

    async def test_구조화_필드가_실린다(self, captured_logs) -> None:
        from src.observability.sinks import log_sink

        await log_sink(_event())
        rec = captured_logs[-1]
        assert rec.kind == CHUNK_STORED
        assert rec.rows_stored == 261


class Test발행자_계약:
    def test_기본_생성이_가능하다(self) -> None:
        """호출부가 싱크를 몰라도 되어야 한다 (헌법 원칙 IV)."""
        pub = EventPublisher()
        assert pub.dropped == 0

    async def test_세션_없이도_동작한다(self) -> None:
        """DB 싱크가 없으면 파일에만 남기고 조용히 끝난다."""
        pub = EventPublisher(db_sink=None, file_sink=성공싱크())
        await pub.publish(_event())
        assert pub.dropped == 0


class Test도달_확인:
    """FR-017a — 호출이 예외 없이 끝난 것을 성공으로 간주해서는 안 된다.

    비활성 로거에 `info()`를 부르면 **예외 없이 조용히 반환한다.** 예외 유무만 보면
    "전부 기록됨"과 "전부 유실됨"이 같은 신호(`dropped == 0`)를 낸다. 003 구현에서
    실제로 이 상태가 발생했고, 로그 파일이 안 생기는 것을 보고서야 드러났다.
    """

    async def test_비활성_로거를_유실로_센다(self) -> None:
        import logging

        from src.observability.logging_config import COLLECTION_LOGGER_NAME
        from src.observability.sinks import log_sink

        logger = logging.getLogger(COLLECTION_LOGGER_NAME)
        logger.disabled = True
        try:
            with pytest.raises(RuntimeError, match="기록 경로"):
                await log_sink(_event())
        finally:
            logger.disabled = False

    async def test_핸들러가_없으면_유실로_센다(self) -> None:
        """핸들러가 없으면 기록은 어디에도 남지 않는다."""
        import logging

        from src.observability.logging_config import COLLECTION_LOGGER_NAME
        from src.observability.sinks import log_sink

        logger = logging.getLogger(COLLECTION_LOGGER_NAME)
        saved = list(logger.handlers)
        logger.handlers = []
        try:
            with pytest.raises(RuntimeError, match="기록 경로"):
                await log_sink(_event())
        finally:
            logger.handlers = saved

    async def test_레벨이_높아도_유실로_센다(self) -> None:
        import logging

        from src.observability.logging_config import COLLECTION_LOGGER_NAME
        from src.observability.sinks import log_sink

        logger = logging.getLogger(COLLECTION_LOGGER_NAME)
        saved = logger.level
        logger.setLevel(logging.CRITICAL)
        try:
            with pytest.raises(RuntimeError, match="기록 경로"):
                await log_sink(_event())
        finally:
            logger.setLevel(saved)

    async def test_발행자가_그_유실을_센다(self, captured_logs) -> None:
        """SC-007a — 도달 확인 실패가 집계되어야 화면이 드러낼 수 있다."""
        import logging

        from src.observability.logging_config import COLLECTION_LOGGER_NAME

        logger = logging.getLogger(COLLECTION_LOGGER_NAME)
        logger.disabled = True
        try:
            pub = EventPublisher(db_sink=성공싱크())
            await pub.publish(_event())
        finally:
            logger.disabled = False
        # 파일 유실은 반대편(DB)에 `log_sink_failed`로 남는다.
        assert pub.dropped == 0  # DB는 살아 있다

    async def test_정상_상태에서는_예외가_없다(self, captured_logs) -> None:
        from src.observability.sinks import log_sink

        await log_sink(_event())
        assert captured_logs
