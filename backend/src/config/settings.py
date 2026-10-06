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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

_ROOT_MARKER: Final = ".env.example"

# 축적 대상 통화. 탐색 시작일은 통화마다 다르다 (FR-002).
SUPPORTED_CURRENCIES: Final = ("USD", "JPY", "EUR")

#: 키움 REST API의 실행 모드 (006 research R6-1). 모드마다 도메인과 앱 키가 따로다.
KIWOOM_MODES: Final = ("real", "mock")


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


def _env_choice(key: str, default: str, choices: tuple[str, ...]) -> str:
    """정해진 값 중 하나. 벗어나면 기동을 거절한다.

    조용히 기본값으로 떨어뜨리지 않는다 — 예를 들어 키움 모드를 잘못 적었는데 `real`로
    떨어지면, 모의 키로 실전 도메인을 부르고 인증 실패만 반복된다.
    """
    value = os.getenv(key) or default
    if value not in choices:
        raise ValueError(f"{key}는 {' · '.join(choices)} 중 하나여야 합니다: {value!r}")
    return value


def _env_ratio(key: str, default: str) -> Decimal:
    """0보다 크고 1 이하인 비율. `Decimal`로 읽는다.

    금융 값은 아니지만 금융 계층의 `float` 정적 검사를 예외 없이 유지하려고 `Decimal`로 둔다.
    """
    raw = os.getenv(key) or default
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{key}는 0보다 크고 1 이하인 수여야 합니다: {raw!r}") from exc
    if not (Decimal("0") < value <= Decimal("1")):
        raise ValueError(f"{key}는 0보다 크고 1 이하인 수여야 합니다: {raw!r}")
    return value


def _env_seconds_ms(key: str, default: str) -> int:
    """초 단위 설정(소수 허용)을 밀리초 정수로 읽는다. `.env`는 사람이 읽는 초로 두고 코드는 정수로
    다룬다."""
    raw = os.getenv(key) or default
    try:
        seconds = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{key}는 0 이상의 초여야 합니다: {raw!r}") from exc
    if not seconds.is_finite() or seconds < 0:
        raise ValueError(f"{key}는 0 이상의 초여야 합니다: {raw!r}")
    return int(seconds * 1000)


def _env_user_agent(key: str, default: str) -> str:
    """사용자 에이전트. **설정하지 않았으면** 기본값, **비워 두었으면** 빈 문자열이다.

    `_env_str`과 달리 빈 값을 기본값으로 바꾸지 않는다 — 비우면 `aiohttp` 기본값이 나가 출처가
    403으로 막는다. 차단 경로를 일부러 재현하는 수단이다(007 quickstart 17).
    """
    raw = os.environ.get(key)
    return default if raw is None else raw.strip()


def _env_date(key: str) -> dt.date | None:
    raw = os.getenv(key)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{key}는 YYYY-MM-DD 형식이어야 합니다: {raw!r}") from exc


def _env_month(key: str) -> dt.date | None:
    """`YYYY-MM` 달(그 달 1일). 없으면 None — 시작일에 코드 기본값을 두지 않는다(헌법)."""
    raw = os.getenv(key)
    if not raw:
        return None
    parts = raw.split("-")
    shaped = len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 2
    if not shaped or not raw.replace("-", "").isdigit():
        raise ValueError(f"{key}는 YYYY-MM 형식이어야 합니다: {raw!r}")
    try:
        return dt.date(int(parts[0]), int(parts[1]), 1)
    except ValueError as exc:
        raise ValueError(f"{key}는 YYYY-MM 형식이어야 합니다: {raw!r}") from exc


def _recheck_months(provisional: int) -> int:
    """하루 한 번 다시 받는 최근 개월 수 — 잠정 기간 안이어야 한다."""
    value = _env_int("APT_TRADE_DAILY_RECHECK_MONTHS", 3, minimum=1)
    if value > provisional:
        raise ValueError(
            f"APT_TRADE_DAILY_RECHECK_MONTHS({value})는 "
            f"APT_TRADE_PROVISIONAL_MONTHS({provisional}) 이하여야 합니다")
    return value


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


