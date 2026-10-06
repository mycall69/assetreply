"""주식 매도 세금 설정 (011)

`stock_setting`에 열 셋을 더한다 — 국내 매도 세율 `sale_tax_rate_domestic DECIMAL(9,6) NULL`, 해외 양도소득세율
`capital_gains_rate_foreign DECIMAL(9,6) NULL`, 해외 연간 기본공제 `capital_gains_deduction_foreign DECIMAL(15,0) NULL`.
NULL이면 기본값(0.20%·22%·2,500,000원 — 코드의 상수)이다. 기존 행(수수료·배당 세율만)은 그대로 읽힌다. 다른 열은 바꾸지 않는다
(011 FR-035·FR-037, research R11-7).

Revision ID: f4c2a8e19d35
Revises: e3b9c4d27f61
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c2a8e19d35"
down_revision: str | None = "e3b9c4d27f61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPREAD = sa.Numeric(9, 6)
WON = sa.Numeric(15, 0)


def upgrade() -> None:
    op.add_column("stock_setting", sa.Column("sale_tax_rate_domestic", SPREAD, nullable=True))
    op.add_column("stock_setting", sa.Column("capital_gains_rate_foreign", SPREAD, nullable=True))
    op.add_column("stock_setting",
                  sa.Column("capital_gains_deduction_foreign", WON, nullable=True))


def downgrade() -> None:
    op.drop_column("stock_setting", "capital_gains_deduction_foreign")
    op.drop_column("stock_setting", "capital_gains_rate_foreign")
    op.drop_column("stock_setting", "sale_tax_rate_domestic")
