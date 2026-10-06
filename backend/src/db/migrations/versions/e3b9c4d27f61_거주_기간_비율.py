"""거주 기간 비율 (010 반복 5)

`apt_setting`에 `residence_ratio DECIMAL(9,6) NULL`을 더한다 — 거주 기간 = 보유 기간 ×
비율(양도소득세의 비과세· 장기보유특별공제, research R10-21). NULL이면 기본값 1.000000이다(기존 행은
그대로 읽힌다). 다른 열은 바꾸지 않는다.

Revision ID: e3b9c4d27f61
Revises: d5e1f7a93c28
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b9c4d27f61"
down_revision: str | None = "d5e1f7a93c28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPREAD = sa.Numeric(9, 6)


def upgrade() -> None:
    op.add_column("apt_setting", sa.Column("residence_ratio", SPREAD, nullable=True))


def downgrade() -> None:
    op.drop_column("apt_setting", "residence_ratio")
