---

description: "Task list for 012-period-tables-history-db"
---

# Tasks: 외환 기간 전환 스크롤, 주식·가상자산 일자별 표의 일·주·월 단위, 시뮬레이션 이력의 로컬 DB 저장, 투자금 기본값

**Input**: Design documents from `/specs/012-period-tables-history-db/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
- 테스트 작성 → **실패 확인** → 구현 순서다.
- **테스트를 구현보다 먼저 커밋한다.** 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes).
- **구현 뒤 테스트가 실패하면 멈추고 실패 목록과 원인 판단을 먼저 보고한다.** 원인이 테스트 쪽으로 보여도 같다. 이전에 통과하던 테스트가 실패로 바뀐
  경우도 같다(006 D2).

**Organization**: 사용자 스토리별로 묶는다. 네 스토리는 서로 독립이다.
- US1(외환 기간 전환 스크롤, P1)이 MVP다. US2(주식·가상자산 일·주·월 표)도 P1이다.
- US3(이력의 로컬 DB)는 P2, US4(원금 기본값)는 P3다.
- 높이 붙잡기 훅은 US1·US2가 함께 기대므로 Foundational에 둔다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python은 `backend/.venv/bin/python`을 직접 호출한다(헌법 — Python 가상환경 필수).
- 린트는 `ruff check --no-cache`(CLAUDE.md)다. 테스트를 먼저 쓸 때 임포트는 구현 뒤 기준(전부 `src.*` 묶음)으로 정렬한다.

## 이 기능에서 특히 조심할 것

- **계산 결과는 바뀌지 않는다**(FR-017, SC-009)
  - 계산 모듈의 `rows`·`latest`와 요약 계산을 고치지 않는다. 주식 두 모듈에는 `daily`를 **더하기만** 한다(research R12-4).
  - 시계열 경로(`…/series`)는 질의·응답 모두 그대로다. 주식 차트는 지금처럼 `rows`(월 첫 거래일·사건 날)로 그린다(spec FR-007).
  - T001이 기준 응답을 남기고 T068이 대조한다.
- **바뀌는 기존 테스트는 research R12-15의 목록뿐이고, 스토리의 테스트 커밋 전에 승인을 받는다**(T005·T011·T038)
  - 승인 뒤 그 테스트 커밋에서 **바뀐 요구를 단언하는 부분만** 고친다. 목록에 있어도 바뀐 요구를 단언하지 않으면 고치지 않는다.
  - 구현 뒤 목록 밖의 테스트가 실패하면 결함으로 보고 멈춘다.
  - 공유 테스트 기반(`frontend/tests/setup.ts`)에는 **더하기만** 한다(T043 — 이력 대역).
- **외환의 검증된 부품은 고치지 않는다** — `api/services/period_rows.py`·`components/fx/DailyTable.tsx`·`components/fx/PeriodRowBadges.tsx`.
  `PeriodTabs.tsx`에는 선택 속성 `titles`만 더한다(기본값은 지금 문구).
- **표 묶기는 서버의 순수 함수다**(research R12-2) — `simulation/period_table.py`는 DB·HTTP를 부르지 않고(`test_layer_boundaries`), `api/`를 부르지 않는다.
  화면은 대표일·표시를 계산하지 않는다(`tests/noClientSideFinance.test.ts`).
- **값을 만들지 않는다**(원칙 V)
  - 기준일에 시세가 없으면 **날짜를** 옮긴다. 결측 구간 행에는 값 키가 없다.
  - `test_no_interpolation`은 주석까지 "전일 값"·"이전 값"·"직전 값"·`fillna`·`ffill`·`bfill`·`interpolate`·`backfill`을 찾는다. "이전 단위"처럼 쓰고
    "이전 값"을 쓰지 않는다.
- **가드 테스트**
  - `test_no_hardcoded_dates`는 `src`(마이그레이션 포함)의 ISO 날짜 리터럴을 막는다.
  - `test_dialect_isolation`은 `sqlalchemy.dialects`·`on_duplicate_key_update`를 `db/dialect.py` 밖에서 막는다. JSON 열을 쓰지 않는다 — 조건은 `Text`다.
  - `test_no_float`는 `simulation`·`repository`·`db`의 `float`를 막는다.
  - `test_layer_boundaries`: 저장소는 `src.api`에서 `src.api.errors`만 부른다.
- **화면 테스트가 실제 차트를 그리면 vitest가 종료 코드 1이다**(011 T036) — 결과 화면을 그리는 페이지 테스트는 `lightweight-charts`를 모의하고 시계열
  요청에 시계열 응답을 준다. "N passed"만 보지 말고 종료 코드를 본다.
- **요청 문자열**: 표 단위가 `daily`이면 `period`를 보내지 않는다 — 기본 단위의 요청 문자열이 지금과 같다(exact URL 테스트 보호, research R12-7).
- **이력**
  - 브라우저 옛 키는 옮기기가 2xx일 때만 지운다.
  - `/api/history/settings`를 `/api/history/{asset}`보다 먼저 등록한다.
  - 지금 시각은 `api/services/history.utc_now()`로 얻고 테스트가 그것을 바꾼다.
  - 이력 클라이언트는 `apiClient.get` 등이 아니라 공통 요청 함수를 직접 쓴다(research R12-12).
- **DB 비밀번호·키를 출력하거나 셸 인자로 넘기지 않는다.** 앱 DB 사용자는 `CREATE DATABASE` 권한이 없다 — 마이그레이션은 `alembic upgrade head`로만 한다.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 구현 전의 기준(불변 대조용 응답·기존 검사 통과 상태)

- [X] T001 구현 전 기준 응답을 남긴다 (FR-017, SC-009, quickstart 0·3-7)
  - 서버를 띄운다(`./start.sh`).
  - 다음 실행의 표 경로 첫 쪽(`summary`·`condition`)과 `/series` 응답을 저장소 밖 작업용 임시 폴더(`012-baseline/before/`)에 JSON으로 저장한다.
    - 일시금: 주식 KRX 005930.KS·NASDAQ AAPL(원화 원금), 가상자산 BTC(원화)
    - 정기예금 시중은행, 부동산 헬리오시티 30평대
    - 적립식 주식(국내 매달)·가상자산(매일), 적금 시중은행
  - `end`를 고정한다(날짜가 지나도 같은 입력). 받은 시각·조건을 `meta.json`에 적는다. 202면 수집이 끝난 뒤 다시 받는다.
- [X] T002 구현 전 기존 검사의 통과 상태를 기록한다 (SC-009)
  - 서버를 내린다(`./stop.sh`).
  - 백엔드 `pytest -q --cov=src`·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수를 이 파일 Notes에 적는다. 실패가 있으면 기능 전의 실패로 기록하고 멈추고 보고한다.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: US1·US2가 함께 쓰는 높이 붙잡기 훅(research R12-1)

**⚠️ CRITICAL**: US1·US2는 이 페이즈 뒤에 시작한다. US3·US4는 이 페이즈와 무관하다.

### Tests for Foundational ⚠️

- [X] T003 [P] `frontend/tests/useHeightHold.test.tsx` — `hooks/useHeightHold` (FR-001, FR-006, SC-001)
  - `hold(reload)` 동안 감싼 요소의 `minHeight`가 바꾸기 직전 높이(`getBoundingClientRect().height` 모의)다.
  - 다시 받기가 끝나면 놓는다.
    - 새 내용이 스크롤을 받칠 만큼 높으면 `minHeight`가 `""`다.
    - 새 내용이 짧아 "지금 스크롤 + 창 높이 − 요소 위치"보다 낮으면 그 바닥 값이 남는다(`window.scrollY`·`innerHeight` 모의).
  - 늦게 끝난 이전 붙잡기가 새 붙잡기를 놓지 않는다(차례 번호).
  - 다음 붙잡기가 남은 바닥을 새 높이로 바꾼다. 실패(거부된 약속)여도 놓는다.

### Implementation for Foundational

- [X] T004 `frontend/src/hooks/useHeightHold.ts` — `app/fx/page.tsx`의 `holdWhile`(`:41-52`)을 훅으로 뽑고, 놓을 때 바닥을 남기는 판정을 더한다 (FR-001, FR-006)
  - 반환: `{ref, style, hold(reload: () => Promise<void>)}`.
  - 외환 화면은 아직 바꾸지 않는다(T009).

**Checkpoint**: T003 통과. 외환 테스트는 그대로 통과한다.

---

## Phase 3: User Story 1 - 외환 표의 기간을 바꿔도 화면이 제자리다 (Priority: P1) 🎯 MVP

**Goal**: 일·주·월을 바꿔도 창이 움직이지 않는다. 먼 날짜 선택(FR-005a)·통화 전환은 지금 그대로다.

**Independent Test**: 외환 화면을 표 중간까지 내린 뒤 일 → 주 → 월을 누른다. 매번 단위 탭의 화면상 위치가 그대로이고 표는 새 단위의 최신 행부터 보인다
(quickstart 4-1).

### Tests for User Story 1 ⚠️

- [X] T005 [US1] 기존 테스트 변경 승인을 받는다 — research R12-15 US1의 둘 (FR-001)
  - `frontend/tests/PeriodSwitch.test.ts` "전환하면 스크롤을 처음으로 되돌릴 신호를 낸다" → `tableEpoch`가 그대로다
  - `frontend/tests/FxPageLayout.test.tsx` "StrictMode — … 기간 단위 전환은 새 표가 붙은 뒤 표의 처음으로 옮긴다" → 기간 전환 뒤에도 `scrollIntoView`가
    불리지 않는다(통화 부분은 그대로)
  - 바꿀 단언을 그대로 보이고 승인 날짜를 Notes에 적는다. 승인 없이는 T006·T007을 커밋하지 않는다.
- [X] T006 [P] [US1] `frontend/tests/PeriodSwitch.test.ts` — T005의 승인된 변경 + 새 검사 (FR-001, FR-002)
  - 기간 전환은 `tableEpoch`를 올리지 않는다. 먼 날짜의 다시 받기는 지금처럼 올린다(`fxWorkspaceScroll.test.ts`는 그대로).
  - 통화 전환의 `loadAll`이 늦게 와도 그 사이 기간이 바뀌었으면 `daily`를 덮지 않는다. 통화가 바뀌었을 때도 같다(spec FR-002 — 기존 결함).
- [X] T007 [P] [US1] `frontend/tests/FxPageLayout.test.tsx` — T005의 승인된 변경 + 새 검사 (FR-001, SC-001)
  - StrictMode에서 일 → 주 → 월을 눌러도 `scrollIntoView`가 불리지 않는다. 바꾸는 동안 높이를 붙잡는 지금 검사는 그대로다.
  - 먼 날짜(쌓인 행 밖)를 고르면 `scrollIntoView`가 한 번 불린다(004 FR-005a 그대로).
  - 새 표가 짧으면 놓은 뒤에도 바닥 `minHeight`가 남는다(T003의 판정이 화면에 들어왔는지).

### Implementation for User Story 1

- [X] T008 [US1] `frontend/src/stores/fxWorkspaceStore.ts` (FR-001, FR-002)
  - `setPeriod`가 `tableEpoch`를 올리지 않는다. 주석의 "FR-005b" 설명을 "먼 날짜(FR-005a)만의 신호"로 고친다.
  - `loadAll`이 요청을 시작한 때의 통화·단위와 응답을 받을 때의 값이 다르면 `daily`를 쓰지 않는다.
- [X] T009 [US1] `frontend/src/app/fx/page.tsx` — 통화·기간 전환을 `useHeightHold`(T004)로 감싼다 (FR-001, SC-001)
  - 화면의 `tableEpoch` 효과(`:54-63`)는 그대로 둔다 — 이제 먼 날짜에만 돈다.
- [X] T010 [US1] 브라우저 확인 — quickstart 4-1 (SC-001)
  - 1440px 창, CDP로 단위 탭의 `getBoundingClientRect().top`을 전환 전후에 잰다.
  - 일 → 주 → 월 → 일, 월에서 짧은 표, 먼 날짜, 통화 전환을 확인하고 quickstart 실행 기록에 적는다.

**Checkpoint**: US1 완결 — 외환 화면만으로 시연할 수 있다.

---

## Phase 4: User Story 2 - 주식·가상자산 일자별 투자 성과 표를 일·주·월로 본다 (Priority: P1)

**Goal**: 네 표(주식·가상자산 × 일시금·적립식)가 일·주·월을 고른다. 대표일·📅·⏳·사건 행·결측 구간 행은 서버가 정한다. 보드·차트는 그대로다.

**Independent Test**: 삼성전자 일시금(배당 재투자)과 비트코인 일시금을 실행하고 단위를 일·주·월로 바꾼다(spec US2 Independent Test, quickstart 3-1·3-2·4-2).

### Tests for User Story 2 ⚠️

- [X] T011 [US2] 기존 테스트 변경 승인을 받는다 — research R12-15 US2의 목록 (FR-003, FR-005, FR-008)
  - 목록의 테스트를 하나씩 읽어 바뀐 요구(월 행 → 기간 행, 기본 단위 일, `buy` 행, ◇ → 결측 구간 행, 차트-표 끝점 짝)를 단언하는지 가린다.
  - 바뀐 요구를 단언하지 않는 것은 목록에서 뺀다.
  - 남은 목록을 테스트마다 "지금 단언 → 새 단언"으로 보이고 승인을 받는다. 승인 날짜를 Notes에 적는다.
- [X] T012 [P] [US2] `backend/tests/unit/test_period_table.py` — `simulation/period_table` (FR-004, FR-004a, FR-004b, FR-005, FR-009, SC-002, SC-003)
  - quickstart 1의 표를 그대로 고정한다(손으로 만든 날짜 목록 — 2026-10 달력).
    - 금요일 휴장 주
    - 대체공휴일 계산 끝
    - 미국 주식 계산 끝 월요일
    - 토요일 말일
    - 가상자산 금요일 결측
    - 가상자산 월~금 결측
    - 구간에 시세일 없음
    - 대표일의 사건
    - 일 단위
    - 결측 구간 둘
    - 첫 주 금요일이 첫 평가일 전
    - 시세가 끊긴 종목의 끝난 마지막 구간
  - data-model 3.2 불변식
    - 사건 행이 모든 단위에 한 번씩
    - 기간마다 대표 행 하나
    - `shifted_from`은 대표일 ≠ 기준일일 때만
    - `is_ongoing`은 주·월에서 구간 끝 > 계산 끝일 때만
    - `missing`은 일 단위만, 수가 입력과 같음
  - `page`(data-model 3.3)
    - 같은 날 항목을 한 쪽에 붙잡는다
    - `Missing`의 커서는 `date_from`이다
    - `before` 미만만 돌려준다
    - `has_more`
  - 달력 함수 `period_bounds`·`anchor_of`·`is_ongoing`(data-model 3.1)
- [X] T013 [P] [US2] `backend/tests/unit/test_reinvest_daily.py` — `reinvest.Outcome.daily` (FR-004, FR-017, data-model 4)
  - 첫 매수일부터 일봉마다 하나, 오름차순이다.
  - 월 행이 있는 날의 상태는 그 월 행과 값이 같다.
  - 마지막은 `latest`와 값이 같다.
  - 매수일에만 `bought_shares`·`trade_fee`가 있다.
  - 배당락·재투자·분할 날은 그날 사건을 모두 처리한 뒤의 상태다.
  - `rows`·`latest`가 `daily`를 더하기 전과 같다(기존 단위 테스트가 그대로 통과하는 것과 함께).
- [X] T014 [P] [US2] `backend/tests/unit/test_recurring_stock_daily.py` — `recurring_stock.RecurringOutcome.daily` (FR-004, FR-005, FR-017)
  - 첫 납입일부터 일봉마다 하나이고 `kind = "day"`다.
  - 납입·배당·재투자 날은 그날 마지막 사건 행과 값이 같다.
  - 월 행이 있는 날은 월 행과 같다. 마지막은 `latest`와 같다.
- [X] T015 [P] [US2] `backend/tests/integration/test_stock_table_period_api.py` — `GET /api/stocks/simulation`의 `period` (FR-003~FR-005, FR-007~FR-009, SC-002, SC-003, SC-005, contracts/rest-api.md 1)
  - 질의
    - `period` 없음 → `"period": "daily"`
    - `weekly`·`monthly` 응답에 `period`가 실린다
    - `yearly`·`""` → 400 `invalid_query`, 메시지 "기간 단위는 daily · weekly · monthly 중 하나여야 합니다"
  - 행 종류
    - `kind`가 `buy`·`period`·`dividend`·`reinvest` 안이다. `month_first`가 없다
    - `buy` 행은 하나이고 `tradeFee`가 있다
  - 단위와 무관
    - `dividend`·`reinvest` 행 수가 세 단위에서 같다(SC-003)
    - `summary`·`condition`이 세 단위에서 같다(SC-005, FR-007)
    - `/series` 응답이 `period`와 무관하다(질의에 넣어도 무시)
  - 표시(국내 종목 픽스처 — 2026-10-09 금요일 휴장, 계산 끝 2026-10-05 휴장)
    - 주 행의 대표일·`shiftedFrom`
    - 진행 중 주의 `isOngoing`
    - 끝난 주에 표시 없음
    - 대표일의 배당락 행이 표시를 지고 날짜는 배당락일 그대로
  - 쪽: 같은 날 배당락·재투자 행이 쪽 경계에서 갈리지 않는다(`limit=1`로 경계를 만든다). `oldestReturned`로 끝까지 받으면 일 단위 행 수가 시세일 수(사건 날
    포함)와 맞는다. `period=weekly`·`monthly`도 `before=oldestReturned`로 끝까지 받으면 행이 겹치지도 빠지지도 않는다(FR-009 — 같은 기간 행이 두 쪽에
    나오지 않고, 사건 행 수가 한 번에 받은 것과 같다).
- [X] T016 [P] [US2] `backend/tests/integration/test_crypto_table_period_api.py` — `GET /api/crypto/simulation`의 `period` (FR-004, FR-004b, FR-008, SC-002)
  - `period=daily`
    - 출처 결측 이틀 → `{"kind": "missing", "date", "dateTo"}` 행 하나, 값 키 없음
    - 결측 행 수 = `/series`의 `source_missing` 끊김 수
    - 시작 월 1일 결측이면 매수일보다 앞의 결측 행이 표 맨 아래에 있다
  - `weekly`·`monthly`에는 `missing` 행이 없다.
  - 주: 금요일 결측·토일 있음 → 대표일 목요일·`shiftedFrom` 금요일. 월~금 결측 → 일요일.
  - 표 행에 `firstDayMissing`이 없다. `buy` 행에 수수료가 있다. `summary`가 세 단위에서 같다.
- [X] T017 [P] [US2] `backend/tests/integration/test_recurring_table_period_api.py` — 적립식 두 경로의 `period` (FR-003~FR-005, SC-003)
  - `contribution` 행(미뤄진 `deferred` 포함) 수가 세 단위에서 같다.
  - 납입이 있는 대표일에는 `period` 행이 없고 그날 마지막 사건 행이 표시를 진다.
  - 가상자산 적립식 일 단위의 결측 행 수 = 시계열 끊김 수(적립식은 시작일부터).
  - 응답 `condition`에 `period`가 없다(기존 정확 비교 보호). `summary`가 세 단위에서 같다.
- [X] T018 [US2] T011에서 승인된 백엔드 기존 테스트를 새 기대로 고친다 (FR-008)
  - research R12-15 US2 백엔드 목록이다. 바뀐 요구를 단언하는 줄만 고치고, 고친 줄 위에 `# 012 승인 <날짜>` 주석을 단다.
