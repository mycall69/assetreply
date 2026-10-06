"""이력 조건 — 자산군마다의 검증·직렬화·식별자 (012 T053) — FR-011, FR-013, data-model 2, research
R12-9.

순수 함수다(DB·HTTP 없음). 서버가 조건에서 식별자를 계산한다 — 유일 키가 저장된 내용에서 나오므로,
두 브라우저가 다른 판의 화면으로 저장해도 같은
조건은 한 항목이다. 규칙은 012 전 화면 lib(`conditionId` 계열)과 **글자까지 같다** — 옮긴 항목의
식별자가 바뀌지 않는다.

- 조건 칸 밖의 키(결과·`id`·`savedAt`)는 버린다 — 결과를 저장하지 않는다(005 R5-9)
- 011 전 형식(`mode`·`frequency`·`product` 없음)은 그대로 저장한다 — 쓰는 곳이 일시금·정기예금으로
  읽는다(011 FR-033)
- **원금·매입가는 받은 글자 그대로 둔다.** 검증할 때만 `Decimal`로 읽는다 — 이 모듈은 그것으로
  계산하지 않는다(원칙 VI 해석 — plan Complexity
  Tracking, 사용자 확인 2026-10-06). 지수 표기(`1e7`)는 받지 않는다 — 같은 금액이 다른 글자가 되면
  같은 조건이 두 항목이 된다
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, get_args

from src.api.errors import InvalidHistory, UnknownAsset

AssetClass = Literal["stock", "crypto", "deposit", "realestate"]
ASSET_CLASSES: Final[tuple[str, ...]] = get_args(AssetClass)

FREQUENCIES: Final = ("daily", "weekly", "monthly", "yearly")
INSTITUTIONS: Final = (
    "commercial_bank",
    "savings_bank",
    "credit_union",
    "mutual_finance",
    "saemaul",
)
AREAS: Final = ("10", "20", "30k", "30l", "40", "50", "60")

MAX_TEXT: Final = 200
MAX_KEY: Final = 255
_PLAIN_DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?")

Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class HistoryCondition:
    asset: AssetClass
    #: 조건 식별자 — API의 `id`.
    key: str
    #: 저장하는 칸만 남긴 조건.
    body: Json
    #: 정해진 차례(키 정렬)로 직렬화한 글 — DB에 이것을 저장한다.
    text: str


def parse_asset(raw: str) -> AssetClass:
    for asset in ("stock", "crypto", "deposit", "realestate"):
        if raw == asset:
            return asset
    raise UnknownAsset(f"모르는 자산군입니다: {raw} (stock · crypto · deposit · realestate)")


def _bad(field: str, why: str) -> InvalidHistory:
    return InvalidHistory(f"{field}: {why}")


def _text(raw: Mapping[str, object], field: str, *, label: str | None = None) -> str:
    value = raw.get(field)
    name = label or field
    if not isinstance(value, str) or value == "":
        raise _bad(name, "글자여야 합니다")
    if len(value) > MAX_TEXT:
        raise _bad(name, f"{MAX_TEXT}자를 넘습니다")
    return value


def _nullable_text(raw: Mapping[str, object], field: str, *, label: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise _bad(label, f"글자(최대 {MAX_TEXT}자) 또는 null이어야 합니다")
    return value


def _date(raw: Mapping[str, object], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str):
        raise _bad(field, "ISO 날짜(YYYY-MM-DD)여야 합니다")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise _bad(field, "ISO 날짜(YYYY-MM-DD)여야 합니다") from exc
    if len(value) != len("YYYY-MM-DD"):
        raise _bad(field, "ISO 날짜(YYYY-MM-DD)여야 합니다")
    return value


def _amount(raw: Mapping[str, object], field: str) -> str:
    """0보다 큰 십진 문자열. 받은 글자 그대로 돌려준다."""
    value = raw.get(field)
    if not isinstance(value, str) or _PLAIN_DECIMAL.fullmatch(value) is None:
        raise _bad(field, "0보다 큰 십진 문자열이어야 합니다(지수 표기·쉼표 없이)")
    try:
        positive = Decimal(value) > 0
    except InvalidOperation as exc:
        raise _bad(field, "0보다 큰 십진 문자열이어야 합니다") from exc
    if not positive:
        raise _bad(field, "0보다 커야 합니다")
    return value


def _choice(raw: Mapping[str, object], field: str, options: tuple[str, ...]) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or value not in options:
        raise _bad(field, f"{' · '.join(options)} 중 하나여야 합니다")
    return value


def _object(raw: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = raw.get(field)
    if not isinstance(value, dict):
        raise _bad(field, "객체여야 합니다")
    return value


def _plan(raw: Mapping[str, object]) -> Json:
    """투자 방식 — 적립식만 칸을 둔다(일시금은 칸이 없다 — 011 전 형식과 같다)."""
    if "mode" not in raw:
        return {}
    if raw.get("mode") != "recurring":
        raise _bad("mode", "recurring이거나 없어야 합니다")
    plan: Json = {"mode": "recurring"}
    if "frequency" in raw:
        plan["frequency"] = _choice(raw, "frequency", FREQUENCIES)
    return plan


def _recurring_suffix(body: Json) -> str:
    if body.get("mode") != "recurring":
        return ""
    frequency = body.get("frequency")
    return f"|recurring:{frequency if isinstance(frequency, str) else 'monthly'}"


def _stock(raw: Mapping[str, object]) -> tuple[Json, str]:
    stock = _object(raw, "stock")
    ref = {
        name: _text(stock, name, label=f"stock.{name}")
        for name in ("market", "symbol", "name", "currency")
    }
    reinvest = raw.get("reinvest")
    if not isinstance(reinvest, bool):
        raise _bad("reinvest", "true 또는 false여야 합니다")
    body: Json = {
        "stock": ref,
        "start": _date(raw, "start"),
        "principal": _amount(raw, "principal"),
        "principalCurrency": _text(raw, "principalCurrency"),
        "reinvest": reinvest,
        **_plan(raw),
    }
    key = "|".join(
        [
            ref["market"],
            ref["symbol"],
            str(body["start"]),
            str(body["principal"]),
            str(body["principalCurrency"]),
            "R" if reinvest else "N",
        ]
    )
    return body, key + _recurring_suffix(body)


def _crypto(raw: Mapping[str, object]) -> tuple[Json, str]:
    coin = _object(raw, "coin")
    coin_id = coin.get("coinId")
    if not isinstance(coin_id, int) or isinstance(coin_id, bool) or coin_id <= 0:
        raise _bad("coin.coinId", "양의 정수여야 합니다")
    ref: Json = {
        "coinId": coin_id,
        "symbol": _text(coin, "symbol", label="coin.symbol"),
        "name": _text(coin, "name", label="coin.name"),
        "nameKo": _nullable_text(coin, "nameKo", label="coin.nameKo"),
        "currency": _text(coin, "currency", label="coin.currency"),
    }
    if "slug" in coin:
        ref["slug"] = _nullable_text(coin, "slug", label="coin.slug")
    body: Json = {
        "coin": ref,
        "start": _date(raw, "start"),
        "principal": _amount(raw, "principal"),
        "principalCurrency": _text(raw, "principalCurrency"),
        **_plan(raw),
    }
    key = "|".join(
        [str(coin_id), str(body["start"]), str(body["principal"]), str(body["principalCurrency"])]
    )
    return body, key + _recurring_suffix(body)


def _deposit(raw: Mapping[str, object]) -> tuple[Json, str]:
    body: Json = {
        "institution": _choice(raw, "institution", INSTITUTIONS),
        "start": _date(raw, "start"),
        "principal": _amount(raw, "principal"),
    }
    if "product" in raw:
        if raw.get("product") != "installment":
            raise _bad("product", "installment이거나 없어야 합니다")
        body["product"] = "installment"
    key = "|".join([str(body["institution"]), str(body["start"]), str(body["principal"])])
    return body, key + ("|installment" if "product" in body else "")


def _realestate(raw: Mapping[str, object]) -> tuple[Json, str]:
    complex_id = raw.get("complexId")
    if not isinstance(complex_id, int) or isinstance(complex_id, bool) or complex_id <= 0:
        raise _bad("complexId", "양의 정수여야 합니다")
    buy_price = None if raw.get("buyPrice") is None else _amount(raw, "buyPrice")
    body: Json = {
        "complexId": complex_id,
        "complexName": _text(raw, "complexName"),
        "umd": _text(raw, "umd"),
        "area": _choice(raw, "area", AREAS),
        "areaLabel": _text(raw, "areaLabel"),
        "buyDate": _date(raw, "buyDate"),
        "buyPrice": buy_price,
    }
    key = "|".join(
        [
            str(complex_id),
            str(body["area"]),
            str(body["buyDate"]),
            buy_price if buy_price is not None else "market",
        ]
    )
    return body, key


_PARSERS = {"stock": _stock, "crypto": _crypto, "deposit": _deposit, "realestate": _realestate}


def validate(asset: AssetClass, raw: object) -> HistoryCondition:
    """조건을 검증하고 저장할 칸·식별자·글을 만든다. 어기면 `InvalidHistory`(어느 칸인지 말한다)."""
    if not isinstance(raw, dict):
        raise InvalidHistory("condition: 객체여야 합니다")
    body, key = _PARSERS[asset](raw)
    if len(key) > MAX_KEY:
        raise InvalidHistory(f"condition: 식별자가 {MAX_KEY}자를 넘습니다")
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return HistoryCondition(asset=asset, key=key, body=body, text=text)
