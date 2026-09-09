# Tasks: 외환 분석 화면 통합과 전역 내비게이션 셸

**Input**: Design documents from `/specs/002-fx-analysis-workspace/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 v5.0.0 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.

1. 해당 단계의 테스트 태스크를 **묶음 단위로** 모두 작성한다
2. 테스트가 **실패하는 것을 확인**한다. 이 단계의 실패는 예정된 것이므로 중단하지 않는다
3. 구현 태스크를 진행한다
4. **구현을 마친 뒤에도 실패가 남으면 즉시 중단하고, 실패한 테스트와 원인을 사용자에게 보고한다.**
   통과하던 테스트가 깨진 경우에도 같다

커버리지 80% 미만은 머지 차단. 전체 스위트는 **네트워크 없이** 통과해야 한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·테스트·인도할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US5)

## Path Conventions

plan.md의 웹 애플리케이션 구조를 따른다: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`

> **001 재사용 원칙**: 수집·저장·계산 계층은 그대로 쓴다. `simulation/spread_calc.py`는
> **변경하지 않는다** — 같은 입력에 다른 결과가 나오면 FR-023과 001의 재현성 보장이 함께 깨진다.

---

## Phase 1: Setup

**Purpose**: 신규 설정값 선언. 새 의존성은 없다.

- [X] T001 [P] `backend/src/config/settings.py`에 표 기본 행 수(`daily_page_size`, 기본 30)와 새로고침 잠금 만료(`today_refresh_lock_ttl_seconds`)를 설정으로 선언 (헌법 원칙 II, research R2-8)
- [X] T002 [P] 프로젝트 루트 `.env.example`에 T001의 신규 키와 기본값을 주석과 함께 추가

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 확정/잠정 저장 기반과 전역 셸. **모든 사용자 스토리를 차단한다.**

### Tests ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T003 [P] `backend/tests/unit/test_orm_types.py`를 확장해 `FxRate.is_provisional`이 불리언으로 매핑되고 NOT NULL이며 기본값이 거짓인지 검증
- [X] T004 [P] `backend/tests/integration/test_migrations.py`를 확장해 신규 리비전 적용 후 ORM 메타데이터와 실제 스키마가 일치하고, 기존 행이 `is_provisional = FALSE`로 채워지는지 검증
- [X] T005 [P] `backend/tests/integration/test_provisional_repo.py`에 확정 전용 조회와 잠정 포함 조회가 구분되는지 테스트 작성 (FR-042a, data-model 조회 규약)
- [X] T006 [P] `backend/tests/integration/test_coverage_provisional.py`에 **잠정 레코드를 저장해도 `covered_through`가 전진하지 않음**을 테스트 작성 (FR-037b, research R2-2)
- [X] T007 [P] `frontend/tests/Sidebar.test.tsx`에 셸 테스트 작성 — 메뉴 8개, 외환·설정만 활성, "준비중" 항목은 링크가 아니고 키보드 포커스 대상이 아님 (FR-002, FR-005)

### Implementation

