# Implementation Plan: 외환 기간 전환 스크롤, 주식·가상자산 일자별 표의 일·주·월 단위, 시뮬레이션 이력의 로컬 DB 저장, 투자금 기본값

**Branch**: `012-period-tables-history-db` | **Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/012-period-tables-history-db/spec.md`

## Summary

기존 화면 넷의 쓰기 편함을 고친다. 새 자산군·새 출처는 없다.

- **외환 기간 전환(US1)**
  - 기간 전환이 "표의 처음으로" 신호를 내지 않는다. 그 신호는 먼 날짜 선택에만 남는다(R12-1).
  - 높이 붙잡기는 놓을 때 스크롤을 받칠 바닥을 남긴다.
  - 통화 전환의 늦은 응답이 기간 전환 뒤의 표에 섞이는 기존 결함을 함께 막는다.
- **주식·가상자산 표의 일·주·월(US2)**
  - 서버의 새 순수 모듈 `simulation/period_table.py`가 표를 만든다(R12-2·R12-3).
    - 행: 기간 행(대표일 — 주는 금요일 이하의 마지막 시세일, 월은 그 달의 마지막 시세일), 사건 행(매수·배당락·재투자·납입 — 늘 있다), 결측 구간 행(가상자산 일 단위)
    - 표시: 📅 옮겨짐·⏳ 진행 중
  - 주식 계산 모듈 둘에 하루하루 상태(`daily`)를 **더한다**. 차트와 보드의 재료(`rows`·`latest`)는 그대로다(R12-4).
  - 표 경로 넷에 `period` 질의를 더한다. 쪽은 같은 날의 행을 붙잡는다(R12-7).
- **이력의 로컬 DB(US3)**
  - 새 테이블 둘: `simulation_history`, `history_setting`(R12-9).
  - 경로 다섯: 목록·저장·삭제·옮기기·보관 기간.
  - 조건 식별자는 서버가 계산한다 — 지금 규칙과 글자까지 같다.
  - 기한 지난 항목은 읽고 쓸 때마다 지운다(R12-10).
  - 화면마다 그 자산군의 브라우저 이력을 한 번 옮기고, 성공한 뒤에만 지운다(R12-11).
  - 불러오기 실패·저장 실패를 빈 목록과 구별해 알린다(R12-13).
- **원금 기본값(US4)**: 세 스토어의 처음 원금이 `"10000000"`이다. 다른 흐름은 이미 FR-016과 같다(R12-14).

**설계 중 확인한 것**(research "조사에서 확인한 사실" 요약):

| 확인 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 외환 스크롤의 원인 | `setPeriod`가 `tableEpoch`를 올리고 화면 효과가 새 표에 `scrollIntoView` | 신호를 먼 날짜로 한정(R12-1) |
| 주식 하루하루 상태 | 계산 모듈이 사건 행·월 행·`latest`만 낸다 | `daily`를 더한다(R12-4) |
| 주식 차트의 재료 | 표의 행(`rows` — 월 첫 거래일·사건 날)이다 | 표는 `rows`가 아닌 `daily`로 만든다 — 차트 불변(FR-007) |
| 가상자산 일시금 매수일 | 시작 월의 첫 일봉이다(시작일 전일 수 있다) | spec의 "시작일 전" → "첫 평가일 전"(같은 작업 단위에서 고침) |
| 일시금 쪽 함수 | 같은 날 두 행이 쪽 경계에 걸리면 뒤 행이 빠진다 | 쪽 함수 하나로 모으고 같은 날을 붙잡는다(R12-7) |
| 결측 구간 | `compute_gaps`가 순수 함수다 | 시계열과 같은 입력으로 불러 결측 구간 행 = 차트 끊김(R12-6) |
| `frequency` 질의 | 적립식의 납입 주기로 이미 쓴다 | 단위는 외환과 같은 `period` |
| JSON 열 | 쓰는 테이블이 없다 | 조건은 서버가 직렬화한 글(R12-9) |
| 이력 테스트의 모의 | 화면·스토어 테스트가 `apiClient.get`을 경로 무관하게 모의한다 | 이력은 공통 요청 함수를 직접 쓰는 따로 된 클라이언트 + 테스트 기반의 이력 대역(R12-12) |
| 원금 처음 값 | 세 스토어 `""`. 빈칸 단언·이어 치기 테스트 없음 | 처음 값만 바꾼다(R12-14) |

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, Alembic — 새 의존 없음 |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) — `stockStore`·`cryptoStore`의 `tablePeriod`·`tableSeq`, 네 스토어의 이력 칸(data-model 5) |
| 차트 | 바뀌지 않는다(spec FR-007) |
| DB | MySQL 8 — 마이그레이션 1개(`simulation_history`·`history_setting`, `down_revision = "f4c2a8e19d35"`) |
| 출처 | 새 출처·새 외부 호출 없음 |
| 테스트 | pytest·pytest-asyncio(단위·통합), Vitest·RTL. 새 출처가 없어 계약 테스트 픽스처는 없다 |
| 타입·린트 | mypy strict, ruff(`--no-cache`) / tsc(테스트 포함), eslint |
| 계산 | 새 순수 모듈 하나(`period_table`) + 주식 모듈 둘의 `daily` 더함. 모두 날짜·`Decimal`(값은 계산 모듈 그대로) |
| 성능 목표 | 20년 일 단위 표의 첫 쪽·다음 쪽이 각각 3초 안(SC-004). 묶기는 한 번 훑기, 원화 환산은 쪽 크기만 |
| 제약 | 백엔드 단일 워커. 새 배경 태스크 없음. 테스트는 네트워크 없이 통과한다. 화면은 계산하지 않는다(`noClientSideFinance`). 계산 결과 불변(FR-017) |
| 규모 | 표 경로 넷에 질의 하나. 새 경로 다섯(이력 넷 + 설정). 새 화면 부품 약 5(단위 표시·범례·결측 행·설정 절·이력 상태). 스토어 넷, 훅 하나 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 새 I/O는 비동기 세션의 이력 읽기·쓰기뿐이다. 표 묶기는 순수 함수다 |
| II. 데이터 소스 격리 | ✅ | 새 출처 없음. 기록된 이탈(005·007·010)의 범위가 넓어지지 않는다 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 순서: 테스트를 먼저 커밋 → 최초 실패 확인 → 구현. 구현 뒤 실패하면 멈추고 보고한다. 바뀌는 기존 테스트는 아래 재평가를 본다. 먼저 쓸 테스트: <br>• `period_table` 참조 날짜 테스트(quickstart 1)<br>• `daily` 불변식<br>• 조건 식별자 대조·보관 경계·옮기기(quickstart 2)<br>• 경로 통합(`period`·이력 다섯)<br>• 화면·스토어(스크롤 위치·늦은 응답·이력 상태·원금) |
| IV. 모듈화 | ✅ | 대표일·표 묶기는 `simulation/`의 순수 함수다(DB·HTTP 없음 — `test_layer_boundaries`). 조건 검증·식별자는 서비스의 순수 함수, DB는 저장소, 경로는 얇다. `simulation/`이 외환 `api/services/period_rows`를 부르지 않는다(R12-2) |
| V. 정합성·재현성 | ✅ | 기준일에 시세가 없으면 **날짜를 옮기고** 표시한다. 값을 만들거나 옮기지 않는다. 구간에 시세가 없으면 행이 없다. 출처 결측은 값 없는 행으로 드러낸다(FR-004b). 전일 값 복사 없음(`test_no_interpolation` — 새 주석에 금지 낱말을 쓰지 않는다). 결과는 저장하지 않는다(이력은 조건만) |
| VI. 금융 정확성 | ✅(기록) | 표의 값은 계산 모듈의 `Decimal` 그대로이고 API는 문자열이다. 이력 조건의 원금은 사용자가 친 문자열의 기록이다 — DB·서버가 그것으로 계산하지 않는다. 다시 실행하면 그 문자열이 질의가 된다(Complexity Tracking) |
| VII. UI·진행 | ✅ | Zustand. 표는 기존 커서 이어 받기(IntersectionObserver)다. 일 단위 20년도 쪽으로 받는다(헌법 "가상화 또는 다운샘플링" — 쪽 받기). 차트 불변 |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | 새 자산군이 아니다. 스토리마다 계산·경로·화면까지 완결한다(US1~US4는 서로 독립) |
| DB 운영 규약 | ✅ | Alembic 리비전 하나. ORM만 쓰고 방언 문법은 `db/dialect.upsert`뿐이다(`test_dialect_isolation`). 열거형은 비원생(`native_enum=False` — 008 선례), 시각은 UTC `DateTime(timezone=False)`, 금액 열 없음(`test_금액_컬럼에_부동소수점이_없다`) |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 설계 중 바뀐 요구를 spec에 같은 작업 단위로 반영했다. <br>• 첫 평가일 — Edge Cases·FR-004·Assumptions<br>• 결측 구간 = 차트 구간 — FR-004b<br>• 주식 차트 끝점·화면마다 옮기기·단위 유지 — Assumptions<br>• US2 시나리오 9의 전제<br>모든 FR·SC는 아래 추적성 표의 설계·태스크에 연결된다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 계산 결과 불변(FR-017·SC-009) | ✅ | 계산 모듈의 `rows`·`latest`·`summary` 계산을 고치지 않는다(`daily`만 더함). 시계열 경로는 그대로다. 불변 대조(quickstart 3-7)로 확인한다 |
| 일어나지 않음 | ✅ | <br>• 사건 행은 단위 판정 전에 모두 넣는다 — 대표일 판정이 사건 행을 지울 수 없다(SC-003 불변식)<br>• 옮기기 실패면 브라우저 키를 지우지 않는다<br>• 불러오기 실패는 빈 목록이 아니다(FR-014a)<br>• 저장 실패는 알린다(FR-014)<br>• 같은 날 행을 쪽에 붙잡는다(R12-7) |
| 다른 곳에서 일어남 | ✅ | <br>• 표시는 대표일의 마지막 사건 행이 지고, 사건 행의 날짜는 바꾸지 않는다(배당락일이 금요일로 바뀌어 보이지 않음)<br>• 가상자산 주 행은 금요일 이하에서 고른다 — 매주 일요일이 되지 않는다<br>• 이력은 화면마다 자기 자산군 키만 옮긴다<br>• 보관 기간은 보관 기준 시각으로 잰다 — 다시 실행한 항목·옮긴 항목이 지워지지 않는다<br>• 원금 기본값은 처음 값일 뿐이라 화면을 오갈 때 덮지 않는다 |
| 늦게 일어남 | ✅ | <br>• 보관 기간을 줄이면 설정 저장이 곧바로 지운다. 목록 조회도 먼저 지운다<br>• 늦은 표 응답은 차례 번호로 버린다(주식·가상자산) 또는 단위·통화로 버린다(외환 `loadAll` 포함)<br>• 높이 붙잡기는 놓을 때 바닥을 남겨 늦은 스크롤 당김을 막는다 |
| 공유 부품 변경 | ✅(기록) | <br>• `PeriodTabs`(선택 속성 `titles` — 기본값은 지금 외환 문구)<br>• 이력 부품 넷(선택 속성 넷)<br>• `apiClient`(`request` 공개, `delete` 더함)<br>• `tests/setup.ts`(이력 대역 더함)<br>외환 `PeriodRowBadges`·`DailyTable`·`period_rows.py`는 고치지 않는다 |
| **바뀌는 기존 테스트** | ⚠ 승인 필요(구현 때) | research R12-15의 목록이다. 셋 모두 spec이 바꾼 요구사항(004 FR-005b의 기간 전환, 월 행, 이력 보관 위치)에서 나온다. 계산 모듈의 단위 테스트는 바뀌지 않는다. **스토리의 테스트 커밋 전에 목록을 보이고 승인을 받고**, 그 커밋에서 바뀐 요구를 단언하는 부분만 고친다. 구현 뒤 목록 밖의 실패는 결함으로 보고 멈춘다 |

## Project Structure

### Documentation (this feature)

```text
specs/012-period-tables-history-db/
├── spec.md              # /speckit-specify, /speckit-clarify (명확화 5) + plan 설계 중 고친 요구
├── plan.md              # 이 파일
├── research.md          # R12-1 ~ R12-16
├── data-model.md        # 테이블 둘, 조건 칸·식별자, period_table 입출력, daily, 화면 상태
├── quickstart.md        # 품질 게이트, 참조 날짜, API·브라우저 검증, 불변 대조
├── contracts/
│   ├── rest-api.md      # 표 경로의 period·행 종류·표시, 이력 경로 다섯
│   └── ui-wireframes.md # 외환 동작, 단위 탭·표시·결측 행, 이력 칸 상태, 설정 절, 원금
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/simulation/
│   ├── period_table.py            # (신규) 달력·대표일·표 묶기·쪽 — 순수(R12-2·R12-3·R12-5·R12-7)
│   ├── reinvest.py                # (변경 — 더함) Outcome.daily
│   └── recurring_stock.py         # (변경 — 더함) RecurringOutcome.daily, RowKind "day"
├── src/api/services/
│   ├── stock_simulation.py · crypto_simulation.py · stock_recurring.py · crypto_recurring.py
│   │                              # (변경) 사건 행 모으기 → build_table → page → 쪽의 행만 변환. 기존 쪽 함수 셋은 없어진다
│   ├── history_conditions.py      # (신규) 자산군마다 조건 검증·직렬화·식별자 — 순수(data-model 2)
│   └── history.py                 # (신규) utc_now, 목록·저장·삭제·옮기기·정리의 차례(R12-10·R12-11)
├── src/repository/
│   ├── simulation_history.py      # (신규) 목록·upsert·합치기·삭제·정리
│   └── history_setting.py         # (신규) get_retention·save_retention(DEFAULT_RETENTION)
├── src/db/models.py · src/db/migrations/versions/<rev>_시뮬레이션_이력.py   # 테이블 둘
├── src/api/routes/
│   ├── stock_simulation.py · crypto_simulation.py · stock_recurring.py · crypto_recurring.py   # (변경) period 질의·응답 period·행 JSON(kind·표시·missing)
│   └── history.py                 # (신규) /api/history/settings(먼저) · /api/history/{asset}…
├── src/api/errors.py · src/api/main.py   # UnknownAsset·InvalidHistory 처리기, 라우터 등록
└── tests/
    ├── unit/          # test_period_table, test_reinvest_daily, test_recurring_stock_daily, test_history_conditions
    └── integration/   # 표 경로 period(넷), 이력 경로·보관·옮기기, 마이그레이션(기존 일반 검사가 새 테이블을 함께 본다)

