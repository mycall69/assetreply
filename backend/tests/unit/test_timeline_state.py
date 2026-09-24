"""시간축 상태 판정 검증 (T034) — FR-006, FR-006a, SC-011.

`state`는 세 값으로 갈린다. 두 값으로 합치면 FR-006a가 요구하는 "회수를 기다리는 중"을
표현할 수 없어, 사용자가 **기다려야 하는지 아닌지**를 알 수 없다.

| 값 | 하트비트 경과 | 화면 의미 |
|----|--------------|-----------|
| `running` | 60초 이내 | 정상 진행 중 |
| `stalled` | 60~900초 | 응답 없음 — 회수 대기 중 |
| `awaiting_reclaim` | 900초 초과 | 곧 부분 완료로 확정된다 |
"""
from __future__ import annotations

import datetime as dt

from src.api.services.timeline import chunk_bounds, job_state

STALL = 60
RECLAIM = 900


def _ago(seconds: int) -> dt.datetime:
    return dt.datetime.now() - dt.timedelta(seconds=seconds)


class Test상태_판정:
    def test_방금_뛴_하트비트는_running이다(self) -> None:
        assert job_state(_ago(1), stall_seconds=STALL, reclaim_seconds=RECLAIM) == "running"

    def test_경계_직전은_running이다(self) -> None:
        assert job_state(_ago(58), stall_seconds=STALL, reclaim_seconds=RECLAIM) == "running"

    def test_60초를_넘으면_stalled다(self) -> None:
        assert job_state(_ago(120), stall_seconds=STALL, reclaim_seconds=RECLAIM) == "stalled"

    def test_900초를_넘으면_awaiting_reclaim이다(self) -> None:
        assert job_state(_ago(1200), stall_seconds=STALL,
                         reclaim_seconds=RECLAIM) == "awaiting_reclaim"

    def test_세_값이_모두_구별된다(self) -> None:
        """합치면 사용자가 기다려야 하는지 알 수 없다 (FR-006a)."""
        states = {
            job_state(_ago(1), stall_seconds=STALL, reclaim_seconds=RECLAIM),
            job_state(_ago(120), stall_seconds=STALL, reclaim_seconds=RECLAIM),
            job_state(_ago(1200), stall_seconds=STALL, reclaim_seconds=RECLAIM),
        }
        assert len(states) == 3

    def test_하트비트가_없으면_awaiting_reclaim이다(self) -> None:
        """점유가 사라졌는데 작업이 진행 중이면 회수 대상이다."""
        assert job_state(None, stall_seconds=STALL,
                         reclaim_seconds=RECLAIM) == "awaiting_reclaim"


class Test현재_구간_계산:
    """저장하지 않고 계산한다 (research R3-6). 작업 행에 컬럼을 더할 이유가 없다."""

    def test_첫_구간은_시작일부터다(self) -> None:
        got = chunk_bounds(dt.date(2020, 1, 1), dt.date(2022, 12, 31),
                           chunks_done=0, chunk_days=365)
        assert got is not None and got[0] == dt.date(2020, 1, 1)

    def test_수집이_쓰는_분할과_정확히_일치한다(self) -> None:
        """직접 계산하면 윤년 경계에서 하루씩 어긋나 엉뚱한 구간을 강조하게 된다.

        2020년은 윤년이라 365일 청크가 12-31이 아니라 12-30에 끝난다. 화면과 수집이
        같은 함수를 봐야 이런 차이가 생기지 않는다.
        """
        from src.ingestion.collector import split_into_chunks

        start, end = dt.date(2020, 1, 1), dt.date(2022, 12, 31)
        expected = split_into_chunks(start, end, chunk_days=365)
        for i, want in enumerate(expected):
            assert chunk_bounds(start, end, chunks_done=i, chunk_days=365) == want

    def test_두_번째_구간은_첫_구간의_다음날부터다(self) -> None:
        first = chunk_bounds(dt.date(2020, 1, 1), dt.date(2022, 12, 31),
                             chunks_done=0, chunk_days=365)
        second = chunk_bounds(dt.date(2020, 1, 1), dt.date(2022, 12, 31),
                              chunks_done=1, chunk_days=365)
        assert first is not None and second is not None
        assert second[0] == first[1] + dt.timedelta(days=1)

    def test_마지막_구간은_종료일을_넘지_않는다(self) -> None:
        got = chunk_bounds(dt.date(2020, 1, 1), dt.date(2020, 6, 30),
                           chunks_done=0, chunk_days=365)
        assert got == (dt.date(2020, 1, 1), dt.date(2020, 6, 30))

    def test_모두_끝났으면_None이다(self) -> None:
        assert chunk_bounds(dt.date(2020, 1, 1), dt.date(2020, 6, 30),
                            chunks_done=1, chunk_days=365) is None

    def test_범위를_넘어선_진행도_None이다(self) -> None:
        assert chunk_bounds(dt.date(2020, 1, 1), dt.date(2020, 6, 30),
                            chunks_done=99, chunk_days=365) is None
