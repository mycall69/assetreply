"""국내 목록 파싱 (T017) — 006 FR-010, FR-012, data-model 1절 검증 규칙, research R6-2.

T005의 **실제 응답**으로 검증한다. 출처의 KOSPI 목록에는 주식·ETF·리츠가 ETN 등과 함께 오므로
`marketName`으로 가른다. **처음 보는 `marketName`은 단위 전체의 실패다** — 조용히 빼면 출처가
이름을 바꿨을 때 주식 916건이 오류 없이 "목록에서 빠짐"이 된다(57% 감소라 축소 검사도 못 잡는다).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path

import pytest
from src.ingestion.kiwoom.parse import ListingRow, parse_domestic, parse_listing

from src.ingestion.kiwoom.errors import KiwoomInvalidResponse

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "kiwoom"


def body(unit: str) -> str:
    return (FIXTURES / f"{unit}_p01.json").read_text(encoding="utf-8")


def rows_by_code(unit: str) -> dict[str, ListingRow]:
    return {r.code: r for r in parse_domestic(unit, [body(unit)])}


def edited(unit: str, edit) -> str:  # type: ignore[no-untyped-def]
    data = json.loads(body(unit))
    edit(data["list"])
    return json.dumps(data, ensure_ascii=False)


class Test실제_응답:
    def test_KOSPI는_주식_ETF_리츠만_남긴다(self) -> None:
        """실측: 거래소 916 + ETF 1,171 + 리츠 23 (research R6-2)."""
        rows = parse_domestic("KOSPI", [body("KOSPI")])
        kinds = [r.kind for r in rows]
        assert kinds.count("stock") == 916
        assert kinds.count("etf") == 1171
        assert kinds.count("reit") == 23
        assert len(rows) == 2110

    def test_KOSDAQ는_전부_주식이다(self) -> None:
        rows = parse_domestic("KOSDAQ", [body("KOSDAQ")])
        assert len(rows) == 1825
        assert {r.kind for r in rows} == {"stock"}
        assert {r.unit for r in rows} == {"KOSDAQ"}

    def test_ETN_인프라_뮤추얼펀드를_뺀다(self) -> None:
        raw = json.loads(body("KOSPI"))["list"]
        excluded = {r["code"] for r in raw if r["marketName"] in {
            "ETN", "ETN(변동성)", "ETN(손실제한)", "인프라투자금융", "뮤추얼펀드"}}
        assert len(excluded) == 358 + 8 + 1 + 2 + 1
        assert not excluded & set(rows_by_code("KOSPI"))

    def test_삼성전자(self) -> None:
        row = rows_by_code("KOSPI")["005930"]
        assert row == ListingRow(
            country="KR", code="005930", unit="KOSPI", name_ko="삼성전자", name_en=None,
            kind="stock", listed_on=dt.date(1975, 6, 11))

    def test_우선주는_다른_종목이다(self) -> None:
        rows = rows_by_code("KOSPI")
        assert rows["005935"].name_ko == "삼성전자우"
        assert rows["005935"].code != rows["005930"].code

    def test_ETF와_리츠(self) -> None:
        rows = rows_by_code("KOSPI")
        assert rows["069500"].kind == "etf" and rows["069500"].name_ko == "KODEX 200"
        assert rows["0030R0"].kind == "reit"

    def test_영문이_섞인_6자리_코드를_받아들인다(self) -> None:
        """국내 코드는 6자리지만 숫자만은 아니다 (`0030R0`)."""
        assert "0030R0" in rows_by_code("KOSPI")

    def test_0으로_채운_코드를_그대로_둔다(self) -> None:
        assert "000020" in rows_by_code("KOSPI")

    def test_가격과_상장주식수를_싣지_않는다(self) -> None:
        """FR-012 — 저장하면 시세가 두 출처에서 섞일 자리가 생긴다."""
        names = {f.name for f in dataclasses.fields(ListingRow)}
        assert names == {"country", "code", "unit", "name_ko", "name_en", "kind", "listed_on"}

    def test_단위로_파서를_고른다(self) -> None:
        assert len(parse_listing("KOSDAQ", [body("KOSDAQ")])) == 1825


class Test단위_전체의_실패:
    def test_처음_보는_marketName(self) -> None:
        def rename(rows: list[dict[str, str]]) -> None:
            rows[0]["marketName"] = "유가증권"

        with pytest.raises(KiwoomInvalidResponse):
            parse_domestic("KOSPI", [edited("KOSPI", rename)])

    @pytest.mark.parametrize("bad", ["", "   ", "05930", "0059300"])
    def test_코드가_비었거나_6자리가_아니면(self, bad: str) -> None:
        """한 행을 조용히 버리면 그 종목만 "빠짐"이 된다."""
        def corrupt(rows: list[dict[str, str]]) -> None:
            rows[10]["code"] = bad

        with pytest.raises(KiwoomInvalidResponse):
            parse_domestic("KOSPI", [edited("KOSPI", corrupt)])

    def test_같은_코드가_두_번_오면(self) -> None:
        def duplicate(rows: list[dict[str, str]]) -> None:
            rows.append(dict(rows[0]))

        with pytest.raises(KiwoomInvalidResponse):
            parse_domestic("KOSDAQ", [edited("KOSDAQ", duplicate)])

    @pytest.mark.parametrize("raw", ['{"return_code": 0}', '{"list": {}}', "[]", "not json"])
    def test_목록_모양이_아니면(self, raw: str) -> None:
        with pytest.raises(KiwoomInvalidResponse):
            parse_domestic("KOSPI", [raw])

    def test_국내_단위가_아니면_거절한다(self) -> None:
        with pytest.raises(ValueError):
            parse_domestic("NYSE", [body("KOSPI")])


class Test부가_필드:
    def test_이름이_비면_None(self) -> None:
        def blank(rows: list[dict[str, str]]) -> None:
            rows[0]["name"] = "  "

        rows = parse_domestic("KOSDAQ", [edited("KOSDAQ", blank)])
        assert rows[0].name_ko is None

    @pytest.mark.parametrize("reg_day", ["", "00000000", "2025133", "abcdefgh"])
    def test_상장일을_읽을_수_없으면_None(self, reg_day: str) -> None:
        """상장일은 하한일 뿐이다. 모르는 값을 지어내지 않는다 (헌법 원칙 V)."""
        def bad(rows: list[dict[str, str]]) -> None:
            rows[0]["regDay"] = reg_day

        rows = parse_domestic("KOSDAQ", [edited("KOSDAQ", bad)])
        assert rows[0].listed_on is None

    def test_여러_쪽을_잇는다(self) -> None:
        data = json.loads(body("KOSDAQ"))
        first = dict(data, list=data["list"][:1000])
        second = dict(data, list=data["list"][1000:])
        rows = parse_domestic("KOSDAQ", [json.dumps(first), json.dumps(second)])
        assert len(rows) == 1825
