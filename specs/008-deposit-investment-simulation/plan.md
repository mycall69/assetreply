# Implementation Plan: 예금 투자 시뮬레이션

**Branch**: `008-deposit-investment-simulation` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-deposit-investment-simulation/spec.md`

## Summary

사이드바의 "예금"을 실제 메뉴로 만든다. 투자처(시중은행·저축은행·신협·상호금융·새마을금고)를 라디오 버튼으로 고르고 시작일·원금(원화)을
넣으면, 시작일에 1년 만기 정기예금에 가입해 만기마다 세후 이자를 더해 재예치했을 때의 성과를 보드·표·차트·이력 비교로 보인다. 화면은
주식·가상자산을 따르고, 금리는 한국은행 ECOS의 월별 가중평균 금리(신규취급액 기준)다.

**설계 중 실측한 결과**(research R8-1~R8-5, 2026-10-04 ECOS Open API):

| 실측 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 통계표 | 예금은행 `121Y002`, 비은행금융기관 `121Y004`(둘 다 신규취급액 기준, 월) | 잔액 기준(`121Y013`)은 쓰지 않는다 |
| 항목 | 시중은행 **정기예금(1년)** 2012-01~, 저축은행·신협·상호금융 1997-08~, 새마을금고 2012-01~ | 정확히 1년인 항목만 — 시중은행은 2012년부터(R8-1) |
| 상호금융 | 항목 이름에 기관명이 없다(`정기예탁금(1년만기)`) | 코드 계열·상위 항목·값으로 판정, ECOS 화면으로 재확인(quickstart 1) |
| 빈 달 | 다섯 시계열 모두 0개 | 결측 규칙은 픽스처로 검증 |
| 발표 | 2026-10-04에 마지막 달 2026-08, 그 뒤는 `INFO-200` | 하루 한 번 확인, 마지막 발표 달 뒤는 미발표(잠정) |
| 잠정 표시 | 응답에 잠정 필드 없음 | 발표값은 확정, 겹침 3개월로 수정 관측만(R8-4) |
| 규모 | 한 투자처 전체가 한 요청(최대 349행) | 청크 없음, 처음 7요청(항목 목록 2 + 시계열 5), 그 뒤 하루 많아야 5 |

001의 ECOS 어댑터를 **한 곳** 바꾼다 — 환율과 예금이 같은 출처의 호출 한도를 함께 지키도록, 요청이 프로세스 하나뿐인 관문(`EcosGate`)을
지나게 한다(R8-6). 동시 수의 기본값을 001과 같게 두어 **환율 수집의 속도는 그대로**다 — 오늘 환율 조회와 예금 수집은 환율 백필 중에
빈자리를 기다릴 수 있다(느려질 뿐 막히지 않는다, FR-013). 주식·가상자산과 함께 쓰는 성과 차트에 선택 속성
(`provisionalFrom`)을 하나 더한다 — 주식·가상자산은 그대로 그려진다(R8-10).

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — **신규 테이블 6개**(data-model), Alembic 마이그레이션 하나(head `b7e3c9d14a26` 다음). 기존 테이블 변경 없음 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library. 출처는 **실제 응답 픽스처**로 계약 테스트 |
| 타입·린트 | mypy strict, ruff(`--no-cache`) / tsc, eslint |
| 출처 | **한국은행 ECOS Open API**(001과 같은 출처·같은 인증키) — 공식 공개 API, 인증키는 URL 경로에 들어간다 |
| 원금 통화 | KRW만. 환율 없음 |
| 수집 실행 | 앱 수명 태스크 1개 추가 — 예금 금리 수집 줄. 환율 수집과 **ECOS 관문을 공유**(R8-6) |
| 계산 | 순수 함수 `simulation/deposit_rollover.py` — 회차·재예치·경과 이자·잠정·멈춤(R8-7, R8-8) |
| 성능 목표 | 받은 구간이면 결과 3초 안(SC-001). 수집 진행 2초 안(SC-002) |
| 규모 | 투자처 5 × 최대 349개월. 결과 행은 한 해 15줄 남짓 — 30년이어도 수백 줄이라 한 번에 보낸다 |
| 제약 | 백엔드 단일 워커 — 기동 시 남은 점유를 끝난 프로세스의 것으로 보고 회수한다(007 FR-014a와 같다). 테스트는 네트워크 없이(헌법 원칙 III). 날짜는 한국 시간 달력(FR-018) |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 출처 호출은 aiohttp. 수집은 워커 태스크라 요청이 기다리지 않는다(202 + SSE) |
| II. 데이터 소스 격리 | ✅ | 어댑터를 `ingestion/ecos/` 안에 둔다(투자처 ↔ 통계표·항목 대응도 그 안). **약관을 실측으로 확인했다**(R8-2, 2026-10-04 — 자유 이용·상업적 이용 허용, 이탈 아님). 약관 의무: 출처 표시(제7조 ② — 화면 D1·문서), 과다 호출 자제(제6조 — 동시 수·한도 신호 공유·지수 백오프+지터, 설정), 인증키 관리(제4조 — 설정에만, 오류 문구는 `mask_secrets`, FR-014) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행·먼저 커밋·최초 실패 확인, 구현 뒤 실패하면 멈추고 보고(006 D2). 계약 테스트는 실제 응답 픽스처. 실행 주체(`lifespan`의 수집 줄, 202가 요청한 수집)는 그 주체를 거쳐야만 통과하는 테스트와 짝짓는다(006 D1) |
| IV. 모듈화 | ✅ | 계산은 `simulation/deposit_rollover.py` 순수 함수(DB·HTTP 없음). 출처 형식(`RESULT.CODE`·`DATA_VALUE`·항목 코드)은 `ingestion/ecos/` 밖으로 나가지 않는다(Protocol) |
| V. 정합성·재현성 | ✅ | 원본 분리 보관(URL 없이 본문만), `(institution, month)` upsert, `source`·`ingested_at`, 커버리지(`first_month`·`latest_month`·`checked_on`). **결측은 보간하지 않고 멈춘다.** **미발표는 잠정으로 계산하되 잠정 금리를 저장하지 않고 결과에 잠정을 드러낸다**(명세 Clarifications, R8-8). 시작 가능 날짜는 상수가 아니라 받은 첫 달(R8-12). 발표값의 수정은 관측·기록하고 덮어쓰지 않는다(R8-4) |
| VI. 금융 정확성 | ✅ | `Decimal`(정밀도 60), 금리 `DECIMAL(7,4)`·세율 `DECIMAL(9,6)`. 원 미만 버림 위치를 정해 두고 손계산 참조값 다섯(R8-7). 세율은 설정(명시 파라미터) |
| VII. UI·진행 | ✅ | Zustand, SSE 진행(006·007과 같은 `no-transform`), Lightweight Charts(축 쉼표 007 FR-043a), 잠정 구간 구별 |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | 주식 다음이 예금. 수집~화면 수직 슬라이스. 적금·중도 해지·교차 비교는 범위 밖(YAGNI) |
| DB 운영 규약 | ✅ | ORM, 마이그레이션 하나, upsert는 기존 방언 추상화(`db/dialect.py`) |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 아래 추적성 표. tasks가 모든 FR·SC를 참조해야 한다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 출처 응답의 누출 | ✅ | 도메인·API는 투자처 키와 `MonthlyRate`(달·금리)만 본다. 통계표·항목 코드·`RESULT.CODE`는 `ingestion/ecos/` 안에만 |
| 인증키 누출 | ✅ | 원본 테이블에 URL 열이 없다. 실패 사유·사건은 `mask_secrets`. 픽스처는 응답 본문만(quickstart 자동 검사) |
| 001 경로 변경 | ✅(기록) | `EcosClient._get`이 관문을 지난다. 동시 수 기본값이 001과 같아 환율 수집의 출력·속도가 같다(오늘 환율 조회는 백필 중 빈자리를 기다릴 수 있다) — 001~004 테스트 전체가 회귀(Complexity Tracking) |
| 잠정값 | ✅ | 잠정 금리는 계산 안에서만 대신 쓰고 저장하지 않는다. 결과는 보관하지 않아 발표와 함께 확정으로 바뀐다. 응답·화면의 모든 경로(보드·표·차트·비교)에 잠정이 드러난다(SC-005) |
| 공유 부품 변경 | ✅(기록) | `PerformanceChart`의 `provisionalFrom`은 선택 속성(기본 `null`), 시계열 응답에 키 하나 추가 — 주식·가상자산 테스트가 회귀 |

## Project Structure

### Documentation (this feature)

```text
specs/008-deposit-investment-simulation/
├── spec.md              # /speckit-specify, /speckit-clarify
├── plan.md              # 이 파일
├── research.md          # R8-1 ~ R8-12 (ECOS 실측 포함)
├── data-model.md        # 신규 테이블 6개
├── quickstart.md        # 검증 시나리오 20개
├── contracts/
│   ├── rest-api.md      # /api/deposit/* + 출처(ECOS) 계약
│   └── ui-wireframes.md # D1~D8
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks — 36개, Phase 1~7
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── config/settings.py                # 변경 — ECOS_MAX_CONCURRENT_REQUESTS(기본 3), DEPOSIT_RECHECK_OVERLAP_MONTHS(기본 2) (R8-4, R8-6)
│   ├── ingestion/ecos/
│   │   ├── gate.py                       # 신규 — EcosGate: 프로세스 하나의 동시 수 제한 + INFO-300 공유 백오프 (R8-6)
│   │   ├── client.py                     # 변경 — _get이 EcosGate를 지난다(환율 동작 불변)
│   │   ├── deposit_items.py              # 신규 — 투자처 → (통계표, 항목 코드, 이름 패턴), START_TIME (R8-1)
│   │   ├── deposit_client.py             # 신규 — EcosDepositClient: 항목 확인, 월 시계열(원본 함께 반환) (R8-5)
│   │   └── deposit_parse.py              # 신규 — StatisticSearch(M) → MonthlyRate, INFO-200 = 미발표, 잘림 검사 (FR-017)
│   ├── ingestion/protocols.py            # 변경 — DepositRateSource Protocol, MonthlyRate
│   ├── db/models.py                      # 변경 — Deposit* 6개 (data-model)
│   ├── db/migrations/versions/…_예금_스키마.py  # 신규
│   ├── repository/
│   │   ├── deposit_rate.py               # 신규 — 금리 upsert(있으면 바꾸지 않고 다른 값 보고)·조회, 커버리지·확인한 날, 원본
│   │   ├── deposit_job.py                # 신규 — 작업·점유·고아 회수(007 crypto_job과 같은 수단)
│   │   └── deposit_setting.py            # 신규 — 이자 소득세율(기본 0.154)
│   ├── simulation/deposit_rollover.py    # 신규 — 회차·만기·재예치·경과 이자·잠정·멈춤, 행 (FR-021~FR-027, R8-7·R8-8)
│   ├── api/services/
│   │   ├── deposit_collect.py            # 신규 — 202 판정(받지 않은 달 + 오늘 확인 여부), 작업 확보 (FR-010, FR-011)
│   │   ├── deposit_simulation.py         # 신규 — 입력 검증, 시작 가능 날짜, 계산 끝(오늘 KST), 응답 (FR-003~FR-007, FR-035)
│   │   └── deposit_series.py             # 신규 — 행 날짜 + 계산 끝의 점, provisionalFrom (FR-036)
│   ├── api/routes/
│   │   ├── deposit_institutions.py       # 신규 — GET /api/deposit/institutions
│   │   ├── deposit_simulation.py         # 신규 — GET /api/deposit/simulation
│   │   ├── deposit_series.py             # 신규 — GET /api/deposit/simulation/series
│   │   ├── deposit_progress.py           # 신규 — GET /api/deposit/progress (SSE)
│   │   └── deposit_settings.py           # 신규 — GET·PUT /api/deposit/settings
│   ├── api/main.py                       # 변경 — 라우터, lifespan 태스크 1개(예금 수집), 기동 시 고아 점유 회수
│   └── worker/
│       ├── deposit_queue.py              # 신규 — 시작 큐 (007 crypto_queue와 같다)
│       ├── deposit_runner.py             # 신규 — 항목 확인, 시계열 요청, 원본·금리·커버리지, 겹침 비교 사건 (R8-4, R8-5)
│       └── deposit_worker.py             # 신규 — 앱 수명 태스크
└── tests/
    ├── contract/fixtures/deposit/        # 신규 — 실제 응답(항목 목록 2, 시계열 5, INFO-200·100·300)
    ├── contract/                         # test_ecos_deposit_parse.py, test_ecos_deposit_client.py, test_ecos_gate.py
    ├── unit/                             # deposit_rollover(참조값 다섯), 202 판정, 잠정·결측
    └── integration/                      # 수집·커버리지·확인한 날·겹침 사건, 202 게이트, 시뮬레이션·시계열, SSE, 설정, lifespan, 환율과 동시 수집

