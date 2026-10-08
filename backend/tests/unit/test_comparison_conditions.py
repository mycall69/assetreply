"""저장한 비교의 조건 검증·정규화 (013 T061) — FR-004, FR-016, SC-006, data-model 2.

저장하는 것은 **조건뿐**이다 — 자산군, 대상 목록(차례 있음), 공통 조건. 알려진 칸만 남기고(결과 키는
버린다) 정해진 차례로 직렬화한다. 금액은 **받은 글자 그대로**다 — 서버는 검증할 때만 `Decimal`로
읽는다(원칙 VI 해석, 012 R12-9). 틀린 칸은 422 메시지가 칸을 밝힌다 — 빠진 칸을 기본값으로 메워
저장하면 불러올 때 다른 조건으로 돈다.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from src.api.errors import InvalidComparison
from src.api.services.comparison_conditions import validate_condition, validate_name

SAMSUNG = {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"}
HYNIX = {"market": "KRX", "symbol": "000660.KS", "name": "SK하이닉스", "currency": "KRW"}
XLK = {"market": "NYSE", "symbol": "XLK", "name": "Technology Select Sector SPDR Fund",
       "currency": "USD"}
AAPL = {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD"}
BTC = {"coinId": 17, "symbol": "BTC", "name": "Bitcoin", "nameKo": "비트코인", "currency": "USD"}
ETH = {"coinId": 18, "symbol": "ETH", "name": "Ethereum", "nameKo": None, "currency": "USD"}
HELIO = {"complexId": 12, "name": "헬리오시티아파트", "umdName": "가락동", "area": "30k",
         "areaLabel": "30평대(국평)"}


def stock(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "v": 1, "asset": "stock", "method": "lump_sum", "frequency": None, "start": "2020-01-02",
        "amount": "10000000", "principalCurrency": "KRW", "reinvest": True,
        "targets": [SAMSUNG, XLK]}
    base.update(over)
    return base


def bad(raw: object, field: str) -> None:
    with pytest.raises(InvalidComparison) as caught:
        validate_condition(raw)
    assert str(caught.value).startswith(field), str(caught.value)


class Test정규화:
    def test_알려진_칸만_정해진_차례로_직렬화한다(self) -> None:
        cond = validate_condition({**stock(), "summary": {"profit": "1"}, "comparison": {},
                                   "series": [], "targets": [{**SAMSUNG, "rank": 3}, XLK]})
        assert cond.asset == "stock"
        assert cond.body == stock()
        assert cond.text == json.dumps(stock(), ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"))

    def test_금액은_받은_글자_그대로다(self) -> None:
        cond = validate_condition(stock(amount="10000000.50"))
        assert cond.body["amount"] == "10000000.50"
        assert '"amount":"10000000.50"' in cond.text

    def test_적립식은_주기가_있다(self) -> None:
        cond = validate_condition(stock(method="recurring", frequency="weekly"))
        assert cond.body["frequency"] == "weekly"

    def test_예금_부동산(self) -> None:
        deposit = validate_condition({
            "v": 1, "asset": "deposit", "method": "installment", "frequency": None,
            "start": "2015-01-15", "amount": "1000000", "principalCurrency": "KRW",
            "reinvest": None,
            "targets": [{"institution": "commercial_bank"}, {"institution": "mutual_finance"}]})
        assert deposit.asset == "deposit"
        realestate = validate_condition({
            "v": 1, "asset": "realestate", "method": "hold", "frequency": None,
            "start": "2021-03-15", "amount": None, "principalCurrency": "KRW", "reinvest": None,
            "targets": [HELIO, {**HELIO, "area": "20", "areaLabel": "20평대"}]})
        assert realestate.body["amount"] is None

    def test_외화_원금은_모든_대상이_그_통화일_때_된다(self) -> None:
        cond = validate_condition(stock(principalCurrency="USD", targets=[XLK, AAPL]))
        assert cond.body["principalCurrency"] == "USD"

    def test_가상자산(self) -> None:
        cond = validate_condition({**stock(asset="crypto", reinvest=None, targets=[BTC, ETH])})
        assert cond.body["targets"] == [BTC, ETH]


class Test거절:
    @pytest.mark.parametrize(("over", "field"), [
        ({"v": 2}, "v"),
        ({"asset": "fx"}, "asset"),
        ({"method": "hold"}, "method"),
        ({"method": "recurring", "frequency": None}, "frequency"),
        ({"frequency": "monthly"}, "frequency"),
        ({"start": "2020-1-2"}, "start"),
        ({"amount": "1e7"}, "amount"),
        ({"amount": "10,000,000"}, "amount"),
        ({"amount": "0"}, "amount"),
        ({"amount": 10000000}, "amount"),
        ({"principalCurrency": "USD"}, "principalCurrency"),
        ({"principalCurrency": "EUR", "targets": [XLK, AAPL]}, "principalCurrency"),
        ({"reinvest": None}, "reinvest"),
        ({"targets": [SAMSUNG]}, "targets"),
        ({"targets": [SAMSUNG, {**SAMSUNG}]}, "targets"),
        ({"targets": [SAMSUNG] + [{**SAMSUNG, "symbol": f"00000{i}.KS"} for i in range(10)]},
         "targets"),
        ({"targets": [SAMSUNG, {**XLK, "market": "LSE"}]}, "targets"),
        ({"targets": [SAMSUNG, {"market": "KRX", "symbol": "000660.KS"}]}, "targets"),
        ({"targets": "삼성전자"}, "targets"),
    ])
    def test_주식_조건의_틀린_칸(self, over: dict[str, object], field: str) -> None:
        bad(stock(**over), field)

    def test_예금은_다섯이_끝이고_금액은_정수다(self) -> None:
        base = {"v": 1, "asset": "deposit", "method": "deposit", "frequency": None,
                "start": "2015-01-15", "amount": "1000000", "principalCurrency": "KRW",
                "reinvest": None,
                "targets": [{"institution": "commercial_bank"}, {"institution": "savings_bank"}]}
        bad({**base, "amount": "1000000.5"}, "amount")
        bad({**base, "targets": [{"institution": "bank"}, {"institution": "savings_bank"}]},
            "targets")

    def test_정기_적금은_적금_있는_투자처만이다(self) -> None:
        bad({"v": 1, "asset": "deposit", "method": "installment", "frequency": None,
             "start": "2015-01-15", "amount": "1000000", "principalCurrency": "KRW",
             "reinvest": None,
             "targets": [{"institution": "commercial_bank"}, {"institution": "savings_bank"}]},
            "targets")

    def test_부동산은_금액이_없고_평형_키가_정해져_있다(self) -> None:
        base = {"v": 1, "asset": "realestate", "method": "hold", "frequency": None,
                "start": "2021-03-15", "amount": None, "principalCurrency": "KRW",
                "reinvest": None,
                "targets": [HELIO, {**HELIO, "area": "20", "areaLabel": "20평대"}]}
        bad({**base, "amount": "1000"}, "amount")
        bad({**base, "targets": [HELIO, {**HELIO, "area": "99"}]}, "targets")

    def test_객체가_아니면_거절한다(self) -> None:
        bad("조건", "condition")


class Test이름:
    def test_앞뒤_공백을_뺀다(self) -> None:
        name = "주식 3개 · 2020-01-02 · 일시금"
        assert validate_name(f"  {name} ") == name

    @pytest.mark.parametrize("name", ["", "   ", None, 3, "가" * 101])
    def test_빈_이름_100자_초과는_거절한다(self, name: object) -> None:
        with pytest.raises(InvalidComparison) as caught:
            validate_name(name)
        assert str(caught.value).startswith("name")

    def test_100자까지_된다(self) -> None:
        assert validate_name("가" * 100) == "가" * 100


class Test금액_비계산:
    def test_모듈에_곱셈_나눗셈_자릿수_맞춤이_없다(self) -> None:
        # 012 test_history_conditions와 같은 검사 — 금액은 기록이고 이 모듈은 계산하지 않는다.
        source = pathlib.Path("src/api/services/comparison_conditions.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        ops = {type(n.op) for n in ast.walk(tree) if isinstance(n, ast.BinOp)}
        assert not ops & {ast.Mult, ast.Div, ast.FloorDiv}
        assert ".quantize" not in source