frontend/
├── src/hooks/useHeightHold.ts               # (신규) 붙잡기 + 놓을 때 바닥(R12-1) — 외환·주식·가상자산
├── src/app/fx/page.tsx                      # (변경) useHeightHold
├── src/stores/fxWorkspaceStore.ts           # (변경) setPeriod는 tableEpoch를 올리지 않는다, loadAll 늦은 응답 버림
├── src/components/fx/PeriodTabs.tsx         # (변경) 선택 속성 titles
├── src/components/period/PeriodMarks.tsx · PeriodLegend.tsx   # (신규) 📅·⏳ 글자 설명, 범례
├── src/components/stock/PerformanceTable.tsx · crypto/CryptoPerformanceTable.tsx
│   · recurring/RecurringStockTable.tsx · RecurringCryptoTable.tsx   # (변경) 표시·범례·결측 행, ◇ 제거
├── src/lib/types.ts                         # 행 kind(buy·period·missing), shiftedFrom·isOngoing·dateTo, 응답 period, 이력 응답
├── src/lib/apiClient.ts                     # request 공개, delete
├── src/lib/historyApi.ts · legacyHistory.ts # (신규) 이력 경로, 옛 키 읽기·지우기
├── src/lib/simulationHistory.ts · cryptoHistory.ts · depositHistory.ts · realEstateHistory.ts   # (삭제) 저장·식별자는 서버로
├── src/lib/principalFormat.ts               # DEFAULT_PRINCIPAL
├── src/stores/stockStore.ts · cryptoStore.ts   # tablePeriod·tableSeq·setTablePeriod, 이력 비동기, 원금 처음 값
├── src/stores/depositStore.ts · realEstateStore.ts   # 이력 비동기(+ 예금 원금 처음 값)
├── src/components/stock/SimulationHistory.tsx · crypto/CryptoHistory.tsx · deposit/DepositHistory.tsx
│   · realestate/RealEstateHistory.tsx       # 안내 문구, 불러오는 중·불러오기 실패·다시 시도, 옮기지 못한 수
├── src/components/settings/HistoryRetentionForm.tsx · src/app/settings/page.tsx   # (신규 절)
├── src/app/{stocks,crypto,deposit,realestate}/page.tsx   # 단위 탭·붙잡기(주식·가상자산), 이력 속성
└── tests/             # 새 파일 — 스크롤 위치, 단위 탭·표시·결측 행, 늦은 응답, 이력 상태·옮기기, 설정 절, 원금 처음 값
                       # setup.ts — /api/history 대역

