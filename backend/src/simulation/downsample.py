"""LTTB 다운샘플링 (T077).

**헌법 원칙 V가 이 알고리즘을 결정했다.** 평균·OHLC 집계는 원본에 없는 값을 만들어내
"임의 보간 금지"에 걸린다. LTTB(Largest-Triangle-Three-Buckets)는 원본 포인트 중
시각적으로 중요한 것을 *선택*만 하므로 새 값을 생성하지 않는다 (research R5).

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다 (헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

MIN_TARGET = 2


@dataclass(frozen=True, slots=True)
class Point:
    """시계열 한 점. 값은 원본 그대로의 `Decimal`이다."""

    date: dt.date
    value: Decimal


def lttb(points: list[Point], *, target: int) -> list[Point]:
    """포인트 수를 `target` 이하로 줄인다. 첫 점과 마지막 점은 항상 남긴다.

    삼각형 넓이가 가장 큰 점을 버킷마다 하나씩 고른다. 넓이가 크다는 것은 추세가
    꺾이는 지점이라는 뜻이라, 급등락 구간이 평탄화되지 않는다.

    면적 계산에만 `float`을 쓴다. 이 값은 **선택 기준일 뿐 출력에 들어가지 않으므로**
    헌법 원칙 VI(금융 계산에 float 금지)에 저촉되지 않는다. 반환되는 값은 언제나 입력의
    `Decimal` 원본이다.
    """
    if target < MIN_TARGET:
        raise ValueError(f"target은 {MIN_TARGET} 이상이어야 합니다: {target}")
    if not points:
        return []
    if len(points) <= target:
        return list(points)
    if target == MIN_TARGET:
        # 버킷이 0개라 일반 경로의 bucket_size 계산이 0으로 나눈다.
        # 목표가 2면 첫 점과 마지막 점만 남기는 것이 정의상 유일한 답이다.
        return [points[0], points[-1]]

    ordinals = [p.date.toordinal() for p in points]
    values = [float(p.value) for p in points]

    result = [points[0]]
    bucket_size = (len(points) - 2) / (target - 2)
    prev_index = 0

    for i in range(target - 2):
        # 다음 버킷의 평균 좌표 — 삼각형의 세 번째 꼭짓점으로만 쓴다
        next_start = int((i + 1) * bucket_size) + 1
        next_end = min(int((i + 2) * bucket_size) + 1, len(points))
        if next_start >= next_end:
            next_start, next_end = next_end - 1, next_end
        span = next_end - next_start
        avg_x = sum(ordinals[next_start:next_end]) / span
        avg_y = sum(values[next_start:next_end]) / span

        start = int(i * bucket_size) + 1
        end = min(int((i + 1) * bucket_size) + 1, len(points) - 1)
        px, py = ordinals[prev_index], values[prev_index]

        best_index, best_area = start, -1.0
        for j in range(start, max(end, start + 1)):
            area = abs((px - avg_x) * (values[j] - py) - (px - ordinals[j]) * (avg_y - py))
            if area > best_area:
                best_area, best_index = area, j

        result.append(points[best_index])
        prev_index = best_index

    result.append(points[-1])
    return result
