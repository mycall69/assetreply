# Tasks: FX 환율 축적·조회·시각화

**Input**: Design documents from `/specs/001-fx-rate-history/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 v4.1.0 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.

1. 해당 단계의 테스트 태스크를 **묶음 단위로** 모두 작성한다
2. 테스트가 **실패하는 것을 확인**한다. 이 단계의 실패는 예정된 것이므로 중단하지 않는다
3. 구현 태스크를 진행한다
4. **구현을 마친 뒤에도 실패가 남으면 즉시 중단하고, 실패한 테스트와 원인을 사용자에게 보고한다.**
   실패를 남긴 채 다음 태스크로 넘어가지 않는다. 통과하던 테스트가 깨진 경우에도 같다
   (헌법 v4.1.0 원칙 III)

커버리지 80% 미만은 머지 차단. 전체 스위트는 **네트워크 없이** 통과해야 한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·테스트·인도할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)

## Path Conventions

plan.md의 웹 애플리케이션 구조를 따른다: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`

> **헌법 v4.0.0 반영**: DB 접근은 비동기 ORM(SQLAlchemy 2.x async) 경유 필수, 커넥션 풀 필수,
> DB 종속 문법은 `db/dialect.py`로 격리, 마이그레이션은 Alembic. Python은 3.14.x.
> v2.0.0 기준으로 작성됐던 순수 SQL 마이그레이션·`aiomysql` 직접 사용 태스크는 폐기하고 재작성했다.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 프로젝트 초기화. `[X]`는 이미 완료되어 헌법 v4.0.0에서도 유효한 작업이다.

- [X] T001 plan.md의 계층 구조대로 `backend/src/{config,ingestion,repository,simulation,api,db}/`와 `backend/tests/{contract,integration,unit}/`, `frontend/src/{app,components,stores,lib}/` 디렉토리 생성
- [X] T002 `backend/pyproject.toml`을 헌법 v4.0.0에 맞춰 재작성 — `requires-python = ">=3.14"`, 의존성 `fastapi`, `uvicorn[standard]`, `aiohttp`, `sqlalchemy[asyncio]`, `alembic`, `aiomysql`(드라이버), **`cryptography`**(MySQL 8.0+ `caching_sha2_password` 인증에 필수 — research R10), **`python-dotenv`**(현재 전이 의존성이므로 직접 선언), dev 의존성 `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`
- [X] T003 `backend/.venv/`를 **Python 3.14로 재생성**하고 재설치 — 기존 환경은 3.11.15라 헌법 v4.0.0 위반 (research R11)
- [X] T004 [P] `frontend/`에 Next.js 16+ / React 19+ / TypeScript 5.0+ 프로젝트 초기화 및 Zustand, Lightweight Charts, Tailwind CSS 의존성 추가
- [X] T005 [P] `backend/pyproject.toml`의 mypy 설정을 `python_version = "3.14"`, `strict = true`로 갱신하고 ruff 린트 규칙 유지
- [X] T006 [P] `frontend/tsconfig.json`에 `strict: true` 설정 및 `any` 금지 린트 규칙을 `frontend/eslint.config.mjs`에 추가
- [X] T007 `backend/pyproject.toml`에 pytest 설정과 `--cov=src --cov-fail-under=80` 게이트 추가
- [X] T008 [P] `frontend/vitest.config.ts`에 Vitest + React Testing Library 설정
- [X] T009 [P] **프로젝트 루트**에 `.env.example` 작성 (`ECOS_API_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`). 실제 값은 루트 `.env`에 두며 커밋하지 않는다
- [X] T010 `backend/alembic.ini`와 `backend/src/db/migrations/env.py`를 생성해 Alembic을 초기화한다 — 비동기 엔진으로 실행되도록 `run_async_migrations` 구성, 연결 URL은 설정 모듈에서 주입 (research R9)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 사용자 스토리가 의존하는 설정·ORM 모델·커넥션 풀·마이그레이션 기반

**⚠️ CRITICAL**: 이 단계가 끝나기 전에는 어떤 사용자 스토리도 시작할 수 없다

