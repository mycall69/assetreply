"""설정 선언 (T016).

헌법 원칙 II: rate limit·재시도 정책·청크 크기는 코드가 아닌 설정으로 선언한다.
헌법 v4.1.0: 커넥션 풀 크기와 타임아웃, **통화별 탐색 시작일**도 설정값이어야 한다.
축적 시작일을 코드에 하드코딩하는 것은 MUST NOT이다.
인증키와 DB 비밀번호는 환경변수로만 주입하며 코드·저장소에 하드코딩하지 않는다.

`.env`는 저장소 루트에서 로드한다(`backend/`가 아님). 실행 위치에 의존하지 않도록
이 파일 기준으로 상위를 탐색해 루트를 찾는다.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

_ROOT_MARKER: Final = ".env.example"

# 축적 대상 통화. 탐색 시작일은 통화마다 다르다 (FR-002).
SUPPORTED_CURRENCIES: Final = ("USD", "JPY", "EUR")


def repo_root() -> Path:
    """저장소 루트를 상위 탐색으로 찾는다.

    하드코딩된 상대 경로를 쓰지 않는 이유는 크로스 플랫폼 요구사항 때문이다.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / _ROOT_MARKER).exists():
            return parent
    raise RuntimeError(f"저장소 루트를 찾지 못했습니다 ({_ROOT_MARKER} 부재)")


