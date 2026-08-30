"""ECOS 응답 파싱 계약 테스트 (T029, T030).

contracts/ecos-adapter.md의 응답 행 필드 규약을 검증한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.ingestion.ecos.parser import parse_search_response
from src.ingestion.protocols import FetchOutcome

from .conftest import load


def test_정상_응답을_도메인_타입으로_변환한다() -> None:
    result = parse_search_response(load("search_ok.json"), status=200)
    assert result.outcome is FetchOutcome.OK
    assert len(result.quotes) == 3
    assert result.quotes[0].quote_date == dt.date(2005, 3, 15)


def test_쉼표가_포함된_값을_Decimal로_변환한다() -> None:
    """`DATA_VALUE`는 '1,012.30' 형태로 온다 (contracts/ecos-adapter.md)."""
    q = parse_search_response(load("search_ok.json"), status=200).quotes
    assert q[1].base_rate == Decimal("1003.2")
    assert isinstance(q[0].base_rate, Decimal)


def test_쉼표가_없는_값도_처리한다() -> None:
    q = parse_search_response(load("search_ok.json"), status=200).quotes
    assert q[2].base_rate == Decimal("1003.7")


def test_매매기준율이_아닌_항목은_걸러낸다() -> None:
    """`ITEM_NAME2`가 채워져 오는 경우의 안전망.

    실측 확인 결과 731Y001의 `ITEM_NAME2`는 `null`이라 필터가 통과된다. 다만 다른
    통계표나 향후 변경에서 세부 항목이 섞여 올 수 있으므로 필터를 유지한다.
    """
    q = parse_search_response(load("search_mixed_items.json"), status=200).quotes
    assert len(q) == 2
    assert [x.quote_date.day for x in q] == [15, 16]
    assert q[0].base_rate == Decimal("1012.30")


def test_원본_응답을_보존한다() -> None:
    """FR-004a: 원본 응답을 보존한다."""
    body = load("search_ok.json")
    assert parse_search_response(body, status=200).raw_body == body


def test_JPY는_100엔_단위를_보존한다() -> None:
    """FR-007: JPY는 100엔당 원화로 고시된다.

    실측 확인: 단위는 `UNIT_NAME`(그냥 '원')이 아니라 `ITEM_NAME1`('원/일본엔(100엔)')에
    있다. `UNIT_NAME`만 보면 값이 100배 틀어진다.
    """
    q = parse_search_response(load("search_ok_jpy.json"), status=200).quotes
    assert all(x.quote_unit == 100 for x in q)
    assert q[0].base_rate == Decimal("1123.62")


def test_USD는_1단위다() -> None:
    q = parse_search_response(load("search_ok.json"), status=200).quotes
    assert all(x.quote_unit == 1 for x in q)


def test_결과가_날짜_오름차순이다() -> None:
    q = parse_search_response(load("search_ok.json"), status=200).quotes
    assert list(q) == sorted(q, key=lambda x: x.quote_date)
