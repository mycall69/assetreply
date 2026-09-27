---

description: "Task list template for feature implementation"
---

# Tasks: 일자별 환율 표의 스크롤 탐색과 기간 단위 전환

**Input**: Design documents from `/specs/004-fx-table-scroll-periods/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: **필수.** 헌법 v5.2.0 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
테스트 작성 → 실패 확인 → 구현. 구현 후에도 실패가 남으면 중단하고 사용자에게 보고한다.

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 의존 없음)
- **[Story]**: 소속 사용자 스토리 (US1~US3)
- 파일 경로를 반드시 포함한다
- **ID는 안정적 참조다.** 반복(iteration)으로 추가된 태스크는 번호를 이어 붙이므로 ID
  순서가 실행 순서와 일치하지 않을 수 있다. 실행 순서는 페이즈가 정한다
- 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 최소한의 준비. **신규 의존성·마이그레이션이 없다** — 001~003이 쌓아 둔 데이터를
다르게 질의할 뿐이다.

- [X] T001 [P] `frontend/src/lib/types.ts`에 `PeriodUnit`(`"daily" | "weekly" | "monthly"`)과 `PeriodRow` 타입을 추가한다. `PeriodRow`는 002의 `DailyRow`에 `periodFrom`·`periodTo`(필수), `shiftedFrom`(선택), `isOngoing`(필수)을 더한 형태다 (contracts/rest-api)
- [X] T002 [P] `backend/tests/unit/test_period_bounds.py` 파일을 만든다 — 구간 경계 계산의 기준을 고정할 자리다. 주는 월요일~일요일, 월은 1일~말일이다 (spec Assumptions)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 기준일 선정과 구간 판정. 모든 스토리가 여기에 의존한다.

**⚠️ CRITICAL**: 이 단계가 끝나기 전에는 어떤 사용자 스토리도 시작할 수 없다

- [X] T003 `backend/tests/unit/test_period_bounds.py`에 구간 경계 테스트를 작성한다 — 주 경계(월~일), 월 경계(1일~말일), 윤년 2월, 연말연시를 검증한다. **실패를 확인한 뒤** T004로 간다 (FR-008)
- [X] T004 `backend/src/api/services/period_rows.py`에 `period_bounds(date, unit)`을 만든다. 날짜가 속한 구간의 시작·끝을 돌려준다. 일 단위는 `(date, date)`다 (FR-008, data-model 3절)
- [X] T005 [P] `backend/tests/unit/test_period_rows.py`를 작성한다 — 기준일 옮김 판정(`shifted_from`)과 진행 중 판정(`is_ongoing`)을 검증한다. **2026년 실측 결측일**(금요일 5-01·7-17, 말일 1-31·2-28·5-31)을 사례로 쓴다 (FR-013, FR-015a)
- [X] T006 `backend/src/api/services/period_rows.py`에 `shifted_from(quote_date, unit)`을 만든다. 주 단위는 그 날짜가 **금요일이 아니면** 그 주의 금요일을, 월 단위는 **그 달의 말일이 아니면** 말일을 돌려준다. 맞으면 `None`이다 (FR-013, FR-014, data-model 4절)
- [X] T007 `backend/src/api/services/period_rows.py`에 `is_ongoing(period_to, today, unit)`을 만든다. **구간의 끝이 오늘이거나 그 뒤면 진행 중**이다 — 오늘이 아직 끝나지 않았기 때문이다. 일 단위는 항상 거짓이라 단위를 인자로 받는다 — 하루는 그 날짜로 끝난다 (FR-015a, data-model 5절)
- [X] T008 [P] `backend/tests/integration/test_period_page.py`를 작성한다 — 주·월 단위 페이지 조회가 **구간별 마지막 고시일**만 돌려주는지, 커서(`before`)가 기준일 기준으로 동작하는지, **고시가 하나도 없는 구간에는 행이 생기지 않는지**, **축적 구간이 한 주·한 달에 못 미치면 행이 한 개 이하로 나오되 오류가 아닌지** 검증한다. 빈 구간에 행이 생기면 그것은 값을 지어낸 것이다 (FR-008, FR-015, SC-006, SC-009)
- [X] T009 `backend/src/repository/fx_rate.py`에 `quote_dates_before()`·`rows_on()`을, `backend/src/api/services/period_rows.py`에 `period_page()`를 만든다. 리포지토리는 **고시일만** 최신순으로 주고, 구간 묶기는 서비스가 한다 — 내림차순이라 각 구간에서 처음 만나는 날짜가 그 구간의 마지막 고시일이다. **구간 경계를 SQL에 두지 않는다**: `EXTRACT(WEEK ...)`는 MySQL이 일요일 시작, PostgreSQL이 ISO 월요일 시작이라 DB를 바꾸면 **오류 없이 다른 묶음**이 된다(헌법 DB 운영 규약). **금요일·말일을 먼저 찾는 2단계 질의도 쓰지 않는다** — 금요일은 그 주의 마지막 영업일이라 결과가 같다. 존재하는 행만 뽑으므로 보간 경로가 생길 자리가 없다 (FR-008, FR-012, SC-006, research R4-2·R4-3)
- [X] T010 `backend/src/api/services/daily_query.py`의 `daily_page`에 `unit` 매개변수를 더한다. `daily`면 기존 `page_before`를, 그 외에는 `period_page_before`를 쓴다. 반환 행에 `period_from`·`period_to`·`shifted_from`·`is_ongoing`을 실어 보낸다

**Checkpoint**: 기준일 선정과 구간 판정 준비 완료 — 사용자 스토리 착수 가능

---

## Phase 3: User Story 1 - 스크롤로 과거를 훑어본다 (Priority: P1) 🎯 MVP

**Goal**: 표를 아래로 스크롤하면 이전 데이터가 이어서 나타난다. `더 보기` 버튼이 사라진다.

**Independent Test**: 표를 끝까지 스크롤해 이전 데이터가 자동으로 이어지는지 관찰한다.
기간 단위 기능 없이도 검증할 수 있다.

### Tests for User Story 1 ⚠️

> **이 테스트들을 먼저 작성하고 실패를 확인한 뒤 구현한다**

- [X] T011 [P] [US1] `frontend/tests/useInfiniteScroll.test.ts` — 스크롤이 끝에 닿으면 콜백이 불리고, **이미 불러오는 중이면 다시 부르지 않는지** 검증한다. 중복 호출은 오류 없이 성공하면서 같은 행을 두 번 그린다. **감시 지점이 처음부터 화면 안에 있으면(표가 화면보다 짧음) 스크롤 없이도 콜백이 불리는지** 함께 본다 (FR-005, FR-001a, SC-004, SC-001b)
- [X] T012 [P] [US1] `frontend/tests/DailyTableScroll.test.tsx` — `더 보기` 버튼이 **없는지**, 끝에 도달하면 그 사실이 **알림 역할로** 표시되는지, 실패 시 기존 행이 남고 재시도 수단이 있는지 검증한다. 함께 `frontend/tests/DailyTable.test.tsx:70`의 `더 보기가 있으면 버튼을 노출한다`를 **제거한다** — 002 FR-026이 요구한 것은 "이어서 볼 수 있어야 한다"이지 버튼이 아니었다. 남겨 두면 US1 체크포인트에서 전체 테스트가 실패한다 (FR-001, FR-002, FR-004)
- [X] T013 [P] [US1] `frontend/tests/fxWorkspaceScroll.test.ts` — 새 행이 **기존 배열 끝에 덧붙는지**(교체가 아니라), 과거 날짜 선택 시 배열이 비워지는지 검증한다 (FR-003, FR-005a, SC-002)

### Implementation for User Story 1

- [X] T014 [US1] `frontend/src/hooks/useInfiniteScroll.ts`를 만든다. 감시 대상이 화면에 들어오면 콜백을 부른다. **처음부터 화면 안에 있어도 부른다** — 스크롤 이벤트가 아니라 가시성을 신호로 삼는다. 이미 불러오는 중이거나 끝에 도달했으면 부르지 않는다 (FR-005, FR-001a, SC-004, SC-001b)
- [X] T015 [US1] `frontend/src/components/fx/DailyTable.tsx`에서 `더 보기` 버튼을 제거하고 표 끝에 감시 지점을 둔다. 상태에 따라 불러오는 중·끝 도달·실패를 표시한다. **셋은 알림 역할이므로 화면에 나타날 때 보조 기술이 읽는다** — 눈으로 보는 사용자만 끝에 도달했음을 알면 FR-002가 절반만 성립한다. **일 단위에서는 끝이 멀다 — 그것은 의도된 것이고 막지 않는다** (FR-001, FR-002, FR-004, SC-001a, ui-wireframes W3·접근성)
- [X] T016 [US1] `frontend/src/stores/fxWorkspaceStore.ts`의 이어 보기가 새 행을 **기존 배열 끝에 덧붙이도록** 한다. 전체를 교체하면 보던 위치가 처음으로 튄다 (FR-003, SC-002, research R4-6)
- [X] T017 [US1] `frontend/src/stores/fxWorkspaceStore.ts`에 과거 날짜 선택 시 **표를 새로 받는** 경로를 만든다. 쌓인 행을 버리고 그 날짜 주변부터 다시 시작하며, 스크롤 위치를 처음으로 되돌린다. 이어 붙이면 30년치를 한꺼번에 받게 된다 (FR-005a, FR-005b, SC-017, ui-wireframes W6)
- [X] T018 [P] [US1] `frontend/tests/DailyTableScroll.test.tsx`에 **끝 도달 후 추가 요청이 없는지** 검증을 더한다 (SC-003, SC-004)

**Checkpoint**: 버튼 없이 스크롤만으로 과거를 훑을 수 있다. **여기까지가 MVP다**

---

## Phase 4: User Story 2 - 기간 단위를 바꿔 흐름을 본다 (Priority: P1)

**Goal**: 일·주·월 단위를 고를 수 있고, 일 단위가 기본이다.

**Independent Test**: 단위를 전환해 표의 행이 해당 기준일들로 바뀌는지 확인한다.

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] `backend/tests/integration/test_daily_period_contract.py` — `GET /api/fx/daily`가 `period` 매개변수를 받고, **생략 시 002와 완전히 같은 응답**을 내는지 검증한다. 알 수 없는 값은 400 `invalid_query`이며 **조용히 `daily`로 떨어지지 않는다**. **미수집 구간이 있을 때 `202 collecting` 응답이 기간 단위와 무관하게 001·002가 정한 형태 그대로인지** 함께 본다 — T010·T025·T026이 모두 그 경로를 지나간다 (FR-006, FR-007, SC-005, contracts/rest-api)
- [X] T020 [P] [US2] `backend/tests/integration/test_period_response.py` — 응답 행에 `periodFrom`·`periodTo`·`isOngoing`이 **모든 단위에서** 있고, `shiftedFrom`은 옮겨졌을 때만 키가 있는지 검증한다 (FR-014, FR-015a, research R4-4)
- [X] T021 [P] [US2] `backend/tests/integration/test_period_response.py`에 **파생 환율 4종과 잠정 구분이 세 단위에서 같은 규칙으로 나오는지** 검증을 더한다. 주·월 경로가 002의 산출을 우회하면 같은 날짜가 단위에 따라 다른 값을 갖는다 (FR-017, FR-018, SC-012)
- [X] T022 [P] [US2] `backend/tests/integration/test_period_volume.py` — **최소 10년 이상을 덮는 픽스처에서** 월 단위 행 수가 일 단위의 **1/20 이하**인지, 월 단위로 전 구간을 훑는 데 드는 요청 수가 일 단위보다 현저히 적은지 검증한다. **픽스처가 짧으면 비율이 성립하지 않는다** — 영업일이 월 약 20.8일이라 1/20은 긴 구간에서만 안정적이다 (SC-001, SC-011, data-model 7절)
- [X] T023 [P] [US2] `frontend/tests/PeriodTabs.test.tsx` — 기본 선택이 `일`인지, 활성 탭이 비활성과 구별되는지, 키보드로 조작 가능한지 검증한다 (FR-006, FR-007, SC-005)
- [X] T024 [P] [US2] `frontend/tests/PeriodSwitch.test.ts` — 단위를 바꾸면 **이전 단위의 행이 즉시 비워지는지**, 뒤늦게 도착한 이전 단위 응답이 **반영되지 않는지** 검증한다. 002 FR-036c·003 FR-028과 같은 계열이다 (FR-010, FR-011, SC-010)

### Implementation for User Story 2

- [X] T025 [US2] `backend/src/api/routes/daily.py`에 `period` 질의 매개변수를 더한다. 기본값 `daily`, 허용값은 `daily`·`weekly`·`monthly`이며 그 외에는 400 `invalid_query`다. 응답에 `period`를 함께 내려준다 (FR-006, FR-007, contracts/rest-api)
- [X] T026 [US2] `backend/src/api/routes/daily.py`의 행 직렬화에 `periodFrom`·`periodTo`·`isOngoing`을 더하고, `shiftedFrom`은 **값이 있을 때만 키를 넣는다**. 정상 상태에 값을 두면 화면이 존재 여부가 아니라 내용을 검사해야 한다. 세 표시를 하나로 합쳐 보내지 않는다 (FR-014, FR-015a, FR-015b)
- [X] T027 [P] [US2] `frontend/src/components/fx/PeriodTabs.tsx`를 만든다. 002의 `CurrencyTabs`와 **같은 분절 컨트롤 형태**를 쓴다 — 컨테이너가 회색, 활성 항목이 흰색. 통화 선택기와 같은 모양이라 사용자가 한 번만 익히면 된다. 기본 선택은 `일`이다 (FR-006, FR-007, ui-wireframes W1)
- [X] T028 [US2] `frontend/src/stores/fxWorkspaceStore.ts`에 `period` 상태와 전환 동작을 만든다. **전환 즉시 행을 비우고**, 도착한 응답의 `period`를 현재 선택과 대조해 거른다 (FR-010, FR-011, SC-010, research R4-8)
- [X] T029 [US2] `frontend/src/app/fx/page.tsx`에 `PeriodTabs`를 표 머리 왼쪽에 붙인다. 내려받기는 오른쪽에 둔다 — 왼쪽이 "무엇을 볼지", 오른쪽이 "가져갈지"다. **내려받기 버튼에 현재 담길 행 수를 함께 보인다.** **002가 정한 열 구성·서식은 그대로 둔다** (FR-016, FR-016c, SC-020, ui-wireframes W1·W7)

**Checkpoint**: 단위를 바꿔 장기 추이를 볼 수 있다

---

## Phase 5: User Story 3 - 기준일이 옮겨졌음을 안다 (Priority: P2)

**Goal**: 옮겨진 기준일·진행 중 구간이 각각 구별되어 드러나고, 선택 날짜가 구간으로
강조된다.

**Independent Test**: 기준일에 고시가 없는 구간을 포함해 주 단위로 보고, 그 행이 실제
고시일과 그 사실을 함께 보여주는지 확인한다.

### Tests for User Story 3 ⚠️

- [X] T030 [P] [US3] `frontend/tests/PeriodRowBadges.test.tsx` — 옮겨진 기준일·진행 중·잠정값 **셋이 서로 다른 기호**로 나오는지, 셋이 동시에 참인 행에서 모두 보이는지 검증한다. 하나로 뭉뚱그리면 사용자가 이유를 알 수 없다 (FR-015b, SC-015, SC-016)
- [X] T031 [P] [US3] `frontend/tests/PeriodRowBadges.test.tsx`에 옮겨진 행이 **원래 기준일을 정확히 알리는지**, 옮겨지지 않은 행에는 표시가 **없는지** 더한다. 모든 행에 늘 표시가 있으면 구별의 의미가 사라진다 (FR-013, FR-014, SC-007, SC-008)
- [X] T032 [P] [US3] `frontend/tests/PeriodHighlight.test.tsx` — 선택 날짜가 **속한 구간의 행**이 강조되는지, 단위를 바꿔도 **선택 날짜 자체는 바뀌지 않는지**, 속한 구간에 행이 없으면 그 사실이 드러나는지 검증한다 (FR-019, FR-019a, FR-019b, FR-020, SC-013, SC-014)
- [X] T033 [P] [US3] `frontend/tests/csv.test.ts`에 내려받기 검증을 더한다 — 파일의 기간 단위가 화면과 같은지, 원래 기준일·진행 중 표시가 열로 남는지, **머리말에 담긴 범위(가장 이른·늦은 날짜·행 수)가 있는지** (FR-016a, FR-016b, FR-016c, SC-018, SC-019, SC-020)

### Implementation for User Story 3

- [X] T034 [P] [US3] `frontend/src/components/fx/PeriodRowBadges.tsx`를 만든다. 옮겨진 기준일·진행 중을 **각각 다른 기호**로 표시하고, 기호만으로 전달하지 않도록 텍스트 대체를 둔다. 옮겨진 행은 **원래 기준일을 함께 알린다** — 없으면 사용자는 그 값을 금요일·말일 값으로 믿는다 (FR-013, FR-015a, FR-015b, SC-007, SC-015, ui-wireframes W2)
- [X] T035 [US3] `frontend/src/components/fx/DailyTable.tsx`에 `PeriodRowBadges`를 붙인다. 002의 잠정값 표시와 나란히 두되 서로 구별되게 하고, **기존 열 구성은 건드리지 않는다** (FR-015b, FR-016)
- [X] T036 [US3] `frontend/src/stores/fxWorkspaceStore.ts`에 **구간 기준 강조**를 만든다. 선택 날짜가 `periodFrom`~`periodTo` 안에 드는 행을 찾는다. 기준일만으로는 판정할 수 없다. 단위를 바꿔도 선택 날짜 자체는 바꾸지 않는다 (FR-019, FR-019b, SC-013, research R4-7)
- [X] T037 [US3] `frontend/src/components/fx/DailyTable.tsx`에 강조된 행의 날짜와 선택 날짜가 다를 때 **그 관계를 알린다**. 알리지 않으면 사용자는 자신이 고른 날짜가 바뀌었다고 오해한다 (FR-019a, SC-014)
- [X] T038 [US3] `frontend/src/components/fx/DailyTable.tsx`에 선택 날짜가 속한 구간에 행이 없을 때 그 사실을 알린다. 강조가 그냥 사라지면 사용자는 선택이 풀린 것으로 오해한다 (FR-020)
- [X] T039 [US3] `frontend/src/lib/csv.ts`에 기간 단위·원래 기준일·진행 중 열과 **담긴 범위를 밝히는 머리말**을 더한다. **표시가 파일에서 빠지면 화면에서 막은 오해가 파일에서 되살아난다.** 범위가 빠지면 90행을 60년치로 믿는다 (FR-016a, FR-016b, FR-016c, SC-018, SC-019, SC-020, ui-wireframes W7)

**Checkpoint**: 세 스토리 모두 독립적으로 동작한다

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T040 [P] `backend/tests/unit/test_no_interpolation.py` — `backend/src/`에 값을 채우는 코드가 없는지 정적으로 검사한다. 기준일 결측은 **날짜를 옮겨** 푼다 (FR-012, 헌법 원칙 V)

  ```bash
  grep -rn "fillna\|ffill\|이전 값\|전일 값" backend/src/ | grep -v test
  ```

- [X] T041 [P] `backend/tests/unit/test_layer_boundaries.py`에 `backend/src/api/services/period_rows.py`가 라우트를 임포트하지 않는지, 리포지토리가 구간 정의를 갖지 않는지 더한다 (헌법 원칙 IV, DB 운영 규약)
- [X] T042 [P] `backend/tests/unit/test_no_float.py`에 `period_rows.py`·`daily_query.py`·`fx_rate.py`의 `float(` 사용이 없는지 더한다. 집계를 산출하지 않으므로 애초에 필요 없다 (FR-009, 헌법 원칙 VI)
- [X] T043 `backend/src`·`backend/tests`에 mypy strict와 ruff를 통과시킨다 — `cd backend && .venv/bin/python -m mypy src && .venv/bin/python -m ruff check src tests`
- [X] T044 `frontend/`에 `npx tsc --noEmit`과 `npx eslint .`를 통과시킨다. `any` 사용 금지
- [X] T045 `backend/`에서 커버리지 80% 이상을 확인한다 — `cd backend && .venv/bin/python -m pytest -q --cov=src` (헌법 품질 게이트)
- [X] T046 `backend/tests/`와 `frontend/tests/` 전체 스위트가 **네트워크 차단 상태에서** 통과하는지 확인한다 (헌법 원칙 III)
- [ ] T047 `specs/004-fx-table-scroll-periods/quickstart.md`의 검증 시나리오 21개를 순서대로 수동 실행하고 결과를 기록한다. **이 기능은 ECOS를 호출하지 않으므로** 일일 한도를 쓰지 않는다 — 마음껏 반복해도 된다
- [X] T048 `README.md`의 현재 상태 표에 004를 더한다

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작
- **Foundational (Phase 2)**: Setup 완료 후 — **모든 사용자 스토리를 차단**
- **US1 (Phase 3)**: Foundational 완료 후. 기간 단위 없이도 독립적으로 동작한다
- **US2 (Phase 4)**: Foundational 완료 후. US1과 독립이나 **US1의 이어 보기 경로를 공유**하므로 실질적으로 US1 이후가 편하다
- **US3 (Phase 5)**: US2 완료 후. 옮겨진 기준일은 주·월 단위에서만 발생한다
- **Polish (Phase 6)**: 원하는 스토리가 모두 끝난 뒤

### 스토리 간 의존

```
Setup → Foundational ─┬→ US1 (MVP, 독립)
                      └→ US2 ──→ US3
```

US1은 완전히 독립이다. US3은 US2가 만든 주·월 단위 위에서만 의미가 있다.

### Within Each User Story

- 테스트를 먼저 쓰고 **실패를 확인한 뒤** 구현한다 (헌법 원칙 III)
- 백엔드 조회 → 응답 직렬화 → 화면 상태 → 화면 표현 순
- 한 스토리를 끝내고 다음 우선순위로 넘어간다

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/services/period_rows.py` | T004, T006, T007 |
| `backend/src/repository/fx_rate.py` | T009 |
| `backend/src/api/routes/daily.py` | T025, T026 |
| `backend/tests/integration/test_period_response.py` | T020, T021 |
| `frontend/src/components/fx/DailyTable.tsx` | T015, T035, T037, T038 |
| `frontend/src/stores/fxWorkspaceStore.ts` | T016, T017, T028, T036 |
| `frontend/tests/DailyTableScroll.test.tsx` | T012, T018 |
| `frontend/tests/DailyTable.test.tsx` | T012 (002 테스트 갱신) |
| `frontend/tests/PeriodRowBadges.test.tsx` | T030, T031 |

---

## Parallel Example: User Story 1

```bash
# US1의 테스트를 한꺼번에 작성 (서로 다른 파일):
Task: "useInfiniteScroll.test.ts — 끝 감지와 중복 호출 방지"
Task: "DailyTableScroll.test.tsx — 더 보기 없음, 끝 알림, 실패 처리"
Task: "fxWorkspaceScroll.test.ts — 덧붙이기, 과거 선택 시 비우기"
```

---

## Implementation Strategy

### MVP First (User Story 1만)

1. Phase 1 Setup 완료
2. Phase 2 Foundational 완료 (**모든 스토리를 차단하므로 최우선**)
3. Phase 3 US1 완료
4. **멈추고 검증**: quickstart 시나리오 1·1a·2·4·14로 US1을 독립 검증
   (시나리오 3은 월 단위가 필요하므로 US2에서 한다. 끝 도달은 T018이 자동으로 덮는다)
5. 이 시점에 **버튼을 누르지 않고 과거를 훑을 수 있다**

### Incremental Delivery

1. Setup + Foundational → 기반 완성
2. US1 → quickstart 1·1a·2·4·14 → **MVP**
3. US2 → quickstart 3·5·6·17·18·19 → 장기 추이가 보인다
4. US3 → quickstart 7~13·15·16 → 옮겨진 기준일을 안다
5. Polish → quickstart 20

---

## Notes

- `[P]` = 서로 다른 파일, 의존 없음
- 테스트 묶음 작성 → 실패 확인 → 구현 순서를 지킨다. **구현 후에도 실패가 남으면 중단하고
  사용자에게 보고한다** (헌법 v5.2.0 원칙 III, NON-NEGOTIABLE)
- 요구사항을 새로 만들거나 바꾸면 `plan.md` 추적성과 이 문서의 참조를 **같은 작업 단위에서**
  갱신한다 (헌법 명세 작성 규약)
- **신규 마이그레이션이 없다.** 스키마를 바꾸지 않으므로 DB 작업이 필요 없다
- **ECOS를 호출하지 않는다.** 이미 수집된 데이터를 다르게 질의할 뿐이라 일일 한도와 무관하다
- 태스크마다 또는 논리적 묶음마다 커밋한다
