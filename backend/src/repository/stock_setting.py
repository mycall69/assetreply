"""수수료·세율 설정 (T062) — 005 FR-015, FR-016, 006 FR-055(배당 소득세 국내·해외).

`fx_spread`는 통화별이지만 이쪽은 **전역 단일 행**이다. 시장별로 수수료가 다른 것이
현실이지만 명세가 하나로 받는다.

**기본값을 코드에 둔다.** DB에 행이 없을 때 조용히 0으로 떨어지면 수수료·세금이 없는
결과가 나오는데, 값은 그럴듯하고 오류도 나지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import StockSetting

#: 기본 매매 수수료 0.015% (FR-015).
DEFAULT_TRADE_FEE = Decimal("0.000150")
#: 기본 배당 소득세 — 국내 15.4% (005 FR-016), 해외 15% (006 FR-055).
DEFAULT_DIVIDEND_TAX = Decimal("0.154000")
DEFAULT_DIVIDEND_TAX_FOREIGN = Decimal("0.150000")

#: 국내 세율을 쓰는 시장 (006 FR-055). 그 밖(NYSE·NASDAQ·AMEX·TSE)은 해외 세율이다.
DOMESTIC_MARKETS = frozenset({"KRX"})

#: 전역 단일 행의 키.
_ROW_ID = 1


@dataclass(frozen=True, slots=True)
class Settings:
    trade_fee_rate: Decimal
    dividend_tax_rate_domestic: Decimal
    dividend_tax_rate_foreign: Decimal
    is_default: bool

    def dividend_tax_rate_for(self, market: str) -> Decimal:
        """그 시장의 종목에 쓸 배당 소득세 (006 FR-055). 국내 세율을 해외 종목에 쓰면 세후 배당이
        조용히 줄어든다."""
        if market in DOMESTIC_MARKETS:
            return self.dividend_tax_rate_domestic
        return self.dividend_tax_rate_foreign


async def get_settings(session: AsyncSession) -> Settings:
    """현재 설정. 행이 없으면 기본값을 돌려준다.

    `is_default`는 현재 값이 기본값과 같은지다 — 002 FR-033과 같은 규약이다.
    """
    row = (await session.execute(
        select(StockSetting).where(StockSetting.id == _ROW_ID)
    )).scalar_one_or_none()
    if row is None:
        return Settings(DEFAULT_TRADE_FEE, DEFAULT_DIVIDEND_TAX, DEFAULT_DIVIDEND_TAX_FOREIGN,
                        is_default=True)
    return Settings(
        trade_fee_rate=row.trade_fee_rate,
        dividend_tax_rate_domestic=row.dividend_tax_rate,
        dividend_tax_rate_foreign=row.dividend_tax_rate_foreign,
        is_default=(row.trade_fee_rate == DEFAULT_TRADE_FEE
                    and row.dividend_tax_rate == DEFAULT_DIVIDEND_TAX
                    and row.dividend_tax_rate_foreign == DEFAULT_DIVIDEND_TAX_FOREIGN),
    )


async def save_settings(
    session: AsyncSession,
    *,
    trade_fee_rate: Decimal,
    dividend_tax_rate_domestic: Decimal,
    dividend_tax_rate_foreign: Decimal,
) -> None:
    """설정을 저장한다.

    **무효화할 캐시가 없다.** 시뮬레이션 결과를 저장하지 않으므로(research R5-9)
    다음 조회가 자동으로 새 값을 쓴다 — FR-017이 요구하는 재산출이 그렇게 성립한다.
    """
    await upsert(session, StockSetting, [{
        "id": _ROW_ID,
        "trade_fee_rate": trade_fee_rate,
        "dividend_tax_rate": dividend_tax_rate_domestic,
        "dividend_tax_rate_foreign": dividend_tax_rate_foreign,
    }], preserve=())