CLAUDE.md · README.md   # 현재 상태 표에 012, 이력 DB·보관 기간·period 질의 주의
```

**Structure Decision**: 기존 웹 앱 구조(backend/frontend) 그대로다.
- 기간 표는 서버의 순수 모듈 하나가 네 표에 함께 쓰인다. 외환의 검증된 경로(`period_rows.py`·`DailyTable`·`PeriodRowBadges`)는 고치지 않는다.
- 이력은 자산군 무관한 테이블 하나 + 자산군마다의 조건 검증으로 둔다. 화면의 lib 넷은 하나의 클라이언트로 모인다.

## 요구사항 추적성

설계 산출물과의 대응이다(F*n* = contracts/ui-wireframes.md §*n*, A*n* = contracts/rest-api.md §*n*, Q*n* = quickstart.md §*n*). 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md) — 참조하는 태스크가 없는
FR·SC가 남으면 헌법 명세 작성 규약 위반이다.

| 요구사항 | 설계 |
|----------|------|
| FR-001 (외환 기간 전환 — 창 그대로, 먼 날짜·통화 그대로) | R12-1, F1, Q4-1, tasks T003·T004·T005·T006·T007·T008·T009·T010 |
| FR-002 (이전 단위 행·늦은 응답 — 외환) | R12-1(`loadAll`), F1, tasks T006·T008 |
| FR-003 (단위 선택, 처음 일) | R12-8, data-model 5.1, A1.1, F2, tasks T011·T015·T017·T023·T024·T025·T029·T030·T034·T035 |
| FR-004 (대표일·옮겨짐 표시·구간 없음) | R12-3, data-model 3, A1.3, F3, Q1·Q3-1, tasks T012·T013·T014·T015·T016·T017·T020·T021·T027·T028·T029·T030·T033 |
| FR-004a (진행 중 표시) | R12-3, data-model 3.1, A1.3, F3, Q1, tasks T012·T015·T020·T021·T027·T033 |
| FR-004b (결측 구간 행) | R12-6, data-model 3.2·4, A1.3, F4, Q1·Q3-2, tasks T012·T016·T017·T022·T027·T030·T033 |
| FR-005 (사건 행 늘 보임, 표시는 마지막 사건 행) | R12-5, data-model 3.2 불변식, A1.3, F3, Q1·Q3-1, tasks T011·T012·T014·T015·T017·T021·T027·T029·T030·T033 |
| FR-006 (단위 전환 — 창 그대로, 늦은 응답) | R12-8, data-model 5.1, F5, Q4-2, tasks T003·T004·T023·T024·T025·T034·T035 |
| FR-007 (보드·차트·매도 비용·비교 불변) | R12-4·R12-8, A(바뀌지 않는 것), Q3-1·Q3-7, tasks T015·T016·T017·T023·T024·T029·T034 |
| FR-008 (월 행·◇ 대체) | R12-5, A1.3(없어지는 것), F3·F4, tasks T011·T015·T016·T018·T022·T026·T029·T030·T033 |
| FR-009 (20년 이어 받기) | R12-7, data-model 3.3, Q3-6·Q4-2, tasks T012·T015·T027·T029·T036 |
| FR-010 (외환과 같은 모양·글자 설명) | R12-8, F2·F3, tasks T019·T020·T021·T025·T032 |
| FR-011 (DB 저장, 자산군 분리, 같은 조건 하나) | R12-9, data-model 1.1·2, A2·A3·A4, Q2·Q3-4, tasks T038·T039·T040·T047·T050·T051·T052·T053·T055·T056·T060 |
| FR-012 (보관 기간 설정·정리) | R12-10, data-model 1, A6, F7, Q2·Q3-5·Q4-5, tasks T041·T049·T051·T052·T053·T058·T060 |
| FR-013 (브라우저 이력 옮기기) | R12-11, data-model 5.3, A5, Q2·Q4-3, tasks T038·T039·T040·T044·T046·T052·T053·T056·T060 |
| FR-014 (저장 실패 알림) | R12-13, F6, tasks T040·T047·T048·T053·T056·T057·T060 |
| FR-014a (불러오기 실패·다시 시도) | R12-11·R12-13, data-model 5.2, F6, Q4-4, tasks T046·T048·T056·T057·T059·T060 |
| FR-015 (안내 문구) | R12-13, F6, tasks T038·T048·T050·T057·T059·T060 |
| FR-016 (원금 기본값) | R12-14, data-model 5.4, F8, Q4-6, tasks T061·T062·T063 |
| FR-017 (계산 결과 불변) | R12-4, 설계 후 재평가, Q3-7, tasks T001·T013·T014·T028·T068 |
| SC-001 (외환 탭 위치 0건) | R12-1, Q4-1, tasks T003·T007·T009·T010 |
| SC-002 (기준일·표시·결측 행 수) | R12-3·R12-6, Q1·Q3-2, tasks T012·T015·T016·T036 |
| SC-003 (사건 행 개수 같음) | data-model 3.2 불변식, Q1·Q3-1, tasks T012·T015·T017·T036 |
| SC-004 (3초) | R12-16, Q3-6, tasks T065 |
| SC-005 (보드·차트 불변) | R12-8, Q3-1·Q4-2, tasks T015·T025·T036 |
| SC-006 (옮기기 100%·다른 브라우저) | R12-11, Q2·Q4-3, tasks T040·T046·T060 |
| SC-007 (보관 경계 0건) | R12-10, Q2·Q3-5, tasks T041·T060 |
| SC-008 (원금 입력 0회) | R12-14, Q4-6, tasks T061·T062·T064 |
| SC-009 (011까지 계산 결과 같음) | 설계 후 재평가, Q3-7, tasks T001·T002·T068 |

## Complexity Tracking

헌법 이탈이 없다 — 기록할 이탈 없음.

기록할 만한 설계 선택은 넷이다. 모두 원칙을 지키는 쪽이다.

| 선택 | 이유 | 버린 대안 |
|------|------|-----------|
| 이력 조건을 JSON 글로 저장(원금 문자열 포함 — 원칙 VI 해석, R12-9) | 조건은 사용자가 친 입력의 기록이다. 계산에 쓰이는 금액 열이 아니고 DB·서버가 그것으로 계산하지 않는다. 지금의 브라우저 저장과 같은 성격이다. **사용자 확인 2026-10-06.** 지키는 장치 — 서버는 원금을 검증할 때만 `Decimal`로 읽고, 저장·응답은 받은 글자 그대로다. 이력 모듈이 원금으로 계산하지 않는다(T039가 고정) | 자산군마다 테이블 넷과 DECIMAL 열 — 같은 기능이 네 벌이 되고, 화면 조건이 바뀔 때마다 스키마가 바뀐다 |
| 목록 조회가 기한 지난 항목을 지운다(R12-10) | 기간을 줄인 뒤 남는 일(FR-012 늦게 일어남)을 배경 태스크 없이 막는다 | 배경 정리 태스크 — lifespan 태스크가 이미 여덟이고, 정리 주기 사이에 기한 지난 항목이 보인다 |
| 주식 계산 모듈에 `daily`를 더함(R12-4) | 차트·보드의 재료를 그대로 두고 일 단위 표를 만든다 | `rows`에 일 행을 넣기 — 주식 차트가 바뀐다(FR-007 위반) |
| 이력 클라이언트가 공통 요청 함수를 직접 쓴다(R12-12) | 이력과 시뮬레이션은 실패 영역이 다르다. 시뮬레이션 모의가 이력 요청을 가로채지 않는다 | `apiClient.get`을 그대로 쓰기 — 경로 무관 모의를 쓰는 기존 테스트 수십 개가 이력 응답 때문에 흔들린다 |
