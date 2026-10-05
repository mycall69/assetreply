"""행정구역·단지·평형 응답 (009 T025, FR-002~FR-005, FR-011, FR-012, FR-015, FR-032,
contracts/rest-api).

- **행정구역**: 받은 적 없으면 202(목록 줄이 받는다). 30일(`APT_LIST_REFRESH_DAYS`)이 지났으면 받아
  둔 목록으로
  200을 주고 백그라운드로 다시 받는다 — 그 갱신이 실패해도 받아 둔 목록 그대로다. **현존 코드만**
  준다
- **단지**: 동을 고르면 단지 목록 자료(1회)를 **요청 경로에서** 받아 곧바로 이름을 준다(사용자 결정
  Q1). 기본
  정보는 백그라운드(새 단지만). 그 시·군·구 실거래를 받은 적 없으면 수집을 시작한다 — 동 선택이
  수집의 실행 주체다. 단지 목록을 받지 못하면 빈 목록 대신 사유(`listError`, FR-015)
- **평형**: 일곱 구분을 늘, 거래 수·첫 달은 해제·사라짐을 뺀 값. 시작 가능 날짜는 첫 거래 달 1일과
  세법 표의
  첫 날 중 늦은 날(FR-005). 받아 둔 시·군·구가 아니면 202 — 받은 만큼만 센 수는 틀렸다
- 단지 id는 `merged_into`를 따라간다 — 이력이 옛 id를 가지고 있을 수 있다(FR-032)
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import RegionRetired, UnknownComplex, UnknownRegion
from src.api.services.realestate_collect import progress_url, start_trade_job, trade_status
from src.config.settings import Settings, load_settings
from src.db.models import AptComplex, AptRegion
from src.ingestion.datagokr.errors import DataGoKrError
from src.observability.events import mask_secrets
from src.repository import apt_complex, apt_job, apt_region, apt_trade
from src.simulation.apt_area import AREA_BUCKETS, area_bucket
from src.simulation.apt_tax_rules import TAX_RULES_FROM
from src.worker import apt_worker
from src.worker.apt_list_runner import ComplexListSource, latest_for_umd, sync_umd
from src.worker.apt_queue import AptWork, get_apt_list_queue

Json = dict[str, object]
_CODE = re.compile(r"\d{10}")


# ── 의존성(테스트가 바꿔 끼운다) ──────────────────────────────────


def get_realestate_now() -> dt.datetime:
    """지금 시각(UTC). 갱신 주기·확인한 날(한국 시간)의 판정 근거다."""
    return apt_worker.utc_now()


def get_realestate_settings() -> Settings:
    return load_settings()


def get_realestate_source() -> ComplexListSource:
    """공공데이터포털 클라이언트 — 앱 수명에 하나(관문을 수집 태스크와 함께 쓴다)."""
    return apt_worker.shared_source()


# ── 공통 ──────────────────────────────────────────────────────────


def _utc_text(moment: dt.datetime | None) -> str | None:
    return None if moment is None else moment.replace(microsecond=0).isoformat() + "Z"


async def _start_list_job(session: AsyncSession, kind: str, target: str) -> int:
    job_id, created = await apt_job.acquire_or_get_running(session, kind, target, total=0)
    await session.commit()
    if created:
        get_apt_list_queue().request(AptWork(job_id, kind, target))
    return job_id


async def _region(session: AsyncSession, code: str, *levels: str) -> AptRegion:
    region = await apt_region.current(session, code) if _CODE.fullmatch(code) else None
    if region is None or region.level not in levels:
        raise UnknownRegion(f"모르는 행정구역입니다: {code}")
    return region


# ── 행정구역 ──────────────────────────────────────────────────────


async def regions_response(session: AsyncSession, parent: str | None, *, settings: Settings,
                           now: dt.datetime) -> tuple[int, Json]:
    state = await apt_region.get_state(session, apt_region.REGIONS_SCOPE)
    if state is None or state.refreshed_at is None:
        job_id = await _start_list_job(session, "region", apt_region.REGIONS_SCOPE)
        return 202, {"status": "collecting", "kind": "region", "jobId": job_id,
                     "progressUrl": progress_url(job_id)}
    if apt_region.is_stale(state, now=now, days=settings.apt_list_refresh_days):
        await _start_list_job(session, "region", apt_region.REGIONS_SCOPE)
    if parent is not None:
        await _region(session, parent, "sido", "sgg")
    items = [{"code": r.code, "name": r.name, "level": r.level}
             for r in await apt_region.children(session, parent)]
    return 200, {"items": items, "refreshedAt": _utc_text(state.refreshed_at)}


# ── 단지 ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ListOutcome:
    #: 받지 못했으면 (종류, 키 없는 사유).
    error: tuple[str, str] | None
    fetched: bool


async def load_complex_list(session: AsyncSession, source: ComplexListSource, umd_code: str, *,
                            settings: Settings, now: dt.datetime) -> ListOutcome:
    """그 동의 단지 목록 — 받은 적 없거나 30일이 지났으면 1회 받는다. 호출한 쪽이 커밋한다."""
    state = await apt_region.get_state(session, apt_region.umd_scope(umd_code))
    if not apt_region.is_stale(state, now=now, days=settings.apt_list_refresh_days):
        return ListOutcome(None, False)
    try:
        fetched = await source.fetch_complex_list(umd_code)
    except DataGoKrError as exc:
        return ListOutcome((exc.kind, mask_secrets(str(exc)) or ""), False)
    await apt_trade.store_raw(session, endpoint=fetched.endpoint, request_ref=fetched.request_ref,
                              status=fetched.raw_status, result_code=fetched.result_code,
                              body=fetched.raw_body, now=now)
    latest = await latest_for_umd(session, umd_code)
    await sync_umd(session, umd_code, listings=fetched.result.complexes, latest=latest)
    await apt_region.mark_refreshed(session, apt_region.umd_scope(umd_code), now=now)
    return ListOutcome(None, True)


def _sort_key(row: AptComplex) -> tuple[bool, int, str]:
    return (row.households is None, -(row.households or 0), row.name)


def _item(row: AptComplex) -> Json:
    sources = [name for name, value in (("kapt", row.kapt_code), ("trade", row.apt_seq))
               if value is not None]
    return {"complexId": row.id, "name": row.name, "jibun": row.jibun,
            "moveInYear": row.move_in_year, "households": row.households, "sources": sources}


async def complexes_response(session: AsyncSession, source: ComplexListSource, umd_code: str, *,
                             settings: Settings, now: dt.datetime) -> Json:
    region = await _region(session, umd_code, "umd")
    lawd_cd = str(region.lawd_cd)
    outcome = await load_complex_list(session, source, umd_code, settings=settings, now=now)
    await session.commit()

    details: Json = {"pending": False, "progressUrl": None}
    running = await apt_job.running_job_id(session, "complex_details", umd_code)
    if running is None and await apt_complex.pending_details(session, umd_code):
        running = await _start_list_job(session, "complex_details", umd_code)
    if running is not None:
        details = {"pending": True, "progressUrl": progress_url(running)}

    trades = await trade_status(session, lawd_cd, settings=settings, now=now, start=True)
    rows = sorted(await apt_complex.live_in_umd(session, umd_code), key=_sort_key)
    body: Json = {
        "umd": {"code": region.code, "name": region.name, "lawdCd": lawd_cd},
        "items": [_item(r) for r in rows], "details": details, "trades": trades.as_json(),
    }
    if outcome.error is not None:
        body["listError"] = {"kind": outcome.error[0], "reason": outcome.error[1]}
    return body


# ── 평형 ──────────────────────────────────────────────────────────


async def resolve_complex(session: AsyncSession, complex_id: int) -> AptComplex:
    """단지 id → 지금의 행(합쳐진 행은 따라간다). 시·군·구 코드가 사라졌으면 409."""
    row = await apt_complex.resolve(session, complex_id)
    if row is None:
        raise UnknownComplex(f"모르는 단지입니다: {complex_id}")
    sgg = await apt_region.sgg_of(session, row.lawd_cd)
    if sgg is not None and sgg.retired_at is not None:
        raise RegionRetired("단지의 시·군·구가 행정구역 개편으로 바뀌었습니다. 지역에서 다시 골라 "
                            "실행하세요.", row.lawd_cd)
    return row


def _month_text(day: dt.date | None) -> str | None:
    return None if day is None else f"{day:%Y-%m}"


async def areas_response(session: AsyncSession, complex_id: int, *, settings: Settings,
                         now: dt.datetime) -> tuple[int, Json]:
    row = await resolve_complex(session, complex_id)
    status = await trade_status(session, row.lawd_cd, settings=settings, now=now, start=False)
    if status.state != "collected":
        started = await start_trade_job(session, row.lawd_cd, settings=settings, now=now)
        return 202, started.collecting_body(row.lawd_cd)
    trades = [] if row.apt_seq is None else await apt_trade.complex_trades(session, row.apt_seq)
    found: dict[str, list[dt.date]] = {}
    for trade in trades:
        found.setdefault(area_bucket(trade.excl_area).key, []).append(trade.deal_date)
    buckets: list[Json] = []
    for bucket in AREA_BUCKETS:
        days = found.get(bucket.key, [])
        first = min(days).replace(day=1) if days else None
        buckets.append({
            "key": bucket.key, "label": bucket.label,
            "minArea": None if bucket.min_area is None else str(bucket.min_area),
            "maxArea": None if bucket.max_area is None else str(bucket.max_area),
            "maxInclusive": bucket.max_inclusive, "trades": len(days),
            "firstMonth": _month_text(first), "lastMonth": _month_text(max(days) if days else None),
            "startableFrom": None if first is None else max(first, TAX_RULES_FROM).isoformat(),
        })
    return 200, {"complexId": row.id, "taxRulesFrom": TAX_RULES_FROM.isoformat(),
                 "buckets": buckets}
