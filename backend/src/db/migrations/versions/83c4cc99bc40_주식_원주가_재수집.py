"""주식 원주가 재수집 (006 FR-034)

**데이터 정정이다. 스키마는 바꾸지 않는다.**

005~006 T090까지의 수집은 시세 출처가 분할을 소급 반영한 시가·종가·배당을 원주가 자리에
저장했다(006 research R6-18, T090 결함 5). 시뮬레이션이 분할 날 주식 수를 다시 늘려 분할이 두 번
들어간다. 어느 종목이 그런지는 DB만으로 알 수 없다 — 분할이 든 청크는 수집이 실패해 분할 행조차
없다.

그래서 **주식 커버리지를 비워 모두 다시 받게 한다.** 다시 받으면 upsert가 되살린 원주가로 덮는다.
시세·배당·분할·원본은 지우지 않는다(헌법 원칙 V). 커버리지가 비면 202 게이트가 그 구간을 미수집으로
보므로, 다시 받기 전의 값으로 계산되는 일은 없다.

되돌리기는 하지 않는다 — 비운 커버리지는 다시 받으면 채워진다.

Revision ID: 83c4cc99bc40
Revises: f2b8c4d61a07
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "83c4cc99bc40"
down_revision: str | None = "f2b8c4d61a07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.table("stock_coverage").delete())


def downgrade() -> None:
    # 비운 커버리지는 되살리지 않는다. 다시 받으면 채워진다.
    pass
