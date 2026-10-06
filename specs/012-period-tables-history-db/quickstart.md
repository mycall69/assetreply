# Quickstart: 012 검증 안내

**Date**: 2026-10-06 | **Plan**: [plan.md](./plan.md)

구현이 spec을 만족하는지 끝에서 끝까지 확인하는 절차다. 계약은 [contracts/rest-api.md](./contracts/rest-api.md)·[contracts/ui-wireframes.md](./contracts/ui-wireframes.md),
칸의 뜻은 [data-model.md](./data-model.md)를 본다.

## 0. 준비

- **012 전 응답을 먼저 받아 둔다**(3-7의 불변 대조). 012 코드를 올리기 전, 지금 개발 서버에서 받는다.
  - 대상: 일시금 주식(국내·미국)·가상자산·정기예금·부동산과 적립식·적금 각 하나
  - 받는 것: `summary`와 `/series` 본문
- 새 테이블 둘이 있으므로 개발 DB에 마이그레이션을 올린다: `cd backend && .venv/bin/python -m alembic upgrade head`(`simulation_history`·`history_setting`).
- 품질 게이트는 서버를 멈추고 돌린다 — 통합 테스트가 같은 MySQL 스키마를 다시 만든다.

  ```bash
  ./stop.sh
  cd backend && .venv/bin/python -m pytest -q --cov=src && .venv/bin/python -m mypy src && .venv/bin/python -m ruff check --no-cache src tests
  cd frontend && npm test && npx tsc --noEmit && npx eslint .     # 종료 코드를 본다 — "N passed"만 보지 않는다(011 T036)
  ./start.sh
  ```

## 1. 단위 참조값 — 기간 표 (SC-002·SC-003)

`backend/tests/unit/test_period_table.py`의 손으로 만든 날짜 목록으로 대표일·표시를 정확히 고정한다.

| 경우 | 기대 |
|------|------|
| 국내 주식, 금요일 휴장(2026-10-09 한글날) 주 | 대표일 10-08(목), `shiftedFrom` 10-09 |
| 국내 주식, 계산 끝 10-05(월) 대체공휴일 | 이번 주 행 없음. 맨 위는 10-02(금), 표시 없음 |
| 미국 주식, 계산 끝 10-05(월) 일봉 있음 | 맨 위 10-05, `shiftedFrom` 10-09, `isOngoing` |
| 말일이 토요일인 달(2026-10-31) | 대표일 10-30(금), `shiftedFrom` 10-31 |
| 가상자산, 금요일 결측·토일 있음 | 대표일 목요일, `shiftedFrom` 금요일(명확화 2) |
| 가상자산, 월~금 결측·토일 있음 | 대표일 일요일, `shiftedFrom` 금요일 |
| 구간에 시세일 없음 | 그 구간 행 없음 |
| 대표일에 배당락·재투자 | 기간 행 없음, 그날 마지막 사건 행이 표시를 진다. 배당락 행 날짜는 그대로 |
| 일 단위 | 표시 없음, 사건 없는 시세일마다 기간 행 |
| 가상자산 일 단위 결측 둘 | 결측 행 둘, 자리가 맞다. 주·월에는 결측 행 없음 |
| 첫 주 금요일이 첫 평가일 전(가상자산 토요일 매수) | 대표일은 그 주의 계산 기간 안 마지막 일봉, 표시 있음. 첫 평가일 전의 값 행 없음 |
| 시세가 끊긴 종목(마지막 구간이 계산 끝 앞에서 끝남) | 진행 중 표시 없음 |

하루하루 상태(`daily`) 불변식(data-model 4)은 `test_reinvest_daily.py`·`test_recurring_stock_daily.py`가 고정한다. 월 행이 있는 날과 마지막 날의 값이 같아야 한다.

## 2. 단위·계약 — 이력 (SC-006·SC-007)

| 테스트 | 확인하는 것 |
|--------|-------------|
| 조건 식별자 대조 | 화면 lib의 지금 테스트에 나오는 식별자 예시를 서버 함수가 글자까지 같게 낸다(자산군 넷, 011 전 형식 포함) |
| 보관 경계 | 30일 설정에서 보관 기준이 30일 + 1초 전이면 지우고, 29일 전이면 남긴다. 무기한은 지우지 않는다. 기간을 7일로 줄이는 PUT 직후 8일 된 항목이 목록에 없다 |
| 옮기기 | 45일 전 `savedAt` 항목이 옮겨져 남는다(보관 기준 = 옮긴 시각, 차례 = `savedAt`). 같은 조건은 합쳐지고 늦은 쪽이 남는다. 틀린 항목은 `skipped` |
| 자산군 섞임 | 주식에 넣은 항목이 가상자산 목록에 없다 |

