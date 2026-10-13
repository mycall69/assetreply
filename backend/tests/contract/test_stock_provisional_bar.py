"""시세 출처가 아직 확정하지 않은 봉 (버그 stock-provisional-bar) — 005 FR-012·FR-044, 헌법 원칙
II·III·V.

출처의 일봉 응답은 가장 최근 거래일을 아직 일봉으로 굳히지 않았을 때 **마지막 거래 시각의 봉**을
붙인다(시각 = 그 응답의 마지막 거래 시각 — 확정 일봉의 개장 시각이 아니다). 장중이면 그때까지의
값이고, 출처 자료가 늦으면 시가·고가·저가가 0이다. 이것을 일봉으로 저장하면 틀린 값이 남는다. 수집이
그날을 받은 구간에 넣으면 출처가 나중에 바로잡아도 다시 받지 않는다(실측: 삼성전자 2026-10-06 시가
0, NVDA 2026-10-08 종가 = 11:23 EDT의 현재가).

어댑터는 잠정 봉의 행을 만들지 않고 그 첫 날을 알린다. 확정 봉 자리의 0 이하 가격은 출처의 빈 값이다
— 행을 만들지 않고(0으로 채우지 않는다) 잠정도 아니다. 픽스처는 개발 DB에 보관한 원본 응답 본문
그대로다(주소·머리 없음 — README).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo

from src.config.settings import load_settings
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.parse import parse_chart

FIXTURES = Path(__file__).parent / "fixtures" / "stock"
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
D = dt.date.fromisoformat

#: 원본을 받은 시각(개발 DB `stock_raw_response.received_at`, 한국 시각).
ZERO_RECEIVED = dt.datetime(2026, 10, 7, 3, 21, 55, tzinfo=KST)
INTRADAY_RECEIVED = dt.datetime(2026, 10, 9, 0, 23, 41, tzinfo=KST)  # = 10-08 11:23:41 EDT
AFTER_CLOSE_RECEIVED = dt.datetime(2026, 10, 9, 0, 19, 15, tzinfo=KST)


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load(name: str) -> object:
    return json.loads(text(name))


class Test마지막_거래_시각_봉:
    def test_시가가_0이면_행이_없고_잠정이다(self) -> None:
        """삼성전자 2026-10-06 — 시가·고가·저가·거래량 0, 종가만 있다.

        저장하면 그날 산 주식의 단가가 0이다."""
        data = parse_chart(load("chart_live_zero_005930_KS.json"), now=ZERO_RECEIVED)
        assert data.prices == []
        assert data.provisional_from == D("2026-10-06")

    def test_시각을_몰라도_0_봉은_잠정이다(self) -> None:
        """0 봉 판정은 지금 시각과 상관없다 — 출처가 아직 값을 주지 않은 것이다."""
        data = parse_chart(load("chart_live_zero_005930_KS.json"))
        assert data.prices == []
        assert data.provisional_from == D("2026-10-06")

    def test_장중에_받은_봉은_행이_없고_잠정이다(self) -> None:
        """NVDA 2026-10-08 — 11:23 EDT의 현재가(236.08)가 종가 자리에 있다.

        확정 종가는 230.48이다."""
        data = parse_chart(load("chart_live_intraday_NVDA.json"), now=INTRADAY_RECEIVED)
        assert data.prices == []
        assert data.provisional_from == D("2026-10-08")

    def test_장_전에_받은_오늘_봉도_잠정이다(self) -> None:
        now = dt.datetime(2026, 10, 8, 9, 0, tzinfo=NY)
        data = parse_chart(load("chart_live_intraday_NVDA.json"), now=now)
        assert data.provisional_from == D("2026-10-08")

    def test_세션이_끝난_뒤의_응답이면_확정이다(self) -> None:
        """규칙의 경계 — 같은 봉이라도 그 거래일의 정규 세션이 끝난 뒤(16:00 EDT)에 받았으면
        확정으로 읽는다."""
        now = dt.datetime(2026, 10, 8, 16, 0, tzinfo=NY)
        data = parse_chart(load("chart_live_intraday_NVDA.json"), now=now)
        assert [p.quote_date for p in data.prices] == [D("2026-10-08")]
        assert data.provisional_from is None

    def test_마감_뒤에_받은_봉은_확정이다(self) -> None:
        """삼성전자 2026-10-08 — 15:32 KST의 마지막 거래 시각 봉이다.

        값이 출처 확정값과 같다(2026-10-13 실측)."""
        body = load("chart_live_after_close_005930_KS.json")
        data = parse_chart(body, now=AFTER_CLOSE_RECEIVED)
        assert [(p.quote_date, p.open_raw, p.close_raw) for p in data.prices] == [
            (D("2026-10-08"), Decimal("269500.0"), Decimal("262000.0"))]
        assert data.provisional_from is None

    def test_시각을_주지_않으면_세션을_가리지_않는다(self) -> None:
        """시각 없이 부르는 쪽(기존 해석 호출)은 그대로다.

        수집 경로의 클라이언트는 늘 시각을 넘긴다."""
        data = parse_chart(load("chart_live_intraday_NVDA.json"))
        assert [p.quote_date for p in data.prices] == [D("2026-10-08")]
        assert data.provisional_from is None


#: 미국 개장 1분 전(2026-10-13 22:29:57 KST = 09:29:57 EDT)에 10-13 하루를 요청한 응답(원본 id
#: 1042). 10-13 봉이 없고 10-12 마감 봉 하나다.
PREOPEN_RECEIVED = dt.datetime(2026, 10, 13, 22, 29, 57, tzinfo=KST)


class Test세션이_끝나지_않은_요청일:
    def test_봉이_없어도_그날은_잠정이다(self) -> None:
        """출처가 그날 봉을 아직 주지 않았다.

        받은 구간에 넣으면 장이 끝난 뒤에도 다시 받지 않는다(실측)."""
        data = parse_chart(load("chart_preopen_NVDA.json"), now=PREOPEN_RECEIVED,
                           requested_to=D("2026-10-13"))
        assert [p.quote_date for p in data.prices] == [D("2026-10-12")]
        assert data.provisional_from == D("2026-10-13")

    def test_끝난_날만_요청했으면_잠정이_없다(self) -> None:
        data = parse_chart(load("chart_preopen_NVDA.json"), now=PREOPEN_RECEIVED,
                           requested_to=D("2026-10-12"))
        assert data.provisional_from is None

    def test_마감_뒤에는_오늘도_끝난_날이다(self) -> None:
        now = dt.datetime(2026, 10, 13, 16, 0, tzinfo=NY)
        data = parse_chart(load("chart_preopen_NVDA.json"), now=now, requested_to=D("2026-10-13"))
        assert data.provisional_from is None

    def test_마감_뒤에는_다음_날부터가_잠정이다(self) -> None:
        now = dt.datetime(2026, 10, 13, 16, 0, tzinfo=NY)
        data = parse_chart(load("chart_preopen_NVDA.json"), now=now, requested_to=D("2026-10-14"))
        assert data.provisional_from == D("2026-10-14")

    def test_국내_종목의_어제는_끝난_날이다(self) -> None:
        """계산 끝 기본값(한국 날짜의 어제) — 국내 종목은 늘 끝난 세션이라 지금과 같다."""
        body = load("chart_live_after_close_005930_KS.json")
        data = parse_chart(body, now=AFTER_CLOSE_RECEIVED, requested_to=D("2026-10-08"))
        assert data.provisional_from is None


class Test확정_봉_자리의_0:
    def test_행이_없고_잠정도_아니다(self) -> None:
        """출처의 빈 값 자리다. 0으로 저장하지 않는다(원칙 V).

        다시 받아도 같으므로 다시 받지 않는다."""
        body = load("chart_full.json")
        quote = body["chart"]["result"][0]["indicators"]["quote"][0]  # type: ignore[index]
        quote["open"][1] = 0.0
        data = parse_chart(body, now=dt.datetime(2026, 10, 13, tzinfo=dt.UTC))
        assert [p.quote_date for p in data.prices] == [
            D("2021-08-02"), D("2021-08-04"), D("2021-12-29"), D("2022-03-30")]
        assert data.provisional_from is None

    def test_종가가_음수여도_같다(self) -> None:
        body = load("chart_full.json")
        quote = body["chart"]["result"][0]["indicators"]["quote"][0]  # type: ignore[index]
        quote["close"][0] = -1.0
        data = parse_chart(body)
        assert D("2021-08-02") not in [p.quote_date for p in data.prices]
        assert data.provisional_from is None


class Resp:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    def __init__(self, routes: dict[str, Resp]) -> None:
        self.routes = routes

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        return self.routes[(params or {})["interval"]]

    async def close(self) -> None:
        return None


async def test_클라이언트가_요청_끝을_넘긴다() -> None:
    session = Session({"1d": Resp(text("chart_preopen_NVDA.json")),
                       "1mo": Resp(text("chart_no_data_in_range.json"), 400)})
    settings = dataclasses.replace(load_settings(), stock_retry_max_attempts=1)
    now = PREOPEN_RECEIVED.astimezone(dt.UTC)
    async with YahooStockClient(settings, session=session, now=lambda: now) as yahoo:  # type: ignore[arg-type]
        fetched = await yahoo.fetch_chart("NVDA", D("2026-10-13"), D("2026-10-13"))
    assert fetched.data.provisional_from == D("2026-10-13")


async def test_클라이언트가_지금_시각으로_가른다() -> None:
    """클라이언트가 시각을 넘기지 않으면 장중 봉이 확정으로 저장된다 — 이 결함 그대로다."""
    session = Session({"1d": Resp(text("chart_live_intraday_NVDA.json")),
                       "1mo": Resp(text("chart_no_data_in_range.json"), 400)})
    settings = dataclasses.replace(load_settings(), stock_retry_max_attempts=1)
    now = INTRADAY_RECEIVED.astimezone(dt.UTC)
    async with YahooStockClient(settings, session=session, now=lambda: now) as yahoo:  # type: ignore[arg-type]
        fetched = await yahoo.fetch_chart("NVDA", D("2026-10-08"), D("2026-10-08"))
    assert fetched.data.prices == []
    assert fetched.data.provisional_from == D("2026-10-08")
    # 원본은 그대로 남긴다 — 무엇을 받았는지 되짚을 근거다.
    assert [r.kind for r in fetched.raws] == ["chart", "splits"]
