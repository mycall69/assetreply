"""헬리오시티 참조값 (T029) — 009 FR-004, FR-008, FR-016, SC-003, SC-006, research R9-2.

T001의 송파구 2020-01~2023-09 응답(gzip)을 **실제 파서**로 읽어 헬리오시티(`aptSeq 11710-8865`)만
고르고 이 도구의 평형 경계로 나눈다.

- **해제를 넣은 계산**의 월별 평형별 건수·그 달 평균(반올림)은 사용자
  스프레드시트(`helio_sheet_2020_2023.csv`,
  45행 × 5구분)와 **225칸 모두 같다**(SC-003) — 스프레드시트는 해제를 넣은 값이다
- 화면 경로는 **해제를 뺀다**(FR-008, SC-006). 그 기간 해제 27건이 25칸을 바꾼다 — 그 칸의
  기대값(건수·평균)은
  같은 원본을 이 도구와 다른 방법(정수 반올림 손계산)으로 구해 고정했다
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
from pathlib import Path

import pytest

from src.ingestion.datagokr.trade_parse import number_trades, parse_trades
from src.simulation.apt_area import area_bucket
from src.simulation.apt_price import MonthTotal, Trade, aggregate, month_average

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "apt"
HELIO = "11710-8865"
SHEET_BUCKETS = ("10", "20", "30k", "30l", "40")

#: 해제를 빼면 달라지는 칸 — (달, 구분) → (건수, 그 달 평균). 해제 27건.
WITHOUT_CANCELLED = {
    ("2020-06", "30k"): (2, 1_787_500_000), ("2020-11", "30k"): (2, 1_975_000_000),
    ("2021-01", "20"): (2, 1_775_000_000), ("2021-01", "40"): (2, 2_560_000_000),
    ("2021-08", "30k"): (3, 2_093_333_333), ("2021-09", "30k"): (3, 2_340_000_000),
    ("2021-10", "10"): (4, 1_352_500_000), ("2021-11", "10"): (1, 1_350_000_000),
    ("2021-11", "30k"): (2, 2_205_000_000), ("2022-02", "10"): (1, 1_300_000_000),
    ("2022-03", "30k"): (6, 2_191_500_000), ("2022-05", "10"): (3, 1_176_666_667),
    ("2022-05", "30k"): (5, 2_198_000_000), ("2022-07", "10"): (0, None),
    ("2023-01", "20"): (7, 1_456_428_571), ("2023-01", "30k"): (14, 1_720_714_286),
    ("2023-03", "30k"): (16, 1_828_437_500), ("2023-04", "20"): (3, 1_551_666_667),
    ("2023-04", "30k"): (19, 1_872_368_421), ("2023-05", "30k"): (17, 1_887_647_059),
    ("2023-06", "10"): (6, 1_185_000_000), ("2023-06", "30k"): (18, 1_935_000_000),
    ("2023-07", "30k"): (12, 1_942_083_333), ("2023-08", "30k"): (21, 1_986_142_857),
    ("2023-09", "40"): (2, 2_485_000_000),
}


def helio_by_bucket() -> dict[str, list[Trade]]:
    by_bucket: dict[str, list[Trade]] = {}
    for path in sorted(FIXTURES.glob("trade_11710_20*_p1.xml.gz")):
        ym = path.name.split("_")[2]
        rows = []
        # 2쪽짜리 달은 이어 읽는다
        for page in sorted(FIXTURES.glob(f"trade_11710_{ym}_p*.xml.gz")):
            rows.extend(parse_trades(gzip.decompress(page.read_bytes()).decode("utf-8"),
                                     lawd_cd="11710", ym=ym).rows)
        for trade in number_trades(rows):
            if trade.apt_seq == HELIO:
                by_bucket.setdefault(area_bucket(trade.excl_area).key, []).append(
                    Trade(trade.deal_date, trade.amount, cancelled=trade.cancelled))
    return by_bucket


def sheet() -> list[dict[str, str]]:
    with (FIXTURES / "helio_sheet_2020_2023.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cell(monthly: dict[dt.date, MonthTotal], month: str) -> tuple[int, int | None]:
    day = dt.date.fromisoformat(month + "-01")
    found = monthly.get(day)
    return (found.count if found else 0), month_average(monthly, day)


@pytest.fixture(scope="module")
def trades() -> dict[str, list[Trade]]:
    return helio_by_bucket()


def test_원본_범위(trades: dict[str, list[Trade]]) -> None:
    every = [t for group in trades.values() for t in group]
    assert len(every) == 558 and sum(t.cancelled for t in every) == 27
    assert set(trades) == {"10", "20", "30k", "30l", "40"}  # 50·60평대 거래는 이 기간에 없다


def test_해제를_넣으면_스프레드시트와_225칸_모두_같다(trades: dict[str, list[Trade]]) -> None:
    rows = sheet()
    assert len(rows) == 45 and rows[0]["month"] == "2020-01" and rows[-1]["month"] == "2023-09"
    mismatched = []
    for key in SHEET_BUCKETS:
        monthly = aggregate(trades.get(key, []), include_cancelled=True)
        for row in rows:
            expected = (int(row[f"{key}_count"]),
                        int(row[f"{key}_average"]) if row[f"{key}_average"] else None)
            if cell(monthly, row["month"]) != expected:
                mismatched.append((row["month"], key))
    assert mismatched == []


def test_해제를_빼면_25칸이_손계산과_같고_나머지는_그대로(trades: dict[str, list[Trade]]) -> None:
    rows = sheet()
    for key in SHEET_BUCKETS:
        shown = aggregate(trades.get(key, []))  # 화면 경로 — 해제를 뺀다
        for row in rows:
            got = cell(shown, row["month"])
            sheet_value = (int(row[f"{key}_count"]),
                           int(row[f"{key}_average"]) if row[f"{key}_average"] else None)
            assert got == WITHOUT_CANCELLED.get((row["month"], key), sheet_value), (
                row["month"], key)
    removed = sum(int(r[f"{k}_count"]) for r in rows for k in SHEET_BUCKETS) - sum(
        count for count, _ in WITHOUT_CANCELLED.values()) - sum(
        int(r[f"{k}_count"]) for r in rows for k in SHEET_BUCKETS
        if (r["month"], k) not in WITHOUT_CANCELLED)
    assert removed == 27
