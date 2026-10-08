"""저장한 비교 (013)

투자 비교의 조건을 이름을 붙여 저장한다(013 FR-016~FR-018, data-model 1). 테이블 하나:
- `saved_comparison` — 자동 증가 `id`, 이름, 자산군(비원생 열거), 조건(서버가 직렬화한 JSON 글),
  저장 시각(UTC). 목록 색인 `ix_saved_comparison_list (saved_at, id)`

보관 기간이 없다 — 지울 때까지 남는다. 기존 테이블은 바꾸지 않는다.

Revision ID: b3e7d5a1c924
Revises: a6d2f9c41b83
Create Date: 2026-10-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7d5a1c924"
down_revision: str | None = "a6d2f9c41b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
ASSET_CLASSES = ("stock", "crypto", "deposit", "realestate")


def upgrade() -> None:
    op.create_table(
        "saved_comparison",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "asset_class",
            sa.Enum(*ASSET_CLASSES, native_enum=False, length=16, name="comparison_asset_class"),
            nullable=False,
        ),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("saved_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_comparison_list", "saved_comparison", ["saved_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_saved_comparison_list", table_name="saved_comparison")
    op.drop_table("saved_comparison")
