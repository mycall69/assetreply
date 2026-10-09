"""대시보드 설정 (014 T007) — FR-006, FR-008, FR-019, FR-023, data-model 8, 헌법 원칙 II.

한도·재시도·캐시·요청 머리·출처 주소는 코드가 아니라 설정으로 선언한다(원칙 II). 값이 없으면
data-model 8 표의 기본값이고,
최솟값 아래는 기동을 거절한다(조용히 기본값으로 떨어뜨리지 않는다 — 기존 `_env_int` 관례).

**실제 `.env`의 영향을 끊는다** — 키를 지우고 없는 `.env` 경로로 읽는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import INVESTING_DEFAULT_USER_AGENT, load_settings

NO_ENV = Path("/nonexistent/.env")

#: data-model 8 표의 env 24개와 기본값.
DEFAULTS: dict[str, tuple[str, object]] = {
    "MARKET_SOURCE_BASE_URL": ("market_source_base_url", "https://query1.finance.yahoo.com"),
    "MARKET_CHUNK_DAYS": ("market_chunk_days", 730),
    "MARKET_CHUNK_DELAY_MS": ("market_chunk_delay_ms", 1500),
    "MARKET_COLLECT_INTERVAL_SECONDS": ("market_collect_interval_seconds", 1800),
    "MARKET_RECHECK_OVERLAP_DAYS": ("market_recheck_overlap_days", 5),
    "MARKET_RETRY_MAX_ATTEMPTS": ("market_retry_max_attempts", 4),
    "MARKET_RETRY_BASE_DELAY_MS": ("market_retry_base_delay_ms", 1000),
    "MARKET_REQUEST_TIMEOUT_SECONDS": ("market_request_timeout_seconds", 20),
    "MARKET_QUOTE_CACHE_SECONDS": ("market_quote_cache_seconds", 30),
    "MARKET_QUOTE_FAILURE_CACHE_SECONDS": ("market_quote_failure_cache_seconds", 10),
    "MARKET_DELAY_NOTICE_SECONDS": ("market_delay_notice_seconds", 180),
    "MARKET_HOLIDAY_DETECT_SECONDS": ("market_holiday_detect_seconds", 3600),
    "DASHBOARD_REFRESH_SECONDS": ("dashboard_refresh_seconds", 60),
    "DASHBOARD_SERIES_MAX_POINTS": ("dashboard_series_max_points", 30000),
    "YAHOO_MAX_CONCURRENT_REQUESTS": ("yahoo_max_concurrent_requests", 2),
    "NEWS_USER_AGENT": ("news_user_agent", INVESTING_DEFAULT_USER_AGENT),
    "NEWS_CACHE_SECONDS": ("news_cache_seconds", 600),
    "NEWS_FAILURE_CACHE_SECONDS": ("news_failure_cache_seconds", 60),
    "NEWS_FAILURE_CACHE_MAX_SECONDS": ("news_failure_cache_max_seconds", 600),
    "NEWS_REQUEST_TIMEOUT_SECONDS": ("news_request_timeout_seconds", 10),
    "NEWS_RETRY_MAX_ATTEMPTS": ("news_retry_max_attempts", 2),
    "NEWS_KR_URL": ("news_kr_url", "https://stock.naver.com/api/domestic/news/list"),
    "NEWS_US_URL": ("news_us_url", "https://finance.yahoo.com/topic/latest-news/"),
    "NEWS_JP_URL": ("news_jp_url", "https://finance.yahoo.co.jp/news/headline"),
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key in DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ECOS_API_KEY", "test-key")
    return monkeypatch


def test_env는_24개다() -> None:
    assert len(DEFAULTS) == 24


def test_값이_없으면_기본값(clean_env: pytest.MonkeyPatch) -> None:
    s = load_settings(NO_ENV)
    for key, (field, default) in DEFAULTS.items():
        assert getattr(s, field) == default, key


def test_값을_주면_그_값(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("MARKET_CHUNK_DAYS", "365")
    clean_env.setenv("MARKET_QUOTE_CACHE_SECONDS", "15")
    clean_env.setenv("DASHBOARD_SERIES_MAX_POINTS", "500")
    clean_env.setenv("YAHOO_MAX_CONCURRENT_REQUESTS", "1")
    clean_env.setenv("NEWS_US_URL", "http://localhost:9/none")
    clean_env.setenv("MARKET_HOLIDAY_DETECT_SECONDS", "600")
    s = load_settings(NO_ENV)
    assert (s.market_chunk_days, s.market_quote_cache_seconds, s.dashboard_series_max_points) == (
        365,
        15,
        500,
    )
    assert s.yahoo_max_concurrent_requests == 1
    assert s.news_us_url == "http://localhost:9/none"
    assert s.market_holiday_detect_seconds == 600


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MARKET_CHUNK_DAYS", "0"),
        ("YAHOO_MAX_CONCURRENT_REQUESTS", "0"),
        ("DASHBOARD_SERIES_MAX_POINTS", "1"),
        ("DASHBOARD_REFRESH_SECONDS", "0"),
        ("NEWS_RETRY_MAX_ATTEMPTS", "0"),
        ("MARKET_QUOTE_CACHE_SECONDS", "x"),
    ],
)
def test_최솟값_아래와_형식_오류는_거절(
    clean_env: pytest.MonkeyPatch, key: str, value: str
) -> None:
    clean_env.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        load_settings(NO_ENV)


def test_뉴스_UA를_비우면_빈_문자열(clean_env: pytest.MonkeyPatch) -> None:
    """007 관례 — 비우면 aiohttp 기본 UA가 나가 차단 경로를 재현할 수 있다."""
    clean_env.setenv("NEWS_USER_AGENT", "")
    assert load_settings(NO_ENV).news_user_agent == ""
