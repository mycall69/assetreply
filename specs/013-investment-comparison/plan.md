# Implementation Plan: 투자 비교 — 한 자산군의 대상 최대 10개를 같은 조건으로 비교하고 저장해 다시 불러온다

**Branch**: `013-investment-comparison` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/013-investment-comparison/spec.md`

## Summary

사이드바 "투자 비교"가 새 화면(`/compare`)을 연다. 자산군 하나를 고르고 대상 최대 10개를 메뉴와 같은 부품으로 더한 뒤 공통 조건을 한 번 정해 실행하면,
대상마다 투자 원금·현재 가치·비용(기간 전체)·투자 수익·수익률이 한 표에 나란히 보이고, 수익률 추이 선(끝에 매도 후 점)과 최종 지표 막대가 함께 보인다.
실행한 비교는 이름을 붙여 로컬 DB에 저장하고 다시 불러온다.

- **US1 (P1) 같은 조건의 비교 표** — 백엔드에 메뉴 경로마다 짝이 되는 **비교 경로**(대상 하나, R13-1·R13-2)를 둔다. 메뉴와 같은 질의·검증·수집 판정·`prepare`를
  부르고, 메뉴 요약·시계열을 그대로 담은 뒤 정규화 블록(`comparison` — 주 값·현재 가치·비용 몫·잠정·환율, R13-3·R13-4)을 더한다. 화면은 대상마다 요청하고
  (계산된 대상부터 — 명확화 2), 막힘을 갈래로 나눠 비교 전체를 막고 시작일을 제안한다(R13-6). 수집 중인 대상은 그 자산군의 SSE를 구독해 끝나면 그 대상만 다시
  요청한다(R13-7). 조건이 바뀌면 결과를 흐린다(R13-8 — 명확화 6)
- **US2 (P2) 적립식·정기 적금** — 같은 틀에 방식만 바꾼다. 비교 경로 셋(주식·가상자산 적립식, 정기 적금)을 더한다 — 정기예금은 US1에 있다
- **US3 (P2) 그래프** — `CompareReturnChart`(선 = 메뉴 시계열의 보유 중 수익률, 기준일에 보유 중·매도 후 점 — R13-5)와 `CompareMetricBars`(DOM 막대 — R13-12)
- **US4 (P3) 저장·불러오기** — 새 테이블 `saved_comparison`과 `/api/comparison/saved`(R13-10). 이름을 붙여 저장, 지울 때까지 남는다(명확화 3)
- **반복 2026-10-09 단가 등락(US1 확장)** — 비교 표의 투자 원금과 현재 가치 사이에 단가 열 셋(시작일 단가·기준일 단가·등락). 주식 수정주가(상장국 통화)·가상자산 일봉
  시가·예금 발표 금리(%p)·부동산 그 달 시세. 비교 블록의 `comparison.unitPrice`(data-model 3.2)를 순수 모듈 `simulation/unit_price.py`가 계산한다(R13-18, spec FR-011a)

**설계 중 확인한 것**

| 확인 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 거절 본문이 `create_app()` 클로저에만 있다 | 꺼내 쓸 도우미가 없다 | 비교 경로는 대상 하나만 계산하고 **같은 예외를 그대로 올린다**(R13-1). 묶음 경로를 버렸다 |
| 가상자산 일시금에 매도 비용이 없다 | 012 US5 보드는 네 칸 | 비용의 매도 몫·매도 후 점이 없다. spec FR-011·FR-015에 반영(같은 작업 단위) |
| 보드마다 주 값 규칙이 다르다 | 주식 일시금·부동산은 물러남, 적립식은 "—" | `mainBasis`를 서버가 내고 줄에 보인다(R13-4). spec FR-011에 반영 |
| 주식 시계열은 행 날짜에만 점이 있다 | 기준일이 점이 아닐 수 있다 | `lineEnd`로 선 끝을 기준일에 맞춘다(R13-5). spec FR-015에 반영 |
| 정기예금·적금의 진행 중 경과 세금을 내놓지 않는다 | 평가액 안에서만 뺀다 | 계산 모듈에 `accrued_tax`·`open_tax`를 더한다(값 불변, R13-3). spec FR-011에 반영 |
| 주식 상장 판정이 수집 뒤에 끝나는 경우가 있다 | `_require_start_month_bar` | 수집 중인 대상이 남으면 시작일을 제안하지 않는다. 늦게 드러난 막힘은 결과를 거둔다(R13-6). spec FR-010에 반영 |
| 환율 찾기가 빗나가면 전체를 훑는다 | 가상자산 10개의 가장 느린 길 | `resolve_rate` 이분 탐색(결과 같음, R13-13) |
| 메뉴 스토어의 `run`이 이력을 저장한다 | 일곱 호출 지점 | 비교 스토어를 따로 둔다(R13-8·R13-14) |
| 부동산 고르기가 메뉴 결과를 지운다 | `clearResult` | 같은 상태 생성기로 비교 인스턴스를 따로(R13-9) |
| 가드 테스트가 `/compare`를 막는다 | `noUnbuiltAssetRoutes`·`Sidebar.test` | 바뀌는 기존 테스트로 승인 목록에 올린다(R13-16) |

## Technical Context

| 항목 | 값 |
|------|----|
| 언어(백엔드) | Python 3.14 (`.venv/bin/python`) |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async + aiomysql, Alembic |
| 언어(프론트엔드) | TypeScript 5 (`strict`), Next.js 16, React 19 |
| 상태 관리 | Zustand — 새 `compareStore`, 부동산은 `realEstateStateCreator` 하나로 메뉴·비교 인스턴스 둘 |
| 차트 | Lightweight Charts(수익률 추이 — `LineSeries`와 점만 그리는 `LineSeries`). 최종 지표는 DOM 막대 |
| DB | MySQL 8 — 새 테이블 `saved_comparison`, Alembic 리비전 하나(`down_revision = "a6d2f9c41b83"`) |
| 출처 | 새 출처 없음 — 각 자산군의 지금 수집 경로(Yahoo·investing.com·ECOS·공공데이터포털) |
| 테스트 | pytest + pytest-asyncio(통합은 `assetreplay_test`), Vitest + RTL(`lightweight-charts` 모의, `tests/setup.ts`의 `fetch` 대역) |
| 타입·린트 | mypy strict, ruff `--no-cache`, `tsc --noEmit`, eslint |
| 계산 | 서버 `Decimal`. 화면은 서버 문자열을 보이고 견주기만 한다(정렬 — `decimalOrder`). 막대 길이만 그리기 전용 `Number` |
| 성능 목표 | 시세를 받아 둔 대상 10개 × 20년 일시금 → 실행 뒤 5초 안에 표·그래프(SC-004) |
| 제약 | 메뉴 화면·계산 결과·이력 불변(FR-020). 비교 실행은 이력을 쓰지 않는다. 백엔드 단일 워커 |
| 규모 | 대상 ≤10(예금 ≤5), 시계열 대상당 ≤1000점, 저장한 비교 행은 사용자가 지울 때까지 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 새 I/O는 비동기 세션의 저장한 비교 읽기·쓰기와, 메뉴와 같은 비동기 서비스 호출뿐이다. 대상별 요청이라 요청마다 세션이 따로다 |
| II. 데이터 소스 격리 | ✅ | 새 출처·새 어댑터가 없다. 수집은 각 자산군의 지금 경로·한도·백오프를 그대로 쓴다(R13-17) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 순서: 테스트를 먼저 커밋 → 최초 실패 확인 → 구현. 구현 뒤 실패하면 멈추고 보고한다. 먼저 쓸 테스트: <br>• 비용 몫·주 값·조건 검증·경과 세금·이분 탐색의 참조값(quickstart 1) <br>• 비교 경로 ↔ 메뉴 경로의 `summary`·`series`·202·거절 동일성, 이력 불변(quickstart 2) <br>• 저장 API·스키마 <br>• 화면: 막힘·제안, 계산된 대상부터, 흐림, 정렬, 그래프 끝 점, 저장·불러오기, 이력 PUT 없음 <br>바뀌는 기존 테스트는 R13-16 목록 — 구현 뒤 실제 실패 목록으로 승인을 받는다 |
| IV. 모듈화 | ✅ | 순수 함수: `simulation/comparison_costs.py`, `api/services/comparison_metrics.py`·`comparison_conditions.py`(DB·HTTP 없음), 화면 `lib/compareBlock.ts`·`compareCondition.ts`·`decimalOrder.ts`. 저장한 비교 서비스는 저장소 Protocol(`SavedComparisonRepository` — `list_entries`·`add`·`remove`)에 기대고, 경로가 저장소 모듈(`src.repository.saved_comparison`)을 주입한다(mypy가 모듈의 Protocol 충족을 검사한다). 기존 저장소(012 이력 등)를 직접 부르는 관례는 이 기능의 범위 밖이라 고치지 않는다. 비교 경로 모듈이 메뉴 경로 모듈의 요약 함수를 부른다 — 서비스가 경로를 부르지 않는다(Complexity Tracking) |
| V. 정합성·재현성 | ✅ | 결측은 메뉴 시계열의 `gaps` 그대로 끊는다. 비운 비용은 `null` + 까닭(0으로 메우지 않음). 잠정 까닭(`provisional`)을 줄에 보인다. 기준 통화 KRW와 평가 환율의 날짜·출처를 결과에 담는다. `saved_at`은 UTC |
| VI. 금융 정확성 | ✅(기록) | 모든 값은 서버 `Decimal`(비용 합·정기예금 현재 가치 포함). 화면은 합하지 않는다 — 정렬은 문자열 견주기. 기록할 해석 둘: 저장 조건의 금액 글자(012 선례), 막대 길이의 그리기 전용 `Number`(Complexity Tracking) |
| VII. 반응형 UI | ✅ | Zustand 스토어. 수집 진행은 자산군별 SSE를 대상마다 구독한다. 수익률 추이는 Lightweight Charts, 대상당 1000점 다운샘플링 |
| VIII. 한국어 문서화 | ✅ | 문서·주석·커밋 한국어, 식별자 원어 |
| IX. MVP 점진 | ✅ | 새 자산군이 아니다. US1이 API와 화면까지의 수직 조각이다. 범위 밖: 저장한 비교 이름 바꾸기, 부동산 매입가 직접 입력, 날마다의 매도 후 선, 평가액 추이 선 |
| DB 운영 규약 | ✅ | Alembic 리비전 하나. ORM만 쓴다(삽입·삭제·목록 — 방언 문법 불필요). 열거형 비원생(`native_enum=False`), 시각 UTC `DateTime(timezone=False)`, 금액 열 없음(`test_금액_컬럼에_부동소수점이_없다`) |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 설계 중 바뀐 요구를 spec에 같은 작업 단위로 반영했다: <br>• FR-010 — 수집 중이면 제안을 미룸, 늦게 드러난 막힘, 막힌 동안의 수집 <br>• FR-011 — 가상자산 일시금의 매도 몫 없음, 예금 경과 세금, 보드별 주 값 규칙·`mainBasis`, 잠정·환율 표시 <br>• FR-013 — 그 대상만 다시 요청, 연달은 202 한도 <br>• FR-015 — 매도 후 점의 대상, 선 끝 맞추기 <br>• 가정 — 비교 실행은 메뉴 경로를 그대로 쓴다 <br>모든 FR·SC는 아래 추적성 표의 설계·태스크에 연결된다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 메뉴 결과 불변(FR-020·SC-009) | ✅ | 계산 모듈의 더함은 기본값 있는 필드(`accrued_tax`·`open_tax`)와 결과가 같은 탐색(`resolve_rate`)뿐이다. 메뉴 경로 응답은 키도 바뀌지 않는다. quickstart 6이 013 전후 응답을 견준다 |
| 일어나지 않음 | ✅ | 비용 항목 하나를 빠뜨리면 몫의 참조값(항목 합 = 메뉴 합계)이 깨진다. 매도 후 점이 없으면 화면 테스트가 깨진다. 저장 실패를 삼키면 화면 테스트(대역 `fail`)가 깨진다 |
| 다른 곳에서 일어남 | ✅ | 같은 질의 함수(메뉴 스토어의 `toQuery` 계열)로 대상마다 조건을 만든다(SC-002). 늦은 응답은 `runSeq`로 버린다. 비교 스토어는 이력·메뉴 스토어를 건드리지 않는다(이력 PUT 0건 테스트). 부동산 고르기는 인스턴스가 따로다 |
| 늦게 일어남 | ✅ | 수집 중인 대상은 스트림 완료에 그 대상만 다시 요청한다. 연달은 202 한도(3)로 끝없는 대기를 막는다. 수집 중이면 시작일 제안을 미뤄 다시 막히지 않는다 |
| 공유 부품 변경 | ✅ | `ComparisonChart`·`InstitutionPicker`·`SimulationForm`은 고치지 않는다. `HistoryContent`에 빈 목록 문구 속성(처음 값 = 지금 문구), `realEstateStore`는 상태 생성기를 내보내고 구독·실행 차례를 인스턴스 안으로 — 기존 테스트를 고치지 않고 통과해야 한다(못 하면 멈춘다) |
| 바뀌는 기존 테스트 | ⚠ 승인 필요 | R13-16 — `Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`·(표가 전체를 고정하면) `TopBarTitle.test.ts`. 구현 뒤 실제 실패 목록으로 승인을 받는다 |

### 반복 2026-10-09 재평가 — 단가 등락 (spec FR-011a, R13-18)

| 원칙 | 판정 | 근거 |
|------|------|------|
| II. 데이터 소스 격리 | ✅ | 새 출처가 없다. 단가는 지금 계산이 이미 가진 값(원주가 종가·분할 기록·일봉 시가·발표 금리·월 시세)이다. DB 변경 없음 |
| IV. 모듈화 | ✅ | 차이·등락률·분할 비율 글자는 순수 함수 `simulation/unit_price.py`(DB·HTTP 없음). 비교 경로가 값을 모아 넘기고 `comparison_metrics`가 블록에 싣는다 |
| V. 결측 | ✅ | 기준일 시세가 없으면 `value: null`과 까닭 — 가까운 날·달로 메우지 않는다. 미발표 금리·추정 시세는 잠정 표식. 수정주가는 저장하지 않고 실행마다 그 실행의 분할 기록으로 다시 계산한다 |
| VI. 금융 정확성 | ✅ | 서버 `Decimal`(`quantize_rate`). 화면은 형식만 입힌다(`tests/compareNoClientFinance` 그대로) |
| 메뉴 결과 불변(FR-020·SC-009) | ✅ | `unitPrice`는 비교 블록에만 있다. 메뉴 경로·메뉴 요약·시계열은 바뀌지 않는다 — T094가 T080 불변 대조를 다시 돌린다 |
| 바뀌는 기존 테스트 | ⚠ 승인 필요 | 예상: `CompareTable.test.tsx` 열 머리 목록, `tests/support/compareFixtures.ts` `block()`(필수 형 `unitPrice`). T084가 실제 실패로 목록을 확정한다 |

## Project Structure

### Documentation (this feature)

```text
specs/013-investment-comparison/
├── spec.md
├── plan.md                  # 이 파일
├── research.md              # R13-1 ~ R13-18
├── data-model.md            # 테이블 · 비교 조건 · comparison 블록 · 계산 모듈 더함 · 화면 상태
├── quickstart.md            # 검증 안내 · 실행 기록
├── contracts/
│   ├── rest-api.md          # 비교 경로 일곱 · 저장한 비교 경로 셋
│   └── ui-wireframes.md     # F1 ~ F9
├── checklists/
│   └── requirements.md
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   ├── main.py                       (변경 — 처리기 InvalidComparison, 라우터 둘: 저장 먼저)
│   │   ├── errors.py                     (변경 — InvalidComparison)
│   │   ├── routes/
│   │   │   ├── comparison.py             (신규 — 비교 경로 일곱, R13-1·R13-2. 반복 2026-10-09 — 경로마다 단가의 시작·기준일 값을 모은다)
│   │   │   ├── saved_comparison.py       (신규 — GET·POST·DELETE, R13-10)
│   │   │   ├── stock_recurring.py        (변경 — 수집 판정 묶음 `_prepare_or_collect`를 공개 이름 `prepare_or_collect`로)
│   │   │   └── crypto_recurring.py       (변경 — 같은 이유. 비교 경로가 같은 차례로 부른다)
│   │   └── services/
│   │       ├── comparison_metrics.py     (신규, 순수 — 주 값·현재 가치·원금·잠정·환율·lineEnd, R13-4·R13-5. 반복 2026-10-09 — `unitPrice`)
│   │       ├── comparison_conditions.py  (신규, 순수 — 저장 조건 검증·정규화, data-model 2)
│   │       └── saved_comparison.py       (신규 — 목록·저장·삭제, 저장소 Protocol `SavedComparisonRepository`)
│   ├── repository/
│   │   └── saved_comparison.py           (신규)
│   ├── db/
│   │   ├── models.py                     (변경 — SavedComparison)
│   │   └── migrations/versions/<rev>_저장한_비교.py  (신규)
│   └── simulation/
│       ├── comparison_costs.py           (신규, 순수 — 비용 몫, R13-3)
│       ├── unit_price.py                 (신규, 순수 — 반복 2026-10-09 단가 차이·등락률·분할 비율 글자, R13-18)
│       ├── deposit_rollover.py           (변경 — Summary.accrued_tax)
│       ├── installment_ladder.py         (변경 — open_tax)
│       └── fx_convert.py                 (변경 — resolve_rate 이분 탐색, R13-13)
└── tests/
    ├── unit/        test_comparison_costs.py · test_comparison_costs_recurring.py · test_comparison_metrics.py · test_comparison_metrics_recurring.py ·
    │                test_comparison_conditions.py · test_deposit_accrued_tax.py · test_installment_open_tax.py · test_fx_resolve_bisect.py ·
    │                test_unit_price.py · test_comparison_metrics_unit_price.py (반복 2026-10-09)
    └── integration/ test_comparison_api.py · test_comparison_identity.py · test_comparison_identity_recurring.py · test_saved_comparison_api.py ·
                     test_saved_comparison_schema.py · test_comparison_unit_price.py (반복 2026-10-09)

