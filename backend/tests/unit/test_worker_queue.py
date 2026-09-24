"""시작 요청 큐 검증 (T030) — FR-003, research R3-1.

같은 통화의 중복 시작 요청이 큐에 쌓이면 수집이 두 번 돈다. DB 점유가 실행 자체는
막지만, 그 확인에도 비용이 들고 큐가 무의미하게 길어진다. **큐 단계에서 거른다.**
"""
from __future__ import annotations

from src.worker.queue import StartQueue


class Test중복_요청:
    async def test_같은_통화를_두_번_요청하면_두_번째는_거절된다(self) -> None:
        q = StartQueue()
        assert await q.request("USD") is True
        assert await q.request("USD") is False

    async def test_거절돼도_큐에_쌓이지_않는다(self) -> None:
        q = StartQueue()
        await q.request("USD")
        await q.request("USD")
        assert q.size == 1

    async def test_다중_모드에서는_다른_통화를_따로_받는다(self) -> None:
        """큐 자체는 다중 통화를 다룰 수 있다. 단일 제약은 모드로 건다."""
        q = StartQueue(single_currency=False)
        assert await q.request("USD") is True
        assert await q.request("JPY") is True
        assert q.size == 2

    async def test_처리를_마치면_다시_요청할_수_있다(self) -> None:
        q = StartQueue()
        await q.request("USD")
        assert await q.pop() == "USD"
        q.done("USD")
        assert await q.request("USD") is True

    async def test_pop만_하고_done_전에는_거절한다(self) -> None:
        """진행 중인 통화의 중복 요청을 막는다 (FR-003)."""
        q = StartQueue()
        await q.request("USD")
        await q.pop()
        assert await q.request("USD") is False


class Test상태_조회:
    async def test_빈_큐의_크기는_0이다(self) -> None:
        assert StartQueue().size == 0

    async def test_진행_중_통화를_알려준다(self) -> None:
        """다른 통화의 시작 요청을 거절할 때 이름을 대야 한다 (FR-029)."""
        q = StartQueue()
        await q.request("USD")
        await q.pop()
        assert q.in_progress == "USD"

    async def test_처리를_마치면_진행_중이_없다(self) -> None:
        q = StartQueue()
        await q.request("USD")
        await q.pop()
        q.done("USD")
        assert q.in_progress is None

    async def test_대기_중인_통화도_진행_중으로_본다(self) -> None:
        """큐에 있으면 곧 돈다. 그 사이 다른 통화를 받으면 병행이 된다."""
        q = StartQueue()
        await q.request("USD")
        assert q.in_progress == "USD"


class Test단일_통화_제약:
    async def test_다른_통화가_대기_중이면_거절한다(self) -> None:
        """한 번에 한 통화만 돈다 (FR-004, 2026-09-24 반복)."""
        q = StartQueue(single_currency=True)
        assert await q.request("USD") is True
        assert await q.request("JPY") is False

    async def test_앞_통화를_마치면_받는다(self) -> None:
        q = StartQueue(single_currency=True)
        await q.request("USD")
        await q.pop()
        q.done("USD")
        assert await q.request("JPY") is True
