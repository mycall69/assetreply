"""확정/잠정 구분 컬럼 추가 (T009)

헌법 v5.0.0 원칙 V: 출처가 아직 확정하지 않은 구간의 값은 잠정으로 표시해야 하며,
확정값과 구분 없이 저장해서는 안 된다.

기존 행은 전부 확정값이므로 기본값을 거짓으로 채운다. 백필이나 데이터 이동이 필요 없다.

`quote_date` 상한("오늘 미만" → "오늘 이하")은 DB 제약이 아니라 문서상 검증 규칙이므로
이 리비전의 대상이 아니다. 완화는 `repository/fx_rate.py`와 data-model 문서에 반영한다.

Revision ID: a1c4e7b90d21
Revises: 143d3d278574
Create Date: 2026-08-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c4e7b90d21'
down_revision: str | Sequence[str] | None = '143d3d278574'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fx_rate",
        sa.Column(
            "is_provisional",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="출처가 아직 확정하지 않은 값인지 (헌법 v5.0.0 원칙 V)",
        ),
    )


def downgrade() -> None:
    op.drop_column("fx_rate", "is_provisional")
