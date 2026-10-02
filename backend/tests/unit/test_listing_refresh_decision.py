"""목록 갱신 판정 (T018) — 006 FR-013, FR-013a, FR-013b, SC-005a, research R6-3.

**하루의 경계는 한국 시간이다.** UTC로 판정하면 오전 9시 전의 검색이 "어제"로 읽혀, 자정 직후
받은 목록을 그날 다시 받거나(SC-005) 아침 내내 낡은 목록을 쓴다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from src.api.services.listing_refresh import (
    RefreshRecord,
    kst_date,
    list_state,
    should_refresh,
)

D = dt.date.fromisoformat
#: 저장 시각은 UTC다(시간대 없는 값). 2026-10-02 00:05 UTC = 한국 시간 09:05.
NOW = dt.datetime(2026, 10, 2, 0, 5)
TODAY = D("2026-10-02")
YESTERDAY = D("2026-10-01")
INTERVAL = dt.timedelta(minutes=30)


def record(**kwargs: object) -> RefreshRecord:
    base: dict[str, object] = {
        "as_of": None, "as_of_date": None, "row_count": None, "attempt_date": None,
        "attempts": 0, "last_failed_at": None, "last_error_kind": None,
    }
    base.update(kwargs)
    return RefreshRecord(**base)  # type: ignore[arg-type]


def decide(rec: RefreshRecord | None, *, now: dt.datetime = NOW, refreshing: bool = False,
           auth_blocked: bool = False, credentials_present: bool = True,
           max_attempts: int = 5) -> bool:
    return should_refresh(
        rec, now=now, refreshing=refreshing, auth_blocked=auth_blocked,
        credentials_present=credentials_present, retry_interval=INTERVAL,
        max_attempts=max_attempts)


class Test한국_날짜:
    @pytest.mark.parametrize(("utc", "expected"), [
        (dt.datetime(2026, 10, 1, 14, 59), D("2026-10-01")),   # KST 23:59
        (dt.datetime(2026, 10, 1, 15, 0), D("2026-10-02")),    # KST 00:00
        (dt.datetime(2026, 10, 2, 0, 5), D("2026-10-02")),
    ])
    def test_UTC_시각을_한국_날짜로(self, utc: dt.datetime, expected: dt.date) -> None:
        assert kst_date(utc) == expected


class Test갱신_판정:
    def test_기록이_없으면_받는다(self) -> None:
        assert decide(None) is True

    def test_오늘_이미_받았으면_받지_않는다(self) -> None:
        """FR-013, SC-005."""
        assert decide(record(as_of=NOW, as_of_date=TODAY)) is False

    def test_어제_받았으면_받는다(self) -> None:
        assert decide(record(as_of=NOW - dt.timedelta(days=1), as_of_date=YESTERDAY)) is True

    def test_갱신_중이면_받지_않는다(self) -> None:
        """FR-014 — 동시에 들어온 첫 검색이 여럿이어도 한 번이다."""
        assert decide(record(as_of_date=YESTERDAY), refreshing=True) is False

    def test_인증_실패로_막혔으면_받지_않는다(self) -> None:
        """FR-013b — 나을 수 없는 요청으로 한도만 쓴다."""
        assert decide(record(as_of_date=YESTERDAY), auth_blocked=True) is False

    def test_인증_정보가_없으면_시도하지_않는다(self) -> None:
        """FR-028a — 시도해도 실패가 확실하다."""
        assert decide(None, credentials_present=False) is False

    def test_실패_후_간격이_지나지_않았으면_받지_않는다(self) -> None:
        """FR-013a — 검색마다 다시 시도하면 출처를 반복해 두드린다."""
        rec = record(as_of_date=YESTERDAY, attempt_date=TODAY, attempts=1,
                     last_failed_at=NOW - dt.timedelta(minutes=29), last_error_kind="network")
        assert decide(rec) is False

    def test_실패_후_간격이_지나면_다시_받는다(self) -> None:
        """FR-013a — 다음 날까지 기다리면 일시적 실패 하나로 하루 종일 낡은 목록을 쓴다."""
        rec = record(as_of_date=YESTERDAY, attempt_date=TODAY, attempts=1,
                     last_failed_at=NOW - dt.timedelta(minutes=30), last_error_kind="network")
        assert decide(rec) is True

    def test_오늘_상한에_닿으면_받지_않는다(self) -> None:
        """SC-005a."""
        rec = record(as_of_date=YESTERDAY, attempt_date=TODAY, attempts=5,
                     last_failed_at=NOW - dt.timedelta(hours=3), last_error_kind="network")
        assert decide(rec) is False

    def test_상한_아래면_받는다(self) -> None:
        rec = record(as_of_date=YESTERDAY, attempt_date=TODAY, attempts=4,
                     last_failed_at=NOW - dt.timedelta(hours=3), last_error_kind="network")
        assert decide(rec) is True

    def test_어제의_시도_횟수는_세지_않는다(self) -> None:
        rec = record(as_of_date=YESTERDAY, attempt_date=YESTERDAY, attempts=5,
                     last_failed_at=NOW - dt.timedelta(hours=10), last_error_kind="network")
        assert decide(rec) is True

    def test_한국_자정_직후에_새_날로_넘어간다(self) -> None:
        rec = record(as_of=dt.datetime(2026, 9, 30, 16, 0), as_of_date=D("2026-10-01"))
        assert decide(rec, now=dt.datetime(2026, 10, 1, 14, 59)) is False   # KST 10-01 23:59
        assert decide(rec, now=dt.datetime(2026, 10, 1, 15, 0)) is True     # KST 10-02 00:00

    def test_UTC_날짜로_판정하지_않는다(self) -> None:
        """UTC 10-01 16:00은 한국 10-02 01:00이다. UTC로 보면 "오늘 받음"으로 잘못 읽는다."""
        rec = record(as_of=dt.datetime(2026, 10, 1, 1, 0), as_of_date=D("2026-10-01"))
        assert decide(rec, now=dt.datetime(2026, 10, 1, 16, 0)) is True


def state(rec: RefreshRecord | None, **kwargs: object) -> tuple[object, ...]:
    base: dict[str, object] = {
        "today": TODAY, "refreshing": False, "auth_blocked": False,
        "credentials_present": True}
    base.update(kwargs)
    got = list_state("KOSPI", rec, **base)  # type: ignore[arg-type]
    return (got.state, got.reason, got.action)


class Test목록_상태:
    """FR-028, FR-028a, FR-029 — 화면이 "결과 없음"과 "목록 없음"을 가르는 근거."""

    def test_한_번도_받지_않았으면_never(self) -> None:
        assert state(None) == ("never", None, "wait")

    def test_인증_정보가_없으면_할_일을_말한다(self) -> None:
        assert state(None, credentials_present=False) == (
            "never", "auth_missing", "set_credentials")

    def test_오늘_받았으면_ready(self) -> None:
        assert state(record(as_of=NOW, as_of_date=TODAY)) == ("ready", None, None)

    def test_어제_것이면_stale(self) -> None:
        assert state(record(as_of=NOW, as_of_date=YESTERDAY))[0] == "stale"

    def test_갱신_중이면_refreshing이고_기다린다(self) -> None:
        assert state(record(as_of=NOW, as_of_date=YESTERDAY), refreshing=True) == (
            "refreshing", None, "wait")

    def test_마지막_시도가_실패면_failed(self) -> None:
        rec = record(as_of=NOW - dt.timedelta(days=1), as_of_date=YESTERDAY,
                     last_failed_at=NOW, last_error_kind="rate_limit")
        assert state(rec) == ("failed", "rate_limit", "retry_later")

    def test_받은_적_없이_실패했으면_never와_사유(self) -> None:
        rec = record(last_failed_at=NOW, last_error_kind="network")
        assert state(rec) == ("never", "network", "retry_later")

    def test_실패_뒤에_온전히_받았으면_실패가_아니다(self) -> None:
        rec = record(as_of=NOW, as_of_date=TODAY,
                     last_failed_at=NOW - dt.timedelta(hours=1), last_error_kind="network")
        assert state(rec)[0] == "ready"

    def test_인증_실패_막힘(self) -> None:
        rec = record(as_of=NOW - dt.timedelta(days=1), as_of_date=YESTERDAY,
                     last_failed_at=NOW, last_error_kind="auth")
        assert state(rec, auth_blocked=True) == (
            "auth_blocked", "auth_failed", "set_credentials")

    def test_기준_시각을_싣는다(self) -> None:
        got = list_state("KOSDAQ", record(as_of=NOW, as_of_date=TODAY), today=TODAY,
                         refreshing=False, auth_blocked=False, credentials_present=True)
        assert got.unit == "KOSDAQ"
        assert got.as_of == NOW
