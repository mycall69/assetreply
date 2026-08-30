"""항목 매핑 검증 계약 테스트 (T035, FR-015).

응답 필드는 `ITEM_CODE` / `ITEM_NAME`이다. `ITEM_CODE1`이 아니다 — 기존 Apps Script
구현이 이 지점에서 자동탐지에 계속 실패했다 (contracts/ecos-adapter.md).
"""
from __future__ import annotations

import pytest

from src.ingestion.ecos.errors import ItemMappingChanged
from src.ingestion.ecos.item_mapping import resolve_item_mapping

from .conftest import load


def test_알려진_코드가_이름과_일치하면_통과한다() -> None:
    m = resolve_item_mapping(load("item_list_ok.json"), "USD", known_code="0000001")
    assert m.source_item_code == "0000001"
    assert "미국" in m.source_item_name


def test_JPY와_EUR도_매핑된다() -> None:
    body = load("item_list_ok.json")
    assert resolve_item_mapping(body, "JPY", known_code="0000002").source_item_code == "0000002"
    assert resolve_item_mapping(body, "EUR", known_code="0000003").source_item_code == "0000003"


def test_코드가_바뀌면_이름으로_재탐색한다() -> None:
    """출처가 항목코드를 바꿔도 이름 패턴으로 찾아낸다."""
    m = resolve_item_mapping(load("item_list_changed.json"), "USD", known_code="0000001")
    assert m.source_item_code == "9900001"


def test_재탐색은_통화별로_올바른_항목을_고른다() -> None:
    body = load("item_list_changed.json")
    assert resolve_item_mapping(body, "JPY", known_code="0000002").source_item_code == "9900002"
    assert resolve_item_mapping(body, "EUR", known_code="0000003").source_item_code == "9900003"


def test_매핑_불가면_중단한다() -> None:
    """FR-015: 잘못된 통화의 값을 저장하느니 중단한다."""
    with pytest.raises(ItemMappingChanged):
        resolve_item_mapping(load("item_list_unmappable.json"), "USD", known_code="0000001")


def test_매핑_불가_오류는_재시도_대상이_아니다() -> None:
    try:
        resolve_item_mapping(load("item_list_unmappable.json"), "JPY", known_code="0000002")
    except ItemMappingChanged as exc:
        assert exc.retryable is False
    else:
        pytest.fail("ItemMappingChanged가 발생하지 않았다")


def test_ITEM_CODE1이_아니라_ITEM_CODE를_읽는다() -> None:
    """기존 구현이 실패했던 지점 — 필드명이 다르면 매핑이 전부 실패한다."""
    body = '{"StatisticItemList":{"row":[{"ITEM_CODE1":"0000001","ITEM_NAME1":"원/미국달러"}]}}'
    with pytest.raises(ItemMappingChanged):
        resolve_item_mapping(body, "USD", known_code="0000001")
