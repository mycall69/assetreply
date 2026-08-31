"""통화 및 스프레드 기본값 시드

Revision ID: 143d3d278574
Revises: d408d00df25f
Create Date: 2026-08-30 11:29:19.168073

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '143d3d278574'
down_revision: str | Sequence[str] | None = 'd408d00df25f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None



# data-model.md 초기 데이터 — FR-007(JPY 100엔 단위), FR-024(기본 스프레드)
_CURRENCIES = [
    {"code": "USD", "display_name": "미국 달러", "quote_unit": 1, "source_item_code": "0000001"},
    {"code": "JPY", "display_name": "일본 엔", "quote_unit": 100, "source_item_code": "0000002"},
    {"code": "EUR", "display_name": "유로", "quote_unit": 1, "source_item_code": "0000003"},
]

# 값은 `src/db/spread_defaults.py` 한 곳에만 둔다. 리비전이 값을 따로 들고 있으면
# 복원 기본값과 시드가 언젠가 어긋나고, 그때 아무 오류도 나지 않는다 (T049).
from src.db.spread_defaults import DEFAULT_SPREADS  # noqa: E402

_SPREADS = [
    {"currency_code": code, **{k: str(v) for k, v in values.items()}}
    for code, values in DEFAULT_SPREADS.items()
]


def upgrade() -> None:
    currency = sa.table(
        "currency",
        sa.column("code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("quote_unit", sa.SmallInteger),
        sa.column("source_item_code", sa.String),
    )
    spread = sa.table(
        "fx_spread",
        sa.column("currency_code", sa.String),
        sa.column("cash_buy", sa.Numeric),
        sa.column("cash_sell", sa.Numeric),
        sa.column("remit_send", sa.Numeric),
        sa.column("remit_receive", sa.Numeric),
    )
    op.bulk_insert(currency, _CURRENCIES)
    op.bulk_insert(spread, _SPREADS)


def downgrade() -> None:
    op.execute("DELETE FROM fx_spread")
    op.execute("DELETE FROM currency")
