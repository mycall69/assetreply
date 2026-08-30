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
