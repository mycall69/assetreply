"""기준금리 (014 반복 2026-10-11d)

대시보드 기준금리 칸(다섯 중앙은행)의 결정 이력을 저장한다(014 FR-043, data-model 17). 테이블 셋:
- `policy_rate_decision` — 결정 하나(동결 포함). `(bank, decided_on)` 유일, 금리 `DECIMAL(8,4)`, 발표 시각 UTC(자리 표시면 NULL),
  `source`·`ingested_at`
- `policy_rate_raw` — 출처 응답 본문 그대로(목록·결정 이력 쪽). 색인 `(bank, fetched_at)`
- `policy_rate_bank` — 은행마다 다음 결정 예정일·처음 받기 끝남·마지막 겹쳐 받은 날·마지막 성공·실패

기존 테이블은 바꾸지 않는다.

Revision ID: e9f3b7c2a4d1
Revises: a6c2e8f41b93
Create Date: 2026-10-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f3b7c2a4d1"
down_revision: str | None = "a6c2e8f41b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)


def upgrade() -> None:
    op.create_table(
        "policy_rate_decision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bank", sa.String(8), nullable=False),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("announced_at", TS, nullable=True),
        sa.Column("rate", sa.Numeric(8, 4, asdecimal=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ingested_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank", "decided_on", name="ux_policy_rate_decision"),
    )
    op.create_table(
        "policy_rate_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "kind",
            sa.Enum("list", "calendars", native_enum=False, length=16, name="policy_rate_raw_kind"),
            nullable=False,
        ),
        sa.Column("bank", sa.String(8), nullable=True),
        sa.Column("page", sa.SmallInteger(), nullable=True),
        sa.Column("body", sa.Text(length=16_777_215), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_rate_raw_fetched", "policy_rate_raw", ["bank", "fetched_at"])
    op.create_table(
        "policy_rate_bank",
        sa.Column("bank", sa.String(8), nullable=False),
        sa.Column("next_meeting_on", sa.Date(), nullable=True),
        sa.Column("history_complete", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_overlap_on", sa.Date(), nullable=True),
        sa.Column("last_success_at", TS, nullable=True),
        sa.Column("last_failure_at", TS, nullable=True),
        sa.Column("failure_kind", sa.String(16), nullable=True),
        sa.Column("failure_message", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("bank"),
    )


def downgrade() -> None:
    op.drop_table("policy_rate_bank")
    op.drop_index("ix_policy_rate_raw_fetched", table_name="policy_rate_raw")
    op.drop_table("policy_rate_raw")
    op.drop_table("policy_rate_decision")
