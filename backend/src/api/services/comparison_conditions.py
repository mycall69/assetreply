"""저장한 비교의 조건 — 검증·정규화·직렬화 (013 T071) — FR-004, FR-016, SC-006, data-model 2.

순수 함수다(DB·HTTP 없음). 저장하는 것은 **조건뿐**이다 — 자산군, 대상 목록(차례 있음), 공통 조건.
알려진 칸만 남기고(결과 키 `summary`·`comparison`·`series`, 대상의 검색 순위 같은 것은 버린다)
정해진 차례로 직렬화한다 — 화면 `lib/compareCondition.toCondition`과 같은 모양이다.

- **금액은 받은 글자 그대로 둔다.** 검증할 때만 `Decimal`로 읽는다 — 이 모듈은 그것으로 계산하지
  않는다(원칙 VI 해석, 012 R12-9 선례). 지수 표기·쉼표는 받지 않는다
- 틀린 칸은 메시지가 칸을 밝힌다(`InvalidComparison`). 빠진 칸을 기본값으로 메우지 않는다 — 메워
  저장하면 불러올 때 다른 조건으로 돈다
- 대상 수·중복·적금 투자처·원금 통화 규칙은 화면의 규칙과 같다(`maxTargets`·`targetKey`·
  `allowedCurrencies`) — 화면을 거치지 않은 본문도 같은 조건만 저장된다
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from src.api.errors import InvalidComparison
from src.api.services.history_conditions import AREAS, FREQUENCIES, INSTITUTIONS

ComparisonAsset = Literal["stock", "crypto", "deposit", "realestate"]

VERSION: Final = 1
ASSETS: Final[tuple[ComparisonAsset, ...]] = ("stock", "crypto", "deposit", "realestate")
METHODS: Final[dict[str, tuple[str, ...]]] = {
    "stock": ("lump_sum", "recurring"),
    "crypto": ("lump_sum", "recurring"),
    "deposit": ("deposit", "installment"),
    "realestate": ("hold",),
}
#: 정기 적금 금리가 있는 투자처(011) — 나머지는 비교 경로가 400 `installment_not_available`이다.
INSTALLMENT_INSTITUTIONS: Final = ("commercial_bank", "mutual_finance")
STOCK_MARKETS: Final = ("KRX", "NASDAQ", "NYSE", "AMEX", "TSE")
#: 원금 통화로 고를 수 있는 것 — 화면의 선택지와 같다.
PRINCIPAL_CURRENCIES: Final = ("KRW", "USD", "JPY")
MIN_TARGETS: Final = 2
MAX_TARGETS: Final = 10
#: 예금은 투자처가 다섯이다.
MAX_DEPOSIT_TARGETS: Final = 5
MAX_NAME: Final = 100
MAX_TEXT: Final = 200
_PLAIN_DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?")
_INTEGER = re.compile(r"[0-9]+")

Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class ComparisonCondition:
    asset: ComparisonAsset
    #: 저장하는 칸만 남긴 조건.
    body: Json
    #: 정해진 차례(키 정렬)로 직렬화한 글 — DB에 이것을 저장한다.
    text: str


def _bad(field: str, why: str) -> InvalidComparison:
    return InvalidComparison(f"{field}: {why}")


def validate_name(raw: object) -> str:
    """앞뒤 공백을 뺀 1~100자."""
    if not isinstance(raw, str):
        raise _bad("name", "글자여야 합니다")
    name = raw.strip()
    if name == "":
        raise _bad("name", "비었습니다")
    if len(name) > MAX_NAME:
        raise _bad("name", f"{MAX_NAME}자를 넘습니다")
    return name


def _text(raw: Mapping[str, object], field: str, label: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or value == "":
        raise _bad(label, "글자여야 합니다")
    if len(value) > MAX_TEXT:
        raise _bad(label, f"{MAX_TEXT}자를 넘습니다")
    return value


def _nullable_text(raw: Mapping[str, object], field: str, label: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise _bad(label, f"글자(최대 {MAX_TEXT}자) 또는 null이어야 합니다")
    return value


def _choice(value: object, field: str, options: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in options:
        raise _bad(field, f"{' · '.join(options)} 중 하나여야 합니다")
    return value


def _positive_int(raw: Mapping[str, object], field: str, label: str) -> int:
    value = raw.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _bad(label, "양의 정수여야 합니다")
    return value


def _date(value: object) -> str:
    if not isinstance(value, str) or len(value) != len("YYYY-MM-DD"):
        raise _bad("start", "ISO 날짜(YYYY-MM-DD)여야 합니다")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise _bad("start", "ISO 날짜(YYYY-MM-DD)여야 합니다") from exc
    return value


def _amount(value: object, asset: str) -> str | None:
    """0보다 큰 십진 문자열 — 받은 글자 그대로. 예금은 정수, 부동산은 `null`(매입가는 대상마다
    그 달 시세다)."""
    if asset == "realestate":
        if value is not None:
            raise _bad("amount", "부동산은 null이어야 합니다(매입가는 대상마다 그 달 시세)")
        return None
    pattern = _INTEGER if asset == "deposit" else _PLAIN_DECIMAL
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        kind = "정수" if asset == "deposit" else "십진"
        raise _bad("amount", f"0보다 큰 {kind} 문자열이어야 합니다(지수 표기·쉼표 없이)")
    try:
        positive = Decimal(value) > 0
    except InvalidOperation as exc:
        raise _bad("amount", "0보다 큰 십진 문자열이어야 합니다") from exc
    if not positive:
        raise _bad("amount", "0보다 커야 합니다")
    return value


def _stock_target(raw: Mapping[str, object], at: str) -> tuple[Json, str]:
    market = _choice(raw.get("market"), f"{at}.market", STOCK_MARKETS)
    ref: Json = {
        "market": market,
        "symbol": _text(raw, "symbol", f"{at}.symbol"),
        "name": _text(raw, "name", f"{at}.name"),
        "currency": _text(raw, "currency", f"{at}.currency"),
    }
    return ref, f"{market}|{ref['symbol']}"


def _crypto_target(raw: Mapping[str, object], at: str) -> tuple[Json, str]:
    coin_id = _positive_int(raw, "coinId", f"{at}.coinId")
    ref: Json = {
        "coinId": coin_id,
        "symbol": _text(raw, "symbol", f"{at}.symbol"),
        "name": _text(raw, "name", f"{at}.name"),
        "nameKo": _nullable_text(raw, "nameKo", f"{at}.nameKo"),
        "currency": _text(raw, "currency", f"{at}.currency"),
    }
    return ref, str(coin_id)


def _deposit_target(raw: Mapping[str, object], at: str, method: str) -> tuple[Json, str]:
    options = INSTALLMENT_INSTITUTIONS if method == "installment" else INSTITUTIONS
    institution = _choice(raw.get("institution"), f"{at}.institution", options)
    return {"institution": institution}, institution


def _realestate_target(raw: Mapping[str, object], at: str) -> tuple[Json, str]:
    complex_id = _positive_int(raw, "complexId", f"{at}.complexId")
    area = _choice(raw.get("area"), f"{at}.area", AREAS)
    ref: Json = {
        "complexId": complex_id,
        "name": _text(raw, "name", f"{at}.name"),
        "umdName": _text(raw, "umdName", f"{at}.umdName"),
        "area": area,
        "areaLabel": _text(raw, "areaLabel", f"{at}.areaLabel"),
    }
    return ref, f"{complex_id}|{area}"


def _target(raw: object, at: str, asset: str, method: str) -> tuple[Json, str]:
    if not isinstance(raw, dict):
        raise _bad(at, "객체여야 합니다")
    if asset == "stock":
        return _stock_target(raw, at)
    if asset == "crypto":
        return _crypto_target(raw, at)
    if asset == "deposit":
        return _deposit_target(raw, at, method)
    return _realestate_target(raw, at)


def _targets(raw: object, asset: str, method: str) -> list[Json]:
    """2~10개(예금 ≤5), 차례 있음. 같은 대상 키가 두 번이면 거절한다."""
    if not isinstance(raw, list):
        raise _bad("targets", "배열이어야 합니다")
    most = MAX_DEPOSIT_TARGETS if asset == "deposit" else MAX_TARGETS
    if not MIN_TARGETS <= len(raw) <= most:
        raise _bad("targets", f"{MIN_TARGETS}~{most}개여야 합니다: {len(raw)}개")
    seen: set[str] = set()
    targets: list[Json] = []
    for index, item in enumerate(raw):
        ref, key = _target(item, f"targets[{index}]", asset, method)
        if key in seen:
            raise _bad(f"targets[{index}]", f"같은 대상이 두 번 있습니다: {key}")
        seen.add(key)
        targets.append(ref)
    return targets


def _principal_currency(value: object, asset: str, targets: list[Json]) -> str:
    """원화는 늘 된다. 외화는 주식·가상자산에서 **모든 대상의 통화가 그 통화일 때만**(FR-007)."""
    currency = _choice(value, "principalCurrency", PRINCIPAL_CURRENCIES)
    if currency == "KRW":
        return currency
    if asset not in ("stock", "crypto"):
        raise _bad("principalCurrency", "예금·부동산은 KRW여야 합니다")
    if any(t.get("currency") != currency for t in targets):
        raise _bad("principalCurrency", f"모든 대상의 통화가 {currency}일 때만 고를 수 있습니다")
    return currency


def validate_condition(raw: object) -> ComparisonCondition:
    """비교 조건을 검증해 알려진 칸만 남기고 직렬화한다. 틀리면 `InvalidComparison`(칸을 밝힌다)."""
    if not isinstance(raw, dict):
        raise _bad("condition", "객체여야 합니다")
    if raw.get("v") != VERSION or isinstance(raw.get("v"), bool):
        raise _bad("v", f"{VERSION}이어야 합니다")
    asset_text = _choice(raw.get("asset"), "asset", ASSETS)
    asset = next(a for a in ASSETS if a == asset_text)
    method = _choice(raw.get("method"), "method", METHODS[asset])
    frequency = raw.get("frequency")
    if method == "recurring":
        frequency = _choice(frequency, "frequency", FREQUENCIES)
    elif frequency is not None:
        raise _bad("frequency", "적립식이 아니면 null이어야 합니다")
    start = _date(raw.get("start"))
    amount = _amount(raw.get("amount"), asset)
    targets = _targets(raw.get("targets"), asset, method)
    currency = _principal_currency(raw.get("principalCurrency"), asset, targets)
    reinvest = raw.get("reinvest")
    if asset == "stock":
        if not isinstance(reinvest, bool):
            raise _bad("reinvest", "true 또는 false여야 합니다")
    elif reinvest is not None:
        raise _bad("reinvest", "주식이 아니면 null이어야 합니다")
    body: Json = {
        "v": VERSION,
        "asset": asset,
        "method": method,
        "frequency": frequency,
        "start": start,
        "amount": amount,
        "principalCurrency": currency,
        "reinvest": reinvest,
        "targets": targets,
    }
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ComparisonCondition(asset, body, text)
