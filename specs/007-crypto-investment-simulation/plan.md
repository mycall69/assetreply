# Implementation Plan: 가상자산 투자 시뮬레이션

**Branch**: `007-crypto-investment-simulation` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-crypto-investment-simulation/spec.md`

## Summary

사이드바의 "가상자산"을 실제 메뉴로 만든다. 코인 하나를 고르고 시작일·원금을 넣으면, 시작 월의 첫 일봉 시가로 한 번 사서 들고 있었을 때의
성과를 보드·표·차트·이력 비교로 보인다. 화면과 규칙은 주식(005·006)을 따르고, 배당 관련 기능이 없고, 수량이 소수(8자리 버림)다.

**출처는 investing.com이다**(사용자 결정 2026-10-03). 설계 중 실측한 결과(research R7-1~R7-5):

| 실측 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 자동 접근 | curl은 403. **aiohttp + 브라우저형 사용자 에이전트**면 200(일봉은 `domain-id` 헤더도 필요). 로그인 불필요 | 브라우저 없이 aiohttp 어댑터. 헤더는 설정 |
| 약관 | 허가 없는 데이터 저장·사용 금지 | 사용자 결정대로 원칙 II 이탈 기록(Complexity Tracking) |
| 일봉 | 내부 API가 JSON으로 준다. **UTC 하루**(시간봉으로 확인), 원값 소수 14자리, 한 번에 약 5,000행, **오늘 일봉도 온다** | 원값 그대로 `Decimal`, 730일 청크, UTC 어제까지만 저장 |
| 코인 목록 | 내부 API, 100개씩 커서, **3,654개**. `instrument_id`가 유일한 식별자, **심볼 169개 중복** | (출처, `instrument_id`)로 식별, 검색 동순위는 시가총액 순위 |
| 한글 이름 | 한국어 판이 같은 식별자로 짝지어지지만 **한글 이름은 12개**(상위 50개 중 8개) | 명세대로 진행 — 사용자 결정 2026-10-03(R7-5) |

주식 경로를 다섯 곳 건드린다 — KRW 평가식을 공용 순수 함수로(R7-8), `fx_currency_for`를 통화 단위로, 결측 사유 매개변수(R7-9), 검색
동순위의 `priority`(R7-6), **환율 조회를 확정 환율만으로**(R7-8, analyze C1 — 005·006부터의 빈틈). 앞의 넷은 주식의 동작을 바꾸지 않고,
다섯째는 "날짜가 지났는데 아직 잠정인 환율"이 계산 구간에 있을 때만 주식 결과를 바꾼다. 006의 테스트가 회귀를 지킨다.

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — **신규 테이블 11개**(data-model), Alembic 마이그레이션 하나. 기존 테이블 변경 없음 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library. 출처는 **실제 응답 픽스처**로 계약 테스트 |
| 타입·린트 | mypy strict, ruff / tsc, eslint |
| 출처 | **investing.com 내부 API**(목록·일봉) — aiohttp, 브라우저형 사용자 에이전트, 로그인 없음. 원칙 II 이탈(잠정) |
| 시세 통화 | USD 고정(R7-4). 원금 통화 KRW·USD |
| 수집 실행 | 앱 수명 태스크 2개 추가 — 가상자산 수집 줄, 목록 갱신 줄. 같은 출처 클라이언트의 간격 제한기를 공유 (R7-11) |
| 검색 | 006의 메모리 색인(`src/search/`) + 시가총액 `priority` (R7-6) |
| 성능 목표 | 받은 구간이면 결과 3초 안(SC-001). 수집 진행 2초 안(SC-003) |
| 규모 | 코인 3,654개(목록 74요청/주). BTC 일봉 약 5,900행(2010-07-18~), 730일 청크 9개 |
| 제약 | 백엔드 단일 워커(CLAUDE.md), 테스트는 네트워크 없이(헌법 원칙 III), 출처 요청 사이 최소 1.5초 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 출처 호출은 aiohttp. 수집·목록 갱신은 워커 태스크라 요청이 기다리지 않는다. 검색 색인은 메모리 |
| II. 데이터 소스 격리 | ⚠️ 이탈(기록) | 어댑터를 `ingestion/investing/`에 격리, 세마포어·최소 간격·지수 백오프+지터, 사용자 에이전트·간격·재시도는 설정. 비밀 없음(로그인 불필요). **약관이 허가 없는 저장·사용을 금지한다** — 사용자 결정(2026-10-03)으로 개인 이용 전제의 이탈을 기록한다(Complexity Tracking) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행·먼저 커밋·최초 실패 확인. 구현 뒤 실패하면 멈추고 보고(006 D2). 신규 출처라 **계약 테스트가 품질 게이트**다 — 실제 응답 픽스처(R7-3·R7-4의 사례). **실행 주체**(워커 등록, 목록 갱신 요청, `lifespan`)는 그 주체를 거쳐야만 통과하는 테스트와 짝짓는다(006 D1) |
| IV. 모듈화 | ✅ | 시뮬레이션은 `simulation/crypto_hold.py` 순수 함수, KRW 평가는 `simulation/fx_convert.evaluate_krw` 순수 함수, 일치 판정은 `src/search/`. 출처 응답 형식은 `ingestion/investing/` 밖으로 나가지 않는다(Protocol) |
| V. 정합성·재현성 | ✅ | 원본(목록 쪽·일봉 청크) 분리 보관, `(coin_id, day)` upsert, `source`·`ingested_at`, 커버리지, 결측은 행 없음 + `source_missing`으로 끊음(보간 없음). **잠정 일봉은 저장하지 않는다**(UTC 어제까지). 일봉 = UTC 하루를 실측으로 확인(R7-3). 시작 가능 날짜는 상수가 아니라 수집 중 발견(R7-10). **환전·평가에는 확정 환율만**(R7-8, analyze C1). **수집 커버리지 조회**: `crypto_coverage`와 저장소 `get_coverage`, 202 본문의 빠진 구간, 검색 결과의 `firstAvailableDate` — 005 주식과 같은 방식(analyze M4) |
| VI. 금융 정확성 | ✅ | `Decimal`, DB `DECIMAL(36,14)`(가격)·`DECIMAL(38,8)`(거래량). 원값 문자열을 `float` 없이 읽는다. 수수료율은 설정(명시 파라미터). 소수 수량 버림은 손계산 참조값 테스트(R7-7) |
| VII. UI·진행 | ✅ | Zustand, SSE 진행 — 시세 수집과 **목록 갱신**(약 2분, FR-005b, analyze C2) 둘 다(006의 `no-transform`·프레임마다 rollback), Lightweight Charts, LTTB |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | FX 다음이 가상자산 — 005가 건너뛴 자리를 채운다. 수집~화면 수직 슬라이스. 적립식·매도·교차 비교는 범위 밖(YAGNI) |
| DB 운영 규약 | ✅ | ORM, 마이그레이션 하나, upsert는 기존 방언 추상화(`db/dialect.py`), 커넥션 풀 기존 |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 — 브라우저(Chrome)가 필요 없다는 것을 실측으로 확인(R7-1) |
| 명세 작성 규약 | ✅ | 아래 추적성 표. tasks가 모든 FR·SC를 참조해야 한다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 출처 응답의 누출 | ✅ | 도메인·API는 `CoinRow`·`DailyBar` 같은 우리 형식만 본다. `rowDateTimestamp`·`…Raw` 이름은 `ingestion/investing/parse.py`에만 |
| 주식 경로 변경 | ✅(기록) | 공용화 네 곳은 주식의 출력이 같고, 확정 환율 전용은 날짜가 지난 잠정 환율이 있을 때만 다르다 — 006 테스트 전체가 회귀(Complexity Tracking) |
| 잠정값 | ✅ | 잠정 일봉은 저장 전에 버리므로 확정 구간과 섞일 수 없다. 원본에는 남아 사후 추적 가능. 잠정 환율은 계산에 들어가지 않는다(R7-8) |
| 원칙 II 이탈 범위 | ✅(기록) | 이탈은 약관 하나. 나머지 원칙 II 항목(격리·제한·백오프·설정·비밀)은 지킨다 |

## Project Structure

### Documentation (this feature)

```text
specs/007-crypto-investment-simulation/
├── spec.md              # /speckit-specify, /speckit-clarify
├── plan.md              # 이 파일
├── research.md          # R7-1 ~ R7-13 (출처 실측 포함)
├── data-model.md        # 신규 테이블 11개
├── quickstart.md        # 검증 시나리오 20개
├── contracts/
│   ├── rest-api.md      # /api/crypto/* + 출처 API 계약
│   └── ui-wireframes.md # C1~C7
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (아직 없음)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── config/settings.py                # 변경 — InvestingSettings(사용자 에이전트, domain-id, 기본 URL, 간격, 재시도, 청크 730일,
│   │                                      #        목록 주기 7일, 축소 한도 50%) (FR-016, R7-1)
│   ├── ingestion/investing/              # 신규 — 출처 어댑터 (헌법 원칙 II)
│   │   ├── client.py                     #   InvestingClient: 목록 쪽(커서), 일봉 청크. 간격 제한기·백오프. 원본 함께 반환
│   │   ├── parse.py                      #   목록 → CoinRow, 일봉 → DailyBar(원값 Decimal, 빈 거래량 None, UTC 날짜) (FR-012a, R7-3)
│   │   └── errors.py                     #   InvestingBlocked(403) / InvestingFormatError / InvestingNetworkError (FR-020)
│   ├── db/models.py                      # 변경 — Crypto* 11개 (data-model)
│   ├── db/migrations/versions/…_가상자산_스키마.py  # 신규
│   ├── repository/
│   │   ├── crypto_coin.py                # 신규 — 목록 교체(upsert·missing), 갱신 기록, 점유, 원본
│   │   ├── crypto_daily.py               # 신규 — 일봉 upsert·조회, 커버리지, 첫 일봉
│   │   ├── crypto_job.py                 # 신규 — 작업·점유(005 stock_job과 같은 수단)
│   │   └── crypto_setting.py             # 신규 — 수수료율(기본 0.001)
│   ├── search/match.py                   # 변경 — SearchEntry.priority (동순위 정렬, R7-6. 주식은 0)
│   ├── simulation/
│   │   ├── crypto_hold.py                # 신규 — 매수 후 보유, 월 첫 일봉 행, 1일 결측 표시 (FR-025~FR-031, R7-7)
│   │   ├── money.py                      # 변경 — buy_fraction(소수 8자리 버림) (FR-026)
│   │   └── fx_convert.py                 # 변경 — evaluate_krw 공용 순수 함수 (R7-8)
│   ├── api/services/
│   │   ├── stock_fx.py                   # 변경 — fx_currency_for(currency), load_rates는 확정 환율만 (R7-8)
│   │   ├── stock_simulation.py           # 변경 — _evaluate가 evaluate_krw를 부른다(출력 불변)
│   │   ├── series_query.py               # 변경 — compute_gaps(…, inside_reason) (R7-9. 기본 no_quote)
│   │   ├── crypto_index.py               # 신규 — 코인 검색 색인(갱신 기록 버전)
│   │   ├── crypto_list_refresh.py        # 신규 — 주기 판정(7일), 요청, 두 판 받기·축소 검사·교체, 사건 기록 (FR-005, FR-019)
│   │   ├── crypto_collect.py             # 신규 — 202 판정(일봉 + 환율), 작업 확보 (FR-013, FR-036)
│   │   ├── crypto_simulation.py          # 신규 — 조회·환전·KRW 평가·시작 가능 날짜 (FR-007~FR-009, FR-034~FR-036)
│   │   └── crypto_series.py              # 신규 — 일봉 점, source_missing 결측 (FR-043, FR-044)
│   ├── api/routes/
│   │   ├── crypto_search.py              # 신규 — GET /api/crypto/search
│   │   ├── crypto_simulation.py          # 신규 — GET /api/crypto/simulation
│   │   ├── crypto_series.py              # 신규 — GET /api/crypto/simulation/series
│   │   ├── crypto_progress.py            # 신규 — GET /api/crypto/progress (SSE)
│   │   ├── crypto_list_progress.py       # 신규 — GET /api/crypto/list/progress (SSE, FR-005b)
│   │   └── crypto_settings.py            # 신규 — GET·PUT /api/crypto/settings
│   ├── api/main.py                       # 변경 — 라우터, lifespan 태스크 2개(가상자산 수집, 목록 갱신), 기동 시 고아 점유 회수
│   └── worker/
│       ├── crypto_queue.py               # 신규 — 시작 큐 (005 stock_queue와 같다)
│       ├── crypto_runner.py              # 신규 — 청크 수집, 원본 저장, 첫 일봉 기록 (R7-10)
│       ├── crypto_worker.py              # 신규 — 앱 수명 태스크
│       ├── crypto_list_queue.py          # 신규 — 목록 갱신 요청
│       └── crypto_list_worker.py         # 신규 — 목록 갱신 태스크
└── tests/
    ├── contract/fixtures/crypto/         # 신규 — 실제 응답 (목록 en·ko 쪽, BTC 청크, 오늘 일봉, 빈 거래량, SHIB, 일봉 없음, 403)
    ├── contract/                         # test_investing_parse.py, test_investing_client.py
    ├── unit/                             # crypto_hold, buy_fraction, evaluate_krw, 갱신 주기, 검색 priority, compute_gaps 사유
    └── integration/                      # 목록 갱신·검색, 수집·커버리지·첫 일봉, 202 게이트, 시뮬레이션·KRW, 시계열, SSE, 설정, lifespan

