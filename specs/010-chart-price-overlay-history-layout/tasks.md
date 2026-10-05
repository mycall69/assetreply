---

description: "Task list for 010-chart-price-overlay-history-layout"
---

# Tasks: 성과 추이 차트의 가격 선·차트 위 값 표시와 최근 시뮬레이션 배치

**Input**: Design documents from `/specs/010-chart-price-overlay-history-layout/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를 지킨다. **테스트를 구현보다
먼저 커밋한다** — 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes). **구현 뒤 테스트가 실패하면 원인이 테스트 쪽으로 보여도 멈추고
실패 목록과 원인 판단을 먼저 보고한다**(이전에 통과하던 테스트가 실패로 바뀐 경우도 같다 — 006 D2).

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다. US1(가격 선)과 US2(차트 위 상자)는 둘 다 P1이고, US2는
US1의 가격 값을 상자에 보이므로 US1 뒤다. MVP는 US1까지다 — 가격 선만으로도 결과와 원인을 한 차트에서 잇는다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수). 린트는 `ruff check --no-cache`(CLAUDE.md) — 테스트를
  먼저 쓸 때 임포트는 구현 뒤 기준(전부 `src.*` 묶음)으로 정렬한다

## 이 기능에서 특히 조심할 것

- **계산을 바꾸지 않는다**(FR-021): `backend/src/simulation/`의 파일과 표(`/simulation`) 경로의 응답은 바뀌지 않는다. T001이 구현 전 응답을 남기고
  T039가 대조한다. 바뀌는 것은 시계열(`/simulation/series`) 응답에 **키를 더하는 것**뿐이다
- **가격은 표와 같은 계산 결과에서 꺼낸다**(research R10-1): 시계열 경로에서 저장소를 다시 읽지 않는다. 예금은 `prepare`가 계산에 넘긴 바로 그
  `rates`·`latest_month`를 `Prepared`로 넘긴다. 주식 분할은 `run_simulation`이 이미 읽은 `split_rows`
- **가격 결측을 `gaps`에 넣지 않는다**(R10-2): `gaps`는 잔고·수익률 선이 끊기는 자리다. 가격만 없는 점은 `price: null` + `priceMissing`. 기존
  `gaps` 정확 비교(`test_realestate_series_api` 두 곳, 예금·가상자산의 `gaps == []`)는 그대로 통과해야 한다
- **예금의 대신 쓴 금리를 그 달 금리로 내지 않는다**(R10-5): 마지막 발표 달 뒤의 달은 `unpublished`, 발표 기간 안의 빈 달은 `missing`.
  `build_series`의 `rates`·`latest_month`는 **기본값 없는 필수 키워드 인자**다 — 기본값이 있으면 경로가 넘기기를 잊어도 모든 점이 조용히 "미발표"가 된다
- **서식은 표와 같은 함수다**: 백엔드 — 주식 `str()`, 가상자산 `format(…, "f")`, 예금 `rate_text`(`repository/deposit_rate.py`), 부동산 원 정수
  `str()`. 화면 — 주식 `currencySymbol + formatRate`, 가상자산 `currencySymbol + formatPrice`, 예금 `formatAnnualRate`, 금액 `formatMoneyWithSymbol`,
  수익률 `formatPercent`(표와 같은 부호 붙은 형식). 다른 함수를 쓰면 반올림·자릿수가 갈라져 표와 상자가 조용히 어긋난다(FR-002, FR-010)
- **가격의 통화는 자산 자신의 것이다**(Clarifications): 원화 원금으로 미국 종목을 실행해도 `priceCurrency`는 `USD`, 가격은 표의 시작가(종목 통화)다.
  KRW로 환산하지 않는다
- **공유 차트는 조건부로 바꾼다**(R10-7): 가격·분할·값 없는 자리 시리즈는 점에 `price` **키가 있을 때만** 만든다. **005~009의
  `PerformanceChart*.test.tsx`·`chartSeries*.test.ts`는 고치지 않고 통과해야 한다**
- **기존 테스트 모의 객체에 없는 API를 부르지 않는다**(R10-7·R10-9): 모의 객체는 파일마다 인라인이고 `createChart`·`addSeries`·`setData`·
  `subscribeCrosshairMove`·`timeScale().fitContent`·`remove`만 있다. `createSeriesMarkers`·`subscribeClick`·`chart.priceScale()`·`series.priceScale()`를
  부르지 않는다. 라이브러리 열거형(`TrackingModeExitMode`·`LineStyle` 등)을 **실행 중에 읽지 않는다** — 모의 모듈에 없는 내보내기를 읽으면 vitest가
  오류를 낸다(타입 가져오기와 숫자 리터럴은 괜찮다 — 지금 `lineStyle: 2`처럼). 겹침 축 여백은 `createChart` 옵션 `overlayPriceScales`로 준다
- **분할 표식 자리는 화면이 정한다**(R10-4): 서버는 효력일만 보낸다. 표식은 **그린 점(다운샘플 뒤)** 중 효력일 이상인 첫 점이다 — 서버가 정하면 그
  점이 줄이기에서 빠졌을 때 표식이 허공을 가리킨다. 표에는 분할 표시가 없다(spec FR-008 고침)
- **배치에 경계 폭 상수를 두지 않는다**(R10-10): 미디어 쿼리·`ResizeObserver` 없이 줄바꿈 flex의 기본 크기로 정한다. 표 칸이 줄어들게 하는 규칙
  (`min-w-0`로 표를 좁히기, 고정 폭)을 넣지 않는다 — 1440px 기준(006 FR-069 등)을 깨는 길이다
- **주식 다시 실행은 등록 요청을 보내지 않는다**(research R10-11): 등록 경로(`POST /api/stocks/selection`)는 목록 id나 일본 외부 결과만 받고, 이력
  항목에는 목록 id가 없다. `selectStock`을 부르지 않고 입력을 바꿔 `run()` — 이력의 종목은 이미 등록되어 있다
- **주식 가격 점은 표의 행 날짜뿐이다**(spec FR-001, 사용자 결정): 일별 가격을 따로 보내거나 그리지 않는다
- **이력 저장 형식은 바꾸지 않는다**(FR-021): 저장 키·항목 모양 그대로. 006 이전의 막힌 조합 항목도 그대로 열리고, 다시 실행은 지금 규칙으로 거절한다
- **바꿔도 되는 기존 테스트는 plan의 목록뿐이다**: `SimulationHistoryList.test.tsx`·`SimulationHistoryBlocked.test.tsx`의 `<SimulationHistory>` 렌더
  10곳에 `onRerun` 속성만 더한다(검사 내용 그대로 — research R10-12). **구현 단계에서 사용자 승인을 받은 뒤** 테스트 커밋에서 바꾸고 사유를 적는다.
  **이 밖의 기존 테스트를 바꿔야 하면 멈추고 보고한다**
- **실행 주체에는 그 주체를 거쳐야만 통과하는 테스트를 짝짓는다**(006 D1): 주식 화면의 "다시 실행" 버튼 → 스토어 → 시뮬레이션 요청(T028), 네
  화면이 실제로 `TableWithHistory`를 거치는 것(T033)
- **개발 서버를 띄운 채 통합 테스트를 돌리지 않는다**(CLAUDE.md) — 브라우저 확인(T018·T025·T031·T036·T039) 뒤에는 서버를 내리고 테스트한다
- **테스트는 네트워크 없이**(헌법 원칙 III). 새 출처가 없다 — 출처를 부르는 태스크가 없다

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 구현 전의 기준 — 계산 불변(SC-006)을 나중에 대조할 응답과 기존 검사의 통과 상태

- [X] T001 구현 전 기준 응답을 남긴다 — 서버를 띄우고(`./start.sh`) quickstart "참조 실행" 다섯(주식 AAPL·가상자산 BTC·예금 시중은행·부동산 헬리오시티
  30평대·가락미륭 20평대)의 **표 경로**(`/api/{stocks,crypto,deposit,realestate}/simulation`)와 **시계열 경로**(`…/simulation/series`) 응답을
  저장소 밖 작업용 임시 폴더에 JSON으로 저장한다(저장소에 넣지 않는다). 받은 시각과 조건을 함께 적는다. 202면 수집이 끝난 뒤 다시 받는다
  (FR-021, SC-006, quickstart 10)
- [X] T002 구현 전 기존 검사의 통과 상태를 기록한다 — 서버를 내리고(`./stop.sh`) 백엔드 `pytest -q`·`mypy src`·`ruff check --no-cache src tests`,
  프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌려 통과 수를 이 파일 Notes에 적는다. 실패가 있으면 이 기능 전의 실패로 기록하고
  멈추고 보고한다 (SC-006)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 시계열 응답의 새 키를 화면 형식에 선택 키로 둔다 — US1·US2의 화면 테스트와 구현이 기댄다

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 US1·US2의 화면 태스크(T011·T012·T017·T020·T021·T024)를 시작하지 않는다(백엔드 태스크와 US3·US4는
막지 않는다)

- [X] T003 `frontend/src/lib/types.ts` — `PriceKind = "stock_open" | "crypto_open" | "deposit_rate" | "apt_average"`, `PriceMissing = "unpublished" |
  "missing" | "no_trades"`, `SplitMark = { date: string; numerator: number; denominator: number }`. `SimulationPoint`에 `price?: DecimalString | null`
  ("가격이 있는 응답(010)에만 키가 있다"), `priceMissing?: PriceMissing`("price가 null일 때만"), `profit?: DecimalString`("부동산만 — 투자 수익(원)"),
  `SimulationSeriesResponse`에 `priceKind?: PriceKind`, `priceCurrency?: string | null`("예금은 null"), `splits?: SplitMark[]`("주식만"). **모두
  선택 키**다 — 기존 테스트 응답(가격 없음)이 `npx tsc --noEmit`을 그대로 통과해야 한다. 형식만 더하므로 테스트 없이 한 번 커밋한다(`tsc`가 검증)
  (FR-001, data-model 3절)

**Checkpoint**: `npx tsc --noEmit`·`npm test`가 T002와 같은 결과

---

## Phase 3: User Story 1 - 성과와 가격의 흐름을 한 차트에서 본다 (Priority: P1) 🎯 MVP

**Goal**: 네 화면의 성과 추이 차트에 가격 선(주가·시세·그 달 금리·그 달 실거래가 평균)을 눈금 없이 그리고, 값이 없는 날은 지어내지 않고 끊는다. 주식
분할은 표식으로 밝힌다

**Independent Test**: 네 화면에서 한 번씩 실행해 시계열의 `price`가 표의 같은 날(달) 값과 같고(예금은 그 달 금리), 값이 없는 날에 가격 점이 없으며,
범례에 이름·단위가 있는지 본다(quickstart 1~5)

### Tests for User Story 1 ⚠️

- [X] T004 [P] [US1] `backend/tests/unit/test_stock_series_price.py` — `stock_series.build_series`에 `Row`·`SimulationResult`를 직접 만들어 넣는다
  (기존 `test_stock_series_build.py`와 같은 방식): 점의 `price` = **그 날 마지막 행**의 `open_price`(같은 날 배당락 행·달 첫 행), `price`는 늘
  `None`이 아니다, `max_points`를 작게 해 줄인 점마다 `price`가 그 날짜 원래 점의 값(FR-007), `SimulationResult(splits=…)`의 분할 중 `start ≤ date
  ≤ end`인 것만 효력일 오름차순으로 `StockSeries.splits`에, **`splits`를 넘기지 않은 `SimulationResult`도 만들어진다**(기본값 `()` — 기존 테스트를
  위해) (FR-001, FR-007, FR-008)
- [X] T005 [P] [US1] `backend/tests/unit/test_deposit_series_price.py` — `simulate_deposit`(순수 함수)로 만든 `DepositOutcome`과 같은 `rates`·
  `latest_month`를 `deposit_series.build_series(outcome, start=…, rates=…, latest_month=…)`에 넣는다: 점 날짜의 달 `m`이 `m > latest_month` →
  `price None` + `price_missing "unpublished"`, `m`이 `rates`에 없음(만기 사이의 빈 달 — 계산이 멈추지 않는 경우) → `None` + `"missing"`, 아니면
  `rates[m]`. **가입·재예치 행(잠정이 아닌 행)의 적용 금리 `Row.rate` = 그 날 점의 `price`**(FR-002). 잠정 행의 대신 쓴 금리가 `price`에 들어가지
  않는다. 계산 끝 점의 달이 미발표면 `unpublished`. 줄인 점의 `price`가 그 날짜 원래 값 (FR-001~FR-003, FR-007, SC-002)
- [X] T006 [P] [US1] `backend/tests/unit/test_realestate_series_price.py` — `HoldingResult`를 직접 만들어 `realestate_series.build_series`에 넣는다:
  점의 `price` = 그 점이 나온 행의 `month_average`, **첫 점(매입일)은 매입 달 행**, **끝점(계산 끝)은 그 달 행(`rows[0]`)**, `month_average None` →
  `price None` + `price_missing "no_trades"`이고 그 점의 `balance`·`return_rate`·`estimated`는 지금과 같다(적용 시세), 시세 없음 달은 점이 없고
  `gaps`는 지금과 같다(`no_price`), 줄인 점의 `price`가 그 날짜 원래 값 (FR-001, FR-003, FR-006, FR-007, FR-011)
- [X] T007 [P] [US1] `backend/tests/integration/test_stock_series_price_api.py` — 기존 `test_stock_series_api.py`와 같은 준비로 `GET
  /api/stocks/simulation/series`: `priceKind "stock_open"`, `priceCurrency` = 종목 통화(**원화 원금으로 미국 종목을 실행해도 `USD`**), 점마다 `price`
  = 같은 조건 표(`/simulation`)의 그 날 마지막 행 `openPrice`(문자열 그대로), **점의 날짜 집합 = 표의 날짜 집합**(일별 점이 없다 — spec FR-001), 분할을 넣은 종목(효력일이 점의 날짜가 아닌 날)의 `splits`
  `[{date, numerator, denominator}]`와 효력일 앞 점·뒤 첫 점의 `price` 비율, 분할 없는 종목은 `splits: []`, `maxPoints`를 작게 한 응답의 점마다
  `price`가 전체 응답의 같은 날짜 값, `priceMissing` 키가 없다, 기존 키(`balance`·`returnRate`·`gaps`)가 그대로 (FR-001, FR-002, FR-007, FR-008,
  SC-001)
- [X] T008 [P] [US1] `backend/tests/integration/test_crypto_series_price_api.py` — 기존 `test_crypto_series_api.py`와 같은 준비로 `GET
  /api/crypto/simulation/series`: `priceKind "crypto_open"`, `priceCurrency` = 코인의 시세 통화(원화 원금이어도), 점마다 `price` = 표의 그 날
  `openPrice`, 출처 결측 날은 점이 없고 `gaps`(`source_missing`)는 지금과 같다, 다운샘플 점의 `price`가 그 날짜 값 (FR-001~FR-003, FR-007, SC-001,
  SC-002)
- [X] T009 [P] [US1] `backend/tests/integration/test_deposit_series_price_api.py` — 기존 `test_deposit_series_api.py`와 같은 준비로 `GET
  /api/deposit/simulation/series`: `priceKind "deposit_rate"`, `priceCurrency null`, 가입·재예치 점의 `price` = 표의 그 행 `rate`(잠정이 아닌 행),
  마지막 발표 달 뒤 점은 `price null` + `priceMissing "unpublished"`, 발표 기간 안에 빈 달을 하나 둔 금리로(만기 사이 달) 그 달 점이 `price null` +
  `priceMissing "missing"`이고 계산은 멈추지 않는다, 값이 있으면 `priceMissing` 키가 없다, `gaps == []`·`provisionalFrom`이 그대로 (FR-001~FR-003,
  FR-011, SC-001, SC-002)
- [X] T010 [P] [US1] `backend/tests/integration/test_realestate_series_price_api.py` — 기존 `test_realestate_series_api.py`와 같은 준비(헬리오시티 30평대,
  드문단지)로 `GET /api/realestate/simulation/series`: `priceKind "apt_average"`, `priceCurrency "KRW"`, 점마다 `price` = 표의 그 달 `monthAverage`(첫
  점은 매입 달, 끝점은 그 달), 표의 `monthAverage`가 빈 달은 `price null` + `priceMissing "no_trades"`이고 `balance`·`returnRate`는 표와 같다, 시세
  없음 달은 점이 없고 `gaps`가 지금과 같다 (FR-001~FR-003, FR-006, SC-001, SC-002)
- [X] T011 [P] [US1] `frontend/tests/chartSeriesPrice.test.ts` — 순수 함수(`lib/chartSeries.ts`): `priceSegments(points, gaps)` — 잔고와 같은 자리
  (`splitSeriesAtGaps` — `not_collected`·`source_missing`·`no_price`)에서 끊고 **`price === null`인 점에서 다시 끊는다**, `no_quote`(휴장)는 잇는다,
  점 하나뿐인 구간도 남긴다, `null` 점을 앞뒤 구간에 넣지 않는다(직전 값 복사 없음). `splitMarks(points, splits)` — 그린 점 중 `date ≥ split.date`인
  첫 점, 효력일 뒤에 점이 없으면 표식 없음, 효력일이 점의 날짜와 같으면 그 점, 같은 점에 분할 둘이면 표식 하나에 둘 다, 다운샘플로 효력일 직후 점이
  빠진 점 목록에서는 그 다음 점 (FR-003, FR-008, SC-002)
- [X] T012 [P] [US1] `frontend/tests/PerformanceChartPrice.test.tsx` — 파일 안의 인라인 모의 객체(`createChart` 옵션, `addSeries` 옵션, `setData` 값을
  기록)로 `PerformanceChart`: 점에 `price`가 있으면 가격 시리즈가 `priceScaleId "price"`·`priceLineVisible false`·`lastValueVisible false`이고 값이
  `Number(price)`·날짜가 점과 같다, `createChart` 옵션에 `overlayPriceScales`, `price null` 점에서 가격 시리즈가 둘로 나뉘고 잔고·수익률 시리즈는
  나뉘지 않는다, 점 하나뿐인 가격 구간은 `pointMarkersVisible true`, `priceKind "apt_average"`면 모든 가격 구간에 점 표식, `provisionalFrom` 뒤 가격
  구간은 연한 색, 분할 표식 시리즈(점만)가 `splitMarks`의 날짜·가격에 있다, 부동산 추정 표식은 잔고 축(`left`)에만 있고 가격 축에 없다, 범례
  `주가 (USD)`·`시세 (USD)`·`금리 (연 %)`·`실거래가 평균 (KRW)`(`priceKind` → 이름, `priceCurrency` → 단위)·분할이 있으면 `● 분할`, **같은 응답에서
  `price` 키를 지우면 시리즈 수·옵션이 지금과 같다**. 모의 객체에 `createSeriesMarkers`·`subscribeClick`·`priceScale`을 두지 않는다(부르면 실패)
  (FR-001, FR-003~FR-006, FR-008)

### Implementation for User Story 1

- [X] T013 [P] [US1] 주식 — `backend/src/api/services/stock_simulation.py`(`SimulationResult.splits: tuple[SplitOn, ...] = ()`, `run_simulation`의 두
  반환 경로 모두 `split_rows`로 채운다)·`backend/src/api/services/stock_series.py`(`SeriesPoint.price: Decimal` = 그 날 마지막 행 `row.open_price`,
  `StockSeries.splits` — 구간 안·오름차순)·`backend/src/api/routes/stock_series.py`(`priceKind "stock_open"`, `priceCurrency` = `stock.currency`, 점
  `price` = `str(p.price)`, `splits`). 시뮬레이터(`simulation/reinvest.py`)는 바꾸지 않는다 (FR-001, FR-002, FR-007, FR-008)
- [X] T014 [P] [US1] 가상자산 — `backend/src/api/services/crypto_series.py`(`SeriesPoint.price: Decimal` = `v.row.open_price`)·
  `backend/src/api/routes/crypto_series.py`(`priceKind "crypto_open"`, `priceCurrency` = `coin.quote_currency`, 점 `price` = `format(p.price, "f")`)
  (FR-001, FR-002)
- [X] T015 [P] [US1] 예금 — `backend/src/api/services/deposit_simulation.py`(`Prepared`에 `rates: Mapping[date, Decimal]`·`latest_month: date`를 더하고
  `prepare`·`simulate_or_collect` 두 곳에서 넘긴다 — `prepare`가 읽은 값 그대로)·`backend/src/api/services/deposit_series.py`(`build_series(outcome, *,
  start, rates, latest_month, max_points=…)` — `rates`·`latest_month`는 **기본값 없는 필수 인자**, `SeriesPoint.price: Decimal | None`·`price_missing:
  Literal["unpublished", "missing"] | None`, 불변식 "`price is None` ⇔ `price_missing is not None`")·`backend/src/api/routes/deposit_series.py`(`priceKind
  "deposit_rate"`, `priceCurrency None`, 점 `price` = `rate_text(p.price)` 또는 `None`, `price`가 `None`일 때만 `priceMissing`) (FR-001~FR-003, FR-011)
- [X] T016 [P] [US1] 부동산 — `backend/src/api/services/realestate_series.py`(`SeriesPoint.price: int | None` = 행의 `month_average`, 끝점은
  `result.rows[0].month_average`, `price_missing: Literal["no_trades"] | None`)·`backend/src/api/routes/realestate_series.py`(`priceKind "apt_average"`,
  `priceCurrency "KRW"`, 점 `price` = `str(p.price)` 또는 `None`, `None`일 때만 `priceMissing`) (FR-001~FR-003, FR-006)
- [X] T017 [US1] 화면 — `frontend/src/lib/chartSeries.ts`(`priceSegments`·`splitMarks`)·`frontend/src/components/stock/PerformanceChart.tsx`(점에
  `price` 키가 있을 때만: 가격 시리즈 — 겹침 축 `"price"`, 파랑 실선·잠정 연한 파랑, 점 하나 구간과 부동산은 점 표식, 분할 표식 시리즈(점만, 가격 축),
  `createChart` 옵션 `overlayPriceScales.scaleMargins`, 범례 이름·단위·`● 분할`. 머리 주석에 010 규칙을 더한다). 화면 파일(`app/*/page.tsx`)·스토어는
  바꾸지 않는다 — 시계열 응답의 새 키가 그대로 흐른다. ui-wireframes F1 (FR-001, FR-003~FR-006, FR-008)
- [X] T018 [US1] quickstart 1~5를 실행하고 `specs/010-chart-price-overlay-history-layout/quickstart.md`에 실행 기록을 더한다 — 네 화면의 표 대조
  불일치 수(0이어야 한다), 주식 주가 점 수 = 표의 날짜 수, AAPL `splits`와 표식 위치·꺾임, 예금 미발표 점, 부동산 거래 없는 달·가락미륭 시세 없음 끊김, 다운샘플 대조, 화면 캡처
  (1440px). 가상자산 출처 결측이 개발 DB에 없으면 그 사실과 T008로 갈음함을 적는다. 끝나면 서버를 내린다 (SC-001, SC-002, FR-007)

**Checkpoint**: 네 화면의 차트에 가격 선이 표와 같은 값으로 그려지고, 값이 없는 날은 끊기며, 범례가 단위를 밝힌다. 005~009 차트 테스트 그대로 통과

---

## Phase 4: User Story 2 - 마우스를 올린 날의 값을 차트 위에서 읽는다 (Priority: P1)

**Goal**: 커서 가까이 상자에 그 날(달)의 값을 표와 같은 형식으로 보이고, 값이 없는 칸은 "—"와 사유, 차트를 벗어나면 사라진다. 차트 아래 한 줄은
없앤다

**Independent Test**: 네 화면에서 차트 10곳에 마우스를 올려 상자 값이 표와 같은지, 사유가 뜨는지, 잘리지 않고 사라지는지 본다(quickstart 6·7)

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] `backend/tests/integration/test_realestate_series_profit_api.py` — 기존 `test_realestate_series_api.py`와 같은 준비로 `GET
  /api/realestate/simulation/series`: 점마다 `profit` = 표의 그 달 `profit`(원 정수 문자열), 끝점은 `summary.profit`, 거래 없는 달(`no_trades`) 점에도
  `profit`이 있다 (FR-009, SC-003)
- [X] T020 [P] [US2] `frontend/tests/chartHover.test.ts` — 순수 함수: `hoverView(series, time)` — 주식 `날짜 · 주가 $132.76 · 잔고 ₩… · 수익률`(국내
  종목 `₩70,000.00` — 표의 시작가와 같은 `formatRate`), 가상자산 `시세 $0.0000053`(표의 시가와 같은 `formatPrice`), 예금 `잔고 · 수익률 · 금리 연 3.71%`
  (`formatAnnualRate`), 부동산 `2023-06 · 평가액 · 투자 수익 · 수익률 · 실거래가 평균`(금액은 `formatMoneyWithSymbol(…, "KRW")`, **첫 점·끝 점은 날짜**),
  잔고는 `formatMoneyWithSymbol(…, basisCurrency)`, 수익률 `formatPercent`(표와 같은 부호 붙은 형식). 값 없는 칸 — 예금 `— 미발표`·`— 결측`, 부동산 `— 거래 없음`(평가액·투자
  수익·수익률은 그대로). 분할 표식 점 — `분할 1→4 (2020-08-31 효력)`(분모→분자). 자리(값 없는 시각) — 구간 `from ~ to` · 가상자산 모든 값 `—` +
  `출처 결측`, 부동산 모든 값 `—` + `시세 없음`. `gapSlots(points, gaps)` — 첫 점 ~ 끝 점 안의 `source_missing`·`no_price` **구간마다 `from` 하나**(날마다
  두지 않는다 — 여러 날 구간도 자리 하나), `no_quote`·`not_collected`는 자리 없음, 점 범위 밖 구간은 없음. `placeHover(point, box, area)` — 기본 커서 오른쪽 아래 12px, 오른쪽이 넘치면 커서 왼쪽, 아래가 넘치면 위,
  늘 `0 ≤ left ≤ area.width − box.width`·`0 ≤ top ≤ area.height − box.height` (FR-009~FR-012, SC-003)
- [X] T021 [P] [US2] `frontend/tests/PerformanceChartHover.test.tsx` — 파일 안의 인라인 모의 객체(`subscribeCrosshairMove` 콜백을 잡는다)로
  `PerformanceChart`: 콜백에 `{ time, point }`를 주면 `role="tooltip"`·`data-testid="performance-hover"` 상자가 `hoverView`의 줄을 보이고 위치가
  `placeHover`의 결과(차트 칸 크기는 `getBoundingClientRect` 흉내로), `{}`(벗어남)를 주면 상자가 없다, `performance-tooltip`(차트 아래 한 줄)이
  어떤 경우에도 없다, 다운샘플된 점의 시각이면 그 점의 날짜·값, 가격이 있고 점 범위 안에 `source_missing`·`no_price` 구간이 있으면 값 없는 자리
  시리즈(데이터가 `{ time }`뿐, **구간마다 하나**)가 있고 그 시각의 상자가 구간 `from ~ to`와 사유를 보인다, 부동산 거래 없는 달 점은 `— 거래 없음`과 평가액, 예금 미발표 점은 `— 미발표`.
  **`price` 키가 없는 응답이면 값 없는 자리 시리즈가 없다**(기존 테스트의 시리즈 수 그대로). 모의 객체에 `subscribeClick`이 없다 (FR-009~FR-014, SC-003)

### Implementation for User Story 2

- [X] T022 [US2] 부동산 투자 수익 — `backend/src/api/services/realestate_series.py`(`SeriesPoint.profit: int` = 행의 `profit`, 끝점은 `summary.profit` —
  점이 있는 행은 `profit`이 `None`이 아니다)·`backend/src/api/routes/realestate_series.py`(점 `profit` = `str(p.profit)`) (FR-009)
- [X] T023 [P] [US2] `frontend/src/lib/format.ts` — `formatAnnualRate`를 `components/deposit/DepositPerformanceTable.tsx`에서 옮긴다(동작 그대로).
  가져오는 곳 `components/deposit/DepositPerformanceTable.tsx`·`components/deposit/DepositNotice.tsx`·`app/deposit/page.tsx`를 고친다 — 차트(공유 부품)가
  예금 표 부품을 거꾸로 가져오지 않게 한다. 동작이 바뀌지 않는 이동이라 먼저 실패하는 새 테스트가 없다 — 기존 예금 화면·표 테스트가 회귀 검사이고,
  커밋에 그 사유를 적는다(헌법 원칙 III) (FR-009)
- [X] T024 [US2] 화면 — `frontend/src/lib/chartHover.ts`(신규 — `hoverView`·`placeHover`)·`frontend/src/lib/chartSeries.ts`(`gapSlots`)·
  `frontend/src/components/stock/PerformanceChart.tsx`(차트 칸을 `relative`로 감싸고 상자를 `absolute`로, `subscribeCrosshairMove`의 `time`·`point`로
  상자를 열고 닫는다 — 값은 지금처럼 `lookup`의 **원본 문자열**, 가격이 있을 때만 값 없는 자리 시리즈(겹침 축, `{ time }`만, 구간마다 하나), **차트 아래 한 줄
  `performance-tooltip`을 없앤다**, 터치는 라이브러리 기본 추적 모드 그대로 — 새 API·열거형 읽기 없음). ui-wireframes F2 (FR-009~FR-014)
- [X] T025 [US2] quickstart 6·7을 실행하고 기록한다 — 네 화면 × 10곳의 상자 값과 표 대조(다른 값 0건), 마우스 이동부터 상자 표시까지의 시간(0.2초 안),
  오른쪽·아래 끝의 잘림 0건, 벗어난 뒤 남는 상자 0건, 터치 흉내(길게 누름 → 상자, 따라감, 다음 탭에 사라짐). 끝나면 서버를 내린다 (SC-003, FR-012,
  FR-014)

**Checkpoint**: 상자가 커서 가까이 표와 같은 값을 보이고, 차트 아래 한 줄이 없다

---

## Phase 5: User Story 3 - 주식 이력에서 다시 실행한다 (Priority: P2)

**Goal**: 주식 최근 시뮬레이션의 각 항목에 "다시 실행"을 더한다 — 그 항목의 종목·조건을 입력에 넣고 곧바로 실행한다(등록 요청 없음 — 이력의
종목은 이미 등록되어 있다)

**Independent Test**: 두 조건으로 이력을 만든 뒤 다른 종목을 고른 상태에서 다시 실행해 입력·결과가 그 항목대로 돌아오는지, 막힌 조합이 거절되는지
본다(quickstart 9)

### Tests for User Story 3 ⚠️

- [X] T026 [P] [US3] `frontend/tests/stockStoreRerun.test.ts` — `apiClient`를 흉내 내어 `useStockStore.getState().rerunHistory(id)`: 입력이 항목의
  `stock`·`start`·`principal`·`principalCurrency`·`reinvest`가 되고, `listedOn`·`startable`·`selectionError`가 `null`이 되고, `GET
  /api/stocks/simulation?…`이 그 조건(`reinvest`·`principalCurrency` 포함)으로 나간다. **등록 요청(`/api/stocks/selection`)이 나가지 않는다**(research
  R10-11 — 등록 경로는 목록 id·일본 외부 결과만 받는다). 막힌 조합(원금 EUR·미국 종목) → 입력은 항목대로 들어가고 시뮬레이션 요청 없이
  `error` = `run()`의 지금 문구(`principalRule(…)` + "통화를 다시 고르세요."), 통화가 바뀌지 않는다. 202 → `collecting`이 들어가고 진행 구독이
  시작된다(`run()`과 같다). 없는 id → 아무 요청 없음 (FR-018~FR-020, SC-005)
- [X] T027 [P] [US3] `frontend/tests/SimulationHistoryRerun.test.tsx` — `<SimulationHistory onRerun={…}>`: 행(`history-row`)마다 "다시 실행" 버튼,
  `aria-label` = `{행 이름} 다시 실행`(가상자산 `CryptoHistory`와 같은 꼴), 삭제 `×` 앞, 누르면 `onRerun(entry.id)`, **막힌 조합 행에도 버튼이 있다**
  (FR-018, FR-019)
- [X] T028 [P] [US3] `frontend/tests/StocksPageRerun.test.tsx` — 기존 `CryptoPage.test.tsx`와 같은 방식(진행 스트림 모듈 흉내, `fetch` 흉내)으로
  주식 화면을 렌더하고 브라우저 저장소에 006 형식 이력 항목을 넣는다 → 화면에서 "다시 실행"을 누르면 그 항목 조건의 시뮬레이션 요청이 나가고
  등록 요청은 없다(**화면 → 스토어 → `run()` 경로를 거쳐야만 통과** — 006 D1) (FR-018, FR-020)
- [X] T029 [US3] **기존 테스트 변경(D2 — 사용자 승인 뒤)** `frontend/tests/SimulationHistoryList.test.tsx`·`frontend/tests/SimulationHistoryBlocked.test.tsx`
  — `<SimulationHistory>` 렌더 10곳에 `onRerun={vi.fn()}`(또는 기존 흉내 함수와 같은 꼴)만 더한다. 검사 내용은 바꾸지 않는다. 승인 전에는 이 태스크와
  T030을 시작하지 않고 보고한다(plan 설계 후 재평가, research R10-12)

### Implementation for User Story 3

- [X] T030 [US3] `frontend/src/stores/stockStore.ts`(`rerunHistory(id)` — 항목을 찾아 `set({ input: { stock: entry.stock, start, principal,
  principalCurrency, reinvest }, listedOn: null, startable: null, selectionError: null })` 뒤 `run()` — 가상자산 `rerunHistory`와 같은 꼴, `selectStock`·
  등록 요청 없음. 이력 저장 형식은 그대로)·
  `frontend/src/components/stock/SimulationHistory.tsx`(필수 속성 `onRerun: (id: string) => void`, 행마다 "다시 실행" 버튼 — `CryptoHistory`와 같은 문구·
  클래스, 지금 행 끝의 `ml-auto`를 버튼으로 옮긴다)·`frontend/src/app/stocks/page.tsx`(`onRerun={(id) => void rerunHistory(id)}`). ui-wireframes F4
  (FR-018~FR-020)
- [X] T031 [US3] quickstart 9를 실행하고 기록한다 — 다시 실행 결과(보드·표)와 같은 조건 직접 실행의 대조(다른 사례 0건), 막힌 조합 항목의 거절과
  사유, 받지 않은 구간 항목의 수집 진행. 끝나면 서버를 내린다 (SC-005)

**Checkpoint**: 주식 이력의 다시 실행이 직접 실행과 같은 결과를 낸다

---

## Phase 6: User Story 4 - 최근 시뮬레이션을 성과 표 옆에서 본다 (Priority: P3)

**Goal**: 네 화면의 최근 시뮬레이션을 창이 넓으면 성과 표 오른쪽(sticky)에, 좁으면 지금처럼 아래에 둔다 — 경계는 표의 실제 폭으로 정해진다

**Independent Test**: 네 화면에서 창 폭을 바꾸며 표와 이력이 나란히 놓이는 경계 폭을 재고, 표의 열이 잘리지 않으며 표를 내려도 이력이 남는지
본다(quickstart 8)

### Tests for User Story 4 ⚠️

- [ ] T032 [P] [US4] `frontend/tests/TableWithHistory.test.tsx` — `<TableWithHistory table={…} history={…}>`: 바깥(`data-testid="table-with-history"`)이
  `flex flex-wrap items-start gap-5`, 표 칸이 `flex: 999 1 auto`(기본 크기 = 표 고유 폭 — 표를 좁히는 `min-w-0`·고정 폭 없음), 이력 칸이 `flex: 1 1
  400px`·`sticky top-4 self-start`·`max-height: calc(100vh − 2rem)`·세로 스크롤, DOM 순서 표 → 이력, `table`이 없으면(실행 전) 이력 칸만.
  네 이력 부품(`SimulationHistory`·`CryptoHistory`·`DepositHistory`·`RealEstateHistory`)의 행(`history-row`)이 `flex-wrap`(칸 안 가로 넘침 없음)
  (FR-015~FR-017, SC-004 — 구조, data-model 6절)
- [ ] T033 [P] [US4] `frontend/tests/TableWithHistoryPages.test.tsx` — 기존 화면 테스트(`CryptoPage`·`DepositPage`·`RealEstatePage.test.tsx`)와 같은
  흉내로 네 화면(주식·가상자산·예금·부동산)을 결과가 있는 상태(스토어 `setState`)로 렌더한다: 성과 표 `section`과 최근 시뮬레이션이 **같은
  `table-with-history` 안**에 표 → 이력 순서, 이력 비교 차트(와 출처 줄이 있는 화면 — 예금·부동산 — 의 출처 줄)는 그 밖·뒤, 결과가 없으면 이력만 그 안 (FR-015, FR-017 — 006 D1)

### Implementation for User Story 4

- [ ] T034 [US4] `frontend/src/components/TableWithHistory.tsx`(신규 — data-model 6절의 규칙, 경계 폭 상수·미디어 쿼리 없음, 머리 주석에 research
  R10-10의 이유)·이력 행 줄바꿈 `frontend/src/components/stock/SimulationHistory.tsx`·`frontend/src/components/crypto/CryptoHistory.tsx`·
  `frontend/src/components/deposit/DepositHistory.tsx`·`frontend/src/components/realestate/RealEstateHistory.tsx`(행 `flex-wrap`, 버튼 묶음은 줄의 끝)
  (FR-015, FR-016)
- [ ] T035 [US4] 네 화면 `frontend/src/app/stocks/page.tsx`·`frontend/src/app/crypto/page.tsx`·`frontend/src/app/deposit/page.tsx`·
  `frontend/src/app/realestate/page.tsx` — 성과 표 `section`과 이력 부품을 `TableWithHistory`로 감싼다. 차트는 그 위, 이력 비교 차트·출처 줄은 그
  아래 그대로. 머리 주석의 화면 순서 설명을 고친다. ui-wireframes F3 (FR-015~FR-017)
- [ ] T036 [US4] quickstart 8을 실행하고 기록한다 — 네 화면(주식은 원화 원금 해외 종목)에서 1440px 창의 표 가로 스크롤 없음, 1280~1920px을 10px씩(예금의 계산 경계 약 1,390px)
  넓혀 찾은 **경계 폭**, 경계 폭과 10px 좁은 폭의 표·이력 칸 가로 넘침 없음, 경계 이상에서 끝까지 내려도 이력이 화면 안, 비교 차트 전체 폭.
  측정값을 `specs/010-chart-price-overlay-history-layout/plan.md`의 "측정한 경계 폭" 표 "구현 뒤 실측" 열에 적는다. **어느 경계든 1920px을 넘으면
  멈추고 보고한다**(경계를 조용히 넓히지 않는다 — spec Assumptions). 끝나면 서버를 내린다 (SC-004, FR-015)

**Checkpoint**: 넓은 창에서 표와 이력이 나란히, 좁은 창에서 지금처럼 아래. 표의 열은 어느 폭에서도 잘리지 않는다

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T037 [P] `README.md`·`CLAUDE.md` — 현재 상태 표에 010(네 자산군 차트의 가격 선 — 주식 원주가 시가·분할 표식, 가상자산 시가, 예금 그 달 발표
  금리, 부동산 그 달 실거래가 평균, 눈금 없는 겹침 축 / 커서 가까이 상자·값 없는 칸의 사유 / 표 옆 최근 시뮬레이션 — 경계는 표의 실제 폭 / 주식 이력
  다시 실행). CLAUDE.md에 **차트 모의 객체 주의**(기존 차트 테스트의 인라인 모의 객체에 없는 API·열거형을 실행 중에 쓰지 않는다)와 **가격 결측은
  `gaps`가 아니라 `priceMissing`**을 한 줄씩 (헌법 원칙 VIII — 문서화. 대응 FR 없음)
- [ ] T038 품질 게이트 — 서버를 내리고 백엔드 전체 테스트·커버리지 80% 이상·`mypy src`(strict)·`ruff check --no-cache src tests`, 프론트엔드
  `npm test`·`npx tsc --noEmit`·`npx eslint .`. **기존 테스트 파일이 plan의 목록(T029의 둘) 밖에서 바뀌지 않았는지** `git diff --stat`(T002 기준
  커밋부터)으로 따로 확인하고, 통과 수를 T002와 견준다 (SC-006)
- [ ] T039 quickstart 10을 실행하고 기록한다 — T001의 기준 응답과 같은 조건의 구현 뒤 응답을 대조한다: 표 경로의 `summary`·`rows`가 같고, 시계열
  경로의 기존 키(`balance`·`returnRate`·`gaps`·`provisionalFrom`·`estimated`·`provisional`)가 같다(새 키만 늘었다). 이력 비교 차트·외환 화면이 그대로다.
  다른 것이 하나라도 있으면 멈추고 보고한다. 끝나면 서버를 내린다 (FR-021, SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작. **T001·T002는 다른 모든 코드 변경보다 먼저다** — 기준이 바뀐 뒤에는 남길 수 없다
- **Foundational (Phase 2)**: T002 뒤. 화면 쪽 스토리 태스크를 막는다(백엔드 태스크 T004~T010·T013~T016은 막지 않는다)
- **US1 (Phase 3)**: Foundational 뒤. MVP
- **US2 (Phase 4)**: US1 뒤 — 상자가 가격을 보이고, 같은 파일(`PerformanceChart.tsx`·`chartSeries.ts`·`realestate_series.py`)을 만진다
- **US3 (Phase 5)**: Setup 뒤면 언제든(차트와 무관). **T029는 사용자 승인 뒤**
- **US4 (Phase 6)**: Setup 뒤면 언제든. US3과 같은 파일(`SimulationHistory.tsx`·`app/stocks/page.tsx`)을 만지므로 US3 뒤가 자연스럽다
- **Polish (Phase 7)**: 모든 스토리 뒤

### Within Each Phase

- 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 백엔드: 계산 결과 형식(`Prepared`·`SimulationResult`) → 조립 함수 → 라우트. 화면: 순수 함수 → 부품 → 화면

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `frontend/src/components/stock/PerformanceChart.tsx`·`frontend/src/lib/chartSeries.ts` | T017, T024 |
| `backend/src/api/services/realestate_series.py`·`backend/src/api/routes/realestate_series.py` | T016, T022 |
| `frontend/src/components/stock/SimulationHistory.tsx` | T030, T034 |
| `frontend/src/app/stocks/page.tsx` | T030, T035 |
| `frontend/src/app/deposit/page.tsx` | T023, T035 |
| `specs/010-chart-price-overlay-history-layout/quickstart.md`(실행 기록) | T018, T025, T031, T036, T039 |
| `specs/010-chart-price-overlay-history-layout/plan.md`(경계 폭 기록) | T036 |
| 기존 테스트 `SimulationHistoryList.test.tsx`·`SimulationHistoryBlocked.test.tsx` | T029 |

### Parallel Opportunities

- US1 테스트 T004~T012는 모두 다른 파일 — 함께 쓴다
- US1 백엔드 구현 T013~T016은 자산군마다 다른 파일 — 함께 한다
- US2 테스트 T019~T021, US3 테스트 T026~T028, US4 테스트 T032·T033은 각 페이즈 안에서 함께 쓴다
- US3·US4는 US1·US2와 다른 파일(위 표의 겹침 제외) — 차트 작업과 나란히 진행할 수 있다

---

## Parallel Example: Phase 3 (US1 테스트)

```text
Task: "T004 test_stock_series_price.py — 그 날 마지막 행의 시가·분할 구간·다운샘플"
Task: "T005 test_deposit_series_price.py — unpublished·missing·적용 금리와 같음"
Task: "T006 test_realestate_series_price.py — month_average·no_trades·첫 점·끝점"
Task: "T007 test_stock_series_price_api.py — 표 openPrice 대조·USD·splits"
Task: "T008 test_crypto_series_price_api.py — 표 openPrice 대조·시세 통화"
Task: "T009 test_deposit_series_price_api.py — 표 rate 대조·미발표·결측 달"
Task: "T010 test_realestate_series_price_api.py — 표 monthAverage 대조·거래 없음"
Task: "T011 chartSeriesPrice.test.ts — priceSegments·splitMarks"
Task: "T012 PerformanceChartPrice.test.tsx — 겹침 축·끊김·표식·범례·키 없으면 그대로"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1(기준 응답·기준 게이트) → Phase 2(형식)
2. Phase 3 (US1) — **멈추고 검증**: T018 — 네 화면의 가격 선이 표와 같고 결측이 끊긴다

### Incremental Delivery

1. MVP(US1) — 가격 선·분할 표식·범례
2. US2 — 커서 가까이 상자·사유·아래 한 줄 제거
3. US3 — 주식 다시 실행(기존 테스트 변경 승인 뒤)
4. US4 — 표 옆 최근 시뮬레이션, 경계 폭 실측 기록
5. Polish — 기록 갱신, 게이트, 계산 불변 대조

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(010): <페이즈>`. 그 페이즈의 테스트만 담고 **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는
     예정된 것이다. plan 목록의 기존 테스트(T029)를 바꾸면 이 커밋에서 바꾸고 사유를 적는다 — 목록 밖의 기존 테스트를 바꿔야 한다면 먼저 보고한다
  2. **구현 커밋** — `feat(010): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다
  - 테스트가 없는 태스크만 있는 페이즈(Setup의 기준 기록, Foundational의 형식, 브라우저 확인, 문서)는 한 번 커밋한다(Setup의 기준 응답은 저장소에
    넣지 않으므로 커밋할 것이 없으면 Notes 기록만)
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다** — 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2)
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
- 설계 중 spec이 바뀌면(FR·SC) plan의 추적성 표와 이 파일의 참조를 같은 작업 단위에서 고친다(헌법 명세 작성 규약)
- **2026-10-05 T001 기준 응답**: 저장소 밖 작업용 임시 폴더(`010-baseline/`)에 다섯 참조 실행의 표·시계열 응답을 저장했다 — 주식 AAPL(NASDAQ,
  표 112행·점 112), 가상자산 BTC(coinId 1, 표 34행 — **표는 달마다, 시계열은 날마다 1,008점**), 예금 시중은행(표 38행·점 37), 부동산 헬리오시티
  30평대(complexId 4, 표 68행·점 69)·가락미륭 20평대(complexId 17, 점 65 — 시세 없음 구간). 가상자산의 "표와 대조"(T008·T018)는 표에 있는 날만 할 수
  있다 — 나머지 날은 받아 둔 일봉의 시가와 대조한다
- **2026-10-05 T002 기준 게이트**: 백엔드 2,315 passed(커버리지 95.92%), mypy 195 파일 통과, ruff 통과 / 프론트엔드 114 파일·1,031 passed, tsc·eslint 통과