- [X] T008 `backend/src/db/models.py`의 `FxRate`에 `is_provisional` 컬럼 추가 (data-model 1절)
- [X] T009 `backend/src/db/migrations/versions/`에 `is_provisional` 리비전 생성 — 기존 행을 `FALSE`로 채운다. `quote_date` 상한은 DB 제약이 아니라 문서상 검증 규칙이므로 마이그레이션 대상이 아니며, "오늘 이하" 완화는 `repository/fx_rate.py`(T010)와 data-model 문서에 반영한다
- [X] T010 `backend/src/repository/fx_rate.py`에 확정/잠정 구분 조회와 upsert 구현 — 확정 전용 조회 경로가 SC-003의 근거다 (FR-042a)
- [X] T011 `backend/src/repository/coverage.py`에 **잠정은 커버리지에 반영하지 않음**을 코드와 주석으로 명시 (FR-037b)
- [X] T012 [P] `frontend/src/components/shell/Sidebar.tsx`에 사이드바 구현 — 메뉴 정적 정의에 준비 여부 포함, 미준비 항목은 링크·포커스 제외 (research R2-9, ui-wireframes W1)
- [X] T013 [P] `frontend/src/components/shell/TopBar.tsx`에 현재 화면 이름 표시 구현 (FR-004)
- [X] T014 [P] `frontend/src/components/shell/CollectionIndicator.tsx`에 수집 진행 표시기 구현 — 진행 중일 때만 노출, 클릭 시 수집 현황으로 이동 (FR-049)
- [X] T015 `frontend/src/app/layout.tsx`에 셸(사이드바 + 상단 바)을 적용하고 본문 영역을 중첩 레이아웃으로 구성
- [X] T016 `frontend/src/app/page.tsx`를 대시보드 자리로 바꾸고 준비 중 안내를 표시 (research R2-10)
- [X] T017 001의 라우트를 이관 — `/chart`·`/spreads`·`/collection`을 제거하고 `/fx`·`/settings`·`/fx/collection`으로 옮긴다 (research R2-10). **미구현 자산군의 라우트는 만들지 않는다**
- [X] T018 [P] `frontend/src/stores/fxWorkspaceStore.ts`에 선택 통화·선택 날짜·차트 기간을 **단일 상태**로 구현 (contracts/ui-interaction)

**Checkpoint**: 셸이 뜨고 메뉴 이동이 되며, 잠정 컬럼이 스키마에 존재한다.

---

## Phase 3: User Story 1 — 한 화면에서 환율과 실거래 기준 가격 확인 (Priority: P1) 🎯 MVP

**Goal**: 통화와 날짜를 고르면 매매기준율과 파생 환율 4종을 한 화면에서 확인한다.

**Independent Test**: 사이드바에서 외환으로 이동해 통화·날짜를 지정했을 때, 요약과 상세 표가
한 화면에 나타나고 고시 없는 날의 행이 없는지로 검증한다.

### Tests for User Story 1 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T019 [P] [US1] `backend/tests/integration/test_latest_api.py`에 요약 조회 테스트 작성 — 최근 값, 통화쌍, 기준 날짜, `change.absolute`·`percent`·`direction`, `isProvisional` (FR-011~014)
- [X] T020 [US1] `backend/tests/integration/test_latest_api.py`에 데이터 없음 테스트 추가 — `status: "no_data"`
- [X] T021 [P] [US1] `backend/tests/integration/test_daily_api.py`에 표 조회 테스트 작성 — 파생 4종이 **문자열**로 반환되고, **고시 없는 날의 행이 없으며**, 날짜가 내림차순인지 (FR-020, FR-021, FR-023)
- [X] T022 [US1] `backend/tests/integration/test_daily_api.py`에 페이징 테스트 추가 — `before`·`limit`·`hasMore`·`oldestReturned` (FR-026)
- [X] T023 [P] [US1] `backend/tests/unit/test_daily_derive.py`에 표의 파생값이 `simulation/spread_calc.py`의 결과와 **정확히 일치**함을 검증 (FR-023, FR-027)
- [X] T024 [P] [US1] `frontend/tests/RateSummary.test.tsx`에 요약 렌더 테스트 작성 — 큰 숫자, 기준 날짜, 방향 기호가 색과 함께 표시됨 (FR-013)
- [X] T025 [P] [US1] `frontend/tests/DailyTable.test.tsx`에 표 렌더 테스트 작성 — 결측 날짜 행 없음, "현재 스프레드를 각 날짜에 적용한 가정" 안내 존재 (FR-024)

### Implementation for User Story 1

