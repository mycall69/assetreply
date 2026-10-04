"""환율과 예금이 함께 쓰는 ECOS 관문 (T005) — 008 FR-013, SC-012, research R8-6.

같은 출처·같은 인증키다. 각자 세마포어를 가지면 **합친 호출을 아무도 보지 않아**, 한쪽이 한도에
걸려도 다른 쪽이 계속 불러 둘 다 막힌다. 관문은 프로세스 하나에 하나다:

- 동시에 나가는 ECOS 요청 수를 `ECOS_MAX_CONCURRENT_REQUESTS`로 제한한다
  (001 `EcosClient`와 예금 클라이언트를 합쳐서)
- 누가 한도 초과(`INFO-300`)를 받으면, 그 백오프 동안 **다른 쪽의 다음 요청도** 기다린다
- 한도 신호가 없으면 서로 기다리지 않는다(동시 수 안에서)

001 `EcosClient`의 재시도·잘림·항목 매핑은 001 계약 테스트가 그대로 지킨다.
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt

import pytest

from src.config.settings import Settings, load_settings
from src.ingestion.ecos import gate as gate_module
from src.ingestion.ecos.client import EcosClient
from src.ingestion.ecos.deposit_client import EcosDepositClient
from src.ingestion.ecos.gate import get_gate

from .conftest import StubResponse, load

DAY = (dt.date(2005, 3, 15), dt.date(2005, 3, 17))


def _settings(limit: int) -> Settings:
    return dataclasses.replace(load_settings(), ecos_max_concurrent_requests=limit)


class _HoldingSession:
    """요청을 붙잡아 두고 동시에 나가 있는 수를 잰다."""

    def __init__(self, body: str, counter: dict[str, int], release: asyncio.Event) -> None:
        self._body = body
        self._counter = counter
        self._release = release
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> _HoldingSession:
        self.calls.append(url)
        return self

    async def __aenter__(self) -> StubResponse:
        self._counter["now"] += 1
        self._counter["max"] = max(self._counter["max"], self._counter["now"])
        await self._release.wait()
        self._counter["now"] -= 1
        return StubResponse(self._body)

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def close(self) -> None:
        return None


class _SequenceSession:
    def __init__(self, *bodies: str) -> None:
        self._bodies = list(bodies)
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> StubResponse:
        self.calls.append(url)
        return StubResponse(self._bodies[min(len(self.calls) - 1, len(self._bodies) - 1)])

    async def close(self) -> None:
        return None


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def test_관문은_프로세스에_하나다() -> None:
    assert get_gate(load_settings()) is get_gate(load_settings())


async def test_환율과_예금을_합친_동시_요청이_설정_수를_넘지_않는다() -> None:
    settings = _settings(2)
    counter = {"now": 0, "max": 0}
    release = asyncio.Event()
    fx = [EcosClient(settings, session=_HoldingSession(  # type: ignore[arg-type]
        load("search_ok.json"), counter, release), item_codes={"USD": "0000001"}) for _ in range(2)]
    deposit = [EcosDepositClient(settings, session=_HoldingSession(  # type: ignore[arg-type]
        load("deposit/items_121Y004.json"), counter, release)) for _ in range(2)]
    tasks = [asyncio.create_task(c.fetch_daily_rates("USD", *DAY)) for c in fx]
    tasks += [asyncio.create_task(c.fetch_items("121Y004")) for c in deposit]
    await _settle()
    assert counter["now"] == 2, "관문이 동시 수를 지키지 않았다"
    release.set()
    await asyncio.gather(*tasks)
    assert counter["max"] == 2


async def test_한쪽이_한도_초과를_받으면_다른_쪽도_백오프_동안_기다린다(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """예금이 INFO-300을 받고 쉬는 동안 환율이 계속 부르면 한도가 더 굳는다(SC-012 ②)."""
    pause = asyncio.Event()
    sleeping = asyncio.Event()
    real_sleep = asyncio.sleep

    async def held_sleep(seconds: float) -> None:
        # 0초 양보(테스트의 _settle)는 그대로 두고, 백오프 대기만 붙잡는다.
        if seconds <= 0:
            await real_sleep(0)
            return
        sleeping.set()
        await pause.wait()

    monkeypatch.setattr(gate_module.asyncio, "sleep", held_sleep)
    settings = _settings(3)
    deposit_session = _SequenceSession(load("info_300_rate_limit.json"),
                                       load("deposit/items_121Y004.json"))
    fx_session = _SequenceSession(load("search_ok.json"))
    deposit = EcosDepositClient(settings, session=deposit_session)  # type: ignore[arg-type]
    fx = EcosClient(settings, session=fx_session,  # type: ignore[arg-type]
                    item_codes={"USD": "0000001"})

    first = asyncio.create_task(deposit.fetch_items("121Y004"))
    await sleeping.wait()
    second = asyncio.create_task(fx.fetch_daily_rates("USD", *DAY))
    await _settle()
    assert fx_session.calls == [], "한도 초과 백오프 중에 다른 쪽이 출처를 불렀다"
    pause.set()
    await asyncio.gather(first, second)
    assert len(fx_session.calls) == 1
    assert len(deposit_session.calls) == 2


async def test_한도_신호가_없으면_서로_기다리지_않는다() -> None:
    settings = _settings(3)
    counter = {"now": 0, "max": 0}
    release = asyncio.Event()
    fx = EcosClient(settings, session=_HoldingSession(  # type: ignore[arg-type]
        load("search_ok.json"), counter, release), item_codes={"USD": "0000001"})
    deposit = EcosDepositClient(settings, session=_HoldingSession(  # type: ignore[arg-type]
        load("deposit/items_121Y004.json"), counter, release))
    tasks = [asyncio.create_task(fx.fetch_daily_rates("USD", *DAY)),
             asyncio.create_task(deposit.fetch_items("121Y004"))]
    await _settle()
    assert counter["now"] == 2, "한도 신호가 없는데 한쪽이 기다렸다"
    release.set()
    await asyncio.gather(*tasks)
