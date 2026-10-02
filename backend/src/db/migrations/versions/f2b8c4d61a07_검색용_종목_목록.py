"""검색용 종목 목록 (006)

테이블 5개를 더한다. 005의 `stock`은 바꾸지 않는다 — 목록의 상장일을
`stock.first_available_date`에 복사하지 않는다(006 research R6-8).

원본 본문은 `stock_listing_raw_body`에 **한 번만** 두고 지우지 않는다(헌법 원칙 V,
006 analyze C1). 처음부터 MEDIUMTEXT다 — 국내 KOSPI 목록 한 쪽이 약 800KB다(T005 실측).

Revision ID: f2b8c4d61a07
Revises: a4d91c7e55b0
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b8c4d61a07"
down_revision: str | None = "a4d91c7e55b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)


def upgrade() -> None:
    op.create_table(
        "stock_listing",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("name_ko", sa.String(128), nullable=True),
        sa.Column("name_en", sa.String(256), nullable=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("listed_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default=sa.text("'listed'")),
        sa.Column("first_seen_at", TS, nullable=False),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ingested_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ux_stock_listing_country_code", "stock_listing",
                    ["country", "code"], unique=True)
    op.create_index("ix_stock_listing_unit_status", "stock_listing", ["unit", "status"])

    op.create_table(
        "stock_listing_refresh",
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("as_of", TS, nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("attempt_date", sa.Date(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", TS, nullable=True),
        sa.Column("last_failed_at", TS, nullable=True),
        sa.Column("last_error_kind", sa.String(16), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.PrimaryKeyConstraint("unit"),
    )

    op.create_table(
        "stock_listing_lock",
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("heartbeat_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("unit"),
    )

    op.create_table(
        "stock_listing_raw_body",
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(length=16_777_215), nullable=False),
        sa.Column("first_stored_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("sha256"),
    )

    op.create_table(
        "stock_listing_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("batch_started_at", TS, nullable=False),
        sa.Column("page_no", sa.SmallInteger(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
        sa.ForeignKeyConstraint(["body_sha256"], ["stock_listing_raw_body.sha256"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stock_listing_raw")
    op.drop_table("stock_listing_raw_body")
    op.drop_table("stock_listing_lock")
    op.drop_table("stock_listing_refresh")
    op.drop_index("ix_stock_listing_unit_status", table_name="stock_listing")
    op.drop_index("ux_stock_listing_country_code", table_name="stock_listing")
    op.drop_table("stock_listing")
