"""007 가상자산 테스트 공용 도구 — 출처 스텁, 설정, 목록 시드.

출처 스텁은 **쪽(`CoinPageFetch`) 단위로** 내놓는다. 클라이언트가 실제로 내놓는 모양 그대로라야 교체
서비스가 받는 입력이 운영과 같다. 본문은 실제 응답 픽스처(T001)다. 네트워크를 쓰지 않는다(헌법 원칙
III).
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from pathlib import Path

from src.config.settings import Settings, _Secret
from src.ingestion.investing.client import CoinPageFetch
from src.ingestion.investing.parse import parse_coin_page

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "crypto"

#: 기준 시각. 저장 시각은 UTC(시간대 없는 값)다 — 2026-10-03 00:05:12 UTC = 한국 09:05:12.
NOW = dt.datetime(2026, 10, 3, 0, 5, 12)
TODAY = dt.date(2026, 10, 3)
#: 로그·사유에 남으면 안 되는 사용자 에이전트(FR-019, SC-011).
UA_SENTINEL = "UA-SENTINEL-crypto-7777"

BTC_ID = "1057391"
ETH_ID = "1061443"
BNB_ID = "1061448"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EN = [fixture("coins_en_p1.json"), fixture("coins_en_last.json")]
KO = [fixture("coins_ko_p1.json")]


def crypto_settings(**over: object) -> Settings:
    base: dict[str, object] = dict(
        ecos_api_key=_Secret("ecos"), investing_user_agent=UA_SENTINEL,
        investing_min_interval_ms=0, crypto_list_refresh_days=7)
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


def compact_bodies() -> tuple[list[str], list[str]]:
    """`coins_all_compact.json`(3,654개)을 출처 응답 모양의 쪽 본문으로 되돌린다 — 영문·한국어 각
    37쪽.

    한국어 판의 이름은 한글 이름이 있으면 그것, 없으면 영문 그대로다(출처가 그렇게 준다 — research
    R7-5).
    """
    coins = json.loads(fixture("coins_all_compact.json"))
    en: list[str] = []
    ko: list[str] = []
    pages = [coins[i:i + 100] for i in range(0, len(coins), 100)]
    for n, chunk in enumerate(pages):
        cursor = f"cursor-{n + 1}" if n + 1 < len(pages) else None
        row = [{k: c[k] for k in ("instrument_id", "name", "symbol", "rank", "slug")}
               for c in chunk]
        en.append(json.dumps({"coins": row, "next_page_cursor": cursor}))
        ko_row = [dict(r, name=c.get("name_ko") or c["name"])
                  for r, c in zip(row, chunk, strict=True)]
        ko.append(json.dumps({"coins": ko_row, "next_page_cursor": cursor}, ensure_ascii=False))
    return en, ko


Reply = Sequence[str | Exception]
PageHook = Callable[[str, int], Awaitable[None]]


class StubCoinSource:
    """`CoinListSource` 스텁. 판마다 응답을 차례로 꺼낸다.

    응답 하나는 본문 목록이다 — 본문을 쪽마다 내놓고, 예외가 있으면 그 자리에서 낸다(중간 쪽 실패).
    `before_page`가 있으면 **k번째 쪽을 내놓기 전에** 부른다 — 그때까지의 진행이 기록되었는지
    테스트가 본다.
    """

    def __init__(self, replies: dict[str, list[Reply]] | None = None) -> None:
        self._replies = {k: list(v) for k, v in (replies or {}).items()}
        self.calls: list[str] = []
        self.before_page: PageHook | None = None

    def add(self, edition: str, reply: Reply) -> None:
        self._replies.setdefault(edition, []).append(reply)

    async def fetch_coin_pages(self, edition: str) -> AsyncIterator[CoinPageFetch]:
        self.calls.append(edition)
        queue = self._replies.get(edition) or []
        if not queue:
            raise AssertionError(f"스텁에 {edition} 응답이 없습니다")
        reply = queue.pop(0)
        for page_no, item in enumerate(reply, start=1):
            if self.before_page is not None:
                await self.before_page(edition, page_no)
            if isinstance(item, Exception):
                raise item
            yield CoinPageFetch(page=parse_coin_page(item), page_no=page_no, raw=item, status=200)


async def seed(session_factory, *, en: Reply = EN, ko: Reply = KO,  # type: ignore[no-untyped-def]
               now: dt.datetime = NOW, settings: Settings | None = None):
    """목록을 **교체 서비스로** 넣는다. 테이블에 직접 넣으면 교체 규칙이 가려진다."""
    from src.api.services.crypto_list_refresh import refresh_coins

    source = StubCoinSource({"en": [en], "ko": [ko]})
    return await refresh_coins(session_factory, source, settings=settings or crypto_settings(),
                               now=lambda: now)


def reset_crypto_list_state() -> None:
    """검색 색인과 목록 갱신 큐를 비운다. 둘 다 프로세스 메모리에 산다 — 스키마를 새로 만들어도
    남는다."""
    from src.api.services.crypto_index import reset_coin_index
    from src.worker.crypto_list_queue import reset_crypto_list_queue

    reset_coin_index()
    reset_crypto_list_queue()


# ── 일봉 수집 (Phase 4) ──────────────────────────────────────────────

LEASH_ID = "1230723"
SHIB_ID = "1177506"


async def add_coin(session_factory, source_id: str = BTC_ID, symbol: str = "BTC",  # type: ignore[no-untyped-def]
                   name: str = "Bitcoin", *, name_ko: str | None = "비트코인",
                   first_available: dt.date | None = None, rank: int | None = 1) -> int:
    """코인 한 줄을 넣는다. 목록 교체 규칙을 보는 테스트가 아니면 이것으로 충분하다."""
    from src.db.models import CryptoCoin

    async with session_factory() as s:
        coin = CryptoCoin(
            source="investing", source_id=source_id, slug=name.lower(), symbol=symbol,
            name_en=name, name_ko=name_ko, quote_currency="USD", market_rank=rank,
            status="listed", first_available_date=first_available,
            first_seen_at=NOW, last_seen_at=NOW)
        s.add(coin)
        await s.commit()
        return int(coin.id)


def _rows(*names: str) -> list[dict]:  # type: ignore[type-arg]
    rows: dict[str, dict] = {}  # type: ignore[type-arg]
    for name in names:
        data = json.loads(fixture(name))["data"] or []
        for row in data:
            rows[row["rowDateTimestamp"][:10]] = row
    return [rows[k] for k in sorted(rows, reverse=True)]


class StubDailySource:
    """`CryptoSource` 스텁. 코인마다 픽스처 행을 모아 두고, 요청 구간의 행만 실어 **실제 응답
    모양**으로 돌려준다.

    응답 해석은 실제 파서(`parse_daily`)가 한다 — 형식 오류도 실제 경로로 난다. `errors`는 n번째
    호출(1부터)에서 낼 예외, `corrupt`는 n번째 호출 응답의 첫 행에서 망가뜨릴 필드다.
    """

    def __init__(self, data: dict[str, Sequence[str]]) -> None:
        self._rows = {source_id: _rows(*names) for source_id, names in data.items()}
        self.calls: list[tuple[str, dt.date, dt.date]] = []
        self.errors: dict[int, Exception] = {}
        self.corrupt: dict[int, str] = {}
        self.gate: object | None = None

    async def fetch_daily(self, source_id: str, start: dt.date, end: dt.date, *,
                          last_day: dt.date):  # type: ignore[no-untyped-def]
        import asyncio

        from src.ingestion.investing.client import DailyFetch
        from src.ingestion.investing.parse import parse_daily

        self.calls.append((source_id, start, end))
        n = len(self.calls)
        if isinstance(self.gate, asyncio.Event):
            await self.gate.wait()
        if n in self.errors:
            raise self.errors[n]
        rows = [dict(r) for r in self._rows.get(source_id, [])
                if start <= dt.date.fromisoformat(r["rowDateTimestamp"][:10]) <= end]
        if n in self.corrupt and rows:
            rows[0][self.corrupt[n]] = "-"
        body = json.dumps({"data": rows or None, "summary": {}})
        return DailyFetch(bars=parse_daily(body, last_day=last_day), requested_from=start,
                          requested_to=end, raw=body, status=200)


async def seed_daily(session_factory, coin_id: int, *names: str,  # type: ignore[no-untyped-def]
                     covered: tuple[dt.date, dt.date] | None = None,
                     drop: Sequence[dt.date] = ()) -> None:
    """수집을 마친 상태를 흉내 낸다 — 일봉과 커버리지. 커버리지를 적지 않으면 미수집으로 판정돼
    202다."""
    from src.ingestion.investing.parse import parse_daily
    from src.repository import crypto_daily

    body = json.dumps({"data": _rows(*names), "summary": {}})
    bars = [b for b in parse_daily(body, last_day=dt.date(2100, 1, 1)) if b.day not in drop]
    async with session_factory() as s:
        await crypto_daily.store_bars(s, coin_id, bars)
        if covered is not None:
            await crypto_daily.record_coverage(s, coin_id, *covered)
        await s.commit()


async def seed_usd(session_factory, start: dt.date, end: dt.date, *,  # type: ignore[no-untyped-def]
                   provisional: Sequence[dt.date] = ()) -> None:
    """매일의 USD 매매기준율과 커버리지. 값은 날마다 달라 행마다 그 날짜의 환율을 썼는지
    드러난다."""
    from decimal import Decimal

    from src.db.dialect import upsert
    from src.db.models import FxCoverage, FxRate

    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    async with session_factory() as s:
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": d,
            "base_rate": Decimal(1100 + d.toordinal() % 100), "quote_unit": 1,
            "source": "ECOS:731Y001", "is_provisional": d in provisional} for d in days])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD", "covered_from": start, "covered_through": end}], preserve=())
        await s.commit()


def usd_rate(day: dt.date) -> str:
    """`seed_usd`가 넣은 그날의 환율(소수 6자리 문자열)."""
    return f"{1100 + day.toordinal() % 100}.000000"