- [X] T026 [US1] `backend/src/api/services/daily_query.py`에 일자별 조회와 파생 산출 조합 구현 — 계산은 `simulation/spread_calc.py`를 **호출만** 한다 (헌법 원칙 IV)
- [X] T027 [US1] `backend/src/api/routes/latest.py`에 `GET /api/fx/latest` 구현 — 미수집 구간이 있으면 001의 `api/services/collection_gate.py`를 재사용해 임계값 분기를 적용한다 (FR-048, contracts/rest-api)
- [X] T028 [US1] `backend/src/api/routes/daily.py`에 `GET /api/fx/daily` 구현 — 금액·비율은 문자열로 직렬화하고, 미수집 구간에는 `collection_gate`를 적용해 임계값 초과 시 `202`를 반환한다 (헌법 원칙 VI, FR-048, research R2-5)
- [X] T029 [P] [US1] `frontend/src/lib/types.ts`에 `latest`·`daily` 응답 타입 추가 — 금액은 `DecimalString`
- [X] T030 [P] [US1] `frontend/src/components/fx/CurrencyTabs.tsx`에 통화 분절 컨트롤 구현 — 코드와 한글 이름 병기 (FR-006)
- [X] T031 [P] [US1] `frontend/src/components/fx/RateSummary.tsx`에 요약 카드 구현 (ui-wireframes W2)
- [X] T032 [P] [US1] `frontend/src/components/fx/DailyTable.tsx`에 상세 표와 "더 보기" 구현. 선택 날짜가 표시 범위 밖이면 `before = 선택날짜 + 1일`로 다시 받아 그 날짜가 첫 행이 되게 한다 (FR-020~026, FR-022a)
- [X] T033 [US1] `frontend/src/app/fx/page.tsx`에 통화 탭·요약·표를 조립하고 통화 변경 시 갱신 배선 (FR-007)
- [X] T034 [US1] `frontend/src/stores/fxWorkspaceStore.ts`에 진입 시 `GET /api/fx/coverage`를 한 번 받아 보관하고, 선택 날짜가 현재 통화의 조회 가능 범위를 벗어나면 범위를 알리고 상태를 바꾸지 않도록 구현 (FR-010, research R2-6, contracts/ui-interaction)

**Checkpoint**: US1만으로 "이 통화가 이 시점에 얼마였나"가 한 화면에서 답해진다. **MVP 완성.**

---

## Phase 4: User Story 2 — 추이를 보고 특정 시점을 짚어낸다 (Priority: P2)

**Goal**: 기간별 추이를 보고 차트 위에서 시점을 지정하면 세 영역이 함께 움직인다.

**Independent Test**: 기간을 선택해 차트를 띄운 뒤 임의 시점을 지정했을 때, 강조선·날짜 입력·표
강조 행이 모두 같은 날짜를 가리키는지로 검증한다.

### Tests for User Story 2 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T035 [P] [US2] `backend/tests/integration/test_series_provisional.py`에 시계열 응답의 `isProvisional` 필드 테스트 작성 (FR-017a)
- [X] T036 [P] [US2] `backend/tests/unit/test_downsample_endpoints.py`에 **다운샘플링 후에도 첫 점과 끝 점이 항상 남는지** 테스트 작성 (FR-017b, research R2-4 — 현재 구현이 만족하지만 검증이 없어 교체 시 조용히 깨진다)
- [X] T037 [P] [US2] `frontend/tests/TrendChart.test.tsx`에 차트 테스트 작성 — 선택 날짜 강조선, 결측 구간 미연결, 잠정 구간 구분, **차트의 마지막 표시 시점이 요약의 기준 날짜와 일치** (FR-016, FR-017, FR-017a, SC-007a)
- [X] T038 [US2] `frontend/tests/selectedDate.test.tsx`에 연동 테스트 작성 — 세 경로 중 어디서 바꿔도 나머지가 따라오고, **날짜 변경만으로는 네트워크 호출이 발생하지 않음** (FR-009, SC-002, contracts/ui-interaction 갱신 범위 표)

### Implementation for User Story 2

