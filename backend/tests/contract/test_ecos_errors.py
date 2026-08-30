"""ECOS 오류 판별 계약 테스트 (T031~T034).

**출처는 오류도 HTTP 200으로 반환한다.** 본문 `RESULT` 코드를 검사하지 않으면 오류를
성공으로 오인해 빈 데이터를 저장하게 된다 (contracts/ecos-adapter.md).
"""
from __future__ import annotations

import pytest

from src.ingestion.ecos.errors import (
    SourceAuthError,
    SourceRateLimited,
    SourceResponseTruncated,
    SourceUnavailable,
)
from src.ingestion.ecos.parser import parse_search_response
from src.ingestion.protocols import FetchOutcome

from .conftest import load


def test_INFO_200은_오류가_아니라_데이터_없음이다() -> None:
    """구간에 고시가 없는 것은 정상이다."""
    r = parse_search_response(load("info_200_no_data.json"), status=200)
    assert r.outcome is FetchOutcome.NO_DATA
    assert r.quotes == ()
    assert r.raw_result_code == "INFO-200"


def test_INFO_200도_원본을_보존한다() -> None:
    body = load("info_200_no_data.json")
    assert parse_search_response(body, status=200).raw_body == body


def test_INFO_100은_인증_오류다() -> None:
    with pytest.raises(SourceAuthError):
        parse_search_response(load("info_100_bad_key.json"), status=200)


def test_인증_오류는_재시도_대상이_아니다() -> None:
    """키 문제는 재시도해도 달라지지 않는다."""
    try:
        parse_search_response(load("info_100_bad_key.json"), status=200)
    except SourceAuthError as exc:
        assert exc.retryable is False
    else:
        pytest.fail("SourceAuthError가 발생하지 않았다")


def test_INFO_300은_한도_초과다() -> None:
    with pytest.raises(SourceRateLimited) as exc:
        parse_search_response(load("info_300_rate_limit.json"), status=200)
    assert exc.value.retryable is True


def test_비JSON_응답은_SourceUnavailable이다() -> None:
    """차단 페이지·점검 안내 HTML — JSON 파싱 실패와 구분해 기록한다."""
    with pytest.raises(SourceUnavailable):
        parse_search_response(load("blocked_page.html"), status=200)


def test_HTTP_200이어도_본문_오류를_잡는다() -> None:
    """상태 코드만 보면 오류를 성공으로 오인한다 — 기존 구현이 밟았던 함정."""
    for name, expected in (("info_100_bad_key.json", SourceAuthError),
                           ("info_300_rate_limit.json", SourceRateLimited)):
        with pytest.raises(expected):
            parse_search_response(load(name), status=200)


def test_비정상_HTTP_상태도_오류다() -> None:
    with pytest.raises(SourceUnavailable):
        parse_search_response("Service Unavailable", status=503)


class Test응답_잘림:
    """1회 요청 행 한도(실측 1000건)에 걸려 일부만 오는 경우.

    조용히 넘어가면 데이터가 빠진 채 커버리지만 갱신되어 영영 메워지지 않는다
    (헌법 원칙 V).
    """

    def test_전체_건수보다_적게_오면_오류다(self) -> None:
        with pytest.raises(SourceResponseTruncated):
            parse_search_response(load("search_truncated.json"), status=200)

    def test_잘림은_재시도_대상이_아니다(self) -> None:
        """청크 크기를 줄여야 해결된다 — 재시도해도 같은 결과다."""
        try:
            parse_search_response(load("search_truncated.json"), status=200)
        except SourceResponseTruncated as exc:
            assert exc.retryable is False
            assert "청크 크기" in str(exc)
        else:
            pytest.fail("SourceResponseTruncated가 발생하지 않았다")

    def test_전부_수신하면_오류가_아니다(self) -> None:
        r = parse_search_response(load("search_ok.json"), status=200)
        assert len(r.quotes) == 3
