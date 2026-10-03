# Implementation Plan: 주식 시뮬레이션 개선 — 시작일·종목 검색·환전

**Branch**: `006-stock-simulation-enhancements` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-stock-simulation-enhancements/spec.md`

## Summary

005의 주식 투자 시뮬레이션을 세 방향으로 다듬는다.

1. **시작일** — 기본 2020-01-01, 월·년 이동. 날짜 산술은 정수로 한다(research R6-7).
2. **종목 검색** — 키움증권 REST API로 국내(KOSPI·KOSDAQ·ETF·리츠)·미국(NYSE·NASDAQ·AMEX) 목록을
   받아 로컬 DB에 두고, 메모리 색인에서 한글·초성·영문·코드로 찾는다(R6-1~R6-5). 일본은 005의 외부
   검색을 그 시장에만 남긴다(R6-12). 고른 종목은 그 자리에서 등록한다(R6-17).
3. **환전** — 엔화 고시 단위를 반영하고(R6-9), 필요한 환율이 없으면 003의 시작 큐로 수집한다(R6-10).
   원금 통화는 원화 또는 종목 통화만 허용한다(R6-11).

**설계 중 005의 결함 셋을 확인했다.** 셋 다 오류 없이 그럴듯하게 보이거나, 테스트를 통과하면서 실제
경로에서만 깨진다. 이 기능이 함께 닫는다.

| 결함 | 근거 | 닫는 곳 |
|------|------|---------|
| 고른 종목을 저장하는 경로가 없다 — 실제 사용에서 모든 시뮬레이션이 "알 수 없는 종목" | `ensure_stock` 호출처 0 | FR-030b, R6-17 |
| `first_available_date`가 채워지지 않아 휴일 시작을 거절한다 — 기본값 2020-01-01이 매번 거절됨 | `first_trade_date` 저장처 0 | FR-005a, R6-8, R6-17 |
| 엔화 고시 단위를 버린다(100배), 교차 통화가 원화를 거치지 않는다 | `load_rates`, 직접 재현 | FR-042, FR-050 |

외환 쪽에서도 하나를 찾았다. 001의 `ensure_background_job`은 작업과 점유만 만들고 워커에 넘기지
않는다(R6-10). 006은 그 함수를 직접 쓰지 않지만 **영향을 받는다** — 외환 화면이 먼저 남긴 고아 점유가
006의 수집 요청을 막는다. **006에서 함께 고친다**(FR-046a, analyze H2).

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — **신규 테이블 5개**, Alembic 마이그레이션. 기존 테이블 구조 변경 없음 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library |
| 타입·린트 | mypy strict, ruff / tsc, eslint |
| 목록 출처 | **키움증권 REST API** — 공식, 인증 필요. 목록에만 쓴다 (R6-1, R6-2) |
| 시세 출처 | 005 그대로 (Yahoo chart, 원칙 II 잠정 결정 유지) |
| 검색 | 메모리 색인 + `src/search/`의 순수 함수 (R6-5) |
| 갱신 실행 | 앱 수명과 함께 사는 목록 갱신 워커, DB 점유 (R6-3) |
| 환율 수집 | 고쳐진 `ensure_background_job` → 003의 `StartQueue`. 외환 화면과 같은 수집 표 (R6-10) |
| 성능 목표 | 검색 결과의 95%가 입력을 멈춘 뒤 0.5초 안 (SC-001). 입력 대기 150ms 포함 |
| 규모 | 검색용 목록 국내 3,935건 + 미국 12,745건 (T005 실측 2026-10-02). 단위마다 한 쪽에 전부 온다 |
| 제약 | 백엔드 단일 워커(CLAUDE.md), 테스트는 네트워크 없이(헌법 원칙 III) |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 키움 호출은 aiohttp. 갱신은 워커 태스크라 검색 요청이 기다리지 않는다(FR-017). 검색 색인은 메모리라 I/O가 없다 |
| II. 데이터 소스 격리 | ✅ | 어댑터를 `ingestion/kiwoom/`에 격리하고 한도·재시도·간격을 설정으로 둔다. 비밀은 `.env`. 이용약관은 **사용자가 확인했다(2026-10-02)** — 개인 이용 전제, Complexity Tracking 참조 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행. **테스트를 구현보다 먼저 커밋한다** — 페이즈마다 테스트 커밋(최초 실패 요약 포함)과 구현 커밋을 나눈다(tasks Notes, analyze C2). 키움 응답은 **실제 응답을 저장한 픽스처**로 계약 테스트한다(공식 예시는 자리 표시용이라 쓰지 않는다, R6-2). 신규 데이터 소스이므로 계약 테스트가 품질 게이트다 |
| IV. 모듈화 | ✅ | 일치 판정·순위·시세 식별자 변환은 `src/search/`의 순수 함수(DB·HTTP 없음). 날짜 산술은 프론트엔드 순수 함수. 엔화 단위 환산은 `simulation/fx_convert.py` |
| V. 데이터 정합성 | ✅ | 목록에서 빠진 종목을 지우지 않는다. 일부만 받은 목록·축소된 목록으로 교체하지 않는다(FR-015, FR-018, FR-018a). 수집으로 채울 수 없는 구간의 환율을 값으로 메우지 않는다(FR-043a) |
| VI. 금융 계산 정확성 | ✅ | 엔화 단위 나눗셈은 `Decimal`. 목록의 가격(`lastPrice`)은 저장하지 않는다 — 시세가 두 출처에서 섞일 자리를 없앤다. 원금 칸의 쉼표(FR-053)는 **표시 계층에만** 있고 요청·이력·계산에는 쉼표 없는 문자열이 간다(서버가 `Decimal`로 읽는다) |
| VII. 반응형 UI | ✅ | 로컬 검색과 일본 검색을 따로 그린다(FR-027). 갱신·수집은 화면을 막지 않는다 |
| VIII. 한국어 문서화 | ✅ | 모든 산출물·주석·커밋이 한국어 |
| IX. MVP/YAGNI | ✅ | 새 자산군이 아니라 주식 자산군을 다듬는다. 범위를 명세의 Out of Scope로 좁혔다. "가상자산은 006" 기록을 갱신한다(FR-070) |
| DB 운영 규약 | ✅ | ORM만. 갱신 중복 차단은 기본 키 INSERT 충돌(005의 점유와 같다). 검색에 DB 방언(정규식·콜레이션)을 쓰지 않는다(R6-5) |
| 시계열 불변식 | ✅ | 목록 원본을 분리 보관하고 **지우지 않는다** — 같은 본문은 한 번만 저장한다(R6-13, analyze C1). `stock_listing`에 `source`·`ingested_at` 기록. 시각은 UTC, "오늘"만 한국 시간 날짜 |
| 명세 작성 규약 | ✅ | 설계 중 드러난 요구사항 5건(FR-018a·FR-022 보강·FR-030a·FR-030b·FR-043a)과 analyze에서 드러난 1건(FR-046a)을 spec에 같은 작업 단위로 더했다. 아래 추적성 표가 모든 FR·SC를 잇는다 |

### 설계 후 재평가

| 원칙 | 판정 | 비고 |
|------|------|------|
| II. 데이터 소스 격리 | ⚠️→✅ | 이용약관을 사용자가 확인했다(2026-10-02). **토큰을 메모리에만** 두는 것으로 비밀 노출 경로를 줄였다(공식 클라이언트는 토큰을 파일에 저장한다, R6-1). 원본 보관에서 헤더를 빼 인증 헤더가 섞이지 않게 했다(data-model 4a절) |
| III. TDD | ✅ | 축소 검사(FR-018a)·HTTP 200 + `return_code≠0` 판정(R6-1)은 **실패 응답 픽스처**로 검증한다. 성공 픽스처만 있으면 두 방어선이 테스트되지 않은 채 통과한다. 진행 스트림의 실시간 전달(FR-045a)은 흉내 낸 테스트로 잡히지 않아 **실제 브라우저 확인(T119)을 태스크로 둔다** |
| V. 데이터 정합성 | ⚠️→✅ | 시작 가능 날짜를 메타데이터가 아니라 **실제 일봉**으로 판정하게 바꿨다(R6-8). 메타데이터를 믿으면 첫 매수가 몰래 밀린다 — 값을 만들지는 않지만 사용자가 고른 조건을 바꾸는 것이라 원칙 V의 취지(재현성)에 걸린다 |
| V. 원본 보존 | ❌→✅ | 처음 설계는 원본을 최근 7회분만 남기고 지웠다 — 헌법 원칙 V "원본 응답을 보존"(MUST) 위반이었다(analyze C1). 지우지 않고 내용 주소로 중복을 없애는 것으로 바꿨다(R6-13) |
| VI. 금융 계산 | ✅ | `LISTING_SHRINK_THRESHOLD`는 금융 값이 아니지만 `Decimal`로 읽는다 — 금융 계층의 `float` 정적 검사를 예외 없이 유지하기 위해서다 |

## Project Structure

### Documentation (this feature)

```text
specs/006-stock-simulation-enhancements/
├── spec.md              # 명세 (FR 68, SC 24 — 구현 단계 반영으로 FR-047a·FR-065·FR-034·SC-007b, 반복 2026-10-03으로 FR-045a·FR-053·SC-017~019 추가)
├── plan.md              # 이 파일
├── research.md          # R6-1 ~ R6-17
├── data-model.md        # 신규 테이블 5개, 설정, 원금 통화
├── quickstart.md        # 검증 시나리오 26개(24~26은 반복 2026-10-03)
├── contracts/
│   ├── rest-api.md      # 검색 2종, 종목 등록, 시뮬레이션 변경점
│   └── ui-wireframes.md # W1 시작일 ~ W4 수집 중
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks가 만든다
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── ingestion/kiwoom/            # 신규 — 목록 출처 어댑터 (R6-1)
│   │   ├── client.py                #   토큰(메모리), 연속조회, 재시도
│   │   ├── parse.py                 #   국내·미국 목록 → 도메인 타입. 출처 필드명은 여기서만
│   │   └── errors.py                #   auth / rate_limit / network / invalid
│   ├── search/                      # 신규 — 순수 함수 (R6-5, R6-6)
│   │   ├── hangul.py                #   정규화, 초성 열, 받침 대기 판정
│   │   ├── match.py                 #   일치 판정, 순위, 결정적 정렬
│   │   └── price_symbol.py          #   목록 종목 → 005 시세 식별자
│   ├── repository/
│   │   ├── stock_listing.py         # 신규 — 목록·갱신 기록·원본. 삭제 질의 없음 (T083)
│   │   └── stock_listing_lock.py    # 신규 — 갱신 점유(지우는 것은 점유뿐)
│   ├── api/services/
│   │   ├── listing_index.py         # 신규 — 메모리 색인, 버전 확인
│   │   ├── listing_refresh.py       # 신규 — 갱신 판정(오늘·간격·상한·막힘), 교체 트랜잭션
│   │   ├── stock_selection.py       # 신규 — 고른 종목 등록 (R6-17)
│   │   ├── stock_collect.py         # 변경 — 환율 판정 추가 (R6-10)
│   │   ├── collection_gate.py       # 변경 — ensure_background_job이 시작 큐로 넘기고 수집 표를 돌려준다 (R6-10, FR-046a)
│   │   ├── stock_fx.py              # 변경 — 고시 단위 반영 (R6-9)
│   │   └── stock_simulation.py      # 변경 — 원금 통화 판정, 시작 가능 날짜 (R6-8, R6-11)
│   ├── api/routes/
│   │   ├── stock_search.py          # 변경 — 로컬 검색 + /external 분리 (R6-12)
│   │   ├── stock_selection.py       # 신규
│   │   ├── stock_simulation.py      # 변경 — 202 fx, 오류 본문
│   │   ├── stock_series.py          # 변경 — 202 fx
│   │   ├── series.py·daily.py·rates.py·latest.py  # 변경 — 외환 202에 state·busyWith, jobId null 허용 (FR-046a)
│   │   ├── collection.py            # 변경 — 스트림의 busyWith를 프레임마다 읽는다 (R6-10). SSE 머리글 `no-transform` (T117, R6-19)
│   │   ├── collect.py               # 변경 — SSE 머리글 `no-transform` (T117, R6-19)
│   │   └── stock_progress.py        # 변경 — 스냅샷에 `daysDone`·`daysTotal`, SSE 머리글 `no-transform` (T117, FR-045a)
│   ├── api/collection_stream.py     # 변경 — busy_with_fn (R6-10)
│   ├── simulation/fx_convert.py     # 변경 — per_unit
│   ├── worker/listing_worker.py     # 신규 — 목록 갱신 워커, 국내·미국 두 줄 (R6-3)
│   ├── worker/listing_queue.py      # 신규 — 갱신 요청 큐(단위로 중복 거르기). 주식 큐와 섞지 않는다
│   ├── worker/stock_worker.py       # 변경 — 출처가 심볼을 모르면 작업 사유에 표지 (FR-032, R6-6), 출처를 연다 (T096)
│   ├── ingestion/yahoo/errors.py    # 변경 — "구간에 시세 없음"(HTTP 400)은 빈 구간 (T097)
│   ├── ingestion/yahoo/parse.py     # 변경 — 분할 비율이 실수(5.0)로 온다. 양의 정수만 받는다 (T103). 반영가 → 원주가 (`restore_unadjusted`, R6-18)
│   ├── ingestion/yahoo/client.py    # 변경 — 청크마다 분할 기록(월봉)을 함께 받아 되살린다. 원본 둘을 돌려준다 (T108, R6-18)
│   ├── worker/stock_runner.py       # 변경 — 받은 원본을 모두 저장한다 (T108)
│   ├── db/models.py                 # 변경 — 신규 테이블 5개
│   ├── db/migrations/versions/      # 신규 마이그레이션 1개
│   └── config/settings.py           # 변경 — 키움·목록 설정 (data-model 7절)
├── scripts/capture_kiwoom_fixtures.py   # 신규 — 계약 테스트 픽스처 캡처(수동 실행)
└── tests/
    ├── contract/test_kiwoom_*.py    # 실제 응답 픽스처 + 실패 응답 픽스처
    ├── unit/test_search_*.py        # 초성·순위·식별자 표 검증
    ├── unit/test_layer_boundaries.py, test_no_secret_in_events.py   # 확장
    └── integration/test_listing_*.py, test_selection_*.py, test_fx_gate_*.py

