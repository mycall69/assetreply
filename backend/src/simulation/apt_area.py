"""평형 일곱 구분 (T021) — 009 FR-004, research R9-2.

출처는 전용면적(㎡)만 준다. 시세·거래 건수는 같은 단지·같은 **평형 구분** 안에서 센다. 경계는 명세의
고정 표이고 헬리오시티 스프레드시트(2020-01~2023-09, 225칸)와 같다:

    10평대        50㎡ 미만
    20평대        50㎡ 이상  70㎡ 미만
    30평대(국평)   70㎡ 이상  85㎡ 이하   ← 국민주택규모 85㎡로 가른다
    30평대(대형)   85㎡ 초과 105㎡ 미만
    40평대        105㎡ 이상 135㎡ 미만
    50평대        135㎡ 이상 165㎡ 미만
    60평대 이상    165㎡ 이상

면적은 `Decimal`로 비교한다 — 84.99 같은 경계 근처 값이 부동소수점으로 흔들리면 다른 구분의 시세를
자기 시세로 읽는다. 구분은 저장하지 않는다(data-model 3절) — 경계가 바뀌어도 다시 받지 않는다.

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: 국민주택규모(전용㎡). 이 면적을 넘으면 취득세에 농어촌특별세가 붙는다(FR-020).
NATIONAL_HOUSING_SIZE = Decimal(85)


class UnknownArea(ValueError):  # noqa: N818 — API `invalid_query`의 사유다
    """모르는 평형 구분 키."""

    def __init__(self, key: str) -> None:
        super().__init__(f"모르는 평형 구분입니다: {key}")
        self.key = key


@dataclass(frozen=True, slots=True)
class AreaBucket:
    """평형 구분 하나. 경계가 없는 쪽은 `None`이다."""

    key: str
    label: str
    min_area: Decimal | None
    min_inclusive: bool
    max_area: Decimal | None
    max_inclusive: bool

    def contains(self, area: Decimal) -> bool:
        if self.min_area is not None:
            if area < self.min_area or (area == self.min_area and not self.min_inclusive):
                return False
        if self.max_area is not None:
            if area > self.max_area or (area == self.max_area and not self.max_inclusive):
                return False
        return True

    @property
    def exceeds_85(self) -> bool:
        """이 구분의 모든 면적이 85㎡를 넘는가 — 농어촌특별세 판정(FR-020)."""
        return self.min_area is not None and self.min_area >= NATIONAL_HOUSING_SIZE


AREA_BUCKETS: tuple[AreaBucket, ...] = (
    AreaBucket("10", "10평대", None, False, Decimal(50), False),
    AreaBucket("20", "20평대", Decimal(50), True, Decimal(70), False),
    AreaBucket("30k", "30평대(국평)", Decimal(70), True, NATIONAL_HOUSING_SIZE, True),
    AreaBucket("30l", "30평대(대형)", NATIONAL_HOUSING_SIZE, False, Decimal(105), False),
    AreaBucket("40", "40평대", Decimal(105), True, Decimal(135), False),
    AreaBucket("50", "50평대", Decimal(135), True, Decimal(165), False),
    AreaBucket("60", "60평대 이상", Decimal(165), True, None, False),
)

_BY_KEY = {bucket.key: bucket for bucket in AREA_BUCKETS}


def area_bucket(excl_area: Decimal) -> AreaBucket:
    """전용면적이 드는 구분. 구분은 빈틈 없이 모든 양수 면적을 덮는다."""
    for bucket in AREA_BUCKETS:
        if bucket.contains(excl_area):
            return bucket
    raise ValueError(f"면적이 어느 구분에도 들지 않습니다: {excl_area}")


def bucket_by_key(key: str) -> AreaBucket:
    try:
        return _BY_KEY[key]
    except KeyError:
        raise UnknownArea(key) from None