### Tests ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T011 [P] `backend/tests/unit/test_config.py`의 기존 설정 테스트를 확장 — DB 커넥션 풀 설정(`db_pool_size`, `db_max_overflow`, `db_pool_timeout_seconds`)의 기본값과 환경변수 오버라이드 테스트를 추가한다. 기존 12개 테스트(8개 기본값·오버라이드·인증키 마스킹·불변성)는 v3.0.0에서도 유효하므로 유지 (헌법 v4.0.0 커넥션 풀 MUST)
- [X] T012 [P] `backend/tests/unit/test_orm_types.py`에 ORM 타입 매핑 테스트 작성 — 모든 금액·비율 컬럼이 `Numeric(asdecimal=True)`로 매핑되고 `python_type`이 `Decimal`이며, 메타데이터 전체에 `Float` 계열 컬럼이 0개임을 검사 (헌법 원칙 VI, research R7)
- [X] T013 [P] `backend/tests/integration/test_engine_pool.py`에 커넥션 풀 테스트 작성 — 엔진이 `AsyncAdaptedQueuePool`을 사용하고 풀 크기·타임아웃이 설정값을 반영하며, 동시 요청이 풀을 재사용(매 요청 새 연결 생성 없음)함을 확인 (헌법 v4.1.0 MUST)
- [X] T014 [P] `backend/tests/integration/test_migrations.py`에 Alembic 마이그레이션 테스트 작성 — `upgrade head` 후 ORM 메타데이터와 실제 스키마가 일치, 재실행 시 멱등, 시드 데이터(통화 3종·JPY `quote_unit=100`·스프레드 기본값) 확인
- [X] T015 [P] `backend/tests/integration/test_dialect_upsert.py`에 방언 upsert 헬퍼 테스트 작성 — 같은 키 재삽입 시 중복 행이 생기지 않고 값이 갱신되며, 호출부가 방언 API를 직접 쓰지 않음을 확인 (research R12, FR-003)

### Implementation

- [X] T016 [P] `backend/src/config/settings.py`에 설정 선언 구현 — contracts/ecos-adapter.md 설정 표의 8개 키와 DB 접속·**커넥션 풀 크기·타임아웃**을 모두 설정값으로 선언한다. 값을 코드에 하드코딩하지 않는다. **`.env`는 저장소 루트에서 로드한다**(`backend/`가 아님) — 경로를 `pathlib`으로 상위 탐색해 해결하며 하드코딩된 상대 경로를 쓰지 않는다 (FR-009, 헌법 v4.1.0·크로스 플랫폼 요구사항)
- [X] T017 `backend/src/db/engine.py`에 SQLAlchemy 비동기 엔진과 커넥션 풀 구현 — `create_async_engine(mysql+aiomysql://..., pool_size, max_overflow, pool_timeout, pool_pre_ping)`. 요청마다 새 연결을 여는 구현을 금지한다 (헌법 v4.1.0 MUST, research R10)
- [X] T018 `backend/src/db/session.py`에 비동기 세션 팩토리와 FastAPI 의존성 주입 구현 — 요청 단위 세션 수명 관리
- [X] T019 `backend/src/db/models.py`에 ORM 모델 7종 정의 — `currency`, `fx_rate`, `fx_raw_response`, `fx_coverage`, `fx_spread`, `fx_collection_job`, `fx_collection_lock`. 금액·비율은 `Numeric(18,6\|9,6, asdecimal=True)`, `Float` 금지 (data-model.md, 헌법 원칙 VI)
- [X] T020 `backend/src/db/dialect.py`에 방언 격리 upsert 헬퍼 구현 — MySQL `on_duplicate_key_update`와 PostgreSQL `on_conflict_do_update`를 분기한다. **방언 API가 등장할 수 있는 유일한 파일** (research R12)
- [X] T021 `backend/src/db/migrations/versions/`에 초기 스키마 리비전 생성 — `alembic revision --autogenerate` 후 인덱스·제약·타입이 data-model.md와 일치하는지 **사람이 검토한 뒤** 커밋 (research R9)
- [X] T022 `backend/src/db/migrations/versions/`에 시드 리비전 생성 — `currency` 3행(USD unit 1, JPY unit 100, EUR unit 1)과 `fx_spread` 기본값 3행 (FR-024)
- [X] T023 [P] `backend/src/ingestion/protocols.py`에 `FxRateSource` Protocol과 도메인 타입 `DailyQuote`, `FetchResult`, `ItemMapping` 정의. `base_rate`는 `Decimal` (헌법 원칙 VI)
- [X] T024 [P] `backend/src/ingestion/ecos/errors.py`에 오류 계층 정의 — `SourceAuthError`, `SourceRateLimited`, `SourceError`, `SourceUnavailable`, `ItemMappingChanged`
- [X] T025 `backend/src/api/main.py`에 FastAPI 앱 부트스트랩과 오류→HTTP 상태 매핑 구현 (contracts/rest-api.md 공통 오류표: 400/404/422/502/503)
- [X] T026 [P] `frontend/src/app/layout.tsx`와 `frontend/src/components/TabNav.tsx`에 4탭 셸 구현 (contracts/ui-sketches.md 화면 구성)
- [X] T027 [P] `frontend/src/lib/apiClient.ts`에 API 클라이언트 기반 구현 — 금액·비율은 문자열로 수신하며 `number`로 변환하지 않는다 (정밀도 손실 방지)

**Checkpoint**: ORM 모델·커넥션 풀·마이그레이션 기반 준비 완료 — 사용자 스토리 시작 가능

---

## Phase 3: User Story 1 - 특정 날짜의 환율 조회 (Priority: P1) 🎯 MVP

**Goal**: ECOS에서 매매기준율을 수집·저장하고, 통화와 날짜로 조회한다. 고시 없는 날은 값을 만들지 않고
직전 영업일을 참고로 제시한다.

