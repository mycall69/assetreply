---

description: "Task list for 011-recurring-investment-installment-savings"
---

# Tasks: 주식·가상자산 적립식 투자, 예금 정기 적금, 주식 매도 세금 설정

**Input**: Design documents from `/specs/011-recurring-investment-installment-savings/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
- 테스트 작성 → **실패 확인** → 구현 순서다.
- **테스트를 구현보다 먼저 커밋한다.** 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes).
- **구현 뒤 테스트가 실패하면 멈추고 실패 목록과 원인 판단을 먼저 보고한다.** 원인이 테스트 쪽으로 보여도 같다. 이전에 통과하던 테스트가 실패로 바뀐
  경우도 같다(006 D2).

**Organization**: 사용자 스토리별로 묶는다.
- US1(주식 적립식, P1)이 MVP다.
- US2(가상자산 적립식)·US3(정기 적금)은 P2, US4(매도 세금 설정 화면)는 P3다.
- 매도 세금의 **계산 기반**(설정 저장소·세율 인자화)은 US1의 보드가 기대므로 Foundational에 둔다. US4는 설정 경로·화면을 맡는다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python은 `backend/.venv/bin/python`을 직접 호출한다(헌법 — Python 가상환경 필수).
- 린트는 `ruff check --no-cache`(CLAUDE.md)다. 테스트를 먼저 쓸 때 임포트는 구현 뒤 기준(전부 `src.*` 묶음)으로 정렬한다.

## 이 기능에서 특히 조심할 것

- **일시금·정기예금은 바뀌지 않는다**(FR-039, SC-006)
  - `simulation/reinvest.py`·`crypto_hold.py`는 고치지 않는다. `deposit_rollover.py`는 금리 해석기를 공개 이름으로 꺼내는 것만 한다(동작 불변).
  - 일시금 경로(`/api/stocks/simulation`·`/api/crypto/simulation`·`/api/deposit/simulation`과 `/series`)의 조회 문자열·응답 모양은 그대로다. 예외는
    주식 보드 `saleCost`의 세율이 설정에서 오는 것뿐이다.
  - T001이 기준 응답을 남기고 T067이 대조한다.
- **바꿔도 되는 기존 테스트는 셋뿐이고, 바꾸기 전에 승인을 받는다**(plan 설계 후 재평가)
  - `tests/unit/test_stock_sale_cost.py`
  - `tests/integration/test_stock_sale_cost_api.py::test_세율_표_밖_기준일은_세금을_비운다`
  - `tests/unit/test_no_hardcoded_dates.py`의 `_LEGAL_DATE_MODULES`
  - T008·T033이 승인을 받는다. 이 밖의 기존 테스트를 바꿔야 하면 멈추고 보고한다.
  - 공유 테스트 보조(`tests/integration/deposit_support.py` 등)에는 **더하기만** 한다. 기존 상수·함수의 값과 동작은 그대로 둔다.
- **기본 매도 세율은 010 반복 4의 표 값과 문자열까지 같다**(R11-7) — `Decimal("0.0020")`·`Decimal("0.22")`·`Decimal("2500000")`.
  - `test_stock_sale_cost_api.py`의 국내·해외 검사가 `taxRate: "0.0020"`·`"0.22"`·`deduction: "2500000"`을 정확히 비교한다.
  - `saleCost` 키를 늘리지 않는다.
- **가드 테스트의 금지 낱말을 쓰지 않는다**
  - `test_no_interpolation`은 주석·문서 문자열까지 "전일 값"·"이전 값"·"직전 값"·`fillna`·`ffill`·`bfill`·`interpolate`·`backfill`을 찾는다.
  - `test_no_adjusted_price`는 `adjusted_close`·`close_adjusted`·`adjclose`를 찾는다.
  - `test_layer_boundaries`는 ECOS 응답 키(`ITEM_CODE`·`ITEM_NAME`·`DATA_VALUE`·`StatisticSearch` 등)를 어댑터 밖에서 찾는다.
  - `test_dialect_isolation`은 `text(` 앞에 사유 주석이 있는지 본다.
  - `test_no_hardcoded_dates`는 날짜 리터럴을 허용 목록 모듈에서만 받는다 — 가상자산 과세 시행일은 `crypto_sale_cost.py` 하나다.
- **휴장·결측의 납입은 다음 거래일로 미룬다** — 다른 날의 가격으로 사지 않는다. 예정일은 늘 시작일에서 센다. 계산 끝 뒤로 미뤄진 납입은 넣지
  않는다(R11-3).
- **재투자 끔의 배당은 매수에 쓰이지 않는다**(R11-4, SC-004). 돈의 칸을 매수 대기금·배당 현금 둘로 둔다.
- **화면은 계산하지 않는다**(`tests/noClientSideFinance.test.ts`). 합·평가·주기 일정은 모두 서버가 준다. 화면의 주기 안내 문장은 날짜를 계산하지 않고
  요일·날짜 이름만 쓴다.
- **금리 계열 키(`{inst}_isav`)는 API·화면에 나오지 않는다**(R11-2). 서비스가 (투자처, 상품)을 키로 바꾼다.
- **공유 차트는 조건부로 바꾼다**(R11-12)
  - 누적 납입 원금 선은 점에 `principal` 키가 있을 때만 그린다.
  - 005~010의 `PerformanceChart*.test.tsx`·`chartSeries*.test.ts`·`chartHover.test.ts`는 고치지 않고 통과해야 한다.
  - 모의 객체에 없는 API(`createSeriesMarkers`·`subscribeClick`·`priceScale()`)나 라이브러리 열거형을 실행 중에 쓰지 않는다(`lineStyle`은 숫자
    리터럴).
- **일시금 화면 테스트를 지킨다**(R11-11)
  - `stockStoreRerun.test.ts`·`StocksPageRerun.test.tsx`가 일시금 조회 문자열과 `input` 다섯 칸을 정확히 비교한다.
  - 방식·주기는 `plan` 칸에 둔다(`input` 밖). 적립식 결과는 `recurring`·`installment` 칸에 둔다.
- **ECOS 인증키를 출력하거나 셸 인자로 넘기지 않는다.** 픽스처는 응답 본문만 저장한다(URL에 키가 있다).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 구현 전의 기준(불변 대조용 응답·기존 검사 통과 상태)과 출처 픽스처

- [X] T001 구현 전 기준 응답을 남긴다 (FR-039, SC-006, quickstart 3-3)
  - 서버를 띄운다(`./start.sh`).
  - 다음 일시금의 표 경로와 `/series` 응답을 저장소 밖 작업용 임시 폴더(`011-baseline/`)에 JSON으로 저장한다. 받은 시각·조건을 함께 적는다.
    - 주식 KRX 005930.KS(원화)
    - 주식 NASDAQ AAPL(원화 원금 — 해외 매도 세금)
    - 가상자산 BTC(원화)
    - 예금 시중은행
    - 부동산 헬리오시티 30평대(표·시계열 — 손대지 않지만 FR-039의 대조 대상, 분석 E1)
    - 외환 USD(`/api/fx/series` 최근 1년 — 같은 이유)
  - 202면 수집이 끝난 뒤 다시 받는다.
- [X] T002 구현 전 기존 검사의 통과 상태를 기록한다 (SC-006)
  - 서버를 내린다(`./stop.sh`).
  - 백엔드 `pytest -q --cov=src`·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수를 이 파일 Notes에 적는다. 실패가 있으면 기능 전의 실패로 기록하고 멈추고 보고한다.
- [X] T003 ECOS 적금 시계열 픽스처를 저장한다 (FR-029, research R11-1)
  - 작업 폴더의 스크립트가 `.env`에서 키를 읽는다. 키는 출력하지 않는다.
  - `StatisticSearch`(월)로 `121Y002/BEABAA2122`(2003-01~2026-08)와 `121Y004/BEBB0200`(2012-01~2026-08)의 **응답 본문만** 받아 저장한다.
    - `backend/tests/contract/fixtures/deposit/series_commercial_bank_isav.json`
    - `backend/tests/contract/fixtures/deposit/series_mutual_finance_isav.json`
  - 기존 `items_121Y002.json`·`items_121Y004.json`에 두 항목과 `정기적금(3년만기)`·`정기적금(3-4년)`이 있는지 확인한다(없으면 멈추고 보고).
  - `backend/tests/contract/fixtures/deposit/README.md`에 받은 날짜·항목·행 수를 더한다.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 세 스토리가 함께 기대는 것들이다.
- 납입 일정·환전(US1·US2)
- 화면 형식·차트의 누적 납입 원금 선(US1~US3)
- 매도 세금의 계산 기반(US1·US4)

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 US1~US4를 시작하지 않는다. 예외로 US3의 백엔드 태스크 T040~T047은 T003 뒤면 시작할 수 있다. T048은
`recurring_series.py`·`main.py`·`errors.py`를 T026과 함께 만지므로 T026 뒤다(분석 F3).

### Tests for Foundational ⚠️

- [X] T004 [P] `backend/tests/unit/test_contribution_schedule.py` — `simulation/contribution_schedule` (FR-003~FR-005, FR-010, FR-018, SC-002)
  - `scheduled_dates(start, end, frequency, trading_days=…)`
    - 매주 = 시작일 + 7k
    - 매달 = 시작일 날짜, 없는 달은 말일(1-31 → 2-28/29·3-31·4-30)이고 늘 시작일에서 센다(4-30 다음이 5-31)
    - 매년 = 같은 월·일, 2-29 → 평년 2-28
    - 매일(주식) = 넘긴 거래일, 매일(가상자산) = 달력일
    - 계산 끝 포함
  - `assign`
    - 휴장일 예정일 → 다음 거래일
    - 긴 연휴로 예정일 둘이 한 날에 모임 → `ScheduledContribution(on, scheduled=(d1, d2))`
    - 계산 끝 뒤 → `pending_after_end` 1
    - 예정일 = 거래일이면 미뤄짐 없음
  - `fund`
    - 원화·원화 → 금액 그대로, `basis_krw` = 금액
    - 원화 원금·USD 종목 → `to_foreign(금액, exchange_rate(그날 매매기준율, 스프레드))`(90% 우대), 고시일 = 그날 또는 가장 가까운 이전 확정일,
      `fx_kind "cash_buy_discounted"`
    - USD 원금 → 금액 그대로, `basis_krw = to_principal(금액, 그날 매매기준율, "KRW")`, `fx_kind "base"`
    - 예정일 n개가 모인 납입의 금액 = 납입액 × n
    - 그날 이전 환율이 없으면 예외
- [X] T005 [P] `backend/tests/integration/test_stock_sale_tax_setting.py` — `repository/stock_setting`의 `get_sale_tax`·`save_sale_tax` (FR-035, FR-037, data-model 1.1)
  - 통합 DB 세션 fixture(`session_factory`)를 쓰는 저장소 검사다.
  - 행 없음 → 기본값 `Decimal("0.0020")`·`Decimal("0.22")`·`Decimal("2500000")`, `str()` 결과가 `"0.0020"`·`"0.22"`·`"2500000"`, `is_default True`
  - 수수료·배당 세율만 저장한 기존 행 → 세 열 NULL → 기본값
  - 저장한 뒤 → DB 6자리(`"0.001500"`), `is_default False`
  - 기존 `get_settings`·`save_settings` 결과 불변
- [X] T006 [P] `frontend/tests/PerformanceChartPrincipal.test.tsx` — 파일 안의 인라인 모의 객체(기존 차트 테스트와 같은 방식) (FR-015, FR-019, FR-032)
  - 점에 `principal`이 있으면 잔고 축(`left`)에 점선 시리즈가 하나 더 생긴다(`lineStyle` 숫자 리터럴). 값 = `Number(principal)`, 날짜 = 점.
  - 결측 `gaps`·`provisionalFrom`에서 잔고 선과 같이 끊고 구별한다.
  - 범례 "┄ 누적 납입 원금 (KRW)"
  - 커서 상자에 "누적 납입 원금 ₩…"(표와 같은 `formatMoneyWithSymbol`), `depositRate`가 있으면 "정기예금 금리 2.9%"(`formatAnnualRate`)
  - **같은 응답에서 `principal`·`depositRate` 키를 지우면 시리즈 수·옵션·범례가 지금과 같다**
- [X] T007 [P] `frontend/tests/chartHoverPrincipal.test.ts` — `lib/chartHover` (FR-015, FR-032)
  - `hoverView`가 `principal` 키가 있는 점에서 "누적 납입 원금" 줄을 잔고 다음에 둔다.
  - 적금 시계열(`priceKind "installment_rate"`)에서 "적금 금리"·"정기예금 금리" 줄을 둔다.
  - 키가 없으면 기존 줄 목록과 같다(기존 `chartHover.test.ts` 그대로).
- [X] T008 **기존 테스트 변경 승인을 받는다**(A1·A2 — research R11-7, plan 설계 후 재평가)
  - 사용자에게 두 파일의 바뀔 검사(이름·이유·바뀐 기대값)를 보이고 승인을 받는다.
    - `backend/tests/unit/test_stock_sale_cost.py`: 시행일 표·`transaction_tax_rate`·표 밖 검사 셋 → 세율 인자 검사
    - `backend/tests/integration/test_stock_sale_cost_api.py::test_세율_표_밖_기준일은_세금을_비운다` → 2021 기준일도 설정 세율
  - 승인 전에는 T009를 시작하지 않는다. (FR-037, 006 D2)
  - **2026-10-06 승인**: A1·A2·A3 셋 다(A3는 T037에서 바꾼다)
- [X] T009 승인된 변경(T008 뒤) — `backend/tests/unit/test_stock_sale_cost.py` (FR-013, FR-037)
  - 세율 인자 검사로 바꾼다 — `domestic_sale_cost(sale_krw, fee_rate=…, tax_rate=…)`, `foreign_sale_cost(…, rate=…, deduction=…)`.
  - 원 미만 버림·공제 이하·손실의 기대값은 지금 그대로다.
  - 새 검사
    - 세율 0이면 세금 0
    - 공제 0이면 차익 전부 과세
    - `tax`·`total`이 늘 값이다
  - `backend/tests/integration/test_stock_sale_cost_api.py`의 표 밖 검사 하나를 바꾼다 — KRX 2021 기준일도 `taxKind "transaction_tax"`·`taxRate "0.0020"`·`profitAfterSale`에 값.
    나머지 검사는 고치지 않는다.

### Implementation for Foundational

- [X] T010 `backend/src/simulation/contribution_schedule.py` — `Frequency`·`scheduled_dates`·`ScheduledContribution`·`assign`·`Contribution`·`fund` (data-model 2.1)
  - 순수 함수다. `fx_convert`의 `exchange_rate`·`to_foreign`·`to_principal`·`resolve_rate`를 쓴다.
  - 머리 주석에 R11-3·R11-5 규칙을 적는다(가드 낱말 금지). (FR-003~FR-005, FR-010, FR-018)
- [X] T011 매도 세금 계산 기반 (FR-013, FR-035, FR-037, FR-039)
  - `backend/src/db/models.py`(`StockSetting`에 열 셋)
    - `sale_tax_rate_domestic: Mapped[Decimal | None] = mapped_column(SPREAD, nullable=True)`
    - `capital_gains_rate_foreign` 같음
    - `capital_gains_deduction_foreign: Mapped[Decimal | None] = mapped_column(WON, nullable=True)` — 주석 "NULL = 기본값"
  - `backend/src/db/migrations/versions/<rev>_주식_매도_세금_설정.py`(`down_revision = "e3b9c4d27f61"`, 열 셋 추가·제거)
  - `backend/src/repository/stock_setting.py`
    - `DEFAULT_SALE_TAX_DOMESTIC = Decimal("0.0020")`, `DEFAULT_CAPITAL_GAINS_RATE = Decimal("0.22")`, `DEFAULT_CAPITAL_GAINS_DEDUCTION = Decimal("2500000")`
    - `SaleTaxSettings(domestic, foreign_rate, foreign_deduction, is_default)`, `get_sale_tax`, `save_sale_tax`
    - 기존 함수는 그대로
  - `backend/src/simulation/stock_sale_cost.py`
    - `TRANSACTION_TAX`·`CAPITAL_GAINS`·`transaction_tax_rate`·`OUTSIDE_KIND`를 없앤다. 함수가 `tax_rate`/`rate`·`deduction`을 받는다.
    - 머리 주석의 "표 밖은 비운다"를 "설정값(011 FR-037)"으로 고친다.
  - `backend/src/api/services/stock_sale.py`(`sale_cost_for(result, *, market, fee_rate, sale_tax: SaleTaxSettings)`)
  - `backend/src/api/services/stock_simulation.py`(`Prepared.sale_tax`, `prepare`가 `get_sale_tax`로 읽는다)
  - `backend/src/api/routes/stock_simulation.py`(`summary_json(…, sale_tax=…)`)
  - 개발 DB에 `alembic upgrade head`를 올리고 quickstart 0에 적는다.
- [X] T012 [P] 화면 형식 — `frontend/src/lib/types.ts` (FR-002, FR-015, FR-022, FR-035, data-model 3·4, contracts/rest-api)
  - `Frequency = "daily" | "weekly" | "monthly" | "yearly"`
  - `SimulationPoint.principal?: DecimalString`("적립식·적금 시계열에만"), `depositRate?: DecimalString`("적금만")
  - `PriceKind`에 `"installment_rate"`
  - 응답 형식
    - `RecurringStockResponse`·`RecurringStockRow`·`RecurringSummary`
    - `RecurringCryptoResponse`·`RecurringCryptoRow`
    - `InstallmentResponse`·`InstallmentRow`·`InstallmentContract`·`LadderDeposit`·`InstallmentSummary`
    - `CryptoSaleCost`
    - `DepositInstitution.installment?: {available: true; description; firstMonth; latestMonth; checkedOn; startableFrom} | {available: false; reason}`
    - `SaleTaxSettings`
  - 모두 새 형식이거나 선택 키다 — 기존 테스트가 `npx tsc --noEmit`을 그대로 통과해야 한다.
- [X] T013 공유 차트 — `frontend/src/components/stock/PerformanceChart.tsx`·`frontend/src/lib/chartSeries.ts`·`frontend/src/lib/chartHover.ts` (FR-015, FR-019, FR-032)
  - `toPerformanceData`의 필드에 `"principal"`
  - 점에 `principal` 키가 있을 때만 잔고 축 점선(`lineStyle: 1`) 시리즈 — 결측·잠정 분할은 잔고와 같은 경로
  - 범례·상자 줄(`principal`·`depositRate`)
  - `PRICE_NAME`에 `installment_rate: "적금 금리"`
  - ui-wireframes §5

**Checkpoint**: T004~T007·T009가 통과한다. `npm test`·`npx tsc --noEmit`·백엔드 전체가 T002와 같은 결과다(바뀐 것은 T009의 승인 변경뿐).

---

## Phase 3: User Story 1 - 주식을 정해진 주기마다 사 모은다 (Priority: P1) 🎯 MVP

**Goal**: 주식 화면에서 적립식(주기·한 번 납입액·재투자)을 실행한다.
- 납입마다 정수 매수하고, 1주 미만이면 매수 대기금에 모은다.
- 원화 원금이면 납입마다 환전한다.
- 다섯 칸 보드·표·차트(누적 납입 원금)·이력을 보인다.

**Independent Test**: quickstart 3-1·3-2·3-3·4-1~4-3
- 국내 매달·1주가 비싼 종목 매주·미국 원화 매주의 표·보드가 손계산과 같다.
- 일시금 응답이 T001과 같다.

### Tests for User Story 1 ⚠️

- [X] T014 [P] [US1] `backend/tests/unit/test_recurring_stock.py` — `simulate_recurring_stock` (FR-006~FR-011, FR-014, SC-001~SC-004)
  - 머리 주석에 손계산을 적는다. 참조값:
    - 국내 매달 6개월(휴장 포함) — 행마다 매수 수·수수료·매수 대기금·총자산
    - 1주가 비싼 종목 매주 — 모이다 사는 날·이월
    - 재투자 켬 — 세후 배당은 배당락일에 배당 현금으로 들어오고, 재투자일(배당락일 뒤 둘째 거래일)에 매수 대기금으로 옮겨져 매수 대기금 전액으로 산다
    - **재투자 켬 + 매일 납입** — 배당락일 다음 거래일의 납입 매수는 그 배당을 쓰지 않는다(매수 대기금 = 납입분만). 재투자일에 그 거래일의 납입 매수가
      먼저이고, 남은 돈 + 옮겨 온 배당으로 `reinvest` 행이 다시 산다(분석 B1)
    - 재투자일이 계산 끝 뒤면 배당 현금으로 남는다
    - 재투자 끔 — 배당 현금이 쌓이고 그 뒤 납입 매수에 쓰이지 않는다
    - 분할 날 보유 수 조정 — 매수 대기금·배당 현금 불변
    - 배당락일 당일 납입 매수분에는 배당이 붙지 않는다
  - 행 종류·`month_first`는 그날 납입 행이 없을 때만 둔다. 같은 날 사건은 행이 따로다. 최신순이다.
  - 불변식 — 모든 매수 뒤 `pending < 1주 × 시가 × (1 + 수수료율)`, `pending ≥ 0`, `contributed` 끝값 = 납입액 × 넣은 예정일 수
- [X] T015 [P] [US1] `backend/tests/integration/test_stock_recurring_api.py` — `GET /api/stocks/recurring-simulation` (FR-002, FR-004, FR-005, FR-010~FR-014, FR-016, SC-002)
  - 준비는 `test_stock_sale_cost_api.py`와 같다(시드 시세·환율). 확인할 것:
  - 수집 판정
    - 미수집이면 202이고, 일시금 `collecting_body`와 같은 본문이다.
  - 오류
    - `frequency=hourly`·`amount=0`·`amount=abc` → 400 `invalid_query`
    - 막힌 통화 조합 → 400 `currency_pair_not_allowed`
    - 상장 전 시작일 → 409 `before_listing`
    - 환율 출처가 시작일보다 늦게 시작 → 409 `fx_not_available_before`(수집 전 판정 — 일시금과 같다)
    - 받아 둔 환율 안에서 어느 납입일 이전의 확정 환율이 없음 → 409 `fx_unavailable`(계산 중 — 분석 F1)
  - 200 응답의 모양
    - `condition`(`mode "recurring"`·`frequency`·`amount`)
    - `summary`(`contributed` = `contributions` × `amount`, `feeTotal` = `buyFeeTotal` + `saleCost.fee`, `taxTotal` = `dividendTaxTotal` + `saleCost.tax`,
      `profitAfterSale` = `profit` − `saleCost.total`, `returnRateAfterSale` = 그 값 ÷ `contributedKrw`, `pendingAfterEnd`)
  - 행
    - 행 키(`contribution`·`deferred`·`pending`·`dividendCash`·`contributed`·`contributedKrw`), 해외 원화 원금 납입 행의 `exchangeRate`·`exchangeRateDate`
  - 페이지
    - `before`·`limit`·`hasMore`
  - 해외 매도 세금
    - `saleCost`가 `capital_gains_tax`·`deduction "2500000"`이다.
    - 취득가는 매수마다 그 행의 매매기준율이다.
- [X] T016 [P] [US1] `backend/tests/integration/test_stock_recurring_series_api.py` — `/series` (FR-015, FR-016)
  - 점의 날짜 집합 = 표의 날짜 집합(날마다 하나 — 같은 날 여러 행이면 마지막 상태)
  - 점 `principal` = 그 날 표의 `contributedKrw`
  - `balance` = 원화 총자산
  - `price` = 010 수정 종가
  - `maxPoints` 다운샘플의 점마다 값이 원래 점과 같다
- [X] T017 [P] [US1] `frontend/tests/recurringText.test.ts` — `lib/recurringText.frequencyNote(frequency, start)` (FR-003, ui-wireframes §1)
  - 매일 "매일(거래일)", 매주 "매주 월요일", 매달 "매달 15일", 29~31일 "매달 31일(없는 달은 말일)", 매년 "매년 1월 15일" + 공통 "(휴장이면 다음 거래일)"
  - 날짜 계산이 없다(`Date` 산술 없이 문자열 분해 — `startDate.ts`와 같은 방식)
- [X] T018 [P] [US1] `frontend/tests/InvestmentModeFields.test.tsx` (FR-001, FR-002, SC-009, ui-wireframes §1)
  - "투자 방식" fieldset/legend, 라디오 둘(방향키 이동)
  - 적립식이면 주기 select(aria-label "납입 주기", 넷)와 안내 문장
  - 금액 칸 이름이 "투자 원금" ↔ "한 번 납입액"으로 바뀐다
  - 바꾸면 `onChange({mode, frequency})`
- [X] T019 [P] [US1] `frontend/tests/RecurringBoard.test.tsx` (FR-012, FR-020, SC-009, ui-wireframes §2)
  - 다섯 칸(`role="group" aria-label`)과 각 칸의 메모
    - 매수 ₩…(n회)·매도 ₩…
    - 배당 소득세 ₩…·매도 세금 ₩…
    - "매도 비용을 뺀 값"·"보유 중 ₩…"
  - 기준 줄
    - "매수 수수료·배당 소득세는 이미 총자산에서 빠져 있습니다"
    - 매수 대기금·배당 현금·보유·"다음 거래일에 들어갈 납입 n회"
  - 수익률 도움말(`aria-describedby`)
  - 외화 원금 "$… (₩…)"
  - 매도할 주식 없음
  - 가상자산 `not_yet_taxed`("₩0 · 가상자산 과세 시행 전") / `outside_rules`("—", "세법 미반영", 투자 수익·수익률 "—" + 보유 중 값)
- [X] T020 [P] [US1] `frontend/tests/RecurringStockTable.test.tsx` (FR-014, SC-010, ui-wireframes §3)
  - 열과 단위
  - 행 구분("＋" — 매수 0이면 회색, "◆", "⟳ 재투자")과 키 `${date}:${kind}`
  - `deferred` 표시("+2회(08-15·08-16)")
  - 배당 현금 열은 배당 행이 하나라도 있으면 있다. 재투자 켬이면 배당락일 ~ 재투자일 사이의 행에만 값이 있다(분석 B1)
  - 환율 칸 — 환전·평가
  - 끝없는 스크롤 센티널·상태 줄(기존 표와 같은 `useInfiniteScroll`)
- [X] T021 [P] [US1] `frontend/tests/simulationHistoryRecurring.test.ts` — `lib/simulationHistory` (FR-033, SC-006, data-model 3)
  - 적립식 항목의 선택 칸(`mode "recurring"`·`frequency`)과 식별자 `…|recurring:monthly`
  - 같은 조건의 일시금·적립식이 따로 항목
  - 일시금 항목의 식별자는 지금과 같다(기존 `simulationHistory.test.ts` 그대로)
  - 옛 항목(선택 칸 없음)을 읽으면 그대로다
- [X] T022 [P] [US1] `frontend/tests/stockStoreRecurring.test.ts` — `stores/stockStore` (FR-001, FR-016, FR-033, FR-034)
  - `plan` 기본 `{mode: "lump_sum", frequency: "monthly"}`
  - 적립식 `run()`은 `GET /api/stocks/recurring-simulation?market=…&symbol=…&start=…&amount=…&principalCurrency=…&frequency=…&reinvest=…`(정확한 문자열)
    → 결과가 `recurring`에 들어가고 일시금 칸은 빈다
  - 202 → 진행 감시(일시금과 같은 `watchProgress`·`watchFx`)
  - `loadMore`는 `&before=`
  - 방식·주기를 바꾸면 두 결과를 모두 비운다
  - 이력 저장에 `mode`·`frequency`
  - `rerunHistory`
    - 적립식 항목 → `plan`을 맞추고 적립식 경로
    - 옛 항목 → `plan.mode "lump_sum"`
    - `input`은 다섯 칸 그대로
  - `compareSelected`
    - 적립식 항목은 `/api/stocks/recurring-simulation/series`
    - `label`에 " · 적립식 매달"
  - **기존 `stockStoreRerun.test.ts`를 고치지 않는다**
- [X] T023 [US1] `frontend/tests/StocksPageRecurring.test.tsx` — 실행 주체 검사(006 D1) (FR-001, FR-012, FR-014, FR-015, FR-033)
  - 화면에서 "적립식" 라디오를 누르고, 주기를 고르고, 금액을 넣고, "시뮬레이션"을 누른다.
  - **적립식 경로**가 불린다(누르지 않으면 불리지 않는다).
  - 다섯 칸 보드·적립식 표가 보이고 일시금 보드(네 칸)는 없다.
  - 이력 행이 "적립식 · 매달 ₩500,000"이다.
  - 일시금으로 되돌리면 결과가 빈다.

### Implementation for User Story 1

- [X] T024 [US1] `backend/src/simulation/recurring_stock.py` — `RecurringCondition`(`reinvest_lag_days` 기본값 없음)·`RecurringRow`·`RecurringOutcome`·`simulate_recurring_stock` (FR-006~FR-011, FR-014)
  - research R11-4의 하루 순서·두 칸·행 규칙을 따른다. 재투자 켬의 배당은 재투자일까지 배당 현금에 두고, 재투자일에 그 배당 금액만 매수 대기금으로 옮긴다
    (배당마다 재투자일과 금액을 기억한다 — 분석 B1).
  - `money`의 `buy_quantity`·`spend_for`·`apply_split`·`quantize_rate`를 쓴다.
  - `reinvest.py`는 고치지 않는다.
- [X] T025 [US1] `backend/src/api/services/stock_recurring.py` (FR-002, FR-004, FR-005, FR-010~FR-013, FR-016)
  - `parse_frequency`(밖이면 `InvalidQuery` — "주기는 daily · weekly · monthly · yearly 중 하나여야 합니다")
  - `prepare_recurring`
    - 종목·설정·매도 세금 설정을 읽는다(`require_stock`·`check_principal_currency`·`get_settings`·`get_sale_tax`).
    - 시세를 `start`부터 읽고 `_require_start_month_bar`를 거친다.
    - 배당·분할을 읽는다. 환율은 `load_rates`(확정만)이고, 원화 원금이면 `cash_buy_spread`다.
    - `scheduled_dates`(매일이면 거래일) → `assign` → `fund` → `simulate_recurring_stock`
  - 행마다 원화 평가 — `evaluate_krw(balance, pending + dividend_cash, 그 행 매매기준율, 그 행의 basis_krw)`
  - 요약
    - 매수 수수료 합·배당 소득세 합을 행 매매기준율로 원화로 바꾼다.
    - 매도 비용은 `stock_sale_cost` + 설정이다. 해외 취득가는 매수마다 행 환율이다.
    - `feeTotal`·`taxTotal`·`profitAfterSale`·`returnRateAfterSale`
  - `page`(커서)
  - 계산 결과를 저장하지 않는다.
- [X] T026 [US1] 라우트 — `backend/src/api/routes/stock_recurring.py`(`GET /api/stocks/recurring-simulation`·`/recurring-simulation/series`)·`backend/src/api/services/recurring_series.py`·`backend/src/api/main.py`(라우터 등록) (FR-015, FR-016, contracts/rest-api §1)
  - 검증·판정 순서는 일시금 라우트와 같다 — `check_principal_currency`(형식) → `require_stock` → 조합 → `require_start_available` → `collecting_body` → `prepare_recurring`.
  - `recurring_series.py`
    - 날마다 마지막 상태 하나, 점 `principal`·`price`(010 `split_restated_close`)
    - LTTB 다운샘플
    - 결측 구간은 일시금과 같은 `compute_gaps`
  - 행 JSON — 해당 없는 키는 두지 않는다.
- [X] T027 [P] [US1] 화면 부품
  - `frontend/src/lib/recurringText.ts`(`frequencyNote`)
  - `frontend/src/components/recurring/InvestmentModeFields.tsx`
  - `frontend/src/components/recurring/RecurringBoard.tsx`(주식·가상자산 공유 — `asset: "stock" | "crypto"`)
  - `frontend/src/components/recurring/RecurringStockTable.tsx`
  - 서식 함수는 지금 것(`formatMoney`·`formatMoneyWithSymbol`·`formatRate`·`formatPercent`·`formatPrice`)을 쓴다.
  - ui-wireframes §1~§3 (FR-001~FR-003, FR-012, FR-014, SC-009, SC-010)
- [X] T028 [US1] 이력과 스토어 (FR-001, FR-033, FR-034)
  - `frontend/src/lib/simulationHistory.ts` — 선택 칸·식별자
  - `frontend/src/stores/stockStore.ts`
    - `plan`·`setPlan`(결과 비움)·`recurring`
    - `run()`의 적립식 갈래(`toRecurringQuery`)·`loadMore`
    - `rerunHistory`(빠진 칸 기본값)·`compareSelected`(적립식 경로·`label`)
  - `frontend/src/components/stock/SimulationHistory.tsx` — 적립식 행 표기
  - 일시금 갈래의 조회 문자열·`input`은 바꾸지 않는다.
- [X] T029 [US1] `frontend/src/app/stocks/page.tsx` — `InvestmentModeFields`를 `SimulationForm` 위에 둔다 (FR-001, FR-012, FR-014, FR-015)
  - 금액 칸 이름은 `SimulationForm`의 선택 속성 `principalLabel`로 넘긴다. 기본은 지금 문구다 — 기존 폼 테스트 그대로.
  - `recurring`이 있으면 `RecurringBoard`·`RecurringStockTable`을, 없으면 지금 부품을 그린다.
  - 차트는 같은 `PerformanceChart`다.
  - 부제목은 일시금 그대로다. 적립식이면 "정해진 주기로 사 모은 투자 성과"다.
- [X] T030 [US1] quickstart 3-1·3-2·3-3·4-1~4-3을 실행하고 `specs/011-recurring-investment-installment-savings/quickstart.md` 실행 기록에 더한다 (SC-001, SC-002, SC-003, SC-006, SC-010)
  - 손계산과 다른 값 0건
  - 일시금 응답 대조(T001)
  - 1440px 표 고유 폭 — 넘으면 "시작가·종가"를 한 칸으로 접고 다시 잰다
  - 화면 캡처

**Checkpoint**: 주식 적립식이 끝에서 끝까지 동작하고, 일시금은 T001과 같다. MVP다.

---

## Phase 4: User Story 2 - 가상자산을 정해진 주기마다 사 모은다 (Priority: P2)

**Goal**: 가상자산 화면에서 적립식(주기·한 번 납입액)을 실행한다.
- 납입마다 소수 8자리로 사고, 출처 결측일의 납입은 다음 일봉으로 미룬다.
- 보드는 과세 시행 전 세금 0이다.

**Independent Test**: quickstart 3-4·4-4 — 코인 매일 원화 1년의 표·보드가 손계산과 같다. 결측일 납입이 다음 날로 간다.

### Tests for User Story 2 ⚠️

- [X] T031 [P] [US2] `backend/tests/unit/test_recurring_crypto.py` — `simulate_recurring_crypto` (FR-017~FR-019, SC-001, SC-002)
  - 매일 원화(환전 납입마다), 출처 결측 이틀 → 다음 일봉에 합침
  - 수량은 `buy_fraction`(소수 8자리 버림, 수수료 포함), 남은 돈 이월
  - 잔고 = 보유 × 그날 시가
  - 행 = 납입 행 + 그 달 첫 일봉 행(그날 납입이 없을 때만, `first_day_missing`)
  - `daily`는 일봉마다
  - 손계산을 머리 주석에 적는다
- [X] T032 [P] [US2] `backend/tests/unit/test_crypto_sale_cost.py` — `crypto_sale_cost(sale_krw, fee_rate=…, day=…)` (FR-020)
  - 수수료 = floor(평가액 × 수수료율)
  - 2026-12-31 → `tax 0`·`not_yet_taxed`
  - 2027-01-01 → `tax None`·`total None`·`outside_rules`
- [X] T033 [US2] **기존 테스트 변경 승인을 받는다**(A3 — research R11-7) (FR-020)
  - **2026-10-06 승인**(A1·A2와 함께 — Phase 2 기록). 바꾸기는 T037에서 한다.
  - 바꿀 것: `backend/tests/unit/test_no_hardcoded_dates.py`의 `_LEGAL_DATE_MODULES`에서 `simulation/stock_sale_cost.py`(T011 뒤 날짜가 없다)를 빼고
    `simulation/crypto_sale_cost.py`를 더한다.
  - 주석에 "011 — 가상자산 과세 시행일(법령), 출처의 시작일이 아니다"를 적는다.
  - 사용자에게 보이고 승인을 받은 뒤 바꾼다. 승인 전에는 T037을 시작하지 않는다.
- [X] T034 [P] [US2] `backend/tests/integration/test_crypto_recurring_api.py` — `GET /api/crypto/recurring-simulation` (FR-002, FR-017~FR-021, SC-002)
  - 준비는 `crypto_support.seed_daily`·`seed_usd`다.
  - 202(일시금과 같은 `collecting_body`)
  - 400 `invalid_query`·`currency_pair_not_allowed`, 409 `before_listing`·`fx_not_available_before`(수집 전)·`fx_unavailable`(계산 중 — 분석 F1)
  - 200 — `summary`(`contributed`·`heldQuantity`·`pending`·`buyFeeTotal`·`saleCost` `not_yet_taxed`·`feeTotal`·`taxTotal "0"`·`profitAfterSale`)
  - 결측일 납입 행의 `deferred`
  - `boughtQuantity` `.8f`
  - `before`·`limit` 페이지
  - 2027-01-01 이후 기준일 → `outside_rules`·`taxTotal null`·`profitAfterSale null`. 계산 끝이 min(`end`, UTC 어제)이므로 시드의 끝만 늦춰서는 만들 수
    없다 — `monkeypatch.setattr("src.api.routes.crypto_simulation.utc_yesterday", lambda: D("2027-01-05"))`로 시계를 바꾸고 2027-01-04까지의 일봉·
    커버리지·환율을 시드한다(분석 C1)
- [X] T035 [P] [US2] `backend/tests/integration/test_crypto_recurring_series_api.py` — `/series` (FR-019)
  - 점은 일봉마다이고 `principal`이 있다.
  - 출처 결측 구간은 `gaps` `source_missing`(일시금과 같은 판정)
  - `price` = 시가
- [X] T036 [P] [US2] 화면 테스트 (FR-017, FR-019, FR-020, FR-033, FR-034)
  - `frontend/tests/RecurringCryptoTable.test.tsx` — 열·수량 `formatQuantity`·"◇ 1일 결측"·`deferred`·스크롤
  - `frontend/tests/cryptoHistoryRecurring.test.ts` — 선택 칸·식별자·옛 항목
  - `frontend/tests/cryptoStoreRecurring.test.ts`
    - 적립식 `run()`은 `GET /api/crypto/recurring-simulation?coinId=…&start=…&amount=…&principalCurrency=…&frequency=…`
    - 결과는 `recurring`
    - 방식 전환 비움, `loadMore`, 다시 실행·비교 `label`
  - `frontend/tests/CryptoPageRecurring.test.tsx` — 실행 주체(006 D1): "적립식"을 눌러 실행하면 적립식 경로·다섯 칸 보드("가상자산 과세 시행 전")
    - 기존 `CryptoPage.test.tsx`의 "배당 재투자 없음" 검사 그대로
  - **US1 결함 함께 고침(단언은 그대로)**: `StocksPageRecurring.test.tsx`가 실제 차트 라이브러리를 jsdom에서 그려(`matchMedia` 없음) 처리되지 않은
    오류로 vitest가 종료 코드 1을 냈다. "누르지 않으면" 검사는 시계열 요청에도 일시금 본문을 줘 차트가 `points`를 읽다 오류를 냈다. 차트 모의와
    시계열 응답만 더했다. T030의 "1,230 통과"는 이 종료 코드를 놓친 기록이다.

### Implementation for User Story 2

- [X] T037 [US2] `backend/src/simulation/recurring_crypto.py`(R11-6)·`backend/src/simulation/crypto_sale_cost.py`(R11-7 — 시행일 상수 하나, 2027 세법은 계산하지 않음) (FR-017~FR-020)
  - T033 승인 뒤 `backend/tests/unit/test_no_hardcoded_dates.py` 허용 목록을 바꾼다.
  - 바꿨다(2026-10-06 승인 — `stock_sale_cost.py`를 빼고 `crypto_sale_cost.py`를 더함).
  - 그 달 첫 일봉이 납입 행이어도 1일 결측(`first_day_missing`)을 싣는다 — 007의 "그 달의 행이 1일이 아니다"와 같은 뜻(T031이 고정).
- [X] T038 [US2] 서비스·라우트 (FR-002, FR-017~FR-021, contracts/rest-api §2)
  - `backend/src/api/services/crypto_recurring.py`
    - 일시금 `crypto_simulation`의 검증 함수·`require_start_available`·`collecting_body`·`load_rates`를 함께 쓴다.
    - 일봉을 `start.replace(day=1)`부터 읽는다. 시작 월 일봉 판정은 일시금과 같다.
    - 예정일은 달력일 → `assign`(일봉 날짜) → `fund` → 계산
    - 원화 평가는 행마다 분모, 매도 비용은 `crypto_sale_cost(기준일 = UTC 어제 이하 마지막 일봉)`
  - `backend/src/api/routes/crypto_recurring.py`(`GET /api/crypto/recurring-simulation`·`/series`) — 계산 끝은 일시금 라우트의 `calculation_end`를
    가져와 쓴다(같은 규칙, 그리고 T034가 그 모듈의 `utc_yesterday`를 바꿔 시계를 정한다)
  - `recurring_series.py`에 가상자산 조립(일봉마다)
  - `main.py` 등록
- [X] T039 [US2] 화면 (FR-017, FR-019, FR-020, FR-033, FR-034)
  - `frontend/src/components/recurring/RecurringCryptoTable.tsx`
  - `frontend/src/lib/cryptoHistory.ts`
  - `frontend/src/stores/cryptoStore.ts`(`plan`·`recurring`·`run` 갈래·`loadMore`·`rerunHistory`·`compareSelected`)
  - `frontend/src/components/crypto/CryptoHistory.tsx`(행 표기)
  - `frontend/src/app/crypto/page.tsx`(`InvestmentModeFields`·`RecurringBoard asset="crypto"`)
  - quickstart 3-4·4-4를 실행해 기록한다.

**Checkpoint**: 가상자산 적립식이 동작하고, 일시금 가상자산은 T001과 같다.

---

## Phase 5: User Story 3 - 적금으로 모아 정기예금으로 굴린다 (Priority: P2)

**Goal**: 예금 화면에서 정기 적금(시중은행·상호금융)을 실행한다.
- 매달 붓는 1년 적금이 만기되면 정기예금에 넣고 새 적금을 붓는다.
- 1년 뒤에는 두 만기 금액을 합쳐 다시 정기예금에 넣는다.
- 저축은행·신협·새마을금고는 사유와 함께 막는다.

**Independent Test**: quickstart 3-5·3-6·4-5
- 시중은행·2015-01-15·월 1,000,000원의 세 주기가 손계산과 같다.
- 정기예금 원금 = 앞 정기예금 만기 금액 + 적금 만기 금액이다.

### Tests for User Story 3 ⚠️

- [X] T040 [P] [US3] `backend/tests/contract/test_ecos_installment_items.py` — `ingestion/ecos/installment_items` (FR-029, research R11-1·R11-2)
  - `resolve_installment_items(items_121Y002 본문, "121Y002")` → `{"commercial_bank_isav": 항목 BEABAA2122 "정기적금(1-2년)", 시작 2003-01}`
  - `121Y004` → `{"mutual_finance_isav": BEBB0200 "정기적금", 2012-01}`
  - 알려진 코드가 바뀌면 이름 패턴으로 다시 찾는다. `정기적금(3년만기)`·`정기적금(3-4년)`·`정기적금`(예금은행 전체)은 걸리지 않는다.
  - 못 찾으면 `ItemMappingChanged`
  - T003 픽스처를 008 `parse_monthly`로 읽어 행 수·첫 달·마지막 달을 확인한다.
  - **기존 `Test투자처_항목`은 고치지 않는다**(`resolve_deposit_items` 결과 그대로)
- [X] T041 [P] [US3] `backend/tests/unit/test_installment_ladder.py` — `simulate_installment_ladder` (FR-024~FR-028, FR-030, SC-001, SC-005)
  - 머리 주석에 손계산을 적는다. 참조값:
    - 세 주기(시중은행 실측 금리 일부를 상수로)
    - 회차 이자 Σ(12 − i)·만기 이자 trunc 한 번(12회 = 78/1200)·세금 trunc
    - 만기 금액 → 그날 정기예금 원금, 같은 날 새 적금 첫 회
    - 둘째 만기 원금 = 정기예금 만기 금액 + 적금 만기 금액
  - 날짜
    - 31일 시작(말일 규칙)
    - 2-29 시작(평년 2-28)
  - 평가
    - 매달 1일 행의 경과 평가 식(R11-8 — 경과 이자 합을 한 번 버린 뒤 세금)
    - 만기일 평가 = 만기 금액 합
    - 노는 돈 0
  - 잠정
    - 새 가입 달 미발표 → 그 계약부터 잠정(`provisional_from`)
  - 오류·멈춤
    - 둘째 적금 가입 달 결측 → 그날 멈춤(`Stopped`)
    - 첫 가입 결측 → `RateMissing`
    - 시작 < max(적금 첫 달, 정기예금 첫 달 − 1년) → `BeforeFirstMonth(startable_from)`
  - 계산 끝 이후 회차는 내지 않는다.
  - 같은 날 행 순서
- [X] T042 [P] [US3] `backend/tests/integration/test_deposit_installment_collection.py` (FR-030)
  - 008 실행기(`collect_institution`)가 계열 키 `commercial_bank_isav`로 적금 시계열을 받아 `deposit_rate`·`deposit_coverage`에 저장한다.
  - 원본(`deposit_raw_response`)은 본문만이다.
  - 다시 확인·겹쳐 받기·수정 사건(`deposit_rate_revised`)이 계열마다 성립한다.
  - 정기예금 키 `commercial_bank`의 저장은 그대로다.
  - `tests/integration/deposit_support.py`의 `SERIES`·스텁에 두 계열을 **더한다**(기존 값 그대로).
- [X] T043 [P] [US3] `backend/tests/integration/test_deposit_installment_api.py` — `GET /api/deposit/installment-simulation` (FR-022~FR-031, SC-005)
  - 오류
    - `savings_bank` → 400 `installment_not_available`(`allowed`)
    - 모르는 키 → 400 `unknown_institution`
    - `amount` 형식 → 400
  - 수집 판정
    - 두 계열 모두 미수집 → 202 `series "installment"`(두 작업이 큐에 걸림) → 끝난 뒤 다시 202 `series "deposit"` 또는 200
    - 받아 둔 뒤 시작이 이르면 409 `before_first_month` `startableFrom` = max(적금 첫 달, 정기예금 첫 달 − 1년)
    - 첫 가입 결측 → 409 `rate_missing`
  - 200
    - `contracts[0].amount` = `deposits[0].fromInstallment`
    - `deposits[1].principal` = 앞 정기예금 만기 금액 + `contracts[1].amount`
    - `summary.contributed` = 낸 회차 × 월 납입액
    - `installmentValue` + `depositValue` = `balance`
    - 확인 실패 `recheckFailed`
    - 계열 키가 응답 어디에도 없다
- [X] T044 [P] [US3] `backend/tests/integration/test_deposit_installment_series_api.py`·`test_deposit_institutions_installment.py` (FR-029, FR-032)
  - 시계열
    - `priceKind "installment_rate"`, `price` = 그 달 적금 금리(`unpublished`·`missing`), `depositRate`, `principal`
    - 점 날짜 = 표 날짜
  - 투자처 목록
    - 투자처마다 `installment` — 시중은행·상호금융 `available true`(받기 전 null 칸, 받은 뒤 `startableFrom`), 나머지 셋 `available false`·`reason`
    - 기존 키·다섯 투자처 순서 그대로
- [X] T045 [P] [US3] 화면 테스트 (FR-022, FR-023, FR-029, FR-031~FR-034, SC-009)
  - `frontend/tests/ProductPicker.test.tsx` — "상품" fieldset, 라디오 둘
  - `frontend/tests/InstitutionPickerInstallment.test.tsx` — 적금이면 셋 `disabled` + 사유(`aria-describedby`), 시작 가능 날짜 안내
  - `frontend/tests/InstallmentBoard.test.tsx` — 여섯 칸·구성 메모·기준 줄(지금 적금·지금 예금)
  - `frontend/tests/InstallmentTable.test.tsx` — 열·구분·잠정 표기·가입 행의 구성 `title`
  - `frontend/tests/depositHistoryInstallment.test.ts` — `product`·식별자 `|installment`·옛 항목
  - `frontend/tests/depositStoreInstallment.test.ts`
    - 적금 `run()`은 `GET /api/deposit/installment-simulation?institution=…&start=…&amount=…`
    - 202 `series` 진행 감시 → 끝나면 다시 실행(두 번째 202도)
    - 상품 전환 비움, 고를 수 없는 투자처면 시중은행으로 바꾸고 알림
    - 다시 실행·비교 `label` " · 정기 적금"
  - `frontend/tests/DepositPageInstallment.test.tsx` — 실행 주체(006 D1): "정기 적금"을 눌러 실행하면 적금 경로·여섯 칸 보드·적금 부제목
    - 정기예금 부제목 검사(`DepositPage.test.tsx`)는 그대로
  - **기존 테스트 변경(사용자 승인 2026-10-06)**: `DepositPage.test.tsx`의 "투자처는 라디오 다섯" 검사가 화면 전체의 라디오를 셌다 — 상품 라디오 둘이
    더해지면 깨진다. 조회를 "투자처" 묶음 안(`within(group)`)으로 좁혔다. 기대값(다섯·순서·기본 시중은행)은 그대로다.
  - 보드의 세후 이자 구성(적금 · 예금)은 서버가 나눠 준다(`summary.installmentAfterTax`·`depositAfterTax`) — 화면이 계약을 더하지 않는다(contracts §3에 더한다).

### Implementation for User Story 3

- [X] T046 [US3] 수집 (FR-029, FR-030)
  - `backend/src/ingestion/ecos/installment_items.py`(`INSTALLMENT_SERIES` — 키·통계표·알려진 코드·이름 패턴 `^정기적금\(1-2년\)$`·`^정기적금$`, `resolve_installment_items`)
  - `backend/src/ingestion/ecos/deposit_client.py`(`items_for(key)`가 계열 키를 안다 — 통계표 항목 캐시 공유, 기존 투자처 해석 불변)
  - 실행기·큐·저장소는 고치지 않는다.
  - 항목 목록 응답 읽기를 `deposit_items.monthly_items`·`pick_item`으로 꺼내 008 투자처와 함께 쓴다(동작 그대로 — 008 계약 테스트 통과).
  - 클라이언트는 적금 항목을 처음 필요할 때 받아 둔 본문에서 찾는다 — 항목 목록을 받을 때 함께 찾으면 적금 항목의 변경이 정기예금 수집까지 멈춘다.
- [X] T047 [US3] `backend/src/simulation/installment_ladder.py`(R11-8) (FR-024~FR-028, FR-030)
  - `backend/src/simulation/deposit_rollover.py`에서는 금리 해석기를 공개 이름으로 꺼내는 것만 한다(`_rate_resolver` → 공개 별칭, 동작·기존 테스트 불변).
  - `add_one_year`·`maturity_interest`·`accrued_interest`·`interest_tax`를 함께 쓴다.
  - 회차일은 `contribution_schedule.months_later`(011 — `_add_months`를 공개 이름으로 바꿈, 같은 말일 규칙)다.
- [X] T048 [US3] 서비스·라우트 (FR-022~FR-032, contracts/rest-api §3·§4)
  - `backend/src/api/services/deposit_installment.py`
    - (투자처, 상품) → 계열 키
    - 고를 수 있는 투자처와 설명 — 시중은행 "예금은행 정기적금(1~2년 만기) 평균", 상호금융 "상호금융 정기적금 평균 — 만기 구분 없음"
    - 두 계열 `judge`(R11-9 — 적금 먼저 202, 둘 다 수집 요청, `BeforeFirstMonth`를 적금 시작 가능 날짜로 바꿔 낸다)
    - `prepare`(두 계열 금리·커버리지·세율 → `simulate_installment_ladder`)
  - `backend/src/api/routes/deposit_installment.py`(`GET /api/deposit/installment-simulation`·`/series`)
  - `recurring_series.py`의 적금 조립(점 `principal`·`price` 적금 금리·`depositRate`)
  - `backend/src/api/routes/deposit_institutions.py`(`installment` 객체)
  - `backend/src/api/errors.py`·`main.py`(`InstallmentNotAvailable` 400 처리기, 라우터 등록)
- [X] T049 [US3] 화면 (FR-022, FR-023, FR-029, FR-031~FR-034)
  - `frontend/src/components/deposit/ProductPicker.tsx`
  - `frontend/src/components/deposit/InstitutionPicker.tsx`(선택 속성 `product` — 적금이면 비활성·사유, 기본은 지금 동작)
  - `frontend/src/components/deposit/InstallmentBoard.tsx`·`InstallmentTable.tsx`
  - `frontend/src/lib/depositHistory.ts`
  - `frontend/src/stores/depositStore.ts`(`product`·`installment`·`run` 갈래·`series` 202 감시·다시 실행·비교)
  - `frontend/src/components/deposit/DepositHistory.tsx`(행 표기)
  - `frontend/src/components/deposit/DepositSimulationForm.tsx`(선택 속성 `principalLabel` "월 납입액" — 기본 지금 문구)
  - `frontend/src/app/deposit/page.tsx`(상품 라디오·부제목·적금 부품·`DepositNotice` 재사용)
- [X] T050 [US3] quickstart 3-5·3-6·4-5를 실행하고 기록한다 (SC-001, SC-005, SC-006)
  - 개발 DB에 적금 계열을 실제로 받는다(진행 표시·수집 시간).
  - 손계산 대조, 정기예금 일시금이 T001과 같은지

**Checkpoint**: 적금이 동작하고 정기예금은 T001과 같다.

---

## Phase 6: User Story 4 - 주식 매도 세금을 설정에서 정한다 (Priority: P3)

**Goal**: 설정 화면에서 국내 매도 세율·해외 양도소득세율·해외 기본공제를 보고 바꾸고 기본값으로 되돌린다. 일시금·적립식 주식 보드가 그 값을 쓴다.

**Independent Test**: quickstart 3-7·4-7 — 해외 공제를 0으로 바꾸면 미국 종목의 매도 세금이 차익 × 22%가 되고, 되돌리면 T001과 같다.

### Tests for User Story 4 ⚠️

- [X] T051 [P] [US4] `backend/tests/integration/test_stock_sale_tax_settings_api.py` — `GET/PUT /api/stocks/settings/sale-tax` (FR-035~FR-038, SC-007)
  - GET 기본값
    - `"0.0020"`·`"0.22"`·`"2500000"`·`isDefault true`·`defaults`
  - PUT
    - 세 키 모두 필요 — 빠지면 422
    - 422 `invalid_setting`: `"-0.1"`·`"1"`·`"abc"`·`null`·소수 7자리·공제 `"100.5"`·`"-1"`·16자리 — 값 그대로
    - 저장 → 6자리 문자열·`isDefault false`
  - 반영
    - 저장한 국내 0.0015 → 일시금 `/api/stocks/simulation`의 `saleCost.taxRate "0.001500"`·세금 = floor(매도금액 × 0.0015)
    - 적립식 보드도 같다
    - 해외 공제 0 → 세금 = floor(차익 × 0.22)
    - 표·`profit`(보유 중)은 그대로
  - 기본값을 보내면 응답이 T001과 같다
  - 기존 `GET/PUT /api/stocks/settings`는 그대로
- [X] T052 [P] [US4] 화면 테스트 (FR-035~FR-037, SC-007, ui-wireframes §2a·§9)
  - `frontend/tests/StockSaleTaxForm.test.tsx`
    - 세 칸·기본값과 근거
    - 퍼센트 ↔ 비율 문자열 변환 — `"0.0020"` ↔ `"0.2"`, `"0.22"` ↔ `"22"`
    - 검증 문구(`role="alert"`)·저장하지 않음
    - "기본값으로"는 `defaults`를 보낸다
    - "기본값"/"변경됨"
  - `frontend/tests/SettingsSaleTax.test.tsx` — 설정 화면에 섹션이 있고 `GET/PUT /api/stocks/settings/sale-tax`를 부르며 저장 뒤 다시 그린다
  - `frontend/tests/PerformanceBoardSaleTaxNote.test.tsx` — 일시금 보드의 매도 칸 메모 끝에 "세율·공제: 설정값(설정 > 주식 매도 세금)"
    - 기존 `PerformanceBoardSaleCost.test.tsx`는 그대로 통과한다

### Implementation for User Story 4

- [X] T053 [US4] `backend/src/api/routes/stock_settings.py` — `GET/PUT /api/stocks/settings/sale-tax` (FR-035, FR-036, contracts/rest-api §5)
  - 검증: 세율은 0 ≤ x < 1·소수 6자리 이하, 공제는 정수·0 이상·15자리 이하. 빠진 키를 기본값으로 채우지 않는다.
  - `save_sale_tax`(T011) → `session.commit()` → 다시 읽어 돌려준다.
  - 저장소 `get_sale_tax`는 기본값과 같은 저장값을 기본값 상수로 돌려준다 — 되돌린 뒤의 응답 문자열이 처음과 같다(SC-007).
- [X] T054 [US4] 화면 (FR-035~FR-037)
  - `frontend/src/components/settings/StockSaleTaxForm.tsx` — `CryptoSettingsForm`의 문자열 `toPercent`·`toRate`, 공제는 `normalizePrincipal`·`formatPrincipal`
  - `frontend/src/app/settings/page.tsx` — `StockSaleTaxSection`, `key`로 다시 그림
  - `frontend/src/components/stock/PerformanceBoard.tsx` — 매도 칸 메모 끝 한 줄. 기존 문장은 글자 그대로 둔다.
  - `RecurringBoard`의 세금 메모에 "(설정)"
  - quickstart 3-7·4-7을 실행하고 기록한다.

**Checkpoint**: 설정을 바꾸면 다음 실행의 매도 세금이 바뀌고, 되돌리면 같다.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T055 이력·비교의 섞인 경우를 확인한다 (FR-033, FR-034, SC-006)
  - 주식·가상자산·예금 각각 일시금·적립식(적금) 항목을 함께 골라 비교한다. 범례가 방식을 구별하고 기준이 원화 수익률이다.
  - `localStorage`에 011 전 형식 항목을 넣고 다시 실행한다.
  - quickstart 4-6
- [ ] T056 성능을 잰다 (SC-008, research R11-14)
  - 매일 적립 20년(국내 종목 `start=2006-10-02&frequency=daily`)을 받아 둔 뒤 표 첫 쪽·다음 쪽·`/series` 응답 시간을 잰다.
  - 3초 넘으면 멈추고 보고한다(행마다 환율 조회·페이지마다 재계산을 먼저 본다).
  - quickstart 3-8에 기록한다.
- [ ] T057 입력 시간과 접근성을 확인한다 (SC-009)
  - 처음 쓰는 사람 기준으로 적립식·적금 조건 입력 1분을 잰다.
  - 라디오 방향키·`aria` 연결, 비활성 투자처의 사유 읽기
  - quickstart 4-8
- [ ] T058 문서를 갱신한다
  - `CLAUDE.md` "현재 상태" 표에 011 한 줄
  - 주의 문단 — 적금 계열 키 `{inst}_isav`, 적금은 시중은행·상호금융만, 매도 세금 설정 경로·기본값 문자열, 적립식 경로는 일시금과 따로, 가상자산 과세 시행일 모듈
  - `README.md` 기능 설명
  - `spec.md` Status
- [ ] T059 품질 게이트를 돌린다(서버를 내린 채) — 백엔드 `pytest -q --cov=src`(커버리지 80% 이상)·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .` (헌법 품질 게이트, SC-006)
  - 통과 수를 Notes에 적는다.
  - 이 기능 전 커밋과 견주어 바뀐 기존 테스트 파일이 승인한 셋(A1~A3)과 `deposit_support.py`(더하기만)뿐인지 `git diff --stat`으로 확인한다.
- [ ] T060 불변 대조 (FR-039, SC-006)
  - 서버를 띄우고 T001의 응답(일시금 주식·가상자산·정기예금, 부동산, 외환)을 다시 받아 비교한다.
  - 다른 키·값이 있으면 멈추고 보고한다. 주식 `saleCost`도 기본 설정이면 같아야 한다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작한다. **T001·T002는 다른 모든 코드 변경보다 먼저다.**
- **Foundational (Phase 2)**: T002 뒤. **T008(승인)이 T009를 막는다.** T010·T011은 각자의 테스트(T004·T005·T009) 뒤다.
- **US1 (Phase 3)**: Foundational 뒤. MVP다.
- **US2 (Phase 4)**: Foundational 뒤. `RecurringBoard`(T027)·`InvestmentModeFields`(T027)·`recurring_series.py`(T026)를 쓰므로 US1 뒤가 자연스럽다.
  **T033(승인)이 T037을 막는다.**
- **US3 (Phase 5)**: 백엔드 T040~T047은 T003 뒤면 언제든 할 수 있다(Foundational과 무관). T048은 `recurring_series.py`·`main.py`·`errors.py`를 US1과
  함께 만지므로 T026 뒤다(분석 F3). 화면(T045·T049)은 T012·T013 뒤다.
- **US4 (Phase 6)**: T011 뒤. 화면은 T027(`RecurringBoard`) 뒤다.
- **Polish (Phase 7)**: 모든 스토리 뒤

### Within Each Phase

- 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 백엔드는 순수 계산 → 서비스 → 라우트, 화면은 순수 함수 → 부품 → 스토어 → 화면 순서다.

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/services/recurring_series.py` | T026, T038, T048 |
| `backend/src/api/main.py`·`backend/src/api/errors.py` | T026, T038, T048 |
| `backend/src/api/services/stock_simulation.py`·`stock_sale.py`·`routes/stock_simulation.py` | T011 |
| `backend/src/repository/stock_setting.py` | T011, T053(읽기만) |
| `backend/tests/unit/test_no_hardcoded_dates.py` | T037(승인 T033 뒤) |
| `backend/tests/integration/deposit_support.py`(더하기만) | T042, T043, T044 |
| `frontend/src/lib/types.ts` | T012 |
| `frontend/src/components/stock/PerformanceChart.tsx`·`lib/chartHover.ts`·`lib/chartSeries.ts` | T013 |
| `frontend/src/components/recurring/RecurringBoard.tsx` | T027, T054 |
| `frontend/src/components/stock/PerformanceBoard.tsx` | T054 |
| `frontend/src/stores/stockStore.ts`·`lib/simulationHistory.ts` | T028 |
| `frontend/src/app/settings/page.tsx` | T054 |
| `specs/011-…/quickstart.md`(실행 기록) | T011, T030, T039, T050, T054, T055, T056, T057 |

### Parallel Opportunities

- Foundational 테스트 T004~T007은 다른 파일이라 함께 쓴다(T009는 T008 승인 뒤).
- US1 테스트 T014~T022는 함께 쓴다. T023은 부품 테스트와 같은 화면을 보므로 뒤에 둔다.
- US3 백엔드(T040~T044·T046~T048)는 US1·US2 작업과 나란히 할 수 있다. 겹치는 파일은 위 표를 본다.
- US2·US3·US4 화면 테스트는 서로 다른 파일이다.

---

## Parallel Example: Phase 3 (US1 테스트)

```text
Task: "T014 test_recurring_stock.py — 참조값·두 칸·불변식"
Task: "T015 test_stock_recurring_api.py — 202·오류·요약 산식·행 키·해외 환전"
Task: "T016 test_stock_recurring_series_api.py — 점 날짜 = 표 날짜·principal"
Task: "T017 recurringText.test.ts — 주기 안내 문장"
Task: "T018 InvestmentModeFields.test.tsx — 라디오·주기·금액 칸 이름"
Task: "T019 RecurringBoard.test.tsx — 다섯 칸·메모·가상자산 세금 갈래"
Task: "T020 RecurringStockTable.test.tsx — 열·구분·미뤄짐·스크롤"
Task: "T021 simulationHistoryRecurring.test.ts — 선택 칸·식별자·옛 항목"
Task: "T022 stockStoreRecurring.test.ts — 경로·plan·비움·다시 실행·비교"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1(기준 응답·기준 게이트·적금 픽스처) → Phase 2(일정·환전, 매도 세금 기반 — 승인 A1·A2, 형식, 차트 선)
2. Phase 3 (US1) — **멈추고 검증**(T030): 주식 적립식이 손계산과 같고, 일시금이 T001과 같다.

### Incremental Delivery

1. MVP(US1) — 주식 적립식
2. US2 — 가상자산 적립식(승인 A3)
3. US3 — 정기 적금 → 정기예금 사다리
4. US4 — 매도 세금 설정 화면
5. Polish — 섞인 이력·성능·입력 시간·문서·게이트·불변 대조

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(011): <페이즈>`
     - 그 페이즈의 테스트만 담고 **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는 예정된 것이다.
     - 승인된 기존 테스트 변경(T009·T037의 허용 목록)은 이 커밋에서 하고 승인 날짜를 적는다.
  2. **구현 커밋** — `feat(011): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다.
  - 테스트가 없는 태스크만 있는 페이즈(기준 기록, 형식, 브라우저 확인, 문서)는 한 번 커밋한다.
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다.** 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2).
- 설계 중 spec이 바뀌면(FR·SC) plan의 추적성 표와 이 파일의 참조를 같은 작업 단위에서 고친다(헌법 명세 작성 규약).
- 커밋 전에 비밀 검사 스크립트를 돌린다. `.env`가 추적되지 않는지, 스테이징된 내용에 키·DB 비밀번호가 없는지, `.venv/`·`node_modules/`·`.next/`·`logs/`
  경로가 없는지 본다.
