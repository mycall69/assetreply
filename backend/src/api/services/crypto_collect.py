"""가상자산 수집 필요 판정 (T032) — 007 FR-013, FR-036, contracts/rest-api 202.

**표와 차트가 같은 판정을 쓴다**(005·006과 같은 이유). 한쪽만 수집을 시작하면 같은 구간을 두 번
받거나, 한쪽은 받은 만큼만 계산한 **틀린 값**을 보인다 — 둘 다 숫자가 멀쩡해 보인다.

일봉과 **환율을 함께 본다.** 시세 통화(USD)가 KRW가 아니면 원금 통화와 관계없이 KRW 평가에 환율이
필요하다(006 FR-068). 환율 판정·요청은 006의 것을 그대로 부른다 — 외환 화면과 같은 판정이다.

일봉은 **시작 월 1일부터** 받는다 — 시작 월의 첫 일봉이 매수일이다(FR-025).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.stock_collect import (
    Collecting,
    FxCollecting,
    plan_fx,
    require_fx_available,
)
from src.api.services.stock_fx import fx_currency_for
from src.config.settings import Settings
from src.db.models import CryptoCoin
from src.repository import crypto_daily, crypto_job
from src.repository.stock import missing_ranges
from src.worker.crypto_queue import CryptoWork, get_crypto_queue
from src.worker.stock_runner import split_into_chunks

Json = dict[str, object]


def start_month(start: dt.date) -> dt.date:
    return start.replace(day=1)


async def plan_collection(
    session: AsyncSession, coin: CryptoCoin, start: dt.date, end: dt.date, *, settings: Settings,
) -> Collecting | None:
    """받지 못한 구간이 있으면 작업을 확보하고 수집 줄에 넘긴다. 다 받았으면 `None`.

    **이미 진행 중이면 새 작업을 만들지 않고 그 작업을 준다** — 중복 수집은 출처 호출만 두 배로
    쓴다.
    """
    coin_id = int(coin.id)
    gaps = missing_ranges(await crypto_daily.get_coverage(session, coin_id), start, end)
    if not gaps:
        return None
    missing_from = min(g[0] for g in gaps)
    missing_through = max(g[1] for g in gaps)
    chunks = sum(len(split_into_chunks(a, b, settings.investing_chunk_days)) for a, b in gaps)
    job_id, created = await crypto_job.acquire_or_get_running(
        session, coin_id, missing_from, missing_through, chunks_total=chunks)
    if created:
        # 커밋해야 수집 줄이 다른 세션에서 그 작업을 볼 수 있다.
        await session.commit()
        get_crypto_queue().request(CryptoWork(
            job_id=job_id, coin_id=coin_id, source_id=coin.source_id,
            start=missing_from, end=missing_through))
    return Collecting(job_id, missing_from, missing_through)


def collecting_json(coin: CryptoCoin, collecting: Collecting | None,
                    fx: FxCollecting | None) -> Json:
    """202 본문. **결과를 싣지 않는다.** 일봉이 다 있으면 수집 필드가 없고, 환율이 다 있으면 `fx`가
    없다."""
    body: Json = {"status": "collecting", "coinId": int(coin.id)}
    if collecting is not None:
        body.update({
            "jobId": collecting.job_id,
            "missingFrom": collecting.missing_from.isoformat(),
            "missingThrough": collecting.missing_through.isoformat(),
            "progressUrl": f"/api/crypto/progress?jobId={collecting.job_id}",
        })
    if fx is not None:
        body["fx"] = {
            "currency": fx.currency, "state": fx.state, "busyWith": fx.busy_with,
            "missingFrom": fx.missing_from.isoformat(),
            "missingThrough": fx.missing_through.isoformat(),
        }
    return body


async def collecting_body(
    session: AsyncSession, coin: CryptoCoin, *, start: dt.date, end: dt.date, settings: Settings,
) -> Json | None:
    """표와 차트가 함께 쓰는 수집 판정. 받을 것이 없으면 `None`, 있으면 202 본문.

    **환율로 막힐 요청이면 일봉 수집도 시작하지 않는다** — 받아도 결과를 낼 수 없다.
    """
    first = start_month(start)
    currency = fx_currency_for(coin.quote_currency)
    if currency is not None:
        await require_fx_available(session, currency, first)
    collecting = await plan_collection(session, coin, first, end, settings=settings)
    fx = await plan_fx(session, currency, first, end) if currency is not None else None
    if collecting is None and fx is None:
        return None
    return collecting_json(coin, collecting, fx)
