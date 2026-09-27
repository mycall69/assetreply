# Implementation Plan: 주식 투자 시뮬레이션

**Branch**: `005-stock-investment-simulation` | **Date**: 2026-09-27
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-stock-investment-simulation/spec.md`

## Summary

종목·시작일·원금을 입력하면 배당 재투자를 포함한 투자 성과를 표·보드·차트로 제시하고,
검색 이력에서 여럿을 골라 수익률을 비교한다. 사용자가 쓰던 Google Apps Script 시뮬레이터의
동작을 요구사항으로 옮긴 것이다.

기술적 무게 중심은 **정밀도 이식**과 **출처 격리** 두 곳이다. 참조 구현이 JavaScript
`number`로 모든 금액을 계산하므로 옮기는 과정 전체가 헌법 원칙 VI 위반 구간이고, 시세
출처가 문서화되지 않은 엔드포인트라 언제 막혀도 이상하지 않다.

계산은 `simulation/`의 **순수 함수**로 둔다. 그래야 참조 구현과 직접 대조하는 테스트를
쓸 수 있고, 정밀도 차이가 다른 실패에 묻히지 않는다.

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — 신규 테이블 8개, Alembic 마이그레이션 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library |
| 타입·린트 | mypy strict, ruff / tsc, eslint |
| 시세 출처 | **Yahoo Finance chart 엔드포인트** (research R5-1) — 비공식 |
| 계산 위치 | **`simulation/`의 순수 함수** (research R5-4) |
| 표 행 생성 | 서버 (research R5-8) |
| 결과 저장 | **하지 않음.** 조건만 이력으로 (research R5-9) |
| 이력 보관 | 브라우저 `localStorage` (research R5-10) |

NEEDS CLARIFICATION 없음. 명세가 설계로 미룬 항목은 research에서 전부 결정했다.

## Constitution Check

헌법 v5.2.0의 9개 원칙과 제약 섹션에 대한 게이트.

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 시세 조회는 `aiohttp`, DB는 비동기 세션. 수집은 003의 워커 구조를 잇는다 |
| II. 데이터 소스 격리 | ⚠️ | 어댑터 격리·rate limit 설정화·백오프는 충족한다. **이용약관 항목이 미충족** — 아래 Complexity Tracking 참조 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행. 시뮬레이션이 순수 함수라 **참조 구현과 직접 대조**하는 단위 테스트가 가능하다. 출처는 저장된 응답 픽스처로 계약 테스트 |
| IV. 모듈화 | ✅ | 재투자 계산은 `simulation/`, 조회는 `repository/`, 조합은 `api/services/`. DB·HTTP 없이 단독 테스트된다 |
| V. 데이터 정합성·재현성 | ✅ | 값을 만들어 채우지 않는다. **원주가로 계산**하고 수정주가는 보관만 한다. 환율 결측은 값이 아니라 **날짜를 밝혀** 푼다 |
| VI. 금융 계산 정확성 | ⚠️→✅ | 참조 구현이 `number`를 쓴다. `Decimal`로 옮기되 **정밀도 규칙을 data-model 4절에 한 곳으로 모은다**. 정적 검사로 `float` 사용을 막는다 |
| VII. 반응형 UI | ✅ | 상태는 Zustand. 수집이 길면 진행 상태를 보이고 화면을 막지 않는다 |
| VIII. 한국어 문서화 | ✅ | 모든 산출물·주석·커밋이 한국어 |
| IX. MVP/YAGNI | ⚠️ | **자산군 순서 이탈.** 아래 Complexity Tracking 참조. 기능 범위 자체는 명세의 Out of Scope로 좁혔다 |
| DB 운영 규약 | ✅ | ORM만 쓴다. 방언 구문은 `db/dialect.py` 뒤로 격리된 기존 `upsert`를 재사용. 마이그레이션 스크립트로 관리 |
| 시계열 불변식 | ✅ | `(stock_id, 날짜)` 유니크 + upsert, `source`·`ingested_at`, 원본/정규화 분리, **수정주가와 원주가 구분 저장** |
| 명세 작성 규약 | ✅ | FR 신설 시 plan 추적성·tasks 참조를 같은 작업 단위에서 갱신한다 |

**위반 2건.** 둘 다 Complexity Tracking에 기록한다.

### 설계 후 재평가

| 원칙 | 판정 | 비고 |
|------|------|------|
| IV. 모듈화 | ✅ | 순수 함수 경계가 원칙 VI의 안전장치이기도 하다. 참조 구현과의 대조가 통합 테스트가 아니라 단위 테스트로 가능해진다 |
| V. 데이터 정합성 | ⚠️→✅ | 환율 결측 시 "가장 가까운 이전 고시일"을 쓰는 것이 보간에 가까운지 검토했다. **값을 만들어내지 않고 어느 날짜의 값인지 밝힌다**는 점이 경계다. 밝히지 않으면 곧바로 위반이므로 FR-041c를 요구사항으로 올렸다 |
| VI. 금융 계산 | ⚠️→✅ | 정밀도 규칙을 한 곳에 모으고 정적 검사를 두는 것으로 완화된다. 통화별 자릿수를 흩뿌리면 그 통화만 조용히 어긋난다 |

## Project Structure

### Documentation (this feature)

```
specs/005-stock-investment-simulation/
├── spec.md
├── plan.md               # 이 문서
├── research.md           # R5-1 ~ R5-10
├── data-model.md
├── quickstart.md         # 검증 시나리오 22개
├── contracts/
│   ├── rest-api.md
│   └── ui-wireframes.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```
backend/src/
├── ingestion/
│   └── yahoo/                     # [신규] 시세 어댑터. 응답 타입이 여기서 나가지 않는다
│       ├── client.py              #   chart·search 호출, 백오프, 세마포어
│       ├── parse.py               #   일봉·배당·분할로 정규화
│       └── errors.py
├── simulation/
│   └── reinvest.py                # [신규] **순수 함수.** 재투자 시뮬레이션
├── repository/
│   ├── stock.py                   # [신규] 종목·커버리지
│   └── stock_price.py             # [신규] 시세·배당·분할
├── api/
│   ├── services/
│   │   ├── stock_simulation.py    # [신규] 조회·환산·페이지 조합
│   │   └── stock_fx.py            # [신규] 초기 환전과 평가 환산
│   └── routes/
│       ├── stock_search.py        # [신규]
│       ├── stock_simulation.py    # [신규]
│       └── stock_settings.py      # [신규]
├── worker/
│   └── stock_runner.py            # [신규] 003 구조 계승. 점유는 FX와 분리
└── db/
    ├── models.py                  # [변경] 테이블 8개 추가
    └── migrations/                # [신규] 리비전 1개

frontend/src/
├── app/stock/page.tsx             # [신규] 시뮬레이션 화면
├── components/stock/
│   ├── StockSearch.tsx            # [신규] 검색·선택
│   ├── SimulationForm.tsx         # [신규] 시작일·원금·재투자
│   ├── PerformanceBoard.tsx       # [신규] 보드
│   ├── PerformanceTable.tsx       # [신규] 표 (004의 스크롤 방식)
│   ├── PerformanceChart.tsx       # [신규] 잔고·수익률
│   ├── SimulationHistory.tsx      # [신규] 이력·선택
│   └── ComparisonChart.tsx        # [신규] 비교
├── stores/stockStore.ts           # [신규]
├── lib/simulationHistory.ts       # [신규] localStorage 보관
└── app/settings/page.tsx          # [변경] 수수료·세율 추가
```

