"""부동산 스키마 (009)

테이블 10개를 더한다(data-model 1~9절 — 작업·점유가 둘). 기존 테이블은 바꾸지 않는다. 면적은
`DECIMAL(9,4)`(출처가 소수 4자리까지 준다 — T001 실측), 금액은 원 단위 `DECIMAL(15,0)`, 비율은 기존
`SPREAD`. 거래의 유니크 키는 (자산 식별자, 날짜)를 거래 사건에 맞춘 것이다(응답 안 순번까지 —
research R9-4). 원본에는 URL 열이 없다 — 인증키가 질의 문자열에 있다(FR-013).

Revision ID: a9d3e5c71f20
Revises: c4d8e2f91b07
Create Date: 2026-10-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9d3e5c71f20"
down_revision: str | None = "c4d8e2f91b07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
AREA = sa.Numeric(9, 4)
WON = sa.Numeric(15, 0)
SPREAD = sa.Numeric(9, 6)
JOB_STATUS = sa.Enum(
    "running", "succeeded", "partial", "failed",
    native_enum=False, length=16, name="jobstatus")
MEDIUMTEXT = sa.Text(length=16_777_215)


def upgrade() -> None:
    op.create_table(
        "apt_region",
        sa.Column("code", sa.CHAR(10), nullable=False),
        sa.Column("level", sa.String(8), nullable=False),
        sa.Column("parent_code", sa.CHAR(10), nullable=True),
        sa.Column("lawd_cd", sa.CHAR(5), nullable=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("full_name", sa.String(80), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("ingested_at", TS, nullable=False),
        sa.Column("seen_at", TS, nullable=False),
        sa.Column("retired_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "apt_complex",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("umd_code", sa.CHAR(10), nullable=False),
        sa.Column("lawd_cd", sa.CHAR(5), nullable=False),
        sa.Column("apt_seq", sa.String(20), nullable=True),
        sa.Column("kapt_code", sa.String(20), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("jibun", sa.String(20), nullable=True),
        sa.Column("move_in_year", sa.SmallInteger(), nullable=True),
        sa.Column("move_in_source", sa.String(8), nullable=True),
        sa.Column("households", sa.Integer(), nullable=True),
        sa.Column("details_checked_at", TS, nullable=True),
        sa.Column("merged_into", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("apt_seq", name="uq_apt_complex_apt_seq"),
        sa.UniqueConstraint("kapt_code", name="uq_apt_complex_kapt_code"),
    )

    op.create_table(
        "apt_trade",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lawd_cd", sa.CHAR(5), nullable=False),
        sa.Column("deal_ym", sa.CHAR(6), nullable=False),
        sa.Column("deal_date", sa.Date(), nullable=False),
        sa.Column("apt_seq", sa.String(20), nullable=False),
        sa.Column("umd_code", sa.CHAR(10), nullable=False),
        sa.Column("jibun", sa.String(20), nullable=False),
        sa.Column("apt_name", sa.String(80), nullable=False),
        sa.Column("apt_dong", sa.String(20), nullable=False),
        sa.Column("floor", sa.SmallInteger(), nullable=False),
        sa.Column("excl_area", AREA, nullable=False),
        sa.Column("amount", WON, nullable=False),
        sa.Column("occurrence", sa.SmallInteger(), nullable=False),
        sa.Column("dealing_type", sa.String(8), nullable=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("cancelled_on", sa.Date(), nullable=True),
        sa.Column("missing_since", TS, nullable=True),
        sa.Column("missing_reason", sa.String(16), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("ingested_at", TS, nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lawd_cd", "deal_date", "apt_seq", "apt_dong", "floor", "excl_area",
                            "amount", "occurrence", name="uq_apt_trade_event"),
    )
    op.create_index("ix_apt_trade_complex", "apt_trade", ["apt_seq", "deal_date"])

    op.create_table(
        "apt_raw_response",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.String(24), nullable=False),
        sa.Column("request_ref", sa.String(40), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("result_code", sa.String(16), nullable=True),
        sa.Column("body", MEDIUMTEXT, nullable=False),
        sa.Column("body_sha256", sa.CHAR(64), nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apt_raw_request", "apt_raw_response",
                    ["endpoint", "request_ref", "received_at"])
    op.create_index("ix_apt_raw_received", "apt_raw_response", ["received_at"])

    op.create_table(
        "apt_trade_coverage",
        sa.Column("lawd_cd", sa.CHAR(5), nullable=False),
        sa.Column("deal_ym", sa.CHAR(6), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("trade_rows", sa.Integer(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("lawd_cd", "deal_ym"),
    )

    op.create_table(
        "apt_collection_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target", sa.String(20), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("started_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apt_job_target", "apt_collection_job", ["kind", "target", "status"])

    op.create_table(
        "apt_collection_lock",
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target", sa.String(20), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("acquired_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("heartbeat_at", TS, server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["apt_collection_job.id"]),
        sa.PrimaryKeyConstraint("kind", "target"),
    )

    op.create_table(
        "apt_api_usage",
        sa.Column("api", sa.String(16), nullable=False),
        sa.Column("kst_date", sa.Date(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("api", "kst_date"),
    )

    op.create_table(
        "apt_list_state",
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("refreshed_at", TS, nullable=True),
        sa.Column("first_trade_ym", sa.CHAR(6), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("scope"),
    )

    op.create_table(
        "apt_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("holding_tax_base_ratio", SPREAD, nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("apt_setting")
    op.drop_table("apt_list_state")
    op.drop_table("apt_api_usage")
    op.drop_table("apt_collection_lock")
    op.drop_table("apt_collection_job")
    op.drop_table("apt_trade_coverage")
    op.drop_table("apt_raw_response")
    op.drop_table("apt_trade")
    op.drop_table("apt_complex")
    op.drop_table("apt_region")
