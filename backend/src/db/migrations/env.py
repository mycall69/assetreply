"""Alembic 마이그레이션 환경 (비동기).

연결 URL은 저장소 루트의 `.env`에서 읽는다. `backend/`가 아니라 루트인 이유는
`.env`를 프로젝트 전체에서 하나로 관리하기 때문이다.

헌법 v3.0.0: 스키마 변경은 ORM 마이그레이션 도구로만 관리하며 수동 DDL을 금지한다.
"""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _repo_root() -> Path:
    """저장소 루트를 상위로 탐색해 찾는다.

    실행 위치에 의존하지 않도록 이 파일 기준으로 거슬러 올라가며 `.env.example`을 찾는다.
    하드코딩된 상대 경로를 쓰지 않는 이유는 크로스 플랫폼 요구사항 때문이다.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env.example").exists():
            return parent
    raise RuntimeError("저장소 루트를 찾지 못했습니다 (.env.example 부재)")


def _database_url() -> str:
    """루트 `.env`의 값으로 비동기 연결 URL을 만든다."""
    load_dotenv(_repo_root() / ".env")
    missing = [k for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
               if not os.getenv(k)]
    if missing:
        raise RuntimeError(f".env에 다음 값이 없습니다: {', '.join(missing)}")
    return (
        f"mysql+aiomysql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
        "?charset=utf8mb4"
    )


config.set_main_option("sqlalchemy.url", _database_url())

from src.db.models import Base  # noqa: E402  (URL 구성 이후에 임포트)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL 스크립트만 생성하는 모드."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진으로 마이그레이션을 실행한다 (헌법 원칙 I)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