**Independent Test**: 데이터가 비어 있는 상태에서 통화·과거 날짜로 조회했을 때 시스템이 데이터를
수집하고 그 날짜의 매매기준율을 반환한다. 임계값 초과 시에는 `202`와 수집 중 안내까지만 확인한다
(진행률 표시는 US4). quickstart 시나리오 4·5·6.

**Scope note**: 동기 수집 경로(필요 구간 ≤ 임계값)까지 구현한다. 임계값 초과 시 `202`를 반환하되
진행률 스트리밍과 진행 화면은 US4에서 붙인다. 수집기의 청크 분할·청크별 커밋·재개는 이 스토리에
포함된다(조회 정확성의 전제이기 때문).

### Tests for User Story 1 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T028 [P] [US1] `backend/tests/contract/fixtures/`에 픽스처 10종 작성 — contracts/ecos-adapter.md 픽스처 표 (`search_ok.json`, `search_ok_jpy.json`, `search_mixed_items.json`, `info_200_no_data.json`, `info_100_bad_key.json`, `info_300_rate_limit.json`, `blocked_page.html`, `item_list_ok.json`, `item_list_changed.json`, `item_list_unmappable.json`)
- [X] T029 [P] [US1] `backend/tests/contract/test_ecos_parse.py`에 정상 응답 파싱 테스트 — `Decimal` 변환, 쉼표 포함 `DATA_VALUE` 처리, `ITEM_NAME2` 필터링
- [X] T030 [US1] `backend/tests/contract/test_ecos_parse.py`에 JPY `quote_unit=100` 보존 테스트 (FR-007)
- [X] T031 [P] [US1] `backend/tests/contract/test_ecos_errors.py`에 `INFO-200` → `outcome=NO_DATA` 테스트 (오류로 처리되지 않아야 함)
- [X] T032 [US1] `backend/tests/contract/test_ecos_errors.py`에 `INFO-100` → `SourceAuthError` 및 **재시도하지 않음** 테스트
- [X] T033 [US1] `backend/tests/contract/test_ecos_errors.py`에 `INFO-300` → `SourceRateLimited` 및 지수 백오프 발동 테스트
- [X] T034 [US1] `backend/tests/contract/test_ecos_errors.py`에 비-JSON HTML → `SourceUnavailable` 테스트 (JSON 파싱 실패와 구분)
- [X] T035 [P] [US1] `backend/tests/contract/test_item_mapping.py`에 항목 매핑 검증 테스트 — 정상 통과, 코드 변경 시 이름 기반 재탐색, 불일치 시 `ItemMappingChanged`로 저장 없이 중단 (FR-015)
- [X] T036 [P] [US1] `backend/tests/unit/test_chunker.py`에 청크 분할 테스트 — 365일 단위, 시작·끝 경계, 구간이 청크보다 짧은 경우
- [X] T037 [P] [US1] `backend/tests/integration/test_sync_threshold.py`에 임계값 경계 테스트 — 필요 구간이 임계값 이하(29일)면 수집 완료 후 `200`, 초과(31일)면 즉시 `202 collecting` 반환 (FR-035, FR-035a, FR-035b)
- [X] T038 [P] [US1] `backend/tests/integration/test_rate_query.py`에 고시 있는 날 조회 테스트 — `status: "quoted"`, 값·단위·출처 포함
- [X] T039 [US1] `backend/tests/integration/test_rate_query.py`에 고시 없는 날 조회 테스트 — `status: "no_quote"`, **최상위에 `baseRate` 없음**, `reference`에 직전 영업일 값과 경고 문구 (FR-018a, FR-018b)
- [X] T040 [US1] `backend/tests/integration/test_rate_query.py`에 범위 밖 조회 테스트 — `400 out_of_range`
- [X] T041 [P] [US1] `backend/tests/integration/test_upsert.py`에 멱등성 테스트 — 같은 구간 재수집 시 중복 행 없음, 값이 다르면 갱신되고 `ingested_at` 유지·`updated_at` 변경 (FR-003a, FR-003b)
- [X] T042 [P] [US1] `backend/tests/integration/test_resume.py`에 중단 후 재개 테스트 — 재실행 시 `covered_through + 1`부터 시작, 이미 받은 구간 재요청 없음 (FR-011)
- [X] T043 [P] [US1] `frontend/tests/RateResult.test.tsx`에 `quoted`와 `no_quote` 렌더 구분 테스트 — `no_quote`일 때 주 결과 영역에 숫자가 없고 참고 영역이 시각적으로 분리됨

### Implementation for User Story 1

