"""대시보드 지표 (014)

대시보드 지표 12개(환율 셋은 외환의 고시 이력을 쓴다)의 일별 확정 종가를 저장한다(014 FR-017~FR-019,
data-model 1). 테이블 넷:
- `market_indicator_daily` — `(indicator_id, trade_date)` 복합 기본 키, 종가 `DECIMAL(20,6)`,
  `source`·`ingested_at`
- `market_indicator_raw` — 청크 응답 본문 그대로(`Text(16_777_215)` — utf8mb4에서 LONGTEXT). 색인 `(indicator_id, received_at)`
- `market_indicator_coverage` — 지표마다 발견한 첫 날·받은 연속 구간·마지막 성공·실패
- `market_close_revision` — 확정 값이 출처에서 바뀐 사실. 같은 `(indicator_id, trade_date,
  source_close)`는 한 번만

기존 테이블은 바꾸지 않는다.

Revision ID: c8d4f1a2e9b7
Revises: b3e7d5a1c924
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4f1a2e9b7"
down_revision: str | None = "b3e7d5a1c924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
PRICE = sa.Numeric(20, 6, asdecimal=True)


def upgrade() -> None:
    op.create_table(
        "market_indicator_daily",
        sa.Column("indicator_id", sa.String(32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("close", PRICE, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("ingested_at", TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("indicator_id", "trade_date"),
    )
    op.create_table(
        "market_indicator_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("indicator_id", sa.String(32), nullable=False),
        sa.Column("requested_from", sa.Date(), nullable=False),
        sa.Column("requested_to", sa.Date(), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("body", sa.Text(length=16_777_215), nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_raw_received", "market_indicator_raw", ["indicator_id", "received_at"]
    )
    op.create_table(
        "market_indicator_coverage",
        sa.Column("indicator_id", sa.String(32), nullable=False),
        sa.Column("first_day", sa.Date(), nullable=True),
        sa.Column("covered_from", sa.Date(), nullable=True),
        sa.Column("covered_through", sa.Date(), nullable=True),
        sa.Column("last_success_at", TS, nullable=True),
        sa.Column("last_failure_at", TS, nullable=True),
        sa.Column("last_failure_kind", sa.String(32), nullable=True),
        sa.Column("last_failure_message", sa.String(500), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("indicator_id"),
    )
    op.create_table(
        "market_close_revision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("indicator_id", sa.String(32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("stored_close", PRICE, nullable=False),
        sa.Column("source_close", PRICE, nullable=False),
        sa.Column("detected_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "indicator_id", "trade_date", "source_close", name="ux_market_close_revision"
        ),
    )


def downgrade() -> None:
    op.drop_table("market_close_revision")
    op.drop_table("market_indicator_coverage")
    op.drop_index("ix_market_raw_received", table_name="market_indicator_raw")
    op.drop_table("market_indicator_raw")
    op.drop_table("market_indicator_daily")