**구조 선택**: 웹 애플리케이션. 001~004가 세운 배치를 잇는다.

`simulation/reinvest.py`를 따로 두는 이유는 **원칙 IV이자 원칙 VI의 안전장치**이기 때문이다.
DB·HTTP를 모르는 함수여야 참조 구현과 같은 입력을 넣어 같은 출력이 나오는지 단위 테스트로
확인할 수 있다.

`stock_fx.py`를 나눈 이유는 **초기 환전과 평가 환산이 서로 다른 환율을 쓰기** 때문이다
(FR-041b). 한 함수에 두면 어느 쪽 환율인지 호출부마다 판단해야 하고, 틀려도 값이
그럴듯하다.

## 요구사항 추적성

**범위 표기(`FR-001~003`)를 쓰지 않는다.** 63개 규모에서는 개별 ID가 문자열로
있어야 누락을 기계적으로 찾을 수 있다 — 004에서 미참조 17건을 그렇게 잡았다.

| 요구사항 | 설계 근거 |
|----------|-----------|
| FR-001, FR-003 (입력) | contracts/rest-api `GET /api/stock/simulation` 질의 매개변수 |
| FR-002, FR-002a, FR-002b, FR-002c (종목 선택·검색) | contracts/rest-api `GET /api/stock/search`, ui-wireframes W1, research R5-2 |
| FR-004, SC-016 (시세 없음) | contracts/rest-api 오류표 `unknown_stock`, quickstart 20 |
| FR-005 (상장 이전) | contracts/rest-api 오류표 `before_listing`, quickstart 18 |
| FR-006, FR-008, FR-009 (매수·재투자) | `simulation/reinvest.py`, research R5-4, quickstart 6 |
| FR-007, SC-006 (정수 매수) | data-model 5절, quickstart 5 |
| FR-007a, FR-007b, SC-024, SC-025 (수수료 산식) | data-model 5절, quickstart 5 |
| FR-010, FR-010a, FR-010b, SC-017 (분할) | data-model `stock_split`, research R5-3, quickstart 8 |
| FR-011, FR-012, SC-005 (원주가·수정주가) | data-model `stock_price`, research R5-3, quickstart 21 |
| FR-013, SC-003, SC-004 (잔고·총자산) | data-model 3절, quickstart 5 |
| FR-014, SC-002 (재현성) | research R5-3 — 원주가는 바뀌지 않는다 |
| FR-014a, FR-014b, SC-026, SC-027 (시세 단절) | contracts/rest-api `asOf`·`isFinal`, ui-wireframes W2, quickstart 16 |
| FR-015, FR-016 (설정 항목) | contracts/rest-api `/api/stock/settings`, data-model `stock_setting` |
| FR-017, SC-007 (설정 반영) | contracts/rest-api 설정 절, ui-wireframes 갱신 범위, quickstart 13 |
| FR-018, SC-008 (적용 조건 표시) | contracts/rest-api `condition`, quickstart 13 |
| FR-019, FR-020, FR-021, FR-022, FR-023, SC-009 (초기 환전) | `api/services/stock_fx.py`, data-model 6절, research R5-6, quickstart 9 |
| FR-024, FR-025, FR-027, FR-028 (표 구성) | contracts/rest-api 응답 `rows`, ui-wireframes W4, quickstart 7 |
| FR-026 (월 행의 빈 칸) | contracts/rest-api 월 행 키 생략, quickstart 7 |
| FR-029, FR-030, SC-012 (스크롤) | 004의 방식 계승, ui-wireframes W4, quickstart 14 |
| FR-031, FR-032, SC-013 (보드) | contracts/rest-api `summary`, ui-wireframes W2, quickstart 5 |
| FR-033, FR-034 (차트) | ui-wireframes W3, 001의 결측 렌더링 규칙, quickstart 15 |
| FR-035, FR-036, SC-014 (이력) | `lib/simulationHistory.ts`, ui-wireframes W5, quickstart 17 |
| FR-037, FR-037a, FR-037b, SC-018 (이력 보관) | research R5-10, ui-wireframes W5, quickstart 17 |
| FR-038, FR-039, FR-040, SC-015 (비교) | ui-wireframes W6, quickstart 17 |
| FR-041, SC-019 (기준 통화) | data-model 6절, ui-wireframes W2, quickstart 12 |
| FR-041a, FR-041b, SC-020, SC-021 (평가 환산) | data-model 6절, research R5-6, quickstart 10 |
| FR-041c (환율 결측) | research R5-6, ui-wireframes W4, quickstart 11 |
| FR-042, SC-010 (보간 금지) | research R5-6, quickstart 21 |
| FR-043, FR-046 (수집 범위·출처 기록) | data-model `stock_coverage`·`stock_raw_response`, research R5-7 |
| FR-044, SC-022 (재수집 없음) | data-model `stock_coverage`, quickstart 3 |
| FR-045, SC-023 (재개) | research R5-7, quickstart 3 |
| FR-047, SC-001a (수집 진행) | contracts/rest-api 202·SSE, ui-wireframes W7, quickstart 2 |
| FR-048, SC-028 (중복 수집 차단) | contracts/rest-api 202 절, ui-wireframes W7, quickstart 4 |
| FR-049, SC-029 (부분 결과 금지) | contracts/rest-api 202 절, ui-wireframes W7, quickstart 2 |
| SC-001 (응답 시간) | quickstart 3 — 시세가 보관된 경우의 기준이다 |
| SC-011 (재투자 차이) | quickstart 6 |
| SC-030, SC-031 (검색 표시·직접 입력 금지) | contracts/rest-api 검색 응답, ui-wireframes W1, quickstart 1 |

