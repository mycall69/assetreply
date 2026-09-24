"""진행 중일 때 다른 통화 시작 거절 (T089) — FR-004, FR-029, SC-017.

한 번에 한 통화만 돈다. 다른 통화의 시작 요청이 오면 **거절하고 어느 통화가 진행
중인지 알려야 한다.** 조용히 무시하면 사용자는 버튼이 고장난 것으로 여긴다.
"""
from __future__ import annotations

import pytest

from src.worker.queue import StartQueue, get_queue, reset_queue


@pytest.fixture(autouse=True)
def _clean_queue():
    reset_queue()
    yield
    reset_queue()


class Test거절:
    async def test_다른_통화가_진행_중이면_받지_않는다(self) -> None:
        q = StartQueue()
        assert await q.request("USD") is True
        assert await q.request("JPY") is False

    async def test_어느_통화가_진행_중인지_알려준다(self) -> None:
        """이름을 대지 않으면 사용자가 무엇을 기다려야 할지 모른다 (FR-029)."""
        q = StartQueue()
        await q.request("USD")
        assert q.in_progress == "USD"

    async def test_같은_통화의_중복_요청도_거절한다(self) -> None:
        """이 경우는 '합류'로 다뤄진다 — 새 작업을 만들지 않는다 (FR-003)."""
        q = StartQueue()
        await q.request("USD")
        assert await q.request("USD") is False

    async def test_앞_통화가_끝나면_받는다(self) -> None:
        q = StartQueue()
        await q.request("USD")
        await q.pop()
        q.done("USD")
        assert await q.request("JPY") is True


class Test전역_큐:
    def test_같은_인스턴스를_돌려준다(self) -> None:
        """라우트와 워커가 같은 큐를 봐야 요청이 전달된다."""
        assert get_queue() is get_queue()

    def test_리셋하면_새_인스턴스다(self) -> None:
        first = get_queue()
        reset_queue()
        assert get_queue() is not first


class Test라우트_응답:
    async def test_진행_중이면_409를_돌려준다(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.main import create_app

        queue = get_queue()
        await queue.request("USD")

        with TestClient(create_app()) as client:
            res = client.post("/api/fx/collect", json={"currency": "JPY"})
        assert res.status_code == 409
        body = res.json()
        assert body["status"] == "collection_in_progress"
        assert "USD" in body["message"], "진행 중인 통화 이름이 본문에 없다"

    async def test_지원하지_않는_통화는_404다(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.main import create_app

        with TestClient(create_app()) as client:
            res = client.post("/api/fx/collect", json={"currency": "XXX"})
        assert res.status_code == 404
