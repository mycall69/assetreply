"""ECOS 계약 테스트 공용 픽스처.

헌법 원칙 III: 외부 API는 저장된 응답 픽스처로 검증하며, 전체 스위트는 네트워크 없이
통과해야 한다. 여기의 스텁은 실제 HTTP를 발생시키지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Self

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> object:
    return json.loads(load(name))


class StubResponse:
    """aiohttp 응답 흉내. 상태 코드와 본문만 제공한다."""

    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class StubSession:
    """호출 순서대로 정해둔 응답을 돌려준다. 호출 횟수를 기록해 재시도를 검증한다."""

    def __init__(self, *responses: StubResponse) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> StubResponse:
        self.calls.append(url)
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[idx]

    async def close(self) -> None:
        return None


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """백오프 대기를 즉시 반환시키고 대기 시간을 기록한다."""
    import asyncio

    delays: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return delays
