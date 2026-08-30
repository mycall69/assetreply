"""도메인 타입·오류 계층·오류 매핑 계약 테스트 (T023·T024·T025 보완).

contracts/ecos-adapter.md의 오류 분류표와 contracts/rest-api.md의 공통 오류표가
코드와 일치하는지 확인한다.
"""
import datetime as dt
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.errors import InvalidSpread, OutOfRange, UnknownCurrency
from src.api.main import create_app
from src.ingestion.ecos.errors import (
    ItemMappingChanged,
    SourceAuthError,
    SourceError,
    SourceRateLimited,
    SourceUnavailable,
)
from src.ingestion.protocols import DailyQuote, FetchOutcome, FetchResult, ItemMapping


class Test오류_재시도_정책:
    """contracts/ecos-adapter.md 오류 분류표의 '재시도' 열."""

    def test_인증_오류는_재시도하지_않는다(self) -> None:
        """INFO-100: 키 문제는 재시도해도 달라지지 않는다."""
        assert SourceAuthError().retryable is False

    def test_항목_매핑_변경은_재시도하지_않는다(self) -> None:
        """FR-015: 잘못된 통화의 값을 저장하느니 중단한다."""
        assert ItemMappingChanged().retryable is False

    def test_한도_초과는_재시도한다(self) -> None:
        """INFO-300: 지수 백오프 후 재시도 (FR-012)."""
        assert SourceRateLimited().retryable is True

    def test_응답_불가는_재시도한다(self) -> None:
        assert SourceUnavailable().retryable is True

    def test_모든_소스_오류가_공통_기반을_공유한다(self) -> None:
        for cls in (SourceAuthError, SourceRateLimited, SourceUnavailable, ItemMappingChanged):
            assert issubclass(cls, SourceError)


class Test도메인_타입:
    """헌법 원칙 II: 이 타입에 출처 고유 필드명이 없어야 한다."""

    def test_고시값은_Decimal이다(self) -> None:
        q = DailyQuote(dt.date(2005, 3, 15), Decimal("1012.30"), 1)
        assert isinstance(q.base_rate, Decimal)

    def test_고시값은_불변이다(self) -> None:
        q = DailyQuote(dt.date(2005, 3, 15), Decimal("1012.30"), 1)
        with pytest.raises((AttributeError, TypeError)):
            q.base_rate = Decimal("1")  # type: ignore[misc]

    def test_데이터없음은_오류가_아닌_결과다(self) -> None:
        """INFO-200은 정상 응답으로 취급한다."""
        r = FetchResult((), FetchOutcome.NO_DATA, "{}", 200, "INFO-200")
        assert r.outcome is FetchOutcome.NO_DATA
        assert r.quotes == ()

    def test_결과가_원본_응답을_보존한다(self) -> None:
        """FR-004a: 원본 응답을 보존한다."""
        r = FetchResult((), FetchOutcome.OK, '{"x":1}', 200, None)
        assert r.raw_body == '{"x":1}'
        assert r.raw_status == 200

    def test_항목_매핑_타입(self) -> None:
        m = ItemMapping("JPY", "0000002", "원/일본엔")
        assert (m.currency_code, m.source_item_code) == ("JPY", "0000002")


class Test오류_HTTP_매핑:
    """contracts/rest-api.md 공통 오류표."""

    @pytest.fixture
    def client(self) -> TestClient:
        app = create_app()

        @app.get("/_raise/{kind}")
        async def _raise(kind: str) -> None:
            raise {
                "out_of_range": OutOfRange,
                "unknown_currency": UnknownCurrency,
                "invalid_spread": InvalidSpread,
                "unavailable": SourceUnavailable,
                "rate_limited": SourceRateLimited,
                "auth": SourceAuthError,
                "mapping": ItemMappingChanged,
            }[kind]()

        return TestClient(app, raise_server_exceptions=False)

    @pytest.mark.parametrize(
        ("kind", "status", "code"),
        [
            ("out_of_range", 400, "out_of_range"),
            ("unknown_currency", 404, "unknown_currency"),
            ("invalid_spread", 422, "invalid_spread"),
            ("unavailable", 502, "source_unavailable"),
            ("auth", 502, "source_unavailable"),
            ("mapping", 502, "source_unavailable"),
            ("rate_limited", 503, "source_rate_limited"),
        ],
    )
    def test_도메인_오류가_계약된_상태코드로_매핑된다(
        self, client: TestClient, kind: str, status: int, code: str
    ) -> None:
        res = client.get(f"/_raise/{kind}")
        assert res.status_code == status
        assert res.json()["status"] == code

    def test_한도_초과_응답은_저장된_데이터가_유효함을_알린다(self, client: TestClient) -> None:
        """FR-013: 이미 저장된 데이터는 유효한 상태로 유지된다."""
        assert "유효" in client.get("/_raise/rate_limited").json()["message"]

    def test_헬스체크(self, client: TestClient) -> None:
        assert client.get("/health").json() == {"status": "ok"}


class Test세션_팩토리:
    async def test_엔진과_세션_수명주기(self) -> None:
        from src.db.session import get_session, init_engine, shutdown_engine

        init_engine()
        agen = get_session()
        session = await anext(agen)
        assert session is not None
        await agen.aclose()
        await shutdown_engine()
