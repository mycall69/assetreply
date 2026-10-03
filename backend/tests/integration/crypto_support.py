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
