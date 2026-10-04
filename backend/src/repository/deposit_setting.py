"""예금 이자 소득세율 설정 (T018) — 008 FR-030, FR-031, data-model 6절.

**전역 단일 행이고 주식·가상자산 설정과 따로다**(FR-030) — 배당 소득세율과 같은 15.4%로 시작하지만
한쪽을 바꿀 때 다른 쪽이 따라 바뀌면 안 된다.

**기본값을 코드에 둔다.** 행이 없을 때 0으로 떨어지면 세금 없는 결과가 나오는데 값은
그럴듯하다(005·007과 같다).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import DepositSetting

#: 기본 이자 소득세율 15.4% — 소득세 14% + 지방소득세 1.4%(FR-030, 사용자 결정).
DEFAULT_INTEREST_TAX: Final = Decimal("0.154000")
_ROW_ID = 1


@dataclass(frozen=True, slots=True)
class DepositSettings:
    interest_tax_rate: Decimal
    is_default: bool


async def get_settings(session: AsyncSession) -> DepositSettings:
    """현재 설정. 행이 없으면 기본값이다. `is_default`는 현재 값이 기본값과 같은지다."""
    row = await session.get(DepositSetting, _ROW_ID, populate_existing=True)
    if row is None:
        return DepositSettings(DEFAULT_INTEREST_TAX, is_default=True)
    return DepositSettings(row.interest_tax_rate,
                           is_default=row.interest_tax_rate == DEFAULT_INTEREST_TAX)


async def save_settings(session: AsyncSession, *, interest_tax_rate: Decimal) -> None:
    """저장한다. 결과를 저장하지 않으므로 다음 조회가 새 값을 쓴다 — 무효화할 캐시가 없다."""
    await upsert(session, DepositSetting,
                 [{"id": _ROW_ID, "interest_tax_rate": interest_tax_rate}], preserve=())