#: 출처가 받아 주는 브라우저형 사용자 에이전트. `.env`에 줄이 없을 때만 쓴다(007 research R7-1).
INVESTING_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

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
    # 환율(001)과 예금 금리(008)가 함께 쓰는 ECOS 동시 요청 수 — 프로세스 하나의 관문이
    # 지킨다(008 R8-6). 001의 통화 동시 수와 같게 두어 환율 수집의 속도는 그대로다.
    ecos_max_concurrent_requests: int = 3
    # 예금 금리를 다시 확인할 때 마지막으로 받은 달의 몇 달 전부터 받을지 — 겹친 달로 출처의
    # 사후 수정을 관측한다(덮어쓰지 않는다, 008 R8-4).
    deposit_recheck_overlap_months: int = 2

    # ── 공공데이터포털 — 실거래·법정동코드·단지 목록·기본 정보 (009 research R9-5) ──
    # 네 자료가 같은 인증키다(활용신청 네 건). 키는 URL 질의에 들어가므로 URL을 남기지
    # 않는다(FR-013).
    data_api_key: _Secret = field(default_factory=lambda: _Secret(""), repr=False)
    # 네 자료가 함께 쓰는 동시 요청 수 — 한 프로세스의 관문(`DataGoKrGate`)이 지킨다.
    data_api_max_concurrent: int = 3
    # 자료별 하루 호출 한도(한국 시간 날짜). 보내기 전에 세고 넘으면 보내지 않는다 — 포털
    # 한도(10,000·5,000)에서 여유를 뒀다.
    data_api_daily_limit_trade: int = 9000
    data_api_daily_limit_kapt: int = 4500
    data_api_daily_limit_region: int = 9000
    # 한 요청의 최대 시도 횟수(첫 시도 포함)와 재시도 간격 기준 — 연결 실패·5xx만 다시 시도한다.
    data_api_retry_max_attempts: int = 4
    data_api_retry_base_delay_ms: int = 1000
    # 시·군·구의 첫 거래 달을 찾기 시작하는 달. **코드 기본값이 없다** — 헌법은 시작일을 코드에 두지
    # 못하게 한다(001 `ECOS_PROBE_FLOOR`와 같은 취지). 없으면 실거래 수집이 사유와 함께 멈춘다.
    apt_trade_probe_start: dt.date | None = None
    # 잠정 기간(개월, 계약 월 기준)과 그중 하루 한 번 다시 받는 최근 개월 수 — 그 앞의 잠정 달은 한
    # 달에 한 번(R9-5).
    apt_trade_provisional_months: int = 12
    apt_trade_daily_recheck_months: int = 3
    # 행정구역·동의 단지 목록을 다시 받는 주기(일).
    apt_list_refresh_days: int = 30

    # ── 주식 시세 출처 (005 research R5-1) ──
    #
    # **문서화되지 않은 비공식 엔드포인트다.** Yahoo가 2017년 공식 API를 종료한 뒤
    # 대체 공개 API를 내놓지 않았고, 이 호출은 예고 없이 바뀌거나 막힐 수 있다.
    # 헌법 원칙 II의 "이용약관 준수" 항목이 미충족이며, 그 이탈은 005 plan의
    # Complexity Tracking에 기록돼 있다.
    #
    # **호출 간격을 보수적으로 잡는다.** 공격적 폴링이 차단의 주된 원인이다.
    stock_source_base_url: str = "https://query1.finance.yahoo.com"
    stock_chunk_delay_ms: int = 1500
    stock_max_concurrent: int = 1
    stock_retry_max_attempts: int = 4
    stock_retry_base_delay_ms: int = 2000
    stock_request_timeout_seconds: int = 20

    # ── 검색용 종목 목록 — 키움증권 REST API (006 research R6-1·R6-3) ──
    #
    # **목록에만 쓴다.** 시세·배당·분할은 005의 출처 그대로다 (006 FR-012).
    # 키가 비어 있어도 기동은 된다 — 목록 갱신만 "인증 정보 미설정"으로 남는다 (FR-028a).
    kiwoom_mode: str = "real"
    kiwoom_app_key: _Secret = field(default=_Secret(""), repr=False)
    kiwoom_app_secret: _Secret = field(default=_Secret(""), repr=False)
    # 미국 목록은 계좌·토큰별 분당 5회로 제한된다 — 쪽 사이를 12초로 둔다 (R6-2).
    kiwoom_us_page_delay_seconds: int = 12
    kiwoom_kr_page_delay_seconds: int = 1
    # 한 요청의 최대 시도 횟수(첫 시도 포함). 네트워크·5xx만 다시 시도한다 —
    # 인증 실패는 다시 시도하지 않는다.
    kiwoom_max_retries: int = 3
    # 갱신 실패 뒤 다음 시도까지와 목록 단위마다 하루 시도 상한 (FR-013a).
    listing_retry_interval_minutes: int = 30
    listing_max_attempts_per_day: int = 5
    # 새 건수 < 이전 건수 × 이 값이면 교체하지 않는다 (FR-018a).
    listing_shrink_threshold: Decimal = Decimal("0.5")
    # 갱신 점유의 심장박동이 이 시간 넘게 멈추면 회수한다 (data-model 3절).
    listing_lock_stale_minutes: int = 10

    # ── 가상자산 시세·코인 목록 — investing.com (007 research R7-1) ──
    #
    # **공개되지 않은 내부 API다.** 약관이 허가 없는 저장·사용을 금지하므로 개인 이용 전제의
    # 잠정 결정이다(헌법 원칙 II 이탈, 007 plan Complexity Tracking). 로그인·키는 필요 없다.
    # 기본 사용자 에이전트는 403으로 막힌다.
    investing_coins_base_url: str = "https://endpoints.investing.com/pd-instruments"
    investing_history_base_url: str = "https://api.investing.com/api/financialdata"
    investing_user_agent: str = INVESTING_DEFAULT_USER_AGENT
    # 일봉 API가 요구하는 `domain-id` 헤더 값(없으면 400).
    investing_domain_id: str = "www"
    # 요청 사이 최소 간격. 목록 갱신과 시세 수집이 **한 클라이언트에서** 함께 지킨다(R7-11).
    investing_min_interval_ms: int = 1500
    # 한 요청의 최대 시도 횟수(첫 시도 포함). 429·5xx·연결 오류만 다시 시도한다 — 403은 차단이다.
    investing_max_retries: int = 3
    investing_backoff_base_ms: int = 2000
    investing_request_timeout_seconds: int = 30
    # 한 요청의 일봉 구간. 출처는 약 5,000행에서 표시 없이 자른다(R7-3).
    investing_chunk_days: int = 730
    # 코인 목록을 다시 받는 주기(일)와 축소 한도(007 FR-005, R7-4).
    crypto_list_refresh_days: int = 7
    crypto_list_shrink_threshold: Decimal = Decimal("0.5")
    crypto_list_lock_stale_minutes: int = 10

    # ── 부동산 단지 번호 — Npay 부동산 단지 자동완성 (010 반복 3, research R10-19) ── **공개되지
    # 않은 내부 API다**(헌법 원칙 II 이탈, 010 plan Complexity Tracking — 개인 이용 전제의 잠정
    # 결정). 단지 이름에서 Npay 부동산 단지 화면을 열 번호만 찾는다 — 단지 하나에 한 번, 저장해 다시
    # 쓴다. 기본 사용자 에이전트는 403, 짧은 시간에 여러 번 부르면 429다.
    naver_land_base_url: str = "https://fin.land.naver.com/front-api/v1"
    naver_land_user_agent: str = INVESTING_DEFAULT_USER_AGENT
    naver_land_referer: str = "https://fin.land.naver.com/map"
    # 없으면 출처가 곧바로 429를 준다(T067 실측 — 브라우저답지 않은 요청을 거른다).
    naver_land_accept_language: str = "ko-KR,ko;q=0.9"
    naver_land_min_interval_ms: int = 2000
    # 한 요청의 최대 시도 횟수(첫 시도 포함). 429·5xx·연결 오류만 다시 시도한다 — 403은 차단이다.
    naver_land_max_retries: int = 2
    naver_land_backoff_base_ms: int = 3000
    naver_land_request_timeout_seconds: int = 10
    # 못 찾은 단지를 다시 찾기까지의 날 수. 찾은 번호는 다시 찾지 않는다.
    naver_land_recheck_days: int = 30

    # ── 수집 동작 ──
    collection_sync_threshold_days: int = 30
    job_history_success_retention_days: int = 90

    # ── 조회·표시 (002) ──
    # 일자별 상세 표가 한 번에 내려주는 기본 행 수.
    daily_page_size: int = 30
    # 오늘 새로고침 잠금의 스테일 회수 기준. 단일 호출이라 수집 잠금보다 짧게 잡는다.
    # 길게 잡으면 프로세스가 죽었을 때 새로고침이 오래 막힌다 (research R2-8).
    today_refresh_lock_ttl_seconds: int = 60

    # ── 수집 실행·관측 (003) ──
    # 진전이 없다고 화면에 알리는 기준. 점유 회수 기준(900초)과 별개다 — 경고는
    # 사람에게 빨리 알리고, 회수는 시스템이 안전해진 뒤 되찾는다 (FR-006a, R3-3).
    stall_threshold_seconds: int = 60
    # 화면 조회용 수집 이벤트의 보관 범위. 통화별 최근 N개 작업 (FR-023, R3-9).
    event_retention_jobs: int = 20
    # 미해결 작업 정리 주기. 기동 시 1회 실행에 더해 이 간격으로 반복한다 (R3-2).
    reconcile_interval_seconds: int = 60
    # 수집 전용 로그 파일. 웹서버 표준출력과 분리한다 — 접근 로그와 뒤엉키면
    # 운영자가 걸러내야 한다 (R3-10).
    collection_log_path: str = "logs/collection.log"

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

    @property
    def kiwoom_credentials_present(self) -> bool:
        """앱 키와 시크릿이 **둘 다** 있는가. 한쪽만 있으면 토큰을 받을 수 없다."""
        return bool(self.kiwoom_app_key.reveal()) and bool(self.kiwoom_app_secret.reveal())

    def collection_log_file(self) -> Path:
        """수집 로그의 절대 경로.

        상대 경로는 **저장소 루트 기준**으로 푼다. uvicorn이 `backend/`에서 뜨기 때문에
        그대로 두면 `backend/logs/`에 생겨, `be-start.sh`가 쓰는 루트 `logs/`와 갈라진다.
        운영자가 두 곳을 뒤져야 한다.
        """
        path = Path(self.collection_log_path)
        return path if path.is_absolute() else repo_root() / path

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

    provisional_months = _env_int("APT_TRADE_PROVISIONAL_MONTHS", 12, minimum=1)
    return Settings(
        ecos_api_key=_Secret(api_key),
        ecos_chunk_days=_env_int("ECOS_CHUNK_DAYS", 365, minimum=1),
        ecos_chunk_delay_ms=_env_int("ECOS_CHUNK_DELAY_MS", 1000),
        ecos_max_concurrent_per_currency=_env_int("ECOS_MAX_CONCURRENT_PER_CURRENCY", 1, minimum=1),
        ecos_max_concurrent_currencies=_env_int("ECOS_MAX_CONCURRENT_CURRENCIES", 3, minimum=1),
        ecos_retry_max_attempts=_env_int("ECOS_RETRY_MAX_ATTEMPTS", 5, minimum=1),
        ecos_retry_base_delay_ms=_env_int("ECOS_RETRY_BASE_DELAY_MS", 1000),
        ecos_max_concurrent_requests=_env_int("ECOS_MAX_CONCURRENT_REQUESTS", 3, minimum=1),
        deposit_recheck_overlap_months=_env_int("DEPOSIT_RECHECK_OVERLAP_MONTHS", 2),
        data_api_key=_Secret(_env_str("DATA_API_KEY")),
        data_api_max_concurrent=_env_int("DATA_API_MAX_CONCURRENT", 3, minimum=1),
        data_api_daily_limit_trade=_env_int("DATA_API_DAILY_LIMIT_TRADE", 9000, minimum=1),
        data_api_daily_limit_kapt=_env_int("DATA_API_DAILY_LIMIT_KAPT", 4500, minimum=1),
        data_api_daily_limit_region=_env_int("DATA_API_DAILY_LIMIT_REGION", 9000, minimum=1),
        data_api_retry_max_attempts=_env_int("DATA_API_RETRY_MAX_ATTEMPTS", 4, minimum=1),
        data_api_retry_base_delay_ms=_env_int("DATA_API_RETRY_BASE_DELAY_MS", 1000),
        apt_trade_probe_start=_env_month("APT_TRADE_PROBE_START"),
        apt_trade_provisional_months=provisional_months,
        apt_trade_daily_recheck_months=_recheck_months(provisional_months),
        apt_list_refresh_days=_env_int("APT_LIST_REFRESH_DAYS", 30, minimum=1),
        stock_source_base_url=_env_str(
            "STOCK_SOURCE_BASE_URL", "https://query1.finance.yahoo.com"),
        stock_chunk_delay_ms=_env_int("STOCK_CHUNK_DELAY_MS", 1500),
        stock_max_concurrent=_env_int("STOCK_MAX_CONCURRENT", 1, minimum=1),
        stock_retry_max_attempts=_env_int("STOCK_RETRY_MAX_ATTEMPTS", 4, minimum=1),
        stock_retry_base_delay_ms=_env_int("STOCK_RETRY_BASE_DELAY_MS", 2000),
        stock_request_timeout_seconds=_env_int(
            "STOCK_REQUEST_TIMEOUT_SECONDS", 20, minimum=1),
        kiwoom_mode=_env_choice("KIWOOM_MODE", "real", KIWOOM_MODES),
        kiwoom_app_key=_Secret(_env_str("KIWOOM_APP_KEY")),
        kiwoom_app_secret=_Secret(_env_str("KIWOOM_APP_SECRET")),
        kiwoom_us_page_delay_seconds=_env_int("KIWOOM_US_PAGE_DELAY_SECONDS", 12),
        kiwoom_kr_page_delay_seconds=_env_int("KIWOOM_KR_PAGE_DELAY_SECONDS", 1),
        kiwoom_max_retries=_env_int("KIWOOM_MAX_RETRIES", 3, minimum=1),
        listing_retry_interval_minutes=_env_int("LISTING_RETRY_INTERVAL_MINUTES", 30),
        listing_max_attempts_per_day=_env_int("LISTING_MAX_ATTEMPTS_PER_DAY", 5, minimum=1),
        listing_shrink_threshold=_env_ratio("LISTING_SHRINK_THRESHOLD", "0.5"),
        listing_lock_stale_minutes=_env_int("LISTING_LOCK_STALE_MINUTES", 10, minimum=1),
        investing_coins_base_url=_env_str(
            "INVESTING_COINS_BASE_URL", "https://endpoints.investing.com/pd-instruments"),
        investing_history_base_url=_env_str(
            "INVESTING_HISTORY_BASE_URL", "https://api.investing.com/api/financialdata"),
        investing_user_agent=_env_user_agent("INVESTING_USER_AGENT", INVESTING_DEFAULT_USER_AGENT),
        investing_domain_id=_env_str("INVESTING_DOMAIN_ID", "www"),
        investing_min_interval_ms=_env_seconds_ms("INVESTING_MIN_INTERVAL_SECONDS", "1.5"),
        investing_max_retries=_env_int("INVESTING_MAX_RETRIES", 3, minimum=1),
        investing_backoff_base_ms=_env_seconds_ms("INVESTING_BACKOFF_BASE_SECONDS", "2"),
        investing_request_timeout_seconds=_env_int(
            "INVESTING_REQUEST_TIMEOUT_SECONDS", 30, minimum=1),
        investing_chunk_days=_env_int("INVESTING_CHUNK_DAYS", 730, minimum=1),
        crypto_list_refresh_days=_env_int("CRYPTO_LIST_REFRESH_DAYS", 7, minimum=1),
        crypto_list_shrink_threshold=_env_ratio("CRYPTO_LIST_SHRINK_THRESHOLD", "0.5"),
        crypto_list_lock_stale_minutes=_env_int("CRYPTO_LIST_LOCK_STALE_MINUTES", 10, minimum=1),
        naver_land_base_url=_env_str(
            "NAVER_LAND_BASE_URL", "https://fin.land.naver.com/front-api/v1"),
        naver_land_user_agent=_env_user_agent(
            "NAVER_LAND_USER_AGENT", INVESTING_DEFAULT_USER_AGENT),
        naver_land_referer=_env_str("NAVER_LAND_REFERER", "https://fin.land.naver.com/map"),
        naver_land_accept_language=_env_str("NAVER_LAND_ACCEPT_LANGUAGE", "ko-KR,ko;q=0.9"),
        naver_land_min_interval_ms=_env_seconds_ms("NAVER_LAND_MIN_INTERVAL_SECONDS", "2"),
        naver_land_max_retries=_env_int("NAVER_LAND_MAX_RETRIES", 2, minimum=1),
        naver_land_backoff_base_ms=_env_seconds_ms("NAVER_LAND_BACKOFF_BASE_SECONDS", "3"),
        naver_land_request_timeout_seconds=_env_int(
            "NAVER_LAND_REQUEST_TIMEOUT_SECONDS", 10, minimum=1),
        naver_land_recheck_days=_env_int("NAVER_LAND_RECHECK_DAYS", 30, minimum=1),
        collection_sync_threshold_days=_env_int("COLLECTION_SYNC_THRESHOLD_DAYS", 30),
        job_history_success_retention_days=_env_int("JOB_HISTORY_SUCCESS_RETENTION_DAYS", 90),
        daily_page_size=_env_int("DAILY_PAGE_SIZE", 30, minimum=1),
        today_refresh_lock_ttl_seconds=_env_int("TODAY_REFRESH_LOCK_TTL_SECONDS", 60, minimum=1),
        stall_threshold_seconds=_env_int("STALL_THRESHOLD_SECONDS", 60, minimum=1),
        event_retention_jobs=_env_int("EVENT_RETENTION_JOBS", 20, minimum=1),
        reconcile_interval_seconds=_env_int("RECONCILE_INTERVAL_SECONDS", 60, minimum=1),
        collection_log_path=_env_str("COLLECTION_LOG_PATH", "logs/collection.log"),
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
