"""시세 출처 오류 구별 (T009) — 005 contracts/rest-api 오류표, 헌법 원칙 II.

**"결과 없음"과 "출처가 죽음"을 같게 다루면** 사용자는 그 종목이 존재하지 않는다고
읽는다. 할 일이 정반대인데 화면이 같은 말을 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.yahoo.errors import (
    StockSourceAuthError,
    StockSourceRateLimited,
    StockSourceUnavailable,
    StockSymbolNotFound,
    raise_for_response,
)

FIXTURES = Path(__file__).parent / "fixtures" / "stock"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class Test상태_코드별_구별:
    def test_429는_호출_한도다(self) -> None:
        """출처가 한도를 공개하지 않으므로 상태 코드가 유일한 신호다."""
        with pytest.raises(StockSourceRateLimited):
            raise_for_response(429, {})

    def test_401과_403은_인증_문제다(self) -> None:
        for status in (401, 403):
            with pytest.raises(StockSourceAuthError):
                raise_for_response(status, {})

    def test_5xx는_출처_장애다(self) -> None:
        for status in (500, 502, 503):
            with pytest.raises(StockSourceUnavailable):
                raise_for_response(status, {})

    def test_200은_통과한다(self) -> None:
        raise_for_response(200, load("chart_full.json"))


class Test본문_오류:
    def test_없는_종목은_따로_구별한다(self) -> None:
        """404로 내려보내려면 "출처 장애"와 달라야 한다."""
        with pytest.raises(StockSymbolNotFound):
            raise_for_response(404, load("chart_not_found.json"))

    def test_200인데_본문이_오류면_장애로_본다(self) -> None:
        """상태 코드만 보면 통과하는 경로다. 조용히 빈 결과가 되면 안 된다."""
        with pytest.raises(StockSourceUnavailable):
            raise_for_response(200, {"chart": {"result": None, "error": {
                "code": "Internal", "description": "upstream failure"}}})

    def test_빈_결과는_오류가_아니다(self) -> None:
        """상장 이전 구간 요청은 정상이다. 오류로 올리면 사용자가 고장으로 여긴다."""
        raise_for_response(200, load("chart_empty.json"))


class Test오류_메시지:
    def test_출처_응답_본문을_그대로_노출하지_않는다(self) -> None:
        """내부 사정이 사용자 화면에 새어 나가지 않는다."""
        try:
            raise_for_response(404, load("chart_not_found.json"))
        except StockSymbolNotFound as exc:
            assert "delisted" not in str(exc).lower()
