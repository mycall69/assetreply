"""주식 투자 시뮬레이션 스키마 (005)

테이블 9개를 더한다. `fx_*`와 합치지 않는 이유는 그쪽이 통화 단위이고 여기는 종목
단위라, 한 테이블에 섞으면 키 설계가 둘 다 어색해지고 FX 질의가 주식 행을 걸러내야
하기 때문이다 (005 research R5-7).

`stock_raw_response.body`를 **처음부터 MEDIUMTEXT로 둔다.** 001이 `fx_raw_response`에서
`TEXT`(65,535바이트)를 넘겨 마이그레이션을 한 번 더 했던 자리이고, 주식 일봉은 한 번에
수천 행이 온다.

금액·비율은 전부 `Numeric`이다. `Float`/`Double`은 곧바로 헌법 원칙 VI 위반이다.

Revision ID: a4d91c7e55b0
Revises: e7f2b1a94c63
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4d91c7e55b0"
down_revision: str | None = "e7f2b1a94c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICE = sa.Numeric(20, 6)
SPREAD = sa.Numeric(9, 6)
JOB_STATUS = sa.Enum(
    "running", "succeeded", "partial", "failed",
    native_enum=False, length=16, name="jobstatus")


def upgrade() -> None:
    op.create_table(
        "stock",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("market", sa.String(8), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("first_available_date", sa.Date(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ux_stock_market_symbol", "stock", ["market", "symbol"], unique=True)

    op.create_table(
        "stock_price",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        # 원주가. 시뮬레이션이 쓰는 값이다.
        sa.Column("open_raw", PRICE, nullable=False),
        sa.Column("close_raw", PRICE, nullable=False),
        # 수정주가. 보관만 하고 계산에 쓰지 않는다 (FR-011).
        sa.Column("close_adjusted", PRICE, nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("stock_id", "quote_date"),
    )

    op.create_table(
        "stock_dividend",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        # 세전이다. 세율은 설정이라 바뀌며, 세후를 저장하면 과거 행이 낡는다.
        sa.Column("amount_per_share", PRICE, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("stock_id", "ex_date"),
    )

    op.create_table(
        "stock_split",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        # 분자·분모 정수로 둔다. 소수면 3:1이 0.333333…이 되어 오차가 들어간다.
        sa.Column("numerator", sa.Integer(), nullable=False),
        sa.Column("denominator", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("stock_id", "effective_date"),
    )

    op.create_table(
        "stock_raw_response",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("requested_from", sa.Date(), nullable=True),
        sa.Column("requested_to", sa.Date(), nullable=True),
        # length를 주면 MySQL에서 MEDIUMTEXT(16MB)가 선택된다. 다른 DB에서는 각자의
        # 대용량 텍스트 타입이 골라지므로 이식성 규약을 지킨다.
        sa.Column("body", sa.Text(length=16_777_215), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_raw_received", "stock_raw_response", ["received_at"])

    op.create_table(
        "stock_coverage",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("covered_from", sa.Date(), nullable=False),
        sa.Column("covered_through", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("stock_id"),
    )

    op.create_table(
        "stock_collection_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False),
        sa.Column("chunks_total", sa.Integer(), nullable=False),
        sa.Column("chunks_done", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_job_status", "stock_collection_job",
                    ["stock_id", "status"])

    op.create_table(
        "stock_collection_lock",
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["stock_collection_job.id"]),
        sa.PrimaryKeyConstraint("stock_id"),
    )

    op.create_table(
        "stock_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("trade_fee_rate", SPREAD, nullable=False),
        sa.Column("dividend_tax_rate", SPREAD, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # 외래 키 역순으로 지운다.
    op.drop_table("stock_setting")
    op.drop_table("stock_collection_lock")
    op.drop_index("ix_stock_job_status", table_name="stock_collection_job")
    op.drop_table("stock_collection_job")
    op.drop_table("stock_coverage")
    op.drop_index("ix_stock_raw_received", table_name="stock_raw_response")
    op.drop_table("stock_raw_response")
    op.drop_table("stock_split")
    op.drop_table("stock_dividend")
    op.drop_table("stock_price")
    op.drop_index("ux_stock_market_symbol", table_name="stock")
    op.drop_table("stock")
