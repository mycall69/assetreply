"""대시보드 시가 (014 반복 2026-10-10b)

대시보드 지표 일봉에 시가·고가·저가를 더한다(014 FR-017·FR-029, data-model 1.1, research R14-18). 열
셋 모두
`DECIMAL(20,6)` NULL이다 — 출처가 주지 않거나 0이면 비운다(0으로 메우지 않는다). 이미 넣은 날은
워커가 저장해 둔
원본 응답에서 되살린다(다시 받지 않는다). 종가·개정 표는 바꾸지 않는다.

Revision ID: d5e1a7c3b2f8
Revises: c8d4f1a2e9b7
Create Date: 2026-10-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e1a7c3b2f8"
down_revision: str | None = "c8d4f1a2e9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICE = sa.Numeric(20, 6, asdecimal=True)
COLUMNS = ("open_price", "high_price", "low_price")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("market_indicator_daily", sa.Column(name, PRICE, nullable=True))


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column("market_indicator_daily", name)