- [X] T019 [P] [US2] `frontend/tests/PeriodTabs.test.tsx` — 선택 속성 `titles` (FR-010)
  - `titles`를 주면 세 탭의 `title`이 그 값이다. 주지 않으면 지금 외환 문구다(기존 검사 그대로).
- [X] T020 [P] [US2] `frontend/tests/PeriodMarks.test.tsx` — `components/period/PeriodMarks`·`PeriodLegend` (FR-004, FR-004a, FR-010, contracts/ui-wireframes.md F3)
  - 📅·⏳의 `title`·`aria-label` 글자 설명이 F3 표와 글자까지 같다.
    - 주식은 "시세가 없어", 가상자산은 "일봉이 없어"다
    - 주는 "(금)", 월은 "(말일)"이다
  - 표시 없는 행·일 단위는 아무것도 그리지 않는다. 범례는 주·월에만 있다.
- [X] T021 [P] [US2] `frontend/tests/PerformanceTablePeriod.test.tsx` — 주식 일시금·적립식 표 (FR-004, FR-004a, FR-005, FR-010)
  - `shiftedFrom`·`isOngoing` 행에 표시가 붙고 둘이 구별된다.
  - `buy`·`period` 행은 지금 월 행처럼 그린다. 배당락·재투자·납입 기호는 그대로다.
  - 범례가 주·월에만 있다.
