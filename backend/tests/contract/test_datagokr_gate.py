"""공공데이터포털 관문 (T006) — 009 FR-012, SC-012, research R9-5, 헌법 원칙 II.

네 자료(실거래·법정동코드·단지 목록·기본 정보)가 같은 포털·같은 인증키다. 관문은 이벤트 루프에
하나다:

- 동시에 나가는 요청 수를 `DATA_API_MAX_CONCURRENT`로 묶는다(실거래 줄·목록 줄·요청 경로가 함께)
- **자료별 하루 호출 수를 보내기 전에 센다** — 설정 한도에 닿으면 보내지 않고 한도 오류다. 출처가
  키를 막기 전에 멈추는 것이 목적이다(SC-012). 날짜는 한국 시간이고 자정이 지나면 0부터 다시 센다
- 포털이 한도 사유 22를 주면 그날 그 자료의 요청을 더 보내지 않는다(다른 자료는 계속)
"""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from src.ingestion.datagokr.errors import DataGoKrRateLimited
from src.ingestion.datagokr.gate import DataGoKrGate

LIMITS = {"trade": 3, "region": 9000, "kapt": 4500}


class FakeCounter:
    """하루 호출 수를 메모리에 센다 — DB 구현(`repository/apt_usage.py`)은 통합 테스트가 본다."""

    def __init__(self) -> None:
        self.calls: dict[tuple[str, dt.date], int] = {}

    async def take(self, api: str, day: dt.date, limit: int) -> bool:
        used = self.calls.get((api, day), 0)
        if used >= limit:
            return False
        self.calls[(api, day)] = used + 1
        return True


class Clock:
    def __init__(self, day: str) -> None:
        self.day = dt.date.fromisoformat(day)

    def __call__(self) -> dt.date:
        return self.day


def gate(counter: FakeCounter | None = None, *, limit: int = 3,
         day: str = "2026-10-05") -> DataGoKrGate:
    return DataGoKrGate(limit, counter or FakeCounter(), LIMITS, today=Clock(day))


async def test_동시_요청_수를_넘지_않는다() -> None:
    door = gate(limit=2)
    now = peak = 0
    release = asyncio.Event()

    async def request(api: str) -> None:
        nonlocal now, peak
        async with door.slot(api):
            now += 1
            peak = max(peak, now)
            await release.wait()
            now -= 1

    apis = ("region", "kapt", "region", "kapt", "region")
    tasks = [asyncio.create_task(request(api)) for api in apis]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert now == 2
    release.set()
    await asyncio.gather(*tasks)
    assert peak == 2


async def test_하루_한도에_닿으면_보내지_않는다() -> None:
    counter = FakeCounter()
    door = gate(counter)
    for _ in range(3):
        async with door.slot("trade"):
            pass
    with pytest.raises(DataGoKrRateLimited):
        async with door.slot("trade"):
            raise AssertionError("한도를 넘겨 보냈다")
    assert counter.calls[("trade", dt.date(2026, 10, 5))] == 3
    async with door.slot("region"):  # 다른 자료는 따로 센다
        pass


async def test_자정이_지나면_다시_센다() -> None:
    counter = FakeCounter()
    clock = Clock("2026-10-05")
    door = DataGoKrGate(3, counter, LIMITS, today=clock)
    for _ in range(3):
        async with door.slot("trade"):
            pass
    clock.day = dt.date(2026, 10, 6)
    async with door.slot("trade"):
        pass
    assert counter.calls[("trade", dt.date(2026, 10, 6))] == 1


async def test_사유_22를_받은_자료는_그날_더_보내지_않는다() -> None:
    counter = FakeCounter()
    clock = Clock("2026-10-05")
    door = DataGoKrGate(3, counter, {**LIMITS, "trade": 9000}, today=clock)
    door.block("trade")
    with pytest.raises(DataGoKrRateLimited):
        async with door.slot("trade"):
            raise AssertionError("막힌 자료를 보냈다")
    assert ("trade", dt.date(2026, 10, 5)) not in counter.calls  # 세지도 않는다
    async with door.slot("kapt"):
        pass
    clock.day = dt.date(2026, 10, 6)
    async with door.slot("trade"):
        pass
