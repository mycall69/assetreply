"""데이터 소스 인터페이스와 도메인 타입 (T023).

헌법 원칙 II: 데이터 소스는 교체 가능한 어댑터로 구현하며, 특정 벤더의 응답 형식이
도메인 계층에 노출되면 안 된다. **이 파일의 타입에는 ECOS 고유 필드명이 없다.**
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class FetchOutcome(StrEnum):
    """수집 결과 구분."""

    OK = "ok"
    # 해당 구간에 고시가 없었다 — 오류가 아니다 (contracts/ecos-adapter.md)
    NO_DATA = "no_data"


@dataclass(frozen=True, slots=True)
class DailyQuote:
    """하루치 고시값. 금액은 반드시 `Decimal`(헌법 원칙 VI)."""

    quote_date: dt.date
    base_rate: Decimal
    quote_unit: int


@dataclass(frozen=True, slots=True)
class FetchResult:
    """한 번의 수집 요청 결과. 원본 응답을 함께 담아 보존한다(FR-004a)."""

    quotes: tuple[DailyQuote, ...]
    outcome: FetchOutcome
    raw_body: str
    raw_status: int
    raw_result_code: str | None


@dataclass(frozen=True, slots=True)
class ItemMapping:
    """통화와 출처 항목 식별자의 대응."""

    currency_code: str
    source_item_code: str
    source_item_name: str


class FxRateSource(Protocol):
    """환율 데이터 소스. 상위 계층은 이 Protocol에만 의존한다(헌법 원칙 IV)."""

    async def fetch_daily_rates(
        self, currency_code: str, date_from: dt.date, date_to: dt.date
    ) -> FetchResult: ...

    async def verify_item_mapping(self, currency_code: str) -> ItemMapping: ...


# ── 예금 금리 (008) ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MonthlyRate:
    """한 달의 금리. `month`는 그 달 1일, `rate`는 연 %(헌법 원칙 VI — `Decimal`)."""

    month: dt.date
    rate: Decimal


@dataclass(frozen=True, slots=True)
class MonthlyFetchResult:
    """월 시계열 한 번의 요청 결과. `NO_DATA`는 **미발표**다 — 오류가 아니다(008 FR-010).

    원본 본문만 담는다 — 요청 URL은 담지 않는다(인증키가 경로에 있다, 008 FR-014).
    """

    rates: tuple[MonthlyRate, ...]
    outcome: FetchOutcome
    raw_body: str
    raw_status: int
    raw_result_code: str | None


class DepositSeries(Protocol):
    """투자처 하나의 월 시계열 손잡이. 상위 계층은 출처의 항목 코드를 모른다(헌법 원칙 II)."""

    @property
    def institution(self) -> str: ...

    @property
    def source_ref(self) -> str: ...

    @property
    def start_month(self) -> dt.date: ...