- [X] T022 [P] [US2] `frontend/tests/CryptoTablePeriod.test.tsx` — 가상자산 일시금·적립식 표 (FR-004b, FR-008, F4)
  - `missing` 행은 한 칸에 "MM-DD~MM-DD 출처 결측 — 값 없음"이고 값 칸이 없다.
  - ◇가 어디에도 없다.
  - 표시·범례는 T021과 같다.
- [X] T023 [P] [US2] `frontend/tests/stockStoreTablePeriod.test.ts` — `stockStore`의 표 단위 (FR-003, FR-006, FR-007, data-model 5.1)
  - 처음 `tablePeriod`는 `"daily"`이고 요청 문자열에 `period`가 없다.
  - `setTablePeriod("weekly")`
    - 요청에 `&period=weekly`가 붙는다(일시금·적립식 각자의 경로)
    - 행·`hasMore`·`oldestReturned`만 바뀌고 `summary`·시계열은 같은 객체다
  - 늦은 응답
    - 주 → 월 사이에 늦게 온 주 응답은 버린다
    - 일 → 주 → 일의 첫 "일" 응답도 버린다(차례 번호)
    - 이어 받기도 같은 번호를 본다
  - 다시 실행해도 고른 단위가 남는다. 이력의 다시 실행도 같다.
  - 실패하면 고른 단위는 남고 표 자리에 오류가 있다.
- [X] T024 [P] [US2] `frontend/tests/cryptoStoreTablePeriod.test.ts` — `cryptoStore`의 같은 검사 (FR-003, FR-006, FR-007)
- [X] T025 [P] [US2] `frontend/tests/StocksCryptoPagePeriod.test.tsx` — 두 화면 (FR-003, FR-006, FR-010, SC-005)
  - `lightweight-charts`를 모의한다.
  - 표 머리에 `role="tablist"` 단위 탭이 있고 처음이 "일"이다. 탭 제목은 F2 문구다.
  - 탭을 바꾸면
    - `scrollIntoView`가 불리지 않는다
    - 바꾸는 동안 높이를 붙잡는다
    - 보드 글자가 그대로다
- [X] T026 [US2] T011에서 승인된 프론트엔드 기존 테스트를 고친다 (FR-008)
  - 표 테스트의 고정 행 `kind: "month_first"` → `"period"`(단언은 그대로)
  - ◇ 검사 둘 → 결측 구간 행 검사

### Implementation for User Story 2

- [X] T027 [US2] `backend/src/simulation/period_table.py` — 달력·`build_table`·`page` (FR-004, FR-004a, FR-004b, FR-005, FR-009, data-model 3)
  - 대표일: 주는 "그 주 ∩ 계산 기간에서 금요일 이하의 마지막 시세일, 없으면 그 주 ∩ 계산 기간의 마지막 시세일", 월은 "그 달 ∩ 계산 기간의 마지막
    시세일"이다(research R12-3).
  - `is_ongoing`은 `period_to > end`(일 단위는 거짓)다.
- [X] T028 [US2] `backend/src/simulation/reinvest.py`·`recurring_stock.py` — `daily` 더하기 (FR-004, FR-017, data-model 4)
  - `Outcome.daily: tuple[Row, ...] = ()`, `RecurringOutcome.daily: tuple[RecurringRow, ...] = ()`, `RowKind`에 `"day"`.
  - `rows`·`latest`의 계산 줄은 고치지 않는다.
- [X] T029 [US2] 주식 표 경로 — `backend/src/api/services/stock_simulation.py`·`stock_recurring.py`·`backend/src/api/routes/stock_simulation.py`·`stock_recurring.py` (FR-003~FR-005, FR-007~FR-009, contracts/rest-api.md 1)
  - `period` 질의(밖이면 `InvalidQuery`)와 응답 `period`를 더한다.
  - 사건 행을 모은다 — 일시금 `buy`는 매수일의 월 행이다.
  - `build_table` → `page` → 쪽의 항목만 행 JSON으로 바꾼다(원화 환산 포함).
  - `kind`·`shiftedFrom`·`isOngoing`을 싣는다.
  - 기존 쪽 함수(`stock_simulation.page`·`stock_recurring`의 쪽)는 `period_table.page`로 바꾼다.
- [X] T030 [US2] 가상자산 표 경로 — `backend/src/api/services/crypto_simulation.py`·`crypto_recurring.py`·`backend/src/api/routes/crypto_simulation.py`·`crypto_recurring.py` (FR-003~FR-005, FR-004b, FR-008)
  - T029와 같다.
  - 일 단위는 `series_query.compute_gaps(…, inside_reason="source_missing")`를 시계열 경로와 같은 입력으로 불러 `missing`을 넘긴다. 입력은 일시금은 시작 월 1일,
    적립식은 시작일부터다.
  - 표 행 JSON에서 `firstDayMissing`을 뺀다.