frontend/
├── next.config.ts                   # 변경 — 프록시를 `/api/*` 전체로. 005가 `/api/stocks`를 빠뜨렸다 (T110)
├── src/
│   ├── lib/startDate.ts             # 신규 — 정수 날짜 산술 (R6-7)
│   ├── lib/searchSequence.ts        # 신규 — 응답 번호로 늦은 결과 폐기 (R6-12)
│   ├── lib/collectionStream.ts      # 재사용 — 003 수집 스트림 구독(환율 대기)
│   ├── lib/principalFormat.ts       # 신규 — 원금 쉼표 표시·쉼표 없는 값 (T115, FR-053)
│   ├── lib/displayCode.ts           # 신규 — 시세 식별자 → 표시용 코드 (T116, FR-025)
│   ├── lib/stockProgressStream.ts   # 변경 — 스냅샷 `daysDone`·`daysTotal` (T118)
│   ├── components/stock/
│   │   ├── StartDateInput.tsx       # 신규 — W1, W1a
│   │   ├── StockSearch.tsx          # 변경 — 두 영역, 목록 상태, 잘림, W2a. 종목명(코드) (T116)
│   │   ├── SimulationForm.tsx       # 변경 — 원금 통화 제한 W3. 원금 쉼표 (T115)
│   │   ├── SimulationHistory.tsx    # 변경 — 막힌 조합 항목 표시
│   │   └── CollectingNotice.tsx     # 변경 — 환율 줄 W4, W4a. 받은 날 / 받을 날 (T118)
│   ├── stores/stockStore.ts         # 변경 — 시작일 기본값, 종목 등록, 환율 대기 재요청
│   └── lib/types.ts                 # 변경 — 검색 응답, 202 fx, 오류 본문
└── tests/                           # 각 변경에 대응하는 테스트
```

**Structure Decision**: 001~005와 같은 웹 앱 구조(`backend/` + `frontend/`)를 잇는다. 새 최상위
패키지는 `src/search/` 하나다 — 일치 판정은 금융 계산이 아니라 `simulation/`에 두지 않고, DB·HTTP를
모르는 순수 함수라 `api/services/`에도 두지 않는다. `test_layer_boundaries`에 "`search`는
`repository`·`api`·`db`·`ingestion`을 임포트하지 않는다"를 더한다.

## 요구사항 추적성

모든 FR·SC를 설계 근거와 잇는다. tasks.md는 이 표의 각 줄을 참조해야 한다(헌법 명세 작성 규약).

| 요구사항 | 설계 근거 |
|----------|-----------|
| FR-001 (기본 시작일) | `stockStore` 초기값, ui-wireframes W1, quickstart 13 |
| FR-002 (월·년 이동) | `lib/startDate.ts`, `StartDateInput.tsx`, ui-wireframes W1, quickstart 13 |
| FR-003, SC-012 (없는 날짜는 말일로) | research R6-7, `lib/startDate.ts` 표 검증, quickstart 13 |
| FR-004 (어제 이후 금지) | research R6-7, ui-wireframes W1, quickstart 13 |
| FR-005, SC-013 (상장 이전 사전 안내, 하한 이전이면 실행 막음) | research R6-8 1단계, contracts/rest-api `before_listing`(`basis: listing`), ui-wireframes W1a(실행 막음), quickstart 14·15 |
| FR-005a, SC-013a (상장일·출처 시세 시작일은 하한, 시작 월 전체의 실제 일봉 기준, 빈 구간 응답) | research R6-8 2단계·"구현 단계에서 정한 것", contracts/rest-api `basis: price_start`, `ingestion/yahoo/errors.py`(빈 구간 400, tasks T097), quickstart 14·15·실행 기록 |
| FR-006 (종목을 바꿔도 시작일 유지) | `stockStore`, ui-wireframes W1, quickstart 13 |
| FR-010 (국내 목록 범위) | research R6-2 단위 표, data-model `stock_listing`, quickstart 3 |
| FR-010a (ETF·리츠의 거래 시장) | research R6-6, `search/price_symbol.py`, quickstart 11 |
| FR-011 (미국 목록) | research R6-2, data-model `stock_listing`, quickstart 5 |
| FR-012 (키움은 목록에만) | research R6-1, data-model 1절 "`lastPrice` 저장하지 않음", Constitution Check VI |
| FR-013, SC-005 (하루 한 번) | research R6-3 판정 1, data-model `stock_listing_refresh.as_of_date`, quickstart 8 |
| FR-013a, SC-005a (간격·상한 재시도) | research R6-3 판정 4·실패 종류 표, data-model 7절, quickstart 9 |
| FR-013b (인증 실패는 재시작까지) | research R6-3 "인증 실패 막힘", data-model 5절, quickstart 9 |
| FR-014 (다운로드 한 번, 남은 점유 회수) | research R6-3 DB 점유, data-model 3절 `stock_listing_lock`·정체 회수, quickstart 2 |
| FR-015 (단위별 교체, 국내가 미국을 기다리지 않음) | research R6-2·R6-4, research R6-3 "워커는 국내·미국 두 줄", data-model `stock_listing_refresh`, quickstart 2 |
| FR-016, SC-004 (실패해도 지우지 않음) | research R6-4, quickstart 9 |
| FR-017 (다운로드 중엔 이전 목록) | research R6-3, contracts/rest-api `lists[].state: refreshing`, quickstart 2 |
| FR-018 (중단되면 교체하지 않음) | research R6-4 단계 1, 계약 테스트(중간 쪽 실패 픽스처) |
| FR-018a (축소 검사) | research R6-4 단계 2, data-model 7절 `LISTING_SHRINK_THRESHOLD`, 계약 테스트(짧은 목록 픽스처) |
| FR-019, SC-016 (빠진 종목 유지) | research R6-4 단계 3, data-model `stock_listing` 상태 전이, contracts/rest-api `listingStatus` |
| FR-019a (코드로 식별, 이전상장 한계) | data-model `UNIQUE (country, code)`, research R6-4 이전상장, research R6-6 알려진 한계 |
| FR-020 (국내 검색 필드) | research R6-5 색인, `search/match.py`, quickstart 3 |
| FR-021 (미국 검색 필드, 티커 두 표기) | research R6-5 색인, `api/services/listing_index.py`(목록·시세 출처 티커), quickstart 5 |
| FR-022, SC-002 (초성 규칙·받침 대기) | research R6-5 일치 규칙 표, `search/hangul.py`, quickstart 3 |
| FR-023, SC-003 (결정적 순서) | research R6-5 순위, contracts/rest-api 순서 절, quickstart 4 |
| FR-024 (잘림 표시) | contracts/rest-api `truncated`, ui-wireframes W2, quickstart 4 |
| FR-025 (결과 표시 항목) | contracts/rest-api 결과 필드, ui-wireframes W2 |
| FR-025 종목명(코드), SC-019 (반복 2026-10-03) | research R6-20, `frontend/src/lib/displayCode.ts`, `StockSearch.tsx`(결과 줄·고른 종목 표시), ui-wireframes W2, tasks T112·T116, quickstart 25 |
| FR-026 (일본은 외부 검색, 국내·미국 제외) | research R6-12, contracts/rest-api `/search/external`, quickstart 6 |
| FR-027, SC-015 (로컬이 외부를 기다리지 않음) | research R6-12 엔드포인트 분리, ui-wireframes W2, quickstart 6 |
| FR-028, SC-006 (목록 없음 ≠ 결과 없음) | contracts/rest-api `lists`, data-model 2절 상태 표, ui-wireframes W2a, quickstart 1 |
| FR-028a (대체 없음, 사유별 할 일) | contracts/rest-api `lists[].action`, ui-wireframes W2a, quickstart 1 |
| FR-029 (기준 시각 표시, 한국 시간) | contracts/rest-api `lists[].asOf`, ui-wireframes W2, `frontend/src/lib/format.ts` `formatKst` |
| FR-029a (늦은 결과 폐기) | research R6-12, `lib/searchSequence.ts`, quickstart 7 |
| FR-030, SC-007 (005 식별자 재사용) | research R6-6, `search/price_symbol.py`, contracts/rest-api `/selection`, quickstart 10 |
| FR-030a (미국은 티커로 같은 종목) | research R6-6, contracts/rest-api `/selection`, quickstart 12 |
| FR-030b, SC-007a (고른 종목 등록, 실제 출처로 결과까지) | research R6-17, research R6-6 역변환(이력 재실행 경로), `api/services/stock_selection.py`, `search/price_symbol.py` 왕복 검사, contracts/rest-api `/selection`·종목 미등록 절, `worker/stock_worker.py`(출처를 연다, tasks T096), quickstart 10·실행 기록 |
| FR-031, SC-008 (시장·기호 정확히, 검증 표본) | research R6-6 티커 표기 다섯 갈래, 계약 테스트(클래스 주식), quickstart 11·12·실행 기록 |
| FR-032 (출처가 모름 ≠ 시세 없음) | research R6-6(수집 작업의 표지), contracts/rest-api `price_symbol_unknown`·진행 스트림 `status`, quickstart 12 |
| FR-033 (005 이력 유효) | data-model 8절, research R6-17 재실행 경로 |
| FR-034, SC-007b (반영가를 원주가로 되살림, 분할 이중 적용 없음) | research R6-18, `ingestion/yahoo/parse.py` `restore_unadjusted`·`parse_splits`, `ingestion/yahoo/client.py`(분할 기록 요청), `worker/stock_runner.py`(원본 둘 저장), 마이그레이션(주식 커버리지 비우기), data-model 6절, tasks T102~T108, quickstart 23·실행 기록 결함 5 |
| FR-040 (원화 원금 환전 규칙 유지) | 005 `stock_fx.py`, research R6-9 |
| FR-041 (첫 매수일 환율) | 005 `build_exchange` 유지, quickstart 16 |
| FR-042, SC-009 (고시 단위) | research R6-9, `simulation/fx_convert.py` `per_unit`, contracts/rest-api 7절, quickstart 16 |
| FR-043, SC-010 (환율 수집) | research R6-10, contracts/rest-api 202 `fx`, ui-wireframes W4, quickstart 17 |
| FR-043a (수집으로 채울 수 없는 구간 — 출처에 없음·설정 밖) | research R6-10 판정 표, data-model 6절 `currency.first_available_date`·탐색 시작일, contracts/rest-api `fx_not_available_before`(`reason`), ui-wireframes W4a, quickstart 19 |
| FR-044 (시작일부터 필요 구간 전체) | research R6-10 필요한 구간 |
| FR-045 (둘 다 끝나야 결과) | contracts/rest-api 202 절, ui-wireframes W4, quickstart 17 |
| FR-045a, SC-017 (받은 날 / 받을 날, 진행의 실시간 전달 — 반복 2026-10-03) | research R6-19, contracts/rest-api 진행 스트림 `daysDone`·`daysTotal`·SSE 머리글, `api/routes/stock_progress.py`·`collection.py`·`collect.py`, `lib/stockProgressStream.ts`, `CollectingNotice.tsx`, ui-wireframes W4, tasks T113·T114·T117·T118·T119, quickstart 26 |
| FR-046 (다른 통화 수집 대기, 화면이 다시 요청) | research R6-10 한 번에 한 통화·"화면이 다시 요청하는 시점"·스트림 `busyWith`, contracts/rest-api `fx.state: waiting`·6a절, quickstart 18 |
| FR-046a (실제로 실행되는 수집 경로) | research R6-10 "발견한 결함"·수집 표, `api/services/collection_gate.py`, contracts/rest-api 6a절(외환 202), quickstart 18 |
| FR-047 (수집 실패 시 메우지 않음) | research R6-10, Constitution Check V |
| FR-047a (수집 실패 뒤 자동으로 다시 요청하지 않음) | `frontend/src/stores/stockStore.ts`(실패 사유 표시, `watchFx`가 `GET /api/fx/jobs`로 끝난 환율 작업의 성패를 확인 — tasks T099·T100), research R6-6(심볼 미확인은 다시 수집하지 않음)·R6-10, quickstart 실행 기록 |
| FR-050, SC-011 (원금 통화 제한) | research R6-11, contracts/rest-api `currency_pair_not_allowed`, quickstart 20 |
| FR-050a (모든 경로에서 거절) | research R6-11 서버 한 함수, quickstart 20 `curl` |
| FR-050b, SC-011a (통화를 몰래 바꾸지 않음) | research R6-11 화면, ui-wireframes W3, quickstart 20 |
| FR-050c (이력의 막힌 항목 보존·사유 표시) | research R6-11 이력, data-model 8절, `SimulationHistory.tsx` |
| FR-050d (EUR 제외) | data-model 8절, ui-wireframes W3 |
| FR-051 (막힌 조합은 계산되지 않음) | research R6-11 |
| FR-052 (같은 통화는 환전 없음) | 005 FR-023 유지, quickstart 20 |
| FR-053, SC-018 (원금 쉼표 — 표시에만, 반복 2026-10-03) | research R6-20, `frontend/src/lib/principalFormat.ts`, `SimulationForm.tsx`, ui-wireframes W3, tasks T111·T115, quickstart 24 |
| FR-060, SC-014 (비밀은 설정) | data-model 7절, research R6-1 토큰 메모리, R6-14 정적 검사, quickstart 21 |
| FR-061 (인증 응답 보관 안 함, 원본 보존) | research R6-1·R6-13, data-model 4·4a절 "헤더를 담지 않는다"·"지우지 않는다", quickstart 21 |
| FR-062 (인증 실패는 갱신만 실패) | research R6-3, data-model 2절 `auth_blocked`, quickstart 9 |
| FR-063 (한도·재시도 설정) | data-model 7절 |
| FR-064 (이용 조건 확인) | research R6-15, Complexity Tracking |
| FR-065 (목록 갱신 사건 기록) | research R6-14, `api/services/listing_refresh.py` `_event`, `tests/integration/test_listing_events.py`(tasks T101 — 구현 뒤 보강) |
| FR-070 (기록 갱신) | research R6-16, quickstart 22 |
| SC-001 (0.5초) | research R6-5 성능·입력 대기 150ms, quickstart 3 |

## Complexity Tracking

| 위반·위험 | 왜 필요한가 | 더 단순한 대안을 기각한 이유 |
|-----------|-------------|------------------------------|
| **원칙 II — 키움 이용약관** | 국내·미국 한글·초성 검색에는 한글 종목명을 주는 목록이 필요하고, 사용자가 키움을 지정했다 | 약관 페이지가 로그인 뒤에 있어 설계 중에는 읽지 못했다. **사용자가 확인했다(2026-10-02).** 공식 고객용 API의 조회 기능을 개인 용도로 쓰며 목록을 재배포하지 않는다 — 저장소도 비공개다(사용자 확인 2026-10-02). 도구를 공개하거나 여럿에게 제공하면 다시 따진다(005의 Yahoo 판단과 같은 전제) |
| **메모리 색인** — DB가 원본인데 사본을 프로세스에 둔다 | 초성·혼용 일치는 SQL `LIKE` 하나로 표현할 수 없고, DB 고유 문법은 이식성 규약에 걸린다(R6-5) | 매 검색마다 전 목록을 DB에서 읽는 방법은 SC-001(0.5초)을 위협한다. 색인은 단위별 기준 시각을 버전으로 들고 검색마다 확인하므로 **DB와 어긋난 채 머물지 않는다** |
| **005·003 결함 수정이 이 기능에 섞인다** — 종목 등록(FR-030b), 시작 가능 날짜 판정(FR-005a), 그리고 T090에서 찾은 다섯: 주식 워커가 출처를 열지 않음(T096), 상장 전 구간의 HTTP 400(T097), 테스트가 운영 수집 로그에 씀(T098), 분할 비율 실수(T103), 출처 시세가 분할을 소급 반영해 분할이 두 번 들어감(T104~T108, FR-034 — 005 research R5-3의 전제 오류, 사용자 결정 2026-10-03 A안). 그 뒤 브라우저 사용에서 둘 더: 프론트엔드 프록시가 `/api/stocks`를 넘기지 않아 주식 화면 전체가 404(T109·T110, 버그 `stock-search-not-found`), 프록시가 SSE를 gzip으로 압축해 진행이 브라우저에 도착하지 않음(T113·T117·T119, FR-045a — 003의 외환 스트림부터 있던 결함) | 006의 검색이 고른 종목을 시뮬레이션까지 잇지 못하면 이 기능 전체가 무의미하다. 기본 시작일 2020-01-01이 휴일이라 005의 판정으로는 매번 거절된다. T096·T097·T103은 실제 출처로 돌리면 시세 수집이 매번 실패하는 결함이라 SC-007a를 막는다. 결함 5는 실패 대신 **조용히 틀린 수익률**을 내므로 더 미룰 수 없다 | 005로 돌아가 따로 고치면 006이 그 수정을 기다려야 하고, 같은 파일을 두 브랜치가 고친다. 결함과 근거는 research R6-17·R6-8·R6-18, tasks T096~T098·T102~T110, quickstart 실행 기록, `.specify/bugs/stock-search-not-found/`에 따로 적어 추적할 수 있게 했다 |
| **001의 `ensure_background_job`을 006에서 고친다** — 외환 화면의 동작이 바뀐다 | 외환 화면이 남긴 고아 점유가 006의 환율 수집을 막는다(FR-046a, analyze H2) | 006이 감지만 하고 안내하는 방법은 외환 화면의 결함을 남긴다 — 지금은 외환 화면의 자동 수집이 실제로 돌지 않는다. 고치면 그것도 함께 돈다. 바뀌는 것은 "작업과 점유를 누가 만드는가"와 외환 202 본문(`jobId`가 `null`일 수 있음, `state`·`busyWith` 추가)이다. 외환 화면의 프론트엔드는 두 필드를 읽지 않아 화면은 그대로다. 기존 외환 테스트가 옛 동작을 단정하면 함께 고친다(tasks T091, analyze N1) |
| **원칙 III — 구현 뒤 실패한 테스트를 멈추고 먼저 보고하지 않았다**(진행 과정의 위반, analyze D2. **사용자 확인 2026-10-03**) | **경위**: 구현 뒤 실패한 테스트를 같은 흐름에서 고치고 커밋 메시지와 완료 보고에 사후로 적었다 — Phase 4 `test_fx_background_job` 3건(하루치만 보는 경로라 202가 나지 않음 — 테스트 전제 오류), Phase 5 `startDate` 1행(어제 경계 밖의 기대값 — 테스트 데이터 오류), Phase 6 `test_stock_search_local` 3건(국내 단위만 있다는 Phase 3의 전제 — 이전에 통과하던 테스트), T090 `test_logging_config` 2건(운영 로그 경로를 전제). 모두 구현이 아니라 테스트 쪽이 틀렸다 | **재발 방지**: 구현 뒤 테스트가 실패하면 원인이 테스트 쪽으로 확실해 보여도 **멈추고 실패 목록과 원인 판단을 먼저 보고**한 뒤 진행한다. 이전에 통과하던 테스트가 실패로 바뀐 경우도 같다(헌법 원칙 III) |
| **원칙 III — 실패하는 테스트 없이 구현한 태스크가 있다**(진행 과정의 위반, analyze D1·C1) | **경위**: T036(목록 갱신 워커를 만들고 `lifespan`에 등록)은 그것을 덮는 테스트 태스크가 목록에 없었다 — 판정·교체 테스트가 모두 `refresh_unit`을 직접 불러, 워커 등록이 빠져도 통과한다. 구현 뒤 T094로 보강했다. FR-065(목록 갱신 사건 기록)도 구현(`listing_refresh._event`)이 먼저 있었고 T101로 보강했다. 두 보강 테스트는 처음부터 통과해 "먼저 실패함"의 기록이 없다 | **재발 방지**: "실행 주체"(워커 등록·`lifespan`·스케줄러·사건 기록처럼 다른 경로가 대신 불러 주지 않는 것)를 만드는 태스크에는, **그 주체를 거쳐야만 통과하는** 테스트 태스크를 짝지어 둔다. 내부 함수를 직접 부르는 테스트는 주체가 빠져도 통과한다 — 003·005가 겪은 "실행되지 않는 수집"과 같은 유형이다 |
