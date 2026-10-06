"""수수료·세율 설정 (T062) — 005 FR-015, FR-016, 006 FR-055(배당 소득세 국내·해외), 011 FR-035(매도
세금).

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

#: 011 FR-035 — 매도 세금의 기본값. **010 반복 4의 법령 표 값과 자릿수까지 같다** — 기본 설정의 보드
#: 응답(`taxRate "0.0020"`·`"0.22"`, `deduction "2500000"`)이 011 전과 문자열까지 같아야
#: 한다(FR-039, research R11-7). 국내는 2026년 증권거래세 실질 세율(코스피 거래세 + 농어촌특별세,
#: 코스닥과 같다), 해외는 양도소득세 22%(지방소득세 포함)와 연간 기본공제 250만 원이다.
DEFAULT_SALE_TAX_DOMESTIC = Decimal("0.0020")
DEFAULT_CAPITAL_GAINS_RATE = Decimal("0.22")
DEFAULT_CAPITAL_GAINS_DEDUCTION = Decimal("2500000")

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


@dataclass(frozen=True, slots=True)
class SaleTaxSettings:
    """매도 세금 설정(011 FR-035). 보드가 기준일에 모두 판다고 가정할 때만 쓴다 — 표·차트의 보유 중
    값에는 들어가지 않는다(FR-038)."""

    #: 국내 매도 세율(비율 — 0.0020 = 0.20%).
    domestic: Decimal
    #: 해외 양도소득세율(지방소득세 포함, 비율).
    foreign_rate: Decimal
    #: 해외 연간 기본공제(원). **원화로** 뺀다(FR-013) — 종목 통화로 빼면 공제가 환율 배수만큼
    #: 커진다.
    foreign_deduction: Decimal
    is_default: bool


async def get_sale_tax(session: AsyncSession) -> SaleTaxSettings:
    """매도 세금 설정. 행이 없거나 열이 NULL이면 기본값이다 — 0으로 떨어지면 세금이 없는 결과가
    그럴듯하게 나온다."""
    row = (await session.execute(
        select(StockSetting).where(StockSetting.id == _ROW_ID)
    )).scalar_one_or_none()
    domestic = DEFAULT_SALE_TAX_DOMESTIC
    rate = DEFAULT_CAPITAL_GAINS_RATE
    deduction = DEFAULT_CAPITAL_GAINS_DEDUCTION
    if row is not None:
        if row.sale_tax_rate_domestic is not None:
            domestic = row.sale_tax_rate_domestic
        if row.capital_gains_rate_foreign is not None:
            rate = row.capital_gains_rate_foreign
        if row.capital_gains_deduction_foreign is not None:
            deduction = row.capital_gains_deduction_foreign
    return SaleTaxSettings(
        domestic=domestic, foreign_rate=rate, foreign_deduction=deduction,
        is_default=(domestic == DEFAULT_SALE_TAX_DOMESTIC and rate == DEFAULT_CAPITAL_GAINS_RATE
                    and deduction == DEFAULT_CAPITAL_GAINS_DEDUCTION))


async def save_sale_tax(session: AsyncSession, *, domestic: Decimal, foreign_rate: Decimal,
                        foreign_deduction: Decimal) -> None:
    """매도 세금을 저장한다. 수수료·배당 세율은 **지금 값 그대로** 둔다.

    행이 없으면 수수료·배당 세율 열(NOT NULL)에 지금 설정(기본값)을 함께 넣는다. 반대로
    `save_settings`는 매도 세금 열을 건드리지 않는다(그 열을 행에 싣지 않으므로 충돌 갱신에서
    빠진다) — 두 설정 화면이 서로의 값을 덮지 않는다.
    """
    current = await get_settings(session)
    await upsert(session, StockSetting, [{
        "id": _ROW_ID,
        "trade_fee_rate": current.trade_fee_rate,
        "dividend_tax_rate": current.dividend_tax_rate_domestic,
        "dividend_tax_rate_foreign": current.dividend_tax_rate_foreign,
        "sale_tax_rate_domestic": domestic,
        "capital_gains_rate_foreign": foreign_rate,
        "capital_gains_deduction_foreign": foreign_deduction,
    }], preserve=())