- [X] T039 [US2] `backend/src/api/routes/series.py`의 응답 포인트에 `isProvisional`을 추가 (contracts/rest-api 변경분)
- [X] T040 [P] [US2] `frontend/src/components/fx/PeriodPresets.tsx`에 기간 프리셋 6단계(1개월/6개월/1년/5년/10년/전체) 구현 (FR-015, spec Assumptions)
- [X] T041 [P] [US2] `frontend/src/components/fx/TrendChart.tsx`에 차트 구현 — 결측 구간 분리, 잠정 구간 스타일 구분, 범례 (FR-017, FR-017a)
- [X] T042 [US2] `frontend/src/components/fx/TrendChart.tsx`와 `frontend/src/stores/fxWorkspaceStore.ts`를 연결해 강조선·날짜 라벨·점 표식을 선택 날짜에 묶고, 차트 지정 시 **가장 가까운 실제 포인트**의 날짜를 선택 (FR-016, contracts/ui-interaction)
- [X] T043 [US2] `frontend/src/components/fx/TrendChart.tsx`에 선택 날짜가 현재 기간 밖일 때의 안내를 구현하고 **선택 날짜를 임의로 바꾸지 않음** (contracts/ui-interaction)
- [X] T044 [US2] `frontend/src/components/fx/PeriodPresets.tsx`에서 `GET /api/fx/coverage`로 통화별 축적 범위를 받아, 프리셋 구간이 그보다 이를 때 실제 범위만 표시하고 그 사실을 알림 (FR-019)

**Checkpoint**: 추이 확인과 시점 지정이 동작한다.

---

## Phase 5: User Story 3 — 스프레드 조정과 기본값 복원 (Priority: P2)

**Goal**: 설정에서 통화별 스프레드를 조정하고 언제든 기본값으로 되돌린다.

**Independent Test**: 값을 바꿔 저장하면 외환 화면의 파생 환율이 바뀌고, 복원하면 원래 값으로
돌아오는지로 검증한다.

### Tests for User Story 3 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T045 [P] [US3] `backend/tests/integration/test_spreads_defaults.py`에 `GET /api/fx/spreads` 확장 테스트 작성 — `defaults` 포함, `isDefault` 판정, 통화 순서 USD→JPY→EUR (FR-027, FR-033)
- [X] T046 [P] [US3] `backend/tests/integration/test_spreads_restore.py`에 복원 테스트 작성 — 통화 지정 시 해당 통화만, 생략 시 전 통화 (FR-031)
- [X] T047 [US3] `backend/tests/integration/test_spreads_restore.py`에 복원값이 **시드 리비전의 기본값과 일치**함을 검증하고, 전 통화 복원 중 일부 실패 시 성공분을 되돌리지 않고 `restored` 목록으로 결과를 알리는지 확인 (FR-031a, data-model 4절)
- [X] T048 [P] [US3] `frontend/tests/SpreadForm.test.tsx`에 설정 폼 테스트 작성 — 통화 순서 고정, 범위 위반 시 **해당 입력 옆** 인라인 오류, 기존 값 유지 (FR-029)
- [X] T049 [P] [US3] `frontend/tests/RestoreDefaultsDialog.test.tsx`에 확인창 테스트 작성 — 무엇이 어떻게 바뀌는지 표시, 취소 시 값 유지 (FR-032, ui-wireframes W4-a)

### Implementation for User Story 3

