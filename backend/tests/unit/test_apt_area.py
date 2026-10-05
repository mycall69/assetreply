"""평형 일곱 구분 (T013) — 009 FR-004, research R9-2.

DB·HTTP 없는 순수 함수다(헌법 원칙 IV). 경계는 명세의 고정 표다 — 10평대 50㎡ 미만, 20평대 50~70㎡
미만, 30평대(국평) 70~85㎡ **이하**, 30평대(대형) 85㎡ 초과~105㎡ 미만, 40평대 105~135㎡ 미만,
50평대 135~165㎡ 미만, 60평대 이상 165㎡ 이상. 국평과 대형은 국민주택규모 85㎡로 가른다.

면적은 `Decimal`로 비교한다 — 84.99 같은 경계 근처 값이 부동소수점으로 흔들리면 다른 구분의 시세를
자기 시세로 읽는다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.simulation.apt_area import AREA_BUCKETS, UnknownArea, area_bucket, bucket_by_key

A = Decimal


def test_일곱_구분의_순서와_이름() -> None:
    assert [b.key for b in AREA_BUCKETS] == ["10", "20", "30k", "30l", "40", "50", "60"]
    assert [b.label for b in AREA_BUCKETS] == [
        "10평대", "20평대", "30평대(국평)", "30평대(대형)", "40평대", "50평대", "60평대 이상",
    ]


@pytest.mark.parametrize(("area", "key"), [
    ("0.01", "10"), ("49.99", "10"),
    ("50", "20"), ("50.00", "20"), ("69.99", "20"),
    ("70", "30k"), ("84.99", "30k"), ("85", "30k"), ("85.00", "30k"),
    ("85.01", "30l"), ("104.99", "30l"),
    ("105", "40"), ("134.99", "40"),
    ("135", "50"), ("164.99", "50"),
    ("165", "60"), ("300.5", "60"),
])
def test_경계_값이_정확히_갈린다(area: str, key: str) -> None:
    assert area_bucket(A(area)).key == key


@pytest.mark.parametrize(("area", "key"), [
    # 헬리오시티 실측 면적(research R9-2) — 스프레드시트와 225칸이 같은 경계다
    ("39.1", "10"), ("39.12", "10"), ("39.17", "10"), ("39.86", "10"),
    ("49.19", "10"), ("49.21", "10"), ("49.29", "10"), ("49.32", "10"),
    ("59.96", "20"),
    ("84.94", "30k"), ("84.99", "30k"),
    ("99.6", "30l"),
    ("110.44", "40"), ("110.66", "40"), ("130.06", "40"),
    ("150.07", "50"), ("150.09", "50"),
])
def test_헬리오시티_면적(area: str, key: str) -> None:
    assert area_bucket(A(area)).key == key


def test_화면용_경계표() -> None:
    """화면이 경계표를 그대로 보인다(FR-004) — 자기 집이 어느 구분인지 알아야 한다."""
    by_key = {b.key: b for b in AREA_BUCKETS}
    ten = by_key["10"]
    assert (ten.min_area, ten.max_area, ten.max_inclusive) == (None, A(50), False)
    assert (by_key["30k"].min_area, by_key["30k"].min_inclusive) == (A(70), True)
    assert (by_key["30k"].max_area, by_key["30k"].max_inclusive) == (A(85), True)
    assert (by_key["30l"].min_area, by_key["30l"].min_inclusive) == (A(85), False)
    assert (by_key["30l"].max_area, by_key["30l"].max_inclusive) == (A(105), False)
    assert (by_key["60"].min_area, by_key["60"].max_area) == (A(165), None)


def test_구분이_빈틈도_겹침도_없다() -> None:
    """0.01㎡ 간격으로 300㎡까지 모든 면적이 정확히 한 구분에 든다."""
    area = A("0.01")
    while area <= A(300):
        assert sum(1 for b in AREA_BUCKETS if b.contains(area)) == 1, area
        area += A("0.01")


def test_85제곱미터_초과_여부() -> None:
    """취득세 농어촌특별세는 전용 85㎡ 초과에만 붙는다(FR-020) — 구분으로 판정할 수 있어야 한다."""
    assert [b.key for b in AREA_BUCKETS if b.exceeds_85] == ["30l", "40", "50", "60"]


def test_키로_찾기() -> None:
    assert bucket_by_key("30k").label == "30평대(국평)"
    with pytest.raises(UnknownArea):
        bucket_by_key("30")
