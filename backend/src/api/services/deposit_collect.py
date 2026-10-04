"""예금 금리 수집 필요 판정 (T020) — 008 FR-010, FR-011, FR-016, contracts/rest-api 202.

**표와 차트가 같은 판정을 쓴다**(005~007과 같은 이유). 한쪽만 수집을 시작하면 같은 구간을 두 번
받거나, 한쪽은 받은 만큼만 계산한 **틀린 값**을 보인다.

필요한 구간은 시작 달 ~ 계산 끝의 달(기본 이번 달, 한국 시간)이다. 커버리지 `[first_month,
latest_month]` 안의 빈 달은 결측이라 다시 받으러 가지 않는다 — 받을 것은 마지막 발표 달 뒤의
달뿐이다. 그 달은 **미발표일 수 있다**:

- 오늘(한국 시간) 아직 확인하지 않았으면 202 — 확인하러 간다
- 오늘 확인했는데 없으면 미발표다 — 200, 그 달부터 잠정(research R8-3)
- 오늘 확인이 실패했고 받아 둔 금리로 답할 수 있으면 200 + `recheckFailed` — 같은 날 202를
  되풀이하지 않는다.
  확인한 날은 성공했을 때만 갱신하므로 다음 날 다시 확인한다(FR-016)
- 받은 적이 없으면 늘 202다 — 답할 금리가 없다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository import deposit_job, deposit_rate
from src.simulation.deposit_rollover import BeforeFirstMonth
from src.worker.deposit_queue import DepositWork, get_deposit_queue
from src.worker.deposit_runner import months_between, shift_months

Json = dict[str, object]

_KST_OFFSET = dt.timedelta(hours=9)


@dataclass(frozen=True, slots=True)
class Judgment:
    #: 202 본문. 계산할 수 있으면 `None`이다.
    collecting: Json | None
    #: 오늘 확인이 실패했을 때 그 종류와 사유(FR-016).
    recheck_failed: tuple[str, str] | None = None


def kst_midnight_utc(today: dt.date) -> dt.datetime:
    """한국 시간 그날 0시를 UTC(시간대 없는 값)로 — 작업의 마감 시각과 비교한다."""
    return dt.datetime.combine(today, dt.time()) - _KST_OFFSET


def month_text(month: dt.date) -> str:
    return f"{month:%Y-%m}"


async def judge(session: AsyncSession, institution: str, start: dt.date, end: dt.date,
                today: dt.date) -> Judgment:
    """받아야 할 달이 있으면 작업을 확보하고 수집 줄에 넘긴다. 계산할 수 있으면 `collecting`이
    `None`.

    시작일이 그 투자처의 첫 달보다 이르면 `BeforeFirstMonth`를 낸다 — 받아 둔 범위로 알 수 있으면
    수집보다 먼저다(FR-006).
    """
    need_from, need_to = start.replace(day=1), end.replace(day=1)
    coverage = await deposit_rate.get_coverage(session, institution)
    missing_from = need_from
    if coverage is not None:
        if start < coverage.first_month:
            raise BeforeFirstMonth(coverage.first_month)
        if need_to <= coverage.latest_month or coverage.checked_on >= today:
            return Judgment(None)
        failed = await deposit_job.last_failure_since(
            session, institution, kst_midnight_utc(today))
        if failed is not None:
            kind, reason = deposit_job.split_error(failed.last_error)
            return Judgment(None, (kind or "network", reason or "금리를 확인하지 못했습니다."))
        missing_from = max(need_from, shift_months(coverage.latest_month, 1))

    job_id, created = await deposit_job.acquire_or_get_running(
        session, institution, need_from, need_to, months_total=months_between(need_from, need_to))
    if created:
        # 커밋해야 수집 줄이 다른 세션에서 그 작업을 볼 수 있다.
        await session.commit()
        get_deposit_queue().request(DepositWork(
            job_id=job_id, institution=institution, start_month=need_from, end_month=need_to))
    return Judgment({
        "status": "collecting", "institution": institution, "jobId": job_id,
        "missingFrom": month_text(missing_from), "missingThrough": month_text(need_to),
        "progressUrl": f"/api/deposit/progress?jobId={job_id}",
    })
