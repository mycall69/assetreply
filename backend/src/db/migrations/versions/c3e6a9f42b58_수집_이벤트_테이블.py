"""수집 이벤트 테이블과 기록 누락 건수 (003 T008)

`fx_collection_event`를 만들고 `fx_collection_job`에 `events_dropped`를 더한다.

이번 기능이 새로 만드는 저장 구조는 이벤트 테이블 하나뿐이다. 나머지는 001·002가
가진 데이터를 다르게 읽는다 — 이어받기 지점은 `job.range_start`, 오늘 호출 수는
`fx_raw_response` 행 수, 멈춤 판정은 `lock.heartbeat_at` 경과다.

Revision ID: c3e6a9f42b58
Revises: b2d5f8c31e47
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e6a9f42b58"
down_revision: str | None = "b2d5f8c31e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fx_collection_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("chunk_from", sa.Date(), nullable=True),
        sa.Column("chunk_to", sa.Date(), nullable=True),
        sa.Column("rows_stored", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["fx_collection_job.id"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currency.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # 작업별 시간순 조회
    op.create_index("ix_event_job_time", "fx_collection_event",
                    ["job_id", "occurred_at"])
    # 통화별 보관 범위 정리 (research R3-9). 조인 없이 찾을 수 있어야 한다.
    op.create_index("ix_event_currency_job", "fx_collection_event",
                    ["currency_code", "job_id"])

    # 기존 행은 기록 누락이 없었으므로 0으로 채운다. NULL로 두면 "기록 완전함"과
    # "확인하지 않음"이 구별되지 않는다.
    op.add_column(
        "fx_collection_job",
        sa.Column("events_dropped", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
    )

    # `fx_raw_response(received_at)` 인덱스는 001이 이미 만들어 두었다. 오늘 호출 수
    # 집계(research R3-5)가 그것을 그대로 쓴다 — 새로 만들 것이 없다.


def downgrade() -> None:
    op.drop_column("fx_collection_job", "events_dropped")
    op.drop_index("ix_event_currency_job", table_name="fx_collection_event")
    op.drop_index("ix_event_job_time", table_name="fx_collection_event")
    op.drop_table("fx_collection_event")
