"""동기 수집 임계값 테스트 (T037).

FR-035/035a/035b: 필요 구간이 임계값 이하면 대기 후 결과, 초과하면 즉시 진행 상태.
"""
from __future__ import annotations

import datetime as dt

from src.api.services.collection_gate import CollectionDecision, decide_collection


def test_임계값_이하면_동기_대기다() -> None:
    d = decide_collection(missing_days=29, threshold_days=30)
    assert d is CollectionDecision.WAIT


def test_임계값과_같으면_동기_대기다() -> None:
    assert decide_collection(missing_days=30, threshold_days=30) is CollectionDecision.WAIT


def test_임계값_초과면_백그라운드다() -> None:
    assert decide_collection(missing_days=31, threshold_days=30) is CollectionDecision.BACKGROUND


def test_30년치는_백그라운드다() -> None:
    days = (dt.date(2026, 8, 29) - dt.date(1995, 1, 1)).days
    assert decide_collection(missing_days=days, threshold_days=30) is CollectionDecision.BACKGROUND


def test_수집이_필요없으면_대기도_없다() -> None:
    assert decide_collection(missing_days=0, threshold_days=30) is CollectionDecision.NONE


def test_음수는_수집_불필요로_간주한다() -> None:
    assert decide_collection(missing_days=-5, threshold_days=30) is CollectionDecision.NONE