- [X] T044 [US1] `backend/src/ingestion/ecos/client.py`에 aiohttp 기반 호출 구현 — **본문 `RESULT` 코드 검사 필수**(HTTP 200으로도 오류가 옴), 지수 백오프 + 지터, `asyncio.sleep` 사용(`time.sleep` 금지)
- [X] T045 [US1] `backend/src/ingestion/ecos/parser.py`에 응답→도메인 타입 변환 구현 — `TIME`→`date`, `DATA_VALUE`(쉼표 포함 문자열)→`Decimal`, `ITEM_NAME2` 필터, `quote_unit` 결정
- [X] T046 [US1] `backend/src/ingestion/ecos/item_mapping.py`에 항목 매핑 검증 구현 — 응답 필드는 `ITEM_CODE`/`ITEM_NAME` (`ITEM_CODE1` 아님), 불일치 시 이름 패턴 재탐색, 실패 시 중단 (FR-015)
- [X] T047 [P] [US1] `backend/src/repository/fx_rate.py`에 ORM 세션 기반 조회와 upsert 구현 — upsert는 `db/dialect.py` 헬퍼만 호출하며 방언 구문을 직접 쓰지 않는다 (research R12)
- [X] T048 [P] [US1] `backend/src/repository/raw_response.py`에 원본 응답 저장 구현 — 자동 정리 없음, 기한 없이 보관 (FR-004a)
- [X] T049 [P] [US1] `backend/src/repository/coverage.py`에 커버리지 조회·갱신 구현 (통화당 1행)
- [X] T050 [US1] `backend/src/ingestion/collector.py`에 수집기 구현 — 365일 청크 분할, **청크별 커밋과 커버리지 갱신**, 중단 후 `covered_through + 1`부터 재개, 선두 `INFO-200` 구간에서 `first_available_date` 발견 (research R2, R3)
- [X] T051 [US1] `backend/src/api/services/collection_gate.py`에 임계값 판정 구현 — `collection.sync_threshold_days`(기본 30) 기준으로 동기 대기 경로와 백그라운드 위임 경로를 분기한다 (FR-035, FR-035a, FR-035b)
- [X] T052 [US1] `backend/src/api/services/rate_query.py`에 조회 서비스 구현 — 커버리지 기반으로 `quoted`/`no_quote`/미수집 판정, 직전 영업일 탐색 (research R8: 별도 휴장일 캘린더 없이 커버리지+값 존재로 판정)
- [X] T053 [US1] `backend/src/api/routes/rates.py`에 `GET /api/fx/rates/{currency}` 구현 — contracts/rest-api.md의 200 quoted / 200 no_quote / 202 collecting / 400 out_of_range 응답. `progressUrl`은 US4 이후에만 포함
- [X] T054 [US1] `backend/src/api/routes/coverage.py`에 `GET /api/fx/coverage` 구현 (FR-005)
- [X] T055 [P] [US1] `frontend/src/components/RateQueryForm.tsx`에 통화·날짜 선택 폼 구현 (ui-sketches S1)
- [X] T056 [P] [US1] `frontend/src/components/RateResult.tsx`에 결과 카드 구현 — 매매기준율을 상단에 크게, JPY는 `원 / 100엔` 단위 표기 (FR-007, ui-sketches S1)
- [X] T057 [P] [US1] `frontend/src/components/NoQuoteResult.tsx`에 고시 없음 화면 구현 — 주 결과에 숫자 없음, 점선 구분 아래 참고 박스에 직전 영업일 값과 경고, **파생 환율 4종 미표시** (ui-sketches S2)
- [X] T058 [P] [US1] `frontend/src/components/EmptyState.tsx`에 데이터 없음 화면 구현 (ui-sketches S7)
- [X] T059 [P] [US1] `frontend/src/stores/rateStore.ts`에 조회 상태 Zustand 스토어 구현

**Checkpoint**: 환율 조회가 단독으로 완전히 동작한다. quickstart 시나리오 2·4·5·6·10 통과 가능

---

## Phase 4: User Story 2 - 스프레드를 반영한 실거래 환율 확인 (Priority: P2)

**Goal**: 통화별 4종 스프레드를 설정하고, 조회 결과에 파생 환율을 함께 제시한다.

**Independent Test**: 알려진 매매기준율과 스프레드로 4종 파생 환율이 정확히 계산되고, 스프레드를
변경하면 결과가 즉시 반영된다 (quickstart 시나리오 7).

### Tests for User Story 2 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T060 [P] [US2] `backend/tests/unit/test_spread_calc.py`에 검증된 참조값 테스트 작성 — 4종 계산식, 손으로 계산한 기대값과 대조 (FR-023, 헌법 원칙 VI)
- [X] T061 [US2] `backend/tests/unit/test_spread_calc.py`에 스프레드 0일 때 4종이 모두 매매기준율과 같아지는 테스트
- [X] T062 [US2] `backend/tests/unit/test_spread_calc.py`에 반올림 테스트 — 소수 2자리 `ROUND_HALF_UP`, 중간 반올림 없음, 동일 입력에 동일 출력 (FR-027, research R7)
- [X] T063 [P] [US2] `backend/tests/integration/test_spread_api.py`에 범위 위반 테스트 — 음수·1 이상 입력 시 `422`이며 기존 값이 유지됨 (FR-025)
- [X] T064 [US2] `backend/tests/integration/test_rate_query.py`에 조회 응답의 `derived`·`appliedSpread`·`spreadBasis` 포함 테스트 (FR-022, FR-026a)
- [X] T065 [P] [US2] `frontend/tests/SpreadSettings.test.tsx`에 스프레드 변경 후 파생값 갱신 테스트

