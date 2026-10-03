"""코인 목록 갱신 판정 (T013) — 007 FR-005, data-model 2절.

**일주일에 한 번** 다시 받는다 — 마지막으로 갱신에 성공한 지 7일이 지난 뒤(한국 시간 날짜) 처음
검색할 때. 받은 적이 없으면 첫 검색 때 받는다. **실패하면 다음 날** 첫 검색 때 다시 시도한다 — 같은
날 검색마다 다시 받으면 막힌 출처를 하루 내내 두드린다.

화면 상태(`edition_state`)도 순수 함수다. "받은 적 없음"과 "갱신 실패"를 가른다 — 같게 보이면
사용자는 목록이 없는 이유를 모른다.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.api.services.crypto_list_refresh import CoinRefreshRecord, edition_state, list_due
from src.api.services.listing_refresh import kst_date

D = dt.date.fromisoformat
TODAY = D("2026-10-03")


def record(*, as_of_date: dt.date | None = None, attempt_date: dt.date | None = None,
           failed_at: dt.datetime | None = None, kind: str | None = None) -> CoinRefreshRecord:
    as_of = None if as_of_date is None else dt.datetime.combine(as_of_date, dt.time(1))
    return CoinRefreshRecord(
        as_of=as_of, as_of_date=as_of_date, row_count=3654 if as_of else None,
        attempt_date=attempt_date, attempts=1 if attempt_date else 0,
        last_failed_at=failed_at, last_error_kind=kind)


class Test갱신_판정:
    def test_받은_적이_없으면_받는다(self) -> None:
        assert list_due(None, today=TODAY, refresh_days=7) is True

    @pytest.mark.parametrize(("days", "due"), [(0, False), (1, False), (6, False), (7, True),
                                               (30, True)])
    def test_마지막_성공_뒤_7일이_지나야_받는다(self, days: int, due: bool) -> None:
        last = TODAY - dt.timedelta(days=days)
        assert list_due(record(as_of_date=last, attempt_date=last), today=TODAY,
                        refresh_days=7) is due

    def test_오늘_이미_실패했으면_다음_날까지_받지_않는다(self) -> None:
        failed = record(as_of_date=TODAY - dt.timedelta(days=9), attempt_date=TODAY,
                        failed_at=dt.datetime(2026, 10, 3, 1), kind="network")
        assert list_due(failed, today=TODAY, refresh_days=7) is False
        assert list_due(failed, today=TODAY + dt.timedelta(days=1), refresh_days=7) is True

    def test_받은_적_없이_오늘_실패했어도_다음_날이다(self) -> None:
        failed = record(attempt_date=TODAY, failed_at=dt.datetime(2026, 10, 3, 1), kind="blocked")
        assert list_due(failed, today=TODAY, refresh_days=7) is False
        assert list_due(failed, today=TODAY + dt.timedelta(days=1), refresh_days=7) is True

    def test_주기는_설정을_따른다(self) -> None:
        last = TODAY - dt.timedelta(days=3)
        assert list_due(record(as_of_date=last, attempt_date=last), today=TODAY,
                        refresh_days=3) is True

    def test_하루의_경계는_한국_시간_자정이다(self) -> None:
        """UTC 14:59는 한국 23:59(10-03), UTC 15:00은 한국 00:00(10-04)이다."""
        last = record(as_of_date=D("2026-09-27"), attempt_date=D("2026-09-27"))
        before = kst_date(dt.datetime(2026, 10, 3, 14, 59, 59))
        after = kst_date(dt.datetime(2026, 10, 3, 15, 0, 0))
        assert (before, after) == (D("2026-10-03"), D("2026-10-04"))
        assert list_due(last, today=before, refresh_days=7) is False
        assert list_due(last, today=after, refresh_days=7) is True


class Test화면_상태:
    def test_받은_적이_없으면_never다(self) -> None:
        state = edition_state(None, refreshing=False)
        assert (state.state, state.as_of, state.reason) == ("never", None, None)

    def test_처음_받는_중도_never다(self) -> None:
        """이전 목록이 없다 — "처음 받는 중"과 "새로 받는 중(이전 목록으로 찾는다)"은
        다르다(ui-wireframes C2)."""
        assert edition_state(None, refreshing=True).state == "never"

    def test_이전_목록이_있으면_갱신_중이다(self) -> None:
        state = edition_state(record(as_of_date=D("2026-09-20")), refreshing=True)
        assert state.state == "refreshing"
        assert state.as_of == dt.datetime(2026, 9, 20, 1)

    def test_마지막_갱신이_실패했으면_사유와_이전_기준_시각이다(self) -> None:
        failed = record(as_of_date=D("2026-09-20"), attempt_date=TODAY,
                        failed_at=dt.datetime(2026, 10, 3, 1), kind="blocked")
        state = edition_state(failed, refreshing=False)
        assert (state.state, state.reason, state.as_of) == (
            "failed", "blocked", dt.datetime(2026, 9, 20, 1))

    def test_받은_적_없이_실패했어도_실패다(self) -> None:
        failed = record(attempt_date=TODAY, failed_at=dt.datetime(2026, 10, 3, 1), kind="network")
        state = edition_state(failed, refreshing=False)
        assert (state.state, state.reason, state.as_of) == ("failed", "network", None)

    def test_실패_뒤_성공했으면_준비다(self) -> None:
        recovered = CoinRefreshRecord(
            as_of=dt.datetime(2026, 10, 3, 2), as_of_date=TODAY, row_count=3654,
            attempt_date=TODAY, attempts=2, last_failed_at=dt.datetime(2026, 10, 2, 1),
            last_error_kind=None)
        state = edition_state(recovered, refreshing=False)
        assert (state.state, state.reason) == ("ready", None)
