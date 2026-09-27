"""기간 단위 기준일 판정과 구간 페이지 조회 (T004, T006, T007, T009).

004 data-model 3~6절. **구간 정의가 존재하는 유일한 곳이다.**

구간 경계를 SQL에 두지 않는다. `EXTRACT(WEEK FROM ...)`은 MySQL과 PostgreSQL이 서로
다른 주 정의를 쓰므로(전자는 일요일 시작, 후자는 ISO 월요일 시작), DB를 바꾸면 같은
질의가 다른 묶음을 돌려준다 — 오류 없이 **결과만 달라지는** 종류다. 헌법 DB 운영 규약이
막으려는 것이 정확히 이것이다.

대신 리포지토리는 고시일만 최신순으로 돌려주고, 묶는 일은 여기서 한다. 내림차순이므로
각 구간에서 **처음 만나는 날짜가 그 구간의 마지막 고시일**이다 — 금요일·말일을 먼저 찾고
실패하면 다시 찾는 2단계가 필요 없다 (research R4-2).
"""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Literal, get_args

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxRate
from src.repository.fx_rate import page_before, quote_dates_before, rows_on

PeriodUnit = Literal["daily", "weekly", "monthly"]

#: 질의 매개변수 검증용. 알 수 없는 값을 조용히 `daily`로 떨어뜨리지 않는다.
PERIOD_UNITS: tuple[str, ...] = get_args(PeriodUnit)

_FRIDAY = 4  # `dt.date.weekday()`는 월요일이 0이다
_DAYS_PER_WEEK = 7

#: 한 구간에 들어갈 수 있는 고시일의 상한. 훑을 날짜 수를 정하는 데 쓴다.
_MAX_DAYS_IN_PERIOD: dict[str, int] = {"daily": 1, "weekly": 7, "monthly": 31}


def period_bounds(day: dt.date, unit: PeriodUnit) -> tuple[dt.date, dt.date]:
    """`day`가 속한 구간의 시작과 끝 (data-model 3절).

    주는 월요일~일요일, 월은 1일~말일이다 (spec Assumptions). 일 단위는 하루이므로
    시작과 끝이 같다 — 필드를 비우지 않는 이유는 단위에 따라 응답 구조가 달라지면
    화면이 두 형태를 다뤄야 하기 때문이다.
    """
    if unit == "daily":
        return day, day
    if unit == "weekly":
        start = day - dt.timedelta(days=day.weekday())
        return start, start + dt.timedelta(days=_DAYS_PER_WEEK - 1)
    last_day = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last_day)


def shifted_from(quote_date: dt.date, unit: PeriodUnit) -> dt.date | None:
    """원래 기준일. 옮겨지지 않았으면 `None` (FR-013, FR-014).

    주 단위는 그 주의 금요일, 월 단위는 그 달의 말일이 원래 기준일이다. 실제 고시일이
    그것과 다르면 **날짜가 옮겨진 것**이며, 그 사실이 드러나지 않으면 사용자는 값을
    금요일·말일의 값으로 오해한다.

    **주말 고시가 없다는 전제에 기댄다.** 토·일에 고시가 있으면 그것이 그 주의 마지막이
    되어 옮겨진 것으로 잘못 판정한다. 한국 외환시장은 주말 고시를 하지 않는다
    (research R4-2, spec Assumptions).
    """
    if unit == "daily":
        return None
    start, end = period_bounds(quote_date, unit)
    anchor = start + dt.timedelta(days=_FRIDAY) if unit == "weekly" else end
    return None if quote_date == anchor else anchor


def is_ongoing(period_to: dt.date, today: dt.date, unit: PeriodUnit) -> bool:
    """구간이 아직 끝나지 않았는가 (FR-015a, data-model 5절).

    구간의 끝이 오늘이거나 그 뒤면 진행 중이다 — 오늘이 아직 끝나지 않았기 때문이다.
    드러나지 않으면 사용자는 그 값을 구간의 마지막 값으로 읽는다.

    **일 단위는 항상 거짓이다.** 하루는 그 날짜로 끝난다. 오늘 행에 진행 중 표시가
    붙으면 잠정값 표시와 뜻이 겹쳐 둘 다 의미를 잃는다.
    """
    if unit == "daily":
        return False
    return period_to >= today


async def period_page(
    session: AsyncSession,
    currency_code: str,
    *,
    unit: PeriodUnit,
    before: dt.date | None,
    limit: int,
) -> list[FxRate]:
    """구간별 마지막 고시일의 행을 최신순으로 `limit`건 (FR-008, FR-012).

    커서는 주·월 단위에서 **기준일** 미만을 뜻한다 (research R4-3). 오프셋을 쓰지 않는
    이유는 003이 백그라운드로 수집해 조회 중에 행이 늘 수 있기 때문이다 — 오프셋이면
    같은 행을 두 번 주거나 건너뛰어 FR-005가 조용히 깨진다.

    고시가 하나도 없는 구간은 훑을 날짜 자체가 없으므로 **행이 만들어지지 않는다**
    (FR-015). 값을 지어내는 경로가 애초에 존재하지 않는다 (헌법 원칙 V).
    """
    if unit == "daily":
        return await page_before(session, currency_code, before=before, limit=limit)

    # 커서가 가리키는 **구간 전체**를 건너뛴다. 기준일 하나만 제외하면 같은 구간의
    # 이전 고시일이 새 기준일로 뽑혀 같은 주·달이 두 번 나온다 — 날짜가 달라 눈에
    # 띄지도 않는다. FR-005(중복 방지)가 조용히 깨지는 경로다.
    cursor = None if before is None else period_bounds(before, unit)[0]

    # 한 구간의 고시일은 최대 `_MAX_DAYS_IN_PERIOD`일이므로, 그 배수만큼 훑으면
    # `limit`개 구간이 반드시 들어온다. 고시가 드문 구간일수록 더 많이 들어온다.
    scan = limit * _MAX_DAYS_IN_PERIOD[unit]
    days = await quote_dates_before(
        session, currency_code, before=cursor, limit=scan)

    anchors: list[dt.date] = []
    seen: set[dt.date] = set()
    for day in days:  # 내림차순이므로 구간마다 처음 만나는 날이 마지막 고시일이다
        start, _ = period_bounds(day, unit)
        if start in seen:
            continue
        seen.add(start)
        anchors.append(day)
        if len(anchors) == limit:
            break

    rows = await rows_on(session, currency_code, anchors)
    return sorted(rows, key=lambda r: r.quote_date, reverse=True)