### Implementation for User Story 2

- [X] T066 [P] [US2] `backend/src/simulation/spread_calc.py`에 파생 환율 산출 순수 함수 구현 — 전 계산 `Decimal`, 표시 직전 1회만 `quantize(Decimal('0.01'), ROUND_HALF_UP)`. **이 모듈은 `repository`·`api`를 임포트하지 않는다** (헌법 원칙 IV)
- [X] T067 [P] [US2] `backend/src/repository/spread.py`에 ORM 기반 스프레드 조회·갱신 구현 (0 이상 1 미만 검증)
- [X] T068 [US2] `backend/src/api/routes/spreads.py`에 `GET /api/fx/spreads`와 `PUT /api/fx/spreads/{currency}` 구현
- [X] T069 [US2] `backend/src/api/services/rate_query.py`에 파생 환율 산출 연동 — `derived`, `appliedSpread`, `spreadBasis: "current"` 응답에 추가 (파생값은 저장하지 않고 조회 시 계산)
- [X] T070 [P] [US2] `frontend/src/components/SpreadSettings.tsx`에 스프레드 설정 화면 구현 — 3통화 × 4항목 입력, 범위 위반 인라인 오류, "모든 과거 날짜에 동일 적용" 안내 (ui-sketches S5)
- [X] T071 [US2] `frontend/src/components/RateResult.tsx`에 파생 환율 4종과 "현재 설정된 스프레드를 이 날짜에 적용한 결과" 안내 문구 추가 (ui-sketches S1)

**Checkpoint**: US1과 US2가 각각 독립적으로 동작한다

---

## Phase 5: User Story 3 - 기간별 환율 추이 시각화 (Priority: P2)

**Goal**: 선택한 구간의 환율 추이를 차트로 제공하고, 결측 구간을 값으로 메우지 않는다.

**Independent Test**: 축적된 구간을 지정해 차트를 요청하면 값이 시간 순으로 표시되고, 임의 시점을
가리키면 그 날짜와 값이 정확히 나타난다 (quickstart 시나리오 8·9).

### Tests for User Story 3 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T072 [P] [US3] `backend/tests/unit/test_downsample.py`에 LTTB 부분집합 테스트 — **출력의 모든 값이 입력에 존재한다**(새 값을 만들지 않음, 헌법 원칙 V, research R5)
- [X] T073 [US3] `backend/tests/unit/test_downsample.py`에 LTTB 극값 보존 테스트 — 구간 내 최대·최소가 결과에 남는지
- [X] T074 [P] [US3] `backend/tests/integration/test_series_api.py`에 `gaps` 산출 테스트 — `no_quote`와 `not_collected`가 구분되어 반환됨 (FR-032)
- [X] T075 [US3] `backend/tests/integration/test_series_api.py`에 차트 요청의 자동 수집 유발 테스트 — 임계값 초과 시 `202` (FR-032a)
- [X] T076 [P] [US3] `frontend/tests/FxChart.test.tsx`에 결측 구간 미연결 테스트 — `gaps` 구간에서 시리즈가 분리되는지

### Implementation for User Story 3

- [X] T077 [P] [US3] `backend/src/simulation/downsample.py`에 LTTB 순수 함수 구현 — 원본 포인트를 선택만 하며 값을 생성하지 않는다
- [X] T078 [US3] `backend/src/api/services/series_query.py`에 시계열 조회와 `gaps` 산출 서비스 구현 — 커버리지와 값 존재 여부로 `no_quote`/`not_collected` 판정
- [X] T079 [US3] `backend/src/api/routes/series.py`에 `GET /api/fx/series` 구현 — `maxPoints` 기본 2000, `downsampled`·`algorithm`·`sourcePointCount`·`gaps` 응답
- [X] T080 [US3] `backend/src/api/routes/series.py`에 차트 요청의 자동 수집 연동 — `collection_gate` 모듈 재사용 (FR-032a, T051 의존)
- [X] T081 [P] [US3] `frontend/src/components/FxChart.tsx`에 Lightweight Charts 렌더링 구현 — **`gaps` 구간에서 시리즈를 분리**해 직선 연결을 막는다 (ui-chart.md)
- [X] T082 [P] [US3] `frontend/src/components/ChartPeriodSelector.tsx`에 기간 프리셋(1개월/1년/5년/전체)과 직접 지정 구현 (FR-029, ui-sketches S3)
- [X] T083 [P] [US3] `frontend/src/components/ChartTooltip.tsx`에 툴팁과 상세 이동 구현 — 표시 날짜는 **실제 포인트의 날짜**, 결측 구간에서는 사유 표시 (FR-030, FR-031)
- [X] T084 [US3] `frontend/src/components/FxChart.tsx`에 범례와 다운샘플링 안내 추가 ("표시 N개 중 M개, LTTB", ui-sketches S3)
- [X] T085 [P] [US3] `frontend/src/stores/chartStore.ts`에 차트 상태 Zustand 스토어 구현