- [X] T031 [US2] `frontend/src/lib/types.ts` — 행 `kind`(`buy`·`period`·`missing`, `month_first` 제거)·`shiftedFrom?`·`isOngoing?: true`·`dateTo`, 응답 `period`, 결측 행 판별 합 타입 (contracts/rest-api.md 1.3)
- [X] T032 [US2] `frontend/src/components/fx/PeriodTabs.tsx`(선택 속성 `titles`)·`frontend/src/components/period/PeriodMarks.tsx`·`PeriodLegend.tsx` (FR-010, F2·F3)
- [X] T033 [US2] 표 넷 — `components/stock/PerformanceTable.tsx`·`components/crypto/CryptoPerformanceTable.tsx`·`components/recurring/RecurringStockTable.tsx`·`RecurringCryptoTable.tsx` (FR-004, FR-004a, FR-004b, FR-005, FR-008, F3·F4)
  - 속성 `period`를 더한다.
  - 날짜 칸에 `PeriodMarks`, 표 아래에 `PeriodLegend`를 둔다.
  - `missing` 행을 그리고 ◇ 그리기를 지운다. `data-kind`·키는 `${date}:${kind}`다.
- [X] T034 [US2] `frontend/src/stores/stockStore.ts`·`cryptoStore.ts` — `tablePeriod`·`tableSeq`·`setTablePeriod` (FR-003, FR-006, FR-007, data-model 5.1)
  - 실행·이어 받기·다시 실행에 `period`(일이 아니면)와 차례 번호를 쓴다.
- [X] T035 [US2] `frontend/src/app/stocks/page.tsx`·`frontend/src/app/crypto/page.tsx` (FR-003, FR-006, F2·F5)
  - 표 머리에 `PeriodTabs`(F2 제목)를 둔다.
  - 단위 전환을 `useHeightHold`로 감싼다.
  - 전환 중에는 "⟳ 불러오는 중…"을 보인다.
- [X] T036 [US2] 검증 — quickstart 3-1·3-2·3-3(API)·4-2(브라우저) (SC-002, SC-003, SC-005)
  - 배당·재투자 행 수, 결측 행 수 = 끊김 수, 세 단위 `summary`, 창 위치, 이어 받기를 확인한다.
  - quickstart 실행 기록에 적는다.

**Checkpoint**: US2 완결 — 네 표가 일·주·월을 고르고 보드·차트가 그대로다.

---

## Phase 5: User Story 3 - 최근 시뮬레이션 이력이 로컬 DB에 남고 보관 기간을 정한다 (Priority: P2)

**Goal**: 네 자산군의 이력이 DB에 있다. 보관 기간을 설정에서 고른다(기본 30일). 브라우저 이력은 화면을 처음 열 때 옮긴다.

**Independent Test**: 이력이 있는 브라우저에서 새 버전을 연다. 항목이 그대로 보이고, 다른 브라우저에서도 같다. 보관 기간을 7일로 바꾸면 보관 기준 시각이 7일보다 오래된
항목이 사라진다(spec US3 Independent Test, quickstart 2·3-4·3-5·4-3~4-5).

### Preparation for User Story 3

- [X] T037 [US3] 개발 DB 상태를 확인한다 — 머리 리비전이 `f4c2a8e19d35`인지(`alembic current`). 다르면 멈추고 보고한다 (data-model 1)

### Tests for User Story 3 ⚠️

- [X] T038 [US3] 기존 테스트 변경 승인을 받는다 — research R12-15 US3의 목록 (FR-011, FR-013, FR-015)
  - lib 테스트 일곱은 삭제·옮김이다. 어느 검사가 서버 테스트(T039·T040)나 옮기기 테스트(T044·T046)로 가는지 짝을 보인다.
  - 안내 문구 검사 다섯은 새 문구로 바꾼다.
  - 브라우저 키에 심는 스토어·화면 테스트는 대역(T043)에 심게 바꾼다.
  - 승인 날짜를 Notes에 적는다.
- [X] T039 [P] [US3] `backend/tests/unit/test_history_conditions.py` — `api/services/history_conditions` (FR-011, FR-013, data-model 2)
  - 식별자 대조
    - 지금 화면 lib 테스트에 나오는 식별자 예시(자산군 넷 — 일시금·적립식·적금·`buyPrice: null`)를 서버 함수가 글자까지 같게 낸다
    - 011 전 형식(`mode`·`frequency`·`product` 없음)은 일시금·정기예금의 식별자다
  - 검증 — 어기면 `InvalidHistory`이고 메시지가 칸을 말한다
    - "날짜(`start`·`buyDate`)는 ISO 날짜다"
    - "`principal`·`buyPrice`는 0보다 큰 십진 문자열 — 서버가 계산하지 않고 받은 글자 그대로 둔다"
    - "`frequency`는 `daily·weekly·monthly·yearly`"
    - "`mode`는 `recurring`, 그 밖의 방식은 칸을 두지 않는다"
    - "문자열 칸의 길이는 각각 200 이하, 식별자는 255 이하"
  - 직렬화가 칸 차례와 무관하게 같은 글이다. 원금 `"10000000"`이 글자 그대로 돌아온다(수로 바뀌지 않는다).
  - `history_conditions`·`history`·`repository/simulation_history`에 곱셈·나눗셈·`quantize`가 없다(덧셈·뺄셈은 보관 기간의 시각 계산에만) — 원금은 검증의 `Decimal(…)` 읽기뿐이다
    (원칙 VI 해석의 장치, plan Complexity Tracking — 사용자 확인 2026-10-06).
- [X] T040 [P] [US3] `backend/tests/integration/test_history_api.py` — 이력 경로 넷 (FR-011, FR-013, FR-014, SC-006, contracts/rest-api.md 2~5·7)
  - 목록·저장·삭제
    - 빈 목록 GET은 `{"entries": [], "retentionDays": 30}`이다
    - PUT 뒤 GET, 같은 조건 다시 PUT이면 항목 하나·맨 앞이고 `lastRunAt`이 바뀐다
    - 다른 조건은 마지막 실행 내림차순이다
    - DELETE는 멱등이고, `id`가 없으면 400 `invalid_query`다
  - 오류: 모르는 자산군은 404 `unknown_asset`, 틀린 조건은 422 `invalid_history`다.
  - 자산군 분리: 주식에 넣은 항목이 가상자산 목록에 없다.
  - 옮기기
    - `imported`·`merged`·`skipped` 수
    - 항목의 `id`는 무시하고 다시 계산한다
    - 차례는 `savedAt`이다
    - 45일 전 `savedAt` 항목이 남는다(보관 기준 = 옮긴 시각)
    - `savedAt`이 없거나 ISO 시각이 아니면 마지막 실행 시각은 옮긴 시각이다. 항목은 건너뛰지 않는다(조건이 맞으면 옮긴다)
    - 같은 조건 합치기는 늦은 쪽이다
    - 본문이 배열이 아니면 400 `invalid_query`
  - 결과(평가·수익률)를 저장하지 않는다 — 조건 칸 밖의 키는 버린다.
- [X] T041 [P] [US3] `backend/tests/integration/test_history_retention.py` — 보관 기간 (FR-012, SC-007, contracts/rest-api.md 6)
  - `history.utc_now`를 바꾼다.
  - 30일에서 보관 기준이 30일 + 1초 전이면 목록에 없고 DB에서도 지워졌다. **정확히 30일 전은 남는다**(`retain_from < 지금 − 기간` — data-model 1.1). 29일
    전도 남는다.
  - 다시 실행한 항목은 처음 저장 시각이 오래돼도 남는다.
  - 무기한은 지우지 않는다.
  - 설정
    - GET 기본값은 `{"retentionDays": 30, "isDefault": true, "options": [7, 30, 90, 180, 365, null]}`이다
    - `PUT {"retentionDays": 7}` 직후 네 자산군 모두에서 8일 된 항목이 지워졌다
    - `10`·`"30"`·`true`·`30.0`은 422 `invalid_setting`이다
  - `GET /api/history/settings`가 자산군 경로로 잡히지 않는다.
- [X] T042 [P] [US3] `backend/tests/integration/test_history_schema.py` — 마이그레이션 (data-model 1)
  - 두 테이블과 기본 키 `(asset_class, condition_key)`·`ix_simulation_history_list`가 있다. `history_setting.retention`이 비원생 열거다.
  - 내렸다 다시 올리기를 한다(`test_deposit_schema.py`와 같은 방식).
  - 기존 일반 검사(`test_migrations.py`)는 그대로 통과해야 한다.
- [X] T043 [US3] `frontend/tests/setup.ts` — `/api/history` 경로만 받는 메모리 안 대역을 **더한다** (research R12-12)
  - `fetch`를 감싸 목록·저장·삭제·옮기기·설정을 흉내 낸다. 식별자는 조건 칸을 정렬해 이은 글이다. 단, **옮기기로 받은 항목에 `id`가
    있으면 그것을 쓴다** — 옛 키에 `id`를 넣어 둔 기존 화면 테스트(`StocksPageRerun` 등)가 그 `id`로 항목을 찾는다. 서버 식별자 규칙과의 일치는 T039가 따로
    확인한다.
  - 테스트마다 비운다. 그 밖의 경로는 지금처럼 원래 `fetch`로 넘긴다.
  - 심기·읽기·실패 만들기 도우미를 `frontend/tests/support/historyStub.ts`로 둔다(다른 테스트 도우미와 같은 자리).
