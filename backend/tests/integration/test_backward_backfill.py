"""역방향 백필 통합 테스트 (T116).

FR-002: 통화별로 출처가 실제로 제공하는 최초 고시일부터 축적한다.
FR-002a: 실제 최초 제공일은 수집 중 발견해 기록한다.

**왜 이 테스트가 필요한가**: 축적 시작일을 앞당기는 것만으로는 아무것도 고쳐지지 않는다.
`next_start_date()`는 재개를 위해 `covered_through + 1`을 돌려주므로, 이미 커버리지가
`[1995-01-01, 어제]`로 저장된 통화는 시작일을 1964로 바꿔도 계속 어제 다음날부터
수집한다. 앞쪽 미수집 구간을 인식하는 분기가 함께 있어야 한다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from src.db.models import Currency, FxCoverage
from src.ingestion.collector import collect_range, next_start_date

from .conftest import StubSource

# 출처가 1964년부터 제공하지만 과거에 1995년부터만 수집했던 상황을 재현한다
PROBE_START = dt.date(1964, 1, 1)
OLD_START = dt.date(1995, 1, 1)

QUOTES = {"USD": [
    ("1964-05-04", "255.00"),
    ("1970-03-02", "310.00"),
    ("1995-01-03", "788.70"),
    ("1996-06-03", "810.20"),
]}


async def _collect_old_range(session_factory) -> StubSource:
    """기존 상태 재현 — 1995~1996만 수집된 커버리지를 만든다."""
    src = StubSource(QUOTES)
    async with session_factory() as s:
        await collect_range(s, src, "USD", OLD_START, dt.date(1996, 12, 31),
                            chunk_days=365)
        await s.commit()
    return src


async def test_커버리지가_탐색_시작일보다_늦으면_앞_구간부터_시작한다(session_factory) -> None:
    """FR-002: 앞쪽이 비어 있으면 재개가 아니라 역방향 백필이 먼저다."""
    await _collect_old_range(session_factory)
    async with session_factory() as s:
        start = await next_start_date(s, "USD", default=PROBE_START)
    assert start == PROBE_START, (
        "커버리지가 탐색 시작일보다 늦게 시작하는데도 앞 구간을 채우지 않았다. "
        "이 분기가 없으면 시작일을 앞당겨도 과거는 영원히 수집되지 않는다."
    )


async def test_앞_구간이_채워지면_covered_from이_앞당겨진다(session_factory) -> None:
    """FR-002: 역방향 백필 결과가 커버리지에 반영되어야 한다."""
    src = await _collect_old_range(session_factory)
    async with session_factory() as s:
        start = await next_start_date(s, "USD", default=PROBE_START)
        await collect_range(s, src, "USD", start, OLD_START - dt.timedelta(days=1),
                            chunk_days=365)
        await s.commit()
        cov = (await s.execute(select(FxCoverage))).scalar_one()

    assert cov.covered_from == PROBE_START, "앞쪽으로 확장되지 않았다"
    assert cov.covered_through == dt.date(1996, 12, 31), "뒤쪽 커버리지가 유실됐다"


async def test_더_이른_최초제공일을_발견하면_갱신한다(session_factory) -> None:
    """FR-002a: 이미 기록된 값보다 이른 날짜를 찾으면 그것이 진짜 최초 제공일이다."""
    src = await _collect_old_range(session_factory)
    async with session_factory() as s:
        cur = (await s.execute(select(Currency).where(Currency.code == "USD"))).scalar_one()
        assert cur.first_available_date == dt.date(1995, 1, 3), "사전 조건이 어긋났다"

        start = await next_start_date(s, "USD", default=PROBE_START)
        await collect_range(s, src, "USD", start, OLD_START - dt.timedelta(days=1),
                            chunk_days=365)
        await s.commit()
        cur = (await s.execute(select(Currency).where(Currency.code == "USD"))).scalar_one()

    assert cur.first_available_date == dt.date(1964, 5, 4), (
        "더 이른 제공일을 발견했는데 갱신되지 않았다. "
        "`current is None`일 때만 기록하면 역방향 백필의 결과가 반영되지 않는다."
    )


async def test_앞_구간이_이미_채워져_있으면_평소대로_재개한다(session_factory) -> None:
    """FR-011 회귀 방지 — 역방향 분기가 정상 재개를 망가뜨리면 안 된다."""
    await _collect_old_range(session_factory)
    async with session_factory() as s:
        start = await next_start_date(s, "USD", default=OLD_START)
    assert start == dt.date(1997, 1, 1)
