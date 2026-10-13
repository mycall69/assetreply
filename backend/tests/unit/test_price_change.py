"""투자 성과표의 가격 등락 — 순수 함수 (014 반복 2026-10-13b T221) — spec FR-048, data-model 19.3,
research R14-38.

- 등락은 외환 표·요약 칸과 **같은 함수**(`fx_change.rate_change`)다 — 등락폭은 저장 정밀도, 등락률은
  소수 둘째 자리, 직전 0 이하면 비율이 없다
- 주식 표는 원주가다. 비교 날짜 뒤 ~ 행 날짜에 효력이 생긴 분할·병합이 있으면 **비교 가격을 그 누적
  비율로 맞춘다**(× 분모/분자, 소수 6자리 `ROUND_HALF_UP` — 010 `split_restated_close`와 같다).
  원주가 그대로 견주면 1:4 분할이 −75%로 보인다(FR-048 실패 양상 *조용히 틀림*)
- 효력일이 비교 날짜 당일이면 비교 가격이 이미 분할 뒤라 맞추지 않는다. 행 날짜 당일이면 맞춘다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.fx_change import Quote, rate_change
from src.simulation.price_change import price_change
from src.simulation.reinvest import SplitOn

D = dt.date.fromisoformat
BEFORE, DAY = D("2024-06-07"), D("2024-06-10")


def change(current: str, previous: str, splits: tuple[SplitOn, ...] = (),
           compared_to: dt.date = BEFORE, day: dt.date = DAY):  # type: ignore[no-untyped-def]
    return price_change(Decimal(current), Decimal(previous), compared_to=compared_to, day=day,
                        splits=splits)


class Test등락:
    @pytest.mark.parametrize(("current", "previous", "direction"), [
        ("110", "100", "up"), ("90", "100", "down"), ("100", "100", "flat")])
    def test_방향(self, current: str, previous: str, direction: str) -> None:
        got = change(current, previous)
        assert got is not None
        assert got.direction == direction
        assert got.compared_to == BEFORE

    def test_등락폭은_저장_정밀도_그대로다(self) -> None:
        got = change("84000.000000", "83500.000000")
        assert got is not None
        assert str(got.absolute) == "500.000000"
        assert str(got.percent) == "0.60"

    @pytest.mark.parametrize(("current", "previous"), [
        ("100.125", "100"), ("1", "3"), ("62431.65234375", "61168.0625"),
        ("0.00001234", "0.00001200"), ("50000", "50000"), ("1197.7", "1239")])
    def test_외환_표와_같은_함수다(self, current: str, previous: str) -> None:
        got = change(current, previous)
        same = rate_change(Decimal(current), Quote(BEFORE, Decimal(previous)))
        assert got is not None and same is not None
        assert (got.absolute, got.percent, got.direction, got.compared_to) == (
            same.absolute, same.percent, same.direction, same.compared_to)
        assert got.split_ratio is None

    def test_등락률_반올림은_짝수_쪽이다(self) -> None:
        got = change("100.125", "100")
        assert got is not None
        assert str(got.percent) == "0.12"

    def test_가격이_없으면_없다(self) -> None:
        assert price_change(None, Decimal("1"), compared_to=BEFORE, day=DAY) is None
        assert price_change(Decimal("1"), None, compared_to=BEFORE, day=DAY) is None

    @pytest.mark.parametrize(("current", "previous"), [
        ("10", "0"), ("10", "-37.63"), ("0", "100"), ("0", "0")])
    def test_가격이_0_이하면_없다(self, current: str, previous: str) -> None:
        # 주식·가상자산에는 0 이하 가격이 없다 — 출처가 값을 비운 날이다(T226 실측: 삼성전자
        # 2026-10-06 시가 0). 견주면 −100%와 이튿날의 ▲전액이 사실처럼 보인다(원칙 V — 외환 표
        # 규칙과 다르다)
        assert change(current, previous) is None


class Test분할_맞춤:
    def test_10대1_분할이면_직전_값을_10으로_나눠_견준다(self) -> None:
        got = change("121.790000", "1208.880000", (SplitOn(DAY, 10, 1),))
        assert got is not None
        assert str(got.absolute) == "0.902000"
        assert str(got.percent) == "0.75"
        assert got.direction == "up"
        assert got.split_ratio == "10:1"

    def test_병합_1대10이면_직전_값에_10을_곱한다(self) -> None:
        got = change("52", "5", (SplitOn(DAY, 1, 10),))
        assert got is not None
        assert got.absolute == Decimal("2")
        assert str(got.percent) == "4.00"
        assert got.split_ratio == "1:10"

    def test_나누어떨어지지_않는_비율은_소수_6자리_반올림이다(self) -> None:
        got = change("70", "100", (SplitOn(DAY, 3, 2),))
        assert got is not None
        # 100 × 2/3 = 66.6666…7 → 66.666667(ROUND_HALF_UP) — 010 split_restated_close와 같은 자릿수
        assert got.absolute == Decimal("70") - Decimal("66.666667")
        assert got.split_ratio == "3:2"

    def test_사이에_분할이_둘이면_누적_비율이다(self) -> None:
        splits = (SplitOn(D("2024-06-08"), 2, 1), SplitOn(DAY, 5, 1))
        got = change("101", "1000", splits)
        assert got is not None
        assert got.absolute == Decimal("1")
        assert got.split_ratio == "10:1"

    def test_서로_지워지면_맞추지_않는다(self) -> None:
        splits = (SplitOn(D("2024-06-08"), 2, 1), SplitOn(DAY, 1, 2))
        got = change("101", "100", splits)
        assert got is not None
        assert got.absolute == Decimal("1")
        assert got.split_ratio is None

    @pytest.mark.parametrize(("effective", "applied"), [
        (D("2024-06-01"), False),   # 비교 날짜 앞 — 두 가격 모두 분할 뒤
        (BEFORE, False),            # 비교 날짜 당일 — 비교 가격이 이미 분할 뒤
        (D("2024-06-08"), True),    # 사이
        (DAY, True),                # 행 날짜 당일 — 그 날 가격은 분할 뒤
        (D("2024-06-11"), False),   # 행 날짜 뒤 — 두 가격 모두 분할 전
    ])
    def test_효력일의_경계(self, effective: dt.date, applied: bool) -> None:
        got = change("100", "400", (SplitOn(effective, 4, 1),))
        assert got is not None
        assert (got.split_ratio == "4:1") is applied
        assert got.absolute == (Decimal("0") if applied else Decimal("-300"))