- [X] T044 [P] [US3] `frontend/tests/legacyHistory.test.ts` — `lib/legacyHistory` (FR-013, data-model 5.3)
  - 키 넷이 글자까지 같다 — `assetreplay:stock-history:v1`·`assetreplay:crypto-history:v1`·`assetreplay.depositHistory.v1`·`assetreplay:realestate-history:v1`.
  - 읽기는 `none`·`unreadable`(JSON 아님)·`entries`로 나뉜다.
  - `clearLegacy`는 그 키만 지운다.
- [X] T045 [P] [US3] `frontend/tests/historyApi.test.ts` — `lib/historyApi`·`apiClient.delete` (contracts/rest-api.md 2~6)
  - 경로·방법·본문이 계약대로다. `id`는 질의로 인코딩한다(`|`·`:` 포함).
  - 오류는 `ApiError`다.
- [X] T046 [P] [US3] `frontend/tests/historyStoreMigration.test.ts` — 네 스토어의 `restoreHistory` (FR-013, FR-014a, SC-006, data-model 5.2)
  - 자산군마다 매개변수로 돈다.
  - 차례: 옛 키 → 옮기기 → 2xx면 키 삭제 → 목록. 다른 자산군의 키는 그대로다.
  - 실패
    - 옮기기가 실패하면 키가 남고 `historyLoadError`다
    - 목록이 실패하면 `historyLoadError`이고 빈 목록이 아니다
    - 다시 시도가 같은 차례를 한다
  - `unreadable` 키는 옮기지도 지우지도 않는다.
  - `historyLoading`은 첫 목록 전까지 참이다. `skipped > 0`이면 `historyNotice`다.
- [X] T047 [P] [US3] `frontend/tests/historyStoreSave.test.ts` — 네 스토어의 저장·삭제 (FR-011, FR-014)
  - 200 결과 뒤 `PUT`의 `condition`이 지금 항목 모양(`id`·`savedAt` 없음)이다. 202 뒤에는 저장하지 않는다.
  - 저장이 실패하면 결과는 그대로이고 `historySaveError`가 F6 문구다. 삭제가 실패하면 "이력을 지우지 못했습니다."다.
  - 다시 실행·비교가 서버 `id`로 항목을 찾는다.
  - 저장 응답 목록으로 `history`가 바뀌고 `retentionDays`가 실린다.
  - 목록이 새로 와서 선택한 항목이 빠지면(보관 기간 정리), `selectedHistory`에서 그 `id`가 빠지고 이미 받은 `comparison`은 그대로다(spec Edge Cases — 비교에
    쓰인 항목이 기간 지나 지워짐). 비교 단추는 남은 선택 수로 판단한다.
- [X] T048 [P] [US3] `frontend/tests/HistoryPanelStates.test.tsx` — 이력 부품 넷 (FR-014, FR-014a, FR-015, contracts/ui-wireframes.md F6)
  - 안내
    - "ⓘ 이 기기의 로컬 DB에 저장됩니다. 마지막 실행 뒤 30일이 지나면 지워집니다 — 기간은 설정에서 바꿉니다." + 자산군 구별 문구(지금 그대로)
    - 무기한이면 "기한 없이 남습니다."다
    - "이 브라우저"가 어디에도 없다
  - 상태
    - 불러오는 중에는 빈 상태 문구가 없다
    - 불러오기 실패는 `role="alert"`와 다시 시도 단추이고, 누르면 `onRetry`다
    - 옮기지 못한 수를 알린다
  - 지금 속성만으로 그려도 그대로 그린다(선택 속성).
- [X] T049 [P] [US3] `frontend/tests/HistoryRetentionSection.test.tsx` — 설정 절 (FR-012, F7)
  - GET으로 값을 보이고, 선택지는 여섯(7일·30일·90일·180일·365일·무기한)이다. 줄이면 곧바로 지워진다는 안내가 있다.
  - 저장은 `PUT {"retentionDays": …}`이고 무기한은 `null`이다.
  - 성공하면 "저장했습니다. 기간이 지난 항목은 곧바로 지웠습니다."다. 실패하면 붉은 `role="alert"`에 서버 메시지다.
- [X] T050 [US3] T038에서 승인된 프론트엔드 기존 테스트를 고친다 (FR-011, FR-015)
  - lib 테스트 일곱을 삭제한다. 그 검사는 T039·T040·T044·T046으로 옮겨졌는지 T038의 짝으로 확인한다.
  - 안내 문구 검사를 새 문구로 바꾼다.
  - 키에 심는 테스트를 대역 도우미로 바꾼다. 고친 줄 위에 `// 012 승인 <날짜>` 주석을 단다.

### Implementation for User Story 3

- [X] T051 [US3] `backend/src/db/models.py`·`backend/src/db/migrations/versions/<rev>_시뮬레이션_이력.py` (`down_revision = "f4c2a8e19d35"`) (FR-011, FR-012, data-model 1)
  - `simulation_history`: `asset_class Enum("stock","crypto","deposit","realestate", native_enum=False, length=16) PK`, `condition_key String(255) PK`,
    `condition Text NOT NULL`, `last_run_at DateTime(timezone=False) NOT NULL`, `retain_from DateTime(timezone=False) NOT NULL`,
    `ix_simulation_history_list (asset_class, last_run_at)`.
  - `history_setting`: `id SmallInteger PK 기본 1`, `retention Enum("days_7","days_30","days_90","days_180","days_365","unlimited", native_enum=False, length=16) NOT NULL`,
    `updated_at server_default now() onupdate`.
  - 개발 DB에 `alembic upgrade head`를 올린다.
- [X] T052 [US3] `backend/src/repository/simulation_history.py`·`history_setting.py` (FR-011~FR-013, data-model 1)
  - 목록(마지막 실행 내림차순)·upsert(`db/dialect.upsert`)·합치기(늦은 쪽)·삭제·정리(`retain_from < cutoff`)
  - `get_retention`·`save_retention` — 행이 없으면 `DEFAULT_RETENTION = "days_30"`
- [X] T053 [US3] `backend/src/api/services/history_conditions.py`·`history.py` (FR-011~FR-014, data-model 2, research R12-10·R12-11)
  - 검증·직렬화·식별자와 `utc_now()`
  - 목록·저장·삭제·옮기기는 같은 거래 안에서 정리를 먼저 한다. 설정 저장은 모든 자산군을 정리한다.
- [X] T054 [US3] `backend/src/api/routes/history.py`·`backend/src/api/errors.py`(`UnknownAsset`·`InvalidHistory`)·`backend/src/api/main.py`(처리기·라우터 — 설정 경로 먼저) (contracts/rest-api.md 2~7)
- [X] T055 [US3] `frontend/src/lib/apiClient.ts`(`request` 공개, `delete`)·`frontend/src/lib/historyApi.ts`·`frontend/src/lib/legacyHistory.ts`·`frontend/src/lib/types.ts`(목록 응답·`lastRunAt`) (research R12-12)
- [X] T056 [US3] 스토어 넷 — `frontend/src/stores/stockStore.ts`·`cryptoStore.ts`·`depositStore.ts`·`realEstateStore.ts` (FR-011, FR-013, FR-014, FR-014a, data-model 5.2)
  - 비동기 `restoreHistory`, `historyLoading`·`historyLoadError`·`historyNotice`·`retentionDays`
  - 저장 `PUT`·삭제 `DELETE`
  - `frontend/src/lib/simulationHistory.ts`·`cryptoHistory.ts`·`depositHistory.ts`·`realEstateHistory.ts`를 지운다.
  - 넷이 같은 흐름(불러오기·옮기기·저장·삭제와 실패 문구)은 `frontend/src/lib/historyFlow.ts` 한 곳에 둔다 — 한 자산군만 실패를 삼키지 않게 한다.
- [X] T057 [US3] 이력 부품 넷 — `components/stock/SimulationHistory.tsx`·`components/crypto/CryptoHistory.tsx`·`components/deposit/DepositHistory.tsx`·`components/realestate/RealEstateHistory.tsx` (FR-014, FR-014a, FR-015, F6)
  - 선택 속성: `loading`·`loadError`·`onRetry`·`notice`·`retentionDays`
  - 안내 문구를 바꾼다.
  - 안내·상태는 `frontend/src/components/history/HistoryStates.tsx`(`HistoryNotice`·`HistoryContent`)를 넷이 함께 쓴다.