- [X] T050 [US3] `backend/src/db/spread_defaults.py`에 기본값을 **단일 출처**로 선언하고 시드 리비전과 복원 로직이 함께 참조하도록 정리 (data-model 4절)
- [X] T051 [US3] `backend/src/api/routes/spreads.py`에 `GET` 응답의 `defaults`·`isDefault` 추가와 `POST /api/fx/spreads/restore` 구현
- [X] T052 [P] [US3] `frontend/src/components/settings/SpreadForm.tsx`에 3통화 × 4항목 폼 구현 — 기본값과 다르면 표시 (FR-033, ui-wireframes W4)
- [X] T053 [P] [US3] `frontend/src/components/settings/RestoreDefaultsDialog.tsx`에 복원 확인창 구현 — 변경 전후 값을 나란히 제시
- [X] T054 [US3] `frontend/src/app/settings/page.tsx`에 설정 화면 조립과 "모든 과거 날짜에 동일 적용" 안내 배치 (FR-035)
- [X] T055 [US3] `frontend/src/app/settings/page.tsx`와 `frontend/src/stores/fxWorkspaceStore.ts`를 연결해 저장·복원 후 요약과 표만 갱신하고 **차트는 다시 받지 않음** (FR-034, contracts/ui-interaction 갱신 범위 표)

**Checkpoint**: 스프레드 조정과 복원이 동작하고 파생 환율에 반영된다.

---

## Phase 6: User Story 4 — 오늘 환율 새로고침 (Priority: P3)

**Goal**: 오늘 값을 잠정으로 받아와 확정값과 구분해 보여준다.

**Independent Test**: 새로고침 후 오늘 값이 갱신되고 갱신 시각이 바뀌며, 확정값과 구분되어
표시되는지로 검증한다.

### Tests for User Story 4 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T056 [P] [US4] `backend/tests/integration/test_lock_scope.py`에 잠금 범위 테스트 작성 — 수집 잠금과 새로고침 잠금이 **같은 통화에서 공존**하고 서로 차단하지 않음 (FR-036a, research R2-8)
- [X] T057 [P] [US4] `backend/tests/integration/test_today_refresh.py`에 새로고침 테스트 작성 — `updated` / `no_quote_today` 분기, `fetchedAt` 포함, 값 생성 금지 (FR-039)
- [X] T058 [US4] `backend/tests/integration/test_today_refresh.py`에 중복 요청 테스트 추가 — `joinedExisting: true`, 외부 호출 1회 (FR-036b, SC-008)
- [X] T059 [US4] `backend/tests/integration/test_today_refresh.py`에 실패 테스트 추가 — 외부 실패 시에도 저장된 과거 데이터와 표시 중인 값이 유효 (FR-040)
- [X] T060 [P] [US4] `backend/tests/integration/test_provisional_transition.py`에 **잠정 → 확정 전환** 테스트 작성 — 날짜가 지난 뒤 증분 수집이 그 날짜를 건너뛰지 않고 값을 덮으며 `is_provisional`이 거짓이 됨. **잠정 시점과 확정 시점의 원본 응답이 `fx_raw_response`에 모두 남아 값 변화를 대조할 수 있는지도 함께 검증한다** (FR-037a, FR-037b, FR-037d, FR-043, 헌법 원칙 V)
- [X] T061 [P] [US4] `backend/tests/integration/test_provisional_isolation.py`에 확정 구간 불변 테스트 작성 — 오늘 값을 여러 번 갱신해도 과거 확정값이 변하지 않음 (FR-042, SC-003)
- [X] T062 [P] [US4] `frontend/tests/TodayRefresh.test.tsx`에 새로고침 UI 테스트 작성 — 잠정 배지, 갱신 시각, 실패 시 기존 값 유지 (ui-wireframes W3-b·W3-c)

### Implementation for User Story 4

