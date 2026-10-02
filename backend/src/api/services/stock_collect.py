"""수집 필요 판정과 작업 확보 (T093) — 005 FR-044, FR-047~049.

**표와 차트가 같은 판정을 쓴다.** 한쪽만 수집을 시작하면 같은 구간을 두 번 받거나,
한쪽은 비어 있고 한쪽은 **받은 만큼만 계산한 틀린 값**을 보여준다. 둘 다 숫자가
멀쩡해 보이므로 알아챌 신호가 없다 (FR-049).

판정 근거는 커버리지다. 받으러 갔다가 아무 값도 없었던 구간도 커버리지에는
기록되므로(상장폐지·거래정지), 한 번 시도한 구간을 영원히 다시 받으러 가지 않는다.

006 — **환율도 함께 본다**(FR-043~046). 원금 통화와 종목 통화가 다르면 필요한 구간
(시작일 ~ 계산 끝) 전체의 환율 커버리지를 보고, 비었으면 외환 수집을 요청한다. 시작일
환율만 보면 외환 수집이 멈춘 뒤의 행들이 마지막으로 받은 환율로 평가된다(FR-044).
요청은 `ensure_background_job`을 거친다 — 외환 화면과 같은 판정이다(analyze A1).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.collection_gate import CollectState, ensure_background_job
from src.config.settings import SUPPORTED_CURRENCIES, Settings, load_settings
from src.db.models import Currency, FxCoverage, Stock
from src.ingestion.yahoo.errors import StockSymbolNotFound
from src.repository.stock import get_coverage, missing_ranges
from src.repository.stock_job import acquire_or_get_running, symbol_unknown
from src.worker.queue import StartQueue
from src.worker.stock_queue import StockWork, get_stock_queue
from src.worker.stock_runner import CHUNK_DAYS, split_into_chunks

Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class Collecting:
    """수집 중 응답에 실을 것 (FR-047)."""

    job_id: int
    missing_from: dt.date
    missing_through: dt.date


@dataclass(frozen=True, slots=True)
class FxCollecting:
    """환율 수집 중 (006 contracts 5절). `state`는 수집 표의 것을 그대로 쓴다."""

    currency: str
    state: CollectState
    busy_with: str | None
    missing_from: dt.date
    missing_through: dt.date


class FxNotAvailableBefore(Exception):
    """필요한 날짜가 **수집으로 채울 수 없는 구간**이다 (006 FR-043a, 409).

    수집하지 않는다 — 시작하면 끝나도 여전히 비어 다시 수집하게 되고, 시뮬레이션은 영원히
    "수집 중"에 머문다. 두 사유를 섞지 않는다: `before_probe_start`는 설정을 바꾸면 풀리는데
    `before_first_quote`로 말하면 사용자는 영영 불가능한 것으로 읽는다.
    """

    def __init__(self, *, reason: str, currency: str, available_from: dt.date,
                 message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.currency = currency
        self.available_from = available_from


def collecting_json(
    stock: Stock, collecting: Collecting | None, fx: FxCollecting | None = None
) -> Json:
    """202 본문. **결과를 함께 싣지 않는다** (FR-049).

    주식 시세가 다 있으면 주식 수집 필드(`jobId` 등)를 싣지 않고, 환율이 다 있으면 `fx`를
    싣지 않는다 (006 contracts 5절). 둘 다 비면 둘 다 싣는다 (FR-045).
    """
    body: Json = {"status": "collecting", "market": stock.market, "symbol": stock.symbol}
    if collecting is not None:
        body.update({
            "jobId": collecting.job_id,
            "missingFrom": collecting.missing_from.isoformat(),
            "missingThrough": collecting.missing_through.isoformat(),
            "progressUrl": f"/api/stocks/progress?jobId={collecting.job_id}",
        })
    if fx is not None:
        body["fx"] = {
            "currency": fx.currency, "state": fx.state, "busyWith": fx.busy_with,
            "missingFrom": fx.missing_from.isoformat(),
            "missingThrough": fx.missing_through.isoformat(),
        }
    return body


def fx_currency_for(stock: Stock, principal_currency: str) -> str | None:
    """환산에 외환 DB의 환율이 필요한 통화. 필요 없으면 `None`.

    원금 통화와 종목 통화가 같으면 환전이 없다(005 FR-023). 외환 DB는 원화 대비 환율만
    가지므로 수집할 수 있는 것은 외화 종목의 통화뿐이다.
    """
    if principal_currency == stock.currency or stock.currency not in SUPPORTED_CURRENCIES:
        return None
    return stock.currency


async def require_fx_available(
    session: AsyncSession, currency: str, start: dt.date, *, settings: Settings | None = None
) -> None:
    """필요한 날짜를 외환 수집으로 채울 수 있는지 본다 (FR-043a, research R6-10 표).

    **탐색 시작일을 먼저 판정한다**(analyze N2). 기록된 최초 고시일은 수집한 범위 안의 첫
    날이라, 탐색 시작일보다 앞은 출처에 있는지 모른다. 거꾸로 보면 설정으로 풀리는 제약을
    "출처에 없음"으로 말하게 된다.
    """
    probe = (settings or load_settings()).probe_start(currency)
    if start < probe:
        raise FxNotAvailableBefore(
            reason="before_probe_start", currency=currency, available_from=probe,
            message=(f"{currency} 환율 수집 범위가 {probe.isoformat()}부터로 설정되어 "
                     "있습니다. 설정을 바꾸면 받을 수 있습니다."))
    row = await session.get(Currency, currency)
    first = row.first_available_date if row is not None else None
    if first is not None and start < first:
        raise FxNotAvailableBefore(
            reason="before_first_quote", currency=currency, available_from=first,
            message=f"{first.isoformat()} 이전의 {currency} 환율은 출처에 없습니다.")


async def plan_fx(
    session: AsyncSession, currency: str, start: dt.date, end: dt.date,
    *, queue: StartQueue | None = None,
) -> FxCollecting | None:
    """필요한 구간의 환율 커버리지를 보고, 비었으면 외환 수집을 **요청한다**(FR-043, FR-044).

    작업도 점유도 여기서 만들지 않는다 — `ensure_background_job`의 수집 표를 그대로 싣는다.
    같은 통화가 진행 중이면 그 진행을 따라가고(`collecting`), 다른 통화 때문에 시작할 수
    없으면 기다리는 중임을 드러낸다(`waiting`, FR-046).
    """
    coverage = await session.get(FxCoverage, currency)
    covered = (coverage.covered_from, coverage.covered_through) if coverage else None
    gaps = missing_ranges(covered, start, end)
    if not gaps:
        return None
    ticket = await ensure_background_job(session, currency, queue=queue)
    return FxCollecting(
        currency=currency, state=ticket.state, busy_with=ticket.busy_with,
        missing_from=min(g[0] for g in gaps), missing_through=max(g[1] for g in gaps))


async def collecting_body(
    session: AsyncSession, stock: Stock, *, principal_currency: str,
    start: dt.date, end: dt.date,
) -> Json | None:
    """표와 차트가 함께 쓰는 수집 판정. 받을 것이 없으면 `None`, 있으면 202 본문.

    **환율로 막힐 요청이면 주식 수집도 시작하지 않는다** — 받아도 결과를 낼 수 없다.
    """
    currency = fx_currency_for(stock, principal_currency)
    if currency is not None:
        await require_fx_available(session, currency, start)
    # 시작 월의 1일부터 받는다 — 수집 후 판정이 시작일 앞부분의 일봉까지 본다(research R6-8).
    collecting = await plan_collection(session, stock, start.replace(day=1), end)
    fx = await plan_fx(session, currency, start, end) if currency is not None else None
    if collecting is None and fx is None:
        return None
    return collecting_json(stock, collecting, fx)


async def plan_collection(
    session: AsyncSession, stock: Stock, start: dt.date, end: dt.date
) -> Collecting | None:
    """받지 못한 구간이 있으면 작업을 확보한다. 다 받았으면 `None`.

    **이미 진행 중이면 새 작업을 만들지 않고 그 작업 ID를 준다**(FR-048). 중복 수집은
    오류 없이 성공하면서 출처 호출만 두 배로 쓰는데, 출처가 한도를 공개하지 않아 그
    대가를 미리 알 수 없다.
    """
    stock_id = int(stock.id)
    covered = await get_coverage(session, stock_id)
    gaps = missing_ranges(covered, start, end)
    if not gaps:
        return None
    # 006 FR-032 — 마지막 수집이 "출처가 심볼을 모름"으로 끝났으면 다시 받으러 가지 않는다.
    # 가면 같은 실패를 되풀이하고, 화면은 "받고 있습니다"와 실패를 번갈아 보인다.
    if await symbol_unknown(session, stock_id):
        raise StockSymbolNotFound(
            f"시세 출처에서 그 종목을 찾지 못했습니다: {stock.market}:{stock.symbol}")

    missing_from = min(g[0] for g in gaps)
    missing_through = max(g[1] for g in gaps)
    chunks = sum(len(split_into_chunks(a, b, CHUNK_DAYS)) for a, b in gaps)

    job_id, created = await acquire_or_get_running(
        session, stock_id, missing_from, missing_through, chunks_total=chunks)
    if created:
        # 커밋해야 워커가 다른 세션에서 그 작업을 볼 수 있다.
        await session.commit()
        get_stock_queue().request(StockWork(
            job_id=job_id, stock_id=stock_id, symbol=stock.symbol,
            start=missing_from, end=missing_through))

    return Collecting(job_id, missing_from, missing_through)
