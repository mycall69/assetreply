"""정기 적금 조회·조합 (011 T048) — FR-022~FR-032, research R11-2·R11-8·R11-9.

**계산을 직접 하지 않는다.** 사다리 계산은 `simulation/installment_ladder`의 순수 함수다(헌법
원칙 IV). 여기서는 입력을 검증하고, 두 금리 계열의 수집을 판정하고, 받아 둔 금리로 계산을 부른다.
**결과를 저장하지 않는다**(005 R5-9).

- (투자처, 상품) → **금리 계열 키**의 대응은 여기에만 있다. 계열 키는 응답에 나오지 않는다 — 화면은
  (투자처, 상품)으로 말한다(research R11-2)
- 적금은 출처에 적금 항목이 있는 투자처만이다 — 시중은행·상호금융. 나머지 셋은 사유와 함께 막는다.
  정기예금 금리로 대신하지 않는다(FR-029)
- 수집 판정은 두 계열을 008의 `judge`로 **함께** 본다(R11-9)
  - 적금 계열은 시작 달 ~ 계산 끝 달, 정기예금 계열은 첫 만기 달 ~ 계산 끝 달이다
  - 계산 끝이 첫 만기 전이면 정기예금은 필요 없다
  - 받을 것이 있으면 둘 다 걸고 적금 쪽을 먼저 202로 돌려준다
- 시작 가능 날짜는 max(적금 첫 달, 정기예금 첫 달 − 1년)이다. 각 계열의 `judge`가 내는 첫 달을 이
  날짜로 바꿔 낸다 — 정기예금의 첫 달을 그대로 내면 사용자가 1년 늦은 날짜로 옮긴다
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InstallmentNotAvailable, InvalidQuery, NoRateData
from src.api.services import deposit_simulation as deposit
from src.api.services.deposit_collect import judge
from src.repository import deposit_rate, deposit_setting
from src.repository.deposit_setting import DepositSettings
from src.simulation.deposit_rollover import BeforeFirstMonth, add_one_year
from src.simulation.installment_ladder import (
    LadderOutcome,
    simulate_installment_ladder,
    startable_from,
)

Json = dict[str, object]

_WON: Final = re.compile(r"^[0-9]+$")

UNAVAILABLE_REASON: Final = "출처(ECOS)에 이 투자처의 정기적금 금리 통계가 없습니다."


@dataclass(frozen=True, slots=True)
class InstallmentOption:
    """투자처 하나의 적금 — 금리 계열 키와 상품 범위 설명(화면이 밝힌다, research R11-1)."""

    series: str
    description: str


#: 적금이 있는 투자처. 순서는 투자처 목록(FR-003)과 같다.
INSTALLMENT_OPTIONS: Final[dict[str, InstallmentOption]] = {
    "commercial_bank": InstallmentOption("commercial_bank_isav",
                                         "예금은행 정기적금(1~2년 만기) 평균"),
    "mutual_finance": InstallmentOption("mutual_finance_isav",
                                        "상호금융 정기적금 평균 — 만기 구분 없음"),
}


@dataclass(frozen=True, slots=True)
class InstallmentRequest:
    institution: deposit.Institution
    option: InstallmentOption
    start: dt.date
    end: dt.date
    monthly: Decimal


@dataclass(frozen=True, slots=True)
class PreparedInstallment:
    outcome: LadderOutcome
    settings: DepositSettings
    #: 계산에 넘긴 두 계열의 월별 금리와 마지막 발표 달 — 차트의 그 달 금리가 **같은 값**을 본다
    #: (008 `Prepared`와 같은 이유).
    installment_rates: Mapping[dt.date, Decimal]
    installment_latest: dt.date
    deposit_rates: Mapping[dt.date, Decimal]
    deposit_latest: dt.date | None
    recheck_failed: tuple[str, str] | None = None


def require_installment(key: str) -> tuple[deposit.Institution, InstallmentOption]:
    """투자처를 찾고 적금이 있는지 본다. 모르는 키는 400 `unknown_institution`, 적금이 없으면 400
    `installment_not_available`이다 — 어느 경로(이력 재실행·직접 요청)로 들어와도 막는다(FR-023)."""
    institution = deposit.require_institution(key)
    option = INSTALLMENT_OPTIONS.get(key)
    if option is None:
        raise InstallmentNotAvailable(f"{institution.name} — {UNAVAILABLE_REASON}",
                                      list(INSTALLMENT_OPTIONS))
    return institution, option


def parse_monthly(raw: str) -> Decimal:
    """월 납입액 — 원 단위 양의 정수 문자열(쉼표 없음). 조용히 0이나 반올림으로 떨어뜨리지
    않는다."""
    if not _WON.match(raw) or int(raw) <= 0:
        raise InvalidQuery("월 납입액은 원 단위 양의 정수여야 합니다.")
    return Decimal(raw)


def read_request(institution: str, start: str, amount: str,
                 end: str | None) -> InstallmentRequest:
    """입력 검증 — 표와 차트가 같은 순서로 막는다(008 `read_request`와 같은 순서)."""
    monthly = parse_monthly(amount)
    first_day = deposit.parse_day(start, "시작일")
    found, option = require_installment(institution)
    finish = deposit.calculation_end(
        first_day, None if end is None else deposit.parse_day(end, "끝 날짜"))
    return InstallmentRequest(found, option, first_day, finish, monthly)


def _collecting(body: Json, institution: str, series: str) -> Json:
    """008의 202 본문에서 계열 키를 투자처 키로 바꾸고 계열을 더한다 — 계열 키를 화면에 내지
    않는다."""
    return {**body, "institution": institution, "series": series}


async def simulate_or_collect(
    session: AsyncSession, request: InstallmentRequest,
) -> PreparedInstallment | Json:
    """받지 않은 달이 있으면 202 본문, 아니면 계산 결과. **표와 차트가 이 함수 하나를 거친다.**"""
    key, series = request.institution.key, request.option.series
    today = deposit.kst_today()
    saving_coverage = await deposit_rate.get_coverage(session, series)
    deposit_coverage = await deposit_rate.get_coverage(session, key)
    deposit_first = None if deposit_coverage is None else deposit_coverage.first_month
    first_maturity = add_one_year(request.start)
    need_deposit = first_maturity <= request.end

    # 수집 전 판정 — 받아 둔 범위로 알 수 있으면 받기보다 먼저다(008 FR-006과 같다).
    if saving_coverage is not None:
        startable = startable_from(saving_coverage.first_month, deposit_first)
        if request.start < startable:
            raise BeforeFirstMonth(startable)

    try:
        saving = await judge(session, series, request.start, request.end, today)
    except BeforeFirstMonth as exc:
        raise BeforeFirstMonth(startable_from(exc.first_month, deposit_first)) from exc
    held = None
    if need_deposit:
        try:
            held = await judge(session, key, first_maturity, request.end, today)
        except BeforeFirstMonth as exc:
            saving_first = (exc.first_month if saving_coverage is None
                            else saving_coverage.first_month)
            raise BeforeFirstMonth(startable_from(saving_first, exc.first_month)) from exc

    # 둘 다 걸어 둔 뒤 적금 쪽을 먼저 알린다 — 끝나면 화면이 다시 요청하고, 정기예금 쪽이 남았으면
    # 또 202다.
    if saving.collecting is not None:
        return _collecting(saving.collecting, key, "installment")
    if held is not None and held.collecting is not None:
        return _collecting(held.collecting, key, "deposit")
    recheck = saving.recheck_failed or (None if held is None else held.recheck_failed)
    prepared = await prepare(session, request, need_deposit=need_deposit)
    return PreparedInstallment(
        prepared.outcome, prepared.settings, prepared.installment_rates,
        prepared.installment_latest, prepared.deposit_rates, prepared.deposit_latest, recheck)


async def prepare(session: AsyncSession, request: InstallmentRequest, *,
                  need_deposit: bool) -> PreparedInstallment:
    """받아 둔 두 계열의 금리로 계산한다. 결측·첫 달 전은 계산 함수가 막는다."""
    series, key = request.option.series, request.institution.key
    saving_rates = await deposit_rate.get_rates(session, series)
    saving_coverage = await deposit_rate.get_coverage(session, series)
    if not saving_rates or saving_coverage is None:
        raise NoRateData("이 투자처의 적금 금리를 출처에서 받지 못했습니다.")
    deposit_rates = await deposit_rate.get_rates(session, key)
    deposit_coverage = await deposit_rate.get_coverage(session, key)
    if need_deposit and (not deposit_rates or deposit_coverage is None):
        raise NoRateData("이 투자처의 정기예금 금리를 출처에서 받지 못했습니다.")
    settings = await deposit_setting.get_settings(session)
    outcome = simulate_installment_ladder(
        monthly=request.monthly, start=request.start, end=request.end,
        installment_rates=saving_rates, installment_first=saving_coverage.first_month,
        installment_latest=saving_coverage.latest_month, deposit_rates=deposit_rates,
        deposit_first=None if deposit_coverage is None else deposit_coverage.first_month,
        deposit_latest=None if deposit_coverage is None else deposit_coverage.latest_month,
        tax_rate=settings.interest_tax_rate)
    return PreparedInstallment(
        outcome, settings, saving_rates, saving_coverage.latest_month, deposit_rates,
        None if deposit_coverage is None else deposit_coverage.latest_month)
