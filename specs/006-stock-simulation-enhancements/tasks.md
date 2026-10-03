---

description: "Task list for 006-stock-simulation-enhancements"
---

# Tasks: 주식 시뮬레이션 개선 — 시작일·종목 검색·환전

**Input**: Design documents from `/specs/006-stock-simulation-enhancements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를
지킨다. **테스트를 구현보다 먼저 커밋한다** — 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes).
구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다.

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
  그 함수가 큐로 넘기도록 **함께 고치고**, 006의 환율 판정도 **그 함수를 거친다**(T091·T092·T093, FR-046a) —
  외환 화면이 남긴 점유가 006의 수집을 막기 때문이다 (research R6-10, analyze H2)
- **원본 응답은 지우지 않는다**: 보존 기간을 두면 헌법 원칙 V 위반이다. 같은 본문은 한 번만 저장한다
  (research R6-13, analyze C1)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 설정과 계약 테스트 픽스처를 갖춘다

- [X] T001 [P] `backend/tests/unit/test_settings_kiwoom.py` — data-model 7절의 키 10개가 기본값대로 읽히는지, `LISTING_SHRINK_THRESHOLD`가 `Decimal`인지, `KIWOOM_MODE`가 `real`·`mock` 밖이면 기동을 거절하는지, **앱 키·시크릿이 설정 객체의 `repr`·`str`에 드러나지 않는지** 검증한다 (FR-060, FR-063)
- [X] T002 `backend/src/config/settings.py`에 키움·목록 설정을 더한다. 키·시크릿은 ECOS 키와 같은 비밀 감싸개(`reveal()`)로 둔다 (FR-060, FR-063, data-model 7절)
- [X] T003 [P] `.env.example`에 data-model 7절의 키 이름을 **값 없이** 더한다 (FR-060)
- [X] T004 [P] `backend/scripts/capture_kiwoom_fixtures.py`를 만든다 — 실제 응답을 받아 `backend/tests/contract/fixtures/kiwoom/`에 쪽마다 저장한다. **토큰 발급 응답과 요청·응답 헤더를 저장하지 않는다.** 연속조회 여부만 파일 이름에 남긴다. 테스트 스위트에서 실행되지 않는다 (FR-061, research R6-2)
- [X] T005 T004를 **한 번 실행**해 픽스처를 만든다(키움 키 필요, 실제 출처 호출). **실측(2026-10-02): 단위마다 한 쪽에 전부 온다. KOSPI 목록에 ETF·리츠·ETN이 함께 와서 단위를 7개 → 5개로 줄였다(research R6-2). 미국 티커 표기 다섯 갈래를 시세 출처에서 확인했다(R6-6).** 처음 지시: 국내 4단위·미국 3단위의 첫 쪽과 다음 쪽, **클래스 주식이 들어 있는 미국 쪽**을 받는다. 쪽당 건수·쪽 수를 `research.md` R6-2 "확인하지 못한 것"에 기록하고, 클래스 주식 표기를 R6-6에 기록한다. 실패 응답 픽스처(인증 실패 `8001`, 한도 `1700`, HTTP 200 + `return_code≠0`, 중간 쪽 실패, **이전의 40% 길이 목록**과 경계 검증용 **정확히 50% 길이 목록**)는 실제 응답의 모양을 본떠 손으로 만든다. **저장소가 비공개라 응답 전체를 픽스처로 커밋한다** — 저장소를 공개로 바꾸기 전에 검증에 필요한 행으로 줄인다 (SC-008, research R6-2, R6-6, R6-15)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 신규 테이블, 키움 어댑터의 공통 부분, 헌법 정적 검사

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 어떤 스토리도 시작하지 않는다

- [X] T006 [P] `backend/tests/unit/test_orm_types.py`에 검사를 더한다 — 신규 5개 테이블이 정의되는지, `stock_listing`이 **`UNIQUE (country, code)`**이고 `unit`이 키가 아닌지, `status` 기본값이 `listed`인지, `name_ko`·`name_en`·`listed_on`이 NULL 허용인지, **가격·상장주식수 컬럼이 없는지**(FR-012), `stock_listing_refresh`·`stock_listing_lock`의 PK가 `unit`인지, **`stock_listing_raw_body`의 PK가 `sha256` CHAR(64)이고 `body`가 MEDIUMTEXT인지, `stock_listing_raw.body_sha256`이 그것을 가리키고 `stock_listing_raw`에 본문 컬럼이 없는지**, **`stock` 테이블의 컬럼이 005와 같은지** (FR-012, FR-019a, FR-061, data-model 1~4a절)
- [X] T007 `backend/src/db/models.py`에 `StockListing`·`StockListingRefresh`·`StockListingLock`·`StockListingRaw`·`StockListingRawBody`를 더한다. 컬럼·타입·제약은 data-model 1~4a절을 그대로 따른다 — `code` VARCHAR(16) NOT NULL, `unit` VARCHAR(8) NOT NULL, `name_ko` VARCHAR(128) NULL, `name_en` VARCHAR(256) NULL, `kind` VARCHAR(8) NOT NULL(`stock`|`etf`|`reit`), `status` VARCHAR(8) NOT NULL 기본 `listed`(`listed`|`missing`), `last_error` VARCHAR(512) NULL, `stock_listing_raw_body.sha256` CHAR(64) PK, `stock_listing_raw.body_sha256` CHAR(64) NOT NULL FK, 인덱스 `(unit, status)` (FR-015, FR-019, FR-019a, FR-061)
- [X] T008 `backend/src/db/migrations/versions/`에 마이그레이션 1개를 더하고 `backend/tests/integration/test_migrations.py`가 올림·내림을 모두 지나는지 확인한다 (헌법 DB 운영 규약)
- [X] T009 [P] `backend/tests/contract/test_kiwoom_client.py` — 토큰을 **메모리에만** 두고 만료 10분 전에 갱신하는지, 연속조회가 **응답 헤더**의 `cont-yn`·`next-key`로 이어지는지, **HTTP 200 + `return_code≠0`을 실패로 판정하는지**, **세부 코드를 `return_msg`의 `[NNNN:…]`에서 뽑아 판정하는지**(실제 오류 응답은 `return_code: 3`이고 세부 코드는 메시지 안에만 있다 — 픽스처 `error_auth_token.json`·`error_invalid_token.json`), 오류 코드를 `auth`(8001·8002·8011·8012·8003·8005·8006·8009·8015·8016·8030·8031, HTTP 401)·`rate_limit`(1700~1702)·`network`(연결 실패·시간 초과·5xx)·`invalid`로 나누는지, `KIWOOM_MODE`에 따라 도메인이 바뀌는지 검증한다. aiohttp를 가짜 응답으로 바꿔 끼운다 (FR-013b, FR-060, FR-061, research R6-1, R6-3)
- [X] T010 `backend/src/ingestion/kiwoom/errors.py`·`client.py`를 만든다. 공식 클라이언트를 쓰지 않는다. 토큰을 DB·파일·로그에 쓰지 않는다 (FR-060, FR-061, research R6-1)
- [X] T011 [P] `backend/tests/unit/test_layer_boundaries.py`에 검사를 더한다 — 키움 응답 필드명(`stk_cd`·`stk_nm`·`stk_enm`·`stex_tp`·`mrkt_tp`·`regDay`·`listCount`·`lastPrice`)이 `ingestion/kiwoom/` 밖에 없는지, **`src/search/`가 존재하고** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는지. 패키지가 없으면 통과하지 않고 실패해야 한다 — 없는 모듈을 검사하면 조용히 통과한다 (헌법 원칙 II·IV)
- [X] T012 [P] `backend/tests/unit/test_no_secret_in_events.py`에 검사를 더한다 — 키움 앱 키·시크릿·토큰 문자열이 수집 사건, `stock_listing_raw_body.body`, `stock_listing_refresh.last_error`에 남지 않는지. 이 페이즈에서는 클라이언트·오류 메시지·사건 마스킹을 검사하고, **저장 계층(원본 본문·갱신 기록 사유)의 검사는 T019·T024가 맡는다** — 저장소가 US1에서 생긴다 (FR-060, FR-061, SC-014)

**Checkpoint**: 테이블과 어댑터 공통 부분이 준비됐다

---

## Phase 3: User Story 1 - 국내 종목을 한글·초성으로 바로 찾는다 (Priority: P1) 🎯 MVP

**Goal**: 국내 목록을 받아 두고, 한글·초성·혼용·코드로 바로 찾고, 고른 종목으로 시뮬레이션까지 간다.

**Independent Test**: 국내 목록을 받아 둔 상태에서 quickstart 3의 표로 검색하고, 고른 종목으로 실행해
"알 수 없는 종목"이 나오지 않는지 확인한다. 미국 목록·환전·시작일 없이 검증한다.

### Tests for User Story 1 ⚠️

- [X] T013 [P] [US1] `backend/tests/unit/test_search_hangul.py` — NFC 정규화, 공백 제거, 라틴 소문자화, 음절 → 초성 열, **쌍자음(ㅆ)과 홑자음(ㅅ)의 구별**, **받침 대기 판정**("서"는 마지막 글자일 때 "성"과 맞고, 마지막이 아니면 맞지 않음)을 표로 검증한다 (FR-022, research R6-5)
- [X] T014 [P] [US1] `backend/tests/unit/test_search_match.py` — quickstart 3의 표를 그대로 옮긴다(삼성전자, ㅅㅅㅈㅈ, 삼ㅅㅈ, 삼성ㅈ, 삼서, 삼성 전자, 005930, sk하이닉스, ㅎㅇㄴㅅ, kodex 200, ㅆ). 순위가 정확 → 앞부분 → 포함인지, 같은 순위 안에서 **일치한 이름이 짧은 순 → 코드 포인트 순 → 시장 → 코드**인지, **입력 순서를 섞어도 결과 순서가 같은지**, 상한을 넘으면 잘림을 알리는지 검증한다 (FR-020, FR-022, FR-023, FR-024, SC-002, SC-003)
- [X] T015 [P] [US1] `backend/tests/unit/test_search_performance.py` — 합성 종목 15,000건 색인에서 대표 검색어 100개의 처리 시간 95번째 백분위가 50ms 미만인지 검증한다. SC-001의 0.5초는 화면 입력 대기 150ms를 포함한다 (SC-001, research R6-5)
- [X] T016 [P] [US1] `backend/tests/unit/test_price_symbol.py` — 국내: `KOSPI`(주식·ETF·리츠) → `KRX`/`{code}.KS`/KRW, `KOSDAQ` → `KRX`/`{code}.KQ`/KRW. **ETF·리츠를 상품 구분으로 시장을 정하지 않는지**(FR-010a). **역변환**: `KRX`/`{code}.KS`·`.KQ` → 국내 종목코드, 그리고 **목록 → 시세 식별자 → 목록이 같은 종목으로 돌아오는지**(왕복) (FR-010a, FR-030, FR-030b, FR-031, research R6-6 역변환)
- [X] T017 [P] [US1] `backend/tests/contract/test_kiwoom_domestic.py` — T005의 실제 응답 픽스처로 국내 목록을 파싱한다. 0으로 앞을 채운 문자열, `regDay` → 날짜, **`marketName`으로 `kind`(`stock`·`etf`·`reit`)를 정하고 ETN·인프라투자금융·뮤추얼펀드를 빼는지, 처음 보는 `marketName`이면 단위 전체가 `invalid`인지**(research R6-2), 영문이 섞인 6자리 코드(`0030R0`)를 받아들이는지. **`code`가 비었거나 6자리가 아닌 행이 하나라도 있으면 단위 전체를 `invalid`로 실패시키는지** — 한 행을 조용히 버리면 그 종목만 "빠짐"이 된다. 목록의 `lastPrice`·`listCount`를 결과 타입에 싣지 않는지 (FR-010, FR-012, data-model 1절 검증 규칙)
- [X] T018 [P] [US1] `backend/tests/unit/test_listing_refresh_decision.py` — 갱신 판정 순수 함수를 표로 검증한다: 오늘(KST) 이미 받음 → 안 함, 갱신 중 → 안 함, 인증 실패 막힘 → 안 함, 마지막 실패 후 30분 미만 → 안 함, 오늘 5회 도달 → 안 함, 그 밖 → 함. **자정(KST) 직후에 새 날로 넘어가는지**, UTC 날짜로 판정하지 않는지 (FR-013, FR-013a, FR-013b, SC-005a, research R6-3)
- [X] T019 [P] [US1] `backend/tests/integration/test_listing_replace.py` — 교체 트랜잭션: **중간 쪽 실패면 아무것도 바뀌지 않는지**(FR-018), **이전 건수의 50%보다 적으면 교체하지 않고 `invalid`로 남기는지, 정확히 50%면 교체하는지**(FR-018a), 빠진 종목을 지우지 않고 `missing`으로 표시하는지(FR-019, SC-016), 다시 보이면 `listed`로 돌아오는지, **코스닥 → 코스피로 단위를 옮긴 종목이 행 하나로 남고 어느 단위가 먼저 갱신돼도 결과가 같은지**(FR-019a), 단위마다 기준 시각이 따로인지(FR-015), 실패해도 이전 목록이 그대로인지(FR-016, SC-004), 원본이 **헤더 없이** 쪽마다 남고 **지워지지 않는지**, 같은 본문을 다시 받으면 본문은 한 번만 저장되고 쪽 기록은 남는지(FR-061, research R6-13)
- [X] T020 [P] [US1] `backend/tests/integration/test_listing_lock.py` — 같은 단위의 갱신을 동시에 둘 요청하면 **기본 키 충돌로 하나만** 시작하는지, 기동 시 남은 점유를 풀고 심장박동이 10분 넘게 멈춘 점유를 회수하는지 (FR-014, SC-005, data-model 3절)
- [X] T021 [P] [US1] `backend/tests/integration/test_stock_search_local.py` — `GET /api/stocks/search`가 **외부 출처를 부르지 않는지**, 결과 필드(contracts/rest-api)가 맞는지, `lists[]`의 상태(`never`·`refreshing`·`ready`·`stale`·`failed`·`auth_blocked`)와 `reason`·`action`이 맞는지, **목록이 없을 때 오류가 아니라 200 + `lists`로 알리는지**, 갱신 중에도 **기다리지 않고** 이전 목록으로 답하는지, 상한을 넘으면 `truncated`인지, 갱신을 요청만 하는지 (FR-017, FR-024, FR-025, FR-028, FR-028a, FR-029, SC-006)
- [X] T022 [P] [US1] `backend/tests/integration/test_stock_search_external.py` — `GET /api/stocks/search/external`가 결과에서 **TSE만 남기는지**(국내·미국 제외), 출처 장애를 005와 같은 오류로 내는지 (FR-026)
- [X] T023 [P] [US1] `backend/tests/integration/test_stock_selection.py` — **검색 → 등록 → 실행** 경로로 검증한다(픽스처가 `stock` 행을 미리 넣지 않는다). `POST /api/stocks/selection`이 국내 목록 행으로 종목을 만들고, 005가 이미 저장한 같은 종목이 있으면 그것을 쓰고, 두 번 불러도 행이 하나인지. 일본 외부 결과로 등록할 때 시장이 TSE·통화가 JPY가 아니면 거절하는지. 없는 `listingId`는 `404 unknown_listing`. **미등록 국내 종목으로 시뮬레이션을 요청하면 목록으로 등록한 뒤 진행하는지**(이력 재실행 경로). **시작일은 거래일(예: 2021-08-02)로 잡는다** — T063 전에는 휴일 시작이 005 결함으로 거절된다. 이를 피하려고 픽스처에 `first_available_date`를 넣지 않는다 — 결함이 다시 가려진다 (FR-030, FR-030b, FR-033, SC-007, SC-007a, research R6-17)
- [X] T024 [P] [US1] `backend/tests/integration/test_listing_auth_failure.py` — 인증 실패 시 **목록 갱신만 실패**하고 이전 목록 검색·일본 검색·시뮬레이션은 정상인지, 같은 날 다시 시도하지 않는지, 막힘을 초기화(재시작 흉내)하면 같은 날이라도 다시 시도하는지, 인증 정보가 비어 있으면 갱신을 시도하지 않고 `never`·`auth_missing`·`set_credentials`인지 (FR-013b, FR-028a, FR-062)
- [X] T025 [P] [US1] `backend/tests/integration/test_simulation_errors.py`에 더한다 — 시세 출처가 심볼을 모르면 `404 price_symbol_unknown`, 받았는데 시세가 없으면 `404 no_price_data`로 **구별되는지** (FR-032)
- [X] T026 [P] [US1] `frontend/tests/searchSequence.test.ts` — 요청 번호가 최신이 아닌 응답을 버리는지. 로컬·외부가 번호를 따로 가지는지 (FR-029a, research R6-12)
- [X] T027 [P] [US1] `frontend/tests/StockSearchLocal.test.tsx` — 결과마다 시장·통화, 우선주 구별, ETF·리츠 표시, "목록에서 빠짐" 표시가 보이는지(글자로, 색만이 아님), 목록 기준 시각 줄이 보이는지, **결과가 비었을 때 `lists` 상태에 따라 "결과 없음"과 W2a의 "목록을 받지 못함 + 할 일"을 가르는지**, 잘림 안내가 보이는지 (FR-024, FR-025, FR-028, FR-028a, FR-029, SC-006)
- [X] T028 [P] [US1] `frontend/tests/StockSearchRegions.test.tsx` — 로컬 결과가 **외부 검색을 기다리지 않고** 먼저 그려지는지, 외부 검색이 지연·실패해도 로컬 영역은 영향이 없고 실패는 일본 영역에만 보이는지, 로컬 입력 대기가 150ms·외부가 300ms인지 (FR-027, SC-001, SC-015)
- [X] T029 [P] [US1] `frontend/tests/stockSelection.test.ts` — 결과를 고르는 순간 `/api/stocks/selection`을 부르는지, 실패하면 **실행 전에** 사유를 보이는지, 이후 시뮬레이션·이력이 **등록 응답의 식별**을 쓰는지 (FR-030, FR-030b)
- [X] T094 [P] [US1] `backend/tests/integration/test_listing_worker.py` — **구현 뒤 보강한 테스트다**(T036의 위험을 덮는 테스트가 목록에 없었다). 워커 루프가 큐의 단위를 실제로 갱신하는지, 한 단위가 실패해도 루프가 다음 단위를 처리하는지, 큐가 비면 출처를 부르지 않는지, `lifespan`이 워커와 기동 정리를 등록하는지 검증한다. 판정·교체 테스트는 모두 `refresh_unit`을 직접 부르므로 워커 등록이 빠져도 통과한다 (FR-013, FR-014)

### Implementation for User Story 1

- [X] T030 [US1] `backend/src/search/hangul.py` — 정규화·초성 열·받침 대기 판정 (FR-022, research R6-5)
- [X] T031 [US1] `backend/src/search/match.py` — 일치 판정, 순위, 결정적 정렬, 잘림 (FR-020, FR-023, FR-024)
- [X] T032 [US1] `backend/src/search/price_symbol.py` — 국내 규칙 (FR-010a, FR-030, FR-031, research R6-6)
- [X] T033 [US1] `backend/src/ingestion/kiwoom/parse.py` — 국내 목록 파싱과 검증. 출처 필드명은 이 파일에만 둔다 (FR-010, FR-012)
- [X] T034 [US1] `backend/src/repository/stock_listing.py` — upsert·`missing` 표시(지금 그 단위에 속한 행만)·갱신 기록·원본 저장(본문은 SHA-256으로 중복 제거, 기본 키 충돌은 "이미 있음"). **종목·원본 테이블에 삭제 질의를 두지 않는다**. 점유 INSERT·해제는 처음 여기 두었다가 T083에서 `repository/stock_listing_lock.py`로 옮겼다 — 지워야 하는 것은 점유뿐이라, 이 파일에 `delete(`가 없다는 정적 검사가 성립하게 했다(analyze I2) (FR-014, FR-015, FR-019, FR-019a, FR-061)
- [X] T035 [US1] `backend/src/api/services/listing_refresh.py` — 갱신 판정 순수 함수, 전 쪽을 받은 뒤의 검사(빈 목록·필수 필드·축소)와 한 트랜잭션 교체, 실패 종류와 사유 기록(키·토큰 없이), 인증 실패 막힘(프로세스 메모리), 갱신 사건을 수집 전용 로그에 남김 (FR-013, FR-013a, FR-013b, FR-015, FR-016, FR-018, FR-018a, FR-062, FR-065, research R6-3, R6-4, R6-14)
- [X] T036 [US1] `backend/src/worker/listing_worker.py`를 만들고 `backend/src/api/main.py`의 `lifespan`에 등록한다. 기동 시 점유를 풀고 정체 점유를 회수한다. **등록을 빠뜨리면 갱신 요청이 쌓이기만 하고 실행되지 않는다** — 003·005가 겪은 일이다 (FR-013, FR-014, data-model 3절)
- [X] T037 [US1] `backend/src/api/services/listing_index.py` — 메모리 색인. 검색마다 단위별 기준 시각을 읽어 바뀌었으면 다시 만든다. **버전은 단위별 기준 시각의 묶음이다** — 최댓값이면 같은 초에 교체된 두 단위를 구별하지 못해 뒤 단위가 다음 날까지 검색되지 않는다(구현 단계 정정) (SC-001, research R6-5)
- [X] T038 [US1] `backend/src/api/routes/stock_search.py`를 로컬 검색으로 바꾸고 `/external`(TSE만)을 분리한다. 로컬 검색은 갱신을 **요청만** 한다 (FR-017, FR-021, FR-026, FR-027, FR-028, FR-029, research R6-12)
- [X] T039 [US1] `backend/src/api/services/stock_selection.py`·`backend/src/api/routes/stock_selection.py`를 만들고 `main.py`에 등록한다. `stock_simulation.require_stock`은 국내·미국 미등록 종목을 **research R6-6의 역변환**으로 목록에서 찾아 등록하고, 역변환으로 찾지 못하거나 일본이면 `404 unknown_stock` + `action: reselect`로 답한다 (FR-030, FR-030b, FR-033, research R6-6, R6-17)
- [X] T040 [US1] `backend/src/api/main.py`의 오류 처리기를 나눈다 — 시세 출처가 심볼을 모를 때 `price_symbol_unknown`, 우리 DB에 종목이 없을 때 `unknown_stock`. 출처가 모른다는 사실은 수집 워커 안에서 드러나므로, `worker/stock_worker.py`가 작업 사유에 표지를 붙이고 `stock_collect.plan_collection`이 그 표지로 끝난 종목의 수집을 되풀이하지 않는다. 진행 스트림의 `failed`에 `status`를 싣는다 (FR-032, research R6-6, contracts/rest-api 4절)
- [X] T041 [US1] `frontend/src/lib/types.ts`에 검색 응답(`results`·`truncated`·`lists`)·외부 검색·등록 응답 타입을 더한다 (contracts/rest-api)
- [X] T042 [US1] `frontend/src/lib/searchSequence.ts` (FR-029a)
- [X] T043 [US1] `frontend/src/components/stock/StockSearch.tsx`를 두 영역(국내·미국 / 일본)으로 바꾼다. 로컬 입력 대기 150ms·외부 300ms, 목록 상태 줄, 잘림 안내, W2a (FR-024, FR-025, FR-027, FR-028, FR-028a, FR-029, ui-wireframes W2, W2a) **Phase 9에서 결과 줄과 고른 종목 표시가 `종목명(코드)`로 바뀐다(T116).**
- [X] T044 [US1] `frontend/src/stores/stockStore.ts` — 결과를 고르면 등록하고, 등록 응답의 식별을 입력·이력에 쓴다 (FR-030, FR-030b)

**Checkpoint**: 국내 종목을 한글·초성으로 찾아 시뮬레이션까지 간다

---

## Phase 4: User Story 2 - 원화로 외화 종목에 투자한 결과를 올바르게 본다 (Priority: P1)

**Goal**: 엔화 고시 단위를 반영하고, 필요한 환율이 없으면 받아 온 뒤 결과를 낸다.

**Independent Test**: 원화 원금·엔화 종목으로 첫 환전 금액이 고시 단위를 반영한 기대값인지, 환율이 없으면
수집 중으로 바뀌는지 확인한다. 검색·시작일 개선 없이 검증한다.

### Tests for User Story 2 ⚠️

- [X] T045 [P] [US2] `backend/tests/unit/test_fx_per_unit.py` — `per_unit(900.000000, 100) = 9.000000`, `per_unit(x, 1) = x`, 원금 1,000,000원·100엔당 900원·스프레드 1.75%·우대 90%의 첫 환전이 **11만 엔대**인지(1,000엔대가 아님) (FR-042, SC-009, research R6-9)
- [X] T046 [P] [US2] `backend/tests/integration/test_simulation_fx_jpy.py` — 엔화 종목·원화 원금: `exchange.rate`와 행의 `fxRate`가 **1엔당** 값인지, 첫 환전이 **실제 첫 매수일**의 환율인지(시작일이 휴일이어도), 평가 환산이 매매기준율인지 (FR-040, FR-041, FR-042, SC-009)
- [X] T047 [P] [US2] `backend/tests/integration/test_fx_gate.py` — 외환 커버리지가 필요한 구간(시작일 ~ 어제)을 덮지 않으면 202에 `fx.state: queued`가 실리고 **T092의 고쳐진 `ensure_background_job`을 거쳐 003의 `StartQueue.request`가 불리는지**, 판정이 작업 행·점유를 **직접 만들지 않는지**(spy). 외환 화면과 같은 상황에서 같은 `state`를 말하는지(analyze A1). 같은 통화가 진행 중이면 새로 시작하지 않고 `collecting`인지. 다른 통화가 진행 중이면 `waiting`·`busyWith`인지. 커버리지가 중간에 멈춰 있으면(시작일은 덮고 끝은 못 덮음) 수집하는지. 주식·환율이 둘 다 비면 둘 다 실리고 결과가 없는지. **필요한 날짜가 `currency.first_available_date` 이전이면 `409 fx_not_available_before`·`reason: before_first_quote`, 탐색 시작일(`probe_start`) 이전이면 `reason: before_probe_start`인지, 두 경우 모두 수집을 요청하지 않고 다시 요청해도 반복되지 않는지, 메시지가 섞이지 않는지. **판정 순서 경계 사례**: 탐색 시작일 2000-01-01·기록된 최초일 2000-01-04·필요한 날 1980년이면 `before_probe_start`여야 하고 `before_first_quote`가 아니어야 한다 (analyze N2).** 수집이 실패해도 값을 메우지 않는지 (FR-043, FR-043a, FR-044, FR-045, FR-046, FR-047, SC-010)
- [X] T091 [P] [US2] `backend/tests/integration/test_fx_background_job.py` — **고치기 전에 결함을 재현한다**: 외환 차트의 202 뒤 워커가 그 작업을 실행하지 않고 점유만 남는지. 고친 뒤에는 research R6-10의 **수집 표**대로 돌려주는지 — 점유가 있으면 `collecting`·작업 번호, 큐가 받으면 `queued`·`jobId: null`·통화별 스트림 주소, 다른 통화 처리 중이면 `waiting`·`busyWith`. **함수가 작업 행과 점유를 만들지 않는지, 큐가 거절했을 때 아무것도 남지 않는지**(실행되지 않는 작업이 다시 생기면 안 된다). 외환 차트의 202 뒤 워커가 실제로 수집하는지(스텁 출처), 고아 점유가 남지 않는지, **외환 화면이 먼저 띄운 수집을 시뮬레이션의 환율 판정이 따라가는지.** 기존 외환 테스트가 "함수가 점유를 잡는다"나 "202에 항상 `jobId`가 있다"를 단정하면 함께 고친다 (FR-046, FR-046a, research R6-10, analyze N1)
- [X] T048 [P] [US2] `frontend/tests/CollectingNoticeFx.test.tsx` — 환율 줄이 `queued`·`collecting`·`waiting`에 맞는 문구를 보이는지, `waiting`이면 003 수집 스트림을 구독하고 그 수집이 끝나면 **화면이** 시뮬레이션을 다시 요청하는지, 둘 다 끝나기 전에는 결과를 그리지 않는지, `fx_not_available_before`이면 W4a와 "그 달로 옮기기"가 보이는지 (FR-043, FR-043a, FR-045, FR-046)

### Implementation for User Story 2

**구현 순서**: T049 → T050 → **T092 → T051 → T052 → T093** → T053 → T054 → T055. T051이 T092의 함수를 부른다.
T092·T093은 analyze에서 덧붙인 ID라 목록 순서가 실행 순서와 다르다(analyze A2).

- [X] T049 [US2] `backend/src/simulation/fx_convert.py`에 `per_unit`을 더한다. `Decimal`, 소수 6자리 (FR-042)
- [X] T050 [US2] `backend/src/api/services/stock_fx.py`의 `load_rates`가 행의 `quote_unit`으로 나눈 1단위당 값을 만들게 한다 (FR-042, research R6-9)
- [X] T051 [US2] `backend/src/api/services/stock_collect.py`에 환율 판정을 더한다 — 001 커버리지로 필요한 구간을 보고, **수집으로 채울 수 없는 구간이면 탐색 시작일 이전 → 최초 고시일 이전 순서로 판정해 수집하지 않고**(research R6-10 표), 그 밖에는 **T092의 `ensure_background_job`을 불러** 그 수집 표의 `state`·`busyWith`를 그대로 `fx`에 싣는다. 큐를 직접 부르지 않는다 (FR-043, FR-043a, FR-044, FR-045, FR-046, FR-046a, FR-047, research R6-10, analyze A1·A3)
- [X] T052 [US2] `backend/src/api/routes/stock_simulation.py`·`stock_series.py`의 202 본문에 `fx`를 싣고, `main.py`에 `fx_not_available_before`(409) 처리기를 더한다 (FR-043a, FR-045, contracts/rest-api 5·6절)
- [X] T053 [US2] `frontend/src/lib/types.ts`에 202 `fx`와 `fx_not_available_before` 본문 타입을 더한다
- [X] T054 [US2] `frontend/src/stores/stockStore.ts` — `fx.state: waiting`이면 003 수집 스트림(`lib/collectionStream.ts`)을 구독하고 끝나면 다시 요청한다. 화면을 떠나면 구독을 끊는다. `queued`·`collecting`도 같은 스트림으로 끝을 본다. 수집이 실패하면 사유를 보이고 자동으로 다시 요청하지 않는다(FR-047a) — **환율 쪽은 이 판정이 빠진 채 완료로 표시되었다. T099·T100이 고친다(analyze I1).** **003의 스트림은 `busyWith`를 연결할 때 한 번만 읽어 `waiting`이 풀린 것을 알 수 없었다** — 백엔드 `routes/collection.py`·`api/collection_stream.py`가 프레임마다 읽게 함께 고쳤다(구현 단계 발견, T091이 검증) (FR-046, research R6-10)
- [X] T055 [US2] `frontend/src/components/stock/CollectingNotice.tsx`에 환율 줄(W4)과 W4a를 더한다. W4a는 `reason`에 따라 두 문구를 나눈다 (FR-043a, FR-045, FR-046, ui-wireframes W4, W4a) **Phase 9에서 진행 줄이 "N / M 구간"에서 "받은 날 / 받을 날"로 바뀐다(T118).**
- [X] T092 [US2] `backend/src/api/services/collection_gate.py`의 `ensure_background_job`이 **작업도 점유도 만들지 않고** 003의 `StartQueue`로 요청만 넘기게 한다. 작업 번호 대신 **수집 표**(`state`: `collecting`·`queued`·`waiting`, `jobId`: 점유가 있을 때만, `busyWith`, `progressUrl`)를 돌려준다. 큐가 거절하면 아무것도 남기지 않는다 (FR-046a, research R6-10, analyze N1)
- [X] T093 [US2] 외환 화면의 202를 만드는 `backend/src/api/routes/series.py`·`daily.py`·`rates.py`·`latest.py`가 수집 표를 싣게 한다 — `jobId`가 `null`일 수 있고 `state`·`busyWith`가 더해지며, 시작 전이면 `progressUrl`이 `/api/fx/collection/stream?currency=`다. 006의 시뮬레이션 202 `fx`(T051·T052)도 같은 수집 표를 쓴다. 외환 화면의 프론트엔드는 이 필드를 읽지 않으므로 화면은 바꾸지 않는다 (FR-046a, contracts/rest-api 6a절)

**Checkpoint**: 엔화 종목이 원화로 올바르게 계산되고, 환율이 없으면 받아 온다

---

## Phase 5: User Story 3 - 시작일을 기본값에서 월·년 단위로 옮긴다 (Priority: P2)

**Goal**: 기본 2020-01-01, 월·년 이동, 시작 가능 날짜를 실행 전에 알린다.

**Independent Test**: 화면을 열어 기본값을 보고 quickstart 13의 표대로 옮겨 본다. 기본값 그대로 실행해
거절되지 않는지 본다(quickstart 14).

### Tests for User Story 3 ⚠️

- [X] T056 [P] [US3] `frontend/tests/startDate.test.ts` — 한 달·1년 앞뒤 이동을 표로 검증한다: 2020-01-31 + 1개월 = 2020-02-29, 2020-02-29 + 1년 = 2021-02-28, 2020-03-31 − 1개월 = 2020-02-29, 맞춰진 날짜에서 다시 이동하면 맞춰진 날짜에서 출발하는지, 어제가 속한 달을 넘지 못하는지. **`startDate.ts`에 `setMonth`·`setFullYear`가 없는지**(정적 검사) (FR-002, FR-003, FR-004, SC-012, research R6-7)
- [X] T057 [P] [US3] `frontend/tests/StartDateInput.test.tsx` — 처음 값이 2020-01-01인지, 버튼이 "1년 전"·"한 달 전"으로 읽히는지, 경계에서 버튼이 비활성인지, 미래 날짜 입력에 사유가 보이고 실행이 막히는지, **시작일이 `listedOn`보다 이르면 W1a가 보이고 "그 달로 옮기기"를 눌러야만 바뀌는지** (FR-001, FR-002, FR-004, FR-005)
- [X] T058 [P] [US3] `frontend/tests/stockStoreStartDate.test.ts` — 종목을 바꿔도 시작일이 그대로인지, `before_listing`(`basis: price_start`)의 `startableFrom`이 W1a와 같은 모양으로 보이는지 (FR-005a, FR-006)
- [X] T059 [P] [US3] `backend/tests/integration/test_start_available.py` — **검색 → 등록 → 실행** 경로로 검증한다. 시작일이 목록의 상장일보다 이르면 **시세를 받지 않고**(수집 작업 미생성) `400 before_listing`·`basis: listing`인지. 수집 범위가 시작일을 덮는데 시작 월에 일봉이 없으면 `basis: price_start`·`startableFrom`인지. **시작일이 휴일(2020-01-01)이고 `first_available_date`가 비어 있어도 거절하지 않는지**(005 실제 경로 결함). 첫 매수가 시작 월 밖으로 **몰래 밀리지 않는지**. 목록의 상장일이 `stock.first_available_date`에 복사되지 않는지 (FR-005, FR-005a, SC-013, SC-013a, research R6-8, R6-17)

### Implementation for User Story 3

- [X] T060 [US3] `frontend/src/lib/startDate.ts` — 정수 날짜 산술, 그 달 말일로 맞춤, 어제 경계 (FR-002, FR-003, FR-004)
- [X] T061 [US3] `frontend/src/components/stock/StartDateInput.tsx` — W1·W1a (FR-001, FR-002, FR-004, FR-005, ui-wireframes W1, W1a)
- [X] T062 [US3] `frontend/src/components/stock/SimulationForm.tsx`가 `StartDateInput`을 쓰게 하고, `stockStore`의 시작일 초기값을 2020-01-01로, 종목 변경이 시작일을 건드리지 않게 한다 (FR-001, FR-006) **Phase 9에서 원금 칸이 3자리 쉼표로 보인다(T115).**
- [X] T063 [US3] `backend/src/api/services/stock_simulation.py` — 시작 가능 날짜를 두 단계로 판정한다: 수집 전에는 목록 상장일(과 출처가 준 시세 시작일)을 하한으로, 수집 후에는 시작 월의 실제 일봉으로. `run_simulation`이 메타데이터(`listed_on`)를 실제 일봉보다 먼저 믿지 않게 바꾼다. **받아 둔 첫 시세를 수집 전 근거로 쓰지 않고, 주식 수집을 시작 월 1일부터 한다**(`stock_collect.collecting_body`, 구현 단계 결정) (FR-005, FR-005a, research R6-8)
- [X] T064 [US3] `backend/src/api/main.py`의 `before_listing` 처리기가 `startableFrom`·`basis`를 싣게 하고, `frontend/src/lib/types.ts`에 본문 타입을 더한다 (FR-005, FR-005a, contracts/rest-api 2절)

**Checkpoint**: 시작일이 기본값에서 출발하고, 기본값 그대로 실행해도 거절되지 않는다

---

## Phase 6: User Story 4 - 미국 종목을 한글·영문·티커로 찾는다 (Priority: P2)

**Goal**: 미국 3개 거래소 목록을 받아 한글·초성·영문·티커로 찾는다.

**Independent Test**: 미국 목록을 받아 둔 상태에서 애플을 네 방식으로 찾고, 클래스 주식·NYSE Arca ETF로
시뮬레이션한다(quickstart 5, 12).

**의존**: US1의 검색 핵심(T030~T038)을 쓴다.

### Tests for User Story 4 ⚠️

- [X] T065 [P] [US4] `backend/tests/contract/test_kiwoom_us.py` — T005의 실제 응답 픽스처로 미국 목록을 파싱한다. `stk_nm`이 한글 종목명, `stk_enm`이 영문 종목명, `isEtf` → `kind`, `stex_tp` → 단위인지. 여러 쪽이 이어지는지. **한도 초과(`1700`) 픽스처에서 `rate_limit` 실패로 끝나고 받은 쪽까지로 교체하지 않는지** (FR-011, FR-018, research R6-2)
- [X] T066 [P] [US4] `backend/tests/unit/test_price_symbol.py`에 미국을 더한다 — 거래소 → 005 시장, 통화 USD, **T005에서 확정한 클래스 주식 표기 변환**, 규칙으로 못 옮기는 기호는 그대로 보내는지. **역변환**: 표기 변환의 역으로 찾고, 못 찾으면 심볼을 그대로 티커로 한 번 더 찾고, 그래도 없으면 `reselect`인지. **클래스 주식을 포함해 목록 → 시세 식별자 → 목록이 같은 종목으로 돌아오는지**(왕복) (FR-030b, FR-031, SC-007a, SC-008, research R6-6 역변환)
- [X] T067 [P] [US4] `backend/tests/unit/test_search_match.py`에 미국 표를 더한다 — 애플·ㅇㅍ·apple·AAPL, 테슬라·엔비디아, 한글명이 비어 있는 종목이 영문명·티커로만 찾히는지 (FR-021, SC-002)
- [X] T068 [P] [US4] `backend/tests/integration/test_listing_us_pacing.py` — 미국 단위의 쪽 사이 간격이 설정(기본 12초)을 지키는지(가짜 시계), 목록이 한 번도 없을 때 검색이 "결과 없음"이 아니라 `never`/`refreshing`으로 답하는지, 국내 단위가 미국 단위를 기다리지 않는지 (FR-015, FR-017, FR-028, FR-063)
- [X] T069 [P] [US4] `backend/tests/integration/test_stock_selection_us.py` — **같은 티커의 미국 종목이 거래소가 달라도 하나로 쓰이는지**(005가 `AMEX`로 저장한 ETF를 목록이 `NYSE`로 줄 때), 없으면 목록의 거래소로 만드는지 (FR-030, FR-030a, SC-007)
- [X] T095 [P] [US4] `frontend/tests/StockSearchLocal.test.tsx`에 더한다 — 미국 결과에 영문 종목명이 함께 보이는지, 국내 결과에는 그 자리가 없는지. **T075의 테스트가 목록에 없어 더한 태스크다** (FR-025)

### Implementation for User Story 4

- [X] T070 [US4] `backend/src/ingestion/kiwoom/parse.py`에 미국 목록 파싱을 더한다 (FR-011)
- [X] T071 [US4] `backend/src/search/price_symbol.py`에 미국 규칙을 더한다 (FR-031)
- [X] T072 [US4] `backend/src/api/services/listing_refresh.py`에 `NYSE`·`NASDAQ`·`AMEX` 단위와 미국 쪽 사이 간격을 더한다. **`worker/listing_worker.py`를 국내·미국 두 줄로 나누고 `ingestion/kiwoom/client.py`의 토큰 발급을 잠근다**(T068의 "국내가 미국을 기다리지 않음"·"토큰 한 번"을 만족시키려면 필요했다, 구현 단계 결정) (FR-011, FR-015, FR-017, FR-063, research R6-3)
- [X] T073 [US4] `backend/src/api/services/stock_selection.py` — 미국은 **티커로 기존 종목을 먼저 찾는다** (FR-030a)
- [X] T074 [US4] `backend/src/api/services/listing_index.py`에 미국 일치 필드(한글명·영문명·티커)를 더한다 (FR-021)
- [X] T075 [US4] `frontend/src/components/stock/StockSearch.tsx`가 미국 결과에 영문 종목명을 함께 보이게 한다 (FR-025) **Phase 9에서 코드가 오른쪽 칸에서 이름 옆으로 옮겨진다(T116).**

**Checkpoint**: 미국 종목을 한글·초성·영문·티커로 찾는다

---

## Phase 7: User Story 5 - 원금 통화는 원화 또는 종목 통화만 고른다 (Priority: P3)

**Goal**: 교차 통화 조합을 모든 경로에서 막고, 화면이 통화를 몰래 바꾸지 않는다.

**Independent Test**: 원금 USD·국내 종목, 원금 EUR·미국 종목으로 실행을 시도해 둘 다 막히는지
확인한다(quickstart 20).

### Tests for User Story 5 ⚠️

- [X] T076 [P] [US5] `backend/tests/integration/test_principal_currency_pair.py` — 국내 종목 + USD, 미국 종목 + EUR, 미국 종목 + JPY가 표·차트 **둘 다** `400 currency_pair_not_allowed`·`allowed`인지, **어떤 계산도 일어나지 않는지**(시세 수집 작업 미생성), `EUR`이 원금 통화로 더 이상 받아들여지지 않는지, 미국 종목 + USD는 환전 없이 계산되는지 (FR-050, FR-050a, FR-050d, FR-051, FR-052, SC-011)
- [X] T077 [P] [US5] `frontend/tests/SimulationFormCurrency.test.tsx` — 선택지가 `{KRW, 종목 통화}`이고 EUR이 없는지, **USD로 미국 종목을 보다가 국내 종목으로 바꾸면 통화 값이 그대로 남고 "다시 고르세요"가 보이며 실행이 막히는지** (FR-050b, FR-050d, SC-011a)
- [X] T078 [P] [US5] `frontend/tests/SimulationHistoryBlocked.test.tsx` — 005 시절 이력의 막힌 조합 항목이 **지워지지 않고** 남는지, 다시 실행·비교에 고르면 거절 사유가 보이는지, 비교에서 조용히 빠지지 않는지 (FR-050c)

### Implementation for User Story 5

- [X] T079 [US5] `backend/src/api/services/stock_simulation.py` — `check_principal_currency(code, stock_currency)`가 `{KRW, 종목 통화}`만 받게 하고 원금 통화 목록에서 EUR을 뺀다. 표·차트·이력 재실행이 모두 이 함수를 지나게 한다. `main.py`에 처리기를 더한다 (FR-050, FR-050a, FR-050d, FR-051, research R6-11)
- [X] T080 [US5] `frontend/src/components/stock/SimulationForm.tsx`·`frontend/src/stores/stockStore.ts` — 종목에 따라 선택지를 정하고, 허용되지 않게 되면 값을 바꾸지 않고 막는다 (FR-050b, FR-050d, ui-wireframes W3) **Phase 9에서 원금 칸이 3자리 쉼표로 보인다(T115).**
- [X] T081 [US5] `frontend/src/components/stock/SimulationHistory.tsx`·`stockStore.ts` — 막힌 이력 항목을 사유와 함께 표시한다. 비교에 고르면 서버에 묻지 않고 사유와 함께 실패 목록에 올린다. **005의 이력 화면에는 "다시 실행" 버튼이 없어** 재실행 경로의 거절은 서버(T079, T076)가 맡는다 (FR-050c)

**Checkpoint**: 다섯 스토리가 모두 독립적으로 동작한다

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T082 [P] `backend/tests/unit/test_no_float.py`에 검사를 더한다 — `src/search/`, `ingestion/kiwoom/`, `api/services/listing_*.py`, `api/services/stock_collect.py`에 `float(` 사용이 없는지 (헌법 원칙 VI)
- [X] T083 [P] `backend/tests/unit/test_no_interpolation.py`에 검사를 더한다 — 목록 교체와 환율 판정 경로에 값을 채우는 코드가 없는지. 빠진 종목·환율이 없는 구간을 값으로 메우지 않는다. 또 **`repository/stock_listing.py`에 `delete(`가 없는지** — 종목과 원본을 지우는 경로가 생기면 헌법 원칙 V(원본 보존)와 FR-019가 함께 깨진다. 지워야 하는 점유는 `repository/stock_listing_lock.py`로 옮겼다(이 검사가 의미를 갖게 하려고) (FR-019, FR-043a, FR-047, FR-061, 헌법 원칙 V)
- [X] T084 `README.md` — 현재 상태 표에 006을 더하고, 데이터 출처에 키움(검색용 목록, 공식 API)과 **이용 조건**(계좌·HTS ID·사용 등록, 약관 원문은 사용자 확인)을 적고, "가상자산은 006"을 "다음 자산군 기능(번호 미정)"으로 고친다 (FR-064, FR-070, research R6-15, R6-16)
- [X] T085 `CLAUDE.md` — 현재 상태 표에 006을 더하고, "가상자산은 006" 문구를 고치고, 키움 인증 정보 설정과 목록 갱신 워커(`lifespan`의 네 번째 태스크)를 운영 메모에 적는다. 005 `plan.md`는 고치지 않는다 (FR-070)
- [X] T086 `backend/`에서 mypy strict(`src`)와 ruff(`src`·`tests`)를 통과시킨다
- [X] T087 `frontend/`에서 `npx tsc --noEmit`과 `npx eslint .`를 통과시킨다. `any` 금지
- [X] T088 `backend/`에서 커버리지 80% 이상을 확인한다 — `cd backend && .venv/bin/python -m pytest -q --cov=src`
- [X] T089 `backend/tests/`와 `frontend/tests/` 전체가 **네트워크 차단 상태에서** 통과하는지 확인한다. 005가 더한 소켓 가드가 키움 호출도 막는지 본다 — `backend/tests/unit/test_network_guard.py`가 키움 도메인 접속과 aiohttp 경로(해석된 주소)가 가드에 걸리는지 검증한다 (헌법 원칙 III)
- [ ] T090 **부분 완료 — 엔화 시나리오는 2026-10-03에 실행했다(16·19-1 통과, 17·18-1 부분 통과). Yahoo 분할 비율 결함(quickstart 실행 기록 결함 4)과 고친 파서로 다시 돌리자 드러난 결함 5(분할이 두 번 들어감)는 T102~T108이 고쳤고 시나리오 23(토요타·애플)으로 확인했다(사용자 결정 A안). 남은 것: 시나리오 9(다음 날), 화면 조작 시나리오 — **브라우저로 실제 실행해야 한다.** "프론트엔드 테스트가 대신한다"는 가정은 틀렸다: 그 테스트는 `apiClient`를 흉내 내어 프록시를 거치지 않았고, 주식 화면 전체가 브라우저에서 404였다(T109·T110, 버그 `stock-search-not-found`)**. `quickstart.md`의 시나리오 23개(24~26은 T119, 27은 T123이 맡는다)를 순서대로 수동 실행하고 결과를 기록한다. 시나리오 1은 인증 정보를 넣기 전에 해야 한다. 시나리오 2의 측정값으로 research R6-2를 채운다. **실제 출처를 부르므로 미국 목록은 분당 제한을 지킨다.** 시나리오마다 검증하는 FR·SC는 quickstart에 적혀 있다 — 범위 표기로 묶지 않는다(004의 교훈: 범위 표기는 검색에 걸리지 않는다)
- [X] T096 `backend/src/worker/stock_worker.py` — **T090에서 발견**: 주식 수집 워커가 출처를 열지 않아 실제 경로의 모든 시세 수집이 실패했다(005 결함). 003의 `worker_loop`처럼 출처를 열고 닫는다. 재현 테스트 `test_stock_worker.py::Test출처_열기`(열어야만 동작하는 스텁) (005 FR-043, 006 SC-007a, FR-047a)
- [X] T097 `backend/src/ingestion/yahoo/errors.py` — **T090에서 발견**: 시세가 시작되기 전 구간에 대한 HTTP 400 + `chart.error`("Data doesn't exist for startDate …")를 빈 구간으로 받는다. 실제 응답을 픽스처(`chart_no_data_in_range.json`)로 계약 테스트한다. 다른 400은 그대로 오류 (006 FR-005, FR-005a)
- [X] T098 `backend/tests/conftest.py` — **T090에서 발견**: 테스트 세션의 수집 로그를 임시 경로로 옮긴다(`TestClient`가 `lifespan`을 돌려 운영 로그에 썼다). `.env`의 값을 존중하지 않는다. 재현 테스트 `test_logging_config.py::test_테스트는_운영_수집_로그에_쓰지_않는다` (헌법 원칙 III, CLAUDE.md "로그는 두 곳")
- [X] T099 [P] `frontend/tests/CollectingNoticeFx.test.tsx`에 더한다 — **analyze I1**: 환율 수집이 실패·부분 성공으로 끝나면 다시 요청하지 않고 작업의 `lastError`를 보이는지, 성공이면 다시 요청하는지, 진행을 못 본 채 끝났을 때 구독 시점보다 새 작업이 실패했으면 멈추는지, 새 작업이 없으면 예전처럼 다시 요청하는지(서버가 판정한다), **그렇게 판정 없이 다시 요청하는 것이 한 번뿐인지**(출처가 곧바로 거절하면 작업이 구독보다 먼저 끝나 기준 자체가 된다), 실패 뒤 사용자가 다시 실행하면 다시 요청하는지, 작업 조회가 실패하면 다시 요청하는지. 목(mock)이 경로별로 답하고 시뮬레이션 요청만 센다 (FR-047a, SC-007a)
- [X] T100 `frontend/src/stores/stockStore.ts`의 `watchFx` — 스트림의 `idle`은 끝났다는 것만 알리고 **성공인지 실패인지 알리지 않는다.** 구독할 때 그 통화의 마지막 작업 번호를 기준으로 받아 두고(`GET /api/fx/jobs?currency=&limit=`), 끝났다고 판단하면 작업을 조회한다 — `succeeded`면 다시 요청, `failed`·`partial`이면 구독을 끊고 `lastError`를 오류로 보이며 다시 요청하지 않는다. 진행을 본 작업(`snapshot`의 `activeJob.jobId`) 또는 기준보다 새 작업만 이번 수집으로 본다. 조회가 실패하거나 새 작업이 없으면 다시 요청한다 — 서버가 다시 판정한다. **판정 없는 다시 요청은 사용자 실행 한 번에 한 번이다** — 두 번째에는 마지막 작업을 이번 수집으로 본다 (FR-047a, research R6-10)
- [X] T101 [P] `backend/tests/integration/test_listing_events.py` — **구현 뒤 보강한 테스트다**(analyze C1, T094와 같은 유형). 목록 갱신의 시작·완료(쪽 수·종목 수·새 종목·빠진 종목)·실패(실패 종류) 사건이 수집 전용 로그에 남는지, 출처 문구가 키·토큰을 되돌려 보내도 사건에 싣지 않는지. 구현(`listing_refresh._event`)이 먼저 있어 처음부터 통과한다 (FR-065, FR-060, SC-014)
- [X] T102 [P] `backend/tests/contract/test_stock_source_parse.py`에 더한다 — **T090에서 발견**: 실제 응답은 분할 비율을 실수(`5.0`)로 준다. 실제 응답 픽스처(`chart_split_float.json`, 토요타 2021-09-29 5:1)의 분할을 정수로 읽는지, 같은 응답의 일봉·배당도 읽는지, 정수가 아니거나 0·음수인 비율은 반올림하지 않고 출처 오류로 거절하는지 (005 FR-012, 헌법 원칙 V·VI)
- [X] T103 `backend/src/ingestion/yahoo/parse.py` — 분할 비율을 `Decimal(str(값))`로 읽고 **양의 정수일 때만** `int`로 바꾼다(**T121이 정확한 분수로 넓혔다** — 정수가 아닌 비율도 실제로 온다). 아니면 `StockSourceUnavailable`(응답이 유효하지 않음). 005의 `int(str(…))`는 `'5.0'`에서 실패해, 구간에 분할이 있는 모든 종목의 시세 수집이 매번 실패했다 — 005 결함, plan Complexity Tracking "005 결함 수정이 이 기능에 섞인다" (005 FR-012, 006 SC-007a). **결함 5와 함께 커밋한다**: 고친 파서로 실제 출처를 다시 돌리자 결함 5(출처의 시세가 이미 분할을 반영한 값이라 분할이 두 번 들어간다)가 드러났다 — 분할 비율만 고치면 수집 실패가 **조용히 틀린 수익률**로 바뀐다. 사용자가 A안(원주가로 되살리기)을 골랐다(2026-10-03). T107과 한 커밋에 넣는다
- [X] T104 [P] `backend/tests/contract/test_stock_source_parse.py`에 더한다 — **T090 결함 5**: 실제 응답 픽스처(토요타 청크 + 2021-09 이후 분할 기록, 애플 2000-01·2012-08 청크 + 2000 이후 분할 기록)로 반영가를 원주가로 되살리는지. 토요타 2021-09-28 시가 10,420엔(×5), 분할 날부터는 그대로, 수정종가는 그대로, 애플 2000-01-03 시가 104.875010(실제 104.87, ×112), 2012-08-09 배당 2.650004(실제 2.65, ×28). 뒤의 분할이 없으면 값이 그대로인지, 병합(1:10·1:3)은 나누고 저장 자릿수로 맞추는지, 같은 날의 비율이 어긋나면 거절하는지, 월봉 분할 기록에서 실제 분할일을 읽는지 (FR-034, SC-007b)
- [X] T105 [P] `backend/tests/contract/test_yahoo_client.py` — 청크마다 **청크 시작일부터 지금까지의 분할 기록**(월봉, `events=splits`)을 함께 요청하는지, 되살린 원주가와 **원본 둘**(`chart`·`splits`, 요청 구간 포함)을 돌려주는지, 분할 기록이 "구간에 시세 없음"(400)이면 뒤의 분할 없음으로 보는지, 분할 기록을 받지 못하면 청크도 돌려주지 않는지, 넘겨받은 세션을 닫지 않는지. 세션은 흉내 낸다 (FR-034, 헌법 원칙 II·III·V)
- [X] T106 [P] `backend/tests/integration/test_stock_collection.py`에 더한다 — 수집이 한 번 받을 때 온 **원본을 모두** `stock_raw_response`에 남기는지(`kind`·요청 구간). 시세 출처 스텁 넷(`test_stock_collection.py`·`test_stock_worker.py`·`test_start_available.py`·`test_stock_selection.py`)을 새 반환 형태(`ChartFetch`)로 바꾼다. `backend/tests/integration/test_migrations.py`에 더한다 — 정정 마이그레이션이 **주식 커버리지만 비우고** 시세·원본·종목은 남기는지 (FR-034, 헌법 원칙 V)
- [X] T107 `backend/src/ingestion/yahoo/parse.py` — `parse_splits`(분할 기록 응답의 분할만 읽는다), `restore_unadjusted`(날짜 이후의 분할·병합 비율을 곱해 시가·종가·배당을 되살린다. 수정종가는 그대로. 저장 자릿수 6으로 반올림. 같은 날 비율이 어긋나면 `StockSourceUnavailable`), 반환 형태 `ChartFetch`·`RawBody`. T103과 한 커밋 (FR-034, research R6-18)
- [X] T108 `backend/src/ingestion/yahoo/client.py` — 세션·현재 시각 주입, `fetch_chart`가 청크 뒤 분할 기록을 받아 되살리고 원본 둘을 돌려준다. `backend/src/worker/stock_runner.py` — `StockSource`의 반환 형태를 바꾸고 원본을 모두 저장한다. 마이그레이션 — `stock_coverage`를 비운다(시세·배당·분할·원본은 지우지 않는다). `db/models.py`의 `StockPrice` 설명(원주가는 되살린 값) (FR-034, research R6-18, data-model 6절)
- [X] T109 [P] `frontend/tests/nextConfigProxy.test.ts` — **버그 `stock-search-not-found`**(`.specify/bugs/stock-search-not-found/`): 브라우저에서 종목을 검색하면 "Not Found". `next.config.ts`의 rewrite가 `/api/fx`만 백엔드로 넘겨 **주식 화면의 모든 `/api/stocks/*` 요청이 Next.js의 404**가 되었다(005부터). `rewrites()`가 주식·외환 주요 경로를 같은 경로 그대로 백엔드로 넘기는지, **프론트엔드 소스가 부르는 모든 `/api/<접두사>`가 덮이는지** 검사한다 — 다른 프론트엔드 테스트는 `apiClient`를 흉내 내어 프록시를 거치지 않는다 (005 FR-001·FR-002a, 006 FR-020·SC-007a)
- [X] T110 `frontend/next.config.ts` — rewrite를 `/api/:path*` → 백엔드 하나로 바꾼다. 프론트엔드에는 API 라우트 핸들러가 없고, 배열 rewrite는 화면·정적 파일 뒤에(afterFiles) 적용되어 화면 경로와 부딪히지 않는다. 자산군마다 규칙을 더하는 구조를 없앤다. 고친 뒤 3030 경유로 검색이 200인지 확인한다
- [X] T120 [P] `backend/tests/contract/test_stock_source_parse.py`·`backend/tests/unit/test_money.py` — **버그 `fractional-split-ratio`**(`.specify/bugs/fractional-split-ratio/`): 삼성물산(`028260.KS`) 2020-05-13 `0.985:1`이 T103의 "양의 정수만" 규칙에 걸려 그 날짜를 포함한 수집이 매번 실패했다. 실제 응답 픽스처(`chart_split_fractional.json`)의 분할을 `(2020-05-13, 197, 200)`으로 읽는지, 되살린 2020-05-08 시가가 정확히 `104500`·2020-05-12가 `102000`(호가 단위)인지, `2.5:1`→`5:2`·`4:2`→`2:1`처럼 기약 정수 쌍인지, 0·음수·숫자 아닌 값·`INT`를 넘는 기약 분수는 여전히 거절하는지, 보유 100주에 197:200 → 98주(버림)인지. 기존 "정수가 아닌 비율은 거절" 테스트는 "쓸 수 없는 비율은 거절"로 좁혔다 (FR-034, 005 FR-010·FR-010a)
- [X] T121 `backend/src/ingestion/yahoo/parse.py` — 분할의 분자·분모를 `Decimal(str(값))`로 읽어 비율을 `Fraction`으로 **정확히** 나누고 기약 정수 쌍으로 담는다(반올림 없음). 0·음수·무한·숫자 아닌 값, `INT`(2,147,483,647)를 넘는 기약 분수는 `StockSourceUnavailable` (FR-034, 005 FR-010a, research R6-18)

---

## Phase 9: 화면 표시 개선과 진행 전달 (반복 2026-10-03)

**Purpose**: 투자 원금의 3자리 쉼표(FR-053), 검색 결과·고른 종목의 `종목명(코드)`(FR-025), 시세 수집의 "받은 날 / 받을
날"(FR-045a). 진행이 화면에 하나도 도착하지 않던 원인 — Next.js 프록시가 SSE를 gzip으로 압축해 모아 둔다 — 을 함께
고친다(research R6-19).

**순서**: 테스트(T111~T114)를 먼저 커밋하고 최초 실패를 확인한 뒤 구현(T115~T118), 마지막에 실제 브라우저 확인(T119).
구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다(헌법 원칙 III, plan Complexity Tracking D2).

### Tests for Phase 9 ⚠️

- [X] T111 [P] `frontend/tests/principalFormat.test.ts`·`frontend/tests/SimulationFormPrincipal.test.tsx` — 순수 함수: `"10000000"` → `"10,000,000"`, `"1234.5"` → `"1,234.5"`, 쉼표·공백이 섞인 입력을 쉼표 없는 문자열로, 숫자 아닌 글자 제거, 빈 값. 화면: 칸에 `10,000,000`이 보이고 `onChange`는 `"10000000"`을 받는지, 붙여넣은 `1,000,000`도 같은지, `toQuery`의 `principal`과 이력 저장값에 쉼표가 없는지 (FR-053, SC-018)
- [X] T112 [P] `frontend/tests/displayCode.test.ts`·`frontend/tests/StockSearchCode.test.tsx` — 순수 함수: `KRX` `005930.KS` → `005930`, `.KQ`, `TSE` `7203.T` → `7203`, 미국 `AAPL`·`BRK-B`는 그대로, 영문 섞인 국내 코드 `0030R0`. 화면: 결과 줄이 `삼성전자(005930)`·`애플(AAPL)`·`토요타자동차(7203)`, 오른쪽 칸에 코드가 두 번 나오지 않는지, 고른 종목 표시가 `삼성전자(005930)`인지 (FR-025, SC-019)
- [X] T113 [P] `backend/tests/integration/test_collecting_response.py`·`backend/tests/integration/test_progress_sse.py`에 더한다 — (앞 파일) 진행 스냅샷에 `daysTotal`(작업 구간의 달력 일수)과 `daysDone`(그 구간 가운데 커버리지가 덮는 날 수)이 있고 청크를 받을수록 늘어나는지. (뒤 파일) **모든 SSE 응답**(`/api/stocks/progress`, `/api/fx/collection/stream`, 001의 진행 스트림)의 `Cache-Control`에 `no-transform`이 있는지, `text/event-stream`을 내는 곳이 그 셋뿐인지. **보강(구현 전 발견)**: 한 연결(세션 하나)에서 워커가 다른 세션으로 커밋한 진행·완료가 다음 스냅샷에 보이는지 — 처음 읽은 스냅샷에 머물러 완료 신호를 보내지 않았다. 003의 외환 수집 스트림도 같아(`test_timeline_contract.py`) 점유가 풀려도 `snapshot`만 보냈다 (FR-045a, FR-046, SC-017)
- [X] T114 [P] `frontend/tests/CollectingNotice.test.tsx`에 더한다 — 스냅샷이 오면 `730 / 2,467일`처럼 쉼표와 함께 보이고 막대 값이 일수 기준인지, 스냅샷 전에는 "시작하는 중…"인지 (FR-045a)

### Implementation for Phase 9

- [X] T115 `frontend/src/lib/principalFormat.ts`(신규)와 `frontend/src/components/stock/SimulationForm.tsx` — 칸은 쉼표 형식으로 보이고 상태에는 쉼표 없는 문자열을 둔다. 입력 중 커서는 **커서 앞의 숫자 개수**를 기준으로 되돌린다 (FR-053, research R6-20)
- [X] T116 `frontend/src/lib/displayCode.ts`(신규)와 `frontend/src/components/stock/StockSearch.tsx` — 결과 줄과 고른 종목 표시를 `종목명(코드)`로, 오른쪽 칸의 코드를 뺀다 (FR-025, research R6-20)
- [X] T117 `backend/src/api/routes/stock_progress.py` — 스냅샷에 `daysDone`·`daysTotal`. `routes/stock_progress.py`·`collection.py`·`collect.py`의 SSE 머리글을 `Cache-Control: no-cache, no-transform`으로(공용 `SSE_HEADERS`). **주식 진행 스트림과 외환 수집 스트림이 프레임마다 `session.rollback()`으로 앞 읽기 트랜잭션을 끝낸다** — 한 연결이 처음 읽은 스냅샷에 머물렀다(research R6-19 발견 2) (FR-045a, research R6-19)
- [X] T118 `frontend/src/lib/stockProgressStream.ts`·`frontend/src/components/stock/CollectingNotice.tsx` — 스냅샷 타입에 `daysDone`·`daysTotal`, 진행 줄을 `받은 날 / 받을 날`로 (FR-045a)
- [X] T119 실제 브라우저(3030 경유)로 확인한다 — 아직 받지 않은 종목을 실행해 진행 메시지가 **실시간으로 도착**하고 숫자가 늘어나는지, 원금 칸의 쉼표, 결과의 코드 표기. **`no-transform`으로도 Next.js가 압축하면** `frontend/next.config.ts`의 `compress: false`로 바꾸고 그 사실을 research R6-19에 적는다 (SC-017, SC-018, SC-019, quickstart 24~26)

**Checkpoint**: 브라우저에서 원금 `10,000,000`, 결과 `삼성전자(005930)`, 수집 중 `N / M일`이 늘어나다 결과가 나온다.

---

## Phase 10: 성과 보드 통화 기호 (반복 2026-10-03 #2)

**Purpose**: 성과 보드의 투자 원금·투자 수익에 원금 통화의 기호를 숫자 뒤에 붙인다(`10,000,000₩`, `1,000$`,
`100,000¥`). `formatMoney`는 표·차트·이력도 쓰므로 바꾸지 않고 보드 전용 표시를 더한다(FR-054, research R6-21).

**순서**: 테스트(T122)를 먼저 커밋하고 최초 실패를 확인한 뒤 구현(T123). 구현 뒤 테스트가 실패하면 멈추고 먼저
보고한다(헌법 원칙 III, plan Complexity Tracking D2).

- [ ] T122 [P] `frontend/tests/PerformanceBoardCurrency.test.tsx` — 순수 함수: `currencySymbol`(KRW `₩`, USD `$`, JPY `¥`, EUR `€`, 모르는 통화는 통화 코드 그대로), `formatMoneyWithSymbol("10000000", "KRW")` → `10,000,000₩`, USD 소수 `"1000.50"` → `1,000.50$`, 음수 `"-5446"` → `-5,446₩`. 화면: 보드의 투자 원금·투자 수익이 `10,000,000₩`·`188,131,842₩`(KRW), `1,000$`(USD), `¥`(JPY)이고 수익률에는 기호가 없으며 "KRW 기준" 줄이 그대로인지 (FR-054, SC-020)
- [ ] T123 `frontend/src/lib/format.ts`에 `currencySymbol`·`formatMoneyWithSymbol`(기존 `formatMoney`에 기호를 뒤에 붙인다 — `formatMoney`는 바꾸지 않는다), `frontend/src/components/stock/PerformanceBoard.tsx`의 원금·수익 칸이 쓴다. 고친 뒤 브라우저(3030)로 원화·달러 원금 결과를 한 번씩 확인한다 (FR-054, SC-020, quickstart 27)

**Checkpoint**: 브라우저의 성과 보드에 `투자 원금 10,000,000₩`, `투자 수익 …₩`(달러 원금이면 `$`).

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
- **Phase 10 (반복 2026-10-03 #2)**: Phase 9 뒤. 성과 보드(005의 결과물)만 고친다
- **Phase 9 (반복 2026-10-03)**: Phase 8 뒤. US1(검색)·US2(수집 안내)·US5(원금 칸)의 화면을 고친다. T110(프록시)이 먼저 있어야 T119를 브라우저로 확인할 수 있다

### 스토리 간 의존

```
Setup → Foundational ─┬→ US1 (MVP) ──→ US4 (미국)
                      ├→ US2 (환전)
                      ├→ US3 (시작일) ⇢ US1의 T034·T039 사용
                      └→ US5 (원금 통화)
```

### Within Each User Story

- 테스트를 먼저 쓰고 **실패를 확인한 뒤 커밋하고**, 그다음 구현한다 (헌법 원칙 III — "구현보다 테스트가
  먼저 커밋되고"). 테스트와 구현을 한 커밋에 넣으면 테스트가 먼저 실패했다는 기록이 남지 않는다
- 순수 함수 → 어댑터 → 저장소 → 서비스 → 라우트 → 화면 순
- **US1·US3의 통합 테스트는 `stock` 행을 픽스처로 미리 넣지 않는다** — 005의 결함이 다시 가려진다

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T036, T039, T040, T052, T064, T079 |
| `backend/src/api/services/stock_simulation.py` | T039, T063, T079 |
| `backend/src/api/services/listing_refresh.py` | T035, T072 |
| `backend/src/repository/stock_listing.py` | T034, T083 |
| `backend/src/repository/stock_listing_lock.py` | T083 |
| `backend/src/api/services/listing_index.py` | T037, T074 |
| `backend/src/api/services/stock_selection.py` | T039, T073 |
| `backend/src/api/services/collection_gate.py` | T092 |
| `backend/src/api/services/stock_collect.py` | T040, T051 |
| `backend/src/api/routes/series.py`·`daily.py`·`rates.py`·`latest.py` | T093 |
| `backend/src/search/price_symbol.py` | T032, T071 |
| `backend/src/ingestion/kiwoom/parse.py` | T033, T070 |
| `backend/tests/unit/test_price_symbol.py` | T016, T066 |
| `backend/tests/unit/test_search_match.py` | T014, T067 |
| `frontend/src/stores/stockStore.ts` | T044, T054, T062, T080, T081, T100 |
| `frontend/src/components/stock/SimulationForm.tsx` | T062, T080, T115 |
| `frontend/src/components/stock/StockSearch.tsx` | T043, T075, T116 |
| `frontend/src/components/stock/CollectingNotice.tsx` | T055, T118 |
| `backend/src/api/routes/stock_progress.py`·`collection.py`·`collect.py` | T117 |
| `frontend/tests/CollectingNotice.test.tsx` | T114 |
| `frontend/src/lib/format.ts`·`frontend/src/components/stock/PerformanceBoard.tsx` | T123 |
| `frontend/tests/CollectingNoticeFx.test.tsx` | T048, T099 |
| `backend/src/ingestion/yahoo/parse.py` | T103, T107, T121 |
| `backend/src/ingestion/yahoo/client.py`·`backend/src/worker/stock_runner.py` | T108 |
| `frontend/next.config.ts` | T110 |
| `backend/tests/contract/test_stock_source_parse.py` | T102, T104, T120 |
| `backend/tests/integration/test_stock_collection.py`·`test_stock_worker.py`·`test_start_available.py`·`test_stock_selection.py` | T106 (스텁 반환 형태) |
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
6. Phase 9 — 원금 쉼표, 종목명(코드), 수집 진행 표시(반복 2026-10-03)
7. Phase 10 — 성과 보드 통화 기호(반복 2026-10-03 #2)

각 스토리는 앞 스토리를 깨지 않고 더해진다.

## Notes

- **함께 고치는 001 결함**: `ensure_background_job`은 작업과 점유만 만들고 워커에 넘기지 않았다
  (research R6-10). 외환 화면의 자동 수집이 실제로 돌지 않았고, 남긴 점유가 006의 환율 수집을 막는다.
  T091·T092·T093이 고친다 — 외환 화면의 동작도 바뀐다(이제 실제로 수집한다). 외환 202 본문은 `jobId`가
  `null`일 수 있고 `state`·`busyWith`가 더해진다(화면은 그 필드를 읽지 않는다)
- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III, analyze C2)
  1. **테스트 커밋** — `test(006): <페이즈> 테스트`. 그 페이즈의 테스트만 담고, **최초 실행의 실패 요약**
     (실패한 테스트 수와 대표 실패 이유)을 커밋 메시지에 적는다. 이 단계의 실패는 예정된 것이다
  2. **구현 커밋** — `feat(006): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다
  - 테스트가 없는 태스크만 있는 페이즈(문서·게이트 확인)는 한 번 커밋한다
  - 005는 페이즈마다 한 번 커밋해 테스트와 구현이 한 커밋에 섞였다. 006부터 나눈다
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
