"""예금 시뮬레이션 준비 (T020) — 008 FR-002~FR-007, FR-018, FR-026, FR-035, contracts/rest-api.

입력을 검증하고 받아 둔 금리·커버리지·세율로 계산한다. **계산 끝은 오늘(한국 시간)이다**(FR-026) —
예금은 매일 이자가 붙는다(경과분). 투자처의 이름·설명은 여기에만 있다 — 출처의 통계표·항목 코드는
응답에 나오지 않는다 (헌법 원칙 II).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import (
    CurrencyNotAllowed,
    InvalidQuery,
    NoRateData,
    StartAfterEnd,
    UnknownInstitution,
)
from src.repository import deposit_rate, deposit_setting
from src.repository.deposit_setting import DepositSettings
from src.simulation.deposit_rollover import DepositOutcome, simulate_deposit

_KST: Final = dt.timezone(dt.timedelta(hours=9))
_WON: Final = re.compile(r"^[0-9]+$")


@dataclass(frozen=True, slots=True)
class Institution:
    key: str
    name: str
    description: str


#: 화면 순서다(FR-003). 기본 선택은 첫째. 설명은 통계의 범위를 밝힌다 — "시중은행"은 예금은행 전체
#: 평균이다 (research R8-1).
INSTITUTIONS: Final = (
    Institution("commercial_bank", "시중은행", "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함"),
    Institution("savings_bank", "저축은행", "상호저축은행 정기예금(1년) 평균"),
    Institution("credit_union", "신협", "신협 정기예탁금(1년) 평균"),
    Institution("mutual_finance", "상호금융", "상호금융 정기예탁금(1년만기) 평균"),
    Institution("saemaul", "새마을금고", "새마을금고 정기예탁금(1년) 평균"),
)
_BY_KEY: Final = {i.key: i for i in INSTITUTIONS}

SOURCE_NAME: Final = "한국은행 경제통계시스템(ECOS)"
SOURCE_BASIS: Final = "신규취급액 기준 가중평균"


def kst_today() -> dt.date:
    """오늘(한국 시간). 하루의 경계가 한국 시간이다(FR-018)."""
    return dt.datetime.now(_KST).date()


def require_institution(key: str) -> Institution:
    found = _BY_KEY.get(key)
    if found is None:
        raise UnknownInstitution("알 수 없는 투자처입니다.", [i.key for i in INSTITUTIONS])
    return found


def check_currency(code: str | None) -> None:
    """원금은 원화만이다(FR-004). 주어지지 않으면 원화다."""
    if code is not None and code != "KRW":
        raise CurrencyNotAllowed("예금 원금은 원화(KRW)만 가능합니다.", ["KRW"])


def parse_won(raw: str) -> Decimal:
    """원금 — 원 단위 양의 정수 문자열(쉼표 없음). 조용히 0이나 반올림으로 떨어뜨리지 않는다."""
    if not _WON.match(raw) or int(raw) <= 0:
        raise InvalidQuery("원금은 원 단위 양의 정수여야 합니다.")
    return Decimal(raw)


def parse_day(raw: str, name: str) -> dt.date:
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidQuery(f"{name}은 YYYY-MM-DD여야 합니다.") from exc


def calculation_end(start: dt.date, end: dt.date | None) -> dt.date:
    """계산 끝 — 요청한 끝과 오늘(한국 시간) 중 이른 날. 시작일이 그보다 늦으면 막는다(FR-005)."""
    today = kst_today()
    finish = today if end is None else min(end, today)
    if start > finish:
        raise StartAfterEnd(finish, f"{finish.isoformat()}(오늘)까지만 계산할 수 있습니다. "
                                    "시작일을 그 이전으로 고르세요.")
    return finish


@dataclass(frozen=True, slots=True)
class Prepared:
    outcome: DepositOutcome
    settings: DepositSettings


async def prepare(session: AsyncSession, institution: str, *, start: dt.date, end: dt.date,
                  principal: Decimal) -> Prepared:
    """받아 둔 금리로 계산한다. 결측·첫 달 전은 계산 함수가
    막는다(`RateMissing`·`BeforeFirstMonth`)."""
    rates = await deposit_rate.get_rates(session, institution)
    coverage = await deposit_rate.get_coverage(session, institution)
    if not rates or coverage is None:
        raise NoRateData("이 투자처의 금리를 출처에서 받지 못했습니다.")
    settings = await deposit_setting.get_settings(session)
    outcome = simulate_deposit(
        principal=principal, start=start, end=end, rates=rates,
        first_month=coverage.first_month, latest_month=coverage.latest_month,
        tax_rate=settings.interest_tax_rate)
    return Prepared(outcome, settings)