frontend/
├── src/
│   ├── app/deposit/page.tsx              # 신규 — 예금 화면 (D1)
│   ├── stores/depositStore.ts            # 신규 — 입력·실행·수집 대기·이력 (cryptoStore를 본뜬다)
│   ├── components/deposit/
│   │   ├── InstitutionPicker.tsx         # 신규 — 라디오 다섯, 설명 줄 (D1)
│   │   ├── DepositSimulationForm.tsx     # 신규 — 시작일·원금(원화만) (D1)
│   │   ├── DepositPerformanceTable.tsx   # 신규 — 열 10개, 구분·잠정 글자, 내용 폭 (D4)
│   │   ├── DepositNotice.tsx             # 신규 — 보드 아래 잠정·멈춤 줄 (D3)
│   │   └── DepositHistory.tsx            # 신규 — 이력·다시 실행·비교 (D6)
│   ├── components/stock/PerformanceChart.tsx   # 변경 — 선택 속성 provisionalFrom(연한 색, 범례 "잠정") (D5)
│   ├── components/stock/PerformanceBoard.tsx·ComparisonChart.tsx·StartDateInput.tsx·CollectingNotice.tsx  # 그대로
│   ├── components/settings/DepositSettingsForm.tsx  # 신규 — 이자 소득세율 (D7)
│   ├── app/settings/page.tsx             # 변경 — 예금 칸 연결
│   ├── components/shell/Sidebar.tsx      # 변경 — 예금에 /deposit (D1)
│   ├── lib/types.ts                      # 변경 — 예금 응답 형식, SimulationSeriesResponse.provisionalFrom?
│   ├── lib/depositHistory.ts             # 신규 — 이력(다른 저장 키)
│   └── lib/depositProgressStream.ts      # 신규 — /api/deposit/progress 구독
└── tests/                                # 각 변경에 대응. noUnbuiltAssetRoutes.test.ts에서 deposit을 뺀다
```

**Structure Decision**: 기존 웹 애플리케이션 구조를 그대로 쓴다. 예금은 주식·가상자산과 **같은 층을 나란히** 둔다(파일 접두사 `deposit_`).
출처 어댑터는 001과 같은 `ingestion/ecos/` 안에 두되 환율 모듈과 파일을 나눈다 — 같은 출처의 지식(응답 형식·오류 코드·관문)은 한 곳에,
통계마다 다른 해석은 따로 둔다. 자산군에 무관한 것(보드·차트·비교·시작일·수집 안내·원금 쉼표)만 공유한다.

## 요구사항 추적성

설계 산출물·태스크와의 대응이다. 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (메뉴) | D1, `Sidebar.tsx`, `app/deposit/page.tsx`, `noUnbuiltAssetRoutes.test.ts`, tasks T016·T021 |
| FR-002~FR-005 (입력·투자처·원화·시작일) | D1·D2, `InstitutionPicker`, `DepositSimulationForm`, rest-api `unknown_institution`·`currency_not_allowed`·`start_after_end`, `deposit_simulation.py`, tasks T013·T016·T020·T021·T022 |
| FR-006, FR-007 (시작 가능 날짜·시작 달 미발표/결측) | R8-8, R8-12, rest-api `before_first_month`·`rate_missing`, `deposit_coverage.first_month`, `deposit_rollover.py`, tasks T011·T013·T017·T020 |
| FR-008 (출처·통계·기준) | R8-1, `ingestion/ecos/deposit_items.py`(이름 패턴 재확인), quickstart 1, tasks T001·T003·T009·T022 |
| FR-009, FR-010 (보관·받은 구간·미발표 확인) | R8-3, R8-5, data-model 1~3절, `deposit_runner.py`, `deposit_collect.py`(`checked_on`), tasks T006·T008·T012·T013·T018·T019·T020 |
| FR-011, FR-012 (백그라운드·진행·중복·회수) | R8-9, rest-api 202·SSE, data-model 4절, `deposit_queue`·`deposit_worker`·`deposit_progress.py`, `api/main.py` 기동 시 회수, tasks T012·T014·T015·T018·T019·T020 |
| FR-013 (서로 막지 않음·한도 공유) | R8-6, `ingestion/ecos/gate.py`, 별도 수집 줄, quickstart 18, tasks T002·T005·T007·T010·T015 |
| FR-014, FR-015 (인증키·수집 로그) | data-model 2·4절(URL 없음), `mask_secrets`, 수집 사건, quickstart 19, tasks T004·T010·T012·T036 |
| FR-016, FR-017 (실패 사유·값 읽기) | rest-api 출처 절·SSE `failed.kind`, D8, `deposit_parse.py`, tasks T003·T004·T009·T012·T013·T016 |
| FR-018~FR-020 (한국 시간·결측·잠정 관측) | R8-3, R8-4, R8-8, `deposit_rollover.py`, `deposit_rate_revised` 사건, tasks T011·T012·T013·T017 |
| FR-021~FR-027 (가입·만기·이자·재예치·경과·계산 끝·수익) | R8-7, `deposit_rollover.py`, 참조값 다섯, tasks T011·T017·T022 |
| FR-028, FR-029 (재현성·정밀도) | R8-11, `Decimal`, `RATE_PCT`·`SPREAD`, tasks T006·T008·T011·T017 |
| FR-030, FR-031 (세율 설정) | data-model 5절, rest-api 설정, D7, `DepositSettingsForm`, tasks T023·T024·T025·T026·T033 |
| FR-032~FR-034 (표) | D4, `DepositPerformanceTable`, rest-api `rows`, tasks T016·T021·T022·T033 |
| FR-035 (보드) | D3, `PerformanceBoard`(notes), `DepositNotice`, tasks T013·T016·T020·T021 |
| FR-036 (차트) | D5, `deposit_series.py`, `PerformanceChart`(`provisionalFrom`), tasks T027·T028·T029·T030·T033 |
| FR-037, FR-038 (이력·비교) | D6, `depositHistory.ts`, `DepositHistory`, `ComparisonChart`, tasks T031·T032·T033 |
| FR-039 (기록 갱신) | README·CLAUDE.md, tasks T034 |
| SC-001, SC-002 | quickstart 4·6, tasks T022·T036 |
| SC-003, SC-004 | research R8-7 참조값, `deposit_rollover` 단위 테스트, quickstart 5·12, tasks T011 |
| SC-005 | R8-8, quickstart 7·8, 결측 픽스처 통합 테스트, tasks T011·T013·T016·T027·T028·T031 |
| SC-006 | quickstart 6, 같은 입력 두 번, tasks T011·T013 |
| SC-007 | quickstart 10·11(다섯 투자처, 실데이터), tasks T022·T036 |
| SC-008 | quickstart 13, tasks T023·T024·T033 |
| SC-009 | quickstart 15, 시계열 통합 테스트, tasks T027·T033 |
| SC-010 | quickstart 16, tasks T022·T033 |
| SC-011 | quickstart 19, 원본·사건·실패 사유 검사, tasks T012·T036 |
| SC-012 | R8-6, quickstart 18, 관문 계약 테스트, tasks T005·T015·T036 |
| SC-013 | 자동 검사(전체 테스트), tasks T035 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-------------|------------------------------|
| **001의 ECOS 어댑터 요청 경로를 바꾼다** — `EcosClient._get`이 프로세스 하나의 `EcosGate`를 지난다(R8-6) | 예금 금리와 환율이 같은 출처·같은 인증키다. 각자 세마포어를 가지면 합친 호출을 아무도 보지 않아, 한쪽이 한도에 걸려도 다른 쪽이 계속 불러 둘 다 막힌다(명세 FR-013 실패 양상, SC-012) | 예금이 자기 세마포어만 두는 안은 SC-012를 지킬 수 없다. 환율 워커에 예금 요청을 태우는 안은 환율 백필이 예금 확인을 오래 막는다(FR-013). 관문의 동시 수 기본값을 001의 통화 동시 수(3)와 같게 두어 **환율 수집의 출력과 속도가 바뀌지 않게** 한다. 오늘 환율 조회와 예금 수집은 환율 백필 중에 빈자리를 기다릴 수 있다 — 느려질 뿐 막히지 않는다(FR-013). 001~004 테스트 전체가 회귀 검사다. 깨지면 멈추고 보고한다(원칙 III) |
| **공유 차트에 선택 속성을 더한다** — `PerformanceChart.provisionalFrom`, 시계열 응답의 `provisionalFrom` 키(R8-10) | 잠정 구간을 차트에서 구별해야 한다(명세 FR-036, 헌법 원칙 V — 잠정 입력의 결과는 잠정임이 드러나야 한다) | 예금 전용 차트를 따로 만들면 축 쉼표·결측 끊기·두 축 규칙이 두 벌이 된다(007 R7-14가 막은 실패). 속성은 선택이고 기본 `null`이라 주식·가상자산은 그대로 그려진다 — 005~007 차트 테스트가 회귀 검사다 |
