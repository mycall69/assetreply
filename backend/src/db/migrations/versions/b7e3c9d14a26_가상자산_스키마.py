"""가상자산 스키마 (007)

테이블 11개를 더한다. 기존 테이블은 바꾸지 않는다(007 data-model). 가격은 `DECIMAL(36,14)` — 출처 원값이 소수 14자리로
온다(research R7-3). 원본은 처음부터 MEDIUMTEXT다(005·006과 같은 이유).

Revision ID: b7e3c9d14a26
Revises: 4fee5b817ff0
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e3c9d14a26"
down_revision: str | None = "4fee5b817ff0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
CPRICE = sa.Numeric(36, 14)
CVOLUME = sa.Numeric(38, 8)
SPREAD = sa.Numeric(9, 6)
JOB_STATUS = sa.Enum(
    "running", "succeeded", "partial", "failed",
    native_enum=False, length=16, name="jobstatus")
MEDIUMTEXT = sa.Text(length=16_777_215)


def upgrade() -> None:
    op.create_table(
        "crypto_coin",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("slug", sa.String(128), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name_en", sa.String(256), nullable=False),
        sa.Column("name_ko", sa.String(256), nullable=True),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("market_rank", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default=sa.text("'listed'")),
        sa.Column("first_available_date", sa.Date(), nullable=True),
        sa.Column("first_seen_at", TS, nullable=False),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("ingested_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ux_crypto_coin_source_id", "crypto_coin", ["source", "source_id"],
                    unique=True)
    op.create_index("ix_crypto_coin_status", "crypto_coin", ["status"])

    op.create_table(
        "crypto_coin_refresh",
        sa.Column("edition", sa.String(4), nullable=False),
        sa.Column("as_of", TS, nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("attempt_date", sa.Date(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", TS, nullable=True),
        sa.Column("last_failed_at", TS, nullable=True),
        sa.Column("last_error_kind", sa.String(16), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.PrimaryKeyConstraint("edition"),
    )

    op.create_table(
        "crypto_list_lock",
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("heartbeat_at", TS, nullable=False),
        sa.Column("edition", sa.String(4), nullable=True),
        sa.Column("pages_done", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("coins_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("scope"),
    )

    op.create_table(
        "crypto_list_raw_body",
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("body", MEDIUMTEXT, nullable=False),
        sa.Column("first_stored_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("sha256"),
    )
    op.create_table(
        "crypto_list_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("edition", sa.String(4), nullable=False),
        sa.Column("batch_started_at", TS, nullable=False),
        sa.Column("page_no", sa.SmallInteger(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
        sa.ForeignKeyConstraint(["body_sha256"], ["crypto_list_raw_body.sha256"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "crypto_daily",
        sa.Column("coin_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("open", CPRICE, nullable=False),
        sa.Column("high", CPRICE, nullable=False),
        sa.Column("low", CPRICE, nullable=False),
        sa.Column("close", CPRICE, nullable=False),
        sa.Column("volume", CVOLUME, nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("ingested_at", TS, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["coin_id"], ["crypto_coin.id"]),
        sa.PrimaryKeyConstraint("coin_id", "day"),
    )

    op.create_table(
        "crypto_raw_response",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("coin_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_from", sa.Date(), nullable=False),
        sa.Column("requested_to", sa.Date(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("body", MEDIUMTEXT, nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.ForeignKeyConstraint(["coin_id"], ["crypto_coin.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crypto_raw_received", "crypto_raw_response", ["received_at"])

    op.create_table(
        "crypto_coverage",
        sa.Column("coin_id", sa.BigInteger(), nullable=False),
        sa.Column("covered_from", sa.Date(), nullable=False),
        sa.Column("covered_through", sa.Date(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["coin_id"], ["crypto_coin.id"]),
        sa.PrimaryKeyConstraint("coin_id"),
    )

    op.create_table(
        "crypto_collection_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("coin_id", sa.BigInteger(), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("chunks_total", sa.Integer(), nullable=False),
        sa.Column("chunks_done", sa.Integer(), nullable=False),
        sa.Column("started_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["coin_id"], ["crypto_coin.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crypto_job_status", "crypto_collection_job", ["coin_id", "status"])

    op.create_table(
        "crypto_collection_lock",
        sa.Column("coin_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("acquired_at", TS, server_default=sa.func.now(), nullable=True),
        sa.Column("heartbeat_at", TS, server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["coin_id"], ["crypto_coin.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["crypto_collection_job.id"]),
        sa.PrimaryKeyConstraint("coin_id"),
    )

    op.create_table(
        "crypto_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("trade_fee_rate", SPREAD, nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("crypto_setting")
    op.drop_table("crypto_collection_lock")
    op.drop_table("crypto_collection_job")
    op.drop_table("crypto_coverage")
    op.drop_table("crypto_raw_response")
    op.drop_table("crypto_daily")
    op.drop_table("crypto_list_raw")
    op.drop_table("crypto_list_raw_body")
    op.drop_table("crypto_list_lock")
    op.drop_table("crypto_coin_refresh")
    op.drop_table("crypto_coin")
