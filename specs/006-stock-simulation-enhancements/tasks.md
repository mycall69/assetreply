---

description: "Task list for 006-stock-simulation-enhancements"
---

# Tasks: 주식 시뮬레이션 개선 — 시작일·종목 검색·환전

**Input**: Design documents from `/specs/006-stock-simulation-enhancements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를
지킨다. 구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US5)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를
  재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수)

## 이 기능에서 특히 조심할 것

- **HTTP 200인 실패**: 키움은 본문 `return_code`로 실패를 알린다. 상태 코드만 보면 실패 응답을 빈
  목록으로 읽어 **전 종목을 "목록에서 빠짐"으로 바꾼다** — 오류도 나지 않는다 (research R6-1)
- **성공 픽스처만 있으면 방어선이 테스트되지 않는다**: 중간 쪽 실패, 짧게 온 목록, 인증 실패, 한도
  초과 응답을 각각 픽스처로 둔다. 공식 응답 예시는 자리 표시용이라 픽스처로 쓰지 않는다 (research R6-2)
- **토큰은 메모리에만**: 원본 보관 규칙을 인증 응답이나 헤더에 적용하는 순간 토큰이 DB에 남는다 (FR-061)
- **005에서 발견한 결함 둘**: 고른 종목을 저장하는 경로가 없다(`ensure_stock` 호출처 0), `first_available_date`가
  채워지지 않아 휴일 시작을 거절한다. **테스트 픽스처가 `stock` 행을 직접 넣으면 두 결함이 다시 가려진다** —
  US1·US3의 통합 테스트는 반드시 **검색 → 등록 → 실행** 경로를 탄다 (research R6-17)
- **001의 `ensure_background_job`이 고아 점유를 남긴다**: 작업과 점유만 만들고 워커에 넘기지 않는다. 006은
  환율 수집을 003의 `StartQueue`로 하고, 그 함수도 큐로 넘기도록 **함께 고친다**(T091·T092, FR-046a) —
  외환 화면이 남긴 점유가 006의 수집을 막기 때문이다 (research R6-10, analyze H2)
- **원본 응답은 지우지 않는다**: 보존 기간을 두면 헌법 원칙 V 위반이다. 같은 본문은 한 번만 저장한다
  (research R6-13, analyze C1)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 설정과 계약 테스트 픽스처를 갖춘다

- [ ] T001 [P] `backend/tests/unit/test_settings_kiwoom.py` — data-model 7절의 키 11개가 기본값대로 읽히는지, `LISTING_SHRINK_THRESHOLD`가 `Decimal`인지, `KIWOOM_MODE`가 `real`·`mock` 밖이면 기동을 거절하는지, **앱 키·시크릿이 설정 객체의 `repr`·`str`에 드러나지 않는지** 검증한다 (FR-060, FR-063)
- [ ] T002 `backend/src/config/settings.py`에 키움·목록 설정을 더한다. 키·시크릿은 ECOS 키와 같은 비밀 감싸개(`reveal()`)로 둔다 (FR-060, FR-063, data-model 7절)
- [ ] T003 [P] `.env.example`에 data-model 7절의 키 이름을 **값 없이** 더한다 (FR-060)
- [ ] T004 [P] `backend/scripts/capture_kiwoom_fixtures.py`를 만든다 — 실제 응답을 받아 `backend/tests/contract/fixtures/kiwoom/`에 쪽마다 저장한다. **토큰 발급 응답과 요청·응답 헤더를 저장하지 않는다.** 연속조회 여부만 파일 이름에 남긴다. 테스트 스위트에서 실행되지 않는다 (FR-061, research R6-2)
- [ ] T005 T004를 **한 번 실행**해 픽스처를 만든다(키움 키 필요, 실제 출처 호출). 국내 4단위·미국 3단위의 첫 쪽과 다음 쪽, **클래스 주식이 들어 있는 미국 쪽**을 받는다. 쪽당 건수·쪽 수를 `research.md` R6-2 "확인하지 못한 것"에 기록하고, 클래스 주식 표기를 R6-6에 기록한다. 실패 응답 픽스처(인증 실패 `8001`, 한도 `1700`, HTTP 200 + `return_code≠0`, 중간 쪽 실패, **이전의 40% 길이 목록**과 경계 검증용 **정확히 50% 길이 목록**)는 실제 응답의 모양을 본떠 손으로 만든다. **저장소가 비공개라 응답 전체를 픽스처로 커밋한다** — 저장소를 공개로 바꾸기 전에 검증에 필요한 행으로 줄인다 (SC-008, research R6-2, R6-6, R6-15)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 신규 테이블, 키움 어댑터의 공통 부분, 헌법 정적 검사

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 어떤 스토리도 시작하지 않는다

- [ ] T006 [P] `backend/tests/unit/test_orm_types.py`에 검사를 더한다 — 신규 5개 테이블이 정의되는지, `stock_listing`이 **`UNIQUE (country, code)`**이고 `unit`이 키가 아닌지, `status` 기본값이 `listed`인지, `name_ko`·`name_en`·`listed_on`이 NULL 허용인지, **가격·상장주식수 컬럼이 없는지**(FR-012), `stock_listing_refresh`·`stock_listing_lock`의 PK가 `unit`인지, **`stock_listing_raw_body`의 PK가 `sha256` CHAR(64)이고 `body`가 MEDIUMTEXT인지, `stock_listing_raw.body_sha256`이 그것을 가리키고 `stock_listing_raw`에 본문 컬럼이 없는지**, **`stock` 테이블의 컬럼이 005와 같은지** (FR-012, FR-019a, FR-061, data-model 1~4a절)
- [ ] T007 `backend/src/db/models.py`에 `StockListing`·`StockListingRefresh`·`StockListingLock`·`StockListingRaw`·`StockListingRawBody`를 더한다. 컬럼·타입·제약은 data-model 1~4a절을 그대로 따른다 — `code` VARCHAR(16) NOT NULL, `unit` VARCHAR(8) NOT NULL, `name_ko` VARCHAR(128) NULL, `name_en` VARCHAR(256) NULL, `kind` VARCHAR(8) NOT NULL(`stock`|`etf`|`reit`), `status` VARCHAR(8) NOT NULL 기본 `listed`(`listed`|`missing`), `last_error` VARCHAR(512) NULL, `stock_listing_raw_body.sha256` CHAR(64) PK, `stock_listing_raw.body_sha256` CHAR(64) NOT NULL FK, 인덱스 `(unit, status)` (FR-015, FR-019, FR-019a, FR-061)
- [ ] T008 `backend/src/db/migrations/versions/`에 마이그레이션 1개를 더하고 `backend/tests/integration/test_migrations.py`가 올림·내림을 모두 지나는지 확인한다 (헌법 DB 운영 규약)
- [ ] T009 [P] `backend/tests/contract/test_kiwoom_client.py` — 토큰을 **메모리에만** 두고 만료 10분 전에 갱신하는지, 연속조회가 **응답 헤더**의 `cont-yn`·`next-key`로 이어지는지, **HTTP 200 + `return_code≠0`을 실패로 판정하는지**, 오류 코드를 `auth`(8001·8002·8011·8012·8003·8005·8006·8009·8015·8016·8030·8031, HTTP 401)·`rate_limit`(1700~1702)·`network`(연결 실패·시간 초과·5xx)·`invalid`로 나누는지, `KIWOOM_MODE`에 따라 도메인이 바뀌는지 검증한다. aiohttp를 가짜 응답으로 바꿔 끼운다 (FR-013b, FR-060, FR-061, research R6-1, R6-3)
- [ ] T010 `backend/src/ingestion/kiwoom/errors.py`·`client.py`를 만든다. 공식 클라이언트를 쓰지 않는다. 토큰을 DB·파일·로그에 쓰지 않는다 (FR-060, FR-061, research R6-1)
- [ ] T011 [P] `backend/tests/unit/test_layer_boundaries.py`에 검사를 더한다 — 키움 응답 필드명(`stk_cd`·`stk_nm`·`stk_enm`·`stex_tp`·`mrkt_tp`·`regDay`·`listCount`·`lastPrice`)이 `ingestion/kiwoom/` 밖에 없는지, **`src/search/`가 존재하고** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는지. 패키지가 없으면 통과하지 않고 실패해야 한다 — 없는 모듈을 검사하면 조용히 통과한다 (헌법 원칙 II·IV)
- [ ] T012 [P] `backend/tests/unit/test_no_secret_in_events.py`에 검사를 더한다 — 키움 앱 키·시크릿·토큰 문자열이 수집 사건, `stock_listing_raw_body.body`, `stock_listing_refresh.last_error`에 남지 않는지 (FR-060, FR-061, SC-014)

**Checkpoint**: 테이블과 어댑터 공통 부분이 준비됐다

---

## Phase 3: User Story 1 - 국내 종목을 한글·초성으로 바로 찾는다 (Priority: P1) 🎯 MVP

**Goal**: 국내 목록을 받아 두고, 한글·초성·혼용·코드로 바로 찾고, 고른 종목으로 시뮬레이션까지 간다.

**Independent Test**: 국내 목록을 받아 둔 상태에서 quickstart 3의 표로 검색하고, 고른 종목으로 실행해
"알 수 없는 종목"이 나오지 않는지 확인한다. 미국 목록·환전·시작일 없이 검증한다.

### Tests for User Story 1 ⚠️

- [ ] T013 [P] [US1] `backend/tests/unit/test_search_hangul.py` — NFC 정규화, 공백 제거, 라틴 소문자화, 음절 → 초성 열, **쌍자음(ㅆ)과 홑자음(ㅅ)의 구별**, **받침 대기 판정**("서"는 마지막 글자일 때 "성"과 맞고, 마지막이 아니면 맞지 않음)을 표로 검증한다 (FR-022, research R6-5)
- [ ] T014 [P] [US1] `backend/tests/unit/test_search_match.py` — quickstart 3의 표를 그대로 옮긴다(삼성전자, ㅅㅅㅈㅈ, 삼ㅅㅈ, 삼성ㅈ, 삼서, 삼성 전자, 005930, sk하이닉스, ㅎㅇㄴㅅ, kodex 200, ㅆ). 순위가 정확 → 앞부분 → 포함인지, 같은 순위 안에서 **일치한 이름이 짧은 순 → 코드 포인트 순 → 시장 → 코드**인지, **입력 순서를 섞어도 결과 순서가 같은지**, 상한을 넘으면 잘림을 알리는지 검증한다 (FR-020, FR-022, FR-023, FR-024, SC-002, SC-003)
- [ ] T015 [P] [US1] `backend/tests/unit/test_search_performance.py` — 합성 종목 15,000건 색인에서 대표 검색어 100개의 처리 시간 95번째 백분위가 50ms 미만인지 검증한다. SC-001의 0.5초는 화면 입력 대기 150ms를 포함한다 (SC-001, research R6-5)
- [ ] T016 [P] [US1] `backend/tests/unit/test_price_symbol.py` — 국내: `KOSPI`·`KR_ETF`·`KR_REIT` → `KRX`/`{code}.KS`/KRW, `KOSDAQ` → `KRX`/`{code}.KQ`/KRW. **ETF·리츠를 목록상 구분으로 시장을 정하지 않는지**(FR-010a) (FR-010a, FR-030, FR-031)
- [ ] T017 [P] [US1] `backend/tests/contract/test_kiwoom_domestic.py` — T005의 실제 응답 픽스처로 국내 목록을 파싱한다. 0으로 앞을 채운 문자열, `regDay` → 날짜, 단위로 `kind`(`stock`·`etf`·`reit`)를 정하는지. **`code`가 비었거나 6자리가 아닌 행이 하나라도 있으면 단위 전체를 `invalid`로 실패시키는지** — 한 행을 조용히 버리면 그 종목만 "빠짐"이 된다. 목록의 `lastPrice`·`listCount`를 결과 타입에 싣지 않는지 (FR-010, FR-012, data-model 1절 검증 규칙)
- [ ] T018 [P] [US1] `backend/tests/unit/test_listing_refresh_decision.py` — 갱신 판정 순수 함수를 표로 검증한다: 오늘(KST) 이미 받음 → 안 함, 갱신 중 → 안 함, 인증 실패 막힘 → 안 함, 마지막 실패 후 30분 미만 → 안 함, 오늘 5회 도달 → 안 함, 그 밖 → 함. **자정(KST) 직후에 새 날로 넘어가는지**, UTC 날짜로 판정하지 않는지 (FR-013, FR-013a, FR-013b, SC-005a, research R6-3)
- [ ] T019 [P] [US1] `backend/tests/integration/test_listing_replace.py` — 교체 트랜잭션: **중간 쪽 실패면 아무것도 바뀌지 않는지**(FR-018), **이전 건수의 50%보다 적으면 교체하지 않고 `invalid`로 남기는지, 정확히 50%면 교체하는지**(FR-018a), 빠진 종목을 지우지 않고 `missing`으로 표시하는지(FR-019, SC-016), 다시 보이면 `listed`로 돌아오는지, **코스닥 → 코스피로 단위를 옮긴 종목이 행 하나로 남고 어느 단위가 먼저 갱신돼도 결과가 같은지**(FR-019a), 단위마다 기준 시각이 따로인지(FR-015), 실패해도 이전 목록이 그대로인지(FR-016, SC-004), 원본이 **헤더 없이** 쪽마다 남고 **지워지지 않는지**, 같은 본문을 다시 받으면 본문은 한 번만 저장되고 쪽 기록은 남는지(FR-061, research R6-13)
- [ ] T020 [P] [US1] `backend/tests/integration/test_listing_lock.py` — 같은 단위의 갱신을 동시에 둘 요청하면 **기본 키 충돌로 하나만** 시작하는지, 기동 시 남은 점유를 풀고 심장박동이 10분 넘게 멈춘 점유를 회수하는지 (FR-014, SC-005, data-model 3절)
- [ ] T021 [P] [US1] `backend/tests/integration/test_stock_search_local.py` — `GET /api/stocks/search`가 **외부 출처를 부르지 않는지**, 결과 필드(contracts/rest-api)가 맞는지, `lists[]`의 상태(`never`·`refreshing`·`ready`·`stale`·`failed`·`auth_blocked`)와 `reason`·`action`이 맞는지, **목록이 없을 때 오류가 아니라 200 + `lists`로 알리는지**, 갱신 중에도 **기다리지 않고** 이전 목록으로 답하는지, 상한을 넘으면 `truncated`인지, 갱신을 요청만 하는지 (FR-017, FR-024, FR-025, FR-028, FR-028a, FR-029, SC-006)
- [ ] T022 [P] [US1] `backend/tests/integration/test_stock_search_external.py` — `GET /api/stocks/search/external`가 결과에서 **TSE만 남기는지**(국내·미국 제외), 출처 장애를 005와 같은 오류로 내는지 (FR-026)
- [ ] T023 [P] [US1] `backend/tests/integration/test_stock_selection.py` — **검색 → 등록 → 실행** 경로로 검증한다(픽스처가 `stock` 행을 미리 넣지 않는다). `POST /api/stocks/selection`이 국내 목록 행으로 종목을 만들고, 005가 이미 저장한 같은 종목이 있으면 그것을 쓰고, 두 번 불러도 행이 하나인지. 일본 외부 결과로 등록할 때 시장이 TSE·통화가 JPY가 아니면 거절하는지. 없는 `listingId`는 `404 unknown_listing`. **미등록 국내 종목으로 시뮬레이션을 요청하면 목록으로 등록한 뒤 진행하는지**(이력 재실행 경로). **시작일은 거래일(예: 2021-08-02)로 잡는다** — T063 전에는 휴일 시작이 005 결함으로 거절된다. 이를 피하려고 픽스처에 `first_available_date`를 넣지 않는다 — 결함이 다시 가려진다 (FR-030, FR-030b, FR-033, SC-007, SC-007a, research R6-17)
- [ ] T024 [P] [US1] `backend/tests/integration/test_listing_auth_failure.py` — 인증 실패 시 **목록 갱신만 실패**하고 이전 목록 검색·일본 검색·시뮬레이션은 정상인지, 같은 날 다시 시도하지 않는지, 막힘을 초기화(재시작 흉내)하면 같은 날이라도 다시 시도하는지, 인증 정보가 비어 있으면 갱신을 시도하지 않고 `never`·`auth_missing`·`set_credentials`인지 (FR-013b, FR-028a, FR-062)
- [ ] T025 [P] [US1] `backend/tests/integration/test_simulation_errors.py`에 더한다 — 시세 출처가 심볼을 모르면 `404 price_symbol_unknown`, 받았는데 시세가 없으면 `404 no_price_data`로 **구별되는지** (FR-032)
- [ ] T026 [P] [US1] `frontend/tests/searchSequence.test.ts` — 요청 번호가 최신이 아닌 응답을 버리는지. 로컬·외부가 번호를 따로 가지는지 (FR-029a, research R6-12)
- [ ] T027 [P] [US1] `frontend/tests/StockSearchLocal.test.tsx` — 결과마다 시장·통화, 우선주 구별, ETF·리츠 표시, "목록에서 빠짐" 표시가 보이는지(글자로, 색만이 아님), 목록 기준 시각 줄이 보이는지, **결과가 비었을 때 `lists` 상태에 따라 "결과 없음"과 W2a의 "목록을 받지 못함 + 할 일"을 가르는지**, 잘림 안내가 보이는지 (FR-024, FR-025, FR-028, FR-028a, FR-029, SC-006)
- [ ] T028 [P] [US1] `frontend/tests/StockSearchRegions.test.tsx` — 로컬 결과가 **외부 검색을 기다리지 않고** 먼저 그려지는지, 외부 검색이 지연·실패해도 로컬 영역은 영향이 없고 실패는 일본 영역에만 보이는지, 로컬 입력 대기가 150ms·외부가 300ms인지 (FR-027, SC-001, SC-015)
- [ ] T029 [P] [US1] `frontend/tests/stockSelection.test.ts` — 결과를 고르는 순간 `/api/stocks/selection`을 부르는지, 실패하면 **실행 전에** 사유를 보이는지, 이후 시뮬레이션·이력이 **등록 응답의 식별**을 쓰는지 (FR-030, FR-030b)

### Implementation for User Story 1

- [ ] T030 [US1] `backend/src/search/hangul.py` — 정규화·초성 열·받침 대기 판정 (FR-022, research R6-5)
- [ ] T031 [US1] `backend/src/search/match.py` — 일치 판정, 순위, 결정적 정렬, 잘림 (FR-020, FR-023, FR-024)
- [ ] T032 [US1] `backend/src/search/price_symbol.py` — 국내 규칙 (FR-010a, FR-030, FR-031, research R6-6)
- [ ] T033 [US1] `backend/src/ingestion/kiwoom/parse.py` — 국내 목록 파싱과 검증. 출처 필드명은 이 파일에만 둔다 (FR-010, FR-012)
- [ ] T034 [US1] `backend/src/repository/stock_listing.py` — upsert·`missing` 표시(지금 그 단위에 속한 행만)·갱신 기록·점유 INSERT·원본 저장(본문은 SHA-256으로 중복 제거, 기본 키 충돌은 "이미 있음"). **종목·원본 테이블에 삭제 질의를 두지 않는다** (FR-014, FR-015, FR-019, FR-019a, FR-061)
- [ ] T035 [US1] `backend/src/api/services/listing_refresh.py` — 갱신 판정 순수 함수, 전 쪽을 받은 뒤의 검사(빈 목록·필수 필드·축소)와 한 트랜잭션 교체, 실패 종류와 사유 기록(키·토큰 없이), 인증 실패 막힘(프로세스 메모리) (FR-013, FR-013a, FR-013b, FR-015, FR-016, FR-018, FR-018a, FR-062, research R6-3, R6-4)
- [ ] T036 [US1] `backend/src/worker/listing_worker.py`를 만들고 `backend/src/api/main.py`의 `lifespan`에 등록한다. 기동 시 점유를 풀고 정체 점유를 회수한다. **등록을 빠뜨리면 갱신 요청이 쌓이기만 하고 실행되지 않는다** — 003·005가 겪은 일이다 (FR-013, FR-014, data-model 3절)
- [ ] T037 [US1] `backend/src/api/services/listing_index.py` — 메모리 색인. 검색마다 단위별 기준 시각의 최댓값을 읽어 바뀌었으면 다시 만든다 (SC-001, research R6-5)
- [ ] T038 [US1] `backend/src/api/routes/stock_search.py`를 로컬 검색으로 바꾸고 `/external`(TSE만)을 분리한다. 로컬 검색은 갱신을 **요청만** 한다 (FR-017, FR-021, FR-026, FR-027, FR-028, FR-029, research R6-12)
- [ ] T039 [US1] `backend/src/api/services/stock_selection.py`·`backend/src/api/routes/stock_selection.py`를 만들고 `main.py`에 등록한다. `stock_simulation.require_stock`은 국내·미국 미등록 종목을 목록으로 등록하고, 일본은 `404 unknown_stock` + `action: reselect`로 답한다 (FR-030, FR-030b, FR-033, research R6-17)
- [ ] T040 [US1] `backend/src/api/main.py`의 오류 처리기를 나눈다 — 시세 출처가 심볼을 모를 때 `price_symbol_unknown`, 우리 DB에 종목이 없을 때 `unknown_stock` (FR-032)
- [ ] T041 [US1] `frontend/src/lib/types.ts`에 검색 응답(`results`·`truncated`·`lists`)·외부 검색·등록 응답 타입을 더한다 (contracts/rest-api)
- [ ] T042 [US1] `frontend/src/lib/searchSequence.ts` (FR-029a)
- [ ] T043 [US1] `frontend/src/components/stock/StockSearch.tsx`를 두 영역(국내·미국 / 일본)으로 바꾼다. 로컬 입력 대기 150ms·외부 300ms, 목록 상태 줄, 잘림 안내, W2a (FR-024, FR-025, FR-027, FR-028, FR-028a, FR-029, ui-wireframes W2, W2a)
- [ ] T044 [US1] `frontend/src/stores/stockStore.ts` — 결과를 고르면 등록하고, 등록 응답의 식별을 입력·이력에 쓴다 (FR-030, FR-030b)

**Checkpoint**: 국내 종목을 한글·초성으로 찾아 시뮬레이션까지 간다

---

## Phase 4: User Story 2 - 원화로 외화 종목에 투자한 결과를 올바르게 본다 (Priority: P1)

**Goal**: 엔화 고시 단위를 반영하고, 필요한 환율이 없으면 받아 온 뒤 결과를 낸다.

**Independent Test**: 원화 원금·엔화 종목으로 첫 환전 금액이 고시 단위를 반영한 기대값인지, 환율이 없으면
수집 중으로 바뀌는지 확인한다. 검색·시작일 개선 없이 검증한다.

### Tests for User Story 2 ⚠️

- [ ] T045 [P] [US2] `backend/tests/unit/test_fx_per_unit.py` — `per_unit(900.000000, 100) = 9.000000`, `per_unit(x, 1) = x`, 원금 1,000,000원·100엔당 900원·스프레드 1.75%·우대 90%의 첫 환전이 **11만 엔대**인지(1,000엔대가 아님) (FR-042, SC-009, research R6-9)
- [ ] T046 [P] [US2] `backend/tests/integration/test_simulation_fx_jpy.py` — 엔화 종목·원화 원금: `exchange.rate`와 행의 `fxRate`가 **1엔당** 값인지, 첫 환전이 **실제 첫 매수일**의 환율인지(시작일이 휴일이어도), 평가 환산이 매매기준율인지 (FR-040, FR-041, FR-042, SC-009)
- [ ] T047 [P] [US2] `backend/tests/integration/test_fx_gate.py` — 외환 커버리지가 필요한 구간(시작일 ~ 어제)을 덮지 않으면 202에 `fx.state: queued`가 실리고 **003의 `StartQueue.request`가 불리는지**, **001의 `ensure_background_job`이 불리지 않는지**(spy). 같은 통화가 진행 중이면 새로 시작하지 않고 `collecting`인지. 다른 통화가 진행 중이면 `waiting`·`busyWith`인지. 커버리지가 중간에 멈춰 있으면(시작일은 덮고 끝은 못 덮음) 수집하는지. 주식·환율이 둘 다 비면 둘 다 실리고 결과가 없는지. **필요한 날짜가 `currency.first_available_date` 이전이면 `409 fx_not_available_before`·`reason: before_first_quote`, 탐색 시작일(`probe_start`) 이전이면 `reason: before_probe_start`인지, 두 경우 모두 수집을 요청하지 않고 다시 요청해도 반복되지 않는지, 메시지가 섞이지 않는지.** 수집이 실패해도 값을 메우지 않는지 (FR-043, FR-043a, FR-044, FR-045, FR-046, FR-047, SC-010)
- [ ] T091 [P] [US2] `backend/tests/integration/test_fx_background_job.py` — **고치기 전에 결함을 재현한다**: 외환 차트의 202 뒤 워커가 그 작업을 실행하지 않고 점유만 남는지. 고친 뒤에는 `ensure_background_job`이 시작 큐에 요청을 넣고 점유는 워커가 잡는지, 같은 통화가 진행 중이면 그 작업 ID를 돌려주는지, 외환 차트의 202 뒤 워커가 실제로 수집하는지(스텁 출처), 고아 점유가 남지 않는지, **외환 화면이 먼저 띄운 수집을 시뮬레이션의 환율 판정이 따라가는지.** 기존 외환 테스트가 "함수가 점유를 잡는다"를 단정하면 함께 고친다 (FR-046, FR-046a, research R6-10)
- [ ] T048 [P] [US2] `frontend/tests/CollectingNoticeFx.test.tsx` — 환율 줄이 `queued`·`collecting`·`waiting`에 맞는 문구를 보이는지, `waiting`이면 003 수집 스트림을 구독하고 그 수집이 끝나면 **화면이** 시뮬레이션을 다시 요청하는지, 둘 다 끝나기 전에는 결과를 그리지 않는지, `fx_not_available_before`이면 W4a와 "그 달로 옮기기"가 보이는지 (FR-043, FR-043a, FR-045, FR-046)

### Implementation for User Story 2

- [ ] T049 [US2] `backend/src/simulation/fx_convert.py`에 `per_unit`을 더한다. `Decimal`, 소수 6자리 (FR-042)
- [ ] T050 [US2] `backend/src/api/services/stock_fx.py`의 `load_rates`가 행의 `quote_unit`으로 나눈 1단위당 값을 만들게 한다 (FR-042, research R6-9)
- [ ] T051 [US2] `backend/src/api/services/stock_collect.py`에 환율 판정을 더한다 — 001 커버리지로 필요한 구간을 보고, 003 `StartQueue`로 요청하고, 다른 통화 처리 중이면 `waiting`, 최초 고시일 이전이면 수집하지 않는다 (FR-043, FR-043a, FR-044, FR-045, FR-046, FR-047, research R6-10)
- [ ] T052 [US2] `backend/src/api/routes/stock_simulation.py`·`stock_series.py`의 202 본문에 `fx`를 싣고, `main.py`에 `fx_not_available_before`(409) 처리기를 더한다 (FR-043a, FR-045, contracts/rest-api 5·6절)
- [ ] T053 [US2] `frontend/src/lib/types.ts`에 202 `fx`와 `fx_not_available_before` 본문 타입을 더한다
- [ ] T054 [US2] `frontend/src/stores/stockStore.ts` — `fx.state: waiting`이면 003 수집 스트림(`lib/collectionStream.ts`)을 구독하고 끝나면 다시 요청한다. 화면을 떠나면 구독을 끊는다 (FR-046, research R6-10)
- [ ] T055 [US2] `frontend/src/components/stock/CollectingNotice.tsx`에 환율 줄(W4)과 W4a를 더한다. W4a는 `reason`에 따라 두 문구를 나눈다 (FR-043a, FR-045, FR-046, ui-wireframes W4, W4a)
- [ ] T092 [US2] `backend/src/api/services/collection_gate.py`의 `ensure_background_job`이 점유를 직접 잡지 않고 003의 `StartQueue`로 요청을 넘기게 한다. 같은 통화가 진행 중이면 점유 테이블에서 작업 ID를 읽어 돌려준다. 외환 화면의 자동 수집 경로(`routes/series.py`·`daily.py`·`rates.py`·`latest.py`)의 응답 모양은 바꾸지 않는다 (FR-046a, research R6-10)

**Checkpoint**: 엔화 종목이 원화로 올바르게 계산되고, 환율이 없으면 받아 온다

---

## Phase 5: User Story 3 - 시작일을 기본값에서 월·년 단위로 옮긴다 (Priority: P2)

**Goal**: 기본 2020-01-01, 월·년 이동, 시작 가능 날짜를 실행 전에 알린다.

**Independent Test**: 화면을 열어 기본값을 보고 quickstart 13의 표대로 옮겨 본다. 기본값 그대로 실행해
거절되지 않는지 본다(quickstart 14).

### Tests for User Story 3 ⚠️

- [ ] T056 [P] [US3] `frontend/tests/startDate.test.ts` — 한 달·1년 앞뒤 이동을 표로 검증한다: 2020-01-31 + 1개월 = 2020-02-29, 2020-02-29 + 1년 = 2021-02-28, 2020-03-31 − 1개월 = 2020-02-29, 맞춰진 날짜에서 다시 이동하면 맞춰진 날짜에서 출발하는지, 어제가 속한 달을 넘지 못하는지. **`startDate.ts`에 `setMonth`·`setFullYear`가 없는지**(정적 검사) (FR-002, FR-003, FR-004, SC-012, research R6-7)
- [ ] T057 [P] [US3] `frontend/tests/StartDateInput.test.tsx` — 처음 값이 2020-01-01인지, 버튼이 "1년 전"·"한 달 전"으로 읽히는지, 경계에서 버튼이 비활성인지, 미래 날짜 입력에 사유가 보이고 실행이 막히는지, **시작일이 `listedOn`보다 이르면 W1a가 보이고 "그 달로 옮기기"를 눌러야만 바뀌는지** (FR-001, FR-002, FR-004, FR-005)
- [ ] T058 [P] [US3] `frontend/tests/stockStoreStartDate.test.ts` — 종목을 바꿔도 시작일이 그대로인지, `before_listing`(`basis: price_start`)의 `startableFrom`이 W1a와 같은 모양으로 보이는지 (FR-005a, FR-006)
- [ ] T059 [P] [US3] `backend/tests/integration/test_start_available.py` — **검색 → 등록 → 실행** 경로로 검증한다. 시작일이 목록의 상장일보다 이르면 **시세를 받지 않고**(수집 작업 미생성) `400 before_listing`·`basis: listing`인지. 수집 범위가 시작일을 덮는데 시작 월에 일봉이 없으면 `basis: price_start`·`startableFrom`인지. **시작일이 휴일(2020-01-01)이고 `first_available_date`가 비어 있어도 거절하지 않는지**(005 실제 경로 결함). 첫 매수가 시작 월 밖으로 **몰래 밀리지 않는지**. 목록의 상장일이 `stock.first_available_date`에 복사되지 않는지 (FR-005, FR-005a, SC-013, SC-013a, research R6-8, R6-17)

### Implementation for User Story 3

- [ ] T060 [US3] `frontend/src/lib/startDate.ts` — 정수 날짜 산술, 그 달 말일로 맞춤, 어제 경계 (FR-002, FR-003, FR-004)
- [ ] T061 [US3] `frontend/src/components/stock/StartDateInput.tsx` — W1·W1a (FR-001, FR-002, FR-004, FR-005, ui-wireframes W1, W1a)
- [ ] T062 [US3] `frontend/src/components/stock/SimulationForm.tsx`가 `StartDateInput`을 쓰게 하고, `stockStore`의 시작일 초기값을 2020-01-01로, 종목 변경이 시작일을 건드리지 않게 한다 (FR-001, FR-006)
- [ ] T063 [US3] `backend/src/api/services/stock_simulation.py` — 시작 가능 날짜를 두 단계로 판정한다: 수집 전에는 목록 상장일을 하한으로, 수집 후에는 시작 월의 실제 일봉으로. `run_simulation`이 메타데이터(`listed_on`)를 실제 일봉보다 먼저 믿지 않게 바꾼다 (FR-005, FR-005a, research R6-8)
- [ ] T064 [US3] `backend/src/api/main.py`의 `before_listing` 처리기가 `startableFrom`·`basis`를 싣게 하고, `frontend/src/lib/types.ts`에 본문 타입을 더한다 (FR-005, FR-005a, contracts/rest-api 2절)

**Checkpoint**: 시작일이 기본값에서 출발하고, 기본값 그대로 실행해도 거절되지 않는다

---

## Phase 6: User Story 4 - 미국 종목을 한글·영문·티커로 찾는다 (Priority: P2)

**Goal**: 미국 3개 거래소 목록을 받아 한글·초성·영문·티커로 찾는다.

**Independent Test**: 미국 목록을 받아 둔 상태에서 애플을 네 방식으로 찾고, 클래스 주식·NYSE Arca ETF로
시뮬레이션한다(quickstart 5, 12).

**의존**: US1의 검색 핵심(T030~T038)을 쓴다.

### Tests for User Story 4 ⚠️

- [ ] T065 [P] [US4] `backend/tests/contract/test_kiwoom_us.py` — T005의 실제 응답 픽스처로 미국 목록을 파싱한다. `stk_nm`이 한글 종목명, `stk_enm`이 영문 종목명, `isEtf` → `kind`, `stex_tp` → 단위인지. 여러 쪽이 이어지는지. **한도 초과(`1700`) 픽스처에서 `rate_limit` 실패로 끝나고 받은 쪽까지로 교체하지 않는지** (FR-011, FR-018, research R6-2)
- [ ] T066 [P] [US4] `backend/tests/unit/test_price_symbol.py`에 미국을 더한다 — 거래소 → 005 시장, 통화 USD, **T005에서 확정한 클래스 주식 표기 변환**, 규칙으로 못 옮기는 기호는 그대로 보내는지 (FR-031, SC-008, research R6-6)
- [ ] T067 [P] [US4] `backend/tests/unit/test_search_match.py`에 미국 표를 더한다 — 애플·ㅇㅍ·apple·AAPL, 테슬라·엔비디아, 한글명이 비어 있는 종목이 영문명·티커로만 찾히는지 (FR-021, SC-002)
- [ ] T068 [P] [US4] `backend/tests/integration/test_listing_us_pacing.py` — 미국 단위의 쪽 사이 간격이 설정(기본 12초)을 지키는지(가짜 시계), 목록이 한 번도 없을 때 검색이 "결과 없음"이 아니라 `never`/`refreshing`으로 답하는지, 국내 단위가 미국 단위를 기다리지 않는지 (FR-015, FR-017, FR-028, FR-063)
- [ ] T069 [P] [US4] `backend/tests/integration/test_stock_selection_us.py` — **같은 티커의 미국 종목이 거래소가 달라도 하나로 쓰이는지**(005가 `AMEX`로 저장한 ETF를 목록이 `NYSE`로 줄 때), 없으면 목록의 거래소로 만드는지 (FR-030, FR-030a, SC-007)

### Implementation for User Story 4

- [ ] T070 [US4] `backend/src/ingestion/kiwoom/parse.py`에 미국 목록 파싱을 더한다 (FR-011)
- [ ] T071 [US4] `backend/src/search/price_symbol.py`에 미국 규칙을 더한다 (FR-031)
- [ ] T072 [US4] `backend/src/api/services/listing_refresh.py`에 `NYSE`·`NASDAQ`·`AMEX` 단위와 미국 쪽 사이 간격을 더한다 (FR-011, FR-015, FR-063)
- [ ] T073 [US4] `backend/src/api/services/stock_selection.py` — 미국은 **티커로 기존 종목을 먼저 찾는다** (FR-030a)
- [ ] T074 [US4] `backend/src/api/services/listing_index.py`에 미국 일치 필드(한글명·영문명·티커)를 더한다 (FR-021)
- [ ] T075 [US4] `frontend/src/components/stock/StockSearch.tsx`가 미국 결과에 영문 종목명을 함께 보이게 한다 (FR-025)

**Checkpoint**: 미국 종목을 한글·초성·영문·티커로 찾는다

---

## Phase 7: User Story 5 - 원금 통화는 원화 또는 종목 통화만 고른다 (Priority: P3)

**Goal**: 교차 통화 조합을 모든 경로에서 막고, 화면이 통화를 몰래 바꾸지 않는다.

**Independent Test**: 원금 USD·국내 종목, 원금 EUR·미국 종목으로 실행을 시도해 둘 다 막히는지
확인한다(quickstart 20).

### Tests for User Story 5 ⚠️

- [ ] T076 [P] [US5] `backend/tests/integration/test_principal_currency_pair.py` — 국내 종목 + USD, 미국 종목 + EUR, 미국 종목 + JPY가 표·차트 **둘 다** `400 currency_pair_not_allowed`·`allowed`인지, **어떤 계산도 일어나지 않는지**(시세 수집 작업 미생성), `EUR`이 원금 통화로 더 이상 받아들여지지 않는지, 미국 종목 + USD는 환전 없이 계산되는지 (FR-050, FR-050a, FR-050d, FR-051, FR-052, SC-011)
- [ ] T077 [P] [US5] `frontend/tests/SimulationFormCurrency.test.tsx` — 선택지가 `{KRW, 종목 통화}`이고 EUR이 없는지, **USD로 미국 종목을 보다가 국내 종목으로 바꾸면 통화 값이 그대로 남고 "다시 고르세요"가 보이며 실행이 막히는지** (FR-050b, FR-050d, SC-011a)
- [ ] T078 [P] [US5] `frontend/tests/SimulationHistoryBlocked.test.tsx` — 005 시절 이력의 막힌 조합 항목이 **지워지지 않고** 남는지, 다시 실행·비교에 고르면 거절 사유가 보이는지, 비교에서 조용히 빠지지 않는지 (FR-050c)

### Implementation for User Story 5

- [ ] T079 [US5] `backend/src/api/services/stock_simulation.py` — `check_principal_currency(code, stock_currency)`가 `{KRW, 종목 통화}`만 받게 하고 원금 통화 목록에서 EUR을 뺀다. 표·차트·이력 재실행이 모두 이 함수를 지나게 한다. `main.py`에 처리기를 더한다 (FR-050, FR-050a, FR-050d, FR-051, research R6-11)
- [ ] T080 [US5] `frontend/src/components/stock/SimulationForm.tsx`·`frontend/src/stores/stockStore.ts` — 종목에 따라 선택지를 정하고, 허용되지 않게 되면 값을 바꾸지 않고 막는다 (FR-050b, FR-050d, ui-wireframes W3)
- [ ] T081 [US5] `frontend/src/components/stock/SimulationHistory.tsx`·`stockStore.ts` — 막힌 이력 항목을 사유와 함께 표시한다 (FR-050c)

**Checkpoint**: 다섯 스토리가 모두 독립적으로 동작한다

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T082 [P] `backend/tests/unit/test_no_float.py`에 검사를 더한다 — `src/search/`, `ingestion/kiwoom/`, `api/services/listing_*.py`, `api/services/stock_collect.py`에 `float(` 사용이 없는지 (헌법 원칙 VI)
- [ ] T083 [P] `backend/tests/unit/test_no_interpolation.py`에 검사를 더한다 — 목록 교체와 환율 판정 경로에 값을 채우는 코드가 없는지. 빠진 종목·환율이 없는 구간을 값으로 메우지 않는다. 또 **`repository/stock_listing.py`에 `delete(`가 없는지** — 종목과 원본을 지우는 경로가 생기면 헌법 원칙 V(원본 보존)와 FR-019가 함께 깨진다 (FR-019, FR-043a, FR-047, FR-061, 헌법 원칙 V)
- [ ] T084 `README.md` — 현재 상태 표에 006을 더하고, 데이터 출처에 키움(검색용 목록, 공식 API)과 **이용 조건**(계좌·HTS ID·사용 등록, 약관 원문은 사용자 확인)을 적고, "가상자산은 006"을 "다음 자산군 기능(번호 미정)"으로 고친다 (FR-064, FR-070, research R6-15, R6-16)
- [ ] T085 `CLAUDE.md` — 현재 상태 표에 006을 더하고, "가상자산은 006" 문구를 고치고, 키움 인증 정보 설정과 목록 갱신 워커(`lifespan`의 네 번째 태스크)를 운영 메모에 적는다. 005 `plan.md`는 고치지 않는다 (FR-070)
- [ ] T086 `backend/`에서 mypy strict(`src`)와 ruff(`src`·`tests`)를 통과시킨다
- [ ] T087 `frontend/`에서 `npx tsc --noEmit`과 `npx eslint .`를 통과시킨다. `any` 금지
- [ ] T088 `backend/`에서 커버리지 80% 이상을 확인한다 — `cd backend && .venv/bin/python -m pytest -q --cov=src`
- [ ] T089 `backend/tests/`와 `frontend/tests/` 전체가 **네트워크 차단 상태에서** 통과하는지 확인한다. 005가 더한 소켓 가드가 키움 호출도 막는지 본다 (헌법 원칙 III)
- [ ] T090 `quickstart.md`의 시나리오 22개를 순서대로 수동 실행하고 결과를 기록한다. 시나리오 1은 인증 정보를 넣기 전에 해야 한다. 시나리오 2의 측정값으로 research R6-2를 채운다. **실제 출처를 부르므로 미국 목록은 분당 제한을 지킨다.** 시나리오마다 검증하는 FR·SC는 quickstart에 적혀 있다 — 범위 표기로 묶지 않는다(004의 교훈: 범위 표기는 검색에 걸리지 않는다)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음. **T005는 키움 키가 필요하다** — 없으면 US1의 계약 테스트(T017)가 막힌다
- **Foundational (Phase 2)**: Setup 완료 후 — 모든 사용자 스토리를 차단
- **US1 (Phase 3)**: Foundational 완료 후. **MVP**
- **US2 (Phase 4)**: Foundational 완료 후. US1과 독립(검색 없이 기존 종목으로 검증)
- **US3 (Phase 5)**: Foundational 완료 후. 서버 판정(T059·T063)은 US1의 저장소(T034)와 종목 등록(T039)을 쓴다 — T059가 검색 → 등록 → 실행 경로를 탄다
- **US4 (Phase 6)**: **US1 완료 후**. 검색 핵심을 재사용한다
- **US5 (Phase 7)**: Foundational 완료 후. 다른 스토리와 독립
- **Polish (Phase 8)**: 원하는 스토리가 모두 끝난 뒤

### 스토리 간 의존

```
Setup → Foundational ─┬→ US1 (MVP) ──→ US4 (미국)
                      ├→ US2 (환전)
                      ├→ US3 (시작일) ⇢ US1의 T034·T039 사용
                      └→ US5 (원금 통화)
```

### Within Each User Story

- 테스트를 먼저 쓰고 **실패를 확인한 뒤** 구현한다 (헌법 원칙 III)
- 순수 함수 → 어댑터 → 저장소 → 서비스 → 라우트 → 화면 순
- **US1·US3의 통합 테스트는 `stock` 행을 픽스처로 미리 넣지 않는다** — 005의 결함이 다시 가려진다

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T036, T039, T040, T052, T064, T079 |
| `backend/src/api/services/stock_simulation.py` | T039, T063, T079 |
| `backend/src/api/services/listing_refresh.py` | T035, T072 |
| `backend/src/api/services/listing_index.py` | T037, T074 |
| `backend/src/api/services/stock_selection.py` | T039, T073 |
| `backend/src/api/services/collection_gate.py` | T092 |
| `backend/src/search/price_symbol.py` | T032, T071 |
| `backend/src/ingestion/kiwoom/parse.py` | T033, T070 |
| `backend/tests/unit/test_price_symbol.py` | T016, T066 |
| `backend/tests/unit/test_search_match.py` | T014, T067 |
| `frontend/src/stores/stockStore.ts` | T044, T054, T062, T080, T081 |
| `frontend/src/components/stock/StockSearch.tsx` | T043, T075 |
| `frontend/src/components/stock/SimulationForm.tsx` | T062, T080 |
| `frontend/src/lib/types.ts` | T041, T053, T064 |

### Parallel Opportunities

- Setup: T001·T003·T004 동시
- Foundational: T006·T009·T011·T012 동시(테스트), 이어 T007→T008, T010
- US1 테스트 T013~T029는 서로 다른 파일이라 모두 동시에 쓸 수 있다
- US2·US3·US5는 Foundational 뒤 US1과 동시에 진행할 수 있다

## Parallel Example: User Story 1

```bash
# 테스트를 함께 쓴다 (모두 실패해야 한다):
backend/tests/unit/test_search_hangul.py         # T013
backend/tests/unit/test_search_match.py          # T014
backend/tests/unit/test_price_symbol.py          # T016
backend/tests/contract/test_kiwoom_domestic.py   # T017
backend/tests/integration/test_listing_replace.py  # T019
frontend/tests/StockSearchLocal.test.tsx         # T027

# 순수 함수부터 구현한다:
backend/src/search/hangul.py → match.py → price_symbol.py   # T030~T032
```

## Implementation Strategy

### MVP First (User Story 1)

1. Setup — **T005의 픽스처 캡처를 먼저 끝낸다**
2. Foundational
3. US1 → quickstart 3·10으로 확인 → **여기서 멈추고 검증**. 005에서 실제로 안 되던 "검색 → 시뮬레이션"이
   이 시점에 처음 된다

### Incremental Delivery

1. US1 — 국내 검색과 종목 등록 (MVP)
2. US2 — 엔화 단위와 환율 수집. 틀린 숫자를 막는 일이라 US1 다음이다
3. US3 — 시작일. 기본값 휴일 거절이 여기서 닫힌다
4. US4 — 미국 검색
5. US5 — 원금 통화 제한

각 스토리는 앞 스토리를 깨지 않고 더해진다.

## Notes

- **함께 고치는 001 결함**: `ensure_background_job`은 작업과 점유만 만들고 워커에 넘기지 않았다
  (research R6-10). 외환 화면의 자동 수집이 실제로 돌지 않았고, 남긴 점유가 006의 환율 수집을 막는다.
  T091·T092가 고친다 — 외환 화면의 동작도 바뀐다(이제 실제로 수집한다)
- 커밋은 페이즈마다 한다
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
