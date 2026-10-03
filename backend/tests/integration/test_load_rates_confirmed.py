"""평가·환전에는 확정 환율만 (T005) — 007 FR-035, research R7-8, analyze C1, 헌법 원칙 V.

헌법 원칙 V: "잠정값을 계산·비교·시뮬레이션의 입력으로 사용하면 그 결과에도 잠정임이 드러나야
한다(MUST)." 005·006의 `load_rates`는 잠정 행까지 읽어, 날짜가 지났는데 아직 잠정인 환율이 계산에
들어가도 결과에 그 표시가 없었다. **확정 환율만 읽으면** 잠정만 있는 날은 `resolve_rate`가 가장
가까운 이전 확정일과 그 날짜를 돌려주고, 화면은 이미 그 날짜를 보인다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.stock_fx import load_rates
from src.db.dialect import upsert
from src.db.models import FxRate
from src.simulation.fx_convert import resolve_rate

D = dt.date.fromisoformat


async def test_잠정_행은_빼고_앞_확정일을_쓴다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": D("2021-09-01"), "base_rate": Decimal("1160"),
             "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": False},
            {"currency_code": "USD", "quote_date": D("2021-09-02"), "base_rate": Decimal("1999"),
             "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": True},
        ])
        await s.commit()
        lookup = await load_rates(s, "USD", D("2021-09-01"), D("2021-09-03"))
    assert D("2021-09-02") not in lookup.by_date
    assert resolve_rate(lookup, D("2021-09-02")) == (Decimal("1160.000000"), D("2021-09-01"))


async def test_확정_행은_그대로_읽는다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": D("2021-09-02"), "base_rate": Decimal("1165"),
             "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": False}])
        await s.commit()
        lookup = await load_rates(s, "USD", D("2021-09-01"), D("2021-09-03"))
    assert resolve_rate(lookup, D("2021-09-02")) == (Decimal("1165.000000"), D("2021-09-02"))
