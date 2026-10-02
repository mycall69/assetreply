"""키움·목록 설정 (T001) — 006 data-model 7절, FR-060, FR-063.

헌법 원칙 II: 호출 한도·재시도·간격은 코드가 아니라 설정으로 선언하고, 인증 정보는
환경변수로만 주입한다.

**실제 `.env`의 영향을 끊는다.** 테스트 `conftest`가 저장소 루트 `.env`를 환경변수로 올리므로,
그대로 두면 기본값 검사가 실제 키·모드에 따라 통과하거나 실패한다.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.config.settings import load_settings

KEYS = (
    "KIWOOM_MODE", "KIWOOM_APP_KEY", "KIWOOM_APP_SECRET",
    "KIWOOM_US_PAGE_DELAY_SECONDS", "KIWOOM_KR_PAGE_DELAY_SECONDS",
    "KIWOOM_MAX_RETRIES", "LISTING_RETRY_INTERVAL_MINUTES",
    "LISTING_MAX_ATTEMPTS_PER_DAY", "LISTING_SHRINK_THRESHOLD",
    "LISTING_LOCK_STALE_MINUTES",
)

#: 존재하지 않는 파일 — 실제 `.env`를 읽지 않게 한다.
NO_ENV = Path("/nonexistent/.env")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ECOS_API_KEY", "test-key")
    return monkeypatch


class Test기본값:
    def test_data_model_7절의_기본값(self, clean_env: pytest.MonkeyPatch) -> None:
        s = load_settings(NO_ENV)
        assert s.kiwoom_mode == "real"
        assert s.kiwoom_us_page_delay_seconds == 12
        assert s.kiwoom_kr_page_delay_seconds == 1
        assert s.kiwoom_max_retries == 3
        assert s.listing_retry_interval_minutes == 30
        assert s.listing_max_attempts_per_day == 5
        assert s.listing_lock_stale_minutes == 10

    def test_축소_임계값은_Decimal이다(self, clean_env: pytest.MonkeyPatch) -> None:
        """금융 값은 아니지만 금융 계층의 float 정적 검사를 예외 없이 지키려고 Decimal로 읽는다."""
        threshold = load_settings(NO_ENV).listing_shrink_threshold
        assert isinstance(threshold, Decimal)
        assert threshold == Decimal("0.5")

    def test_키가_없으면_빈_값이다(self, clean_env: pytest.MonkeyPatch) -> None:
        """키가 없어도 기동은 된다 — 목록 갱신만 `never`·`auth_missing`이 된다 (FR-028a)."""
        s = load_settings(NO_ENV)
        assert s.kiwoom_app_key.reveal() == ""
        assert s.kiwoom_app_secret.reveal() == ""
        assert s.kiwoom_credentials_present is False


class Test환경변수:
    def test_값을_바꿀_수_있다(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("KIWOOM_MODE", "mock")
        clean_env.setenv("KIWOOM_US_PAGE_DELAY_SECONDS", "20")
        clean_env.setenv("LISTING_SHRINK_THRESHOLD", "0.7")
        s = load_settings(NO_ENV)
        assert s.kiwoom_mode == "mock"
        assert s.kiwoom_us_page_delay_seconds == 20
        assert s.listing_shrink_threshold == Decimal("0.7")

    def test_모드가_real_mock이_아니면_기동을_거절한다(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        """조용히 기본값으로 떨어뜨리면, 모의 키로 실전 도메인을 부르게 된다."""
        clean_env.setenv("KIWOOM_MODE", "prod")
        with pytest.raises(ValueError, match="KIWOOM_MODE"):
            load_settings(NO_ENV)

    @pytest.mark.parametrize("raw", ["0", "1.5", "-0.1", "반"])
    def test_축소_임계값은_0과_1_사이여야_한다(
        self, clean_env: pytest.MonkeyPatch, raw: str
    ) -> None:
        clean_env.setenv("LISTING_SHRINK_THRESHOLD", raw)
        with pytest.raises(ValueError, match="LISTING_SHRINK_THRESHOLD"):
            load_settings(NO_ENV)


class Test비밀:
    def test_키와_시크릿이_repr_str에_드러나지_않는다(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        """설정 객체를 로그나 예외에 찍었을 때 인증 정보가 새면 안 된다 (FR-060)."""
        clean_env.setenv("KIWOOM_APP_KEY", "app-key-SENTINEL-1234")
        clean_env.setenv("KIWOOM_APP_SECRET", "app-secret-SENTINEL-5678")
        s = load_settings(NO_ENV)
        for text in (repr(s), str(s)):
            assert "SENTINEL" not in text
        assert s.kiwoom_app_key.reveal() == "app-key-SENTINEL-1234"
        assert s.kiwoom_credentials_present is True

    def test_한쪽만_있으면_인증_정보가_없는_것이다(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        clean_env.setenv("KIWOOM_APP_KEY", "only-key")
        assert load_settings(NO_ENV).kiwoom_credentials_present is False
