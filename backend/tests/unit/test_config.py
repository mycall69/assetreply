"""설정 선언 모듈 테스트 (T010).

헌법 원칙 II에 따라 rate limit·재시도 정책·청크 크기는 코드가 아닌 설정으로 선언되어야 하며,
운영자가 환경변수로 조정할 수 있어야 한다. 인증키는 환경변수로만 주입된다.
"""
import datetime as dt

import pytest

from src.config.settings import Settings, load_settings


class Test기본값:
    """research R2가 정한 기본값이 그대로 적용되는지 확인한다."""

    def test_ecos_기본_설정값(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        s = load_settings()
        assert s.ecos_chunk_days == 365
        assert s.ecos_chunk_delay_ms == 1000
        assert s.ecos_max_concurrent_per_currency == 1
        assert s.ecos_max_concurrent_currencies == 3
        assert s.ecos_retry_max_attempts == 5
        assert s.ecos_retry_base_delay_ms == 1000

    def test_수집_및_이력_기본_설정값(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        s = load_settings()
        assert s.collection_sync_threshold_days == 30
        assert s.job_history_success_retention_days == 90

    def test_db_기본값(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        s = load_settings()
        assert s.db_host == "localhost"
        assert s.db_port == 3306


class Test환경변수_오버라이드:
    """운영자가 코드 수정 없이 값을 조정할 수 있어야 한다 (FR-009)."""

    def test_청크_크기_오버라이드(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_CHUNK_DAYS", "90")
        assert load_settings().ecos_chunk_days == 90

    def test_동기_임계값_오버라이드(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("COLLECTION_SYNC_THRESHOLD_DAYS", "7")
        assert load_settings().collection_sync_threshold_days == 7

    def test_숫자가_아닌_값은_거부한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_CHUNK_DAYS", "삼백육십오")
        with pytest.raises(ValueError):
            load_settings()

    def test_0_이하의_청크_크기는_거부한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_CHUNK_DAYS", "0")
        with pytest.raises(ValueError):
            load_settings()


class Test인증키:
    """헌법 원칙 II: 인증키는 환경변수로 주입되며 코드에 하드코딩하지 않는다."""

    def test_환경변수에서_인증키를_읽는다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "my-secret-key")
        assert load_settings().ecos_api_key == "my-secret-key"

    def test_인증키가_없으면_오류(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """실제 `.env`의 영향을 배제하기 위해 빈 경로를 주입한다."""
        monkeypatch.delenv("ECOS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ECOS_API_KEY"):
            load_settings(env_file=tmp_path / "absent.env")

    def test_설정을_문자열로_출력해도_인증키가_노출되지_않는다(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "super-secret-value")
        s = load_settings()
        assert "super-secret-value" not in repr(s)
        assert "super-secret-value" not in str(s)


def test_설정은_불변이다(monkeypatch: pytest.MonkeyPatch) -> None:
    """설정이 런타임에 바뀌면 재현성이 깨진다 (헌법 원칙 V)."""
    monkeypatch.setenv("ECOS_API_KEY", "test-key")
    s = load_settings()
    with pytest.raises((AttributeError, TypeError)):
        s.ecos_chunk_days = 1  # type: ignore[misc]


def test_Settings_타입이_공개되어_있다() -> None:
    """의존성 주입을 위해 타입이 임포트 가능해야 한다 (헌법 원칙 IV)."""
    assert Settings is not None


class Test커넥션풀_설정:
    """헌법 v4.0.0: 풀 크기와 타임아웃은 설정값으로 선언해야 한다(MUST)."""

    def test_풀_기본값(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        s = load_settings()
        assert s.db_pool_size > 0
        assert s.db_max_overflow >= 0
        assert s.db_pool_timeout_seconds > 0

    def test_풀_크기_오버라이드(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("DB_POOL_SIZE", "20")
        assert load_settings().db_pool_size == 20

    def test_풀_타임아웃_오버라이드(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", "45")
        assert load_settings().db_pool_timeout_seconds == 45

    def test_음수_풀_크기는_거부한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("DB_POOL_SIZE", "-1")
        with pytest.raises(ValueError):
            load_settings()

    def test_비동기_연결_URL을_만든다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """헌법 원칙 I: DB 접근은 비동기 ORM 세션."""
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        url = load_settings().database_url
        assert url.startswith("mysql+aiomysql://")
        assert "charset=utf8mb4" in url

    def test_연결_URL에_비밀번호가_있어도_repr에는_노출되지_않는다(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("DB_PASSWORD", "super-secret-db-pw")
        s = load_settings()
        assert "super-secret-db-pw" in s.database_url
        assert "super-secret-db-pw" not in repr(s)


class Test탐색_시작일:
    """헌법 v4.1.0: 축적 시작일을 코드에 하드코딩해서는 안 된다(MUST NOT).

    FR-002·FR-009: 통화별 탐색 시작일은 운영자가 조정 가능한 설정값이어야 한다.
    여기 값은 탐색 시작점일 뿐이며, 실제 최초 제공일은 수집 중 발견해 기록한다(FR-002a).
    """

    def test_통화별_탐색_시작일을_읽는다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_PROBE_START_USD", "1964-01-01")
        assert load_settings().probe_start("USD") == dt.date(1964, 1, 1)

    def test_통화별_설정이_없으면_전역_하한을_쓴다(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """실제 `.env`에 통화별 값이 있으므로 빈 경로를 주입해 격리한다."""
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_PROBE_FLOOR", "1960-01-01")
        monkeypatch.delenv("ECOS_PROBE_START_EUR", raising=False)
        settings = load_settings(env_file=tmp_path / "absent.env")
        assert settings.probe_start("EUR") == dt.date(1960, 1, 1)

    def test_하한이_없으면_오류(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """기동 시점에 실패시킨다. 코드 기본값을 두면 그게 다시 하드코딩이다."""
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.delenv("ECOS_PROBE_FLOOR", raising=False)
        for code in ("USD", "JPY", "EUR"):
            monkeypatch.delenv(f"ECOS_PROBE_START_{code}", raising=False)
        with pytest.raises(ValueError, match="ECOS_PROBE_FLOOR"):
            load_settings(env_file=tmp_path / "absent.env")

    def test_잘못된_날짜_형식은_거부한다(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        monkeypatch.setenv("ECOS_PROBE_START_USD", "1964년 5월")
        with pytest.raises(ValueError, match="ECOS_PROBE_START_USD"):
            load_settings()

    def test_지원하지_않는_통화는_오류(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECOS_API_KEY", "test-key")
        with pytest.raises(ValueError, match="KRW"):
            load_settings().probe_start("KRW")
