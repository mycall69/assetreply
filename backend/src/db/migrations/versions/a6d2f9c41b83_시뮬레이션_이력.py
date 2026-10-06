"""시뮬레이션 이력 (012)

최근 시뮬레이션 이력을 브라우저에서 로컬 DB로 옮긴다(012 FR-011~FR-013, data-model 1). 테이블 둘:
- `simulation_history` — 기본 키 `(asset_class, condition_key)`, 조건(서버가 직렬화한 JSON 글),
  마지막 실행 시각, 보관 기준 시각(UTC).
  목록 색인 `ix_simulation_history_list (asset_class, last_run_at)`
- `history_setting` — 단일 행, 보관 기간(비원생 열거). 행이 없으면 기본 30일이다

기존 테이블은 바꾸지 않는다.

Revision ID: a6d2f9c41b83
Revises: f4c2a8e19d35
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6d2f9c41b83"
down_revision: str | None = "f4c2a8e19d35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
ASSET_CLASSES = ("stock", "crypto", "deposit", "realestate")
RETENTIONS = ("days_7", "days_30", "days_90", "days_180", "days_365", "unlimited")


def upgrade() -> None:
    op.create_table(
        "simulation_history",
        sa.Column(
            "asset_class",
            sa.Enum(*ASSET_CLASSES, native_enum=False, length=16, name="history_asset_class"),
            nullable=False,
        ),
        sa.Column("condition_key", sa.String(255), nullable=False),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("last_run_at", TS, nullable=False),
        sa.Column("retain_from", TS, nullable=False),
        sa.PrimaryKeyConstraint("asset_class", "condition_key"),
    )
    op.create_index(
        "ix_simulation_history_list", "simulation_history", ["asset_class", "last_run_at"]
    )
    op.create_table(
        "history_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "retention",
            sa.Enum(*RETENTIONS, native_enum=False, length=16, name="history_retention"),
            nullable=False,
        ),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("history_setting")
    op.drop_index("ix_simulation_history_list", table_name="simulation_history")
    op.drop_table("simulation_history")
