"""단지의 Npay 부동산 단지 번호 (010 반복 3, FR-029, data-model 8.2).

단지 하나에 한 행이다. 다시 찾으면(못 찾음을 정해진 날 수 뒤) 같은 행을 고친다 — 처음 넣은 시각
(`ingested_at`)은 남긴다. 실패는 여기까지 오지 않는다(저장하지 않는다).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import AptComplexNaver

FOUND = "found"
NOT_FOUND = "not_found"
SOURCE = "naver_land_autocomplete"


async def get(session: AsyncSession, complex_id: int) -> AptComplexNaver | None:
    return await session.get(AptComplexNaver, complex_id)


async def save(session: AsyncSession, complex_id: int, *, number: int | None, name: str | None,
               keyword: str, raw: str, now: dt.datetime) -> None:
    """찾음(`number`가 있음) 또는 못 찾음을 저장한다. 커밋은 부른 쪽이 한다."""
    await upsert(session, AptComplexNaver, [{
        "complex_id": complex_id,
        "status": FOUND if number is not None else NOT_FOUND,
        "naver_complex_no": number,
        "naver_name": name,
        "keyword": keyword,
        "checked_at": now,
        "raw_response": raw,
        "source": SOURCE,
        "ingested_at": now,
    }])
    # 같은 세션의 다음 `get`이 낡은 객체를 돌려주지 않게 — upsert는 ORM 객체를 거치지 않는다.
    session.expire_all()