- **2026-10-06 T001 기준 응답**: 저장소 밖 작업 폴더(`011-baseline/before/`)에 일시금 표(모든 쪽)·시계열을 저장했다(`end=2026-09-30` 고정 — 날짜가 지나도
  같은 입력). 주식 KRX 005930.KS(표 126행·점 107), AAPL(112·112), 가상자산 BTC(81·2,000 — 줄인 점), 예금 시중은행 2015-01-15(163·153), 부동산 헬리오시티
  30평대(68·69 — 종료일 입력이 없어 계산 끝이 오늘), 외환 USD 2025-09-30~2026-09-30(243점). 05:31Z
- **2026-10-06 T002 기준 게이트**: 백엔드 2,458 passed(커버리지 96.04%), mypy 207 파일·ruff(`--no-cache`) 통과 / 프론트엔드 132 파일·1,172 passed,
  tsc·eslint 통과
- **2026-10-06 T003**: ECOS 적금 두 시계열 본문을 받았다 — 시중은행 정기적금(1-2년) 284행(2003-01~2026-08), 상호금융 정기적금 176행(2012-01~2026-08).
  항목 목록 픽스처(2026-10-04)에 적금 항목과 걸리면 안 되는 이웃이 모두 있다. 키가 본문에 없음을 저장 전에 확인했다
- **2026-10-06 Phase 2 체크포인트**: 백엔드 2,478 passed(T002의 2,458 + 새 20 — T009 승인 변경 포함), 커버리지 96.07%, mypy 209 파일·ruff 통과 /
  프론트엔드 134 파일·1,183 passed(1,172 + 새 11), tsc·eslint 통과. 개발 DB에 `f4c2a8e19d35`(주식 매도 세금 설정 열 셋)를 올렸다
- **2026-10-06 US1 구현 중 테스트 기대값 고침(모두 사용자 승인)**: 셋 다 테스트를 처음 쓸 때 잘못 적은 것이고, 구현은 바꾸지 않았다.
  - `test_recurring_stock` 재투자 끔 — 보유 6 → 5주(손계산 오류)
  - `test_stock_recurring_api`·`_series_api` — 값을 DB 자릿수 문자열 대신 Decimal로 비교하고, `before_listing`은 400(일시금 처리기 그대로)이다. rest-api.md도 고쳤다
  - `RecurringBoard` 외화 원금 표기 `$12,000`, `RecurringStockTable` 열 이름 도우미
- (T059 결과를 여기에 적는다.)