- [X] T063 [US4] `backend/src/db/models.py`의 `FxCollectionLock`에 `scope`를 추가하고 기본 키를 `(scope, currency_code)`로 변경 (data-model 3절)
- [X] T064 [US4] `backend/src/db/migrations/versions/`에 잠금 범위 리비전 생성 — 기존 행에 `scope = 'collection'`을 채운 뒤 기본 키 재정의
- [X] T065 [US4] `backend/src/repository/collection_lock.py`에 범위 인자를 추가하고 스테일 회수 만료를 범위별로 적용 (research R2-8)
- [X] T066 [US4] `backend/src/ingestion/today.py`에 오늘 하루치 조회와 잠정 저장 구현 — **커버리지를 갱신하지 않는다** (FR-037b, research R2-2)
- [X] T067 [US4] `backend/src/api/services/today_refresh.py`에 잠금 획득·중복 합류·실패 처리 구현 (FR-036b, FR-040)
- [X] T068 [US4] `backend/src/api/routes/today.py`에 `POST /api/fx/today/refresh` 구현 (contracts/rest-api)
- [X] T069 [P] [US4] `frontend/src/components/fx/TodayRefresh.tsx`에 새로고침 버튼과 갱신 시각 표시 구현 (FR-038)
- [X] T070 [US4] `frontend/src/components/fx/`의 `RateSummary.tsx`·`DailyTable.tsx`·`TrendChart.tsx`에 잠정 구분 표시를 연결 — 잠정으로 산출된 파생 환율에도 표시가 따라붙어야 한다 (FR-014, FR-025, FR-041, SC-007)

**Checkpoint**: 오늘 값이 잠정으로 표시되고 확정 구간을 오염시키지 않는다.

---

## Phase 7: User Story 5 — 표 내려받기 (Priority: P3)

**Goal**: 표의 내용을 정밀도 손실 없이 파일로 내려받는다.

**Independent Test**: 내려받은 파일의 수치가 화면 표시값과 정밀도까지 일치하는지로 검증한다.

### Tests for User Story 5 ⚠️ 작성 → 실패 확인 → 구현 (구현 후 실패 시 중단·보고)

- [X] T071 [P] [US5] `frontend/tests/csv.test.ts`에 CSV 조립 테스트 작성 — 서버가 준 문자열이 **그대로** 담기고 자릿수가 잘리지 않음, 잠정 행 구분, 통화·구간·스프레드 메타 포함 (FR-045~047)
- [X] T072 [US5] `frontend/tests/csv.test.ts`에 쉼표 포함 값의 인용 처리 테스트 추가

### Implementation for User Story 5

- [X] T073 [P] [US5] `frontend/src/lib/csv.ts`에 CSV 조립 구현 — **`Number()`·`parseFloat()`를 쓰지 않는다.** 한 번이라도 끼면 헌법 원칙 VI가 파일 출력 단계에서 무너진다 (research R2-7)
- [X] T074 [US5] `frontend/src/components/fx/DailyTable.tsx`에 내려받기 동작 연결 (FR-044)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 헌법 준수 검증과 전체 통합 확인

