"""실거래 수집 상태와 202 (009 T025, FR-009~FR-012, FR-014, contracts/rest-api).

**받아 둔 시·군·구**(첫 달부터 잠정 기간 앞 달까지 모든 달을 받았다 — data-model 5절)가 결과를 내는
조건이다. 받은 만큼만 계산한 결과는 값이 멀쩡해 보이지만 틀렸다(005·008과 같은 이유). 평형과
시뮬레이션이 같은 판정을 쓴다.

- 진행 중인 작업이 있으면 그 작업(새 작업 없음, FR-012)
- 받아 둔 시·군·구면 `collected`
- 마지막 작업이 실패했고 그 뒤 다 받은 적 없으면 `failed` + 종류·사유(FR-014 — 다시 열어도 사유가
  보인다)
- 그 밖에는 수집을 시작한다(큐를 거쳐 — 요청이 수집의 실행 주체다). 받을 달은 처음부터 안다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.db.models import JobStatus
from src.repository import apt_job, apt_region, apt_trade
from src.worker.apt_queue import AptWork, get_apt_trade_queue
from src.worker.apt_trade_runner import (
    ProbeStartMissing,
    is_collected,
    kst_date,
    plan_months,
)

Json = dict[str, object]


def progress_url(job_id: int) -> str:
    return f"/api/realestate/progress?jobId={job_id}"


@dataclass(frozen=True, slots=True)
class TradeStatus:
    state: str  # none · collecting · collected · failed
    job_id: int | None = None
    done: int | None = None
    total: int | None = None
    failure: tuple[str, str] | None = None

    def as_json(self) -> Json:
        return {
            "state": self.state, "jobId": self.job_id, "monthsDone": self.done,
            "monthsTotal": self.total,
            "progressUrl": None if self.job_id is None else progress_url(self.job_id),
            "failure": None if self.failure is None else {
                "kind": self.failure[0], "reason": self.failure[1]},
        }

    def collecting_body(self, lawd_cd: str) -> Json:
        """202 본문(평형·시뮬레이션·시계열이 같다)."""
        assert self.job_id is not None
        return {"status": "collecting", "kind": "trade", "lawdCd": lawd_cd,
                "jobId": self.job_id, "monthsDone": self.done or 0,
                "monthsTotal": self.total or 0, "progressUrl": progress_url(self.job_id)}


async def _running(session: AsyncSession, job_id: int) -> TradeStatus:
    job = await apt_job.get_job(session, job_id)
    return TradeStatus("collecting", job_id, job.done if job else 0, job.total if job else 0)


async def start_trade_job(session: AsyncSession, lawd_cd: str, *, settings: Settings,
                          now: dt.datetime) -> TradeStatus:
    """수집 작업을 확보하고 실거래 줄에 넘긴다. 이미 진행 중이면 그 작업."""
    running = await apt_job.running_job_id(session, "trade", lawd_cd)
    if running is not None:
        return await _running(session, running)
    state = await apt_region.get_state(session, apt_region.sgg_scope(lawd_cd))
    coverage = await apt_trade.coverage(session, lawd_cd)
    try:
        total = len(plan_months(coverage, state.first_trade_ym if state else None,
                                today=kst_date(now), settings=settings))
    except ProbeStartMissing:
        total = 0  # 실행기가 사유를 남기고 멈춘다
    job_id, created = await apt_job.acquire_or_get_running(session, "trade", lawd_cd,
                                                           total=total)
    # 커밋해야 실거래 줄이 다른 세션에서 그 작업을 볼 수 있다.
    await session.commit()
    if created:
        get_apt_trade_queue().request(AptWork(job_id, "trade", lawd_cd))
    return await _running(session, job_id)


async def collected(session: AsyncSession, lawd_cd: str, *, settings: Settings,
                    now: dt.datetime) -> bool:
    state = await apt_region.get_state(session, apt_region.sgg_scope(lawd_cd))
    coverage = await apt_trade.coverage(session, lawd_cd)
    return is_collected(coverage, state.first_trade_ym if state else None,
                        today=kst_date(now), settings=settings)


async def trade_status(session: AsyncSession, lawd_cd: str, *, settings: Settings,
                       now: dt.datetime, start: bool) -> TradeStatus:
    """그 시·군·구 실거래의 상태. `start`면 받은 적 없을 때 수집을 시작한다."""
    running = await apt_job.running_job_id(session, "trade", lawd_cd)
    if running is not None:
        return await _running(session, running)
    if await collected(session, lawd_cd, settings=settings, now=now):
        return TradeStatus("collected")
    last = await apt_job.last_finished(session, "trade", lawd_cd)
    if last is not None and last.status is JobStatus.FAILED:
        kind, reason = apt_job.split_error(last.last_error)
        return TradeStatus("failed", failure=(kind or "network",
                                              reason or "실거래를 받지 못했습니다."))
    if not start:
        return TradeStatus("none")
    return await start_trade_job(session, lawd_cd, settings=settings, now=now)