## 위험과 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| **시세 출처가 막힌다** | 신규 종목 수집 불가 | 어댑터 격리로 교체 가능하게 둔다. 이미 받은 구간은 계속 쓸 수 있다(FR-044). **"언젠가"가 아니라 "언제"의 문제로 전제한다** |
| **`float` 이식 누락** | 값이 조용히 틀린다 | 정밀도 규칙을 data-model 4절 한 곳에 모으고, `simulation/`·`repository/`에 `float(` 정적 검사를 건다 |
| **분할 판정이 틀린다** | 보유 주식 수가 배수로 어긋남 | 제공처를 그대로 믿되 적용 내역을 남긴다(FR-010b). quickstart 8에서 다른 자료와 대조한다 |
| **수정주가를 섞어 쓴다** | 배당 이중 계산 | 컬럼을 나눠 두고(`close_adjusted`), 시뮬레이션이 그 컬럼을 읽지 않는지 테스트로 확인 |
| 환율 결측일이 많다 | 환산 불가 구간 | 가장 가까운 이전 고시일을 쓰되 **그 날짜를 밝힌다**(FR-041c). 밝히지 않으면 원칙 V 위반 |
| 첫 수집이 길다 | 사용자가 고장으로 여김 | 003의 진행 표시·점유 구조를 잇는다(FR-047·048) |