- [X] T075 [P] `frontend/tests/noClientSideFinance.test.ts`에 정적 검사 추가 — `src/lib/csv.ts`와 표 관련 컴포넌트에 `Number(`·`parseFloat(`가 없고 파생 환율을 클라이언트에서 계산하지 않음 (헌법 원칙 VI, research R2-5·R2-7)
- [X] T076 [P] `frontend/tests/noUnbuiltAssetRoutes.test.ts`에 정적 검사 추가 — 미구현 자산군의 라우트 디렉토리와 API 호출이 존재하지 않음 (헌법 원칙 IX, research R2-9)
- [X] T077 [P] `backend/tests/unit/test_today_isolation.py`에 정적 검사 추가 — `ingestion/today.py`가 커버리지 갱신 함수를 호출하지 않음 (FR-037b)
- [X] T078 [P] `backend/tests/unit/test_layer_boundaries.py`를 확장해 `api/services/daily_query.py`가 계산을 직접 수행하지 않고 `simulation/`을 호출만 하는지 검증 (헌법 원칙 IV)
- [X] T079 `backend/.venv/bin/python -m pytest --cov=src --cov-fail-under=80` 통과 확인 및 미달 시 테스트 보완
- [X] T080 `backend/.venv/bin/python -m mypy --strict src`, `cd frontend && npm run typecheck`, `npx eslint src` 통과 확인
- [X] T081 네트워크를 차단한 상태에서 `backend/tests/`와 `frontend/tests/` 전체 스위트 통과 확인 (헌법 원칙 III)
- [X] T082 [P] `backend/tests/integration/test_performance.py`에 성능 측정 추가 — 요약·표·시계열 응답이 병렬 기준 3초 이내(SC-009a), 스프레드 변경 후 재산출 2초 이내(SC-005). 차트 조작 1초(SC-009)는 UI 수동 확인
- [X] T083 `specs/002-fx-analysis-workspace/quickstart.md`의 검증 시나리오 13개를 순서대로 수동 실행하고 결과 기록 (시나리오 12가 SC-007b를 검증한다)
- [X] T084 [P] `backend/src/`와 `frontend/src/` 신규·변경 파일의 주석·docstring이 한국어인지 점검 (헌법 원칙 VIII)
- [X] T085 001 산출물의 라우트 참조를 갱신 — `quickstart.md`와 `contracts/ui-sketches.md`가 제거된 `/chart`·`/spreads`를 가리키지 않도록 정리 (research R2-10)
- [X] T086 [US4] `frontend/tests/TodayRefresh.test.tsx`에 통화 변경 경합 테스트 작성 — 응답이 늦게 도착했을 때 사용자가 통화를 바꿨다면 결과·오류가 새 통화 화면에 반영되지 않고, busy는 풀려 다시 받을 수 있음 (FR-036c)
- [X] T087 [US4] `frontend/src/components/fx/TodayRefresh.tsx`에 요청 귀속 구현 — 요청 시점의 통화를 클로저에 담고 응답 시점의 통화와 비교한다. 안내·오류는 어느 통화의 것인지와 함께 보관해 통화가 바뀌면 자연히 감춰지게 한다 (FR-036c)
- [X] T088 `backend/src/ingestion/today.py`의 `store_provisional`에 잠정 불변식 강제 — 오늘이 아닌 날짜는 잠정으로 저장할 수 없다. 날짜를 오늘로 제한하면 "통화당 최대 1행"은 기본 키에서 자동으로 따라온다. `backend/tests/integration/test_provisional_invariant.py`에 6건 검증 (FR-037c)
- [X] T089 잠정 잔존 탐지·노출 구현 — `backend/src/repository/fx_rate.py`의 `oldest_stale_provisional`로 통화별 가장 오래된 잔존을 찾고, `GET /api/fx/coverage`가 `staleProvisional`로 내려주며, `frontend/src/components/CollectionStatus.tsx`가 해당 통화 행에 날짜와 해소 방법을 함께 표시한다. **오늘 날짜의 잠정은 잔존으로 세지 않는다** — 매일 경고가 떠서 신호가 무의미해진다 (FR-043a, FR-043b, SC-007b)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음
- **Foundational (Phase 2)**: Setup 완료 후. **모든 사용자 스토리를 차단**
- **User Stories (Phase 3~7)**: Foundational 완료 후
- **Polish (Phase 8)**: 인도하려는 모든 스토리 완료 후

### User Story Dependencies

- **US1 (P1)**: Foundational 후 시작. 다른 스토리에 의존하지 않음 — **MVP**
- **US2 (P2)**: Foundational 후 시작 가능. T038(연동 테스트)은 US1의 표가 있어야 검증되므로 T032 이후
- **US3 (P2)**: Foundational 후 시작 가능. T055(갱신 배선)는 US1의 요약·표에 연결하므로 T033 이후
- **US4 (P3)**: Foundational 후 시작 가능. T070(잠정 표시 연결)는 US1·US2의 화면에 붙으므로 두 스토리 이후
- **US5 (P3)**: US1의 표(T032)에 의존

### Within Each User Story

- 테스트 묶음 작성 → 실패 확인 → 구현 순서를 지킨다. **구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다** (헌법 v5.0.0 원칙 III, NON-NEGOTIABLE)
- 스키마 → 리포지토리 → 서비스 → 엔드포인트 → UI 순
- 순수 함수와 정적 검사는 언제든 병렬 작업 가능

