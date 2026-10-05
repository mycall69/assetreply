# Implementation Plan: 성과 추이 차트의 가격 선·차트 위 값 표시와 최근 시뮬레이션 배치

**Branch**: `010-chart-price-overlay-history-layout` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-chart-price-overlay-history-layout/spec.md`

## Summary

주식·가상자산·예금·부동산 네 화면의 성과 추이 차트에 **그 자산의 가격 선**을 더한다. 가격 선은 눈금 없이 자기 비율로 그린다. 주식은 원주가 시가(분할 표식 — 반복 1에서 분할만 반영한 수정 종가로 바꾸고 표식을 없앴다),
가상자산은 시가, 예금은 그 달 발표 금리, 부동산은 그 달 실거래가 평균이다.
- 마우스를 올린 날(달)의 값은 **커서 가까이 상자**로 보이고, 차트 아래 한 줄은 없앤다.
- 최근 시뮬레이션은 창이 넓으면 **성과 표 오른쪽**(sticky)에, 좁으면 지금처럼 아래에 둔다.
- 주식 이력에 **다시 실행**을 더한다.

새 출처·새 수집·새 테이블·계산 변경은 없다. 가격은 네 시계열 조립 함수가 받는 계산 결과 안에 이미 있다(research R10-1). 시계열 응답에 키를 더할 뿐이다.

**설계 중 확인한 것**:

| 확인 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 가격의 자리 | 주식 `Row.open_price`(원주가)·가상자산 `row.open_price`·부동산 `month_average`는 결과에 있다. 예금 월별 금리는 `prepare`가 읽고 버린다 | 예금만 `Prepared`로 금리를 넘긴다(R10-5) |
| 다운샘플 | 네 함수 모두 날짜를 골라 점을 통째로 가져온다 | 바꾸지 않는다 — 가격이 점의 필드로 따라간다(R10-3) |
| 기존 `gaps` 정확 비교 | 부동산 2곳·예금·가상자산 `gaps == []` | 가격 결측은 `gaps`가 아니라 점의 `priceMissing`(R10-2) |
| 주식 분할 | 표에 분할 표시가 **없다**. 효력일은 대개 점의 날짜가 아니다 | 표식은 효력일 뒤 첫 점, 화면이 정한다. spec FR-008을 고쳤다(R10-4) |
| 예금 결측 달 | 만기 사이 달의 결측은 계산을 멈추지 않는다 | `priceMissing: "missing"` — spec FR-003·FR-011·SC-002·Edge Cases에 더했다(R10-5) |
| 부동산 상자 | 차트의 선은 평가액인데 상자 목록(FR-009)에 평가액이 없었다 | 상자에 평가액을 더하고 점에 `profit`을 싣는다. spec FR-009·US2를 고쳤다(R10-6) |
| 결측 날의 자리 | 점이 없는 날(출처 결측·시세 없음)은 시간 축에 자리가 없어 상자가 뜰 곳이 없다 | 구간마다 값 없는 자리(whitespace) 하나를 둔다 — 날마다 두면 줄인 차트에서 구간이 과장된다(R10-8, 분석 단계) |
| 주식 점의 밀도 (분석 단계) | 주식 시계열의 점은 표의 행 날짜(달 첫 거래일·배당락·재투자)뿐 — 1년 12~16점 | 주가 선도 같은 점이다(일별 아님). spec FR-001·Assumptions에 밝혔다(사용자 결정) |
| 주식 등록 경로 (분석 단계) | `POST /api/stocks/selection`은 목록 id나 일본 외부 결과만 받는다. 이력 항목에는 목록 id가 없다 | 다시 실행은 등록 요청 없이 입력을 바꿔 `run()`(R10-11) |
| lightweight-charts 5.2.1 | `priceScaleId`가 left·right 밖이면 눈금 없는 겹침 축. 터치는 기본 추적 모드 | 모의 객체에 없는 API(`createSeriesMarkers`·`subscribeClick`·`priceScale()`)를 부르지 않는다(R10-7·R10-9) |
| 표 고유 폭(1440·1920px 창) | 주식 1,071 · 가상자산 842 · 예금 659 · 부동산 836px. 본문 = 창 − 306px | 경계 폭 = 표 폭 + 726px(이력 400 + 간격 20 포함) → 모두 1920px 이하. 상수 없이 줄바꿈 flex(R10-10) |
| 출처 수정 종가 (반복 1) | `stock_price.close_adjusted`는 Yahoo `adjclose` 그대로 — 배당까지 소급하고 받은 시점마다 기준이 다르다(`models.py` 주석) | 쓰지 않는다. 분할만 반영한 수정 종가를 `close_raw`·`stock_split`에서 계산(R10-13) |
| 외환 정렬 (반복 1) | 외환 화면만 본문이 `mx-auto max-w-5xl` — 넓은 창에서 가운데에 뜬다 | 가운데 정렬을 없앤다(R10-17) |
| 외환 통화 전환 (반복 1 — 구현 중 실측) | 통화를 바꾸면 표·차트가 "불러오는 중"으로 바뀌어 문서가 2,186 → 900px로 줄고 스크롤이 0이 된다. 개발 모드에서는 StrictMode가 `DailyTable`의 첫 렌더 장치를 무력화해 다시 붙은 표가 창을 표로 옮긴다(912px) | 바꾸기 직전 높이를 붙잡고, `DailyTable`은 `resetKey` 변화로만 처음으로 돌린다(R10-16). 004 테스트 변경 없음 |

**반복 1(2026-10-05)**: 주식 주가 선을 **분할만 반영한 수정 종가**로 바꾸고 분할 표식을 없앤다(표의 시작가는 그대로). 주식·가상자산·부동산 이름에서
네이버 증권·네이버 부동산(검색)을 새 탭으로 연다 — 외부를 부르지 않는다. 외환 화면을 왼쪽에 붙이고 통화를 바꿔도 스크롤 위치를 그대로 둔다. 사용자
결정 넷은 spec Clarifications(반복 1)에 있다.

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async — 새 의존 없음 |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 차트 | lightweight-charts 5.2.1 — 겹침 가격 축(`priceScaleId: "price"`), 값 없는 자리(whitespace), `subscribeCrosshairMove`의 `time`·`point`. 새 의존 없음 |
| 상태 관리 | Zustand (헌법 원칙 VII) — `stockStore.rerunHistory` |
| DB | 변경 없음(마이그레이션 없음) |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library. 차트는 파일마다 인라인 모의 객체(새 테스트 파일이 자기 모의 객체를 둔다) |
| 타입·린트 | mypy strict, ruff(`--no-cache`) / tsc(테스트 포함), eslint |
| 출처 | 새 출처 없음 |
| 계산 | 변경 없음(FR-021) — 시계열 조립이 결과의 값을 옮겨 담는다 |
| 성능 목표 | 상자는 커서 이동 뒤 0.2초 안(SC-003). 시계열 응답 크기는 점마다 키 1~3개가 늘 뿐이다(최대 점 수 그대로) |
| 제약 | 백엔드 단일 워커, 테스트는 네트워크 없이(헌법 원칙 III). 이력 저장 형식 불변(FR-021). 외환 화면·이력 비교 차트 불변 |
| 규모 | 시계열 4경로, 공유 차트 1, 공유 배치 부품 1(신규), 화면 4, 주식 스토어·이력 부품 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 새 I/O가 없다. 예금 금리는 `prepare`가 이미 비동기로 읽은 값을 넘긴다. 주식 분할도 `run_simulation`이 이미 읽은 값 |
| II. 데이터 소스 격리 | ✅ | 출처를 건드리지 않는다. 응답의 `priceKind`·`priceMissing`은 도메인 용어다(출처 필드명이 아니다). 반복 1의 외부 링크(네이버 증권·부동산)는 **데이터를 받지 않는다** — 이 앱이 네이버를 부르지 않고, 사용자가 새 탭에서 연다. 공개되지 않은 단지 API를 쓰지 않는다(사용자 결정) — 이탈 없음 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 시계열 4경로의 계약·통합 테스트(표와 가격 대조, 다운샘플, 사유), 순수 함수 단위 테스트(`priceSegments`·`splitMarks`(반복 1에서 제거)·`gapSlots`·`hoverView`·`placeHover`), 차트·배치·다시 실행 화면 테스트를 먼저 커밋하고 최초 실패를 확인한다. 구현 뒤 기존 테스트가 실패하면 멈추고 보고(006 D2). 실행 주체(다시 실행 버튼 → 스토어 → `run()`)는 버튼을 눌러야만 통과하는 테스트와 짝짓는다(006 D1) |
| IV. 모듈화 | ✅ | 계산 계층(`simulation/`)은 바뀌지 않는다. 시계열 조립은 계산 결과를 옮길 뿐이다. 화면 쪽 규칙은 순수 함수(`lib/chartSeries.ts`·`lib/chartHover.ts`)로 두어 DOM 없이 검사한다 |
| V. 정합성·재현성 | ✅ | 가격 결측을 지어내지 않는다 — 점이 없거나 `null` + 사유(`unpublished`·`missing`·`no_trades`). 직전 값 복사·앞뒤 잇기 없음(FR-003). 예금 잠정 달에 대신 쓴 금리를 그 달 금리로 내지 않는다. 결측 구간마다 시간 축에 자리 하나를 남겨 커서로 사유를 보인다(R10-8). 부동산 추정 표식은 평가액에만. 반복 1의 수정 종가는 **명시 규칙**(원주가 종가 ÷ 그 뒤 분할 비율)으로 계산하고 저장하지 않는다 — 원본은 원주가·분할 기록이고, 출처의 배당 소급 수정가(받은 시점마다 기준이 다름)는 쓰지 않는다. 상자가 "수정 종가"로 표의 원주가와 다른 값임을 밝힌다 |
| VI. 금융 정확성 | ✅ | 가격은 문자열이고 서식은 표와 같은 함수다(rest-api). 화면은 원본 문자열을 보이고 그리기용 숫자는 선에만 쓴다(지금 규칙) |
| VII. UI·진행 | ✅ | Zustand, Lightweight Charts. 다시 실행의 수집 진행은 기존 SSE 경로 그대로 |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | 새 자산군이 아니다 — 기존 네 자산군 화면의 개선. 외환은 시뮬레이션이 없어 범위 밖 |
| DB 운영 규약 | ✅ | DB 변경 없음 |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 설계 중 바뀐 요구(FR-008 표식 자리, FR-003·FR-011·SC-002 예금 결측 달, FR-009 부동산 평가액)를 spec에 같은 작업 단위로 반영했다. 모든 FR·SC는 아래 추적성 표의 설계와 태스크에 연결된다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 표와 차트의 어긋남 | ✅ | 가격을 같은 계산 결과에서 꺼낸다(R10-1). 예금은 계산에 넘긴 바로 그 `rates`를 넘긴다 — 시계열 경로에서 다시 읽지 않는다 |
| 조용히 빠지는 전달 | ✅ | 예금 `build_series`의 금리 인자는 필수(빠뜨리면 타입 오류). `SimulationHistory.onRerun`은 필수 속성(빠뜨리면 타입 오류 — 지금 결함의 모양을 막는다) |
| 공유 부품 변경 | ✅(기록) | `PerformanceChart`는 점에 `price` 키가 있을 때만 가격·분할·자리 시리즈를 만든다 — 005~009의 차트 테스트(가격 없는 응답)는 바꾸지 않고 통과해야 한다. 차트 아래 한 줄 표시는 없앤다(참조하는 테스트 없음) |
| 배치의 경계 | ✅ | 상수 없음 — 표 고유 폭으로 줄바꿈. 측정 경계 모두 1920px 이하. 표의 열을 줄이지 않으므로 1440px 기준(006 FR-069·007 FR-041·008 FR-034·009 FR-028·SC-010)을 구조적으로 지킨다 |
| 라이브러리 모의 객체 | ✅ | 기존 모의 객체가 지원하는 API(`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale`·`remove`)와 `createChart` 옵션만 쓴다. 라이브러리 열거형을 실행 중에 읽지 않는다 |
| 바뀌는 기존 테스트 | ✅(승인 — T029) | `SimulationHistoryList.test.tsx`·`SimulationHistoryBlocked.test.tsx`의 렌더 10곳에 `onRerun` 속성만 더한다(검사 내용 그대로 — R10-12). 구현 단계에서 사용자 승인을 받는다(006 D2) |
| 바뀌는 기존 테스트 (반복 1) | ✅(없음 — 실측) | 통화 전환은 `tableEpoch`를 올리지 않아 004 `fxWorkspaceScroll`·`PeriodSwitch`는 그대로다(R10-16). 외환 화면 배치를 검사하는 기존 테스트는 없다. 010 자체 테스트(`test_stock_series_price*`·`PerformanceChartPrice`·`chartSeriesPrice`·`chartHover`·`PerformanceChartHover`)는 이 기능 안의 반복 변경이다(T042·T043) |

## Project Structure

### Documentation (this feature)

```text
specs/010-chart-price-overlay-history-layout/
├── spec.md              # /speckit-specify, /speckit-clarify (+ plan 설계 중 고친 요구 3건)
├── plan.md              # 이 파일
├── research.md          # R10-1 ~ R10-12
├── data-model.md        # DB 변경 없음 — 결과·점·응답 형식, 화면 파생 값, 배치
├── quickstart.md        # 검증 시나리오 10개 + 품질 게이트
├── contracts/
│   ├── rest-api.md      # 시계열 4경로에 더하는 키
│   └── ui-wireframes.md # F1~F4
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks — 39개, Phase 1~7 + 반복 1 T040~T054(Phase 8)
```

### Source Code (repository root)

```text
backend/
├── src/api/services/
│   ├── stock_simulation.py     # SimulationResult.splits (기본값 ()), closes — 원주가 종가(반복 1)
│   ├── stock_series.py         # SeriesPoint.price — 반복 1: 분할만 반영한 수정 종가(StockSeries.splits는 응답에서 뺌)
│   ├── crypto_series.py        # SeriesPoint.price
│   ├── deposit_simulation.py   # Prepared.rates·latest_month
│   ├── deposit_series.py       # SeriesPoint.price·price_missing, build_series(…, rates, latest_month) 필수 인자
│   └── realestate_series.py    # SeriesPoint.price·price_missing·profit
├── src/api/routes/
│   ├── stock_series.py         # priceKind(반복 1: stock_adjusted_close)·priceCurrency, 점 price — splits 키 제거
│   ├── crypto_series.py        # priceKind·priceCurrency, 점 price
│   ├── deposit_series.py       # priceKind·priceCurrency(null), 점 price·priceMissing
│   └── realestate_series.py    # priceKind·priceCurrency, 점 price·priceMissing·profit
└── tests/
    ├── unit/                   # 새 파일 — 조립 함수의 가격·분할·사유·다운샘플
    └── integration/            # 새 파일 — 네 경로의 표 대조(SC-001)·사유·다운샘플

