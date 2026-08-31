"""수집 커버리지 리포지토리 (T049, T011).

**커버리지는 확정 수집만 반영한다** (FR-037b, research R2-2). 잠정 레코드(오늘 값)를
저장해도 `covered_through`는 전진하지 않는다.

이 규칙이 왜 중요한가: 001의 재개 로직(`ingestion/collector.next_start_date`)은
`covered_through + 1`부터 다시 받는다. 잠정 저장이 커버리지를 오늘까지 밀면 다음 증분
수집이 오늘을 건너뛰고, **잠정값이 영원히 확정값으로 대체되지 않는다.** 화면은 확정
표시로 바뀌지도 않고 정정도 반영되지 않는데 오류는 나지 않는다.

따라서 잠정 저장 경로(`ingestion/today.py`)는 이 모듈의 갱신 함수를 호출하지 않는다.
`tests/unit/test_today_isolation.py`가 그 사실을 정적으로 검사한다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCoverage


async def get_coverage(session: AsyncSession, currency_code: str) -> FxCoverage | None:
    return (await session.execute(
        select(FxCoverage).where(
            FxCoverage.currency_code == currency_code))).scalar_one_or_none()


async def list_coverage(session: AsyncSession) -> list[FxCoverage]:
    return list((await session.execute(
        select(FxCoverage).order_by(FxCoverage.currency_code))).scalars())