frontend/
├── src/
│   ├── app/compare/page.tsx              (신규)
│   ├── stores/
│   │   ├── compareStore.ts               (신규 — data-model 5)
│   │   ├── compareRealEstatePicker.ts    (신규 — 같은 생성기로 만든 비교 화면의 고르기 인스턴스, R13-9)
│   │   ├── realEstateStore.ts            (변경 — 상태 생성기 `realEstateStateCreator`를 내보내고 구독·실행 차례를 인스턴스 안으로, `simulationQuery` 내보냄)
│   │   └── stockStore.ts                 (변경 — `registerStock` 사용)
│   ├── lib/
│   │   ├── compareApi.ts                 (신규 — 비교 경로·저장 경로 요청)
│   │   ├── compareBlock.ts               (신규, 순수 — 막힘 갈래·비교 전체 상태·제안, R13-6)
│   │   ├── compareCondition.ts           (신규, 순수 — 정규 조건·같음·자동 이름·고를 수 있는 통화)
│   │   ├── decimalOrder.ts               (신규, 순수 — R13-11)
│   │   ├── stockSelection.ts             (신규 — registerStock, stockStore에서 꺼냄)
│   │   └── types.ts                      (변경 — 비교 응답·저장한 비교 타입. 반복 2026-10-09 — `UnitPrice`)
│   └── components/
│       ├── compare/                      (신규 — AssetPicker · TargetChips · CompareTargetPicker · InstitutionChecklist · CompareConditionForm ·
│       │                                   CompareBlockedPanel · CompareTable · CostCell · StaleBanner · CompareReturnChart · CompareMetricBars ·
│       │                                   SaveComparisonForm · SavedComparisons)
│       ├── history/HistoryStates.tsx     (변경 — 빈 목록 문구 속성, 처음 값 그대로)
│       └── shell/Sidebar.tsx · TopBar.tsx (변경 — `/compare`)
└── tests/
    ├── setup.ts                          (변경 — `/api/comparison/saved` 메모리 대역을 이력 대역 곁에)
    ├── support/savedComparisonStub.ts    (신규)
    └── ComparePage*.test.tsx · compareStore*.test.ts · compareBlock.test.ts · compareCondition.test.ts · decimalOrder.test.ts ·
        CompareTable.test.tsx · CompareReturnChart.test.tsx · CompareMetricBars.test.tsx · InstitutionChecklist.test.tsx · SavedComparisons.test.tsx ·
        SaveComparisonForm.test.tsx · HistoryStatesEmptyText.test.tsx · registerStock.test.ts · compareNoClientFinance.test.ts ·
        compareRealEstatePicker.test.ts · CompareTableUnitPrice.test.tsx(반복 2026-10-09)   (신규)