- [X] T058 [US3] `frontend/src/components/settings/HistoryRetentionSection.tsx`(불러오기·저장·알림을 함께 가진 절 — T049가 홀로 그린다)·`frontend/src/app/settings/page.tsx`(맨 아래 절) (FR-012, F7)
- [X] T059 [US3] 화면 넷 — `frontend/src/app/{stocks,crypto,deposit,realestate}/page.tsx` — 이력 부품에 새 속성을 넘긴다. 마운트 효과의 주석("이력은 브라우저에 있다")을 고친다 (FR-014a, FR-015)
- [X] T060 [US3] 검증 — quickstart 2·3-4·3-5(API)·4-3~4-5(브라우저) (FR-011~FR-015, SC-006, SC-007)
  - 012 전 형식 옛 키가 있는 브라우저 프로필에서 네 화면을 연다.
  - 다른 브라우저에서 같은 목록이 보인다.
  - 백엔드를 멈추면 불러오기 실패와 다시 시도가 보인다.
  - 보관 기간 7일 저장
  - quickstart 실행 기록에 적는다.

**Checkpoint**: US3 완결 — 이력이 DB에 있고 보관 기간이 반영된다.

---

## Phase 6: User Story 4 - 투자 원금 칸이 10,000,000원으로 채워져 열린다 (Priority: P3)

**Goal**: 주식·가상자산·예금 화면을 처음 열면 원금 칸이 10,000,000이다. 그 밖의 흐름은 지금 그대로다.

**Independent Test**: 브라우저를 새로 열고 세 화면을 연다. 원금 칸이 모두 10,000,000이고 종목(코인·투자처)만 고르면 실행된다(quickstart 4-6).

### Tests for User Story 4 ⚠️

- [X] T061 [P] [US4] `frontend/tests/principalDefault.test.ts` — 세 스토어 (FR-016, SC-008, data-model 5.4)
  - `vi.resetModules()` 뒤 새로 불러온 스토어의 `input.principal`이 `"10000000"`이고 통화가 `KRW`다(주식·가상자산).
  - 방식(적립식)·상품(적금)·원금 통화를 바꿔도 `"10000000"`이다.
  - 사용자가 고친 값은 화면을 오가도 남는다.
  - 이력 다시 실행은 항목의 값(`"3000000"`)을 넣는다.
- [X] T062 [P] [US4] `frontend/tests/PrincipalDefaultPages.test.tsx` — 세 화면 (FR-016, SC-008, F8)
  - `lightweight-charts`를 모의한다.
  - 원금 칸이 "10,000,000"이고 이름표만 방식·상품에 따라 바뀐다.
  - 종목·코인·투자처를 고르면 실행 단추가 켜진다.
  - 부동산 화면은 바뀌지 않는다(매입가 칸이 비어 있다).

### Implementation for User Story 4

- [X] T063 [US4] `frontend/src/lib/principalFormat.ts`(`DEFAULT_PRINCIPAL = "10000000"`)·`frontend/src/stores/stockStore.ts`·`cryptoStore.ts`·`depositStore.ts`의 처음 `input.principal` (FR-016)
- [X] T064 [US4] 브라우저 확인 — quickstart 4-6 (SC-008)

**Checkpoint**: US4 완결.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T065 성능을 잰다 (SC-004, research R12-16, quickstart 3-6)
  - 20년 일 단위 첫 쪽·다음 쪽을 각각 잰다.
    - 국내 주식 일시금
    - 비트코인 일시금
    - 매일 적립 주식
  - 3초 넘으면 멈추고 보고한다(하루하루 상태의 원화 환산이 쪽 크기만인지 먼저 본다).
- [X] T066 문서를 갱신한다
  - `CLAUDE.md` "현재 상태" 표에 012 한 줄을 더한다.
  - 주의 문단을 더한다.
    - 표의 `period`(`daily`이면 보내지 않음)
    - 기간 표는 `simulation/period_table.py`, 주식 `daily`는 차트에 쓰지 않음
    - 이력은 DB(`simulation_history`·`history_setting`)이고 `/api/history/settings`가 먼저다
    - 옛 키는 옮기기 2xx 뒤에만 지운다
    - 테스트의 이력 대역(`tests/setup.ts`)
  - 외환 스크롤 문단의 "기간 전환 뒤 표의 처음으로"를 012 동작으로 고친다.
  - `README.md` 기능 설명, 개발 DB 마이그레이션 안내
  - `spec.md` Status