## Complexity Tracking

헌법 위반 2건을 기록한다. **기록하지 않으면 "한 번 건너뛰어도 된다"가 규칙이 되고,
해당 원칙은 지키지 않아도 되는 문장으로 남는다.**

### 1. 원칙 IX — 자산군 확장 순서 이탈

| 항목 | 내용 |
|------|------|
| **위반** | 순서가 FX → **가상자산** → 주식/ETF인데 가상자산을 건너뛰고 주식을 먼저 한다 |
| **왜 필요한가** | 사용자가 실제로 쓰던 도구가 주식 시뮬레이터이고, 그 수요가 지금 있다 |
| **왜 더 단순한 대안이 부족한가** | 원칙 IX의 Rationale은 "하나를 끝까지 관통해봐야 재사용할 추상화를 안다"이다. **FX 한 바퀴(001~004)로 그 목적은 이미 달성됐다** — 수집·커버리지·재개·점유·관측·표·차트의 모양이 잡혔고, 이 기능이 그것을 그대로 잇는다. 다음이 가상자산이냐 주식이냐는 그 Rationale이 가르는 문제가 아니다 |
| **헌법을 고치지 않는 이유** | 순서 자체가 틀렸다는 근거가 없다. 한 번의 이탈 때문에 규칙을 무르면 규칙이 없어진다 |
| **가상자산은 언제 하는가** | **005 완료 직후, 006으로 수행한다.** 미루는 것이지 없애는 것이 아니다 |
| **선례로 삼지 않는다** | 006(가상자산) 이후로는 순서를 지킨다. 이 이탈을 근거로 다음 자산군의 순서를 바꾸지 않는다 |

### 2. 원칙 II — 데이터 소스 이용약관

| 항목 | 내용 |
|------|------|
| **위반** | 원칙 II가 "각 데이터 소스의 이용약관·라이선스를 준수"를 MUST로 요구한다. Yahoo는 2017년 공식 API를 종료했고 chart 엔드포인트는 **문서화되지 않은 내부 호출**이다. 약관 준수를 명확히 주장할 수 있는 상태가 아니다 |
| **왜 필요한가** | 일봉·배당·분할 셋을 한 번에 주면서 국내·미국·일본을 덮는 출처가 사실상 이것뿐이다. 공공데이터포털은 시세와 배당이 별도 API이고 **분할 정보를 제공하는 API가 확인되지 않는다** — 분할을 못 받으면 FR-010이 성립하지 않는다 (research R5-1) |
| **왜 더 단순한 대안이 부족한가** | 시장별로 출처를 나누면 어댑터가 셋 이상이 되고 KR 분할 문제는 그대로 남는다. 유료 API는 개인 도구의 전제를 벗어나고, 무료 구간은 일 25회 수준이라 백필이 불가능하다 |
| **완화** | ① 개인·단일 사용자·비상업적 이용 ② **보수적인 호출 간격을 설정으로 선언**한다 — 공격적 폴링이 차단의 주된 원인이다 ③ **어댑터 격리를 엄격히 지킨다.** 원칙 II가 어댑터를 요구하는 이유가 정확히 이 상황이다 |
| **다시 볼 시점** | 출처가 막히거나, 세 시장을 덮는 공식 출처가 생기면. 어댑터 경계를 지켜 두면 교체 비용이 한 파일이다 |
| **사용자 확인** | **2026-09-27 승인됨** — 참조 Apps Script가 쓰던 비공식 엔드포인트를 그대로 쓴다. "일단은"이라는 조건이 붙은 **잠정 결정**이므로 위 "다시 볼 시점"이 그만큼 중요하다. 이 판단은 **개인 이용이라는 전제에 기댄다** — 도구를 공개하거나 여러 사용자에게 제공할 계획이 생기면 전제가 깨지므로 출처를 다시 정해야 한다 |

## Phase 0 산출물

[research.md](./research.md) — 결정 10건 (R5-1 ~ R5-10)

## Phase 1 산출물

- [data-model.md](./data-model.md) — 신규 테이블 8개, 정밀도 규칙, 매수 산식
- [contracts/rest-api.md](./contracts/rest-api.md) — 엔드포인트 4개
- [contracts/ui-wireframes.md](./contracts/ui-wireframes.md) — W1 ~ W7
- [quickstart.md](./quickstart.md) — 검증 시나리오 22개

## 다음 단계

`/speckit-tasks`로 의존성 순서가 매겨진 태스크를 생성한다.
