"""Alembic 마이그레이션 실행 헬퍼 (T021 보조).

헌법 v4.0.0은 마이그레이션을 ORM 마이그레이션 도구로만 관리하도록 요구한다.
이 모듈은 Alembic을 코드에서 호출하기 위한 얇은 래퍼이며, 스키마 정의를 담지 않는다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config

from src.config.settings import load_settings


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "src" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", load_settings().database_url)
    return cfg


def _run(fn: Callable[[Config, str], None], revision: str) -> None:
    fn(_alembic_config(), revision)


async def upgrade_head() -> None:
    """최신 리비전까지 적용한다."""
    await asyncio.to_thread(_run, command.upgrade, "head")


async def downgrade_base() -> None:
    """모든 리비전을 되돌린다."""
    await asyncio.to_thread(_run, command.downgrade, "base")


async def reset_schema() -> None:
    """스키마를 비운 뒤 최신 리비전까지 다시 적용한다 (**테스트 전용**).

    `downgrade base`를 쓰지 않는 이유: MySQL은 DDL이 트랜잭션이 아니라서 downgrade가
    중간에 실패하면 일부만 지워진 상태로 남고, 이후 모든 downgrade가 그 지점에서 막힌다.
    테스트 픽스처가 downgrade의 정확성에 의존하면 무관한 실패로 스위트 전체가 멈춘다.

    이 함수는 스키마 관리 수단이 아니다. 운영 스키마 변경은 반드시 Alembic 리비전으로만
    수행한다(헌법 v4.0.0).
    """
    from sqlalchemy import text

    from src.config.settings import load_settings as _load
    from src.db.engine import create_engine, dispose_engine

    engine = create_engine(_load())
    async with engine.begin() as conn:
        # 원시 SQL 사유: 아래 세 문장은 ORM으로 표현할 수 없다.
        #  - `SET FOREIGN_KEY_CHECKS`는 MySQL 전용 세션 변수다. 외래 키 순서를 고려한
        #    삭제 정렬을 직접 구현하는 것보다 단순하고, **테스트 전용 경로**이므로
        #    이식성 제약(헌법 v4.0.0)의 대상이 아니다. 운영 스키마는 Alembic만 다룬다.
        #  - `information_schema` 조회는 "현재 존재하는 테이블 전부"를 알아야 하는데,
        #    ORM 메타데이터는 과거 리비전이 남긴 테이블을 알지 못한다.
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        rows = (await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE()"))).scalars().all()
        for name in rows:
            await conn.execute(text(f"DROP TABLE IF EXISTS `{name}`"))
        # 위와 동일한 사유 — 제약 검사를 원상 복구한다
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    await dispose_engine(engine)
    await upgrade_head()