frontend/
├── src/lib/
│   ├── types.ts                # 선택 키: price·priceMissing·profit, priceKind·priceCurrency (반복 1: splits·SplitMark 제거)
│   ├── chartSeries.ts          # priceSegments·gapSlots (반복 1: splitMarks 제거)
│   ├── chartHover.ts           # (신규) hoverView·placeHover (반복 1: 주식 줄 "주가(수정 종가)", notes 제거)
│   ├── externalLinks.ts        # (반복 1 신규) 네이버 증권·코인·부동산 검색 URL 만들기
│   └── format.ts               # formatAnnualRate를 예금 표 부품에서 옮긴다(차트가 쓴다 — 부품 간 역참조를 피한다)
├── src/components/
│   ├── TableWithHistory.tsx    # (신규) 줄바꿈 flex + sticky 이력 칸
│   ├── stock/PerformanceChart.tsx   # 가격 선·값 없는 자리·커서 상자·범례, 아래 한 줄 제거 (반복 1: 분할 표식 제거)
│   ├── stock/StockSearch.tsx · crypto/CoinSearch.tsx · realestate/RealEstateBoard.tsx  # (반복 1) 고른 이름·단지 이름을 외부 링크로
│   ├── stock/SimulationHistory.tsx  # onRerun(필수)·다시 실행 버튼, 행 줄바꿈 (반복 1: 이름 링크)
│   ├── crypto/CryptoHistory.tsx · deposit/DepositHistory.tsx · realestate/RealEstateHistory.tsx  # 행 줄바꿈 (반복 1: 가상자산·부동산 이름 링크)
│   ├── fx/DailyTable.tsx       # (반복 1) 통화 전환에서 창 스크롤 없음 — 또는 외환 스토어의 resetKey(R10-16)
│   └── deposit/DepositPerformanceTable.tsx · deposit/DepositNotice.tsx  # formatAnnualRate 가져오는 곳만
├── src/stores/stockStore.ts    # rerunHistory
├── src/app/{stocks,crypto,deposit,realestate}/page.tsx  # TableWithHistory로 감싼다, 주식 onRerun
├── src/app/fx/page.tsx         # (반복 1) 가운데 정렬(mx-auto) 제거
└── tests/                      # 새 파일 — 가격 선·상자·배치·다시 실행·순수 함수
                                # 바뀌는 기존 파일 — SimulationHistoryList·SimulationHistoryBlocked(onRerun 속성만, 승인 필요)