**Checkpoint**: US1·US2·US3가 각각 독립적으로 동작한다

---

## Phase 6: User Story 4 - 대량 수집의 진행 확인과 중단 후 재개 (Priority: P3)

**Goal**: 장시간 수집의 진행 상황을 실시간으로 보이고, 통화별 단일 작업을 보장하며, 실패 이력을
사후에 확인할 수 있게 한다.

**Independent Test**: 대량 수집 중 진행률이 갱신되고, 강제 중단 후 재실행하면 이미 수집된 구간을
다시 받지 않는다 (quickstart 시나리오 1·2·3·11).

### Tests for User Story 4 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T086 [P] [US4] `backend/tests/integration/test_collection_lock.py`에 잠금 테이블 테스트 작성 — 같은 통화 중복 요청 시 기본 키 충돌로 `joinedExisting: true`, 다른 통화는 차단되지 않음, 작업 종료 시 잠금 해제 (FR-015a~c, SC-010, research R6)
- [X] T087 [US4] `backend/tests/integration/test_collection_lock.py`에 스테일 잠금 회수 테스트 작성 — `heartbeat_at`이 임계값보다 오래된 잠금은 회수 가능 (research R6)
- [X] T088 [P] [US4] `backend/tests/integration/test_job_lifecycle.py`에 상태 전이 테스트 — `running`→`succeeded`/`partial`/`failed`, `partial`과 `failed`의 구분 기준은 `chunks_done > 0`
- [X] T089 [P] [US4] `backend/tests/integration/test_rate_limit_abort.py`에 한도 소진 테스트 — `INFO-300` 반복 시 작업 중단, `lastError` 기록, **이미 커밋된 구간과 커버리지는 유효** (FR-013)
- [X] T090 [P] [US4] `backend/tests/integration/test_progress_sse.py`에 진행률 스트림 테스트 — `progress` 이벤트 간격이 10초를 넘지 않음, 재연결 시 현재 상태 즉시 1회 전송 (SC-009)
- [X] T091 [P] [US4] `backend/tests/integration/test_job_retention.py`에 보관 정책 테스트 — `failed`/`partial`은 정리되지 않고 `succeeded`만 90일 후 정리 (FR-038a, FR-038b)
- [X] T092 [P] [US4] `frontend/tests/CollectionProgress.test.tsx`에 중단 화면 테스트 — "이미 저장된 구간은 조회할 수 있습니다" 문구가 표시되는지 (FR-013)

### Implementation for User Story 4

- [X] T093 [P] [US4] `backend/src/repository/collection_lock.py`에 잠금 테이블 리포지토리 구현 — `INSERT` 성공=획득, 기본 키 충돌=진행 중, 청크 커밋 시 `heartbeat_at` 갱신, 종료 시 `DELETE`, 스테일 잠금 회수 (research R6). **표준 SQL만 사용하며 생성 컬럼·부분 인덱스를 쓰지 않는다**
- [X] T094 [P] [US4] `backend/src/repository/job.py`에 수집 작업 이력 리포지토리 구현 (ORM 세션 기반)
- [X] T095 [US4] `backend/src/ingestion/orchestrator.py`에 백그라운드 수집 오케스트레이션 구현 — 잠금 획득·작업 생성·상태 전이·통화 간 병행(`max_concurrent_currencies`)
- [X] T096 [US4] `backend/src/api/progress.py`에 SSE 진행률 스트림 구현 — `progress`/`completed`/`error` 이벤트, 10초 이내 하트비트 (contracts/sse-progress.md)
- [X] T097 [US4] `backend/src/api/routes/collect.py`에 `POST /api/fx/collect` 구현 — `joinedExisting` 응답 포함
- [X] T098 [US4] `backend/src/api/routes/jobs.py`에 `GET /api/fx/jobs` 구현 — `currency`/`status`/`limit` 필터
- [X] T099 [US4] `backend/src/api/routes/rates.py`와 `series.py`의 `202` 응답에 `progressUrl` 연결 (US1·US3에서 남겨둔 자리, contracts/rest-api.md 단계 조건 해제)
- [X] T100 [US4] `backend/src/db/retention.py`에 성공 이력 정리 구현 — `job_history.success_retention_days` 기준
- [X] T101 [P] [US4] `frontend/src/components/CollectionProgress.tsx`에 진행 화면 구현 — 진행 바, 현재 구간, 완료 구간, 중단 시 "저장된 구간은 유효" 안내 (ui-sketches S4)
- [X] T102 [P] [US4] `frontend/src/lib/progressStream.ts`에 `EventSource` 구독 구현 (자동 재연결 의존)
- [X] T103 [P] [US4] `frontend/src/components/CollectionStatus.tsx`에 수집 현황 화면 구현 — 통화별 커버리지 표와 작업 이력, 실패 사유를 목록 안에 펼쳐 표시 (ui-sketches S6)
- [X] T104 [P] [US4] `frontend/src/stores/collectionStore.ts`에 수집 상태 Zustand 스토어 구현

