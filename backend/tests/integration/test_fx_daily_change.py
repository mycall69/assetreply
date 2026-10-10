"""외환 일자별 표의 등락 (014 반복 2026-10-10d T142) — FR-031, SC-016, contracts A9.

행마다 **바로 아래 행** 대비다 — 일 = 직전 고시일, 주·월 = 직전 대표값. 쪽의 마지막 행은 쪽 너머의
한 건과 견준다(아래로 더 받을 때마다 경계 행이 "—"가 되면 안 된다). 저장된 첫 고시는 `null`이다.
`/api/fx/latest`의 전일 대비는 같은 함수이고 응답이 그대로다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxRate
from src.db.session import get_session

TODAY = dt.date.today()

# 07-08·07-09·07-15·07-17은 고시 없음(휴장 사이), 07-06은 07-03과 같은 값(같음),
# 07-17(금) 결측이라 그 주의 대표는 07-16, 9월은 통째로 없다(월 단위에서 8월 → 오늘의 달)
FIXED = [
    ("2026-07-01", "1380.00"), ("2026-07-02", "1381.50"), ("2026-07-03", "1379.20"),
    ("2026-07-06", "1379.20"), ("2026-07-07", "1382.35"), ("2026-07-10", "1385.00"),
    ("2026-07-13", "1384.10"), ("2026-07-14", "1386.75"), ("2026-07-16", "1388.00"),
    ("2026-07-20", "1387.40"), ("2026-07-23", "1390.25"), ("2026-07-24", "1391.00"),
    ("2026-07-31", "1395.55"), ("2026-08-03", "1394.00"), ("2026-08-14", "1401.30"),
]
PROVISIONAL = "1410.00"


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal(rate), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False}
            for d, rate in FIXED
        ] + [
            # 오늘 고시 전 값 — 잠정 행도 바로 아래 행 대비다
            {"currency_code": "USD", "quote_date": TODAY,
             "base_rate": Decimal(PROVISIONAL), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": True},
        ])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _page(
    client: AsyncClient, period: str = "daily", *, limit: int = 200,
    before: str | None = None,
) -> dict[str, object]:
    params: dict[str, str | int] = {"currency": "USD", "period": period, "limit": limit}
    if before is not None:
        params["before"] = before
    response = await client.get("/api/fx/daily", params=params)
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def _expected(row: dict[str, object], below: dict[str, object]) -> dict[str, object]:
    """같은 두 행의 매매기준율로 계산한 값 — SC-016의 기준."""
    current = Decimal(str(row["baseRate"]))
    previous = Decimal(str(below["baseRate"]))
    delta = current - previous
    return {
        "comparedTo": below["date"],
        "absolute": str(delta),
        "percent": str((delta / previous * Decimal(100)).quantize(Decimal("0.01"))),
        "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
    }


def _rows(body: dict[str, object]) -> list[dict[str, object]]:
    rows = body["rows"]
    assert isinstance(rows, list)
    return rows


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
async def test_행마다_바로_아래_행_대비다(client: AsyncClient, period: str) -> None:
    rows = _rows(await _page(client, period))
    assert len(rows) >= 3
    for row, below in zip(rows, rows[1:], strict=False):
        assert row["change"] == _expected(row, below)


async def test_휴장_사이의_행은_직전_고시일_대비다(client: AsyncClient) -> None:
    """빈 날을 꾸미지 않는다 — 07-10은 07-07과 견준다(07-08·07-09 없음)."""
    by_date = {r["date"]: r for r in _rows(await _page(client))}
    change = by_date["2026-07-10"]["change"]
    assert isinstance(change, dict)
    assert change["comparedTo"] == "2026-07-07"
    flat = by_date["2026-07-06"]["change"]
    # 저장 정밀도(`Numeric(18, 6)`) 그대로 — 화면이 `formatRate`로 두 자리를 보인다
    assert flat == {"comparedTo": "2026-07-03", "absolute": "0.000000", "percent": "0.00",
                    "direction": "flat"}


async def test_주_행은_대표일의_하루_전이_아니라_직전_주의_대표값_대비다(
        client: AsyncClient) -> None:
    by_date = {r["date"]: r for r in _rows(await _page(client, "weekly"))}
    change = by_date["2026-07-24"]["change"]
    assert isinstance(change, dict)
    assert change["comparedTo"] == "2026-07-16"  # 07-23(하루 전)이 아니다


async def test_월_행은_직전_달의_대표값_대비다(client: AsyncClient) -> None:
    by_date = {r["date"]: r for r in _rows(await _page(client, "monthly"))}
    change = by_date["2026-08-14"]["change"]
    assert isinstance(change, dict)
    assert change["comparedTo"] == "2026-07-31"  # 08-03(하루 전 고시)이 아니다


@pytest.mark.parametrize(("period", "limit"), [("daily", 4), ("weekly", 2), ("monthly", 1)])
async def test_쪽의_마지막_행도_쪽_너머_한_건과_견준다(
        client: AsyncClient, period: str, limit: int) -> None:
    """아래로 더 받기 전에도 경계 행에 값이 있다 — 다음 쪽의 첫 행이 비교 대상이다."""
    first = await _page(client, period, limit=limit)
    assert first["hasMore"] is True
    last = _rows(first)[-1]
    second = await _page(client, period, limit=limit, before=str(first["oldestReturned"]))
    assert last["change"] == _expected(last, _rows(second)[0])


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
async def test_저장된_첫_고시는_null이다(client: AsyncClient, period: str) -> None:
    """키는 늘 있다 — "확인했고 없다"(`isOngoing`과 같은 규약). 0으로 메우지 않는다."""
    body = await _page(client, period)
    assert body["hasMore"] is False
    rows = _rows(body)
    assert all("change" in r for r in rows)
    assert rows[-1]["date"] == "2026-07-01" or period != "daily"
    assert rows[-1]["change"] is None


async def test_잠정_행도_바로_아래_행_대비이고_잠정_표시는_그대로다(
        client: AsyncClient) -> None:
    rows = _rows(await _page(client))
    top = rows[0]
    assert top["date"] == TODAY.isoformat()
    assert top["isProvisional"] is True
    assert top["change"] == _expected(top, rows[1])


async def test_요약_칸의_전일_대비는_그대로이고_표의_맨_위_행과_같은_글자다(
        client: AsyncClient) -> None:
    """`/api/fx/latest`는 잠정 값을 직전 **확정** 값과 견준다(001) — 여기서는 08-14다."""
    latest = (await client.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert latest["change"] == {
        "comparedTo": "2026-08-14", "absolute": "8.700000", "percent": "0.62",
        "direction": "up",
    }
    top = _rows(await _page(client))[0]
    assert top["change"] == latest["change"]
