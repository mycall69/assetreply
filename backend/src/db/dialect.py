"""DB 방언 격리 (T020, research R12).

**이 파일은 DB 방언 구문이 존재할 수 있는 유일한 곳이다.** 다른 모듈에서
`on_duplicate_key_update`·`on_conflict_do_update` 같은 방언 API를 직접 호출하면
헌법 v4.0.0 위반이다.

upsert는 표준 SQL에 없으므로 격리가 유일한 이식 수단이다. DB를 교체할 때 손댈 지점이
이 함수 하나로 모인다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.db.models import Base

# 행 데이터. 값 타입이 컬럼마다 달라 object로 받는다(`Any`는 mypy strict가 금지).
Row = dict[str, object]


async def upsert(
    session: AsyncSession,
    model: type[Base],
    rows: list[Row],
    *,
    preserve: tuple[str, ...] = ("ingested_at",),
) -> None:
    """기본 키가 충돌하면 갱신하고 아니면 삽입한다 (FR-003, FR-003a).

    `preserve`에 나열된 컬럼은 갱신에서 제외한다. `ingested_at`을 보존하는 이유는
    최초 수집 시각이 정정으로 덮여서는 안 되기 때문이다(FR-003a).
    """
    if not rows:
        return

    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    pk = {str(c.name) for c in model.__table__.primary_key}
    updatable = [k for k in rows[0] if k not in pk and k not in preserve]

    if dialect == "mysql":
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        my_stmt = mysql_insert(model).values(rows)
        await session.execute(
            my_stmt.on_duplicate_key_update(
                **{k: my_stmt.inserted[k] for k in updatable}))
    elif dialect in ("postgresql", "postgres"):
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        pg_stmt = pg_insert(model).values(rows)
        await session.execute(
            pg_stmt.on_conflict_do_update(
                index_elements=sorted(pk),
                set_={k: pg_stmt.excluded[k] for k in updatable}))
    else:
        raise NotImplementedError(
            f"{dialect} 방언의 upsert가 구현되지 않았습니다. 이 함수에 분기를 추가하세요.")

