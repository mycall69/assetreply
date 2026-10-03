"""배당 소득세 해외 (006 FR-055)

`stock_setting`에 `dividend_tax_rate_foreign`(기본 0.15)을 더한다. 기존 `dividend_tax_rate`는 **국내 세율**로
그대로 둔다 — 값을 보존하고 이름을 바꾸지 않는다(마이그레이션 위험을 줄인다, research R6-23).

Revision ID: 4fee5b817ff0
Revises: 83c4cc99bc40
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4fee5b817ff0"
down_revision: str | None = "83c4cc99bc40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `models.SPREAD`와 같은 자릿수 — 비율이다.
RATE = sa.Numeric(9, 6, asdecimal=True)


def upgrade() -> None:
    op.add_column("stock_setting", sa.Column(
        "dividend_tax_rate_foreign", RATE, nullable=False,
        server_default=sa.text("0.150000")))


def downgrade() -> None:
    op.drop_column("stock_setting", "dividend_tax_rate_foreign")
