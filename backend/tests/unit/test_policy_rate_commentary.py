"""기준금리의 변화 까닭 (014 반복 2026-10-11d T204) — FR-042, SC-026, research R14-33, contracts
A16.

출처는 승인된 네이버 뉴스 포커스다(R14-17 — 분류만 다르다). 결정 날의 실측
본문(`fixtures/policy_rate/focus_*`)을 쓴다 — 네트워크 없음.

- 날짜는 최근 결정일(한국)과 다음 날, 분류 차례는 404(채권·선물) → 403(해외 증시) → 429(환율)
- 제목에 **그 은행 낱말과 금리 낱말이 둘 다** 있어야 한다 — 은행 낱말만인 "한은 총재 '환율 아직
  높아…'"는 고르지 않는다
- 결정의 발표 시각 30분 전 이후(모르면 결정일 한국 0시 이후)의 기사만, 최대 3개, 같은 제목은 한 번.
  게시 시각을 모르면 고르지 않는다
- 같은 (분류, 날짜)는 은행 사이에 한 번만 받는다. 은행마다 메모리 10분, 실패는 물러서기(지표 까닭과
  같다)
- 결정이 아직 없으면 `none`(받지 않는다). 0건 읽기(목록 표지 없음)는 `parse_empty` 실패다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from src.api.services.policy_rate_commentary import RateCommentaryService
from src.config.settings import load_settings
from src.ingestion.news.commentary import BANK_SIDS, CommentaryClient, matches_bank
from src.ingestion.news.errors import NewsRateLimited
from src.simulation.policy_rate import Bank, Decision, get_bank

FIX = Path(__file__).parents[1] / "contract" / "fixtures" / "policy_rate"
NOW = dt.datetime(2026, 10, 11, 9, 40, tzinfo=dt.UTC)  # 한국 18:40
EMPTY = json.dumps({"articles": []})
UTC = dt.UTC


def bank(bank_id: str) -> Bank:
    found = get_bank(bank_id)
    assert found is not None
    return found


class Http:
    """뉴스 포커스 본문 대역 — (분류, 날짜)마다 픽스처, 없으면 빈 목록."""

    def __init__(self, bodies: Mapping[tuple[str, str], str] | None = None) -> None:
        self.bodies = dict(bodies or {})
        self.calls: list[tuple[str, str]] = []
        self.fail: Exception | None = None

    async def get_text(
        self, url: str, *, params: Mapping[str, str] | None = None, accept_language: str
    ) -> str:
        assert url == load_settings().news_commentary_naver_url
        query = dict(params or {})
        self.calls.append((query["sid"], query["date"]))
        if self.fail is not None:
            raise self.fail
        return self.bodies.get((query["sid"], query["date"]), EMPTY)


class Decisions:
    def __init__(self, latest: dict[str, Decision]) -> None:
        self.latest_of = latest

    async def latest(self, bank_id: str) -> Decision | None:
        return self.latest_of.get(bank_id)


BOK = Decision(dt.date(2026, 8, 27), dt.datetime(2026, 8, 27, 1, 0, tzinfo=UTC), Decimal("3.00"))
FED = Decision(dt.date(2026, 9, 17), dt.datetime(2026, 9, 16, 18, 0, tzinfo=UTC), Decimal("4.00"))
BOE = Decision(dt.date(2026, 9, 17), dt.datetime(2026, 9, 17, 11, 0, tzinfo=UTC), Decimal("3.75"))


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def service(http: Http, latest: dict[str, Decision], *, clock=lambda: NOW):  # type: ignore[no-untyped-def]
    settings = dataclasses.replace(
        load_settings(), dashboard_commentary_cache_seconds=600, news_failure_cache_seconds=60,
        news_failure_cache_max_seconds=600)
    return RateCommentaryService(
        CommentaryClient(http, settings, clock=clock), Decisions(latest), settings, clock=clock)


class Test낱말:
    def test_은행_낱말과_금리_낱말이_둘_다(self) -> None:
        assert matches_bank("[속보]한은 금리 인상 결정에 찬물…7000피 탈환 다음으로", "bok")
        assert not matches_bank("한은 총재 \"환율 아직 높아…원화 좀 더 강해져야 바람직\"", "bok")
        assert not matches_bank("美 금리 인상에 환율 13.6원 급등…1382원 넘겨(상보)", "fed")
        assert matches_bank("매파 FOMC에 국고채 금리, 단기물 위주 약세…3년물 연 4.090%", "fed")
        assert matches_bank("[1보] ECB 금리 인상…예금금리 연 2.50%로 0.25%p↑", "ecb")
        assert not matches_bank("[1보] ECB 금리 인상…예금금리 연 2.50%로 0.25%p↑", "fed")

    def test_분류_차례(self) -> None:
        assert BANK_SIDS == ("404", "403", "429")


class Test고르기:
    async def test_결정_날의_그_은행_기사_셋(self) -> None:
        http = Http({
            ("404", "20260827"): fixture("focus_404_20260827.json"),
            ("429", "20260827"): fixture("focus_429_20260827.json"),
        })
        body = await service(http, {"bok": BOK}).body(bank("bok"))
        assert body["status"] == "ok"
        assert body["decisionDate"] == "2026-08-27"
        assert body["bank"] == "bok" and body["source"] == "네이버 증권"
        titles = [item["title"] for item in body["items"]]  # type: ignore[attr-defined]
        assert titles == [
            "[속보]한은 금리 인상 결정에 찬물…7000피 탈환 다음으로",
            "한은 '연속 인상'에도…증권가 \"점도표 쇼크없다\" 안도",
            "한은 ‘매파 충격’에 국고채 약세…3년물 금리 6.9bp 상승",
        ]
        first = body["items"][0]  # type: ignore[index]
        assert first["url"].startswith("https://n.news.naver.com/")
        assert first["publishedAt"] == "2026-08-27T06:34:15Z"
        # 결정일과 다음 날, 분류 차례
        assert http.calls[:2] == [("404", "20260827"), ("404", "20260828")]

    async def test_발표_전의_기사는_고르지_않는다(self) -> None:
        # 발표가 한국 16:00이었다면 기준은 15:30 — 14:48·10:42의 기사는 결정 전(전망)이라 빠지고
        # 15:34는 남는다
        late = dataclasses.replace(BOK, announced_at=dt.datetime(2026, 8, 27, 7, 0, tzinfo=UTC))
        http = Http({("404", "20260827"): fixture("focus_404_20260827.json")})
        body = await service(http, {"bok": late}).body(bank("bok"))
        published = [item["publishedAt"] for item in body["items"]]  # type: ignore[attr-defined]
        assert published == ["2026-08-27T06:34:15Z"]

    async def test_발표_시각_30분_전부터다(self) -> None:
        # 출처의 발표 시각은 어림이다 — 한은 10:00인데 결정 기사가 09:52(429, 실측). 그 기사와
        # 05:51의 전망 기사만 남긴 본문
        source = json.loads(fixture("focus_429_20260827.json"))
        keep = ("20260827095233", "20260827055100")
        source["articles"] = [a for a in source["articles"] if a["date"] in keep]
        assert len(source["articles"]) == 2
        http = Http({("429", "20260827"): json.dumps(source, ensure_ascii=False)})
        body = await service(http, {"bok": BOK}).body(bank("bok"))
        titles = [item["title"] for item in body["items"]]  # type: ignore[attr-defined]
        # 05:51 "오늘 기준금리 또 올릴까"는 전망이다
        assert titles == ["한은, 기준금리 3%로 연속 인상…물가 우려에 긴축 속도(종합)"]

    async def test_시각을_모르면_결정일_한국_0시부터(self) -> None:
        unknown = dataclasses.replace(BOK, announced_at=None)
        http = Http({("404", "20260827"): fixture("focus_404_20260827.json")})
        body = await service(http, {"bok": unknown}).body(bank("bok"))
        assert body["status"] == "ok"
        published = [item["publishedAt"] for item in body["items"]]  # type: ignore[attr-defined]
        assert all(p >= "2026-08-26T15:00:00Z" for p in published)

    async def test_다른_분류의_그_은행_기사(self) -> None:
        http = Http({("403", "20260910"): fixture("focus_403_20260910.json")})
        announced = dt.datetime(2026, 9, 10, 12, 15, tzinfo=UTC)
        ecb = Decision(dt.date(2026, 9, 10), announced, Decimal("2.65"))
        body = await service(http, {"ecb": ecb}).body(bank("ecb"))
        titles = [item["title"] for item in body["items"]]  # type: ignore[attr-defined]
        assert titles and all("ECB" in t or "유럽중앙은행" in t for t in titles)
        assert len(titles) <= 3

    async def test_기사가_없으면_none(self) -> None:
        body = await service(Http(), {"boe": BOE}).body(bank("boe"))
        assert body["status"] == "none"
        assert body["items"] == []
        assert body["decisionDate"] == "2026-09-17"

    async def test_결정이_없으면_받지_않고_none(self) -> None:
        http = Http()
        body = await service(http, {}).body(bank("fed"))
        assert body["status"] == "none" and body["decisionDate"] is None
        assert http.calls == []


class Test캐시:
    async def test_같은_분류_날짜는_은행_사이에_한_번(self) -> None:
        http = Http({("404", "20260917"): fixture("focus_404_20260917.json")})
        svc = service(http, {"fed": FED, "boe": BOE})
        await svc.body(bank("fed"))
        first = list(http.calls)
        await svc.body(bank("boe"))
        assert http.calls == first  # 같은 결정일(한국) — 다시 받지 않는다
        assert len(first) == len(set(first)) == 6

    async def test_은행마다_10분_기억한다(self) -> None:
        http = Http({("404", "20260827"): fixture("focus_404_20260827.json")})
        now = [NOW]
        svc = service(http, {"bok": BOK}, clock=lambda: now[0])
        await svc.body(bank("bok"))
        calls = len(http.calls)
        now[0] = NOW + dt.timedelta(seconds=599)
        await svc.body(bank("bok"))
        assert len(http.calls) == calls
        now[0] = NOW + dt.timedelta(seconds=601)
        await svc.body(bank("bok"))
        assert len(http.calls) > calls


class Test실패:
    async def test_출처_실패는_failed와_물러서기(self) -> None:
        http = Http()
        http.fail = NewsRateLimited("뉴스 출처가 요청을 제한했습니다(429).")
        svc = service(http, {"bok": BOK})
        body = await svc.body(bank("bok"))
        assert body["status"] == "failed"
        assert body["failure"]["reason"] == "rate_limited"  # type: ignore[index]
        assert body["failure"]["retryAfterSeconds"] == 60  # type: ignore[index]
        calls = len(http.calls)
        await svc.body(bank("bok"))
        assert len(http.calls) == calls

    async def test_0건_읽기는_parse_empty(self) -> None:
        http = Http({("404", "20260827"): json.dumps({"page": 1})})
        body = await service(http, {"bok": BOK}).body(bank("bok"))
        assert body["status"] == "failed"
        assert body["failure"]["reason"] == "parse_empty"  # type: ignore[index]


@pytest.mark.parametrize("bank_id", ["fed", "bok", "ecb", "boe", "boj"])
def test_다섯_은행_모두_낱말이_있다(bank_id: str) -> None:
    # 은행 낱말 없이는 어떤 제목도 고르지 않는다 — 금리 낱말만으로는 다른 은행 기사가 섞인다
    assert not matches_bank("금리 인상 동결 인하", bank_id)
