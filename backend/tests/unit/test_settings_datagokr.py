"""공공데이터포털·부동산 설정 (T009) — 009 FR-010, FR-012, FR-013, research R9-5, 헌법 원칙 II.

동시 수·자료별 하루 한도·재시도는 코드가 아니라 설정으로 선언한다. 인증키는 환경변수로만 받고 repr에
나오지 않는다.

**실거래 탐색 시작 달(`APT_TRADE_PROBE_START`)에는 코드 기본값이 없다** — 헌법은 시작일을 코드에
두지 못하게 한다(001 `ECOS_PROBE_FLOOR`와 같은 취지). 없으면 None이고, 앱은 뜨지만 실거래 수집이
사유와 함께 멈춘다(T024).

**실제 `.env`의 영향을 끊는다** — 테스트 `conftest`가 저장소 루트 `.env`를 환경변수로 올린다.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.config.settings import load_settings

KEYS = (
    "DATA_API_KEY", "DATA_API_MAX_CONCURRENT", "DATA_API_DAILY_LIMIT_TRADE",
    "DATA_API_DAILY_LIMIT_KAPT", "DATA_API_DAILY_LIMIT_REGION", "DATA_API_RETRY_MAX_ATTEMPTS",
    "DATA_API_RETRY_BASE_DELAY_MS",
    "APT_TRADE_PROBE_START", "APT_TRADE_PROVISIONAL_MONTHS", "APT_TRADE_DAILY_RECHECK_MONTHS",
    "APT_LIST_REFRESH_DAYS",
)
NO_ENV = Path("/nonexistent/.env")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ECOS_API_KEY", "test-key")
    return monkeypatch


def test_기본값(clean_env: pytest.MonkeyPatch) -> None:
    s = load_settings(NO_ENV)
    assert s.data_api_key.reveal() == ""
    assert s.data_api_max_concurrent == 3
    limits = (s.data_api_daily_limit_trade, s.data_api_daily_limit_kapt,
              s.data_api_daily_limit_region)
    assert limits == (9000, 4500, 9000)
    assert (s.data_api_retry_max_attempts, s.data_api_retry_base_delay_ms) == (4, 1000)
    assert s.apt_trade_probe_start is None
    assert (s.apt_trade_provisional_months, s.apt_trade_daily_recheck_months) == (12, 3)
    assert s.apt_list_refresh_days == 30


def test_값을_읽는다(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("DATA_API_KEY", "abcDEF1234567890xyz")
    clean_env.setenv("DATA_API_DAILY_LIMIT_TRADE", "20")
    clean_env.setenv("APT_TRADE_PROBE_START", "2005-01")
    clean_env.setenv("APT_TRADE_PROVISIONAL_MONTHS", "6")
    s = load_settings(NO_ENV)
    assert s.data_api_key.reveal() == "abcDEF1234567890xyz"
    assert s.data_api_daily_limit_trade == 20
    assert s.apt_trade_probe_start == dt.date(2005, 1, 1)
    assert s.apt_trade_provisional_months == 6


def test_인증키는_repr에_나오지_않는다(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("DATA_API_KEY", "abcDEF1234567890xyz")
    assert "abcDEF1234567890xyz" not in repr(load_settings(NO_ENV))


@pytest.mark.parametrize("raw", ["2005", "2005-13", "2005-01-01", "05-01"])
def test_탐색_시작_달은_YYYY_MM(clean_env: pytest.MonkeyPatch, raw: str) -> None:
    clean_env.setenv("APT_TRADE_PROBE_START", raw)
    with pytest.raises(ValueError, match="APT_TRADE_PROBE_START"):
        load_settings(NO_ENV)


@pytest.mark.parametrize(("key", "raw"), [
    ("DATA_API_MAX_CONCURRENT", "0"), ("DATA_API_DAILY_LIMIT_KAPT", "0"),
    ("DATA_API_RETRY_MAX_ATTEMPTS", "0"), ("APT_TRADE_PROVISIONAL_MONTHS", "0"),
    ("APT_LIST_REFRESH_DAYS", "0"),
])
def test_최솟값(clean_env: pytest.MonkeyPatch, key: str, raw: str) -> None:
    clean_env.setenv(key, raw)
    with pytest.raises(ValueError, match=key):
        load_settings(NO_ENV)


def test_매일_다시_받는_달은_잠정_기간_안이다(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("APT_TRADE_PROVISIONAL_MONTHS", "3")
    clean_env.setenv("APT_TRADE_DAILY_RECHECK_MONTHS", "4")
    with pytest.raises(ValueError, match="APT_TRADE_DAILY_RECHECK_MONTHS"):
        load_settings(NO_ENV)
