"""이력 조건 — 자산군마다의 검증·직렬화·식별자 (012 T039) — FR-011, FR-013, data-model 2, research
R12-9.

- 식별자는 서버가 조건에서 계산한다. 규칙은 지금 화면 lib(`conditionId` 계열)과 **글자까지 같다** —
  옮긴 항목의 식별자가 바뀌지 않는다. 아래 예시는
  화면 lib
  테스트(`simulationHistory*.test.ts`·`cryptoHistory*`·`depositHistory*`·`realEstateHistory`)의
  식별자 그대로다
- 011 전 형식(`mode`·`frequency`·`product` 없음)은 일시금·정기예금의 식별자다(011 FR-033)
- 원금·매입가는 받은 글자 그대로 둔다 — 서버는 그것으로 계산하지 않는다(원칙 VI 해석 — plan
  Complexity Tracking, 사용자 확인 2026-10-06)
- 결과(평가·수익률)를 저장하지 않는다 — 조건 칸 밖의 키는 버린다(005 R5-9)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.api.errors import InvalidHistory, UnknownAsset
from src.api.services.history_conditions import ASSET_CLASSES, parse_asset, validate

STOCK = {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"}
STOCK_LUMP = {
    "stock": STOCK,
    "start": "2024-01-15",
    "principal": "500000",
    "principalCurrency": "KRW",
    "reinvest": True,
}
COIN = {
    "coinId": 17,
    "symbol": "BTC",
    "name": "Bitcoin",
    "nameKo": "비트코인",
    "slug": "bitcoin",
    "currency": "USD",
}
CRYPTO_LUMP = {
    "coin": COIN,
    "start": "2024-01-15",
    "principal": "10000",
    "principalCurrency": "KRW",
}
DEPOSIT = {"institution": "commercial_bank", "start": "2015-01-15", "principal": "1000000"}
APT = {
    "complexId": 4,
    "complexName": "헬리오시티",
    "umd": "1171010700",
    "area": "30k",
    "areaLabel": "30평대",
    "buyDate": "2021-03-15",
    "buyPrice": None,
}


class Test자산군:
    def test_자산군은_넷이다(self) -> None:
        assert ASSET_CLASSES == ("stock", "crypto", "deposit", "realestate")

    def test_모르는_자산군은_막는다(self) -> None:
        assert parse_asset("crypto") == "crypto"
        with pytest.raises(UnknownAsset):
            parse_asset("settings")


class Test식별자_대조:
    """화면 lib의 식별자와 글자까지 같다 — 옮긴 항목이 다른 항목이 되지 않는다."""

    def test_주식(self) -> None:
        assert validate("stock", STOCK_LUMP).key == "KRX|005930.KS|2024-01-15|500000|KRW|R"
        recurring = {**STOCK_LUMP, "mode": "recurring", "frequency": "monthly"}
        assert (
            validate("stock", recurring).key
            == "KRX|005930.KS|2024-01-15|500000|KRW|R|recurring:monthly"
        )
        assert validate("stock", {**STOCK_LUMP, "reinvest": False}).key.endswith("|N")

    def test_주식_적립식에_주기가_없으면_매달이다(self) -> None:
        assert validate("stock", {**STOCK_LUMP, "mode": "recurring"}).key.endswith(
            "|recurring:monthly"
        )

    def test_가상자산(self) -> None:
        assert validate("crypto", CRYPTO_LUMP).key == "17|2024-01-15|10000|KRW"
        daily = {**CRYPTO_LUMP, "mode": "recurring", "frequency": "daily"}
        assert validate("crypto", daily).key == "17|2024-01-15|10000|KRW|recurring:daily"

    def test_예금(self) -> None:
        assert validate("deposit", DEPOSIT).key == "commercial_bank|2015-01-15|1000000"
        installment = {**DEPOSIT, "product": "installment"}
        assert (
            validate("deposit", installment).key == "commercial_bank|2015-01-15|1000000|installment"
        )

    def test_부동산(self) -> None:
        assert validate("realestate", APT).key == "4|30k|2021-03-15|market"
        assert (
            validate("realestate", {**APT, "buyPrice": "1350000000"}).key
            == "4|30k|2021-03-15|1350000000"
        )

    def test_011_전_형식은_일시금_정기예금의_식별자다(self) -> None:
        old_stock = {
            "id": "KRX|005930.KS|2020-01-02|10000000|KRW|R",
            "stock": STOCK,
            "start": "2020-01-02",
            "principal": "10000000",
            "principalCurrency": "KRW",
            "reinvest": True,
            "savedAt": "2026-09-01T00:00:00.000Z",
        }
        assert validate("stock", old_stock).key == "KRX|005930.KS|2020-01-02|10000000|KRW|R"
        old_deposit = {
            "id": "saemaul|2020-01-15|10000000",
            "institution": "saemaul",
            "start": "2020-01-15",
            "principal": "10000000",
            "savedAt": "2026-09-01T00:00:00.000Z",
        }
        assert validate("deposit", old_deposit).key == "saemaul|2020-01-15|10000000"


class Test저장하는_칸:
    def test_조건_칸_밖의_키는_버린다(self) -> None:
        raw = {
            **STOCK_LUMP,
            "id": "아무거나",
            "savedAt": "2026-09-01T00:00:00Z",
            "profit": "123",
            "returnRate": "0.1",
        }
        body = validate("stock", raw).body
        assert set(body) == {"stock", "start", "principal", "principalCurrency", "reinvest"}

    def test_일시금에는_방식_칸이_없고_적립식만_있다(self) -> None:
        assert "mode" not in validate("stock", STOCK_LUMP).body
        body = validate("stock", {**STOCK_LUMP, "mode": "recurring", "frequency": "weekly"}).body
        assert (body["mode"], body["frequency"]) == ("recurring", "weekly")

    def test_직렬화는_칸_차례와_무관하게_같은_글이다(self) -> None:
        reordered = dict(reversed(list(STOCK_LUMP.items())))
        assert validate("stock", reordered).text == validate("stock", STOCK_LUMP).text

    def test_원금은_글자_그대로_돌아온다(self) -> None:
        condition = validate("stock", {**STOCK_LUMP, "principal": "10000000"})
        assert json.loads(condition.text)["principal"] == "10000000"
        assert condition.body["principal"] == "10000000"
        assert '"10000000"' in condition.text  # 수로 바뀌지 않는다

    def test_한글은_그대로_싣는다(self) -> None:
        assert "삼성전자" in validate("stock", STOCK_LUMP).text


class Test검증:
    @pytest.mark.parametrize(
        ("asset", "raw", "field"),
        [
            ("stock", {**STOCK_LUMP, "start": "2024-13-01"}, "start"),
            ("stock", {**STOCK_LUMP, "start": "어제"}, "start"),
            ("stock", {**STOCK_LUMP, "principal": "0"}, "principal"),
            ("stock", {**STOCK_LUMP, "principal": "-5"}, "principal"),
            ("stock", {**STOCK_LUMP, "principal": "1e7"}, "principal"),
            ("stock", {**STOCK_LUMP, "principal": 500000}, "principal"),
            ("stock", {**STOCK_LUMP, "reinvest": "true"}, "reinvest"),
            ("stock", {**STOCK_LUMP, "mode": "lump_sum"}, "mode"),
            ("stock", {**STOCK_LUMP, "mode": "recurring", "frequency": "hourly"}, "frequency"),
            ("stock", {k: v for k, v in STOCK_LUMP.items() if k != "stock"}, "stock"),
            ("stock", {**STOCK_LUMP, "stock": {**STOCK, "symbol": "x" * 201}}, "stock.symbol"),
            ("crypto", {**CRYPTO_LUMP, "coin": {**COIN, "coinId": "17"}}, "coin.coinId"),
            ("deposit", {**DEPOSIT, "product": "deposit"}, "product"),
            ("deposit", {**DEPOSIT, "institution": "bank"}, "institution"),
            ("realestate", {**APT, "buyDate": "2021-02-30"}, "buyDate"),
            ("realestate", {**APT, "buyPrice": "0"}, "buyPrice"),
            ("realestate", {**APT, "area": "100"}, "area"),
        ],
    )
    def test_어기면_칸을_말하며_막는다(
        self, asset: str, raw: dict[str, object], field: str
    ) -> None:
        with pytest.raises(InvalidHistory) as caught:
            validate(asset, raw)  # type: ignore[arg-type]
        assert field in str(caught.value)

    def test_조건이_객체가_아니면_막는다(self) -> None:
        with pytest.raises(InvalidHistory):
            validate("stock", ["not", "an", "object"])

    def test_식별자가_255자를_넘으면_막는다(self) -> None:
        long_stock = {**STOCK, "symbol": "S" * 120, "market": "M" * 120}
        with pytest.raises(InvalidHistory):
            validate("stock", {**STOCK_LUMP, "stock": long_stock})


class Test원금으로_계산하지_않는다:
    """원칙 VI 해석의 장치(plan Complexity Tracking — 사용자 확인 2026-10-06) — 이력 모듈은
    원금·매입가로 산술하지 않는다. 검증의
    `Decimal(…)` 읽기뿐이다. 곱셈·나눗셈·`quantize`가 없어야 한다 — 덧셈·뺄셈은 보관 기간의 시각
    계산(지금 − 기간)에만 쓴다."""

    ROOT = Path(__file__).resolve().parents[2]
    MODULES = (
        "src/api/services/history_conditions.py",
        "src/api/services/history.py",
        "src/repository/simulation_history.py",
    )

    @pytest.mark.parametrize("module", MODULES)
    def test_산술_연산이_없다(self, module: str) -> None:
        tree = ast.parse((self.ROOT / module).read_text(encoding="utf-8"))
        arithmetic = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv))
        ]
        assert arithmetic == [], module
        quantize = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "quantize"
        ]
        assert quantize == [], module