```

**Structure Decision**: 기존 웹 앱 구조(backend/frontend)를 그대로 쓴다. 비교는 새 자산군이 아니라 기존 계산을 함께 쓰는 화면이므로, 백엔드는 경로·순수 정규화·
저장만 더하고 계산 모듈은 값을 바꾸지 않는 더함만 한다. 화면은 새 경로 하나와 새 스토어 하나, 메뉴 부품을 그대로 쓰고 부동산 고르기는 같은 생성기의 인스턴스를 하나 더 만든다.

## 요구사항 추적성

범례: F*n* = contracts/ui-wireframes.md §F*n*, A*n* = contracts/rest-api.md §*n*, Q*n* = quickstart.md §*n*, DM*n* = data-model.md §*n*.
각 줄 끝의 `tasks`는 tasks.md "요구사항 ↔ 태스크" 표와 같다 — 모든 FR·SC가 태스크에 참조된다(명세 작성 규약).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (사이드바 → 화면) | R13-15·R13-16, F1, Q5-1, tasks T006·T020·T022·T037·T038 |
| FR-002 (자산군 하나, 바꾸면 비움) | R13-8, DM5, F2, tasks T018·T020·T035·T036 |
| FR-003 (메뉴와 같은 고르기) | R13-9, F2, Q5-2·Q5-9, tasks T015·T016·T017·T020·T032·T033·T036·T038 |
| FR-004 (2~10개, 중복·한도) | R13-9, DM2, F2·F3, A3, Q5-3, tasks T013·T017·T018·T020·T030·T035·T036·T061·T071 |
| FR-005 (같은 기간, 대상별 기준일) | R13-2, DM3(`asOf`), F3·F5, tasks T010·T019·T026·T036 |
| FR-006 (같은 방식) | R13-2, DM2, F3, Q5-7, tasks T039·T043·T044·T045·T049·T050·T051 |
| FR-007 (같은 금액·통화·재투자) | R13-2, DM2·DM5, F3, tasks T013·T030·T036·T044·T045·T050 |
| FR-008 (부동산 매입가 = 그 달 시세) | R13-2, A1.1, F3·F5, Q5-9, tasks T010·T026·T036·T038 |
| FR-009 (지금 설정값, 조건 동일) | R13-1·R13-2, Q2, tasks T010·T018·T026·T034·T035 |
| FR-010 (막힘·제안·늦은 막힘) | R13-6, DM5.1, A1.4, F4, Q1·Q5-4, tasks T014·T018·T020·T031·T035·T036·T038·T044 |
| FR-011 (표 칸·비용 몫·주 값·잠정·환율) | R13-3·R13-4, DM3·DM4, A1.2, F5, Q1·Q2·Q5-2, tasks T007·T008·T009·T010·T011·T019·T021·T023·T024·T025·T026·T027·T028·T036·T040·T041·T042·T043·T045·T046·T047·T048·T049·T050·T084·T088·T092 |
| FR-011a (단가 등락 — 반복 2026-10-09) | R13-18, DM3.2, A1.2, F5, Q5-13, tasks T084·T085·T086·T087·T088·T089·T090·T091·T092·T093·T094 |
| FR-012 (정렬) | R13-11, F5, Q1, tasks T012·T019·T029·T036·T057·T088·T092 |
| FR-012a (조건이 바뀜 — 흐림) | R13-7·R13-8, DM5, F8, Q5-6, tasks T013·T018·T020·T030·T035·T036·T044·T054·T057·T067·T068 |
| FR-013 (계산된 대상부터, 수집·실패) | R13-1·R13-7, DM5.1, A1.3, F4·F5, Q5-5, tasks T014·T018·T019·T020·T031·T035·T036·T054 |
| FR-014 (막힘·수집 중인 대상의 이름·까닭) | R13-6, F4·F5, tasks T014·T019·T020·T031·T036 |
| FR-015 (그래프 — 선·끝 점·최종 지표) | R13-5·R13-12, DM3(`lineEnd`), F6·F7, Q5-10, tasks T009·T025·T042·T048·T052·T053·T054·T055·T056·T057·T058 |
| FR-016 (이름 붙여 저장, 보관 기간 없음) | R13-10, DM1·DM2·DM5.2, A2·A3, F9, Q2·Q5-11, tasks T060·T061·T062·T063·T064·T066·T067·T068·T069·T070·T071·T072·T073·T074·T075·T076·T077·T078·T083 |
| FR-017 (불러오면 다시 실행) | R13-10, F9, Q5-8·Q5-11, tasks T063·T067·T068·T077·T078 |
| FR-018 (삭제) | R13-10, A4, F9, Q5-11, tasks T063·T065·T067·T068·T070·T072·T073·T074·T076·T078·T083 |
| FR-019 (저장 실패 알림) | R13-10, DM5.2, F9, tasks T063·T065·T067·T068·T076·T077·T078 |
| FR-020 (메뉴·이력 불변) | R13-14·R13-16, A1.5, Q5-12·Q6, tasks T001·T010·T018·T026·T035·T043·T067·T080 |
| SC-001 (메뉴와 같은 값) | R13-1·R13-3, A1.2, Q1·Q2·Q5-2, tasks T007·T008·T009·T010·T011·T038·T040·T041·T043·T051 |
| SC-002 (조건 동일·흐림·섞임 없음) | R13-2·R13-7·R13-8, Q2·Q5-6, tasks T010·T018·T043 |
| SC-003 (막힘·제안·수집 중 표시) | R13-6, Q1·Q5-4·Q5-5, tasks T014·T018·T038 |
| SC-004 (10개 × 20년 또는 최장, 5초) | R13-13, Q4, tasks T004·T005·T079 |
| SC-005 (그래프 = 표, 끝 점, 메우지 않음) | R13-5·R13-12, Q1·Q5-10, tasks T009·T052·T053·T058 |
| SC-006 (불러오기 동일·결과 저장 없음·사라지지 않음) | R13-10, A3, Q2·Q5-11, tasks T061·T063·T067·T071·T078·T083 |
| SC-007 (자산군 섞임·이력 기록 없음) | R13-8·R13-14, Q2·Q5-12, tasks T010·T018·T038·T067 |
| SC-008 (한 화면에서 끝냄) | F2·F3, Q5-2, tasks T020·T038 |
| SC-009 (메뉴 결과 불변) | R13-13·R13-16, Q6, tasks T001·T002·T004·T080·T082·T094 |
| SC-010 (단가 = 메뉴 가격 선·보드, 분할 낀 등락률 = 수정주가 — 반복 2026-10-09) | R13-18, DM3.2, Q5-13, tasks T085·T087·T093 |

## Complexity Tracking

헌법 이탈이 없다 — 기록할 이탈 없음. 아래는 해석이 필요한 선택이다.

| 선택 | 이유 | 버린 대안 |
|------|------|-----------|
| 저장한 비교 조건을 JSON 글로 저장(금액 문자열 포함 — 원칙 VI 해석, 012 R12-9 선례) | 조건은 사용자가 친 입력의 기록이다. 서버는 검증할 때만 `Decimal`로 읽고 저장·응답은 받은 글자 그대로다. 불러오면 그 글자로 다시 계산한다 | 자산군마다 테이블·`DECIMAL` 열 — 대상 목록(최대 10)과 자산군별 칸이 네 벌이 된다 |
| 최종 지표 막대의 길이에 `Number()`(그리기 전용) | 막대는 그림이다. 글자 값은 서버 문자열이고, 정렬은 문자열 견주기다(R13-11·R13-12). 차트의 `chartSeries.ts:120` 선례 | 서버가 막대 비율을 낸다 — 화면 배치 값을 API에 넣는다 |
| 비교 경로 모듈이 메뉴 경로 모듈의 요약 함수를 부른다 | 요약 JSON 함수 다섯이 경로 모듈에 있다(조사). 같은 함수를 불러야 SC-001이 구조로 선다. 서비스가 경로를 부르지 않는다 — 경로 → 경로 | 요약 함수를 서비스로 옮긴다 — 다섯 모듈의 이동과 기존 테스트의 불러오기 경로가 바뀐다 |
| 부동산 스토어의 상태 생성기를 두 번 쓴다(메뉴 스토어 리팩터 — 구독·실행 차례를 인스턴스 안으로) | 같은 흐름 하나를 메뉴·비교가 함께 쓴다(FR-003). 필드·동작이 같아 메뉴 테스트를 고치지 않는다 | 비교 쪽에 새로 쓴다 — 202·진행이 얽힌 약 200줄이 두 벌이 된다. 고르기만 슬라이스로 뗀다 — 실행·오류와 얽혀 메뉴 코드가 크게 바뀐다(R13-9) |
