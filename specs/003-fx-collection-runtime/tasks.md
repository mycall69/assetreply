---

description: "Task list template for feature implementation"
---

# Tasks: 외환 수집 실행 계층과 실시간 관측 화면

**Input**: Design documents from `/specs/003-fx-collection-runtime/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: **필수.** 헌법 v5.1.0 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
테스트 작성 → 실패 확인 → 구현. 구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 의존 없음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 파일 경로를 반드시 포함한다
- **ID는 안정적 참조다.** 반복(iteration)으로 추가된 태스크는 번호를 이어 붙이므로 ID 순서가
  실행 순서와 일치하지 않을 수 있다. **실행 순서는 페이즈가 정한다** — T089·T090은 Phase 3,
  T091은 Phase 5,
  T086~T088은 Phase 4에 있다.
- 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다 (T020, T065)

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 로깅 기반과 설정값. 백엔드에 로거가 하나도 없으므로 처음부터 세운다.

- [X] T001 `backend/src/observability/__init__.py`와 `backend/src/worker/__init__.py`를 만들어 신규 패키지 두 개를 연다 (plan.md 구조)
- [X] T002 [P] `backend/src/observability/logging_config.py`에 구조화 포매터와 수집 전용 파일 핸들러를 구성하는 `configure_logging()`을 만든다. 웹서버 표준출력(`logs/backend.log`)과 **분리된 파일**에 쓴다 — 접근 로그와 뒤엉키면 운영자가 걸러내야 한다 (research R3-10)
- [X] T003 [P] `backend/src/config/settings.py`에 `stall_threshold_seconds`(기본 60), `event_retention_jobs`(기본 20), `reconcile_interval_seconds`(기본 60), `collection_log_path`를 추가한다. 각각 환경변수로 덮어쓸 수 있어야 한다 (헌법 원칙 II — 정책은 코드가 아닌 설정)
- [X] T004 [P] `backend/tests/unit/test_logging_config.py`에 포매터가 개행 없는 한 줄을 만드는지, 수집 로거가 루트 핸들러로 전파되지 않는지 검증한다

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 스키마와 이벤트 기반. 모든 스토리가 여기에 의존한다.

**⚠️ CRITICAL**: 이 단계가 끝나기 전에는 어떤 사용자 스토리도 시작할 수 없다

- [X] T005 `backend/tests/unit/test_collection_event_model.py`를 먼저 작성한다 — `FxCollectionEvent`의 필수/선택 컬럼과 제약을 검증한다. **실패를 확인한 뒤** T006으로 간다
- [X] T006 `backend/src/db/models.py`에 `FxCollectionEvent`를 정의한다. 컬럼 제약을 data-model.md 그대로 지킨다 — `id` BIGINT PK AUTO_INCREMENT, `job_id` BIGINT **NOT NULL** FK→`fx_collection_job.id`, `currency_code` CHAR(3) **NOT NULL** FK→`currency.code`, `kind` VARCHAR(30) **NOT NULL**, `chunk_from`·`chunk_to` DATE **NULL 허용**, `rows_stored` INT **NULL 허용**, `detail` TEXT **NULL 허용**, `occurred_at` TIMESTAMP **NOT NULL DEFAULT CURRENT_TIMESTAMP**
- [X] T007 `backend/src/db/models.py`의 `FxCollectionJob`에 `events_dropped` INT **NOT NULL DEFAULT 0**을 추가한다. 기존 컬럼은 변경하지 않는다 (data-model 2절)
- [X] T008 `backend/migrations/versions/`에 Alembic 리비전을 만든다 — `fx_collection_event` 테이블 생성, 인덱스 `(job_id, occurred_at)`·`(currency_code, job_id)`, `fx_collection_job.events_dropped` 컬럼 추가, `fx_raw_response(received_at)` 인덱스 추가. 수동 DDL 금지 (헌법 DB 운영 규약)
- [X] T009 [P] `backend/tests/unit/test_collection_events.py`를 작성한다 — 이벤트 값 객체가 9종 `kind`를 모두 표현하고, 인증 키가 어떤 필드에도 담기지 않는지 검증한다 (FR-020)
- [X] T010 `backend/src/observability/events.py`에 이벤트 값 객체와 `kind` 상수 9종을 정의한다 — `job_started`, `chunk_requested`, `chunk_stored`, `chunk_empty`, `chunk_failed`, `retry`, `rate_limited`, `job_finished`, `log_sink_failed`. **`chunk_empty`와 `chunk_failed`를 반드시 분리한다** — 합치면 시계열 공백의 원인이 출처 결측인지 수집 실패인지 구별할 수 없다. 이 9종이 FR-019가 요구하는 기록 내용을 모두 덮는다. **요청 결과는 성공·결측·실패 셋으로 갈리고**(FR-019a), 저장 건수는 0과 해당 없음을 구별하며(FR-019b), 시각 기준을 문서에 명시한다(FR-019c) (FR-019, FR-019a, FR-019b, FR-019c, FR-021)
- [X] T011 [P] `backend/tests/unit/test_event_sinks.py`를 작성한다 — 한 싱크가 실패해도 다른 싱크가 호출되고 예외가 호출자에게 전파되지 않는지 검증한다 (FR-018a)
- [X] T012 `backend/src/observability/sinks.py`에 DB 적재와 파일 로깅 두 싱크를 만들고, 하나의 발행 함수가 둘 다 호출하게 한다. **싱크 실패는 서로 전파되지 않는다.** 파일 실패 시 DB에 `log_sink_failed` 사건을 남기고, DB 실패 시 파일에 남기며 누락 건수를 센다 (research R3-4, FR-018a·018b)
- [X] T013 [P] `backend/src/repository/collection_event.py`에 `record()`, `list_by_job()`, `list_by_currency()`, `prune_to_recent_jobs()`를 만든다. 정리는 통화별 최근 20개 작업 기준이다 (FR-023, research R3-9)
- [X] T014 [P] `backend/src/repository/raw_response.py`에 `count_calls_on(session, day)`를 추가한다 — `received_at`이 그 날짜인 `fx_raw_response` 행 수를 센다. 별도 집계 테이블을 만들지 않는다 (research R3-5, FR-024)

**Checkpoint**: 스키마와 이벤트 기반 준비 완료 — 사용자 스토리 착수 가능

---

## Phase 3: User Story 1 - 수집을 시작하고 떠나도 진행된다 (Priority: P1) 🎯 MVP

**Goal**: 서버가 실제로 수집을 실행하고, 화면과 무관하게 끝까지 진행한다. 죽어도 점유를
되찾고 작업을 부분 완료로 확정한다.

**Independent Test**: 수집을 시작하고 화면을 벗어난 뒤, 저장된 구간이 늘어났는지 DB로 확인한다.
화면 없이 검증할 수 있다.

### Tests for User Story 1 ⚠️

> **이 테스트들을 먼저 작성하고 실패를 확인한 뒤 구현한다**

- [X] T015 [P] [US1] `backend/tests/integration/test_worker_runs_collection.py` — 수집 시작 요청 후 워커가 실제로 `run_collection`을 돌려 커버리지가 전진하는지 검증한다. 스텁 소스를 쓰며 네트워크 없이 통과해야 한다. 요청 연결이 끊긴 뒤에도 진행이 이어지는지 함께 본다 (FR-001, SC-001, SC-002)
- [X] T016 [P] [US1] `backend/tests/integration/test_worker_lifecycle.py` — 워커 태스크가 앱 수명과 함께 시작·종료되고, 정상 종료 시 진행 중이던 작업이 **부분 완료**로 확정되는지 검증한다 (FR-007)
- [X] T017 [P] [US1] `backend/tests/integration/test_reconcile.py` — 진행 중 상태로 남고 하트비트가 900초를 넘긴 작업이 기동 정리에서 부분 완료로 확정되고 점유가 회수되는지 검증한다. **진행 중으로 남은 작업이 0건**이어야 하고, 회수 뒤 새 수집 시작이 가능해야 한다 (FR-005·005a, SC-010, SC-014)
- [X] T018 [P] [US1] `backend/tests/integration/test_resume_creates_new_job.py` — 중단된 작업을 이어받으면 **새 작업**이 생기고 `range_start`가 이전 커버리지의 다음 날인지 검증한다. 기존 작업의 상태를 되돌리지 않는다 (FR-005b, FR-008)
- [X] T019 [P] [US1] `backend/tests/integration/test_no_duplicate_fetch.py` — 이미 전부 수집된 통화의 시작 요청이 **외부 호출 0회**로 완료되는지 검증한다 (FR-009, SC-003)
- ~~T020~~ (2026-09-24 반복에서 삭제 — SC-013 통화 격리가 명세에서 빠졌다. 한 번에 한 통화만 돌므로 검증 대상이 없다)

### Implementation for User Story 1

- [X] T021 [US1] `backend/src/worker/queue.py`에 시작 요청을 워커로 넘기는 통로를 만든다. `asyncio.Queue` 기반이며 요청은 통화 코드 목록이다 (research R3-1)
- [X] T022 [US1] `backend/src/worker/runner.py`에 수집 태스크를 만든다. 큐에서 요청을 받아 `orchestrator.run_all_currencies`를 호출하고, 취소 시 진행 중 작업을 **부분 완료**로 확정한 뒤 종료한다 (FR-001, FR-007)
- [X] T023 [US1] `backend/src/worker/reconcile.py`에 미해결 작업 정리를 만든다. **기동 시 1회 + 주기 실행** 두 경로를 모두 둔다 — 조회 시점 지연 판정은 아무도 화면을 열지 않으면 영원히 고쳐지지 않는다. **기동 시에는 하트비트 나이를 보지 않는다**(FR-005c) — 방금 떴으므로 남아 있는 진행 중 작업은 정의상 전부 고아다 (research R3-2, FR-005a, FR-005c)
- [X] T024 [US1] `backend/src/api/main.py`의 `lifespan`에 워커 태스크와 정리 태스크를 띄우고, 종료 시 취소 후 완료를 기다린다. 엔진 수명보다 먼저 정리되어야 한다 — 세션이 닫힌 뒤 워커가 DB를 만지면 안 된다
- [X] T025 [US1] `backend/src/api/routes/collect.py`를 변경한다. 작업 생성과 점유 획득 후 **워커 큐에 시작을 넘긴다**. 202 응답 형식은 001과 동일하게 유지한다 (contracts/rest-api 1절)
- [X] T026 [US1] **이벤트 발행을 `backend/src/worker/runner.py`에 두었다** (태스크는 `orchestrator.py`를 지정했으나 위치를 옮김 — `ingestion/`이 관측을 모르게 유지하는 편이 헌법 원칙 IV에 맞다). 발행 종류는 계획대로다
- [X] T027 [US1] `backend/src/repository/job.py`에 `finalize_as_partial()`을 추가한다. 회수·종료 시점에 작업을 부분 완료로 확정하며 사유를 `last_error`에 남긴다. **한 구간도 받지 못한 경우에만 `failed`**, 일부라도 받았으면 `partial`이다 (data-model 상태 전이)
- [X] T028 [US1] `backend/src/repository/collection_lock.py`에 하트비트 경과로 스테일 목록을 돌려주는 조회를 추가한다. 기존 `reclaim_stale_locks`의 900초 기준은 변경하지 않는다 (data-model 3절)
- [X] T029 [US1] `backend/src/worker/runner.py`에서 청크 완료마다 이벤트를 발행하고 누락 건수를 누적한 뒤, 작업 종료 시 `fx_collection_job.events_dropped`에 한 번 쓴다. 사건마다 갱신하면 실패가 잦을 때 그 갱신이 부하가 된다 (research R3-4)
- [X] T030 [P] [US1] `backend/tests/unit/test_worker_queue.py` — 같은 통화의 중복 시작 요청이 큐에 쌓이지 않고 진행 중 작업에 합류하는지 검증한다 (FR-003)
- [X] T031 [US1] `be-start.sh`에 `--workers 1`을 명시하고, 다중 워커가 수집을 중복 실행한다는 주석을 남긴다 (research R3-1의 배포 전제)
- [X] T032 [US1] `backend/tests/integration/test_explicit_start_only.py` — 앱이 기동해도 사용자 조작 없이는 수집이 시작되지 않는지 검증한다 (FR-002)
- [X] T091 [US3] `backend/src/observability/sinks.py`의 `log_sink`가 **기록 전에 경로 생존을 확인**한다 — 로거 비활성·핸들러 없음·레벨 초과를 유실로 센다. 비활성 로거는 `info()` 호출이 예외 없이 조용히 성공하므로, 예외 유무만 보면 "전부 기록됨"과 "전부 유실됨"이 같은 신호를 낸다 (FR-017a, SC-007a)
- [X] T090 [P] [US1] `frontend/tests/CollectionIndicatorEntry.test.tsx` — 진행 중인 수집이 없을 때도 표시기가 렌더링되고 `/fx/collection` 링크를 갖는지 검증한다. **이 테스트가 깨지면 기능 전체가 도달 불가능해진다** (FR-030, SC-018)
- [X] T089 [US1] `backend/src/api/routes/collect.py`에 다른 통화의 수집이 진행 중인지 확인해 **409 `collection_in_progress`로 거절**하고 진행 중인 통화를 본문에 담는 처리를 추가한다. 함께 `backend/tests/integration/test_reject_concurrent_start.py`를 먼저 작성해 실패를 확인한다. 조용히 무시하면 사용자는 버튼이 고장난 것으로 여긴다 (FR-004, FR-029, SC-017)

**Checkpoint**: 수집이 실제로 돌고, 화면을 떠나도 진행되며, 죽어도 회복된다. **여기까지가 MVP다**

---

## Phase 4: User Story 2 - 돌아오면 지금 어디까지 왔는지 즉시 보인다 (Priority: P1)

**Goal**: 통화별 시간축 위에 수집 구간이 실시간으로 채워지고, 이어받기 지점이 보인다.

**Independent Test**: 수집 진행 중 화면에 진입해 첫 화면에 현재 지점이 나타나고 이후 갱신이
이어지는지 관찰한다.

### Tests for User Story 2 ⚠️

- [X] T033 [P] [US2] `backend/tests/contract/test_timeline_contract.py` — `GET /api/fx/collection/timeline` 응답이 계약과 일치하는지 검증한다. `activeJob`은 **진행 중일 때만 포함**되어야 한다 (contracts/rest-api 2절)
- [X] T034 [P] [US2] `backend/tests/unit/test_timeline_state.py` — `state`가 하트비트 경과에 따라 `running`(60초 이내)·`stalled`(60~900초)·`awaiting_reclaim`(900초 초과)으로 갈리는지 검증한다. 멈춘 작업이 정상 진행 작업과 구별되어야 한다 (FR-006, FR-006a, SC-011)
- [X] T035 [P] [US2] `backend/tests/contract/test_collection_stream.py` — 수집 스트림가 연결 직후 `snapshot`을 1회 보내고, 이후 5초 간격으로 갱신하며, 진행 중 수집이 없으면 `idle`을 보내는지 검증한다 (FR-010, FR-015)
- [X] T036 [P] [US2] `frontend/tests/CurrencyTimeline.test.tsx` — 시간축이 완료·진행·미수집 구간을 구별해 그리고, `rangeStart`가 `targetFrom`과 다를 때만 이어받기 표식을 렌더링하는지 검증한다. 구간 완료 시 진행 표시가 완료로 전환되어야 한다 (FR-011, FR-012, FR-013, FR-014)
- [X] T037 [P] [US2] `frontend/tests/CurrencyCard.test.tsx` — 상태별 배지와 설명이 W3 표대로 나오는지, `stalled`일 때 "지금 하실 일은 없습니다"가 함께 보이는지, 이어받은 통화에서 재개 지점이 식별되는지 검증한다 (FR-006a, SC-006)

### Implementation for User Story 2

- [X] T038 [US2] `backend/src/api/services/timeline.py`에 통화별 시간축 조합을 만든다 — `targetFrom`은 `currency.first_available_date`(없으면 설정의 탐색 시작일), `targetTo`는 **항상 어제**, 커버리지와 진행 중 작업을 합친다 (research R3-6)
- [X] T039 [US2] `backend/src/api/services/timeline.py`에 현재 청크 계산을 넣는다. `range_start`·`chunks_done`·청크 크기로 계산하며 **저장하지 않는다** (research R3-6)
- [X] T040 [US2] `backend/src/api/routes/collection.py`에 `GET /api/fx/collection/timeline`을 만든다. **`?currency=` 필수**이며 누락 시 400 `invalid_query`. `callsToday`와 `busyWith`를 함께 내려준다 (FR-027, FR-029, contracts/rest-api 2절)
- [X] T041 [US2] `backend/src/api/routes/collection.py`에 `GET /api/fx/collection/stream`을 만든다. **`?currency=`로 구독 단위를 좁힌다.** `snapshot` 본문은 timeline 응답과 **같은 구조**여야 한다 — 화면이 최초 진입과 갱신에서 다른 형태를 다루지 않게 한다 (FR-010, FR-027)
- [X] T042 [US2] `backend/src/api/collection_stream.py`에 5초 하트비트를 넣는다. 상태 변화가 없어도 `snapshot`을 보낸다 (FR-015, SC-004)
- [X] T043 [P] [US2] `frontend/src/lib/collectionStream.ts`에 수집 스트림 클라이언트를 만든다. `EventSource`의 자동 재연결에 의존하며 `error`에서 `close()`하지 않는다 (002 progressStream의 교훈)
- [X] T044 [US2] `frontend/src/stores/collectionStore.ts`를 수집 스트림 구독으로 전환한다. 선택 상태와 스트림 상태를 Zustand 한 곳에서 관리한다 (헌법 원칙 VII)
- [X] T045 [P] [US2] `frontend/src/components/collection/CurrencyTimeline.tsx`를 만든다. 완료·진행·미수집을 **색만이 아니라 명암·패턴으로도** 구별하고, 진행률 텍스트 대체를 둔다 (ui-wireframes W2, 접근성)
- [X] T046 [P] [US2] `frontend/src/components/collection/CurrencyCard.tsx`를 만든다. 상태 배지와 막대 아래 한 줄을 W3 표대로 렌더링한다. **진행 중이 아닐 때 진행 표시를 내보내지 않는다**(FR-016). `[ 이어받기 ]`와 `[ 수집 시작 ]`은 같은 동작이며 문구만 상황에 맞춘다 (FR-016)
- [X] T047 [US2] `frontend/src/app/fx/collection/page.tsx`를 재구성한다. **통화 선택기가 맨 위**, 그 아래 호출 수, 선택 통화 카드, 기록 순이다. 아래 내용이 선택에 종속되므로 종속 방향이 배치로 드러나야 한다 (FR-027, ui-wireframes W1)
- [X] T048 [US2] `frontend/tests/collectionStore.test.ts` — 재진입 시 첫 `snapshot`으로 현재 상태가 즉시 채워지는지 검증한다 (FR-010, SC-005)
- [X] T086 [US2] `frontend/src/app/fx/collection/page.tsx`에 002의 `frontend/src/components/fx/CurrencyTabs.tsx`를 **옮기지 않고 임포트해** 통화 선택기를 붙인다. 파일을 옮기면 002 화면의 임포트가 깨질 위험만 생기고 얻는 것이 없다 (FR-027, research R3-11)
- [X] T087 [P] [US2] `frontend/tests/CollectionCurrencySwitch.test.tsx` — 통화를 전환하면 이전 통화의 시간축·기록·경고가 **한 프레임도 남지 않는지**, 전환 직후 도착한 이전 통화의 갱신이 반영되지 않는지 검증한다. **002의 FR-036c에서 같은 결함을 겪었다** (FR-028, SC-016)
- [X] T088 [US2] `frontend/src/stores/collectionStore.ts`에서 통화 전환 시 상태를 비우고, 도착한 스트림 이벤트의 `currency`를 현재 선택과 대조해 거른다 (FR-028)

**Checkpoint**: 수집이 도는 모습이 실시간으로 보이고, 이어받기 지점이 드러나며, 통화를 골라 볼 수 있다

---

## Phase 5: User Story 3 - 무슨 일이 있었는지 기록에 남는다 (Priority: P2)

**Goal**: 수집 사건이 화면과 파일 양쪽에 남고, 한쪽이 실패해도 수집은 계속되며 그 사실이
드러난다.

**Independent Test**: 수집을 한 번 돌린 뒤 화면 기록과 파일 로그를 대조해 같은 사건이 양쪽에
있는지 확인한다.

### Tests for User Story 3 ⚠️

- [X] T049 [P] [US3] `backend/tests/integration/test_event_both_sinks.py` — 한 사건이 DB와 파일 양쪽에 남고 내용이 갈라지지 않는지 검증한다 (FR-017, FR-018, SC-007)
- [X] T050 [P] [US3] `backend/tests/integration/test_sink_failure_continues.py` — 이벤트 적재가 실패해도 **수집이 끝까지 진행되고 환율 데이터가 정상 저장**되는지 검증한다 (FR-018a, SC-007b)
- [X] T051 [P] [US3] `backend/tests/integration/test_events_dropped_surfaced.py` — DB 적재 실패 건수가 `events_dropped`에 남고 조회 응답에 드러나는지 검증한다 (FR-018b, SC-007a)
- [X] T052 [P] [US3] `backend/tests/integration/test_empty_vs_failed.py` — 출처가 값을 주지 않은 구간은 `chunk_empty`, 수집 실패는 `chunk_failed`로 **구별되어 기록**되는지 검증한다 (FR-021, SC-008)
- [X] T053 [P] [US3] `backend/tests/integration/test_event_retention.py` — 21번째 작업이 끝날 때 가장 오래된 작업의 사건이 정리되고, **작업 행 자체는 남는지** 검증한다 (FR-023, SC-015)
- [X] T054 [P] [US3] `backend/tests/contract/test_events_endpoint.py` — `GET /api/fx/collection/events`가 `jobId`·`currency` 중 하나를 요구하고, 둘 다 없으면 400 `invalid_query`를 돌려주는지 검증한다 (contracts/rest-api 4절)
- [X] T055 [P] [US3] `frontend/tests/EventList.test.tsx` — `chunk_empty`가 "고시 없음", `chunk_failed`가 "구간 실패"로 **다른 문구**로 나오는지 검증한다 (FR-021, ui-wireframes W6)

### Implementation for User Story 3

- [X] T056 [US3] `backend/src/api/routes/collection.py`에 `GET /api/fx/collection/events`를 만든다. `limit` 기본 100, 최대 500. `retention.jobsKept`와 `eventsDropped`를 함께 내려준다 (contracts/rest-api 4절)
- [X] T057 [US3] `backend/src/api/collection_stream.py`에 `event` 이벤트를 추가한다. 새 사건이 생길 때마다 보낸다 (FR-022)
- [X] T058 [US3] `backend/src/repository/collection_event.py`의 `prune_to_recent_jobs()`를 **작업 종료 시점**에 호출하도록 `worker/runner.py`에 연결한다. 새 작업이 생길 때만 20개 경계가 밀리므로 그때 정리하면 경계가 항상 맞는다. **파일 로그는 정리 대상이 아니다** — 화면 기록과 보관 기준이 독립이다 (research R3-9, FR-023a)
- [X] T059 [P] [US3] `frontend/src/components/collection/EventList.tsx`를 만든다. 사건 종류별 문구와 강조를 W6 표대로 적용하고, 하단에 보관 범위를 명시한다 (FR-023)
- [X] T060 [P] [US3] `frontend/src/components/collection/IncompleteRecordNotice.tsx`를 만든다. `eventsDropped > 0`일 때만 렌더링하며 **"수집 자체는 정상입니다"를 반드시 함께 표시한다** — 경고만 보면 사용자가 데이터를 의심한다 (ui-wireframes W5)
- [X] T061 [US3] `frontend/src/stores/collectionStore.ts`에서 `event` 이벤트를 목록 **앞에 덧붙인다**. 전체 교체하면 사용자가 읽던 위치가 사라진다 (ui-wireframes 갱신 범위)
- [X] T062 [US3] `backend/src/observability/events.py`의 발행 지점에서 인증 정보를 차단한다. **포매터가 아니라 발행 지점**에서 막는다 — 포매터에서 걸러내려면 어떤 필드가 비밀인지 아는 지식이 두 곳에 흩어진다 (research R3-10, FR-020)

**Checkpoint**: 무슨 일이 있었는지 양쪽에 남고, 기록 실패도 드러난다

---

## Phase 6: User Story 4 - 오늘 얼마나 썼는지 보인다 (Priority: P3)

**Goal**: 호출 수가 보이고, 한도 소진이 전체 중단으로 이어지며 그 사유가 드러난다.

**Independent Test**: 수집 후 화면의 호출 수가 실제 요청 횟수와 일치하는지 확인한다.

### Tests for User Story 4 ⚠️

- [X] T063 [P] [US4] `backend/tests/integration/test_calls_today.py` — `callsToday`가 `fx_raw_response`의 오늘 행 수와 일치하는지 검증한다 (FR-024)
- [X] T064 [P] [US4] `backend/tests/integration/test_rate_limit_stops_job.py` — 한도 신호를 받으면 진행 중인 작업이 남은 청크를 포기하고 부분 완료로 끝나며, 사유가 한도임이 남는지 검증한다 (FR-025a, SC-013a)
- ~~T065~~ (2026-09-24 반복에서 삭제 — FR-004a가 빠졌다. 나머지 통화가 없으므로 재확인 호출도 없다)
- [X] T066 [P] [US4] `frontend/tests/RateLimitBanner.test.tsx` — 배너가 전체에 한 번만 뜨고, "지금까지 받은 데이터는 그대로 유효합니다"와 통화별 도달 지점이 포함되는지, 한도 사유가 일반 실패와 구별되어 보이는지 검증한다 (FR-026, SC-012, ui-wireframes W4)

### Implementation for User Story 4

- [X] T067 [US4] `backend/src/ingestion/orchestrator.py`에서 한도 신호를 받으면 남은 청크를 포기하도록 처리한다. **별도 신호 모듈을 만들지 않는다** — 한 번에 한 작업만 도므로 전파 대상이 없다 (research R3-8, 2026-09-24 반복)
- [X] T068 [US4] `backend/src/repository/job.py`에서 한도로 중단된 작업을 부분 완료로 확정한다. 이미 받은 구간은 유효하게 남긴다 (FR-026)
- [X] T069 [US4] `backend/src/ingestion/orchestrator.py`에서 한도 신호를 받으면 `rate_limited` 이벤트를 발행하고 작업의 `last_error`에 사유를 남긴다. 사유 없이 끝나면 나중에 왜 멈췄는지 알 수 없다 (FR-025a)
- [X] T070 [US4] `backend/src/api/services/timeline.py`에서 한도 소진 상태를 날짜가 바뀔 때 해제한다. 다음 날 사용자가 이어받기를 누르면 정상 동작해야 한다 (FR-002 — 자동 시작은 하지 않는다)
- [X] T071 [P] [US4] `frontend/src/components/collection/RateLimitBanner.tsx`를 만든다. 선택 통화 카드 **위**에 걸고 그 통화의 도달 지점을 제시한다. **다른 통화로 전환해도 소진 상태는 유지된다** — 전환하면 풀린다고 오해하면 헛수고한다 (ui-wireframes W4)
- [X] T072 [US4] `frontend/src/app/fx/collection/page.tsx` 상단에 호출 수를 한 줄로 넣고 **"참고 지표입니다 — 한도 판정은 출처 응답으로 합니다"**를 함께 표시한다. 서버 날짜 기준 집계가 실제 리셋과 어긋날 수 있다 (research R3-5)
- [X] T073 [US4] `frontend/src/components/shell/CollectionIndicator.tsx`를 확장한다. **`if (running.length === 0) return null`을 제거해 진행 여부와 무관하게 렌더링하고**, 대기 상태에 `⟳ 수집 현황`을 표시한다(FR-030). 진행 중이면 **단일 통화**를 가리키며 멈춤은 `⚠ USD 응답 없음`, 한도 소진은 `⚠ 한도 소진 — 수집 중단됨`으로 표시한다. 누르면 **그 통화로 전환**되어야 한다 — 이름만 보여주고 갈 수 없으면 사용자가 직접 찾아야 한다 (ui-wireframes W7)
- [X] T074 [P] [US4] `frontend/tests/CollectionIndicator.test.tsx` — 멈춤·한도 상태가 표시기에 반영되는지 검증한다 (ui-wireframes W7)

**Checkpoint**: 네 스토리 모두 독립적으로 동작한다

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T075 [P] `backend/tests/unit/test_no_secret_in_events.py` — 이벤트·로그 어디에도 인증 정보가 나타나지 않는지 정적으로 검사한다 (FR-020, SC-009)
- [X] T076 [P] `backend/tests/unit/test_worker_isolation.py` — `observability/`가 `ingestion/`을 임포트하지 않고, `ingestion/`이 싱크를 모르는지 정적으로 검사한다 (헌법 원칙 IV)
- [X] T077 [P] 헌법 원칙 I 정적 검사 — `backend/src/`에 `requests.`·`time.sleep`이 없는지 확인한다
- [X] T078 [P] 헌법 원칙 VI 정적 검사 — `backend/src/`에 `float(` 사용이 없는지 확인한다
- [X] T079 `backend/` 전체에 mypy strict와 ruff를 통과시킨다
- [X] T080 `frontend/` 전체에 `tsc --noEmit`과 eslint를 통과시킨다. `any` 사용 금지
- [X] T081 `cd backend && .venv/bin/python -m pytest -q --cov=src`로 커버리지 80% 이상을 확인한다. 미만이면 부족한 모듈의 단위 테스트를 보강한다 (헌법 품질 게이트)
- [X] T082 `backend/tests/`와 `frontend/tests/` 전체 스위트가 **네트워크 차단 상태에서** 통과하는지 확인한다 (헌법 원칙 III)
- [X] T083 `CLAUDE.md`의 명령어 절을 갱신한다 — 003이 도입한 `--workers 1` 전제와 수집 로그 파일 경로를 반영한다
- [ ] T084 `specs/003-fx-collection-runtime/quickstart.md`의 검증 시나리오 19개를 순서대로 수동 실행하고 결과를 기록한다. **시나리오 9(한도 소진)는 호출을 많이 쓰므로 하루 한 번만 한다**
- [X] T085 `.env.example`에 003이 추가한 설정값(`STALL_THRESHOLD_SECONDS`, `EVENT_RETENTION_JOBS`, `RECONCILE_INTERVAL_SECONDS`, `COLLECTION_LOG_PATH`)을 주석과 함께 넣는다. 실제 값은 넣지 않는다

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작
- **Foundational (Phase 2)**: Setup 완료 후 — **모든 사용자 스토리를 차단**
- **US1 (Phase 3)**: Foundational 완료 후. 다른 스토리에 의존하지 않는다
- **US2 (Phase 4)**: Foundational 완료 후 시작 가능하나, **US1이 없으면 보여줄 진행이 없다**. 실질적으로 US1 이후
- **US3 (Phase 5)**: Foundational 완료 후. US1의 이벤트 발행(T026)에 의존한다
- **US4 (Phase 6)**: Foundational 완료 후. 중단 전파(T068)가 US1의 오케스트레이터 변경에 의존한다
- **Polish (Phase 7)**: 원하는 스토리가 모두 끝난 뒤

### 스토리 간 의존

```
Setup → Foundational ─┬→ US1 (MVP) ─┬→ US2
                      │             ├→ US3
                      │             └→ US4
                      └→ (US2·US3·US4의 테스트 작성은 선행 가능)
```

US2·US3·US4는 서로 독립이다. US1 완료 후 병렬로 진행할 수 있다.

### Within Each User Story

- 테스트를 먼저 쓰고 **실패를 확인한 뒤** 구현한다 (헌법 원칙 III)
- 모델 → 리포지토리 → 서비스 → 엔드포인트 → 화면 순
- 한 스토리를 끝내고 다음 우선순위로 넘어간다

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/db/models.py` | T006, T007 |
| `backend/src/ingestion/orchestrator.py` | T026, T067, T069 |
| `backend/src/worker/runner.py` | T022, T029, T058 |
| `backend/src/api/routes/collection.py` | T040, T041, T056 |
| `backend/src/api/routes/collect.py` | T025, T089 |
| `backend/src/api/collection_stream.py` | T041, T042, T057 |

| `frontend/src/stores/collectionStore.ts` | T044, T061, T088 |
| `frontend/src/app/fx/collection/page.tsx` | T047, T072, T086 |
| `backend/src/observability/events.py` | T010, T062 |

---

## Parallel Example: User Story 1

```bash
# US1의 테스트를 한꺼번에 작성 (서로 다른 파일):
Task: "test_worker_runs_collection.py — 워커가 실제로 수집을 돌린다"
Task: "test_worker_lifecycle.py — 앱 수명과 함께 시작·종료"
Task: "test_reconcile.py — 진행 중으로 남은 작업이 0건"
Task: "test_resume_creates_new_job.py — 이어받기는 새 작업"
Task: "test_no_duplicate_fetch.py — 외부 호출 0회"
Task: "test_currency_isolation.py — 통화 간 격리"
```

---

## Implementation Strategy

### MVP First (User Story 1만)

1. Phase 1 Setup 완료
2. Phase 2 Foundational 완료 (**모든 스토리를 차단하므로 최우선**)
3. Phase 3 US1 완료
4. **멈추고 검증**: quickstart 시나리오 1·2·3·6·7·17·18로 US1을 독립 검증
5. 이 시점에 **"환율 데이터를 실제로 내려받는다"는 목표가 달성된다**

### Incremental Delivery

1. Setup + Foundational → 기반 완성
2. US1 → quickstart 1·2·3·6·7·17·18 → **MVP**
3. US2 → quickstart 4·5·10 → 진행이 보이고 통화를 고를 수 있다
4. US3 → quickstart 11·12·13·14 → 기록이 남는다
5. US4 → quickstart 9·16 → 한도가 보인다
6. Polish → quickstart 15·17

---

## Notes

- `[P]` = 서로 다른 파일, 의존 없음
- 테스트 묶음 작성 → 실패 확인 → 구현 순서를 지킨다. **구현 후에도 실패가 남으면 중단하고
  사용자에게 보고한다** (헌법 v5.1.0 원칙 III, NON-NEGOTIABLE)
- 요구사항을 새로 만들거나 바꾸면 `plan.md` 추적성과 이 문서의 참조를 **같은 작업 단위에서**
  갱신한다 (헌법 명세 작성 규약)
- 태스크마다 또는 논리적 묶음마다 커밋한다
- 체크포인트에서 멈춰 스토리를 독립 검증할 수 있다
