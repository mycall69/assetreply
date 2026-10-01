"""시뮬레이션 조회·조합 (T036) — 005 FR-005, FR-013, FR-014a, FR-029.

**계산을 직접 하지 않는다.** 재투자 시뮬레이션은 `simulation/reinvest.py`의 순수
함수를 호출만 한다 (헌법 원칙 IV). 여기서 직접 계산하면 참조 구현과의 대조가 통합
테스트가 되고, 정밀도 차이가 다른 실패에 묻힌다.

**결과를 저장하지 않는다.** 결과는 시세·배당·분할·설정·환율의 함수이고 그중 설정과
환율이 바뀐다. 저장하면 갱신 시점을 관리해야 하고, 그 관리가 틀리면 **조용히 낡은
값을 보여준다** (research R5-9).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository import stock_price as price_repo
from src.simulation.reinvest import (
    Condition,
    DayBar,
    DividendOn,
    Row,
    SplitOn,
    simulate,
)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """시뮬레이션 전체 결과. 페이지는 호출부가 자른다.

    `as_of`는 계산이 **어느 날짜까지**인지다. 시세가 끊기면 오늘이 아니다 (FR-014a).
    `is_final`은 항상 명시한다 — "확인했고 아니다"와 "확인하지 않았다"가 구별되어야
    한다.
    """

    rows: list[Row]
    as_of: dt.date | None
    is_final: bool


class BeforeListing(Exception):
    """투자 시작 날짜가 종목의 상장 이전이다 (FR-005).

    **조용히 첫 거래일로 옮기지 않는다.** 옮기면 사용자는 자신이 고른 날짜부터
    계산됐다고 믿는다.
    """


class NoPriceData(Exception):
    """시세를 얻을 수 없다 (FR-004).

    **빈 표를 보여주지 않는다.** 사용자는 그 종목의 성과가 0이라고 읽는다.
    """


async def run_simulation(
    session: AsyncSession,
    stock_id: int,
    *,
    start: dt.date,
    end: dt.date,
    principal: Decimal,
    currency: str,
    reinvest: bool,
    fee_rate: Decimal,
    tax_rate: Decimal,
    listed_on: dt.date | None = None,
) -> SimulationResult:
    """시세를 읽어 순수 함수에 넘기고 결과를 돌려준다.

    시세가 중간에 끊기면(상장폐지·거래정지) **마지막 고시일까지만** 계산한다. 마지막
    시세를 오늘까지 이어 그리면 없는 값을 만들어내는 것이라 헌법 원칙 V 위반이다
    (FR-014a).
    """
    # **상장일과 "우리가 받아 둔 첫 시세"는 다르다.** 전자를 알면 그것을 쓰고,
    # 모르면 후자를 근거로 삼는다. 후자만 쓰면 월초가 휴일인 정상적인 시작일
    # (예: 8월 1일 일요일, 첫 거래일 8월 2일)까지 거절한다.
    earliest = listed_on or await price_repo.first_quote_date(session, stock_id)
    if earliest is None:
        raise NoPriceData("그 종목의 시세를 얻을 수 없습니다.")
    if start < earliest:
        raise BeforeListing(
            f"{earliest.isoformat()}부터 시세가 있습니다. 그 이전은 계산할 수 없습니다.")

    bars_rows = await price_repo.prices(session, stock_id, start, end)
    if not bars_rows:
        raise NoPriceData("요청한 구간에 시세가 없습니다.")

    dividend_rows = await price_repo.dividends(session, stock_id, start, end)
    split_rows = await price_repo.splits(session, stock_id, start, end)

    rows = simulate(
        [DayBar(r.quote_date, r.open_raw) for r in bars_rows],
        [DividendOn(d.ex_date, d.amount_per_share) for d in dividend_rows],
        [SplitOn(s.effective_date, s.numerator, s.denominator) for s in split_rows],
        Condition(
            start=start, principal=principal, currency=currency,
            reinvest=reinvest, fee_rate=fee_rate, tax_rate=tax_rate),
    )

    as_of = bars_rows[-1].quote_date
    # 요청 끝(보통 어제)까지 시세가 있으면 최종이다. 끊겼으면 그 사실이 드러나야 한다.
    is_final = as_of >= end
    return SimulationResult(rows=rows, as_of=as_of, is_final=is_final)


def page(rows: list[Row], before: dt.date | None, limit: int) -> tuple[list[Row], bool]:
    """커서 방식 페이지 (FR-029).

    004가 정한 것과 같다 — 오프셋을 쓰지 않는다. 수집이 조회 중에 행을 추가해도
    "이 날짜 미만"은 같은 집합이라 같은 행을 두 번 주거나 건너뛰지 않는다.

    `(페이지, 더 있는가)`를 돌려준다.
    """
    candidates = [r for r in rows if before is None or r.date < before]
    chunk = candidates[:limit]
    return chunk, len(candidates) > limit