## 3. API 끝에서 끝까지 (개발 서버)

`curl`로 부른다. 202면 진행 URL을 따라가 끝난 뒤 다시 부른다.

1. **주식 일·주·월** — `GET /api/stocks/simulation?market=KRX&symbol=005930.KS&start=2024-01-02&principal=10000000&principalCurrency=KRW&reinvest=true&period=weekly`
   - 행의 `date`가 금요일이거나 `shiftedFrom`이 있다
   - `dividend`·`reinvest` 행 수가 `period=daily`·`monthly`와 같다(SC-003)
   - `summary`가 세 단위에서 같다(SC-005)
2. **가상자산 결측 구간** — 결측이 있는 코인(개발 DB의 `source_missing` 끊김이 있는 코인)을 `period=daily`로 부른다. `missing` 행 수가 `/series`의 `source_missing`
   끊김 수와 같다(SC-002).
3. **틀린 단위** — `period=yearly` → 400 `invalid_query`.
4. **이력** — 차례대로 부른다.
   - `PUT /api/history/stock` → `GET` → 같은 조건 다시 `PUT`이면 항목 하나이고 `lastRunAt`이 바뀐다
   - `DELETE …?id=`
5. **보관 기간** — `PUT /api/history/settings {"retentionDays": 7}` → `GET /api/history/stock`에 7일보다 오래된 항목이 없다. `{"retentionDays": 10}` → 422.
6. **성능(SC-004)** — 다음 셋을 `period=daily`로 첫 쪽·다음 쪽(`before=oldestReturned`)을 각각 잰다. `curl -w '%{time_total}'`로 3초 안이다.
   - 20년 국내 주식 일시금
   - 20년 비트코인 일시금
   - 20년 매일 적립 주식
7. **불변 대조(SC-009)** — 0의 응답과 012 응답의 `summary`·`/series`가 문자열까지 같다.
   - 대상: 일시금 주식·가상자산·정기예금·부동산과 적립식·적금
   - 표 `rows`는 대상이 아니다 — 행 구성이 바뀐다

## 4. 브라우저 (CDP 스크립트 또는 직접 — 1440px 창)

1. **외환(SC-001)** — 일자별 표를 가운데까지 내린 뒤 일 → 주 → 월 → 일을 누른다. 매번 단위 탭의 화면상 위치(`getBoundingClientRect().top`)가 같다.
   - 월에서 표가 짧아져도 같다
   - 먼 날짜를 고르면 표의 처음으로 간다(그대로)
   - 통화를 바꾸면 창이 그대로다(그대로)
2. **주식·가상자산 표** — 삼성전자 일시금(재투자)과 비트코인 일시금을 실행한다.
   - 처음 단위가 "일"이다
   - 주·월로 바꾸면 창이 그대로이고 이전 단위의 행이 남지 않는다
   - 📅·⏳에 글자 설명이 있다
   - 배당락·재투자 행이 세 단위에 모두 있다
   - 보드·차트가 그대로다
   - 맨 아래까지 내리면 이어 받는다
3. **이력(SC-006)** — 차례대로 확인한다.
   - 012 전 브라우저(옛 키에 항목이 있는 프로필)로 네 화면을 연다. 항목이 그대로 보이고 옛 키가 지워졌다(개발자 도구 → Application → Local Storage)
   - 다른 브라우저(또는 시크릿 창)에서 같은 항목이 보인다
   - 안내가 "이 기기의 로컬 DB에 저장됩니다 …"다
4. **이력 실패(FR-014·FR-014a)** — 백엔드를 멈추고 주식 화면을 연다.
   - "이력을 불러오지 못했습니다"와 다시 시도가 보이고, 빈 상태 문구가 없다
   - 백엔드를 띄우고 다시 시도를 누르면 목록이 보인다
5. **설정** — 보관 기간을 7일로 저장한다. 안내 문구와 저장 알림이 보이고, 오래된 항목이 화면 목록에서 사라진다.
6. **원금(SC-008)** — 새 창으로 주식·가상자산·예금을 연다. 칸이 10,000,000이고, 종목(코인·투자처)만 고르면 실행된다.
   - 적립식·적금으로 바꿔도 값이 그대로다
   - 이력 다시 실행은 항목 값이다
   - 부동산 화면은 그대로다

## 실행 기록

(구현 중 채운다 — 날짜·태스크·결과)