- [X] T067 품질 게이트를 돌린다(서버를 내린 채) — 백엔드 `pytest -q --cov=src`(커버리지 80% 이상)·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .` (헌법 품질 게이트)
  - 통과 수와 종료 코드를 Notes에 적는다.
  - 이 기능 전 커밋과 견주어 바뀐 기존 테스트 파일이 승인 목록(T005·T011·T038)과 `tests/setup.ts`(더하기만)뿐인지 `git diff --stat --diff-filter=MD`로 확인한다.
- [X] T068 불변 대조 (FR-017, SC-009, quickstart 3-7)
  - 서버를 띄우고 T001의 응답을 같은 입력으로 다시 받아 `summary`·`condition`·`/series`를 비교한다. 표 `rows`는 비교하지 않는다.
  - 다른 키·값이 있으면 멈추고 보고한다.

---

## Phase 8: User Story 5 - 성과 보드에 현재 잔고가 보인다 (Priority: P3) — 반복 2026-10-07

**Goal**: 주식·가상자산 성과 보드 넷(일시금·적립식)에 현재 잔고 칸을 더한다. 예금·정기 적금·부동산 보드는 그대로다(spec US5, FR-018).

**Independent Test**: 삼성전자 일시금·비트코인 일시금·삼성전자 매일 적립·AAPL(USD 원금) 일시금을 실행한다. 칸 차례가 F9와 같고, 현재 잔고 − 투자 원금(원화) =
보유 중 투자 수익이며, 일 단위 표 맨 위 행의 원화 잔고와 같다. 예금 보드는 그대로다(quickstart 5).

### Tests for User Story 5 ⚠️

- [X] T069 [US5] 바뀌는 기존 테스트 승인을 받는다 (FR-018)
  - 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만든다. 없으면 없음을 Notes에 적는다.
  - 예상: 없다 — 보드 테스트는 칸을 이름(`role="group"`)으로 찾고 칸 수를 세지 않는다. `PerformanceBoardSaleCost.test.tsx`의 "네 칸이다"·"세 칸"은 `totalKrw`가 없는
    형식이라 그대로다.
- [X] T070 [P] [US5] `backend/tests/integration/test_board_total_krw.py` — 일시금 요약의 `totalKrw` (FR-018, SC-010, data-model 4.1, rest-api 1.2)
  - 주식(원화 원금·USD 원금 — AAPL)·가상자산(원화 원금)의 `summary.totalKrw`가 있다.
  - `totalKrw − (principalKrw ?? principal) = profit`이 문자열 Decimal로 0원 차이다.
  - 원화 종목·원화 원금이면 일 단위 표 기준일(첫 쪽 맨 위) 행의 `balance + cash`와 같다(행의 `balance`는 보유 평가액만 — 예수금이 따로다).
  - 적립식 요약은 `totalKrw − contributedKrw = profit`이다(011 — 그대로).
  - `/series`에는 없다. 적립식 요약의 `totalKrw`는 그대로다(011).
- [X] T071 [P] [US5] `frontend/tests/PerformanceBoardTotal.test.tsx` — `components/stock/PerformanceBoard` (FR-018, SC-010, F9)
  - 주식(`saleCost` 있음): 다섯 칸이 투자 원금 · 현재 잔고 · 매도 수수료/세금 · 투자 수익 · 수익률 차례다. 가상자산(`saleCost` 없음): 네 칸.
  - 현재 잔고는 `₩` 값이다. USD 원금이어도 원화만이다. 손익 색이 없다. 칸 안에 "잔고 + 예수금"이 있다.
  - `totalKrw`가 없으면 칸이 없다(예금 — 지금 세 칸 그대로).
  - 화면이 원금 + 수익을 더하지 않는다 — 서로 맞지 않는 값을 줘도 서버의 `totalKrw`가 그대로 보인다.
- [X] T072 [P] [US5] `frontend/tests/RecurringBoardTotal.test.tsx` — `components/recurring/RecurringBoard` (FR-018, SC-010, F9)
  - 주식·가상자산 모두 여섯 칸이 총 납입 원금 · 현재 잔고 · 매매 수수료 총액 · 세금 총액 · 투자 수익 · 수익률 차례다.
  - 현재 잔고는 `summary.totalKrw`의 `₩` 값이고 손익 색이 없다. 칸 안에 주식 "잔고 + 매수 대기금 + 배당 현금", 가상자산 "잔고 + 매수 대기금"이 있다.

### Implementation for User Story 5

- [X] T073 [US5] `backend/src/api/routes/stock_simulation.py`·`backend/src/api/routes/crypto_simulation.py` — `summary_json`에 `totalKrw` (FR-018, research R12-17)
  - 투자 수익을 만든 같은 원화 평가값이다 — `profit + (principalKrw ?? principal)`(적립식 011의 `profit + basisKrw`와 같은 방식). 따로 환산하지 않는다.
- [X] T074 [US5] `frontend/src/lib/types.ts`(`SimulationSummary.totalKrw?`·가상자산 요약)·`frontend/src/components/stock/PerformanceBoard.tsx`(`totalKrw`가 있으면
  투자 원금 다음 칸)·`frontend/src/components/recurring/RecurringBoard.tsx`(총 납입 원금 다음 칸) (FR-018, F9)
- [ ] T075 [US5] 브라우저 확인 — quickstart 5(네 보드·USD 원금·예금 보드) (FR-018, SC-010)
- [ ] T076 [US5] 게이트(서버를 내린 채 — T067과 같은 명령)·불변 대조(T001 기준 — `totalKrw`를 빼고 견준다, quickstart 3-7)·문서(CLAUDE.md·README의 012 줄에 US5,
  spec Status) (FR-017, FR-018, SC-009)

**Checkpoint**: US5 완결.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작한다. **T001·T002는 다른 모든 코드 변경보다 먼저다.**
- **Foundational (Phase 2)**: T002 뒤. US1·US2만 막는다.
- **US1 (Phase 3)**: Foundational 뒤. **T005(승인)가 T006·T007의 커밋을 막는다.** MVP다.
- **US2 (Phase 4)**: Foundational 뒤. **T011(승인)이 T018·T026을 막는다.** 백엔드(T012~T018·T027~T030)는 화면(T019~T026·T031~T035)과 나란히 할 수 있다.
- **US3 (Phase 5)**: T002 뒤면 시작할 수 있다(Foundational과 무관). **T038(승인)이 T050을 막는다.** T043(대역)은 T056(스토어)보다 먼저다 — 대역 없이
  스토어를 바꾸면 이력과 무관한 화면 테스트 수십 개가 흔들린다.
- **US4 (Phase 6)**: T002 뒤면 시작할 수 있다.
- **Polish (Phase 7)**: 모든 스토리 뒤
- **US5 (Phase 8 — 반복 2026-10-07)**: 012 완료(Phase 7) 뒤. **T069(승인)가 T074의 커밋을 막는다.** 테스트 T070~T072는 함께 쓴다

스토리를 하나씩 끝내려면 US1 → US2 → US3 → US4 차례다. 같은 파일을 여러 스토리가 만지므로(아래 표) 스토리 사이에는 나란히 하지 않는다.

### Within Each Phase

- 승인(있으면) → 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 백엔드는 순수 계산 → 저장소 → 서비스 → 라우트, 화면은 순수 함수·부품 → 스토어 → 화면 순서다.

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `frontend/src/stores/stockStore.ts`·`cryptoStore.ts` | T034(US2), T056(US3), T063(US4) |
| `frontend/src/stores/depositStore.ts` | T056, T063 |
| `frontend/src/lib/types.ts` | T031, T055, T074 |
| `backend/src/api/routes/stock_simulation.py`·`crypto_simulation.py` | T029·T030(US2), T073(US5) |
| `frontend/src/components/stock/PerformanceBoard.tsx`·`components/recurring/RecurringBoard.tsx` | T074 |
| `frontend/src/app/stocks/page.tsx`·`crypto/page.tsx` | T035, T059 |
| `frontend/src/app/fx/page.tsx` | T009 |
| `frontend/src/components/fx/PeriodTabs.tsx` | T032 |
| `backend/src/api/services/stock_simulation.py`·`stock_recurring.py`·`routes/stock_*` | T029 |
| `backend/src/api/services/crypto_simulation.py`·`crypto_recurring.py`·`routes/crypto_*` | T030 |
| `backend/src/api/main.py`·`errors.py` | T054 |
| `frontend/tests/setup.ts`(더하기만) | T043 |
| `specs/012-…/quickstart.md`(실행 기록) | T010, T036, T060, T064, T065, T075 |

### Parallel Opportunities

- US2 테스트 T012~T017은 다른 파일이라 함께 쓴다. 화면 테스트 T019~T025도 함께 쓴다.
- US3 테스트 T039~T042(백엔드)와 T044~T049(화면 — T043 뒤)는 함께 쓴다.
- US4 테스트 T061·T062는 함께 쓴다.
- US5 테스트 T070~T072는 함께 쓴다.

---

## Parallel Example: Phase 4 (US2 테스트)

```text
Task: "T012 test_period_table.py — 대표일·표시·사건 행·결측 행·쪽"
Task: "T013 test_reinvest_daily.py — 일시금 하루하루 상태 불변식"
Task: "T014 test_recurring_stock_daily.py — 적립식 하루하루 상태 불변식"
Task: "T015 test_stock_table_period_api.py — period 질의·종류·표시·쪽"
Task: "T016 test_crypto_table_period_api.py — 결측 구간 행 = 시계열 끊김"
Task: "T017 test_recurring_table_period_api.py — 납입 행·condition 불변"
Task: "T019 PeriodTabs.test.tsx — titles"
Task: "T020 PeriodMarks.test.tsx — 글자 설명·범례"
Task: "T021~T022 표 테스트 — 표시·결측 행·◇ 없음"
Task: "T023~T024 스토어 테스트 — 단위·차례 번호·요약 불변"
Task: "T025 화면 테스트 — 탭·창 그대로"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1(기준 응답·기준 게이트) → Phase 2(높이 붙잡기 훅)
2. Phase 3 (US1) — **멈추고 검증**(T010): 외환 단위 탭이 제자리에 남는다.

### Incremental Delivery

1. MVP(US1) — 외환 기간 전환
2. US2 — 주식·가상자산 일·주·월 표(승인 B)
3. US3 — 이력의 로컬 DB와 보관 기간(승인 C)
4. US4 — 원금 기본값
5. Polish — 성능·문서·게이트·불변 대조
6. US5(반복 2026-10-07) — 보드의 현재 잔고

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(012): <페이즈>`
     - 그 페이즈의 새 테스트와 **승인된 기존 테스트 변경**을 담는다(승인 날짜를 적는다).
     - **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는 예정된 것이다.
  2. **구현 커밋** — `feat(012): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다.
  - 테스트가 없는 태스크만 있는 페이즈(기준 기록, 브라우저 확인, 문서)는 한 번 커밋한다.
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다.** 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2).
- 설계 중 spec이 바뀌면(FR·SC) plan의 추적성 표와 이 파일의 참조를 같은 작업 단위에서 고친다(헌법 명세 작성 규약).
- 커밋 전에 비밀 검사 스크립트를 돌린다. `.env`가 추적되지 않는지, 스테이징된 내용에 키·DB 비밀번호가 없는지, `.venv/`·`node_modules/`·`.next/`·`logs/`
  경로가 없는지 본다.
- 개발 서버를 띄운 채 통합 테스트를 돌리지 않는다(같은 MySQL 스키마를 다시 만든다).
- **2026-10-06 T001 기준 응답**: 저장소 밖 작업 폴더(`012-baseline/before/`)에 표 경로 첫 쪽의 머리(`summary`·`condition`·종목 — `rows` 제외)와 `/series`를
  저장했다(`end=2026-09-30` 고정). 주식 KRX 005930.KS·AAPL, 가상자산 BTC, 정기예금 시중은행, 부동산 헬리오시티 30평대, 적립식 주식(국내 매달)·가상자산(매일),
  적금 시중은행 — 8개. 11:44Z
- **2026-10-06 T002 기준 게이트(서버를 내린 채)**: 백엔드 2,663 passed(커버리지 96.25%, 8분 24초), mypy 222 파일·ruff(`--no-cache`) 통과 / 프론트엔드
  155 파일·1,302 passed, tsc·eslint — 모두 종료 코드 0
- **2026-10-06 T005 승인(사용자)**: `PeriodSwitch.test.ts` "전환하면 스크롤을 처음으로 되돌릴 신호를 낸다" → `tableEpoch` 그대로,
  `FxPageLayout.test.tsx` StrictMode 기간 전환 → `scrollIntoView` 불리지 않음(통화 부분·행 잔존 검사 그대로)
- **2026-10-06 T011 승인(사용자)**: 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만들었다 — 백엔드 29건(13개 파일),
  화면 런타임 2건(◇)·tsc 15곳(고정 행 `month_first`·`firstDayMissing`). 바꾸는 이유 다섯(① 첫 쪽의 매수 행 ② 월 행 → 말일 기준·그날 행 ③ ◇ → 결측
  구간 행 ④ 적립식 표의 기간 행 ⑤ 차트-표 날짜 묶음). R12-15 목록 밖 6건도 같은 이유였고 결함이 아니다(research R12-15에 더했다). 고친 줄 위에
  `012 승인 2026-10-06` 주석