### Parallel Opportunities

> **원칙**: 같은 파일을 대상으로 하는 태스크는 병렬 실행할 수 없다. `[P]`는 대상 파일이 서로
> 다른 경우에만 부착돼 있다.

- **Phase 1**: T001·T002 병렬
- **Phase 2**: 테스트 T003~T007 전부 병렬 → 구현에서 T012·T013·T014·T018 병렬(프론트 4종), T008~T011은 순차(모델→리비전→리포지토리)
- **Phase 3**: 테스트 T019·T021·T023·T024·T025 병렬(같은 파일의 T020은 T019 뒤, T022는 T021 뒤). 구현에서 T029~T032 병렬, T026~T028은 순차, T033·T034는 조립·배선이라 마지막
- **Phase 4**: T035·T036·T037 병렬(T038은 US1의 표에 의존하므로 T032 이후). T040·T041 병렬
- **Phase 5**: T045·T046·T048·T049 병렬(T047은 T046과 같은 파일이므로 그 뒤). T052·T053 병렬
- **Phase 6**: T056·T057·T060·T061·T062 병렬(T058·T059는 T057과 같은 파일이므로 그 뒤). T063~T068은 순차(모델→리비전→잠금→수집→서비스→엔드포인트)
- **Phase 8**: T075~T078·T082·T084 병렬
- Foundational 완료 후에는 인력이 있으면 US1~US5를 병렬로 진행 가능

---

## Implementation Strategy

### MVP 범위

**Phase 1 + Phase 2 + Phase 3 (US1)** = T001~T034, 34개 태스크.

이 지점에서 "사이드바로 외환에 들어가 통화와 날짜를 고르면 매매기준율과 실거래 기준 4종 가격이
한 화면에 나온다"는 완결된 가치가 나온다. 001의 탭 왕복이 사라진다.

### 점진적 인도

| 증분 | 태스크 | 추가되는 가치 |
|------|--------|---------------|
| MVP | T001~T034 | 셸 + 한 화면 조회 |
| +US2 | T035~T044 | 추이 확인과 시점 지정 |
| +US3 | T045~T055 | 스프레드 조정과 복원 |
| +US4 | T056~T070 | 오늘 값 최신화 |
| +US5 | T071~T074 | 표 내려받기 |
| 완료 | T075~T085 | 헌법 준수 검증과 운영 준비 |
| 보완 | T086~T087 | 명세 보완(FR-036c) 반영 |

### 위험 순서

1. **Phase 2의 잠정 저장 기반(T008~T011)이 가장 먼저 위험하다.** 특히 T011(커버리지 미반영)이
   틀리면 US4의 확정 전환이 영원히 일어나지 않는데, 증상이 며칠 뒤에야 드러난다. T006 테스트를
   먼저 통과시킨다.
2. **T017(라우트 이관)이 그다음이다.** 001의 화면 4개를 옮기는 작업이라 한 번에 깨질 수 있다.
   T007(셸 테스트)을 먼저 통과시킨 뒤 진행한다.
3. **T063~T065(잠금 범위 변경)는 기본 키를 바꾼다.** 001이 세운 동시성 보장을 건드리므로
   T056(잠금 범위 테스트)을 먼저 통과시킨다.

### 001과의 관계

이번 기능은 001의 수집·저장·계산 계층을 **변경하지 않는다**. 예외는 세 곳이며 모두 확장이다.

- `fx_rate`에 컬럼 추가 (기존 행 영향 없음)
- `fx_collection_lock`의 기본 키 확장 (실행 중에만 존재하는 휘발성 데이터)
- `coverage.py`에 규칙 명시 (동작 변경 없음 — 잠정을 저장하는 경로가 새로 생길 뿐)

`simulation/spread_calc.py`와 `downsample.py`는 **읽기만 하고 고치지 않는다.**
