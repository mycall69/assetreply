# Bug Fix: 계산 끝(어제)이 휴장일이면 주식 보드·표에 "시세가 없습니다" 경고가 잘못 뜬다

- **Slug**: stock-holiday-stale-warning
- **Fixed**: 2026-10-06
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

주식의 `isFinal` 판정을 "마지막 일봉 ≥ 계산 끝(달력상 어제)"에서 바꿨다. "같은 시장의 다른 종목이 그 뒤에 거래했는가"(데이터 근거)와 "비교할 거래가
없으면 빈 평일 수 ≤ 허용치"로 휴장·주말과 시세 단절을 가른다. 일시금과 적립식이 같은 함수를 쓴다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `backend/src/simulation/quote_finality.py` | added | 순수 함수 `is_final(as_of, end, *, market_last, tolerance_weekdays)`·`blank_weekdays` |
| `backend/src/repository/stock_price.py` | modified | `market_last_quote_date(session, stock_id, end)` — 같은 시장(그 종목 포함)의 `end` 이하 마지막 일봉 날짜 |
| `backend/src/api/services/stock_simulation.py` | modified | `reaches_end(session, stock_id, as_of, end)` — 일시금의 `is_final`을 이것으로 |
| `backend/src/api/services/stock_recurring.py` | modified | 적립식의 `is_final`도 `reaches_end` |
| `backend/src/config/settings.py` | modified | `stock_holiday_tolerance_weekdays`(`STOCK_HOLIDAY_TOLERANCE_WEEKDAYS`, 기본 7) |
| `.env.example` | modified | 위 설정과 그 뜻 |
| `backend/tests/unit/test_quote_finality.py` | added test | 판정 규칙 |
| `backend/tests/integration/test_stock_holiday_asof.py` | added test | 일시금·적립식 경로 |

## Diff Highlights

```python
# simulation/quote_finality.py
def is_final(as_of, end, *, market_last, tolerance_weekdays) -> bool:
    if as_of >= end:
        return True
    if market_last is not None and market_last > as_of:
        return False                       # 같은 시장의 다른 종목은 그 뒤에 거래했다 — 이 종목만 끊겼다
    return blank_weekdays(as_of, end) <= tolerance_weekdays   # 시장 전체가 쉬었다면 휴장

# services/stock_simulation.py — run_simulation
is_final = await reaches_end(session, stock_id, as_of, end)   # 이전: as_of >= end
```

## Tests Added or Updated

- `tests/unit/test_quote_finality.py`
  - 계산 끝까지 시세 → 최종
  - 대체공휴일(10-05) → 최종
  - 주말 → 최종
  - 다른 종목 거래 → 단절
  - 평일 60여 일(`test_delisted` 시나리오) → 단절
  - 시장 데이터 없음 → 평일 허용치로 가름
  - 허용치 경계(빈 평일 7 → 최종, 8 → 단절)
  - 허용치 0
- `tests/integration/test_stock_holiday_asof.py`
  - 두 국내 종목(10-01·10-02 일봉, 커버리지 10-05)
  - 일시금: 계산 끝 10-05·10-04 → `isFinal true`
  - 한 종목만 10-05에 거래 → 다른 종목 `isFinal false`, 거래한 종목 `isFinal true`
  - 적립식 `isFinal true`
- 기존 `tests/integration/test_delisted.py`는 바꾸지 않았고 그대로 통과한다(시세 단절은 여전히 `isFinal false`)

## Local Verification

- 먼저 테스트를 커밋했다(e337a6c)
  - 수정 전: 통합 3건이 버그 그대로(`('2026-10-02', False)`) 실패했다. 단위 테스트는 모듈이 없어 수집 오류였다
- 수정 뒤
  - `pytest tests/unit/test_quote_finality.py tests/integration/test_stock_holiday_asof.py tests/integration/test_delisted.py` → 21 passed
  - `pytest tests/unit tests/contract` → 1,517 passed
  - `pytest -k "stock or delisted or quote_finality or recurring or sale"`(통합 포함) → 371 passed
  - `mypy src` → 222 파일 문제 없음, `ruff check --no-cache src tests` → 통과
- 개발 서버 재현(2026-10-06, 백엔드 재기동 뒤)
  - 수정 전: `GET /api/stocks/simulation?market=KRX&symbol=005930.KS&start=2026-09-01&…`이 `asOf 2026-10-02, isFinal false`
  - 수정 뒤: 일시금·적립식 모두 `asOf 2026-10-02, isFinal true`
  - 대조: AAPL은 `2026-10-05, true`로 그대로다
- 화면은 고치지 않았다 — 보드·표의 경고는 서버의 `isFinal`을 그대로 그린다. 브라우저 확인은 `/speckit-bug-test`에서 한다

## Deviations from Assessment

- 판정 함수를 `simulation/quote_finality.py`에 두었다(평가: "`simulation/` 또는 서비스의 작은 함수"). 서비스 쪽에는 DB 조회와 설정 읽기를 묶은
  `reaches_end`만 두었다.
- `market_last_quote_date`는 시장을 인자로 받지 않고 `stock_id`로 시장을 찾는다(하위 질의). `run_simulation`의 서명(종목 id만 받는다)을 바꾸지 않기
  위해서다. 가상자산(`crypto_simulation.run_simulation`)은 이 함수를 쓰지 않는다.
- 평일 허용치 기본값은 평가의 제안값 7을 그대로 썼다. 평가의 Open Question(최장 연휴 확인)은 아직 열려 있다.
- 005 spec·plan은 고치지 않았다(평가: "또는 버그 기록만"). 버그 기록과 코드 주석에 판정 규칙을 남겼다.

## Follow-ups

- 평가의 Open Questions
  - 장 마감 뒤 오늘을 계산 끝에 넣을지
  - 일자별 표에 기준일 행을 둘지
  - 평일 허용치 기본값 확정
- 비교 종목이 하나뿐인 시장(개발 DB의 TSE는 1종목)에서는 상장폐지를 허용치(평일 7일)만큼 늦게 알린다. 설정으로 조정할 수 있다.
- 다음 단계: `/speckit-bug-test slug=stock-holiday-stale-warning`
  - 브라우저에서 국내 종목 보드·표에 경고가 없는지 확인
  - 전체 스위트(서버를 내린 채)
