"""예금 스키마 (008)

테이블 6개를 더한다. 기존 테이블은 바꾸지 않는다(008 data-model). 금리는 연 % 그대로 `DECIMAL(7,4)`, 세율은
기존 `SPREAD`. 원본에는 URL 열이 없다 — 인증키가 URL 경로에 있다(FR-014). 원본은 처음부터 MEDIUMTEXT다
(005~007과 같은 이유).

Revision ID: c4d8e2f91b07
Revises: b7e3c9d14a26
Create Date: 2026-10-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2f91b07"
down_revision: str | None = "b7e3c9d14a26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
RATE_PCT = sa.Numeric(7, 4)
SPREAD = sa.Numeric(9, 6)
JOB_STATUS = sa.Enum(
    "running", "succeeded", "partial", "failed",
    native_enum=False, length=16, name="jobstatus")
MEDIUMTEXT = sa.Text(length=16_777_215)


def upgrade() -> None:
    op.create_table(
        "deposit_rate",
        sa.Column("institution", sa.String(24), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("rate", RATE_PCT, nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("ingested_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("institution", "month"),
    )

    op.create_table(
        "deposit_raw_response",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("institution", sa.String(24), nullable=True),
        sa.Column("endpoint", sa.String(24), nullable=False),
        sa.Column("source_ref", sa.String(32), nullable=False),
        sa.Column("requested_from", sa.Date(), nullable=True),
        sa.Column("requested_to", sa.Date(), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("result_code", sa.String(16), nullable=True),
        sa.Column("body", MEDIUMTEXT, nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deposit_raw_received", "deposit_raw_response", ["received_at"])

    op.create_table(
        "deposit_coverage",
        sa.Column("institution", sa.String(24), nullable=False),
        sa.Column("first_month", sa.Date(), nullable=False),
        sa.Column("latest_month", sa.Date(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("institution"),
    )

    op.create_table(
        "deposit_collection_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("institution", sa.String(24), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("months_total", sa.Integer(), nullable=False),
        sa.Column("months_done", sa.Integer(), nullable=False),
        sa.Column("started_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deposit_job_status", "deposit_collection_job", ["institution", "status"])

    op.create_table(
        "deposit_collection_lock",
        sa.Column("institution", sa.String(24), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("acquired_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("heartbeat_at", TS, server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["deposit_collection_job.id"]),
        sa.PrimaryKeyConstraint("institution"),
    )

    op.create_table(
        "deposit_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("interest_tax_rate", SPREAD, nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("deposit_setting")
    op.drop_table("deposit_collection_lock")
    op.drop_table("deposit_collection_job")
    op.drop_table("deposit_coverage")
    op.drop_table("deposit_raw_response")
    op.drop_table("deposit_rate")