frontend/
├── src/
│   ├── app/crypto/page.tsx               # 신규 — 가상자산 화면 (C1)
│   ├── stores/cryptoStore.ts             # 신규 — 입력·실행·수집 대기·환율 대기·이력 (stockStore를 본뜬다)
│   ├── components/crypto/
│   │   ├── CoinSearch.tsx                # 신규 — 한글·영문·심볼·순위, 엔터·조합 중 무시, 목록 상태 (C2)
│   │   ├── CryptoSimulationForm.tsx      # 신규 — 재투자 없음, 원금 KRW·USD, 시작일 상한 UTC 어제 (C1)
│   │   └── CryptoPerformanceTable.tsx    # 신규 — 수량·결측 표시·열별 통화·내용 폭 (C4)
│   ├── components/stock/PerformanceBoard.tsx·PerformanceChart.tsx·ComparisonChart.tsx·StartDateInput.tsx·CollectingNotice.tsx
│   │                                     # 그대로 쓴다(필요하면 대상 이름을 받게) (R7-12). 반복 2026-10-04 — PerformanceBoard는
│   │                                     # 기호 앞(FR-042a, 006 FR-054 대체), PerformanceChart는 두 축 눈금 형식(FR-043a) (R7-14)
│   ├── components/settings/CryptoSettingsForm.tsx  # 신규 — 거래 수수료율 (C6)
│   ├── app/settings/page.tsx             # 변경 — 가상자산 칸 연결
│   ├── components/shell/Sidebar.tsx      # 변경 — /crypto 경로, 헌법 순서(가상자산 → 주식) (C1)
│   ├── lib/types.ts                      # 변경 — 가상자산 응답 형식
│   ├── lib/format.ts                     # 변경 — formatPrice(유효 숫자), formatQuantity(8자리) (FR-040).
│   │                                     # 반복 2026-10-04 — formatMoneyWithSymbol 기호 앞(FR-042a), formatAxisNumber(FR-043a)
│   ├── lib/chartSeries.ts                # 변경 — source_missing도 끊는다 (C5)
│   ├── lib/cryptoHistory.ts              # 신규 — 이력(주식과 다른 저장 키) (FR-045)
│   └── lib/cryptoProgressStream.ts       # 신규 — /api/crypto/progress 구독 (또는 stockProgressStream을 경로를 받게)
└── tests/                                # 각 변경에 대응. noUnbuiltAssetRoutes.test.ts에서 crypto를 뺀다
```

**Structure Decision**: 기존 웹 애플리케이션 구조(`backend/`·`frontend/`)를 그대로 쓴다. 가상자산은 주식과 **같은 층을 나란히** 둔다(파일
접두사 `crypto_`) — 자산군마다 출처·식별·정밀도가 달라 한 테이블·한 서비스로 합치지 않는다. 자산군에 무관한 것(검색 색인, KRW 평가,
환율 판정, 결측 계산, 보드·차트·비교·시작일 부품)만 공유한다.

## 요구사항 추적성

설계 산출물·태스크와의 대응이다. 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (메뉴) | C1, `Sidebar.tsx`, `app/crypto/page.tsx`, `noUnbuiltAssetRoutes.test.ts`, tasks T028·T033 |
| FR-002, FR-007 (입력·원금 통화) | rest-api 시뮬레이션 매개변수·`currency_pair_not_allowed`, `CryptoSimulationForm`, `crypto_simulation.py`, tasks T024·T032·T033·T035 |
| FR-003, FR-004, FR-006 (검색·같은 심볼·한글) | R7-4~R7-6, rest-api 검색, C2, `crypto_index.py`, `search/match.py`(`priority`), `CoinSearch`, tasks T003·T006·T014·T015·T016·T019·T020 |
| FR-005, FR-005a (목록 저장·주기·빠짐) | R7-4, data-model 1~4절, `crypto_list_refresh.py`, `crypto_list_worker.py`, tasks T013·T014·T017·T018 |
| FR-005b (목록 갱신 진행) | R7-11, data-model 3절, rest-api `/api/crypto/list/progress`, C2, `crypto_list_progress.py`, tasks T015·T016·T018·T020 |
| FR-008, FR-009 (시작 가능 날짜·계산 끝) | R7-10, rest-api `before_listing`·`start_after_end`, `crypto_runner.py`(첫 일봉), `crypto_simulation.py`, tasks T023·T024·T028·T032 |
| FR-010~FR-014 (수집·재개·원본·진행·중복) | R7-3, R7-11, data-model 5~8절, rest-api 202·SSE, `crypto_collect.py`, `crypto_runner.py`, `crypto_progress.py`, tasks T023·T024·T025·T027·T030·T031 |
| FR-012a (숫자 표기) | R7-3, `ingestion/investing/parse.py`, tasks T003·T010 |
| FR-015 (서로 막지 않음) | R7-11 — 별도 줄, tasks T027·T031 |
| FR-016, FR-017 (설정·비밀) | R7-1, `InvestingSettings`. 로그인이 없어 비밀 없음, tasks T002·T004·T008·T011 |
| FR-018 (출처·약관) | R7-1, R7-2, Complexity Tracking, tasks T001·T004·T011·T046 |
| FR-019 (수집 로그) | R7-11, `crypto_list_refresh.py`·`crypto_runner.py`의 사건, tasks T014·T018·T023·T031 |
| FR-020 (실패 사유) | R7-1, `ingestion/investing/errors.py`, rest-api SSE `failed.kind`, C7, tasks T004·T010·T011·T023·T025 |
| FR-021, FR-022 (UTC·잠정) | R7-3 — 시간봉 확인, UTC 어제까지 저장, tasks T003·T023·T024·T028 |
| FR-023, FR-043 (결측·차트) | R7-9, `series_query.compute_gaps`, `chartSeries.ts`, C5, tasks T006·T039·T040·T041·T042 |
| FR-024 (끊김) | rest-api `isFinal`, `crypto_simulation.py`, tasks T024 |
| FR-025~FR-031 (매수·수량·수수료·잔고·재현·1일 결측·정밀도) | R7-7, R7-13, `crypto_hold.py`, `money.buy_fraction`, tasks T021·T022·T024·T029 |
| FR-032, FR-033 (설정) | data-model 9절, rest-api 설정, C6, `CryptoSettingsForm`, tasks T026·T028·T030·T033 |
| FR-034~FR-036 (환전·KRW·환율 판정·확정 환율) | R7-8, `fx_convert.evaluate_krw`, `stock_fx.py`(`load_rates` 확정 전용), `crypto_collect.py`, tasks T005·T012·T024·T035·T036·T037 |
| FR-037~FR-041, FR-037a (표·열별 통화) | C4, `CryptoPerformanceTable`, `format.formatPrice`·`formatQuantity`, tasks T028·T033 |
| FR-042 (보드) | C3, `PerformanceBoard`(기호 위치만 FR-042a), tasks T028·T036 |
| FR-042a, SC-014 (보드 기호 앞 — 반복 2026-10-04) | research R7-14, `format.ts` `formatMoneyWithSymbol`, `PerformanceBoard`, C3, tasks T049·T050·T053, quickstart 21 |
| FR-043a, SC-015 (차트 축 쉼표 — 반복 2026-10-04) | research R7-14, `format.ts` `formatAxisNumber`, `PerformanceChart`(구간마다 시리즈 `priceFormat`), C5, tasks T051·T052·T053, quickstart 22 |
| FR-044 (차트 끝점) | `crypto_series.py` — 표와 같은 계산, tasks T039·T041 |
| FR-045, FR-046 (이력·비교) | `cryptoHistory.ts`, `ComparisonChart`(그대로), tasks T043·T044·T045 |
| FR-047 (기록 갱신) | README·CLAUDE.md — "가상자산은 007", tasks T046 |
| SC-001, SC-003, SC-006 | quickstart 6·8, tasks T021·T024·T025·T034·T048 |
| SC-002, SC-002a | quickstart 3·4, 검색 통합 테스트, tasks T015 |
| SC-004, SC-005 | `crypto_hold` 단위 테스트, quickstart 7·11, tasks T021·T023·T039 |
| SC-007 | quickstart 7·9·15, tasks T024·T035·T038·T039 |
| SC-008 | quickstart 14, tasks T026 |
| SC-009 | quickstart 12, `formatPrice` 테스트, tasks T028 |
| SC-010 | quickstart 16, tasks T034·T048 |
| SC-011 | 로그인 정보가 없다 — 사용자 에이전트가 로그·원본에 남지 않는지 quickstart 20, tasks T014·T034 |
| SC-012 | quickstart 18, tasks T027·T034 |
| SC-013 | 자동 검사(전체 테스트), tasks T047 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-------------|------------------------------|
| **원칙 II — investing.com 약관**(허가 없는 저장·사용 금지, research R7-2), **공개되지 않은 내부 API** 사용 | 사용자가 출처를 지정했고(spec 입력), 약관이 금지해도 **개인 이용을 전제로 그대로 쓰기로 결정했다**(spec Clarifications 2026-10-03). 005 Yahoo 비공식 엔드포인트와 같은 잠정 결정 — 데이터를 재배포하지 않고 저장소는 비공개다 | 약관을 지키는 다른 출처(거래소 공개 API 등)로 바꾸는 안은 사용자가 고르지 않았다(clarify 질문 1). 사용자가 내려받은 파일을 올리는 안은 자동 수집·진행 표시를 잃는다. **공개하거나 여러 사용자에게 제공할 계획이 생기면 출처를 다시 정한다**(CLAUDE.md에 기록) |
| **자동 접근 차단을 사용자 에이전트로 통과한다** — 브라우저형 문자열을 보낸다 | 기본 사용자 에이전트는 403이다(R7-1) | 브라우저를 실제로 띄우는 방법은 운영 기기에 Chrome을 요구한다. 차단 기준이 바뀌면 수집이 막히는 것을 정상 경로로 다룬다(FR-018 실패 양상, FR-020) |
| **006의 주식 경로를 다섯 곳 바꾼다** — `evaluate_krw` 공용화, `fx_currency_for(currency)`, `compute_gaps` 사유 매개변수, `SearchEntry.priority`, **`load_rates` 확정 환율 전용**(analyze C1) | KRW 평가·환율 판정·결측·검색 정렬은 자산군에 무관한 규칙이다. 두 벌 두면 한쪽만 고쳐질 때 이력 비교의 기준이 갈라진다(006 FR-068의 실패 양상). 환율 조회는 잠정 환율을 계산에 넣어 헌법 원칙 V를 어겼다 — 005·006부터의 빈틈이고, 같은 함수를 쓰므로 함께 고친다 | 복사해 두는 방법은 규칙이 두 곳에 생긴다. 앞의 네 곳은 **주식의 출력이 바뀌지 않게**(기본값 유지) 바꾼다. 확정 환율 전용은 주식 결과를 "날짜가 지났는데 아직 잠정인 환율이 있는 날"에만 바꾼다 — 그날의 `fxRateDate`가 앞 확정일이 된다. 006의 테스트 전체가 회귀 검사다. 테스트가 깨지면 멈추고 보고한다(원칙 III) |
