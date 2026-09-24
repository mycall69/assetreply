"""이벤트 싱크 — DB 적재와 파일 로깅 (T012) — research R3-4.

하나의 발행 함수가 두 싱크를 각각 호출한다. **싱크 실패는 서로 전파되지 않고, 호출자
에게도 전파되지 않는다** (FR-018a). 기록은 수집의 목적이 아니라 관찰 수단이라, 관찰에
실패했다고 이미 한도를 써 가며 받고 있는 수집을 되돌릴 이유가 없다.

다만 불완전하다는 사실은 남아야 한다 (FR-018b).

| 실패한 싱크 | 처리 |
|-------------|------|
| 파일 로깅 | DB에 `log_sink_failed` 사건을 추가한다. 화면에서 보인다 |
| DB 적재 | 파일에 남기고 **누락 건수를 센다**. 작업 종료 시 작업 행에 한 번 쓴다 |

DB 적재 실패를 DB에 남길 수 없는 순환을 건수로 끊는다.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.observability.events import LOG_SINK_FAILED, CollectionEvent
from src.observability.logging_config import collection_logger

Sink = Callable[[CollectionEvent], Awaitable[None]]


async def log_sink(event: CollectionEvent) -> None:
    """파일 로그에 한 줄로 남긴다."""
    collection_logger().info(event.message(), extra=event.as_log_fields())


def db_sink_for(session: AsyncSession) -> Sink:
    """세션에 묶인 DB 싱크를 만든다.

    **커밋하지 않는다.** 수집 루프가 청크 커밋과 함께 묶어 내보내므로, 여기서 커밋하면
    청크 경계가 흐려진다. 사건만 세션에 얹는다.
    """
    async def _sink(event: CollectionEvent) -> None:
        from src.db.models import FxCollectionEvent
        session.add(FxCollectionEvent(**event.as_row()))
        await session.flush()

    return _sink


class EventPublisher:
    """사건을 두 싱크로 내보낸다.

    수집 로직은 이 객체의 `publish`만 안다. 어느 싱크가 있는지, 하나가 죽었는지는
    관심 밖이다 (헌법 원칙 IV).
    """

    __slots__ = ("_db", "_file", "dropped")

    def __init__(self, *, db_sink: Sink | None = None, file_sink: Sink | None = None) -> None:
        self._db = db_sink
        self._file = file_sink if file_sink is not None else log_sink
        #: DB 적재에 실패한 사건 수. 작업 종료 시 `fx_collection_job.events_dropped`에
        #: 한 번 쓴다 — 사건마다 갱신하면 실패가 잦을 때 그 갱신이 부하가 된다.
        self.dropped = 0

    async def publish(self, event: CollectionEvent) -> None:
        """사건을 두 싱크로 내보낸다. 어떤 예외도 호출자에게 올리지 않는다."""
        file_ok = await self._try(self._file, event)
        db_ok = await self._try(self._db, event)

        if not db_ok:
            self.dropped += 1

        # 파일이 죽었으면 반대편(DB)에 그 사실을 남긴다. DB도 죽었다면 남길 곳이
        # 없으므로 시도하지 않는다 — 시도하면 같은 실패를 반복하며 재귀에 가까워진다.
        if not file_ok and db_ok:
            notice = CollectionEvent(
                job_id=event.job_id, currency=event.currency, kind=LOG_SINK_FAILED,
                detail="파일 기록에 실패했습니다. 이 작업의 파일 로그가 불완전합니다.",
            )
            if not await self._try(self._db, notice):
                self.dropped += 1

    @staticmethod
    async def _try(sink: Sink | None, event: CollectionEvent) -> bool:
        """싱크를 호출하고 성공 여부를 돌려준다. 싱크가 없으면 성공으로 본다."""
        if sink is None:
            return True
        try:
            await sink(event)
        except Exception:  # noqa: BLE001 — 어떤 싱크 실패도 수집을 멈춰서는 안 된다
            return False
        return True
