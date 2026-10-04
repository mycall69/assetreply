---

description: "Task list for 008-deposit-investment-simulation"
---

# Tasks: 예금 투자 시뮬레이션

**Input**: Design documents from `/specs/008-deposit-investment-simulation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를 지킨다. **테스트를 구현보다
먼저 커밋한다** — 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes). **구현 뒤 테스트가 실패하면 원인이 테스트 쪽으로 보여도 멈추고
실패 목록과 원인 판단을 먼저 보고한다**(이전에 통과하던 테스트가 실패로 바뀐 경우도 같다 — 006 D2).

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수). 린트는 `ruff check --no-cache`(CLAUDE.md)

## 이 기능에서 특히 조심할 것

- **ECOS는 오류도 HTTP 200으로 준다**: `RESULT.CODE`를 본다. `INFO-200`(구간에 값 없음)은 **미발표**이지 오류가 아니고, 받은 구간으로
  기록하지 않는다 — 기록하면 그 달이 영영 빈다(FR-010)
- **인증키가 URL 경로에 있다**: 요청 URL을 로그·원본·실패 사유·사건에 남기지 않는다. 오류 문구는 `mask_secrets`를 거친다. 픽스처에는
  응답 본문만 둔다(FR-014, SC-011)
- **ECOS 고유 이름은 `ingestion/ecos/` 밖에 나오면 안 된다**: `tests/unit/test_layer_boundaries.py`가 `ITEM_CODE`·`DATA_VALUE`·
  `StatisticSearch`·`INFO-200` 등을 어댑터 밖에서 찾는다. 통계표·항목 코드(`121Y004`·`BEBBBI01`)도 어댑터 안에만 둔다(헌법 원칙 II)
- **받은 달은 바꾸지 않는다**: 다시 확인할 때 겹친 달의 값이 다르면 **덮어쓰지 않고** `deposit_rate_revised` 사건만 남긴다(research R8-4)
- **잠정 금리를 저장하지 않는다**: 미발표 달은 계산 안에서만 마지막 발표 달의 금리로 대신 쓴다. 저장하면 발표된 뒤에도 남는다(FR-024)
- **결측은 잠정이 아니다**: 발표된 범위 안의 빈 달은 멈춘다(재예치) 또는 막는다(가입). 미발표와 섞으면 보간이 된다(FR-019)
- **원 미만 버림은 두 곳뿐이다**: 이자 `⌊P × r / 100⌋`, 세금 `⌊이자 × 세율⌋`(경과분도 같은 규칙). 그 밖의 반올림을 넣으면 참조값과 어긋난다.
  수익률은 기존 `quantize_rate`(소수 6자리)를 쓴다(research R8-7)
- **2월 29일**: 다음 해 만기는 2월 28일. 회차 일수 = 실제 일수(365·366). 만기일의 경과 이자 = 만기 이자(FR-022, FR-025)
- **날짜는 한국 시간 달력**이다 — 오늘·확인한 날·계산 끝(FR-018). UTC로 오늘을 정하면 오전 9시 전에 하루가 어긋난다
- **같은 날 202가 되풀이되면 안 된다**: 오늘 확인이 실패했고 받아 둔 금리로 답할 수 있으면 200(잠정 + `recheckFailed`)이다(contracts 오류 절)
- **001 경로를 건드린다**(plan Complexity Tracking): `EcosClient._get`이 `EcosGate`를 지난다. **001~004의 기존 테스트는 고치지 않고 통과해야
  한다** — 고쳐야 한다면 멈추고 보고한다
- **공유 차트를 건드린다**: `PerformanceChart`에 선택 속성 `provisionalFrom`. **005~007의 차트 테스트는 고치지 않고 통과해야 한다**
- **실행 주체에는 그 주체를 거쳐야만 통과하는 테스트를 짝짓는다**(006 D1): `lifespan`의 예금 수집 줄 등록, 시뮬레이션 요청이 수집을 시작하는
  경로, 기동 시 고아 점유 회수
- **테스트는 네트워크 없이**(헌법 원칙 III, 소켓 차단 `conftest.py`). 출처를 부르는 것은 T001의 픽스처 저장 스크립트뿐이다

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 실제 응답 픽스처와 설정 자리

- [X] T001 ECOS의 **실제 응답**을 받아 `backend/tests/contract/fixtures/deposit/`에 저장한다 — `.env`의 `ECOS_API_KEY`를 파일에서 읽고(셸 인자로
  넘기지 않는다), 요청 사이 1초. 받는 것: 항목 목록 `items_121Y002.json`·`items_121Y004.json`, 다섯 투자처의 전체 월 시계열
  `series_commercial_bank.json`(121Y002 `BEABAA2118`)·`series_savings_bank.json`(121Y004 `BEBBBE01`)·`series_credit_union.json`(`BEBBBG01`)·
  `series_mutual_finance.json`(`BEBBBI01`)·`series_saemaul.json`(`BEBBA000`), 미발표 구간(마지막 발표 달 다음 달 ~ 이번 달) `unpublished_info200.json`.
  **응답 본문만** 저장하고 요청 URL은 저장하지 않는다 — 저장 뒤 파일들에 인증키 문자열이 없는지 검사한다. 인증 실패·한도 초과는 001의
  `fixtures/info_100_bad_key.json`·`info_300_rate_limit.json`을 그대로 쓴다. 받은 날짜·요청(키 자리는 `{key}`)·각 시계열의 첫 달·마지막 달을
  `fixtures/deposit/README.md`에 적는다. 스크립트는 저장소에 넣지 않는다(일회성). **약관**은 research R8-2에 확인해 두었다(2026-10-04) — 받기
  전에 Open API 사이트의 이용약관 시행일이 바뀌었는지 보고, 바뀌었으면 개인 이용과 맞지 않는 조항이 있는지 확인한다. 있으면 멈추고 보고한다
  (005·007처럼 이탈 기록이 필요하면 사용자 결정) (FR-008, FR-009, FR-017, research R8-1·R8-2·R8-3)
- [X] T002 [P] `.env.example`에 설정 자리를 더한다 — `ECOS_MAX_CONCURRENT_REQUESTS`(3 — 환율과 예금이 함께 쓰는 ECOS 동시 요청 수),
  `DEPOSIT_RECHECK_OVERLAP_MONTHS`(2 — 다시 확인할 때 마지막 받은 달의 몇 달 전부터 받을지). 값의 의미를 주석으로. 비밀은 없다(인증키는
  기존 `ECOS_API_KEY`) (FR-013, FR-014, research R8-4·R8-6)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 스키마, ECOS 예금 금리 어댑터, 환율과 함께 쓰는 관문. 모든 스토리가 기댄다

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 어떤 스토리도 시작하지 않는다

### Tests for Phase 2 ⚠️

- [X] T003 [P] `backend/tests/contract/test_ecos_deposit_parse.py` — T001 픽스처로: 월 시계열 → `MonthlyRate(month=그 달 1일, rate=Decimal)`,
  `"3.2"`는 `Decimal("3.2")`(끝의 0이 없어도), 쉼표를 지운다, 행은 달 순서, 5개 시계열의 첫 달·마지막 달·행 수가 README와 같다(시중은행
  2012-01·176행, 저축은행·신협·상호금융 1997-08·349행, 새마을금고 2012-01·176행), `INFO-200` → 미발표 결과(빈 행, 오류 아님),
  `INFO-100` → 인증 오류(재시도 안 함), `INFO-300` → 한도 초과(재시도), `ERROR-*` → 형식 오류, JSON이 아님 → 연결 오류, `list_total_count` >
  받은 행 수 → 형식 오류(잘림), `DATA_VALUE`가 숫자가 아닌 행이 하나라도 있으면 **응답 전체가 형식 오류**(일부 행만 돌려주지 않음).
  항목 목록 → 투자처 다섯의 항목 코드를 이름 패턴으로 확정(시중은행 `^정기예금\(1년\)$`, 저축은행 `상호저축은행.*정기예금\(1년\)`, 신협
  `신협.*정기예탁금\(1년\)`, 상호금융 `^정기예탁금\(1년만기\)$`, 새마을금고 `새마을금고.*정기예탁금\(1년\)`), 월 주기(`CYCLE = M`) 행의
  `START_TIME`, 알려진 코드가 바뀌어도 이름으로 다시 찾음, 못 찾으면 형식 오류 (FR-008, FR-016, FR-017, research R8-1·R8-3·R8-5)
- [X] T004 [P] `backend/tests/contract/test_ecos_deposit_client.py` — 가짜 세션으로: 항목 목록 URL(`StatisticItemList/{키}/json/kr/1/10000/{통계표}/`)과
  시계열 URL(`StatisticSearch/…/{통계표}/M/{YYYYMM}/{YYYYMM}/{항목}`)의 모양, 돌려주는 원본에 **URL이 없다**, 연결 오류·한도 초과의 오류 문구에
  인증키가 없다(가짜 키 `TESTKEY1234567890abcd`로 확인 — `mask_secrets`), 한도 초과는 백오프+지터로 설정 횟수만큼 재시도, 인증 오류는 재시도하지
  않음, 넘겨받은 세션을 닫지 않음 (FR-014, FR-016, research R8-5)
- [X] T005 [P] `backend/tests/contract/test_ecos_gate.py` — `EcosGate`: 001 `EcosClient`와 예금 클라이언트가 **같은 관문**을 지나 동시 요청이
  `ECOS_MAX_CONCURRENT_REQUESTS`를 넘지 않음(가짜 세션의 동시 수 측정), 한쪽이 `INFO-300`을 받으면 다른 쪽의 다음 요청도 백오프 동안 기다림
  (주입한 시계), 한도 신호가 없으면 서로 기다리지 않음. `EcosClient`의 기존 동작(재시도·잘림·항목 매핑)은 001 테스트 그대로 (FR-013, SC-012,
  research R8-6)
- [X] T006 [P] `backend/tests/integration/test_deposit_schema.py` — 마이그레이션 뒤 테이블 6개와 열(data-model): `deposit_rate`의 기본 키
  `(institution, month)`·`rate DECIMAL(7,4)`·`source`·`ingested_at`, `deposit_raw_response`에 URL 열이 없음·`body` LONGTEXT
  (utf8mb4 — 구현 뒤 D2 승인으로 기대값 수정),
  `deposit_raw_response`의 `institution`은 NULL 허용(**항목 목록이면 NULL**)·`source_ref VARCHAR(32) NOT NULL`,
  `deposit_coverage`의 `first_month`·`latest_month`·`checked_on`(모두 DATE NOT NULL), 작업·점유(기본 키 `institution`, 작업의
  **`range_start`·`range_end`는 NOT NULL**),
  `deposit_setting.interest_tax_rate DECIMAL(9,6)`(행 없음 = 기본), 마이그레이션 하향·재상향 (FR-009, FR-029, FR-030, data-model)

### Implementation for Phase 2

- [X] T007 `backend/src/config/settings.py` — `ecos_max_concurrent_requests`(기본 3, 최소 1), `deposit_recheck_overlap_months`(기본 2, 최소 0),
  `load_settings`에 연결 (FR-013, research R8-4·R8-6)
- [X] T008 `backend/src/db/models.py`·`backend/src/db/migrations/versions/…_예금_스키마.py` — Deposit* 6개(data-model 1~5절). 형식 이름 `RATE_PCT`
  (`DECIMAL(7,4)`), 세율은 기존 `SPREAD`. 이전 head `b7e3c9d14a26` (FR-009, FR-029, FR-030)
- [X] T009 `backend/src/ingestion/protocols.py`(`MonthlyRate`, `DepositRateSource` Protocol, 결과·원본 타입)·`backend/src/ingestion/ecos/deposit_items.py`
  (투자처 키 → 통계표·항목 코드·이름 패턴, `resolve_deposit_items`)·`backend/src/ingestion/ecos/deposit_parse.py`(`parse_monthly`, `INFO-200` = 미발표,
  잘림·숫자 검사) — 오류는 기존 `ingestion/ecos/errors.py`의 계층을 쓴다 (FR-008, FR-016, FR-017)
- [X] T010 `backend/src/ingestion/ecos/gate.py`(`EcosGate` — 프로세스 하나, 동시 수 + `INFO-300` 공유 백오프)·`backend/src/ingestion/ecos/client.py`
  (`_get`이 관문을 지난다 — **나머지 동작 불변**)·`backend/src/ingestion/ecos/deposit_client.py`(`EcosDepositClient(settings, *, session=None)`:
  `fetch_items(table)`, `fetch_series(institution, from_month, to_month)` → (행 또는 미발표, 원본 본문), 같은 관문). 오류 문구는 `mask_secrets`
  (FR-013, FR-014, research R8-5·R8-6)

**Checkpoint**: 스키마·어댑터·관문 준비. 백엔드 전체 테스트(001~007 포함)가 고치지 않고 통과한다

---

## Phase 3: User Story 1 - 예금에 넣었다면 지금 얼마인지 본다 (Priority: P1) 🎯 MVP

**Goal**: 투자처를 라디오로 고르고 시작일·원금으로 실행하면, 필요한 금리를 받은 뒤(수집 진행) 1년 정기예금 가입·만기·재예치 결과를 보드와
표로 본다. 미발표 달은 잠정, 결측은 멈춤

**Independent Test**: 시중은행·2020-01-15·10,000,000원으로 실행해 표가 research R8-7 참조값 1과 원 단위까지 같은지(quickstart 4·5)

### Tests for User Story 1 ⚠️

- [X] T011 [P] [US1] `backend/tests/unit/test_deposit_rollover.py` — 순수 함수(DB·HTTP 없음): **참조값 1**(research R8-7 표 — 회차 1~6의 금리·원금·
  이자·세금·세후·재예치 원금, 진행 중 회차 7의 경과 262/365일 → 경과 이자 231,607·세금 35,667, 잔고 11,557,207, 투자 수익 1,557,207, 수익률
  0.155721 — 곱·나눗셈·버림 위치를 주석으로), **참조값 2**(2024-02-29 가입 → 만기 2025-02-28, 회차 일수 365, 이자 363,000), **참조값 3**(시작
  달 미발표 → 마지막 발표 달 금리로 잠정 가입, 회차·행 모두 `provisional`, `rateMonth` = 대신 쓴 달, `provisionalFrom` = 가입일), 확정 회차 뒤
  재예치 달이 미발표면 그 회차부터 잠정이고 앞 회차는 확정, 잠정 회차의 만기가 또 지나도 잠정, **참조값 4**(세율 0 → 세금 0, 세후 = 이자),
  **참조값 5**(원금 1원 → 이자 0, 재예치 원금 = 원금), **참조값 6**(금리 −0.5%·원금 10,000,000 → 이자 −50,000(0 쪽 절사)·세금 0·재예치 원금
  9,950,000, 원금 1,000원·금리 −0.004% → 이자 0이고 −0이 아님), 만기일의 경과 이자 = 만기 이자, 행: 가입·매달 1일·만기·재예치(같은 날 재예치가 만기보다
  앞, 최신순), 가입일·만기일이 1일이면 그날 월 행 없음, 재예치 행 원금 = 만기 행 원금 + 세후 이자(SC-004), **결측**: 재예치 달이 결측이면 그
  만기일에서 멈춤(`stopped`·`isFinal: false`·`asOf` = 만기일, 뒤 행 없음), 가입 달이 결측이면 `rate_missing` 오류, 같은 입력 두 번 같은 결과,
  계산 끝 = 주입한 오늘(한국 시간) (FR-007, FR-018, FR-019, FR-021~FR-029, SC-003, SC-004, SC-005, SC-006)
- [X] T012 [P] [US1] `backend/tests/integration/test_deposit_collection.py` — 가짜 출처(T001 픽스처)로 실행기: 처음 받으면 항목 확인 → 전체 시계열 →
  금리 upsert·원본(본문만 — 항목 목록은 **통계표 하나에 한 행**·`institution` NULL·`source_ref`, 시계열은 투자처 행)·커버리지(`first_month`·
  `latest_month`·`checked_on` = 한국 시간 오늘), **작업 구간 = 그 실행에 필요한 구간**(시작 달 ~ 이번 달 — 처음 받을 때도), 다시 확인은 마지막 받은 달의
  2개월 전부터 요청(설정), 미발표(`INFO-200`)면 `latest_month` 그대로·`checked_on` 갱신, **겹친 달의 값이 다르면 바꾸지 않고**
  `deposit_rate_revised` 사건(투자처·달·이전 값·새 값), 실패 종류(`auth`·`rate_limited`·`format`·`network`)가 작업 `last_error`에 남고 **실패하면
  `checked_on`을 갱신하지 않음**, 실패 사유·사건·원본에 인증키 문자열 0건, 같은 투자처 점유 중이면 두 번째 작업 없음, 수집 전용 로그에 시작·
  완료·실패 사건(투자처·구간·종류) (FR-009, FR-010, FR-012, FR-014~FR-016, FR-020, SC-011)
- [X] T013 [P] [US1] `backend/tests/integration/test_deposit_simulation_api.py` — `GET /api/deposit/simulation`: 받은 적 없음 → 202(**`missingFrom`·
  `missingThrough` = 시작 달 ~ 이번 달**, 늘 있다)와 수집 요청, 커버리지 밖의 달이 있고 오늘 확인 전 → 202, **오늘 확인했는데 없는 달 → 200 잠정**(`provisionalFrom`), **오늘 확인 작업이 실패했고
  받아 둔 금리로 답할 수 있음 → 200 + `recheckFailed`(같은 날 202 되풀이 없음)**, 참조값 1의 `summary`·`terms`·`rows`(최신순, `kind`, 원 단위
  정수 문자열, 금리 문자열 그대로), `before_first_month`(`startableFrom`), `rate_missing`(가입 달 결측 픽스처 — 한 달을 뺀 시계열), 재예치 달 결측
  → 200 `stopped`, `unknown_institution`, `principalCurrency=USD` → `currency_not_allowed`, 시작일 > 오늘(한국 시간) → `start_after_end`, 원금
  정수 아님 → `invalid_query`, 수집을 마쳤는데 금리 0행 → `no_rate_data`, 세율은 `deposit_setting` 기본 0.154 (FR-002~FR-007, FR-010,
  FR-016, FR-019, FR-024, FR-026, FR-035, SC-005, SC-006)
- [X] T014 [P] [US1] `backend/tests/integration/test_deposit_progress_sse.py`·`test_deposit_institutions_api.py` — 진행 스트림: `snapshot`(투자처, **받을 달 =
  필요한 구간의 달 수 — 처음 받을 때도 0보다 큼**, 받은 달 = 그중 받은 구간 안의 달, 미발표 달이 있으면 완료 때 받은 달 < 받을 달)·`completed`
  (`latestMonth`)·`failed`(`kind`, 인증키 없는 `reason`), 머리글 `no-transform`, 프레임마다 새 스냅샷(006 T113과 같은 검사). 투자처 목록: 순서
  5개·이름·설명·출처, 받기 전 `firstMonth: null`, 받은 뒤 첫 달·마지막 달·확인한 날 (FR-003, FR-006, FR-011, FR-016)
- [X] T015 [P] [US1] `backend/tests/integration/test_deposit_worker.py` — **실행 주체**: 앱 기동이 예금 수집 줄을 띄운다(태스크 7개), 시뮬레이션
  요청(202)이 큐를 거쳐 워커가 수집을 끝낸다(내부 함수를 직접 부르지 않는다), **기동 시 남은 예금 점유를 회수**하고 그 작업을 `network`로 마감,
  환율 수집이 진행 중이어도 예금 수집이 기다리지 않고(반대도) 함께 끝나며 두 줄의 ECOS 요청이 관문의 동시 수를 넘지 않음 (FR-011~FR-013,
  SC-012)
- [X] T016 [P] [US1] `frontend/tests/` — `DepositPage.test.tsx`(`/deposit` 화면, 라디오 다섯·기본 시중은행·설명 줄, 통화 칸·재투자 칸 없음, 원금
  단위 "원", 출처 줄), `InstitutionPicker.test.tsx`(`fieldset`·`legend`, 방향키 선택, 바꾸면 결과를 지움 — D2), `DepositPerformanceTable.test.tsx`
  (열 10개·머리글 통화, 구분 글자 가입·월·만기·재예치, 잠정이면 "·잠정"과 "(26-08 대신)", 경과분 도움말, 금리 `"3.2"` → `3.20%`, 최신순, 표 `w-max`),
  `DepositNotice.test.tsx`(잠정 줄 — 잠정 시작일·대신 쓴 달과 값·"발표되면 값이 바뀝니다", 멈춤 줄, 확인 실패 줄, `role="status"`),
  `depositStore.test.ts`(202 → 진행 구독 → 완료 뒤 다시 요청, 실패 종류별 문구 D8, `409 before_first_month` → 옮기기 수단), 보드 `notes`에
  투자처·세율·지금 회차. **기존 `Sidebar.test.tsx`의 기대를 바꾼다**: 준비중 목록에서 예금 제거, 예금 항목이 `/deposit` 링크 — 테스트 커밋에서
  바꾸고 사유를 적는다. `noUnbuiltAssetRoutes.test.ts`에서 `deposit`을 뺀다 (FR-001~FR-007, FR-016, FR-032~FR-035, SC-005)

### Implementation for User Story 1

- [X] T017 [US1] `backend/src/simulation/deposit_rollover.py` — `simulate_deposit(principal, start, end, rates, latest_month, tax_rate)` → 회차·행·요약
  (잠정·멈춤 포함). `Decimal` 정밀도 60, 버림 두 곳, 수익률 `money.quantize_rate` (FR-019, FR-021~FR-029, research R8-7·R8-8)
- [X] T018 [US1] `backend/src/repository/deposit_rate.py`(금리 upsert — 있으면 바꾸지 않고 다른 값 목록을 돌려줌, 조회, 커버리지·`checked_on`,
  원본)·`deposit_job.py`(작업·점유·고아 회수 — 007 `crypto_job`과 같은 수단)·`deposit_setting.py`(읽기·쓰기, 기본 0.154) (FR-009, FR-010, FR-012,
  FR-030, data-model 1~5절)
- [X] T019 [US1] `backend/src/worker/deposit_queue.py`·`deposit_runner.py`·`deposit_worker.py`·`backend/src/api/main.py`(`lifespan` 태스크 등록,
  기동 시 회수) — 항목 확인(처음), 시계열 요청(처음은 `START_TIME`부터, 다시는 겹침 2개월), 원본·금리·커버리지, 겹침 비교 사건, 실패 종류,
  수집 사건(FR-009~FR-016, FR-020)
- [X] T020 [US1] `backend/src/api/services/deposit_collect.py`(202 판정 — 받지 않은 달, 오늘 확인 여부, 오늘 실패 작업)·`deposit_simulation.py`(입력 검증,
  시작 가능 날짜, 계산 끝 오늘 한국 시간, 응답)·`backend/src/api/routes/deposit_simulation.py`·`deposit_institutions.py`·`deposit_progress.py`·
  `backend/src/api/main.py`(라우터) — contracts/rest-api (FR-002~FR-007, FR-010, FR-011, FR-016, FR-026, FR-035)
- [X] T021 [US1] `frontend/src/lib/types.ts`(예금 응답)·`frontend/src/lib/depositProgressStream.ts`·`frontend/src/stores/depositStore.ts`·
  `frontend/src/components/deposit/InstitutionPicker.tsx`·`DepositSimulationForm.tsx`·`DepositPerformanceTable.tsx`·`DepositNotice.tsx`·
  `frontend/src/app/deposit/page.tsx`·`frontend/src/components/shell/Sidebar.tsx`(`/deposit`) — D1~D4·D8. 보드는 `PerformanceBoard` 그대로(`notes`),
  수집 안내는 `CollectingNotice`(대상 이름·단위 "개월") (FR-001~FR-007, FR-032~FR-035)
- [X] T022 [US1] 브라우저(3030, 창 1440px) 확인 — quickstart 1~12를 실행하고 기록한다. 1(ECOS 화면의 상호금융 항목 계층), 4(202 → 결과, 진행
  2초 안), 5(참조값 1과 원 단위 일치 — 실행한 날 기준으로 진행 중 회차의 경과 일수가 다르면 그날 값으로 손계산), 6(같은 날 다시 실행 3초 안,
  출처 호출 없음), 7·8(잠정 — 그날의 마지막 발표 달을 적는다), 9(시작 가능 날짜), 10·11(다섯 투자처 × 시작 가능 날짜·중간 해 1월 15일·최근 발표
  달 15일 = 15회, 첫 달 전날 409), 12(2월 29일) (FR-001~FR-008,
  FR-021~FR-027, SC-001, SC-002, SC-007, SC-010)

**Checkpoint**: 예금 화면에서 투자처를 골라 결과를 볼 수 있다(MVP)

---

## Phase 4: User Story 2 - 이자 소득세율을 정한다 (Priority: P2)

**Goal**: 설정의 예금 이자 소득세율(기본 15.4%)을 바꾸면 결과가 새 세율로 다시 나오고 적용 세율이 보인다

**Independent Test**: 세율 0%로 바꾸면 이자 소득세 열이 0, 15.4%로 되돌리면 처음 결과(quickstart 13)

### Tests for User Story 2 ⚠️

- [X] T023 [P] [US2] `backend/tests/integration/test_deposit_settings_api.py` — `GET` 기본 `{"interestTaxRate": "0.154000", "isDefault": true}`,
  `PUT "0.095"` 뒤 시뮬레이션이 그 세율로 계산(`condition.interestTaxRate`), 0 미만·1 이상·숫자 아님 → `422 invalid_setting`, 주식·가상자산 설정
  불변 (FR-030, FR-031, SC-008)
- [X] T024 [P] [US2] `frontend/tests/DepositSettingsForm.test.tsx`·`depositStoreSettings.test.ts` — 15.4 % 표시·저장·범위 밖 거절·기본값으로, 설정
  화면에 주식·가상자산·예금 칸이 따로, 설정을 바꾸고 예금 화면에 돌아오면 다시 요청(007 `refreshIfRan`과 같다) (FR-030, FR-031, SC-008)

### Implementation for User Story 2

- [X] T025 [US2] `backend/src/api/routes/deposit_settings.py`·`backend/src/api/main.py`(라우터) — `GET`·`PUT /api/deposit/settings` (FR-030, FR-031)
- [X] T026 [US2] `frontend/src/components/settings/DepositSettingsForm.tsx`·`frontend/src/app/settings/page.tsx`·`frontend/src/stores/depositStore.ts`
  (설정 변경 뒤 다시 요청) — D7 (FR-030, FR-031)

**Checkpoint**: 세율을 바꾸면 예금 결과가 새 세율로 다시 나온다

---

## Phase 5: User Story 3 - 성과의 흐름을 차트로 본다 (Priority: P2)

**Goal**: 잔고·수익률을 두 축으로 그리고, 잠정 구간을 구별한다

**Independent Test**: 표의 행 날짜의 점 = 그 행, 끝점 = 보드, 잠정 구간이 연한 색과 범례 "잠정"(quickstart 7·15)

### Tests for User Story 3 ⚠️

- [ ] T027 [P] [US3] `backend/tests/integration/test_deposit_series_api.py` — `GET /api/deposit/simulation/series`: 점 = 표의 행 날짜(같은 날 만기·재예치는
  하나) + 계산 끝, **표의 행과 같은 날짜의 점은 그 행의 `balance`·`returnRate`와 같고 끝점은 `summary`와 같다**, `gaps: []`, 잠정이면
  `provisionalFrom`, 결측으로 멈추면 그 만기일에서 끝, 202·오류는 표와 같다 (FR-036, SC-005, SC-009)
- [ ] T028 [P] [US3] `frontend/tests/PerformanceChartProvisional.test.tsx` — `provisionalFrom`이 있으면 그 날짜부터의 점을 연한 색 시리즈로(잔고·수익률
  둘 다, 같은 축·같은 축 형식 — 007 FR-043a), 경계 점을 양쪽에 넣어 선이 이어짐, 범례 "잠정(날짜부터)", `null`·없으면 지금과 같은 시리즈(005~007
  `PerformanceChart*.test.tsx`는 그대로 통과) (FR-036, SC-005)

### Implementation for User Story 3

- [ ] T029 [US3] `backend/src/api/services/deposit_series.py`·`backend/src/api/routes/deposit_series.py`·`backend/src/api/main.py`(라우터) — 시뮬레이션과 같은
  계산의 행 날짜 + 계산 끝, `provisionalFrom` (FR-036)
- [ ] T030 [US3] `frontend/src/components/stock/PerformanceChart.tsx`(선택 속성 `provisionalFrom`)·`frontend/src/lib/types.ts`(`SimulationSeriesResponse.provisionalFrom?`)·
  `frontend/src/stores/depositStore.ts`(시계열)·`frontend/src/app/deposit/page.tsx`(차트 연결) — D5 (FR-036)

**Checkpoint**: 차트가 표·보드와 같은 값으로 그려지고 잠정 구간이 구별된다

---

## Phase 6: User Story 4 - 실행 이력을 남기고 비교한다 (Priority: P3)

**Goal**: 실행 조건이 이력으로 남고, 다시 실행하거나 여러 이력을 골라 수익률을 비교한다

**Independent Test**: 시중은행·저축은행을 같은 조건으로 실행한 뒤 이력에서 골라 비교 차트(quickstart 14)

### Tests for User Story 4 ⚠️

- [ ] T031 [P] [US4] `frontend/tests/depositHistory.test.ts`·`DepositHistory.test.tsx`·`depositStoreCompare.test.ts` — 저장 키가 주식·가상자산과 다름
  (`assetreplay.depositHistory.v1`), 조건만(투자처·시작일·원금 — 결과 수치 없음), 같은 조건은 맨 앞으로, 다시 실행 = 조건을 넣고 곧바로 실행,
  삭제, 둘 이상 골라 비교 → `ComparisonChart`, 범례에 투자처·시작일, 잠정 항목은 "(잠정)", 빠지는 항목은 "…의 시계열을 불러오지 못했습니다"와
  사유(받지 않은 구간 — "실행해서 받으세요", 모르는 투자처) (FR-037, FR-038, SC-005)

### Implementation for User Story 4

- [ ] T032 [US4] `frontend/src/lib/depositHistory.ts`·`frontend/src/components/deposit/DepositHistory.tsx`·`frontend/src/stores/depositStore.ts`(이력·
  비교)·`frontend/src/app/deposit/page.tsx` — D6. 비교는 `ComparisonChart` 그대로(`label`에 잠정 표시) (FR-037, FR-038)
- [ ] T033 [US4] 브라우저 확인 — quickstart 13~16(세율 0%·되돌리기, 이력 비교, 차트와 표·보드, 1440px 표)을 실행하고 기록한다 (FR-030~FR-038,
  SC-008, SC-009, SC-010)

**Checkpoint**: 이력·비교까지 동작한다

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T034 [P] `README.md`·`CLAUDE.md` — 현재 상태 표에 008(예금: ECOS 예금은행·비은행 가중평균 금리, 1년 정기예금 재예치, 이자 소득세 설정,
  미발표 달 잠정), 남은 자산군 부동산, `lifespan` 태스크 7개, **ECOS 관문을 환율과 예금이 함께 쓴다**, 시중은행은 2012-01부터(정확히 1년인 항목),
  **ECOS 인증키는 발급일부터 2년 유효(약관 제4조 ③) — 만료되면 환율·예금 수집이 함께 `auth`로 실패하므로 연장한다**, 화면·문서의 출처 표시(약관
  제7조 ②) (FR-039, research R8-2)
- [ ] T035 품질 게이트 — 백엔드 전체 테스트·커버리지 80% 이상·mypy strict·`ruff check --no-cache`, 프론트엔드 테스트·tsc·eslint. **001~007의 기존
  테스트가 고치지 않고 통과하는지** 따로 확인한다 (SC-013)
- [ ] T036 quickstart 전체(1~20)를 실제 브라우저로 한 번 더 돌려 실행 기록을 채운다 — 17(틀린 인증키 → `auth`, 같은 날 202 되풀이 없음, 확인 실패
  줄), 18(환율 백필과 예금 수집 동시 — 출처 동시 요청이 설정 수를 넘지 않음, 한도 초과 신호가 오면 두 수집이 함께 백오프. 신호가 오지 않았으면 그
  사실을 적고 T005·T015로 갈음한다), 19(수집 로그·원본·작업 기록에 인증키 흔적 0건), 20(다음 날 다시 확인 — 그날
  실행할 수 없으면 사유를 적고 통합 테스트 T012로 갈음한다). 결측은 실데이터에 없으므로 T011·T013의 픽스처로 확인했다고 적는다 (SC-001~SC-012)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작. T001은 출처를 부르는 유일한 단계다
- **Foundational (Phase 2)**: Setup 뒤. 모든 스토리를 막는다. T010은 001~004 테스트 전체가 통과해야 끝난다
- **US1 (Phase 3)**: Foundational 뒤. MVP
- **US2 (Phase 4)**, **US3 (Phase 5)**: US1 뒤. 서로 독립 — 같은 파일(`depositStore.ts`·`page.tsx`·`main.py`)을 만지면 순서대로
- **US4 (Phase 6)**: US1 뒤(US3의 시계열을 비교에 쓴다 — US3 뒤가 자연스럽다)
- **Polish (Phase 7)**: 모든 스토리 뒤

### Within Each Phase

- 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 모델 → 저장소 → 계산 → 실행기 → 서비스 → 라우트 → 화면

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T019, T020, T025, T029 |
| `backend/src/ingestion/ecos/client.py` | T010 |
| `frontend/src/lib/types.ts` | T021, T030 |
| `frontend/src/stores/depositStore.ts` | T021, T026, T030, T032 |
| `frontend/src/app/deposit/page.tsx` | T021, T030, T032 |
| `frontend/src/components/stock/PerformanceChart.tsx` | T030 |
| `frontend/tests/Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts` | T016 |

### Parallel Opportunities

- Phase 2 테스트 T003~T006은 모두 다른 파일 — 함께 쓴다
- 각 스토리의 테스트 태스크([P])는 함께 쓴다
- US2와 US3은 US1 뒤에 나란히 진행할 수 있다(위 같은 파일 표 주의)

---

## Parallel Example: Phase 3 (US1 테스트)

```text
Task: "T011 test_deposit_rollover.py — 참조값 다섯, 잠정, 결측"
Task: "T012 test_deposit_collection.py — 커버리지·확인한 날·겹침 사건"
Task: "T013 test_deposit_simulation_api.py — 202·잠정·recheckFailed·오류"
Task: "T014 test_deposit_progress_sse.py + test_deposit_institutions_api.py"
Task: "T015 test_deposit_worker.py — lifespan·회수·환율과 동시"
Task: "T016 frontend 예금 화면·표·안내·스토어"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 → Phase 2 (001~007 테스트 회귀 확인)
2. Phase 3 (US1)
3. **멈추고 검증**: T022 브라우저 확인 — 투자처 → 실행 → 수집 진행 → 보드·표, 참조값과 원 단위 일치

### Incremental Delivery

1. MVP(US1) — 투자처 다섯, 가입·만기·재예치, 잠정·결측
2. US2 — 세율 설정
3. US3 — 차트(잠정 구간)
4. US4 — 이력·비교
5. Polish — 기록 갱신, 게이트, quickstart 전체

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(008): <페이즈>`. 그 페이즈의 테스트만 담고 **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는
     예정된 것이다. 기존 테스트의 기대를 바꿔야 하면(사이드바 등) 이 커밋에서 바꾸고 사유를 적는다 — 단, 001~007의 다른 테스트를 바꿔야 한다면
     먼저 보고한다(T010, T030)
  2. **구현 커밋** — `feat(008): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다
  - 테스트가 없는 태스크만 있는 페이즈(Setup의 픽스처·설정, 브라우저 확인, 문서)는 한 번 커밋한다
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다** — 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2)
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
- 픽스처를 새로 받아야 하면(형식 변경 등) T001과 같은 방식으로 받고 받은 날짜를 `fixtures/deposit/README.md`에 적는다. 인증키가 들어가지 않았는지
  저장할 때마다 검사한다