- **2026-10-07 T038 승인(사용자)**: 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만들었다 — 백엔드 0건(2,820 passed),
  화면 20개 파일. 모두 research R12-15 US3 목록 안이다. lib 테스트 일곱은 지웠다(식별자·중복·차례·결과 미저장·삭제 → T039·T040, 키·깨진 저장소 → T044,
  저장 실패 알림 → T047, 011 전 형식 → T039·T040). 안내 문구 검사 다섯은 새 문구로, 키에 심고 읽던 열은 이력 대역으로 바꿨다 — `SimulationHistoryBlocked`·
  `StocksPageRerun`은 옛 키(`LEGACY_KEYS.stock`)에 그대로 심어 옮기기를 거치게 했다. 고친 줄 위에 `012 승인 2026-10-07` 주석
- **2026-10-07 T037**: 개발 DB 머리 리비전이 `f4c2a8e19d35`였다(`alembic upgrade head`가 `f4c2a8e19d35 -> a6d2f9c41b83`을 올렸다)
- **2026-10-07 T065 성능**: `period=daily` 첫 쪽·다음 쪽 각 세 번(받아 둔 뒤) — 국내 주식 일시금 20년 0.05~0.09초, 비트코인 일시금(출처 2010-07-18부터,
  약 16년) 0.11~0.15초, 매일 적립 주식 20년 0.10~0.15초. 모두 3초 안(SC-004)
- **2026-10-07 T067 품질 게이트(서버를 내린 채)**: 백엔드 2,820 passed(커버리지 96.34%, 9분 4초), mypy 230 파일·ruff(`--no-cache`) 통과 / 프론트엔드
  163 파일·1,406 passed, tsc·eslint — 모두 종료 코드 0. 이 기능 전 커밋(`b46b606`)과 견주어 바뀌거나 지워진 기존 테스트 48개 파일은 승인 목록(T005·T011·T038)
  안이고, 더하기만 한 둘(`PeriodTabs.test.tsx` — T019, `tests/setup.ts` — T043)뿐이다
- **2026-10-07 T068 불변 대조**: T001의 입력 8개를 다시 받아 16개 파일(표 머리·`/series`)을 견줬다. 14개가 바이트까지 같다. 부동산 헬리오시티 둘만
  `asOf`·시계열 마지막 점 날짜가 10-06 → 10-07이다 — 부동산 경로는 `end`를 받지 않고 오늘(한국 시간)까지 계산한다. 날짜를 맞춰 넣으면 같다(값 변화 없음)

- **2026-10-07 요구사항 리뷰(`checklists/review.md`) 반영** — 사용자 요청("체크하지 않은 항목 모두 수행"). 40개 항목을 spec·plan에 반영했다. 새 FR·SC
  번호 없이 기존 요구에 하위 항목·실패 양상을 더해 아래 추적성 표가 그대로다. 코드 변경 없음 — 정한 요구는 모두 구현된 동작이고, 괄호 안의 테스트가
  이미 고정한다. 체크 표시는 리뷰어가 한다
  - 완전성 CHK001 FR-013 읽을 수 없는 이력(T044·T046) · CHK002 FR-014a 불러오는 중(T046·T048) · CHK003 FR-014 삭제 실패(T047) · CHK004 FR-012 설정
    실패(T041·T049) · CHK005 FR-011 차례(T040) · CHK006 FR-011 길이 한계(T039) · CHK007 FR-003·FR-008~FR-011·FR-014·FR-015 실패 양상
  - 명확성 CHK008 FR-012 경계 — 정확히 30일은 남는다(T041) · CHK009 FR-012 지우는 때 · CHK010 FR-005 그날 마지막 상태 행이 표시를 진다(T017
    `test_같은_날_사건이_여럿이면_…`·T015) · CHK011 FR-004 주식도 같은 금요일 규칙(T012) · CHK012 FR-004b 적립식 포함·찾는 범위(T016·T017) · CHK013 FR-010 →
    ui-wireframes F2·F3
  - 일관성 CHK014 SC-009 = FR-017 범위(T068) · CHK015 헌법 준수 III·Dependencies의 승인 시점 = 구현 때 · CHK016 Key Entities 시각 둘 · CHK017 FR-015
    문구·모를 때(T048) · CHK018 US2 시나리오 5 = Edge Cases
  - 인수 기준 CHK019 SC-001 0px·재는 때(T010·T036) · CHK020·CHK021 SC-004 서버 응답·대상 셋(T065) · CHK022 SC-006·SC-007 "직후" · CHK023 SC-009 같은
    기준일(T068)
  - 시나리오 CHK024·CHK025 Edge Cases(옮긴 뒤 키 삭제 실패, 두 탭) · CHK026 FR-012 확인 단계 없음(F7 결정 그대로) · CHK027·CHK040 Dependencies 이력
    스키마 · CHK028 Assumptions 하향 마이그레이션
  - 경계 CHK029 FR-001·Edge Cases 바닥(T003) · CHK030 FR-016·Edge Cases 빈 원금 · CHK031 FR-009 같은 날 한 쪽(T012 `test_같은_날의_사건_묶음은_…`·T017)
  - 비기능 CHK032 FR-014·FR-014a 알림(T048) · CHK033 Assumptions 로그 제외 · CHK034 FR-012·Assumptions 상한 없음 · CHK035 Assumptions 인증 없음
  - 헌법 CHK036·CHK037 헌법 준수 원칙 VI·FR-011(T039) · CHK038 원칙 V 같은 말(spec 헌법 준수·FR-004·FR-004b·plan) · CHK039 Assumptions 확인(화면에
    `lastRunAt` 없음)
  - **2026-10-07 사용자 확인**: 지금 동작을 그대로 요구로 적은 판단 다섯(CHK001·CHK026·CHK033·CHK034·CHK035·CHK028)을 변경 없이 확정했다(spec
    Clarifications 2026-10-07). 리뷰어(사용자) 확인으로 40개 항목을 충족으로 표시했다

- **2026-10-07 T069(US5)**: 구현을 작업 트리에 둔 채 전체 스위트를 돌렸다 — 백엔드 2,828 passed(새 8건 포함), 프론트엔드 165 파일·1,416 passed. **실제로 실패한
  기존 테스트가 없어** 승인할 목록이 없다(예상과 같다 — 보드 테스트는 칸을 이름으로 찾는다)
- **2026-10-07 US5 문서 바로잡기**: 테스트를 쓰다 확인했다 — 표의 "잔고" 열(`balance`)은 **보유 평가액만**이고 예수금(`cash`)이 따로다. spec·data-model·quickstart·
  research·tasks의 "표 기준일 행의 원화 잔고와 같다"를 "잔고 + 예수금"으로 고쳤고(원화 종목·원화 원금에서 0원 차이 — T070), 보드 칸 안에 무엇을 더한 값인지
  적는 요구를 FR-018·F9에 더했다(표의 잔고 열과 다른 까닭 — 010 반복 4의 "보유 중"과 같은 이유)

## 요구사항 ↔ 태스크

모든 FR·SC가 하나 이상의 태스크에 참조된다(헌법 명세 작성 규약).

| 요구사항 | 태스크 |
|----------|--------|
| FR-001 | T003, T004, T005, T006, T007, T008, T009, T010 |
| FR-002 | T006, T008 |
| FR-003 | T011, T015, T017, T023, T024, T025, T029, T030, T034, T035 |
| FR-004 | T012, T013, T014, T015, T016, T017, T020, T021, T027, T028, T029, T030, T033 |
| FR-004a | T012, T015, T020, T021, T027, T033 |
| FR-004b | T012, T016, T017, T022, T027, T030, T033 |
| FR-005 | T011, T012, T014, T015, T017, T021, T027, T029, T030, T033 |
| FR-006 | T003, T004, T023, T024, T025, T034, T035 |
| FR-007 | T015, T016, T017, T023, T024, T029, T034 |
| FR-008 | T011, T015, T016, T018, T022, T026, T029, T030, T033 |
| FR-009 | T012, T015, T027, T029, T036 |
| FR-010 | T019, T020, T021, T025, T032 |
| FR-011 | T038, T039, T040, T047, T050, T051, T052, T053, T055, T056, T060 |
| FR-012 | T041, T049, T051, T052, T053, T058, T060 |
| FR-013 | T038, T039, T040, T044, T046, T052, T053, T056, T060 |
| FR-014 | T040, T047, T048, T053, T056, T057, T060 |
| FR-014a | T046, T048, T056, T057, T059, T060 |
| FR-015 | T038, T048, T050, T057, T059, T060 |
| FR-016 | T061, T062, T063 |
| FR-017 | T001, T013, T014, T028, T068 |
| SC-001 | T003, T007, T009, T010 |
| SC-002 | T012, T015, T016, T036 |
| SC-003 | T012, T015, T017, T036 |
| SC-004 | T065 |
| SC-005 | T015, T025, T036 |
| SC-006 | T040, T046, T060 |
| SC-007 | T041, T060 |
| SC-008 | T061, T062, T064 |
| SC-009 | T001, T002, T068, T076 |
| FR-018 | T069, T070, T071, T072, T073, T074, T075, T076 |
| SC-010 | T070, T071, T072, T075 |