CLAUDE.md · README.md           # 현재 상태 표에 010 (반복 1 내용 더함)
```

**Structure Decision**: 기존 웹 앱 구조(backend/frontend) 그대로다. 차트·배치 규칙을 공유 부품 하나씩(`PerformanceChart`, `TableWithHistory`)에 두어 네
화면이 같은 규칙을 쓴다 — 한 화면만 다르게 고쳐지는 일을 막는다(007 R7-14와 같은 이유).

## 측정한 경계 폭

설계 때 잰 값(research R10-10)이다. 구현 뒤 quickstart 8이 다시 재서 이 표의 "구현 뒤" 열을 채운다.

2026-10-05 T036 실측: 네 경계 모두 1920px 이하(SC-004). 경계는 설계 계산보다 20~80px 좁다 — 실제 본문 여백·간격이 계산(창 − 306px, 간격 20px)과 조금 다르다. 상수가 아니므로 표 열이 바뀌면 경계도 따라간다.

| 화면 | 가장 넓은 표(조건) | 표 고유 폭 | 경계 폭(설계 계산) | 경계 폭(구현 뒤 실측) |
|------|---------------------|-----------:|-------------------:|----------------------:|
| 주식 | AAPL · 원화 원금 | 1,071px | 약 1,800px | **1,770px** |
| 가상자산 | BTC · 원화 원금 | 842px | 약 1,570px | **1,490px**(이 실행의 표 794px — 시작일이 달라 열 폭이 좁다) |
| 예금 | 시중은행 | 659px | ≤ 1,440px(약 1,390px) | **1,340px** |
| 부동산 | 헬리오시티 30평대 | 836px | 약 1,560px | **1,540px** |

## 요구사항 추적성

설계 산출물·태스크와의 대응이다. 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md — 참조하는 태스크가 없는 FR·SC가 남으면 헌법 명세 작성 규약 위반).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (가격 정의·통화) | R10-1, R10-4~R10-6, rest-api 네 경로(`priceKind`·`priceCurrency`·`price`), data-model 2절, tasks T003·T004·T005·T006·T007·T008·T009·T010·T012·T013·T014·T015·T016·T017, 반복 1 — R10-13(수정 종가), tasks T041·T042·T047·T051 |
| FR-002 (표와 같은 값) | R10-1(같은 계산 결과), R10-5(예금 — 같은 `rates`), rest-api "계약 테스트가 확인하는 것", quickstart 1~4, tasks T005·T007·T008·T009·T010·T013·T014·T015·T016, 반복 1 — 주식은 R10-13 규칙 값, tasks T041·T042·T047 |
| FR-003 (지어내지 않음·끊음·잇기) | R10-2(`priceMissing`), R10-7(`priceSegments`), data-model 2·4절, F1, quickstart 2~4, tasks T005·T006·T008·T009·T010·T011·T012·T015·T016·T017 |
| FR-004 (눈금 없음) | R10-7(겹침 축), F1, tasks T012·T017 |
| FR-005 (범례 이름·단위) | R10-7, F1 범례 표, tasks T012·T017 |
| FR-006 (잠정 색·추정 표식은 평가액만) | R10-6, R10-7, F1, tasks T006·T010·T012·T016·T017 |
| FR-007 (다운샘플 같은 날) | R10-3, rest-api 공통 규칙, quickstart 5, tasks T004·T005·T006·T007·T008·T013·T018 |
| FR-008 (분할 표식 — 반복 1에서 없앰) | R10-4(`splits`·`splitMarks`), rest-api 주식, F1·F2, quickstart 1, tasks T004·T007·T011·T012·T013·T017, 반복 1 — 분할 표식 없앰(spec FR-008), tasks T043·T048 |
| FR-009 (상자 내용·형식) | R10-6(`profit`), R10-9, data-model 4절 상자 표, F2, tasks T019·T020·T021·T022·T023·T024, 반복 1 — 주식 "주가(수정 종가)"·notes 제거, tasks T043·T048 |
| FR-010 (커서 아래 점·표와 같음) | R10-9(`lookup`·원본 문자열), quickstart 6, tasks T020·T021·T024 |
| FR-011 ("—"와 사유) | R10-2, R10-5, R10-6, R10-8(값 없는 자리), F2 사유 표, tasks T006·T009·T015·T020·T021·T024 |
| FR-012 (잘리지 않음·사라짐) | R10-9(`placeHover`), quickstart 6, tasks T020·T021·T024·T025 |
| FR-013 (아래 한 줄 제거) | R10-9, F2, tasks T021·T024 |
| FR-014 (터치 — 길게 누름) | R10-9(기본 추적 모드), F2, quickstart 7, tasks T021·T024·T025 |
| FR-015 (나란히·아래·경계 측정) | R10-10, data-model 6절, F3, 이 문서 "측정한 경계 폭", quickstart 8, tasks T032·T033·T034·T035·T036 |
| FR-016 (sticky·안쪽 스크롤) | R10-10, F3, quickstart 8, tasks T032·T034·T035 |
| FR-017 (비교 차트 전체 폭·동작 그대로) | R10-10, F3, tasks T032·T033·T035 |
| FR-018 (주식 다시 실행) | R10-11(등록 요청 없음), F4, `stockStore.rerunHistory`, quickstart 9, tasks T026·T027·T028·T030 |
| FR-019 (막힌 조합 거절) | R10-11, F4, quickstart 9, tasks T026·T027·T030 |
| FR-020 (수집·진행 같음) | R10-11(직접 실행과 같은 `run()` — 모르는 종목은 서버 사유), quickstart 9, tasks T026·T028·T030 |
| FR-022·FR-023 (외환 정렬·통화 전환 스크롤 — 반복 1) | R10-16·R10-17, F6, quickstart 13, tasks T046·T050·T051 |
| FR-024 (주식 외부 링크 — 반복 1) | R10-14, data-model 7절, F5, quickstart 12, tasks T040·T044·T045·T049·T051 |
| FR-025 (코인 외부 링크 — 반복 1) | R10-14, data-model 7절, F5, quickstart 12, tasks T040·T044·T045·T049·T051 |
| FR-026 (부동산 검색 링크 — 반복 1) | R10-15, data-model 7절, F5, quickstart 12, tasks T040·T044·T045·T049·T051 |
| FR-021 (계산·이력 형식 불변) | R10-1, data-model 5절, quickstart 10, tasks T001·T037·T039, 반복 1 — tasks T054 |
| SC-001 | 네 경로 통합 테스트(표 대조), quickstart 1~4, tasks T007·T008·T009·T010·T018, 반복 1 — tasks T042·T051 |
| SC-002 | 사유 테스트(예금 `unpublished`·`missing`, 부동산 `no_trades`), `priceSegments` 단위 테스트, quickstart 2~4, tasks T005·T008·T009·T010·T011·T018 |
| SC-003 | `hoverView` 단위·차트 화면 테스트, quickstart 6, tasks T019·T020·T021·T025 |
| SC-004 | `TableWithHistory` 화면 테스트(구조), quickstart 8(실측), tasks T032·T036 |
| SC-005 | 다시 실행 스토어·화면 테스트, quickstart 9, tasks T026·T031 |
| SC-006 | 기존 자동 검사 전체(바뀌는 것은 R10-12의 둘뿐), quickstart 10, tasks T001·T002·T038·T039, 반복 1 — tasks T053·T054 |
| SC-007 (반복 1) | 링크 단위·화면 테스트, quickstart 12, tasks T044·T045·T051 |
| SC-008 (반복 1) | 외환 화면 테스트, quickstart 13, tasks T046·T051 |
## Complexity Tracking

헌법 이탈이 없다. 기록할 만한 설계 선택은 두 가지이고, 둘 다 원칙을 지키는 쪽이다.
- **값 없는 자리(R10-8)** — 결측 구간마다 시간 축에 자리가 하나 생긴다. 차트 모양이 바뀌는 유일한 곳이다.
- **공유 차트의 조건부 시리즈(R10-7)** — 가격 시리즈는 점에 `price` 키가 있을 때만 만든다. 그래서 가격 없는 기존 응답은 지금과 같이 그린다.
