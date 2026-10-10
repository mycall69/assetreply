"""지표 모달의 장중 시세 (014 반복 2026-10-10b T116) — FR-028, research R14-19, contracts
A2(`1d`·`5d`).

**저장하지 않는다** — 서버 메모리에 지표·기간마다 짧게(일 60초·주 300초 — 설정) 두고 그 안이면
출처를 다시 부르지 않는다. 같은 순간의 요청은 출처를 한 번 부른다(단일 비행). 실패는 현재 시세와
같은 짧은 기억(10초)이다. 출처의 한도는 Yahoo 관문이 주식·대시보드와 함께 지킨다(클라이언트 안).

점은 모두 잠정이다(확정 값의 근거가 아니다 — spec FR-028). 환율은 시장 환율이고 `market_fx` 주석을
단다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from src.api.services.market_quotes import dec, indicator_json
from src.config.settings import Settings
from src.ingestion.yahoo.market import IntradayFetch, IntradayRange, failure_kind
from src.simulation.market_indicators import Indicator

Json = dict[str, object]


class IntradaySource(Protocol):
    async def fetch_intraday(
        self, indicator_id: str, range_key: IntradayRange
    ) -> IntradayFetch: ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"


@dataclass(frozen=True, slots=True)
class _Entry:
    body: Json
    until: dt.datetime


class IntradayService:
    def __init__(
        self,
        source: IntradaySource,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._source = source
        self._settings = settings
        self._clock = clock
        self._entries: dict[tuple[str, str], _Entry] = {}
        # 잠금은 이벤트 루프에 묶인다 — 처음 쓸 때 만든다
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def _ttl(self, range_key: IntradayRange) -> dt.timedelta:
        seconds = (
            self._settings.dashboard_intraday_day_cache_seconds
            if range_key == "1d"
            else self._settings.dashboard_intraday_week_cache_seconds
        )
        return dt.timedelta(seconds=seconds)

    async def body(self, indicator: Indicator, range_key: IntradayRange) -> Json:
        """contracts A2 장중 본문. 출처가 실패해도 본문이다(`status: "failed"`)."""
        key = (indicator.id, range_key)
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        async with lock:
            now = self._clock()
            cached = self._entries.get(key)
            if cached is not None and now < cached.until:
                return cached.body
            try:
                fetched = await self._source.fetch_intraday(indicator.id, range_key)
            except (
                Exception
            ) as exc:  # 출처의 어떤 실패도 그 기간만의 실패다 — 다른 기간·표는 그대로
                body = self._failed(indicator, range_key, failure_kind(exc), str(exc))
                hold = dt.timedelta(seconds=self._settings.market_quote_failure_cache_seconds)
                self._entries[key] = _Entry(body, now + hold)
                return body
            times = [at for at, _ in fetched.points]
            body = {
                **self._head(indicator, range_key),
                "status": "ok",
                "fetchedAt": _iso(now),
                "session": ({"from": _iso(times[0]), "to": _iso(times[-1])} if times else None),
                "points": [
                    {"time": _iso(at), "value": dec(value), "provisional": True}
                    for at, value in fetched.points
                ],
                "failure": None,
            }
            self._entries[key] = _Entry(body, now + self._ttl(range_key))
            return body

    def _head(self, indicator: Indicator, range_key: IntradayRange) -> Json:
        block = indicator_json(indicator)
        block.pop("order", None)
        # 환율은 `market_fx`(시장 환율), 선물은 `future_roll` — 카드·일봉 그래프와 같은 주석
        notes = list(indicator.notes)
        return {"indicator": block, "range": range_key, "intraday": True, "notes": notes}

    def _failed(
        self, indicator: Indicator, range_key: IntradayRange, reason: str, message: str
    ) -> Json:
        return {
            **self._head(indicator, range_key),
            "status": "failed",
            "fetchedAt": None,
            "session": None,
            "points": [],
            "failure": {
                "reason": reason,
                "message": message or "장중 시세를 받지 못했습니다.",
                "retryAfterSeconds": None,
            },
        }


_shared: IntradayService | None = None


def set_shared_service(service: IntradayService | None) -> None:
    """앱 수명의 서비스 — `lifespan`이 둔다(ASGITransport 테스트는 직접 둔다)."""
    global _shared
    _shared = service


def get_shared_service() -> IntradayService | None:
    return _shared