**Checkpoint**: 모든 사용자 스토리가 독립적으로 동작한다

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 헌법 v4.1.0 준수 검증과 전체 통합 확인

- [X] T105 [P] `backend/src/`와 `frontend/src/` 전체의 주석·docstring이 한국어인지 점검 (헌법 원칙 VIII)
- [X] T106 [P] `backend/tests/unit/test_no_float.py`에 정적 검사 추가 — `simulation`·`repository` 계층에서 금융 값에 `float` 미사용, ORM 메타데이터에 `Float` 컬럼 0개 확인 (헌법 원칙 VI)
- [X] T107 [P] `backend/tests/unit/test_layer_boundaries.py`에 계층 경계 검사 추가 — `simulation/`이 `repository`·`api`를 임포트하지 않음, `ingestion/ecos/` 밖에 ECOS 필드명 없음 (헌법 원칙 II·IV)
- [X] T108 [P] `backend/tests/unit/test_dialect_isolation.py`에 방언 격리 검사 추가 — `db/dialect.py` 외의 파일에서 `on_duplicate_key_update`·`on_conflict_do_update` 등 방언 API 호출이 없고, 원시 SQL(`text()`) 사용처마다 사유 주석이 있음을 확인 (헌법 v4.1.0)
- [X] T109 `backend/.venv/bin/python -m pytest --cov=src --cov-fail-under=80` 통과 확인 및 미달 시 테스트 보완
- [X] T110 `backend/.venv/bin/python -m mypy --strict src`와 `cd frontend && npm run typecheck` 통과 확인
- [X] T111 네트워크를 차단한 상태에서 `backend/tests/`와 `frontend/tests/` 전체 스위트 통과 확인 — 실패하면 어딘가에서 실제 API를 호출하는 것 (헌법 원칙 III)
- [X] T112 `specs/001-fx-rate-history/quickstart.md`의 검증 시나리오 13개를 순서대로 수동 실행하고 결과 기록
- [X] T113 [P] `backend/tests/integration/test_performance.py`에 성능 기준 측정 추가 — 수집된 날짜 조회 3초 이내(SC-001), 스프레드 변경 후 재산출 2초 이내(SC-008), 30년 구간 시계열 응답 시간 기록. 차트 조작 1초(SC-006)는 quickstart 수동 측정으로 보완
- [X] T114 ECOS 일일 호출 한도를 조사해 `backend/src/config/settings.py` 기본값 조정 여부를 판정하고 research.md R1을 갱신한다. **결과**: 절대 수치는 공식 문서(SPA)·응답 헤더·웹 검색 어디에도 없음. 대신 전체 백필과 같은 규모인 150회 연속 호출을 실측해 한도 신호 0회를 확인(하한 ≥150회, 백필 약 146회). 기본값 조정 불필요 — 청크 365일·대기 1000ms 유지 (2026-08-30)
- [X] T115 [P] `backend/tests/unit/test_no_hardcoded_dates.py`에 정적 검사 추가 — `backend/src` 전체(마이그레이션 포함)에 연도 리터럴 날짜와 ISO 날짜 문자열이 없음을 확인 (헌법 v4.1.0 MUST NOT)
- [X] T116 `backend/tests/integration/test_backward_backfill.py`에 역방향 백필 테스트 작성 — 기존 커버리지보다 이른 탐색 시작일이 주어지면 앞 구간부터 수집하고 `covered_from`이 앞당겨지며, 더 이른 최초 제공일을 발견하면 갱신됨 (FR-002, FR-002a)
- [X] T117 프로젝트 루트 `.env.example`과 `backend/src/config/settings.py`에 통화별 탐색 시작일 설정 추가 — `ECOS_PROBE_FLOOR`, `ECOS_PROBE_START_{USD,JPY,EUR}`. 코드 기본값을 두지 않고 미설정 시 기동 실패 (FR-002, FR-009)
- [X] T118 `backend/src/api/routes/collect.py`와 `backend/src/api/services/collection_gate.py`의 `BACKFILL_START` 상수를 제거하고 `settings.probe_start(code)`를 사용 (T117 의존)
- [X] T119 `backend/src/ingestion/collector.py`의 `next_start_date`·`_record_coverage`·`_record_first_available`을 역방향 백필에 맞춰 수정 — 커버리지가 탐색 시작일보다 늦으면 앞 구간부터, 커버리지는 양방향 확장, 더 이른 제공일 발견 시 갱신 (FR-002, FR-002a, T116 의존)
- [X] T120 [P] `frontend/src/stores/chartStore.ts`의 "전체" 프리셋을 커버리지 기반으로 변경하고 `layout.tsx`·`EmptyState.tsx`의 1995 문구 제거 (FR-002, FR-029)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음. T002·T003·T005·T010이 미완료
- **Foundational (Phase 2)**: Setup 완료 후. **모든 사용자 스토리를 차단**
- **User Stories (Phase 3~6)**: Foundational 완료 후
- **Polish (Phase 7)**: 인도하려는 모든 스토리 완료 후

