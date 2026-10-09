"""지표 수집의 할 일 계획 (014 T045) — FR-017, FR-019, research R14-2·R14-11.

- 커버리지가 없으면 **최근 청크**(현지 어제에서 끝나는 2년)다 — 그 응답으로 첫 거래일을 안다
- 첫 날까지 거꾸로 **과거 구간** 청크다(첫 날에서 멈춘다)
- 커버리지 끝이 현지 어제보다 앞이면 **이어 받기**다 — 최근 5일을 겹쳐 받고, 오래 꺼져 있었으면
  2년씩 나눈다(U2)
- 차례: 최근 청크 → 이어 받기 → 과거 구간(지표마다 돌아가며) — 카드의 전일 종가가 곧 이력에서 나온다
"""

from __future__ import annotations

import datetime as dt
import inspect

from src.worker import market_runner
from src.worker.market_runner import IndicatorState, plan_round

D = dt.date
Y = D(2026, 10, 8)


def state(
    indicator_id: str,
    *,
    first: dt.date | None = None,
    cf: dt.date | None = None,
    ct: dt.date | None = None,
    yesterday: dt.date = Y,
) -> IndicatorState:
    return IndicatorState(
        indicator_id, first_day=first, covered_from=cf, covered_through=ct, yesterday=yesterday
    )


def plan(*states: IndicatorState) -> list[tuple[str, str, dt.date, dt.date]]:
    return [
        (t.kind, t.indicator_id, t.start, t.end)
        for t in plan_round(states, chunk_days=730, overlap_days=5)
    ]


def test_커버리지가_없으면_최근_청크() -> None:
    assert plan(state("kospi")) == [("recent", "kospi", Y - dt.timedelta(days=729), Y)]


def test_첫_날까지_거꾸로_과거_구간() -> None:
    cf = D(2024, 10, 10)
    tasks = plan(state("kospi", first=D(1996, 12, 11), cf=cf, ct=Y))
    assert tasks[0] == ("older", "kospi", cf - dt.timedelta(days=730), cf - dt.timedelta(days=1))
    assert tasks[-1][2] == D(1996, 12, 11)
    assert all(kind == "older" for kind, *_ in tasks)
    for (_, _, start, _), (_, _, _, next_end) in zip(tasks, tasks[1:], strict=False):
        assert next_end == start - dt.timedelta(days=1)  # 빈틈 없이 맞닿는다


def test_첫_날에_닿았으면_과거_구간이_없다() -> None:
    assert plan(state("kospi", first=D(1996, 12, 11), cf=D(1996, 12, 11), ct=Y)) == []


def test_이어_받기는_5일을_겹친다() -> None:
    ct = D(2026, 10, 5)
    assert plan(state("kospi", first=D(1996, 12, 11), cf=D(1996, 12, 11), ct=ct)) == [
        ("incremental", "kospi", D(2026, 10, 1), Y)
    ]


def test_같은_현지_날짜_안에서는_한_번뿐() -> None:
    assert plan(state("kospi", first=D(1996, 12, 11), cf=D(1996, 12, 11), ct=Y)) == []


def test_오래_꺼져_있었으면_2년씩_나눈다() -> None:
    ct = Y - dt.timedelta(days=1000)
    tasks = plan(state("kospi", first=D(1996, 12, 11), cf=D(1996, 12, 11), ct=ct))
    assert [k for k, *_ in tasks] == ["incremental", "incremental"]
    first, second = tasks
    assert first[2] == ct - dt.timedelta(days=4)
    assert (first[3] - first[2]).days + 1 == 730
    assert second[2] == first[3] + dt.timedelta(days=1) and second[3] == Y


def test_차례는_최근_청크_이어_받기_과거_구간_돌아가며() -> None:
    states = [
        state("kospi", first=D(2020, 1, 2), cf=D(2024, 10, 10), ct=Y),
        state("dow"),
        state("sp500", first=D(2020, 1, 2), cf=D(2024, 10, 10), ct=D(2026, 10, 1)),
        state("vix"),
    ]
    tasks = plan(*states)
    kinds = [k for k, *_ in tasks]
    assert kinds[:2] == ["recent", "recent"] and [t[1] for t in tasks[:2]] == ["dow", "vix"]
    assert tasks[2][:2] == ("incremental", "sp500")
    older = [t[1] for t in tasks[3:]]
    assert older[:4] == ["kospi", "sp500", "kospi", "sp500"]


def test_건너뛸_지표() -> None:
    tasks = plan_round(
        [state("kospi"), state("dow")], chunk_days=730, overlap_days=5, skip={"kospi"}
    )
    assert [t.indicator_id for t in tasks] == ["dow"]


def test_가드_글자를_쓰지_않는다() -> None:
    """`test_no_interpolation`이 `backfill` 글자를 찾는다 — 이름에 쓰지 않는다."""
    assert "backfill" not in inspect.getsource(market_runner)
