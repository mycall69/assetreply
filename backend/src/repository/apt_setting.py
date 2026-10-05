"""부동산 설정 — 보유세 기준 비율 (009 T038, FR-034, data-model 9절).

**전역 단일 행이고 다른 자산군 설정과 따로다.** 행이 없으면 기본값 0.600000이다 — 보유세 기준 금액 =
그해 6월 적용 시세 × 비율(실거래 평균의 60%를 공시가격 대용으로 쓴다는 사용자 가정). **기본값을
코드에 둔다** — 행이 없을 때 0으로 떨어지면 보유세 없는 결과가 그럴듯한 값으로 나온다(005~008과
같다).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import AptSetting

DEFAULT_HOLDING_TAX_BASE_RATIO: Final = Decimal("0.600000")
_ROW_ID = 1


@dataclass(frozen=True, slots=True)
class AptSettings:
    holding_tax_base_ratio: Decimal
    is_default: bool


async def get_settings(session: AsyncSession) -> AptSettings:
    """현재 설정. 행이 없으면 기본값이다. `is_default`는 현재 값이 기본값과 같은지다."""
    row = await session.get(AptSetting, _ROW_ID, populate_existing=True)
    if row is None:
        return AptSettings(DEFAULT_HOLDING_TAX_BASE_RATIO, is_default=True)
    return AptSettings(row.holding_tax_base_ratio,
                       is_default=row.holding_tax_base_ratio == DEFAULT_HOLDING_TAX_BASE_RATIO)


async def save_settings(session: AsyncSession, *, holding_tax_base_ratio: Decimal) -> None:
    """저장한다. 결과를 저장하지 않으므로 다음 조회가 새 값을 쓴다 — 무효화할 캐시가 없다."""
    await upsert(session, AptSetting,
                 [{"id": _ROW_ID, "holding_tax_base_ratio": holding_tax_base_ratio}], preserve=())
