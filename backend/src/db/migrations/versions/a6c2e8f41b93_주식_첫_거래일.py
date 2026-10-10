"""주식 첫 거래일 (014 반복 2026-10-10f)

종목에 시세 출처(Yahoo)의 첫 거래일(차트 meta)을 둔다(014 FR-033, data-model §12, research
R14-26). **표시 전용**이다 — 시작일 하한(`first_available_date`)과 별개라 메뉴의 시작일 판정이 바뀌지
않는다. `DATE` NULL이다 — 모르면 비운다(지어내지 않는다). 등록·주식 수집이 비었을 때만 채운다.

Revision ID: a6c2e8f41b93
Revises: d5e1a7c3b2f8
Create Date: 2026-10-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c2e8f41b93"
down_revision: str | None = "d5e1a7c3b2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stock", sa.Column("first_trade_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("stock", "first_trade_date")
