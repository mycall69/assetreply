"""Npay 부동산 단지 화면 주소 (010 반복 3, T062) — FR-029, SC-010, contracts/rest-api `GET
/api/realestate/complexes/{complexId}/naver`.

가짜 클라이언트(출처 응답 형식을 모르는 후보 목록)로 경로 전체(단지 → 법정동 이름 → 검색어 → 고르기
→ 저장)를 돈다 — 네트워크 없음(원칙 III).

- 찾음 → 저장하고 `https://fin.land.naver.com/complexes/{번호}`. **두 번째 요청에는 출처를 부르지
  않는다**(저장한 번호)
- 못 찾음 → 저장. `NAVER_LAND_RECHECK_DAYS` 안에는 다시 부르지 않고, 지나면 다시 찾는다
- 실패(차단·요청 제한·연결·형식) → `failed` + 사유, **저장하지 않는다** — 일시 장애 하나로 그 단지가
  영영 검색으로만 열리지 않게
- 같은 법정동 후보가 없으면 단지명만으로 한 번 더 찾는다
- 합쳐진 단지는 합쳐 받은 단지로 찾는다. 모르는 단지는 400 `unknown_complex`(009와 같다)
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.services import apt_naver_link, realestate_lists
from src.config.settings import load_settings
from src.db.models import AptComplex, AptComplexNaver, AptRegion
from src.db.session import get_session
from src.ingestion.naver_land.client import ComplexSearchFetch
from src.ingestion.naver_land.errors import NaverLandBlocked, NaverLandRateLimited
from src.ingestion.naver_land.parse import NaverComplexCandidate

GARAK = "1171010700"
NOW = dt.datetime(2026, 10, 6, 3, 0, 0)
SETTINGS = dataclasses.replace(load_settings(), naver_land_recheck_days=30)


def helio(umd: str = GARAK) -> NaverComplexCandidate:
    return NaverComplexCandidate(
        number=111515, name="헬리오시티", legal_division_code=umd, type="A01"
    )


class FakeNaver:
    """검색어마다 정해 둔 답(후보 목록 또는 예외). 받은 검색어를 기록한다."""

    def __init__(self, answers: dict[str, list[NaverComplexCandidate] | Exception]) -> None:
        self.answers = answers
        self.keywords: list[str] = []

    async def search_complexes(self, keyword: str) -> ComplexSearchFetch:
        self.keywords.append(keyword)
        answer = self.answers.get(keyword, [])
        if isinstance(answer, Exception):
            raise answer
        return ComplexSearchFetch(
            keyword=keyword, candidates=answer, raw=f'{{"keyword": "{keyword}"}}', status=200
        )


@pytest.fixture
async def seeded(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        s.add(
            AptRegion(
                code=GARAK,
                level="umd",
                parent_code="1171000000",
                lawd_cd="11710",
                name="가락동",
                full_name="서울특별시 송파구 가락동",
                source="test",
                ingested_at=NOW,
                seen_at=NOW,
            )
        )
        helio_row = AptComplex(umd_code=GARAK, lawd_cd="11710", name="헬리오시티아파트")
        mirung_row = AptComplex(umd_code=GARAK, lawd_cd="11710", name="가락미륭아파트")
        s.add_all([helio_row, mirung_row])
        await s.flush()
        merged = AptComplex(
            umd_code=GARAK, lawd_cd="11710", name="헬리오시티", merged_into=helio_row.id
        )
        s.add(merged)
        await s.commit()
        return {"helio": helio_row.id, "mirung": mirung_row.id, "merged": merged.id}


@pytest.fixture
def now() -> list[dt.datetime]:
    return [NOW]


def make_client(session_factory, fake: FakeNaver, now: list[dt.datetime]):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[realestate_lists.get_realestate_now] = lambda: now[0]
    app.dependency_overrides[realestate_lists.get_realestate_settings] = lambda: SETTINGS
    app.dependency_overrides[apt_naver_link.get_naver_land_client] = lambda: fake
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def link(http: AsyncClient, complex_id: int) -> dict:  # type: ignore[type-arg]
    response = await http.get(f"/api/realestate/complexes/{complex_id}/naver")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def stored(session_factory, complex_id: int) -> AptComplexNaver | None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return (
            await s.execute(select(AptComplexNaver).where(AptComplexNaver.complex_id == complex_id))
        ).scalar_one_or_none()


async def test_찾으면_저장하고_다음에는_출처를_부르지_않는다(session_factory, seeded, now) -> None:  # type: ignore[no-untyped-def]
    fake = FakeNaver({"가락동 헬리오시티": [helio(), helio("4128112000")]})
    async with make_client(session_factory, fake, now) as http:
        first = await link(http, seeded["helio"])
        second = await link(http, seeded["helio"])
    assert first == {
        "complexId": seeded["helio"],
        "status": "found",
        "url": "https://fin.land.naver.com/complexes/111515",
        "reason": None,
    }
    assert second == first
    assert fake.keywords == ["가락동 헬리오시티"]  # 두 번째는 저장한 번호
    row = await stored(session_factory, seeded["helio"])
    assert row is not None
    assert (row.status, row.naver_complex_no, row.naver_name, row.keyword, row.source) == (
        "found",
        111515,
        "헬리오시티",
        "가락동 헬리오시티",
        "naver_land_autocomplete",
    )
    assert row.raw_response == '{"keyword": "가락동 헬리오시티"}'
    assert row.checked_at == NOW


async def test_못_찾음은_저장하고_정해진_날_수가_지나면_다시_찾는다(
    session_factory, seeded, now
) -> None:  # type: ignore[no-untyped-def]
    fake = FakeNaver({})  # 두 검색어 모두 빈 결과
    async with make_client(session_factory, fake, now) as http:
        assert (await link(http, seeded["mirung"]))["status"] == "not_found"
        assert fake.keywords == [
            "가락동 가락미륭",
            "가락미륭",
        ]  # 같은 법정동 후보가 없어 단지명만으로 한 번 더
        now[0] = NOW + dt.timedelta(days=29)
        assert (await link(http, seeded["mirung"])) == {
            "complexId": seeded["mirung"],
            "status": "not_found",
            "url": None,
            "reason": None,
        }
        assert len(fake.keywords) == 2  # 30일 안 — 다시 부르지 않는다
        fake.answers["가락동 가락미륭"] = [NaverComplexCandidate(596, "미륭", GARAK, "A04")]
        now[0] = NOW + dt.timedelta(days=31)
        again = await link(http, seeded["mirung"])
    assert (again["status"], again["url"]) == ("found", "https://fin.land.naver.com/complexes/596")
    row = await stored(session_factory, seeded["mirung"])
    assert row is not None and (row.status, row.naver_complex_no, row.checked_at) == (
        "found",
        596,
        NOW + dt.timedelta(days=31),
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [(NaverLandRateLimited("요청 제한"), "rate_limited"), (NaverLandBlocked("차단"), "blocked")],
)
async def test_실패는_저장하지_않고_다음_요청에서_다시_찾는다(  # type: ignore[no-untyped-def]
    session_factory, seeded, now, error: Exception, reason: str
) -> None:
    fake = FakeNaver({"가락동 헬리오시티": error})
    async with make_client(session_factory, fake, now) as http:
        failed = await link(http, seeded["helio"])
        assert failed == {
            "complexId": seeded["helio"],
            "status": "failed",
            "url": None,
            "reason": reason,
        }
        assert await stored(session_factory, seeded["helio"]) is None
        fake.answers["가락동 헬리오시티"] = [helio()]
        found = await link(http, seeded["helio"])
    assert found["status"] == "found"
    assert fake.keywords == ["가락동 헬리오시티", "가락동 헬리오시티"]


async def test_같은_법정동_후보가_없으면_단지명만으로_찾는다(session_factory, seeded, now) -> None:  # type: ignore[no-untyped-def]
    fake = FakeNaver(
        {"가락동 헬리오시티": [helio("4128112000")], "헬리오시티": [helio("4128112000"), helio()]}
    )
    async with make_client(session_factory, fake, now) as http:
        got = await link(http, seeded["helio"])
    assert (got["status"], fake.keywords) == ("found", ["가락동 헬리오시티", "헬리오시티"])


async def test_합쳐진_단지는_합쳐_받은_단지로_찾는다(session_factory, seeded, now) -> None:  # type: ignore[no-untyped-def]
    fake = FakeNaver({"가락동 헬리오시티": [helio()]})
    async with make_client(session_factory, fake, now) as http:
        merged = await link(http, seeded["merged"])
        main = await link(http, seeded["helio"])
    assert (merged["complexId"], merged["url"]) == (
        seeded["merged"],
        "https://fin.land.naver.com/complexes/111515",
    )
    assert main["url"] == merged["url"]
    assert fake.keywords == ["가락동 헬리오시티"]  # 합쳐 받은 단지 한 행으로 저장
    assert await stored(session_factory, seeded["merged"]) is None


async def test_모르는_단지는_400이다(session_factory, seeded, now) -> None:  # type: ignore[no-untyped-def]
    async with make_client(session_factory, FakeNaver({}), now) as http:
        response = await http.get("/api/realestate/complexes/999999/naver")
    assert response.status_code == 400
    assert response.json()["status"] == "unknown_complex"
