"""가상자산 거래 수수료율 설정 (T030) — 007 FR-032, FR-033, data-model 9절.

**전역 단일 행이고 주식 설정과 따로다**(FR-032) — 가상자산 거래소 수수료는 증권사 수수료와 자릿수가
다르다. 한 행에 합치면 한쪽을 바꿀 때 다른 쪽이 따라 바뀌는 실수가 오류 없이 지나간다.

**기본값을 코드에 둔다.** 행이 없을 때 0으로 떨어지면 수수료 없는 결과가 나오는데 값은
그럴듯하다(005와 같다).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import CryptoSetting

#: 기본 거래 수수료 0.1% (FR-032, 사용자 결정).
DEFAULT_TRADE_FEE: Final = Decimal("0.001000")
_ROW_ID = 1


@dataclass(frozen=True, slots=True)
class CryptoSettings:
    trade_fee_rate: Decimal
    is_default: bool


async def get_settings(session: AsyncSession) -> CryptoSettings:
    """현재 설정. 행이 없으면 기본값이다. `is_default`는 현재 값이 기본값과 같은지다(002 FR-033과
    같은 규약)."""
    row = await session.get(CryptoSetting, _ROW_ID, populate_existing=True)
    if row is None:
        return CryptoSettings(DEFAULT_TRADE_FEE, is_default=True)
    return CryptoSettings(row.trade_fee_rate, is_default=row.trade_fee_rate == DEFAULT_TRADE_FEE)


async def save_settings(session: AsyncSession, *, trade_fee_rate: Decimal) -> None:
    """저장한다. 결과를 저장하지 않으므로(005 R5-9) 다음 조회가 새 값을 쓴다 — 무효화할 캐시가
    없다."""
    await upsert(session, CryptoSetting, [{"id": _ROW_ID, "trade_fee_rate": trade_fee_rate}],
                 preserve=())
