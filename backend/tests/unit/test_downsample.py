"""LTTB 다운샘플링 테스트 (T072, T073).

**헌법 원칙 V가 이 알고리즘을 결정했다.** 평균·OHLC 집계는 원본에 없는 값을 만들어내
"임의 보간 금지"에 걸린다. LTTB는 원본 포인트를 *선택*만 하므로 위반하지 않는다
(research R5).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.downsample import Point, lttb


def _series(values: list[str], start: dt.date = dt.date(2000, 1, 1)) -> list[Point]:
    return [Point(start + dt.timedelta(days=i), Decimal(v)) for i, v in enumerate(values)]


class Test값을_만들지_않는다:
    """헌법 원칙 V — 출력은 반드시 입력의 부분집합이다."""

    def test_출력의_모든_값이_입력에_존재한다(self) -> None:
        src = _series([str(1000 + (i * 37) % 500) for i in range(500)])
        out = lttb(src, target=50)
        src_set = {(p.date, p.value) for p in src}
        for p in out:
            assert (p.date, p.value) in src_set, f"입력에 없는 값이 생성됨: {p}"

    def test_새로운_날짜를_만들지_않는다(self) -> None:
        src = _series([str(1000 + i) for i in range(200)])
        dates = {p.date for p in src}
        assert all(p.date in dates for p in lttb(src, target=20))

    def test_평균값이_섞이지_않는다(self) -> None:
        """두 값의 평균이 결과에 나타나면 집계가 일어난 것이다."""
        src = _series(["100", "200", "300", "400"])
        out = lttb(src, target=3)
        assert Decimal("150") not in {p.value for p in out}
        assert Decimal("250") not in {p.value for p in out}


class Test극값_보존:
    def test_최대값이_남는다(self) -> None:
        values = [str(1000 + i) for i in range(200)]
        values[97] = "9999"
        out = lttb(_series(values), target=20)
        assert Decimal("9999") in {p.value for p in out}

    def test_최소값이_남는다(self) -> None:
        values = [str(1000 + i) for i in range(200)]
        values[143] = "1"
        out = lttb(_series(values), target=20)
        assert Decimal("1") in {p.value for p in out}

    def test_급등락_구간이_보존된다(self) -> None:
        """1997년 외환위기 같은 급변 구간이 뭉개지면 추이가 왜곡된다."""
        values = [str(800 + i) for i in range(100)]
        values[50] = "1962"
        out = lttb(_series(values), target=15)
        assert Decimal("1962") in {p.value for p in out}


class Test경계:
    def test_첫_점과_마지막_점은_항상_남는다(self) -> None:
        src = _series([str(1000 + i) for i in range(300)])
        out = lttb(src, target=30)
        assert out[0] == src[0]
        assert out[-1] == src[-1]

    def test_목표가_입력보다_크면_전부_반환한다(self) -> None:
        src = _series(["100", "200", "300"])
        assert lttb(src, target=100) == src

    def test_결과_개수가_목표를_넘지_않는다(self) -> None:
        src = _series([str(1000 + i) for i in range(1000)])
        assert len(lttb(src, target=100)) <= 100

    def test_시간_순서가_유지된다(self) -> None:
        src = _series([str(1000 + (i * 17) % 300) for i in range(400)])
        out = lttb(src, target=40)
        assert [p.date for p in out] == sorted(p.date for p in out)

    def test_목표가_2면_첫_점과_마지막_점만_남는다(self) -> None:
        """버킷이 0개가 되는 경계 — 일반 경로는 0으로 나눈다."""
        src = _series(["100", "200", "300", "400"])
        assert lttb(src, target=2) == [src[0], src[-1]]

    def test_빈_입력은_빈_출력이다(self) -> None:
        assert lttb([], target=10) == []

    def test_목표가_2_이하면_거부한다(self) -> None:
        with pytest.raises(ValueError):
            lttb(_series(["1", "2", "3"]), target=1)

    def test_30년치를_2000점으로_줄인다(self) -> None:
        """실제 규모 — 통화당 약 8,400점."""
        src = _series([str(1000 + (i * 13) % 900) for i in range(8400)])
        out = lttb(src, target=2000)
        assert len(out) <= 2000
        assert out[0] == src[0] and out[-1] == src[-1]