### User Story Dependencies

- **US1 (P1)**: Foundational 후 시작. 다른 스토리에 의존하지 않음 — **MVP**
- **US2 (P2)**: Foundational 후 시작 가능. `spread_calc`와 스프레드 API는 US1 없이도 단독 테스트 가능.
  단, T064는 US1의 `test_rate_query.py`에 테스트를 추가하므로 T038~T040 이후에 수행한다.
- **US3 (P2)**: Foundational 후 시작 가능. T080은 US1의 T051(`collection_gate`)에 의존
- **US4 (P3)**: Foundational 후 시작 가능. T099는 US1·US3의 `202` 응답 자리에 연결하므로 두 스토리 이후 수행

### Within Each User Story

- 테스트 묶음 작성 → 실패 확인 → 구현 순서를 지킨다. **구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다** (헌법 v4.1.0 원칙 III, NON-NEGOTIABLE)
- ORM 모델 → 리포지토리 → 서비스 → 엔드포인트 → UI 순
- 순수 함수(`simulation/`)는 다른 계층과 무관하게 언제든 병렬 작업 가능

### Parallel Opportunities

> **원칙**: 같은 파일을 대상으로 하는 태스크는 병렬 실행할 수 없다. 아래의 `[P]`는 대상 파일이
> 서로 다른 경우에만 부착돼 있다.

- Phase 1: T005는 T002와 같은 파일이므로 순차. T010은 T003 이후
- Phase 2: 테스트 T011~T015 전부 병렬(대상 파일 5종이 서로 다름) → 구현에서 T016·T023·T024·T026·T027 병렬, T017~T022는 순차(엔진→세션→모델→방언→마이그레이션)
- Phase 3: 테스트는 파일별로 병렬 — T028·T029·T031·T035·T036·T037·T038·T041·T042·T043. 같은 파일 내 후속 태스크(T030 / T032~T034 / T039·T040)는 순차. 구현에서 T047·T048·T049(리포지토리 3종)과 T055~T059(프론트 5종)이 병렬
- Phase 4: T060·T063·T065 병렬(T061·T062는 T060과 같은 파일, T064는 US1 파일). T066·T067 병렬, T070 병렬(T071은 T056과 같은 파일)
- Phase 5: T072·T074·T076 병렬(T073은 T072와, T075는 T074와 같은 파일). T081~T083·T085 병렬(T084는 T081과 같은 파일)
- Phase 6: T086·T088~T092 병렬(T087은 T086과 같은 파일). T093·T094 병렬, T101~T104 병렬
- Foundational 완료 후에는 인력이 있으면 US1~US4를 병렬로 진행 가능

---

## Implementation Strategy

### MVP 범위

**Phase 1 + Phase 2 + Phase 3 (US1)** = T001~T059, 59개 태스크 (그중 6개는 이미 완료).

이 지점에서 "출처가 제공하는 전 구간의 임의 날짜에 대해 USD/JPY/EUR 매매기준율을 조회한다"는
완결된 가치가 나온다.
헌법 원칙 IX가 요구하는 수직 슬라이스(수집 → 저장 → 조회 API → UI)가 모두 포함된다.

### 점진적 인도

| 증분 | 태스크 | 추가되는 가치 |
|------|--------|---------------|
| MVP | T001~T059 | 날짜별 환율 조회 |
| +US2 | T060~T071 | 실거래 기준 파생 환율 |
| +US3 | T072~T085 | 기간별 추이 확인 |
| +US4 | T086~T104 | 대량 수집의 가시성과 신뢰성 |
| 완료 | T105~T120 | 헌법 준수 검증과 운영 준비 |

### 위험 순서

1. **Phase 2의 ORM 기반(T017~T022)이 가장 먼저 위험하다.** 커넥션 풀·모델 매핑·Alembic 리비전이
   틀리면 그 위의 모든 태스크가 흔들린다. T011~T015 테스트를 먼저 통과시킨다.
2. **수집기(T044~T050)가 그다음이다.** ECOS의 오류-200 반환과 항목코드 변경은 기존 구현이 실제로
   밟았던 함정이므로, 계약 테스트 T029~T035를 먼저 통과시킨 뒤 수집기를 붙인다.

T114(호출 한도 확인)는 완료됐다. 절대 수치는 여전히 비공개지만 전체 백필 규모의 실측으로
SC-005를 직접 검증했고, 설계가 한도 수치를 전제하지 않으므로 조정할 기본값도 없었다(research R1).
