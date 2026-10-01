---

description: "Task list template for feature implementation"
---

# Tasks: 주식 투자 시뮬레이션

**Input**: Design documents from `/specs/005-stock-investment-simulation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: **필수.** 헌법 v5.2.0 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
테스트 작성 → 실패 확인 → 구현. 구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 의존 없음)
- **[Story]**: 소속 사용자 스토리 (US1~US5)
- 파일 경로를 반드시 포함한다
- **ID는 안정적 참조다.** 반복(iteration)으로 추가된 태스크는 번호를 이어 붙이므로 ID
  순서가 실행 순서와 일치하지 않을 수 있다. 실행 순서는 페이즈가 정한다
- 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수)

## 이 기능에서 특히 조심할 것

- **`float` 이식**: 참조 구현이 JS `number`로 모든 금액을 계산한다. 옮기는 과정 전체가
  헌법 원칙 VI 위반 구간이며, float로 계산해도 오류가 나지 않고 숫자도 그럴듯하다
- **수정주가와 원주가**: 섞으면 배당이 이중 계산되는데 차트가 매끄러워 알아챌 신호가 없다
- **예수금**: 정수 매수라 거의 항상 남는다. 총자산에서 빼먹으면 모든 행에서 조금씩 틀린다
- **두 종류의 환율**: 초기 환전은 현금 살 때+우대, 평가 환산은 매매기준율. 섞으면 잔고가
  매수 스프레드만큼 크게 나온다

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 스키마와 공통 타입. 이 기능은 신규 테이블 9개로 시작한다.

- [X] T001 `backend/src/db/models.py`에 테이블 9개를 정의한다 — `stock`, `stock_price`, `stock_dividend`, `stock_split`, `stock_raw_response`, `stock_coverage`, `stock_collection_job`, `stock_collection_lock`, `stock_setting`. 금액·비율은 전부 `DECIMAL`이며 `FLOAT`/`DOUBLE`은 곧바로 원칙 VI 위반이다 (data-model 1절)
- [X] T002 `backend/src/db/migrations/`에 리비전 하나를 만든다. `stock_raw_response.body`는 **처음부터 `MEDIUMTEXT`**다 — 001이 `TEXT`(65,535바이트)를 넘겨 마이그레이션을 한 번 더 했던 자리다 (data-model 1절)
- [X] T003 [P] `backend/src/config/settings.py`에 시세 출처 설정을 더한다 — 기본 URL, **보수적인 호출 간격**, 동시 호출 수, 재시도 정책. 코드가 아닌 설정으로 선언한다 (헌법 원칙 II). 공격적 폴링이 차단의 주된 원인이다 (research R5-1)
- [X] T004 [P] `frontend/src/lib/types.ts`에 `StockSearchResult`·`SimulationRow`·`SimulationSummary`·`SimulationCondition`·`ExchangeInfo` 타입을 더한다 (contracts/rest-api)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 출처 어댑터, 저장, 수집, 정밀도. 모든 스토리가 여기에 의존한다.

**⚠️ CRITICAL**: 이 단계가 끝나기 전에는 어떤 사용자 스토리도 시작할 수 없다

### 정밀도 (원칙 VI의 뿌리)

- [X] T005 [P] `backend/tests/unit/test_money.py`를 작성한다 — 통화별 자릿수(KRW·JPY 0, USD·EUR 2), 수량 버림, 수익률 6자리를 검증한다. **원화·엔화에 소수점 금액은 존재하지 않는다** (data-model 4절)
- [X] T006 `backend/src/simulation/money.py`에 정밀도 규칙을 **한 곳으로** 모은다 — 통화별 자릿수 표, 수량 버림, 반올림 헬퍼. 흩뿌리면 한 군데만 틀려도 **그 통화만 조용히 어긋난다** (data-model 4절, 헌법 원칙 VI)

### 출처 어댑터 (원칙 II)

- [X] T007 [P] `backend/tests/contract/fixtures/`에 시세 응답 픽스처를 저장한다 — 일봉·배당·분할이 있는 종목, 분할만 있는 종목, 빈 응답, 오류 응답. **테스트가 실제 API를 호출하면 원칙 III 위반이다**
- [X] T008 [P] `backend/tests/contract/test_stock_source_parse.py`를 작성한다 — 픽스처에서 일봉·배당·분할이 정규화되는지, **원시 시가·종가와 수정종가가 구분되는지** 검증한다 (FR-011, FR-012)
- [X] T009 [P] `backend/tests/contract/test_stock_source_errors.py`를 작성한다 — 호출 한도·인증 실패·빈 결과가 각각 다른 오류로 구별되는지 검증한다. **"결과 없음"과 "출처가 죽음"을 같게 다루면** 사용자는 그 종목이 존재하지 않는다고 읽는다 (contracts/rest-api 오류표)
- [X] T010 `backend/src/ingestion/yahoo/parse.py`에 정규화를 만든다. **출처 고유 필드명이 이 디렉터리 밖으로 나가지 않는다** (헌법 원칙 II)
- [X] T011 `backend/src/ingestion/yahoo/errors.py`에 출처 오류 타입을 만든다 — 001의 `ingestion/ecos/errors.py`와 같은 모양
- [X] T012 `backend/src/ingestion/yahoo/client.py`에 비동기 호출을 만든다 — `aiohttp`, 세마포어로 동시 호출 제한, 지수 백오프 + 지터. **동기 호출은 원칙 I 위반이다** (헌법 원칙 I·II)
- [X] T013 [P] `backend/tests/unit/test_layer_boundaries.py`에 검사를 더한다 — 출처 고유 필드명(`adjclose`·`gmtoffset`·`chartPreviousClose` 등)이 `ingestion/yahoo/` 밖에 없는지 (헌법 원칙 II)

### 저장

- [X] T014 [P] `backend/tests/integration/test_stock_upsert.py`를 작성한다 — 같은 `(stock_id, quote_date)`를 두 번 저장해도 한 행이고 `ingested_at`이 보존되는지 검증한다 (헌법 시계열 불변식)
- [X] T015 `backend/src/repository/stock.py`에 종목·커버리지 조회·저장을 만든다. upsert는 `db/dialect.py`의 헬퍼만 호출한다 — 방언 구문을 직접 쓰면 헌법 위반이다
- [X] T016 `backend/src/repository/stock_price.py`에 시세·배당·분할 조회·저장을 만든다. 구간 조회는 001의 `series`와 같은 모양이다. **분할 이벤트는 제공처가 준 그대로 저장하고 다시 읽을 수 있어야 한다** — 제공처를 믿기로 한 이상(FR-010a) 틀렸을 때 되짚을 수단이 이 기록뿐이다 (FR-010b, SC-017)
- [X] T017 [P] `backend/tests/integration/test_stock_coverage.py`를 작성한다 — 커버리지 기록과 **빠진 구간 계산**이 맞는지 검증한다 (FR-044)

### 수집 (003 구조 계승)

- [X] T018 [P] `backend/tests/integration/test_stock_collection.py`를 작성한다 — 요청 구간만 받는지(FR-043), 같은 구간을 다시 받지 않는지(FR-044, SC-022), 중단 후 **중단 지점부터** 이어받는지(FR-045, SC-023) 검증한다. 스텁 소스를 쓰며 네트워크 없이 통과해야 한다
- [X] T019 `backend/src/worker/stock_runner.py`에 수집 워커를 만든다. 003의 `worker/runner.py` 구조를 잇되 **점유는 FX와 분리한다** — 출처가 다르므로 호출 한도도 따로다 (research R5-7)
- [X] T020 [P] `backend/tests/integration/test_stock_lock.py`를 작성한다 — 같은 종목의 수집이 진행 중이면 새 작업을 만들지 않고 그 작업 ID를 주는지 검증한다 (FR-048, SC-028)
- [X] T021 `backend/src/repository/stock_job.py`에 작업·점유를 만든다. 003의 `repository/job.py`·`collection_lock.py`와 같은 모양
- [X] T022 `backend/src/api/routes/stock_progress.py`에 진행 상태 SSE를 만든다. **`error`에서 `close()`하지 않는다** — `EventSource`의 자동 재연결에 의존한다 (003이 001에서 얻은 교훈)
- [X] T023 보관한 시세에 **출처와 받은 시각**이 남는지 확인하는 검증을 `backend/tests/integration/test_stock_upsert.py`에 더한다 (FR-046, 헌법 시계열 불변식)

**Checkpoint**: 시세를 받아 저장하고 재개할 수 있다 — 사용자 스토리 착수 가능

---

## Phase 3: User Story 1 - 한 종목에 투자했다면 지금 얼마인지 본다 (Priority: P1) 🎯 MVP

**Goal**: 종목을 검색해 고르고, 시작일·원금을 넣으면 표와 보드가 나온다. 배당 없이도
성립한다.

**Independent Test**: 국내 종목 하나로 시뮬레이션을 돌려 표의 행과 요약 값이 나오는지
확인한다. 환율·차트·이력 없이 검증할 수 있다.

### Tests for User Story 1 ⚠️

> **이 테스트들을 먼저 작성하고 실패를 확인한 뒤 구현한다**

- [X] T024 [P] [US1] `backend/tests/unit/test_reinvest_core.py` — **순수 함수** 시뮬레이터를 검증한다. 초기 1회 매수(FR-006), 정수 매수와 예수금 보존(FR-007, SC-006), 월 첫 거래일 행 생성(FR-025), **제공처가 준 분할 이벤트를 그대로 반영**(FR-010, FR-010a) — 가격 점프로 재판정하지 않는다. **역분할에서 정수로 떨어지지 않으면 버리는지**도 본다 — 올리거나 반올림하면 없던 주식이 생기는데 오류가 나지 않는다 (FR-010). DB·HTTP 없이 단독으로 돈다 (헌법 원칙 IV)
- [X] T025 [P] [US1] `backend/tests/unit/test_buy_quantity.py` — 매수 수량 산식을 검증한다. **수수료를 포함한 총액이 예수금을 넘지 않는** 최대 정수인지, **예수금이 음수가 되지 않는지**(SC-024) 확인한다. 수량을 시가로만 정하고 수수료를 나중에 빼는 구현은 여기서 걸린다 (FR-007a, FR-007b, SC-025)
- [X] T026 [P] [US1] `backend/tests/unit/test_reinvest_balance.py` — 잔고가 **보유 주식 수 × 그 행의 시가**이고 예수금을 포함하지 않는지, 총자산이 잔고+예수금인지 검증한다 (FR-013, SC-003, SC-004)
- [X] T027 [P] [US1] `backend/tests/unit/test_no_adjusted_price.py` — 시뮬레이터가 **수정종가를 읽지 않는지** 정적·동적으로 검사한다. 섞으면 배당이 이중 계산되는데 값은 그럴듯하다 (FR-011, SC-005)
- [X] T028 [P] [US1] `backend/tests/integration/test_stock_search_api.py` — 국내·미국·일본 종목이 모두 검색되는지(FR-002), 응답에 **시장과 거래 통화**가 함께 오는지(FR-002b), 출처 실패와 "결과 없음"이 구별되는지 검증한다 (contracts/rest-api)
- [X] T029 [P] [US1] `backend/tests/integration/test_simulation_api.py` — 표 응답의 행 구조, 커서 페이지, `hasMore`를 검증한다. **월 행에 배당 키가 없는지**(FR-026) 확인한다 — 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다
- [X] T030 [P] [US1] `backend/tests/integration/test_simulation_errors.py` — 상장 이전 시작일이 400 `before_listing`인지(FR-005), 시세를 얻을 수 없을 때 **빈 표가 아니라 사유**가 오는지(FR-004, SC-016) 검증한다
- [X] T031 [P] [US1] `frontend/tests/StockSearch.test.tsx` — 검색 결과에 시장·통화가 보이는지, **코드 직접 입력 칸이 없는지**(SC-031), 키보드로 고를 수 있는지 검증한다 (FR-002a, SC-030)
- [X] T032 [P] [US1] `frontend/tests/PerformanceTable.test.tsx` — 열 구성, 월 행의 빈 배당 칸, **날짜가 실제 거래일인지**(FR-028) 검증한다
- [X] T033 [P] [US1] `frontend/tests/PerformanceBoard.test.tsx` — 투자 원금·수익·수익률이 보이는지, **기준 구간이 함께 드러나는지**(FR-031) 검증한다. **보드의 수치와 표 마지막 행의 대응 수치가 같은지**도 본다 — 어긋나면 사용자는 어느 쪽이 맞는지 알 수 없다 (FR-032, SC-013)

### Implementation for User Story 1

- [X] T034 [US1] `backend/src/simulation/reinvest.py`에 **순수 함수** 시뮬레이터의 핵심을 만든다 — 일별 시세·분할·조건을 받아 행 목록을 돌려준다. `repository`·`api`·`db`를 임포트하지 않는다 (헌법 원칙 IV, research R5-4)
- [X] T035 [US1] `backend/src/simulation/reinvest.py`에 매수 수량 산식을 넣는다. `수량 = ⌊예수금 ÷ (시가 × (1 + 수수료율))⌋` (data-model 5절, FR-007a)
- [X] T036 [US1] `backend/src/api/services/stock_simulation.py`에 조회·조합을 만든다. 계산은 `simulation/`에 **위임만** 한다 — 여기서 직접 계산하면 원칙 IV 위반이고, 001의 `test_layer_boundaries`가 같은 검사를 한다
- [X] T037 [US1] `backend/src/api/routes/stock_search.py`에 검색 엔드포인트를 만든다. **검색 실패와 "결과 없음"을 구별한다** — 출처가 죽었는데 빈 목록을 주면 사용자는 그 종목이 존재하지 않는다고 읽는다. 목록을 미리 쌓지 않고 검색 시점에 출처에 묻는다 — **신규 상장 종목이 빠지지 않는 근거다**(FR-002c, research R5-2) (contracts/rest-api)
- [X] T038 [US1] `backend/src/api/routes/stock_simulation.py`에 시뮬레이션 엔드포인트를 만든다. 금액·비율은 전부 **문자열**로 직렬화한다 — JSON `number`는 IEEE 754라 원칙 VI를 API 경계에서 무력화한다
- [X] T039 [US1] `backend/src/api/routes/stock_simulation.py`에 커서 페이지(`before`·`limit`)를 더한다. 004의 방식을 잇는다 (FR-029)
- [X] T040 [P] [US1] `frontend/src/components/stock/StockSearch.tsx`를 만든다. **코드를 직접 입력하는 칸을 두지 않는다** — 확정은 목록에서 고르는 것으로만 이루어진다 (FR-002a, ui-wireframes W1)
- [X] T041 [P] [US1] `frontend/src/components/stock/SimulationForm.tsx`를 만든다 — 시작일·원금·통화·재투자 여부 (FR-001, FR-003)
- [X] T042 [P] [US1] `frontend/src/components/stock/PerformanceBoard.tsx`를 만든다. **기준 구간을 함께 쓴다** (FR-031, ui-wireframes W2)
- [X] T043 [P] [US1] `frontend/src/components/stock/PerformanceTable.tsx`를 만든다. 004의 `DailyTable`이 세운 형태를 잇는다 (FR-024, ui-wireframes W4)
- [X] T044 [US1] `frontend/src/stores/stockStore.ts`를 만든다 — 종목·조건·결과·로딩 상태 (헌법 원칙 VII)
- [X] T045 [US1] `frontend/src/app/stocks/page.tsx`를 만들어 화면을 조립한다. **경로는 복수(`stocks`)다** — 기존 가드 `noUnbuiltAssetRoutes.test.ts`가 그 이름을 전제하므로 단수로 두면 가드가 실패가 아니라 **통과**한다 (ui-wireframes W1)
- [X] T046 [US1] `frontend/src/components/shell/Sidebar.tsx`의 주식 메뉴를 `/stocks`로 연결하고 "준비중"을 걷어낸다. 함께 **기존 테스트 3건을 갱신한다** — `frontend/tests/noUnbuiltAssetRoutes.test.ts`의 `UNBUILT`에서 `stocks`를 빼고 `hrefs` 기대값에 `/stocks`를 더하며, `frontend/tests/Sidebar.test.tsx`의 "준비되지 않은 자산군" 목록과 `준비중` 개수(6 → 5)를 고친다. 남겨 두면 US1 체크포인트에서 전체 테스트가 실패한다 — 004에서 002의 `더 보기` 테스트가 같은 모양이었다 (FR-050, SC-033, 002 FR-005)
- [X] T047 [P] [US1] `frontend/tests/PerformanceTableScroll.test.tsx` — 스크롤로 이어 보는지, **`더 보기` 버튼이 없는지**, 끝에 도달하면 알리는지 검증한다 (FR-029, FR-030, SC-012)
- [X] T048 [US1] `frontend/src/components/stock/PerformanceTable.tsx`에 004의 `useInfiniteScroll`을 붙인다. 감시 지점이 처음부터 보이면 스크롤 없이도 시작된다 (FR-029)
- [X] T049 [P] [US1] `backend/tests/integration/test_simulation_reproducible.py` — 같은 입력을 두 번 실행해 결과가 같은지 검증한다. **원주가는 바뀌지 않지만 수정주가는 바뀐다** — 재현성이 원주가에 기대는 근거다 (FR-014, SC-002)

**Checkpoint**: 종목을 골라 성과를 볼 수 있다. **여기까지가 MVP다**

---

## Phase 4: User Story 2 - 배당을 다시 넣었다면 얼마나 달랐는지 본다 (Priority: P1)

**Goal**: 배당락 행이 나오고, 재투자를 켜면 그날 시가로 예수금 전액을 써서 정수 매수한다.

**Independent Test**: 배당이 있는 종목으로 재투자를 켠 결과와 끈 결과의 보유 주식 수가
다른지 확인한다.

### Tests for User Story 2 ⚠️

- [ ] T050 [P] [US2] `backend/tests/unit/test_dividend_rows.py` — 배당락 행이 생기는지, 주당 배당금과 배당율이 채워지는지, **월 행에는 그 키가 없는지** 검증한다 (FR-025, FR-026)
- [ ] T051 [P] [US2] `backend/tests/unit/test_reinvest_on.py` — 재투자가 켜지면 세후 배당금을 예수금에 더한 뒤 **그날 시가로 예수금 전액**을 써서 정수 매수하는지, 배당락 행이 **재투자까지 반영된 상태**인지 검증한다 (FR-008, FR-027)
- [ ] T052 [P] [US2] `backend/tests/unit/test_reinvest_off.py` — 재투자가 꺼지면 세후 배당금이 예수금에 쌓이기만 하고 보유 주식이 늘지 않는지 검증한다 (FR-009)
- [ ] T053 [P] [US2] `backend/tests/unit/test_dividend_tax.py` — 세율이 세전 배당금에 적용되는지, 세율을 바꾸면 결과가 달라지는지 검증한다. **저장은 세전이다** — 세후를 저장하면 세율을 바꿨을 때 과거 행이 낡는다 (FR-016, data-model `stock_dividend`)
- [ ] T054 [P] [US2] `backend/tests/unit/test_same_day_events.py` — 같은 날 배당과 분할이 겹치면 **분할을 먼저 적용하고 배당을 계산**하는지, 같은 날 여러 배당이 합산되는지 검증한다 (spec Assumptions, Edge Cases)
- [ ] T055 [P] [US2] `backend/tests/integration/test_reinvest_difference.py` — 재투자 켬/끔의 보유 주식 수가 다른지 검증한다 (SC-011)
- [ ] T056 [P] [US2] `backend/tests/integration/test_settings_api.py` — 수수료·세율 조회·변경, 범위 밖 값이 422인지, `isDefault`가 맞는지 검증한다 (FR-015, FR-016)
- [ ] T057 [P] [US2] `backend/tests/integration/test_settings_applied.py` — 설정을 바꾸면 **새 값 기준으로 다시 제시되는지**(FR-017, SC-007), 응답에 **적용된 수수료율·세율이 실리는지**(FR-018, SC-008) 검증한다. 갱신되지 않으면 화면은 정상으로 보이면서 낡은 값을 보여준다
- [ ] T058 [P] [US2] `frontend/tests/StockSettings.test.tsx` — 설정 화면의 두 항목과 기본값 표시를 검증한다

### Implementation for User Story 2

- [ ] T059 [US2] `backend/src/simulation/reinvest.py`에 배당 처리를 더한다 — 세후 배당금 산출, 배당락 행 생성, 재투자 매수 (FR-008, FR-009, FR-027)
- [ ] T060 [US2] `backend/src/simulation/reinvest.py`에 같은 날 이벤트 순서를 못박는다. **분할 먼저, 배당 나중** (spec Assumptions)
- [ ] T061 [US2] `backend/src/api/routes/stock_settings.py`에 설정 조회·변경을 만든다 (FR-015, FR-016)
- [X] T062 [US2] `backend/src/repository/stock_setting.py`에 전역 단일 행 조회·저장을 만든다 (data-model `stock_setting`)
- [ ] T063 [US2] `backend/src/api/routes/stock_simulation.py`의 응답에 `condition`을 더한다 — 적용된 수수료율·세율. 설정은 언제든 바뀌므로 **값만 남으면 어느 조건의 결과인지 알 수 없다** (FR-018)
- [ ] T064 [US2] `frontend/src/components/stock/PerformanceTable.tsx`에 배당락 행 표시를 더한다. 월 행과 구별되게 한다 (FR-025, ui-wireframes W4)
- [ ] T065 [US2] `frontend/src/app/settings/page.tsx`에 수수료·세율 입력을 더한다. 002의 스프레드 설정과 같은 자리다 (FR-015, FR-016)
- [ ] T066 [US2] `frontend/src/stores/stockStore.ts`에 설정 변경 시 결과를 **다시 받는** 경로를 만든다 (FR-017, ui-wireframes 갱신 범위)

**Checkpoint**: 배당 재투자의 효과를 켰다 껐다 하며 볼 수 있다

---

## Phase 5: User Story 3 - 외화 종목을 내 돈 기준으로 본다 (Priority: P2)

**Goal**: 원화 원금으로 미국·일본 종목에 투자한 결과를 원화 기준으로 본다.

**Independent Test**: 미국 종목에 원화 원금으로 투자해, 적용된 환율과 환전 결과가
드러나는지 확인한다.

### Tests for User Story 3 ⚠️

- [ ] T067 [P] [US3] `backend/tests/unit/test_initial_exchange.py` — 초기 환전이 **현금 살 때 환율에 스프레드의 10%만 적용**한 값인지 검증한다. 우대 방향을 반대로 잡으면 환전 금액이 조용히 달라진다 (FR-019, FR-020)
- [ ] T068 [P] [US3] `backend/tests/unit/test_valuation_fx.py` — 평가 환산이 **매매기준율**을 쓰는지, 현금 살 때 환율이나 우대가 섞이지 않는지 검증한다. 섞으면 잔고가 매수 스프레드만큼 크게 나온다 (FR-041b, SC-021)
- [ ] T069 [P] [US3] `backend/tests/unit/test_fx_missing_day.py` — 기준일에 고시가 없으면 **가장 가까운 이전 고시일**을 쓰고 **그 날짜를 함께 돌려주는지** 검증한다. 밝히지 않으면 곧바로 원칙 V 위반이다 (FR-041c, research R5-6)
- [ ] T070 [P] [US3] `backend/tests/integration/test_simulation_fx.py` — 외화 종목 응답에 `exchange`와 행별 `fxRate`·`fxRateDate`가 오는지, **행마다 환율이 다른지**(초기 환율 하나로 전 구간을 환산하지 않는지) 검증한다 (FR-021, FR-041a, SC-009, SC-020)
- [ ] T071 [P] [US3] `backend/tests/integration/test_simulation_no_fx.py` — 원금 통화와 종목 통화가 같으면 환전이 일어나지 않는지(FR-023), 환율이 아예 없으면 409 `fx_unavailable`인지 검증한다
- [ ] T072 [P] [US3] `frontend/tests/PerformanceBoardFx.test.tsx` — 보드에 적용 환율·날짜와 **기준 통화**가 드러나는지 검증한다 (FR-041, SC-019)

### Implementation for User Story 3

- [ ] T073 [US3] `backend/src/api/services/stock_fx.py`에 **초기 환전**을 만든다 — 현금 살 때 환율에 우대 적용. 실제로 돈을 바꾸는 1회 행위다 (FR-019, FR-020)
- [ ] T074 [US3] `backend/src/api/services/stock_fx.py`에 **평가 환산**을 만든다 — 매매기준율. 환전이 아니라 값어치를 재는 것이다. 두 함수를 한 이름으로 합치지 않는다 (FR-041b, research R5-6)
- [ ] T075 [US3] `backend/src/api/services/stock_fx.py`에 고시 없는 날의 대체를 만든다 — 가장 가까운 이전 고시일과 **그 날짜를 함께** 돌려준다 (FR-041c, FR-022)
- [ ] T076 [US3] `backend/src/api/services/stock_simulation.py`에 기준일별 환산을 붙인다. **초기 환율 하나로 전 구간을 환산하지 않는다** — 그러면 그 뒤의 환율 변동이 통째로 사라져, 주가는 올랐는데 환율이 내려 실제로는 손실인 구간이 이익으로 보인다 (FR-041a)
- [ ] T077 [US3] `backend/src/api/routes/stock_simulation.py`의 응답에 `exchange`와 행별 `fxRate`·`fxRateDate`를 더한다 (contracts/rest-api)
- [ ] T078 [US3] `frontend/src/components/stock/PerformanceBoard.tsx`에 환전 정보와 **기준 통화 표시**를 더한다 (FR-041, ui-wireframes W2)
- [ ] T079 [US3] `frontend/src/components/stock/PerformanceTable.tsx`에 환율 열과 **옮겨진 환율 날짜 표시**를 더한다. 기호만으로 전달하지 않는다 (FR-041c, ui-wireframes W4)

**Checkpoint**: 외화 종목을 원화 기준으로 볼 수 있다

---

## Phase 6: User Story 4 - 성과의 흐름을 차트로 본다 (Priority: P2)

**Goal**: 잔고와 수익률의 추이를 차트로 본다.

**Independent Test**: 시뮬레이션 결과로 차트가 그려지고 휴장일에 선이 끊기지 않는지
확인한다.

### Tests for User Story 4 ⚠️

- [ ] T080 [P] [US4] `frontend/tests/PerformanceChart.test.tsx` — 잔고와 수익률이 함께 그려지는지, 축이 구별되는지 검증한다 (FR-033)
- [ ] T081 [P] [US4] `frontend/tests/PerformanceChartGaps.test.tsx` — **휴장일은 선을 잇고 미수집 구간은 끊는지** 검증한다. 001이 2026-09-27 반복에서 정한 규칙이다 (FR-034)

### Implementation for User Story 4

- [ ] T082 [US4] `frontend/src/components/stock/PerformanceChart.tsx`를 만든다. 001의 `chartSeries.ts`가 쓰는 `reason`별 분리 규칙을 그대로 쓴다 (FR-033, FR-034, ui-wireframes W3)
- [ ] T083 [US4] `backend/src/api/routes/stock_series.py`에 차트용 시계열 엔드포인트를 만든다. 표와 **같은 순수 함수를 같은 입력으로** 부른다 — 다른 경로를 타면 표의 마지막 행과 차트의 끝점이 달라진다. `maxPoints` 초과 시 001의 `simulation/downsample.py`를 재사용한다 (FR-033, SC-032, contracts/rest-api)
- [ ] T083a [P] [US4] `backend/tests/integration/test_stock_series_api.py` — 포인트가 **원금 통화 기준**인지(FR-041), `gaps`의 `reason`이 구분되는지(FR-034), **표 마지막 행과 시계열 끝점이 일치하는지**(SC-032) 검증한다

**Checkpoint**: 성과의 흐름이 보인다

---

## Phase 7: User Story 5 - 여러 종목을 나란히 비교한다 (Priority: P3)

**Goal**: 이력에서 여럿을 골라 수익률을 한 차트에 겹쳐 본다.

**Independent Test**: 두 개 이상의 시뮬레이션을 돌린 뒤 히스토리에서 골라 한 차트에
겹치는지 확인한다.

### Tests for User Story 5 ⚠️

- [ ] T084 [P] [US5] `frontend/tests/simulationHistory.test.ts` — 이력에 **종목·시작일·원금·재투자 여부**가 모두 남는지(FR-036, SC-014), 같은 종목의 다른 조건이 구별되는지, 브라우저를 닫았다 열어도 남는지 검증한다 (FR-037)
- [ ] T085 [P] [US5] `frontend/tests/simulationHistory.test.ts`에 **저장 실패 처리**를 더한다 — 보관 한계에 닿으면 조용히 실패하지 않고 알리는지 (research R5-10)
- [ ] T086 [P] [US5] `frontend/tests/SimulationHistory.test.tsx` — **이 브라우저에만 저장된다는 안내**가 보이는지(FR-037a, SC-018), 항목을 지울 수 있는지(FR-037b) 검증한다
- [ ] T087 [P] [US5] `frontend/tests/ComparisonChart.test.tsx` — 고른 항목들의 수익률이 한 차트에 겹치는지(FR-038), **비교 기준이 드러나는지**(FR-039, SC-015), 시작일이 다르면 각 시작 시점이 드러나는지(FR-040) 검증한다

### Implementation for User Story 5

- [ ] T088 [US5] `frontend/src/lib/simulationHistory.ts`에 `localStorage` 보관을 만든다. **조건만 저장한다** — 결과는 설정·환율이 바뀌면 달라지므로 저장하면 조용히 낡는다 (research R5-9, R5-10)
- [ ] T089 [US5] `frontend/src/components/stock/SimulationHistory.tsx`를 만든다. 안내와 삭제 수단을 둔다 (FR-035~037b, ui-wireframes W5)
- [ ] T090 [US5] `frontend/src/components/stock/ComparisonChart.tsx`를 만든다. **수익률(%)로 겹친다** — 통화가 다른 잔고를 같은 축에 놓으면 숫자 크기가 달라 한쪽이 평평해지고, 사용자는 그 종목이 움직이지 않았다고 읽는다 (FR-038~040, ui-wireframes W6)
- [ ] T091 [US5] `frontend/src/stores/stockStore.ts`에 이력 선택과 비교 실행을 더한다

**Checkpoint**: 다섯 스토리 모두 독립적으로 동작한다

---

## Phase 8: Polish & Cross-Cutting Concerns

### 수집 중 사용자 경험 (전 스토리 공통)

- [ ] T092 [P] `backend/tests/integration/test_collecting_response.py` — 미수집 구간이 있으면 **202 `collecting`**이 오는지(FR-047), **부분 결과가 200으로 나가지 않는지**(FR-049, SC-029), 진행 상태가 **갱신 없이 10초 이상 멈추지 않는지**(SC-001a) 검증한다. 받는 도중의 수익률은 값이 멀쩡해 보이지만 틀렸다
- [ ] T093 `backend/src/api/routes/stock_simulation.py`에 202 경로를 만든다. 001·002가 정한 수집 중 응답 규약을 잇는다 (FR-047, contracts/rest-api)
- [ ] T094 [P] `frontend/tests/CollectingNotice.test.tsx` — 수집 진행이 보이는지, **부분 결과가 표로 먼저 나오지 않는지** 검증한다 (FR-049, SC-029)
- [ ] T095 `frontend/src/components/stock/CollectingNotice.tsx`를 만들고 `stockStore`에 SSE 구독을 붙인다 (FR-047, ui-wireframes W7)

### 시세 단절

- [ ] T096 [P] `backend/tests/integration/test_delisted.py` — 시세가 끊긴 종목에서 **마지막 시세일까지만** 계산하는지, `asOf`가 오늘이 아니고 `isFinal`이 거짓인지 검증한다 (FR-014a, SC-026)
- [ ] T097 `backend/src/api/services/stock_simulation.py`에 시세 단절 판정을 더한다. **마지막 시세를 오늘까지 이어 그리지 않는다** — 없는 값을 만드는 것이라 원칙 V 위반이다 (FR-014a)
- [ ] T098 [P] `frontend/tests/PerformanceBoardAsOf.test.tsx` — 계산의 마지막 날이 오늘이 아니면 **표와 보드 양쪽에서** 드러나는지 검증한다 (FR-014b, SC-027)
- [ ] T099 `frontend/src/components/stock/PerformanceBoard.tsx`에 기준일 안내를 더한다. 상장폐지는 대개 큰 손실인데 알리지 않으면 화면에는 폐지 직전 수익률이 남는다 (FR-014b)

### 헌법 게이트

- [ ] T100 [P] `backend/tests/unit/test_no_float.py`에 검사를 더한다 — `simulation/`·`repository/`의 주식 경로에 `float(` 사용이 없는지. **참조 구현이 JS `number`를 쓰므로 이식 과정 전체가 위험 구간이다** (헌법 원칙 VI)
- [ ] T101 [P] `backend/tests/unit/test_no_interpolation.py`에 검사를 더한다 — 주식 경로에 값을 채우는 코드가 없는지. 휴장일·상장 이전 구간·배당 없는 달을 값으로 메우지 않는다 (FR-042, SC-010, 헌법 원칙 V)
- [ ] T102 [P] `backend/tests/unit/test_layer_boundaries.py`에 검사를 더한다 — `simulation/reinvest.py`가 `repository`·`api`·`db`를 임포트하지 않는지 (헌법 원칙 IV)
- [ ] T103 [P] `backend/tests/unit/test_orm_types.py`에 검사를 더한다 — 신규 8개 테이블의 금액·비율 컬럼에 `Float`가 없는지 (헌법 원칙 VI)
- [ ] T104 `backend/src`·`backend/tests`에 mypy strict와 ruff를 통과시킨다
- [ ] T105 `frontend/`에 `npx tsc --noEmit`과 `npx eslint .`를 통과시킨다. `any` 사용 금지
- [ ] T106 `backend/`에서 커버리지 80% 이상을 확인한다 — `cd backend && .venv/bin/python -m pytest -q --cov=src` (헌법 품질 게이트)
- [ ] T107 `backend/tests/`와 `frontend/tests/` 전체 스위트가 **네트워크 차단 상태에서** 통과하는지 확인한다 (헌법 원칙 III)

### 참조 구현 대조

- [ ] T108 `backend/tests/unit/test_reference_parity.py` — 참조 Apps Script와 **같은 조건**에서 보유 주식 수와 배당 내역이 일치하는지 검증한다. **수수료를 0%로 두고 대조한다** — 참조 구현은 수수료를 다루지 않는다(주석 "수수료 X"). 순수 함수라 이 대조가 단위 테스트로 가능하다 (research R5-4)

### 마무리

- [ ] T109 `specs/005-stock-investment-simulation/quickstart.md`의 검증 시나리오 22개를 순서대로 수동 실행하고 결과를 기록한다. 시나리오 3이 **시세가 보관된 경우 30초 이내**(SC-001)를, 시나리오 2가 **수집 중 진행 표시**(SC-001a)를 확인한다. **새 종목을 연달아 여럿 돌리는 것은 피한다** — 출처가 호출 한도를 공개하지 않으며 공격적 폴링을 막는다
- [ ] T110 `README.md`의 현재 상태 표에 005를 더하고 자산군 진행을 갱신한다
- [ ] T111 `CLAUDE.md`의 현재 상태 절을 갱신한다 — 주식 자산군 추가와 **가상자산이 006으로 남아 있다는 사실**을 적는다 (plan Complexity Tracking)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작
- **Foundational (Phase 2)**: Setup 완료 후 — **모든 사용자 스토리를 차단**
- **US1 (Phase 3)**: Foundational 완료 후. **MVP**
- **US2 (Phase 4)**: US1 완료 후. 시뮬레이터 코어 위에 배당을 얹는다
- **US3 (Phase 5)**: US1 완료 후. US2와 독립이나 표 구조를 공유한다
- **US4 (Phase 6)**: US1 완료 후. 결과 데이터가 있어야 그릴 것이 있다
- **US5 (Phase 7)**: US1 완료 후. 비교할 대상이 있어야 한다
- **Polish (Phase 8)**: 원하는 스토리가 모두 끝난 뒤

### 스토리 간 의존

```
Setup → Foundational → US1 (MVP) ─┬→ US2 (배당·재투자)
                                  ├→ US3 (환율)
                                  ├→ US4 (차트)
                                  └→ US5 (이력·비교)
```

US2~US5는 서로 독립이다. US1이 만든 시뮬레이터와 표 위에 각각 얹힌다.

### Within Each User Story

- 테스트를 먼저 쓰고 **실패를 확인한 뒤** 구현한다 (헌법 원칙 III)
- 순수 함수 → 리포지토리 → 서비스 → 라우트 → 화면 순
- 한 스토리를 끝내고 다음 우선순위로 넘어간다

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/simulation/reinvest.py` | T034, T035, T059, T060 |
| `backend/src/api/services/stock_simulation.py` | T036, T076, T097 |
| `backend/src/api/services/stock_fx.py` | T073, T074, T075 |
| `backend/src/api/routes/stock_simulation.py` | T038, T039, T063, T077, T093 |
| `backend/tests/integration/test_stock_upsert.py` | T014, T023 |
| `backend/tests/unit/test_layer_boundaries.py` | T013, T102 |
| `frontend/src/components/stock/PerformanceTable.tsx` | T043, T048, T064, T079 |
| `frontend/src/components/stock/PerformanceBoard.tsx` | T042, T078, T099 |
| `frontend/src/stores/stockStore.ts` | T044, T066, T091, T095 |
| `frontend/tests/simulationHistory.test.ts` | T084, T085 |
| `frontend/tests/noUnbuiltAssetRoutes.test.ts` | T046 (기존 가드 갱신) |
| `frontend/tests/Sidebar.test.tsx` | T046 (기존 가드 갱신) |

---

## Parallel Example: User Story 1

```bash
# US1의 단위 테스트를 한꺼번에 작성 (서로 다른 파일):
Task: "test_reinvest_core.py — 초기 매수·정수 매수·월 행·분할"
Task: "test_buy_quantity.py — 수수료 포함 총액, 예수금 음수 금지"
Task: "test_reinvest_balance.py — 잔고는 예수금을 포함하지 않는다"
Task: "test_no_adjusted_price.py — 수정종가를 읽지 않는다"
```

---

## Implementation Strategy

### MVP First (User Story 1만)

1. Phase 1 Setup 완료
2. Phase 2 Foundational 완료 (**모든 스토리를 차단하므로 최우선**)
3. Phase 3 US1 완료
4. **멈추고 검증**: quickstart 시나리오 1·2·3·4·5·14·18·19·20으로 US1을 독립 검증
5. 이 시점에 **종목을 골라 투자 성과를 볼 수 있다**

### Incremental Delivery

1. Setup + Foundational → 시세를 받아 저장할 수 있다
2. US1 → quickstart 1·2·3·4·5·14·18·19·20 → **MVP**
3. US2 → quickstart 6·7·13 → 배당 재투자의 효과가 보인다
4. US3 → quickstart 9·10·11·12 → 외화 종목을 원화 기준으로 본다
5. US4 → quickstart 15 → 흐름이 보인다
6. US5 → quickstart 17 → 종목을 비교한다
7. Polish → quickstart 8·16·21·22

---

## Notes

- `[P]` = 서로 다른 파일, 의존 없음
- 테스트 묶음 작성 → 실패 확인 → 구현 순서를 지킨다. **구현 후에도 실패가 남으면 중단하고
  사용자에게 보고한다** (헌법 v5.2.0 원칙 III, NON-NEGOTIABLE)
- 요구사항을 새로 만들거나 바꾸면 `plan.md` 추적성과 이 문서의 참조를 **같은 작업 단위에서**
  갱신한다 (헌법 명세 작성 규약)
- **출처 호출을 아껴 쓴다.** 호출 한도가 공개되지 않으며 공격적 폴링이 차단의 주된
  원인이다. 테스트는 전부 픽스처·스텁으로 돌고, 수동 검증에서만 실제 호출이 나간다
- **헌법 위반 2건이 기록된 상태다** — 원칙 IX(자산군 순서), 원칙 II(이용약관).
  `plan.md`의 Complexity Tracking을 읽고 시작한다
- 태스크마다 또는 논리적 묶음마다 커밋한다
