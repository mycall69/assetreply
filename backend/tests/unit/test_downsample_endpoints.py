"""다운샘플링의 끝점 보존 (T036).

FR-017b: 표시 점 수를 줄이는 처리를 적용하더라도 구간의 가장 최근 값은 항상 표시되어야
한다. 오늘 잠정값이 구간의 마지막 점이므로 여기서 탈락하면 사용자는 "오늘이 아직 안
들어왔나"와 "화면이 생략했나"를 구별할 수 없다.

현재 LTTB 구현은 첫 점과 끝 점을 항상 포함하므로 이 요건을 이미 만족한다(research R2-4).
**다만 그것은 알고리즘의 성질일 뿐 계약이 아니다.** 다운샘플링을 교체하면 조용히 깨지므로
명시적으로 검증한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.downsample import Point, lttb


def _points(n: int) -> list[Point]:
    base = dt.date(2020, 1, 1)
    return [Point(base + dt.timedelta(days=i), Decimal(1000 + (i % 37))) for i in range(n)]


def test_끝점이_항상_남는다() -> None:
    src = _points(5000)
    for target in (3, 10, 100, 2000):
        out = lttb(src, target=target)
        assert out[-1] == src[-1], f"target={target}에서 마지막 점이 사라졌다"


def test_첫점이_항상_남는다() -> None:
    src = _points(5000)
    for target in (3, 10, 100, 2000):
        assert lttb(src, target=target)[0] == src[0], f"target={target}"


def test_목표가_원본보다_크면_그대로_돌려준다() -> None:
    src = _points(50)
    assert lttb(src, target=500) == src


def test_경계_목표값에서도_끝점이_남는다() -> None:
    src = _points(1000)
    for target in (2, 3):
        out = lttb(src, target=target)
        assert out[0] == src[0] and out[-1] == src[-1], f"target={target}"