class _Secret(str):
    """문자열로는 동작하되 repr/str에는 값을 노출하지 않는 래퍼.

    설정 객체를 로그나 예외 메시지에 찍었을 때 인증키가 새는 사고를 막는다.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "'***'"

    def reveal(self) -> str:
        return str.__str__(self)


def _env_int(key: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{key}는 정수여야 합니다: {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{key}는 {minimum} 이상이어야 합니다: {value}")
    return value


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key) or default


def _env_date(key: str) -> dt.date | None:
    raw = os.getenv(key)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{key}는 YYYY-MM-DD 형식이어야 합니다: {raw!r}") from exc


def _probe_starts() -> tuple[tuple[str, dt.date], ...]:
    """통화별 탐색 시작일. 통화별 설정이 없으면 전역 하한을 쓴다.

    코드 기본값을 두지 않는 이유는 헌법 v4.1.0이 시작일 하드코딩을 MUST NOT으로
    규정하기 때문이다. 값이 없으면 조용히 잘린 범위로 동작하는 대신 기동에 실패한다.
    """
    floor = _env_date("ECOS_PROBE_FLOOR")
    per_currency = {c: _env_date(f"ECOS_PROBE_START_{c}") for c in SUPPORTED_CURRENCIES}
    if floor is None and not all(per_currency.values()):
        missing = [c for c, d in per_currency.items() if d is None]
        raise ValueError(
            f"ECOS_PROBE_FLOOR가 설정되지 않았습니다(통화별 설정도 없음: {missing}). "
            "저장소 루트 .env를 확인하세요."
        )
    resolved: list[tuple[str, dt.date]] = []
    for code in SUPPORTED_CURRENCIES:
        start = per_currency[code] or floor
        assert start is not None  # 위 검사로 보장된다
        resolved.append((code, start))
    return tuple(resolved)


@dataclass(frozen=True, slots=True)
class Settings:
    """불변 설정. 런타임에 바뀌면 재현성이 깨진다(헌법 원칙 V)."""

    # ── 외부 데이터 소스 (contracts/ecos-adapter.md 설정 표) ──
    ecos_api_key: _Secret = field(repr=False)
    ecos_chunk_days: int = 365
    ecos_chunk_delay_ms: int = 1000
    ecos_max_concurrent_per_currency: int = 1
    ecos_max_concurrent_currencies: int = 3
    ecos_retry_max_attempts: int = 5
    ecos_retry_base_delay_ms: int = 1000

    # ── 수집 동작 ──
    collection_sync_threshold_days: int = 30
    job_history_success_retention_days: int = 90

    # ── 조회·표시 (002) ──
    # 일자별 상세 표가 한 번에 내려주는 기본 행 수.
    daily_page_size: int = 30
    # 오늘 새로고침 잠금의 스테일 회수 기준. 단일 호출이라 수집 잠금보다 짧게 잡는다.
    # 길게 잡으면 프로세스가 죽었을 때 새로고침이 오래 막힌다 (research R2-8).
    today_refresh_lock_ttl_seconds: int = 60

    # ── 축적 범위 (FR-002, 헌법 v4.1.0) ──
    # 탐색 시작점일 뿐이다. 출처가 제공하는 실제 최초일은 수집 중 발견해
    # `currency.first_available_date`에 기록한다 (FR-002a).
    ecos_probe_starts: tuple[tuple[str, dt.date], ...] = ()

    # ── 데이터베이스 ──
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "assetreplay"
    db_user: str = ""
    db_password: _Secret = field(default=_Secret(""), repr=False)

    # ── 커넥션 풀 (헌법 v4.0.0 MUST) ──
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30

    def probe_start(self, currency_code: str) -> dt.date:
        """통화의 탐색 시작일 (FR-002).

        이 날짜가 곧 최초 제공일이라는 뜻이 아니다. 여기서부터 수집을 시도하고,
        값이 처음 나타난 날짜를 실제 최초 제공일로 기록한다 (FR-002a).
        """
        for code, start in self.ecos_probe_starts:
            if code == currency_code:
                return start
        raise ValueError(f"{currency_code}의 탐색 시작일이 설정되지 않았습니다.")

    @property
    def database_url(self) -> str:
        """비동기 ORM 연결 URL (헌법 원칙 I)."""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password.reveal()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


def load_settings(env_file: Path | None = None) -> Settings:
    """`.env`와 환경변수에서 설정을 읽는다.

    `env_file`을 생략하면 저장소 루트의 `.env`를 사용한다. 테스트에서 실제 `.env`의
    영향을 배제하려면 존재하지 않는 경로를 넘긴다.

    이미 설정된 환경변수를 덮어쓰지 않으므로(`override=False`) 호출자의 환경변수가
    `.env` 값보다 우선한다.
    """
    load_dotenv(repo_root() / ".env" if env_file is None else env_file, override=False)

    api_key = os.getenv("ECOS_API_KEY")
    if not api_key:
        raise ValueError("ECOS_API_KEY가 설정되지 않았습니다. 저장소 루트 .env를 확인하세요.")

    return Settings(
        ecos_api_key=_Secret(api_key),
        ecos_chunk_days=_env_int("ECOS_CHUNK_DAYS", 365, minimum=1),
        ecos_chunk_delay_ms=_env_int("ECOS_CHUNK_DELAY_MS", 1000),
        ecos_max_concurrent_per_currency=_env_int("ECOS_MAX_CONCURRENT_PER_CURRENCY", 1, minimum=1),
        ecos_max_concurrent_currencies=_env_int("ECOS_MAX_CONCURRENT_CURRENCIES", 3, minimum=1),
        ecos_retry_max_attempts=_env_int("ECOS_RETRY_MAX_ATTEMPTS", 5, minimum=1),
        ecos_retry_base_delay_ms=_env_int("ECOS_RETRY_BASE_DELAY_MS", 1000),
        collection_sync_threshold_days=_env_int("COLLECTION_SYNC_THRESHOLD_DAYS", 30),
        job_history_success_retention_days=_env_int("JOB_HISTORY_SUCCESS_RETENTION_DAYS", 90),
        daily_page_size=_env_int("DAILY_PAGE_SIZE", 30, minimum=1),
        today_refresh_lock_ttl_seconds=_env_int("TODAY_REFRESH_LOCK_TTL_SECONDS", 60, minimum=1),
        ecos_probe_starts=_probe_starts(),
        db_host=_env_str("DB_HOST", "localhost"),
        db_port=_env_int("DB_PORT", 3306, minimum=1),
        db_name=_env_str("DB_NAME", "assetreplay"),
        db_user=_env_str("DB_USER"),
        db_password=_Secret(_env_str("DB_PASSWORD")),
        db_pool_size=_env_int("DB_POOL_SIZE", 5, minimum=1),
        db_max_overflow=_env_int("DB_MAX_OVERFLOW", 10, minimum=0),
        db_pool_timeout_seconds=_env_int("DB_POOL_TIMEOUT_SECONDS", 30, minimum=1),
    )
