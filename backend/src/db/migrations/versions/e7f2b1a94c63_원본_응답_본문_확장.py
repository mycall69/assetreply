"""원본 응답 본문을 MEDIUMTEXT로 확장

001이 `fx_raw_response.body`를 `TEXT`로 정의했는데, 한 해치 ECOS 응답이 그 한계
(65,535바이트)를 넘는다. 1964년이 197행에 57KB였고 거래일이 많은 해(약 260행)는
75KB에 이른다.

청크를 줄이면 호출 수가 늘어 일일 한도를 더 쓰므로 컬럼을 키우는 쪽이 맞다.

Revision ID: e7f2b1a94c63
Revises: c3e6a9f42b58
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f2b1a94c63"
down_revision: str | None = "c3e6a9f42b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "fx_raw_response", "body",
        existing_type=sa.Text(),
        type_=sa.Text(length=16_777_215),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 되돌리면 한계를 넘는 기존 행이 잘린다. 원본 응답은 갱신 전 값을 추적하는 유일한
    # 근거이므로(001 FR-003b), 되돌리기 전에 데이터 손실을 감수할지 판단해야 한다.
    op.alter_column(
        "fx_raw_response", "body",
        existing_type=sa.Text(length=16_777_215),
        type_=sa.Text(),
        existing_nullable=False,
    )
