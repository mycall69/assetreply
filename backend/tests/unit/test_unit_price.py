"""단가 등락 (013 반복 2026-10-09 T085) — spec FR-011a, SC-010, research R13-18, data-model 3.2.

비교 표의 시작일 단가·기준일 단가·등락(차이·등락률). 차이·등락률은 서버의 `Decimal`이다(원칙 VI).
값이 하나라도 없으면 비운다 — 가까운 값으로 메우지 않는다(원칙 V). 금리는 %p 차이만이고 등락률이
없다 (사용자 답 2026-10-09). 분할 누적 비율 글자는 수정주가가 시작일 종가를 나눈 그 비율이다.
"""

from __future__ import annotations

import ast
import datetime as dt
import pathlib
from decimal import Decimal

import pytest

from src.simulation.reinvest import SplitOn
from src.simulation.split_adjust import split_restated_close
from src.simulation.unit_price import PricePoint, split_ratio, unit_price

P = Decimal
D = dt.date.fromisoformat
START, END = D("2010-01-04"), D("2026-10-07")


def share(start: str | None, end: str | None) -> tuple[PricePoint, PricePoint]:
    return (PricePoint(START, None if start is None else P(start)),
            PricePoint(END, None if end is None else P(end),
                       missing=None if end is not None else "no_price"))


class Test차이와_등락률:
    def test_오르면_차이와_비율이다(self) -> None:
        u = unit_price("share", "split_restated_close", "KRW",
                       *share("16180.000000", "55000.000000"), split_ratio="50:1")
        assert u.change == P("38820.000000")
        assert u.change_rate == P("2.399258")  # 38820 ÷ 16180 = 2.3992583…
        assert (u.kind, u.basis, u.currency, u.split_ratio) == (
            "share", "split_restated_close", "KRW", "50:1")

    def test_내리면_음수다(self) -> None:
        u = unit_price("coin", "daily_open", "USD", *share("100", "80"))
        assert (u.change, u.change_rate) == (P("-20"), P("-0.200000"))

    def test_등락률은_소수_6자리다(self) -> None:
        u = unit_price("share", "split_restated_close", "USD", *share("3", "4"))
        assert u.change_rate is not None
        assert u.change_rate.as_tuple().exponent == -6
        assert u.change_rate == P("0.333333")

    def test_금리는_차이만이고_등락률이_없다(self) -> None:
        u = unit_price("rate", "published_rate", None, PricePoint(D("2015-01-01"), P("2.10")),
                       PricePoint(D("2026-08-01"), P("2.45"), provisional=True))
        assert (u.change, u.change_rate, u.currency) == (P("0.35"), None, None)
        assert u.as_of.provisional is True

    def test_금리_0에서의_차이는_있다(self) -> None:
        u = unit_price("rate", "published_rate", None, PricePoint(D("2021-01-01"), P("0")),
                       PricePoint(D("2026-08-01"), P("0.5")))
        assert (u.change, u.change_rate) == (P("0.5"), None)

    @pytest.mark.parametrize(("start", "end"), [(None, "55000"), ("16180", None), ("0", "55000")],
                             ids=["시작 없음", "기준일 없음", "시작 0"])
    def test_값이_없거나_시작이_0이면_등락을_비운다(self, start: str | None,
                                           end: str | None) -> None:
        u = unit_price("share", "split_restated_close", "KRW", *share(start, end))
        assert (u.change, u.change_rate) == (None, None)

    def test_기준일_값이_없으면_까닭이_남는다(self) -> None:
        u = unit_price("home", "market_price", "KRW", PricePoint(D("2021-03-01"), P("2100000000")),
                       PricePoint(D("2026-10-01"), None, missing="no_trades"))
        assert (u.as_of.value, u.as_of.missing, u.change) == (None, "no_trades", None)


class Test분할_비율:
    def test_시작일_뒤의_분할만_곱한다(self) -> None:
        splits = [SplitOn(D("2009-05-01"), 2, 1), SplitOn(D("2018-05-04"), 50, 1)]
        assert split_ratio(splits, START) == "50:1"

    def test_시작일_당일의_분할은_이미_반영된_값이다(self) -> None:
        # 효력일 당일의 종가는 이미 분할 뒤 값이다 — split_restated_close와 같은 경계.
        assert split_ratio([SplitOn(START, 2, 1)], START) is None

    @pytest.mark.parametrize(("splits", "ratio"), [
        ([], None),
        ([SplitOn(D("2014-06-09"), 7, 1), SplitOn(D("2020-08-31"), 4, 1)], "28:1"),
        ([SplitOn(D("2019-01-02"), 1, 10)], "1:10"),
        ([SplitOn(D("2019-01-02"), 2, 1), SplitOn(D("2020-01-02"), 1, 2)], None),
        ([SplitOn(D("2019-01-02"), 3, 2)], "3:2"),
        ([SplitOn(D("2019-01-02"), 4, 2)], "2:1"),
    ], ids=["없음", "둘의 곱", "병합", "서로 지움", "3:2", "기약"])
    def test_누적_비율_글자(self, splits: list[SplitOn], ratio: str | None) -> None:
        assert split_ratio(splits, START) == ratio

    def test_수정주가와_같은_비율이다(self) -> None:
        # 분할 50:1이 낀 시작일 종가 809,000원 → 수정주가 16,180원. 비율 글자가 그 나눗셈을 말한다.
        splits = [SplitOn(D("2018-05-04"), 50, 1)]
        assert split_restated_close(P("809000"), START, splits) == P("16180.000000")
        assert split_ratio(splits, START) == "50:1"


class Test순수_모듈:
    def test_DB_HTTP를_임포트하지_않는다(self) -> None:
        source = pathlib.Path("src/simulation/unit_price.py").read_text(encoding="utf-8")
        modules = {
            n.module or "" for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)
        } | {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import)
             for a in n.names}
        banned = ("src.repository", "src.api", "src.db", "sqlalchemy", "aiohttp", "fastapi")
        assert not [m for m in modules if m.startswith(banned)]
