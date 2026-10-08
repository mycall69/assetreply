---

description: "Task list for 013-investment-comparison"
---

# Tasks: 투자 비교 — 한 자산군의 대상 최대 10개를 같은 조건으로 비교하고 저장해 다시 불러온다

**Input**: Design documents from `/specs/013-investment-comparison/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
- 테스트 작성 → **실패 확인** → 구현 순서다.
- **테스트를 구현보다 먼저 커밋한다.** 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes).
- **구현 뒤 테스트가 실패하면 멈추고 실패 목록과 원인 판단을 먼저 보고한다.** 원인이 테스트 쪽으로 보여도 같다. 이전에 통과하던 테스트가 실패로 바뀐
  경우도 같다(006 D2).

**Organization**: 사용자 스토리별로 묶는다.
- US1(같은 조건의 비교 표 — 일시금·정기예금·매입 후 보유, P1)이 MVP다.
- US2(적립식·정기 적금, P2)와 US3(그래프, P2)는 US1의 화면·스토어 위에 더한다.
- US4(저장·불러오기, P3)는 백엔드가 US1과 무관하고, 화면은 US1의 스토어 위에 더한다.
- 환율 찾기 이분 탐색(모든 비교 경로의 성능 — SC-004)은 Foundational이다.

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

- **메뉴는 바뀌지 않는다**(FR-020, SC-009)
  - 계산 모듈에는 **기본값이 있는 필드를 더하기만** 한다(`deposit_rollover.Summary.accrued_tax`·적금 요약 `open_tax`). 기존 값·키는 그대로다.
  - `resolve_rate`의 이분 탐색은 돌려주는 (환율, 쓴 날짜)가 옛 방식과 같아야 한다(T004).
  - 메뉴 경로의 질의·응답 키를 바꾸지 않는다. T001이 기준 응답을 남기고 T080이 대조한다.
  - 메뉴 공유 부품 `ComparisonChart`·`InstitutionPicker`·`SimulationForm`·`PerformanceChart`는 고치지 않는다. `HistoryContent`에는 선택 속성만 더한다(처음 값 = 지금 문구).
- **비교 경로는 메뉴 경로와 같은 함수를 같은 차례로 부른다**(research R13-1)
  - 질의 검증·수집 판정·`prepare`·요약 JSON 함수·시계열 빌더를 메뉴 경로 모듈·서비스에서 그대로 불러 쓴다. 다시 쓰지 않는다.
  - 거절은 같은 예외를 그대로 올린다 — 본문을 비교 경로에서 만들지 않는다.
  - 가상자산 계산 끝은 `routes/crypto_simulation.calculation_end`다. 테스트는 그 모듈의 `utc_yesterday`를 바꿔 2027년 기준일을 만든다(CLAUDE.md 011).
- **비교는 이력을 쓰지 않는다**(FR-020, SC-007, research R13-14)
  - 비교 스토어는 메뉴 스토어의 `run`·`rerunHistory`·`refreshIfRan`과 `saveHistoryFlow`를 부르지 않는다. 화면 테스트가 `historyStub.calls()`에 `PUT`이 없음을 본다.
- **화면은 계산하지 않는다**(원칙 VI)
  - 비용 합·몫·주 값·현재 가치는 서버가 낸다. 정렬은 `lib/decimalOrder`의 문자열 견주기다. `tests/compareNoClientFinance.test.ts`(T021)가 비교 파일의
    `Number(`·`parseFloat(`·`parseInt(`를 막는다. 막대 길이(`CompareMetricBars`)만 그리기 전용 `Number`를 쓴다(plan Complexity Tracking).
- **값을 만들지 않는다**(원칙 V)
  - 비운 비용 항목은 `null` + 까닭이다(0으로 메우지 않는다). 수집 중인 대상의 칸은 비운다(0이 아니다).
  - `test_no_interpolation`은 주석까지 "전일 값"·"이전 값"·"직전 값"·`fillna`·`ffill`·`interpolate`를 찾는다.
- **차트 테스트의 모의 객체**(CLAUDE.md 010·011)
  - 기존 모의에는 `createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`·`LineSeries`만 있다. 새 차트는 그 안에서만
    동작한다 — `createSeriesMarkers`·`priceScale()`·`subscribeClick`·라이브러리 열거형을 실행 중에 쓰지 않는다. 점은 "점만 그리는 `LineSeries`"다.
  - 결과를 그리는 페이지 테스트는 `lightweight-charts`를 모의한다. "N passed"만 보지 말고 **종료 코드**를 본다(011 T036).
- **가드 테스트**
  - `test_no_hardcoded_dates`는 `src`(마이그레이션 포함)의 ISO 날짜 리터럴·`date(2027, …)` 호출을 막는다. 날짜는 테스트·독스트링에만 둔다.
  - `test_dialect_isolation` — 방언 문법은 `db/dialect.py`뿐이다. 저장한 비교는 삽입·삭제·목록이라 방언 문법이 필요 없다.
  - `test_no_float` — `simulation`·`repository`·`db`의 `float` 금지. `test_layer_boundaries` — `simulation`은 `api`·`repository`·`db`를 부르지 않는다,
    저장소는 `src.api`에서 `src.api.errors`만.
  - `tests/noUnbuiltAssetRoutes.test.ts`·`tests/Sidebar.test.tsx`는 지금 `/compare`를 막는다 — 바뀌는 기존 테스트 승인 목록(T006)이다.
- **바뀌는 기존 테스트는 research R13-16의 목록이고, 승인을 받은 뒤에만 고친다**(T006·T039)
  - 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만든다(012 T011·T038과 같은 절차).
  - 목록 밖의 실패는 결함으로 보고 멈춘다. 공유 테스트 기반(`frontend/tests/setup.ts`)에는 **더하기만** 한다(T060).
- **부동산 고르기 인스턴스**(research R13-9) — `realEstateStore`의 필드·동작을 바꾸지 않는다(상태 생성기를 내보내 비교 인스턴스를 하나 더 만든다). 부동산 메뉴의
  기존 테스트가 고치지 않고 통과해야 한다. 고쳐야 하면 멈추고 보고한다.
- **DB 비밀번호·키를 출력하거나 셸 인자로 넘기지 않는다.** 앱 DB 사용자는 `CREATE DATABASE` 권한이 없다 — 마이그레이션은 `alembic upgrade head`로만 한다.
- **개발 서버를 띄운 채 통합 테스트를 돌리지 않는다**(같은 MySQL 스키마를 다시 만든다).
- **브라우저 확인은 사용자 데이터를 바꾸지 않는다** — 비교 실행은 이력을 쓰지 않는다(확인 항목). 확인으로 만든 저장한 비교는 끝에 지우고 전후 목록이 같음을 본다.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 구현 전의 기준(불변 대조용 응답·기존 검사 통과 상태·DB 머리)

- [X] T001 구현 전 기준 응답을 남긴다 (FR-020, SC-009, quickstart 6)
  - 서버를 띄운다(`./start.sh`).
  - 메뉴 표 경로 첫 쪽의 머리(`summary`·`condition`·대상 식별 — `rows` 제외)와 `/series` 응답을 저장소 밖 작업용 임시 폴더(`013-baseline/before/`)에 JSON으로 저장한다.
    - 주식 일시금 KRX `005930.KS`·NYSE `XLK`(원화 원금, 재투자), 주식 적립식 `005930.KS` 매달
    - 가상자산 일시금 BTC(원화), 가상자산 적립식 BTC 매일
    - 정기예금 시중은행, 정기 적금 시중은행, 부동산 헬리오시티 30평대
  - `end`를 고정한다(`2026-09-30` — 받는 경로만). 부동산은 `end`가 없으니 T080을 같은 KST 날짜에 하거나 날짜 차이만 걸러 견준다. 받은 시각·조건을 `meta.json`에 적는다.
    202면 수집이 끝난 뒤 다시 받는다.
- [X] T002 구현 전 기존 검사의 통과 상태를 기록한다 (SC-009)
  - 서버를 내린다(`./stop.sh`).
  - 백엔드 `pytest -q --cov=src`·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수를 Notes에 적는다. 실패가 있으면 기능 전의 실패로 기록하고 멈추고 보고한다.
- [X] T003 개발 DB 상태를 확인한다 — 머리 리비전이 `a6d2f9c41b83`인지(`backend/.venv/bin/python -m alembic current`). 다르면 멈추고 보고한다 (data-model 1)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 환율 찾기 이분 탐색 — 모든 비교 경로(특히 원화 원금 가상자산 일봉)의 성능(research R13-13). 값은 그대로다.

**⚠️ CRITICAL**: 비교 경로(US1·US2)의 성능 확인(T079)이 이 페이즈에 기댄다. 기능상으로는 US1~US4를 막지 않는다.

### Tests for Foundational ⚠️

- [X] T004 [P] `backend/tests/unit/test_fx_resolve_bisect.py` — `simulation/fx_convert.resolve_rate` (SC-004, SC-009, FR-020)
  - 테스트 안에 옛 방식(전체 훑기 — `max(d for d in by_date if d < on)`)의 참조 구현을 둔다.
  - 고정 시드의 무작위 날짜 집합(주말·공휴일 빈 날 포함) × 조회 날짜(정확 일치, 두 고시일 사이, 첫 고시일 전, 마지막 고시일 뒤)에서 (환율, 쓴 날짜)가 참조와 같다.
  - 이전 고시일이 없으면 `None`. 이후 고시일을 쓰지 않는다.
  - `RateLookup({...})`처럼 사전 하나로 만드는 기존 호출(`api/services/stock_fx.py:80`)이 그대로 동작한다.

### Implementation for Foundational

- [X] T005 `backend/src/simulation/fx_convert.py` — `RateLookup`가 정렬된 날짜 튜플을 함께 든다(`field(init=False)` + `__post_init__`의 `object.__setattr__` — 생성자 호출부 그대로). `resolve_rate`의 빗나감 경로를 `bisect`로 바꾼다. 독스트링의 규칙(가장 가까운 이전 고시일, 이후 고시일 금지, 쓴 날짜 반환)은 그대로다 (SC-004, research R13-13)

**Checkpoint**: T004 통과. 기존 환율·주식·가상자산 테스트가 그대로 통과한다.

---

## Phase 3: User Story 1 - 한 자산군의 대상 여러 개를 같은 조건으로 비교한다 (Priority: P1) 🎯 MVP

**Goal**: `/compare`에서 자산군을 고르고 대상 2~10개를 메뉴와 같은 부품으로 더해, 일시금(주식·가상자산)·정기예금·매입 후 보유(부동산)로 실행한다. 대상마다
투자 원금·현재 가치·비용(반영·매도 가정)·투자 수익·수익률이 한 표에 나란히 보인다. 막히면 비교 전체를 막고 시작일을 제안하며, 계산된 대상부터 보이고, 조건이
바뀌면 흐린다.

**Independent Test**: 주식을 고르고 삼성전자·SK하이닉스·XLK를 더한 뒤 2020-01-02, 10,000,000원 일시금(배당 재투자)으로 실행한다. 세 줄의 원금·현재 가치·투자 수익·
수익률이 주식 메뉴의 같은 조건 보드와 같고, 비용은 그 실행의 수수료·세금 합이다(spec US1 Independent Test, quickstart 2·5-1~5-6·5-9·5-12).

### Tests for User Story 1 ⚠️

- [X] T006 [US1] 기존 테스트 변경 승인을 받는다 — research R13-16의 목록 (FR-001)
  - 절차: 이 페이즈의 테스트(T007~T021)를 쓰고 구현(T023~T037)을 마친 뒤, 구현을 작업 트리에 둔 채 전체 스위트(백엔드·프론트엔드)를 돌려 **실제로 실패한** 기존
    테스트로 목록을 만든다.
  - 예상: `frontend/tests/Sidebar.test.tsx`(준비 안 된 항목 `["투자 비교","대시보드"]` → `["대시보드"]`, "준비중" 2 → 1, 포커스 예 "투자 비교" → "대시보드", 링크 목록에
    `/compare`), `frontend/tests/noUnbuiltAssetRoutes.test.ts`(`UNBUILT`에서 `compare`, 사이드바 링크 목록에 `/compare`), `frontend/tests/TopBarTitle.test.ts`(표가 전체를
    고정하면 `/compare`).
  - 목록을 테스트마다 "지금 단언 → 새 단언"으로 보이고 승인을 받는다. 승인 날짜를 Notes에 적는다. 목록 밖의 실패는 결함으로 보고 멈춘다.
- [X] T007 [P] [US1] `backend/tests/unit/test_deposit_accrued_tax.py` — `simulation/deposit_rollover.simulate_deposit`의 `Summary.accrued_tax` (FR-011, SC-001, data-model 4)
  - 계산 끝이 회차 안이면 `accrued_tax = interest_tax(accrued_interest(회차 원금, 금리, 가입일, 만기일, 끝), 세율)`이고 `balance = 회차 원금 + 경과 이자 − accrued_tax`.
  - 계산 끝이 만기일과 같으면 0, 재예치 달 결측으로 멈추면(`rate_missing`) 0.
  - 같은 입력의 `balance`·`profit`·`return_rate`·`terms`가 더하기 전과 같다(고정 참조값).
- [X] T008 [P] [US1] `backend/tests/unit/test_comparison_costs.py` — `simulation/comparison_costs` 일시금 쪽 (FR-011, SC-001, research R13-3, data-model 3.1)
  - 주식 국내: `buy_fee = floor_won(Σ 모든 매수 행 trade_fee)`(처음 매수 + 배당 재투자 매수), `dividend_tax = floor_won(Σ dividend_tax)`.
  - 주식 해외: `buy_fee = floor_won(Σ trade_fee × 그 행 fx_rate)`, `dividend_tax` 같은 규칙. `buy_fee + sale_fee = saleCost.feesKrw`(012 US6 값과 묶는다).
  - 매도 몫: `sale_fee = saleCost.fee`, 국내 `transaction_tax` / 해외 `capital_gains_tax = saleCost.tax`.
  - 가상자산 일시금: `buy_fee`만, `sale`은 `None`. 원화 환산은 `services/crypto_recurring.py:187-190`의 `buyFeeTotal` 규칙과 같다.
  - 정기예금: `interest_tax_matured = Σ terms.tax`, `interest_tax_open = summary.accrued_tax`, `sale`은 `None`.
  - 부동산: `acquisition_tax`·`education_tax`·`rural_tax`·`brokerage_buy`(모두 `in_principal=True`, 합 = `acquisition.total`), `property_tax`·`comprehensive_tax`(합 = `holdingTaxTotal`),
    매도 `brokerage_sale`·`transfer_income_tax`·`transfer_local_tax`(합 = `saleCost.total`).
  - 항목 합 = 몫의 합, `reflected.total + sale.total = total`. 항목 하나가 `None`이면 그 몫의 합과 전체 합이 `None`이고 `blank`에 까닭이 있다(0으로 메우지 않는다).
  - 모듈이 `src.api`·`src.repository`·`src.db`를 부르지 않는다(`test_layer_boundaries`에 맡기되 이 파일에서도 불러오기 목록을 본다).
- [X] T009 [P] [US1] `backend/tests/unit/test_comparison_metrics.py` — `api/services/comparison_metrics` 일시금·정기예금·부동산 (FR-011, FR-015, SC-001, SC-005, research R13-4, data-model 3)
  - 주 값(`mainBasis`): 주식 일시금 — `profitAfterSale`·`returnRateAfterSale`이 둘 다 있으면 `after_sale`, 없으면 `holding`(`PerformanceBoard.tsx:50`). 부동산 — 매도 후 값이
    있으면 `after_sale`, 없으면 `holding`(`RealEstateBoard.tsx:44`). 가상자산 일시금·정기예금 — `holding`.
  - 현재 가치: 주식·가상자산 `totalKrw`, 정기예금 `principal + profit`(`Decimal`), 부동산 `value`(없으면 `None`).
  - 투자 원금 `{amount, currency, krw}`: 원화 원금이면 `krw = amount`, 외화 원금이면 `krw = principalKrw`. 부동산은 `invested`.
  - `holding = {profit, returnRate}` = 메뉴 요약의 `profit`·`returnRate`.
  - `provisional`: 정기예금 `provisionalFrom`이 있으면 `unpublished_rate`, 부동산 `provisional` → `provisional_price`, `estimated` → `estimated_price`, `isFinal = false` → `not_final`.
  - `fx`: 외화 종목·코인이면 `{currency, valuationRate, valuationRateDate, source, exchange}` — 기준일 행의 `fxRate`·`fxRateDate`, 출처 ECOS 매매기준율. 원화 대상은 `None`.
  - `lineEnd = {date: asOf, holdingReturnRate: summary.returnRate, afterSaleReturnRate}` — `afterSaleReturnRate`는 `mainBasis = after_sale`일 때 그 값, 아니면 `None`.
  - 금액·비율 글자에 지수 표기가 없다(`Decimal("0E-12")` → `"0"` — `stock_recurring.dec`).
- [X] T010 [P] [US1] `backend/tests/integration/test_comparison_identity.py` — 비교 경로 넷(주식·가상자산 일시금, 정기예금, 부동산) ↔ 메뉴 경로 (FR-005, FR-008, FR-009, FR-011, FR-020, SC-001, SC-002, SC-007, contracts/rest-api.md 1)
  - 같은 고정 데이터·같은 질의로 두 경로를 부른다. `summary`·`condition`(·주식 `exchange`)이 같다.
  - `series`가 같은 `maxPoints`의 메뉴 `/series`와 같다. `maxPoints`를 빼면 1000으로 다운샘플링된다(`sourcePointCount`가 같고 점 수 ≤ 1000).
  - 받지 않은 구간이 있으면 202 본문이 메뉴와 같다(주식 `jobId`·`progressUrl`, 가상자산, 정기예금, 부동산 `kind:"trade"`).
  - 거절 본문이 메뉴와 같다 — 주식 `before_listing`, 가상자산 `before_listing`·`unknown_coin`, 정기예금 `before_first_month`, 부동산 `before_first_trade`·`no_price_at_purchase`.
  - 부동산 비교 경로에 `buyPrice`를 보내면 400 `invalid_query`(FR-008).
  - 실행 전후 `simulation_history` 행 수가 같다(FR-020).
  - 응답에 `rows`·`terms`가 없다(표가 없다 — FR-011).
- [X] T011 [P] [US1] `backend/tests/integration/test_comparison_api.py` — `comparison` 블록과 메뉴 값의 짝 (FR-011, SC-001, data-model 3)
  - 주식 국내·해외 일시금: `costs.sale.total = summary.saleCost.total`, 해외 `buy_fee + sale_fee = saleCost.feesKrw`, `profit = profitAfterSale`, `returnRate = returnRateAfterSale`.
  - 부동산: 취득 항목 합 = `acquisition.total`, 보유세 항목 합 = `holdingTaxTotal`, 매도 몫 = `saleCost.total`, `principal.krw = invested`.
  - 정기예금: `interest_tax_matured` = 끝난 회차 세금 합, 현재 가치 = `principal + profit`. 미발표 달이 낀 고정 데이터에서 `provisional`에 `unpublished_rate`.
  - 가상자산 일시금: `costs.sale`이 `null`, `lineEnd.afterSaleReturnRate`가 `null`.
  - 해외 주식: `fx.valuationRateDate`가 기준일 행의 `fxRateDate`, `basisCurrency = "KRW"`.
- [X] T012 [P] [US1] `frontend/tests/decimalOrder.test.ts` — `lib/decimalOrder.compareDecimal` (FR-012, research R13-11)
  - 부호, 정수부 길이, 소수 자리(`"9.99" < "10"`, `"-0.5" < "0"`, `"0.10" = "0.1"`, `"-0" = "0"`).
  - `null`은 오름·내림 모두 끝이다. 같은 값은 처음 차례를 지킨다(안정 정렬 도우미 `sortRows`).
- [X] T013 [P] [US1] `frontend/tests/compareCondition.test.ts` — `lib/compareCondition` (FR-004, FR-007, FR-012a, data-model 2)
  - 정규 조건이 data-model 2의 칸 그대로다: `v = 1`, `method` 짝(주식·가상자산 `lump_sum`·`recurring`, 예금 `deposit`·`installment`, 부동산 `hold`), `frequency`는 `recurring`만,
    `reinvest`는 주식만, 부동산 `amount = null`.
  - 같음 판정: 같은 입력이면 같고, 시작일·금액·통화·재투자·방식·주기·대상 더하기·빼기·차례가 다르면 다르다.
  - 대상 키: 주식 `market|symbol`, 가상자산 `coinId`, 예금 투자처, 부동산 `complexId|area`.
  - 자동 이름 `"{자산군} {대상 수}개 · {start} · {방식}"`(예: `주식 3개 · 2020-01-02 · 일시금`).
  - 고를 수 있는 통화: 원화 + 모든 대상의 통화가 같을 때 그 통화. 대상이 없으면 원화만.
- [X] T014 [P] [US1] `frontend/tests/compareBlock.test.ts` — `lib/compareBlock` (FR-010, FR-013, FR-014, SC-003, research R13-6)
  - R13-6 표의 코드마다 갈래(`start`·`remove`·`failed`)와 날짜 칸(`startableFrom`·`availableFrom`·`lastDay`·`month`)·문구.
  - 비교 전체: 막힌 대상이 하나라도 있으면 `blocked`, 아니면 `ok`가 아닌 대상이 있으면 `partial`, 모두 `ok`면 `complete`. `failed`는 막힘이 아니다.
  - 제안 날짜 = `start` 갈래 날짜 가운데 가장 늦은 날. 수집 중인 대상이 하나라도 있으면 `null`(+ 수집 중 수). `start` 갈래가 없으면 `null`.
  - 수집 중이던 대상이 막힘으로 바뀌면(늦게 드러난 막힘) 전체가 `blocked`.
  - `start_after_end`는 `too_late` 갈래이고 제안 날짜 후보가 아니다 — 문구 "시작일을 {lastDay} 이전으로 바꾸세요"(FR-010).
- [X] T015 [P] [US1] `frontend/tests/registerStock.test.ts` — `lib/stockSelection.registerStock` (FR-003, research R13-9) — 006의 `tests/stockSelection.test.ts`(메뉴 스토어의 등록)는 그대로 둔다
  - 목록 결과·외부 결과마다 `POST /api/stocks/selection` 본문이 지금 `stockStore`가 보내는 본문과 같다. 응답 `{market, symbol, name, currency, listedOn}`을 돌려준다. 실패는 `ApiError`.
- [X] T016 [P] [US1] `frontend/tests/compareRealEstatePicker.test.ts` — `stores/compareRealEstatePicker`(같은 상태 생성기의 비교 인스턴스) (FR-003, research R13-9)
  - 비교 인스턴스에서 시·도 → 시·군·구 → 법정동 → 단지 → 평형을 고르면 목록 경로를 차례로 부르고(`apiClient.get` 모의), 메뉴 `useRealEstateStore`의 상태(결과·실행 차례·
    고르기)는 그대로다. 반대 방향도 같다.
  - 202 진행(시·군·구 실거래·단지 상세·평형)이 그 인스턴스에만 보인다 — 진행 구독이 인스턴스마다다.
- [X] T017 [P] [US1] `frontend/tests/InstitutionChecklist.test.tsx` — `components/compare/InstitutionChecklist` (FR-003, FR-004, F2)
  - 체크박스 다섯(이름은 `INSTITUTION_NAMES`), 체크 = `onAdd`, 해제 = `onRemove`.
  - 정기 적금이면 적금 없는 투자처가 꺼지고 까닭이 보인다(`installment.available`). 이미 체크된 곳은 체크가 남고 까닭이 보인다.
  - id·name이 `InstitutionPicker`(`deposit-institution`·`deposit-inst-*`)와 겹치지 않는다.
- [X] T018 [P] [US1] `frontend/tests/compareStore.test.ts` — `stores/compareStore` (FR-002, FR-004, FR-009, FR-010, FR-012a, FR-013, FR-020, SC-002, SC-003, SC-007, data-model 5, research R13-7·R13-8)
  - 실행: 대상마다 비교 경로 하나를 부르고 질의가 메뉴 질의 함수의 출력과 **글자까지** 같다 — 주식 `stockStore.toQuery`, 가상자산 `cryptoStore.toQuery`, 정기예금
    `depositStore.toQuery`, 부동산 `simulationQuery`(매입가 없이).
  - 200 → `ok`, 202 → `collecting`(그 자산군 진행 스트림을 `jobId`로 구독 — 모듈 모의), 거절 → `blocked`, 5xx·네트워크 → `failed`.
  - 스트림 `onCompleted` → **그 대상만** 다시 요청. `onFailed` → `failed`(까닭). 같은 실행에서 연달아 202를 세 번 받으면 `failed`("수집이 끝나지 않았습니다").
  - 새 실행은 차례 번호를 올리고, 늦게 온 이전 실행의 응답·스트림 사건을 버린다.
  - 흐림: 실행 뒤 시작일을 바꾸면 `isStale`, 되돌리면 아님. 정렬은 흐림과 무관.
  - 자산군 전환: 대상·결과를 비우고 시작일·금액을 남기며 모든 구독을 푼다. 없는 방식은 그 자산군의 기본 방식으로.
  - 대상: 같은 대상은 다시 더하지 않는다, 11번째는 더하지 않고 알림, 2개 미만은 실행하지 않는다.
  - 실행·다시 요청 어디에서도 `/api/history` `PUT`이 없다(`historyStub.calls()`).
- [X] T019 [P] [US1] `frontend/tests/CompareTable.test.tsx` — `components/compare/CompareTable`·`CostCell` (FR-011, FR-012, FR-013, FR-014, F5)
  - 열 일곱(대상, 기준일, 투자 원금, 현재 가치, 비용, 투자 수익, 수익률).
  - 투자 원금: 원화는 하나, 외화는 `"$10,000 (₩13,581,000)"` 꼴. 부동산은 투입 금액 + "매입가 ₩… · 취득 비용 포함".
  - 비용: 합(`-₩…`) + "반영 ₩…"·"매도 가정 ₩…", 펼치면 항목 글자, 부동산 취득 항목에 "투자 원금에 포함", 비운 항목 "—" + 까닭, 칸 도움말(현재 가치 − 비용 − 투자 원금 ≠ 투자 수익).
  - 투자 수익·수익률 옆 기준 글자("매도 후"·"보유 중"·값 없으면 "—"). 잠정 ⏳ + 까닭. 외화 대상의 환율 줄(통화 · 환율(날짜 ECOS 매매기준율)).
  - 열 머리 단추로 정렬(`aria-sort` 오름·내림 번갈아), `null`은 끝, 처음 차례는 더한 차례.
  - 수집 중·실패 줄은 맨 아래, 값 칸은 비어 있다(0이 아니다). 수집 중은 진행, 실패는 "다시 시도" 단추.
  - 막힘·수집 중·수집 실패 줄의 글자가 서로 다르다(FR-014).
- [X] T020 [P] [US1] `frontend/tests/ComparePage.test.tsx` — `app/compare/page.tsx` (FR-001~FR-014, SC-008, F1~F5·F8)
  - `lightweight-charts`·진행 스트림 모듈을 모의한다. 검색은 `tests/support/stockSearchFixtures.routeGet`·`coinSearchFixtures.routeSearch`, 등록 `POST`는 `apiClient.post` 모의.
  - 자산군 라디오, 주식 검색으로 셋 더하기, 칩 빼기, 11번째 알림, 같은 대상 알림, 2개 미만이면 "비교 실행" 꺼짐.
  - 실행 → 표 줄이 고정 응답의 값이다. 막힘 응답이 끼면 결과 대신 막힘 칸(이름·까닭·제안). "시작일 옮기기"는 시작일만 바꾸고 요청하지 않는다.
  - 202 대상은 "수집 중" 줄이었다가 스트림 완료 뒤 채워진다. 실행 뒤 시작일을 바꾸면 "조건이 바뀌었습니다" 띠와 흐림, 되돌리면 사라진다.
  - 예금 체크리스트, 부동산 고르기(비교 인스턴스)로 대상 더하기.
  - 페이지가 이력 `PUT`을 하지 않는다. 종료 코드 0.
- [X] T021 [P] [US1] `frontend/tests/compareNoClientFinance.test.ts` — 비교 파일의 클라이언트 계산 금지 (원칙 VI, research R13-11)
  - `components/compare/CompareTable.tsx`·`CostCell.tsx`, `lib/decimalOrder.ts`·`compareBlock.ts`·`compareCondition.ts`, `stores/compareStore.ts`에 주석 밖 `Number(`·`parseFloat(`·
    `parseInt(`가 없다(`tests/noClientSideFinance.test.ts`와 같은 정규식·주석 제거).
- [X] T022 [US1] T006에서 승인된 기존 테스트를 고친다 — 바뀐 요구를 단언하는 부분만. 고친 줄 위에 `// 013 승인 <날짜>` 주석 (FR-001)

### Implementation for User Story 1

- [X] T023 [US1] `backend/src/simulation/deposit_rollover.py` — `Summary`에 `accrued_tax: Decimal`(맨 끝, 기본값 `Decimal(0)`)을 더하고, `matures > end`에서 이미 계산하는 경과 이자의 세금을 넣는다. 만기·멈춤으로 끝나면 0 (FR-011, data-model 4)
- [X] T024 [US1] `backend/src/simulation/comparison_costs.py`(신규, 순수) — 일시금·정기예금·부동산 (FR-011, research R13-3, data-model 3.1)
  - `CostItem(kind, amount: Decimal | None, in_principal: bool)`, `Costs(reflected, sale | None, blank)`와 합 계산(항목 `None`이면 합 `None`).
  - `kind`는 data-model 3.1 표의 글자 그대로: `buy_fee`·`dividend_tax`·`interest_tax_matured`·`interest_tax_open`·`acquisition_tax`·`education_tax`·`rural_tax`·`brokerage_buy`·
    `property_tax`·`comprehensive_tax`·`sale_fee`·`transaction_tax`·`capital_gains_tax`·`crypto_tax`·`brokerage_sale`·`transfer_income_tax`·`transfer_local_tax`.
  - 주식 일시금 행(`SimulationResult.rows`의 `ConvertedRow`)에서 매수 수수료·배당 소득세 원화 합, 가상자산 일시금 매수 수수료 원화, 정기예금 회차 세금·`accrued_tax`, 부동산 취득·
    보유·매도 항목.
  - 원 미만 버림은 `ROUND_FLOOR`(주식 적립식 `floor_won`과 같은 규칙). `src.api`·`src.repository`·`src.db`를 부르지 않는다.
- [X] T025 [US1] `backend/src/api/services/comparison_metrics.py`(신규, 순수) — 일시금·정기예금·부동산 정규화 블록 (FR-011, FR-015, research R13-4·R13-5, data-model 3)
  - 메뉴 요약 JSON(문자열)을 `Decimal`로 읽어 `asOf`·`isFinal`·`principal`·`currentValue`·`mainBasis`·`profit`·`returnRate`·`holding`·`costs`·`lineEnd`·`provisional`·`fx`를 만든다.
  - 금액·비율은 지수 표기 없는 문자열(`stock_recurring.dec`). DB·HTTP·저장소를 부르지 않는다.
- [X] T026 [US1] `backend/src/api/routes/comparison.py`(신규) — 비교 경로 넷: `/api/comparison/stocks/simulation`·`/crypto/simulation`·`/deposit/simulation`·`/realestate/simulation` (FR-005, FR-008, FR-009, FR-011, FR-020, contracts/rest-api.md 1)
  - 질의 선언·검증은 메뉴 경로(`routes/stock_simulation.py:150-164`, `routes/crypto_simulation.py:118-130`, `routes/deposit_simulation.py:77-85`, `routes/realestate_simulation.py:26-40`)와 같다.
    표 전용 질의는 없고 `maxPoints`(`ge=2`, 처음 값 1000)가 있다. 부동산 `buyPrice`가 오면 400 `invalid_query`.
  - 호출 차례는 research 조사 표 그대로 — 주식 `check_principal_currency` → `require_stock` → 통화 짝 → `require_start_available` → `collecting_body` → `prepare` →
    `routes.stock_simulation.summary_json` → `build_series`; 가상자산 `calculation_end` → `require_coin` → … → `prepare(..., daily=True)`; 정기예금 `read_request` →
    `simulate_or_collect`; 부동산 `parse_query` → `prepare` → `render`의 `complex`·`area`·`condition`·`acquisition`·`summary`.
  - 가상자산 일시금은 요약과 시계열을 한 번에 내려고 `prepare(..., daily=True)`를 쓴다(메뉴 표 경로는 `daily=False`). `daily`가 일봉 상태만 더하고 요약 값을 바꾸지
    않는다는 전제이고, T010의 요약 동일성 검사가 지킨다. 다르면 멈추고 보고한다(요약은 `daily=False`, 시계열은 `daily=True`로 두 번 계산하는 쪽으로 바꿀지 묻는다).
  - 응답 `{basisCurrency, target, condition, exchange, summary, series, comparison}`. `rows`·`terms`를 담지 않는다. 이력 서비스를 부르지 않는다.
- [X] T027 [US1] `backend/src/api/main.py` — 비교 라우터를 더한다(다른 라우터와 같은 자리·주석 `# 013 —`). 저장 라우터(T073)는 이것보다 먼저 들어갈 자리를 남긴다 (contracts/rest-api.md 6)
- [X] T028 [US1] `frontend/src/lib/types.ts` — 비교 응답(`ComparisonBlock`·`ComparisonCosts`·`CostItemKind` 유니언·`MainBasis`·`ProvisionalKind`·`LineEnd`·`ComparisonFx`), 대상 칸(data-model 2), `CompareAsset`·`CompareMethod` (data-model 2·3)
- [X] T029 [P] [US1] `frontend/src/lib/decimalOrder.ts` — `compareDecimal`·`sortRows` (FR-012, research R13-11)
- [X] T030 [P] [US1] `frontend/src/lib/compareCondition.ts` — 정규 조건·같음·대상 키·자동 이름·고를 수 있는 통화 (FR-004, FR-007, FR-012a, data-model 2)
- [X] T031 [P] [US1] `frontend/src/lib/compareBlock.ts` — 응답 갈래·비교 전체 상태·제안 날짜·문구 (FR-010, FR-013, FR-014, research R13-6)
- [X] T032 [US1] `frontend/src/lib/stockSelection.ts`(신규 — `registerStock`) · `frontend/src/stores/stockStore.ts`(그것을 쓴다 — 동작 그대로) (FR-003, research R13-9)
- [X] T033 [US1] 부동산 고르기 인스턴스 — `frontend/src/stores/realEstateStore.ts`(상태 생성기 `realEstateStateCreator`를 내보내고 모듈 수준 구독 `watchers`·실행 차례를 생성기 안으로, `simulationQuery`를 내보낸다) · `frontend/src/stores/compareRealEstatePicker.ts`(같은 생성기의 비교 인스턴스) (FR-003, research R13-9 — 구현 중 슬라이스 팩토리에서 바꿨다)
  - 부동산 메뉴의 기존 테스트가 **고치지 않고** 통과해야 한다. 고쳐야 하면 멈추고 보고한다.
- [X] T034 [US1] `frontend/src/lib/compareApi.ts`(신규) — (자산군, 방식) → 비교 경로와 메뉴 질의 함수의 짝(일시금·정기예금·매입 후 보유), 요청은 `apiClient`의 공통 요청 함수 (FR-009, research R13-2)
- [X] T035 [US1] `frontend/src/stores/compareStore.ts`(신규) — data-model 5의 입력·`RunState`·대상 상태, 대상별 구독 `Map`, 차례 번호, 연달은 202 한도 3, 흐림 파생, 자산군 전환 (FR-002, FR-004, FR-010, FR-012a, FR-013, FR-020, research R13-7·R13-8)
  - 메뉴 스토어의 `run` 계열·`saveHistoryFlow`를 부르지 않는다.
- [X] T036 [US1] 비교 부품 — `frontend/src/components/compare/AssetPicker.tsx`·`TargetChips.tsx`·`CompareTargetPicker.tsx`(자산군별 고르기 — `StockSearch`·`CoinSearch`·`InstitutionChecklist`·부동산 피커 셋 + "더하기")·`InstitutionChecklist.tsx`·`CompareConditionForm.tsx`(일시금·정기예금·매입 후 보유 — `StartDateInput`, 금액, 통화, 재투자)·`CompareBlockedPanel.tsx`·`CompareTable.tsx`·`CostCell.tsx`·`StaleBanner.tsx` (FR-002~FR-014, F2~F5·F8)
- [X] T037 [US1] `frontend/src/app/compare/page.tsx`(신규) · `frontend/src/components/shell/Sidebar.tsx`(`{ label: "투자 비교", href: "/compare" }`) · `frontend/src/components/shell/TopBar.tsx`(`TITLES["/compare"] = "투자 비교"`) (FR-001, F1)
- [ ] T038 [US1] 검증 — quickstart 2(개발 서버 `curl` 두 줄)·5-1~5-6·5-9·5-12 (FR-001~FR-014, FR-020, SC-001, SC-003, SC-007, SC-008)
  - 1440×900 헤드리스 Chrome, 새 브라우저 문맥. 비교 실행 전후 네 자산군 `GET /api/history/{asset}`가 같다.
  - quickstart 실행 기록에 적는다.

**Checkpoint**: US1 완결 — 일시금·정기예금·매입 후 보유의 비교 표가 메뉴와 같은 값을 보인다. 이력은 그대로다.

---

## Phase 4: User Story 2 - 적립식·정기 적금으로도 비교한다 (Priority: P2)

**Goal**: 주식·가상자산 적립식(매일·매주·매달·매년)과 정기 적금으로 같은 비교를 한다. 비용은 같은 두 몫이고, 주 값은 적립식 보드 규칙(매도 후, 비면 "—")이다.

**Independent Test**: 가상자산 비트코인·이더리움, 적립식 매달 100,000원(원화). 두 줄의 총 납입 원금이 같고 가상자산 메뉴의 같은 적립식 조건 결과와 같다(spec US2 Independent
Test, quickstart 5-7).

### Tests for User Story 2 ⚠️

- [ ] T039 [US2] 기존 테스트 변경 승인을 받는다 — T006과 같은 절차. 예상 목록은 없다(research R13-16). 실제로 실패한 기존 테스트가 있으면 "지금 단언 → 새 단언"으로 보이고 승인을 받는다 (FR-006)
- [ ] T040 [P] [US2] `backend/tests/unit/test_installment_open_tax.py` — `simulation/installment_ladder`의 `open_tax` (FR-011, SC-001, data-model 4)
  - 진행 중 적금 계약·정기예금이 있으면 `open_tax`가 그 경과 이자의 소득세 합이고, 평가액 = 납입·원금 + 경과 이자 − `open_tax`.
  - 모두 만기로 끝나면 0. 같은 입력의 기존 요약 값(`interest_total`·`tax_total`·`balance`·`profit`·`return_rate`)이 더하기 전과 같다.
- [ ] T041 [P] [US2] `backend/tests/unit/test_comparison_costs_recurring.py` — `simulation/comparison_costs` 적립식·정기 적금 (FR-011, SC-001, research R13-3)
  - 주식 적립식: `buy_fee = buyFeeTotal`, `dividend_tax = dividendTaxTotal`, 매도 `sale_fee = saleCost.fee`, 세금 = `saleCost.tax`.
  - 가상자산 적립식: `buy_fee = buyFeeTotal`, `sale_fee = saleCost.fee`. 기준일이 과세 시행일 전이면 `crypto_tax = 0`(`not_yet_taxed`), 시행일 뒤면 `crypto_tax = None`·`sale.total = None`·
    `total = None`·`blank = "outside_rules"`(0으로 메우지 않는다).
  - 정기 적금: `interest_tax_matured = taxTotal`(메뉴 칸과 같다), `interest_tax_open = open_tax`, `sale = None`.
- [ ] T042 [P] [US2] `backend/tests/unit/test_comparison_metrics_recurring.py` — `api/services/comparison_metrics` 적립식·정기 적금 (FR-011, FR-015, research R13-4)
  - 적립식 둘: `mainBasis = after_sale`, 매도 후 값이 `null`이면 `unavailable`이고 `profit`·`returnRate`가 `None`(물러나지 않는다 — `RecurringBoard.tsx:73`). 현재 가치 `totalKrw`,
    원금 `contributed`(+`contributedKrw`).
  - 정기 적금: `holding`, 현재 가치 `balance`, 원금 `contributed`, `lineEnd.afterSaleReturnRate = None`, `provisionalFrom` → `unpublished_rate`.
- [ ] T043 [P] [US2] `backend/tests/integration/test_comparison_identity_recurring.py` — 비교 경로 셋(주식·가상자산 적립식, 정기 적금) ↔ 메뉴 경로 (FR-006, FR-011, FR-020, SC-001, SC-002, contracts/rest-api.md 1)
  - T010과 같은 대조(`summary`·`condition`·`series`·202·거절). 거절은 정기 적금 `installment_not_available`·`before_first_month`, 가상자산 `start_after_end`.
  - 가상자산 2027년 기준일은 `routes.crypto_simulation`의 `utc_yesterday`를 바꿔 만든다.
  - 실행 전후 `simulation_history` 행 수가 같다.
- [ ] T044 [P] [US2] `frontend/tests/compareStoreRecurring.test.ts` — 적립식·정기 적금 실행 (FR-006, FR-007, FR-010, FR-012a)
  - 적립식 질의 = `stockStore.toRecurringQuery`·`cryptoStore.toRecurringQuery`(`amount`·`frequency`), 정기 적금 = `depositStore.toInstallmentQuery` — 글자까지 같다.
  - 방식·주기를 바꾸면 흐림. 정기 적금 + 적금 없는 투자처가 대상에 있으면 400 `installment_not_available` → `blocked`(`remove` 갈래, "정기 적금이 없는 투자처").
- [ ] T045 [P] [US2] `frontend/tests/ComparePageRecurring.test.tsx` — 방식 칸과 적립식 표 (FR-006, FR-007, FR-011, F3·F5)
  - 주식·가상자산 라디오 일시금·적립식 + 주기(`aria-label="납입 주기"`), 금액 라벨 "한 번 납입액"·"월 납입액", 예금 정기예금·정기 적금, 부동산 "매입 후 보유" 글자.
  - 표의 투자 원금 "총 납입 원금 · N회 납입". 가상자산 적립식의 시행일 뒤 비용 "—" + 까닭, 투자 수익·수익률 "—".

### Implementation for User Story 2

- [ ] T046 [US2] `backend/src/simulation/installment_ladder.py` — 요약에 `open_tax: Decimal`(맨 끝, 기본값 `Decimal(0)`) — 진행 중 계약·정기예금의 경과 이자 세금(평가액에서 빼는 그 값). `_saving_accrued`의 결과를 다시 계산하지 않고 그 자리에서 넣는다 (FR-011, data-model 4)
- [ ] T047 [US2] `backend/src/simulation/comparison_costs.py` — 적립식 둘·정기 적금 함수 (FR-011, research R13-3)
- [ ] T048 [US2] `backend/src/api/services/comparison_metrics.py` — 적립식 둘·정기 적금 정규화 (FR-011, FR-015, research R13-4)
- [ ] T049 [US2] 비교 경로 셋 — `backend/src/api/routes/comparison.py`(`/api/comparison/stocks/recurring-simulation`·`/crypto/recurring-simulation`·`/deposit/installment-simulation`) · `backend/src/api/routes/stock_recurring.py`·`crypto_recurring.py`(`_prepare_or_collect`를 공개 이름 `prepare_or_collect`로 — 호출부만 바꾼다) (FR-006, FR-011, contracts/rest-api.md 1)
  - 질의는 `routes/stock_recurring.py:68-83`, `routes/crypto_recurring.py:146-159`, `routes/deposit_installment.py:117-124`와 같다(+ `maxPoints`). 요약 JSON은 `services/stock_recurring.summary_json`,
    `routes.crypto_recurring.summary_json`, `routes.deposit_installment`의 요약 함수. 시계열은 `recurring_series.build_stock_series`·`build_crypto_series`·`build_installment_series`.
- [ ] T050 [US2] 화면 — `frontend/src/lib/compareApi.ts`(적립식·정기 적금 짝) · `frontend/src/stores/compareStore.ts`(방식·주기) · `frontend/src/components/compare/CompareConditionForm.tsx`(`InvestmentModeFields`·`ProductPicker`, 금액 라벨 `amountLabel`) · `CompareTable.tsx`(총 납입 원금 · N회) (FR-006, FR-007, FR-011, F3·F5)
- [ ] T051 [US2] 검증 — quickstart 5-7(+ 정기 적금 시중은행·상호금융 비교) (FR-006, SC-001)
  - quickstart 실행 기록에 적는다.

**Checkpoint**: US2 완결 — 일곱 방식 모두 비교된다.

---

## Phase 5: User Story 3 - 그래프로 비교한다 (Priority: P2)

**Goal**: 결과 표 아래에 대상별 수익률 추이(보유 중 선 + 기준일의 보유 중·매도 후 점)와 최종 지표 막대가 보인다.

**Independent Test**: US1의 결과에서 그래프를 본다. 대상 셋의 선이 색·선 모양·이름으로 구별되고, 기준일에 매도 후 점이 있으며, 최종 지표의 값이 표와 같다(spec US3
Independent Test, quickstart 5-10).

### Tests for User Story 3 ⚠️

- [ ] T052 [P] [US3] `frontend/tests/CompareReturnChart.test.tsx` — `components/compare/CompareReturnChart` (FR-015, SC-005, research R13-5, F6)
  - 파일 안 인라인 모의(`createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`·`LineSeries`만).
  - 대상마다 `splitSeriesAtGaps` 구간 선, 값은 `returnRate`. 잠정 구간은 연한 색.
  - 시계열 마지막 날 < `lineEnd.date`면 그 날에 보유 중 점을 더한다. 같으면 더하지 않는다.
  - `afterSaleReturnRate`가 있을 때만 점만 그리는 시리즈(`lineVisible: false`, `pointMarkersVisible: true`)를 기준일 하나로 더한다.
  - 대상 10개 → 색 10개가 모두 다르고 선 모양(수)이 번갈아. 범례에 이름(`compare-legend`), 설명 글자 "선: 보유 중(매도 전) · 끝 점: 매도 후"(`compare-basis`).
  - 붙잡은 커서 처리기에 `{time, point, sourceEvent}`를 주면 상자(`compare-hover`)가 대상마다 값을, 없는 대상은 "값 없음"을, 기준일엔 두 값을 보인다. 자리는 `sourceEvent` 좌표.
- [ ] T053 [P] [US3] `frontend/tests/CompareMetricBars.test.tsx` — `components/compare/CompareMetricBars` (FR-015, SC-005, research R13-12, F7)
  - 수익률 묶음·투자 수익 묶음. 글자 값 = 표와 같은 형식 함수의 출력(`formatPercent`·원화 형식). `null`이면 막대 없이 "—". 음수는 기준선 왼쪽. 차례 = 받은 차례.
  - `provisional`이 있는 대상은 이름 곁에 ⏳(표와 같은 글자 — 원칙 V).
- [ ] T054 [P] [US3] `frontend/tests/ComparePageCharts.test.tsx` — 화면의 그래프 (FR-012a, FR-013, FR-015)
  - `ok` 대상만 그래프·막대에 있다. 수집 중 대상은 완료 뒤 더해진다. 막대 차례가 표의 지금 정렬을 따른다. 흐린 동안 그래프·막대도 흐리다.

### Implementation for User Story 3

- [ ] T055 [US3] `frontend/src/components/compare/CompareReturnChart.tsx`(신규) — 색 10개 팔레트·선 모양 번갈아(수 상수 — 열거형을 실행 중에 읽지 않는다), `lineEnd` 점, 커서 상자(`lib/chartHover`의 자리 계산 — `sourceEvent` 좌표), 높이 360 (FR-015, F6)
- [ ] T056 [US3] `frontend/src/components/compare/CompareMetricBars.tsx`(신규) — DOM 막대, 길이만 그리기 전용 `Number`, 잠정 대상 ⏳ (FR-015, F7)
- [ ] T057 [US3] `frontend/src/stores/compareStore.ts`(정렬 상태 `sort`를 스토어로 — 표와 막대가 함께 쓴다) · `frontend/src/app/compare/page.tsx`(표 아래 그래프 둘, 흐림 적용) · `CompareTable.tsx`(정렬 상태를 스토어에서) (FR-012, FR-015)
- [ ] T058 [US3] 검증 — quickstart 5-10 (FR-015, SC-005)
  - quickstart 실행 기록에 적는다.

**Checkpoint**: US3 완결 — 그래프의 끝 값이 표와 같다.

---

## Phase 6: User Story 4 - 비교 시뮬레이션을 저장하고 다시 불러온다 (Priority: P3)

**Goal**: 실행한 비교를 이름을 붙여 로컬 DB에 저장하고(지울 때까지), 목록에서 불러와 지금 데이터로 다시 실행하고, 지운다.

**Independent Test**: US1의 비교를 저장하고 화면을 새로 연다. 저장한 비교를 불러오면 같은 자산군·대상·조건으로 다시 실행된다. 다른 브라우저에서도 같은 목록이 보인다
(spec US4 Independent Test, quickstart 2·5-8·5-11).

### Preparation for User Story 4

- [ ] T059 [US4] 개발 DB에 새 리비전을 올릴 준비 — T003의 머리(`a6d2f9c41b83`)가 그대로인지 다시 본다(다른 작업이 리비전을 더했으면 멈추고 보고한다) (data-model 1)
- [ ] T060 [US4] 화면 테스트 대역 — `frontend/tests/support/savedComparisonStub.ts`(신규 — 메모리 안 `GET`·`POST`·`DELETE /api/comparison/saved`, 도우미 `seed`·`entries`·`fail`·`heal`·`calls`) · `frontend/tests/setup.ts`(**더하기만** — 이력 대역 곁에 `/api/comparison/saved*` 처리와 `beforeEach` 비우기) (FR-016~FR-019)
  - 비교 화면이 저장 목록을 받기 시작하는 T077보다 먼저다 — 대역 없이 화면을 바꾸면 US1~US3 화면 테스트가 실제 `fetch`로 흘러간다.

### Tests for User Story 4 ⚠️

- [ ] T061 [P] [US4] `backend/tests/unit/test_comparison_conditions.py` — `api/services/comparison_conditions` (FR-004, FR-016, SC-006, data-model 2)
  - `v`는 1만. `asset`은 `stock`·`crypto`·`deposit`·`realestate`. `method` 짝(주식·가상자산 `lump_sum`·`recurring`, 예금 `deposit`·`installment`, 부동산 `hold`).
  - `frequency`: `recurring`이면 `daily`·`weekly`·`monthly`·`yearly`, 그 밖은 `null`. `start`는 `YYYY-MM-DD`.
  - `amount`: `[0-9]+(\.[0-9]+)?`, > 0, 예금 둘은 정수, 부동산은 `null`. **받은 글자 그대로** 남는다(`"10000000"`이 수가 되지 않는다).
  - `principalCurrency`: 주식·가상자산은 `KRW` 또는 모든 대상의 `currency`가 같을 때 그 통화, 예금·부동산은 `KRW`. `reinvest`는 주식만 bool, 그 밖은 `null`.
  - `targets`: 2~10개, 예금 ≤5, 정기 적금은 `commercial_bank`·`mutual_finance`만, 같은 대상 키(주식 `market|symbol`, 가상자산 `coinId`, 예금 투자처, 부동산 `complexId|area`)가 두 번이면 거절.
    대상 칸은 data-model 2 표 그대로(부동산 `area`는 `10`·`20`·`30k`·`30l`·`40`·`50`·`60`).
  - 이름: 앞뒤 공백을 뺀 1~100자.
  - 알려진 칸만 남는다 — 결과 키(`summary`·`comparison`·`series`)는 버려진다. 직렬화는 `json.dumps(…, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`.
  - 거절 메시지가 칸을 밝힌다. 모듈에 `*`·`/`·`//`·`.quantize`가 없다(012 `test_history_conditions`의 금액 비계산 검사와 같은 매개 검사에 이 모듈을 더하는 대신 이 파일에서 같은 검사).
- [ ] T062 [P] [US4] `backend/tests/integration/test_saved_comparison_schema.py` — 테이블 (FR-016, data-model 1)
  - 열이 정확히 `id`·`name`·`asset_class`·`condition`·`saved_at`. `id` `bigint` 자동 증가 PK, `name` `varchar(100)` NOT NULL, `asset_class` `varchar(16)` NOT NULL,
    `condition` `text` NOT NULL, `saved_at` `datetime` NOT NULL. 색인 `ix_saved_comparison_list (saved_at, id)`. 처음 0행.
  - 하향(`a6d2f9c41b83`) 뒤 `saved_comparison`만 없어지고 `simulation_history`·`history_setting`은 남는다. 재상향.
- [ ] T063 [P] [US4] `backend/tests/integration/test_saved_comparison_api.py` — `/api/comparison/saved` (FR-016, FR-017, FR-018, FR-019, SC-006, contracts/rest-api.md 2~5)
  - `GET` 빈 목록 `{"entries": []}`. `POST` 201 `{entry, entries}`. 같은 조건·이름을 두 번 저장하면 두 행.
  - 차례: `savedAt` 내림차순, 같은 초는 `id` 내림차순(`api/services/saved_comparison.utc_now`를 바꾼다). `savedAt`은 `%Y-%m-%dT%H:%M:%SZ`.
  - `DELETE /{id}` 200 남은 목록, 없는 `id`도 200, 정수가 아닌 `id`는 422.
  - 검증 실패 422 `{"status": "invalid_comparison", "message": …}`.
  - 이력 보관 기간을 7일로 바꾸고(`PUT /api/history/settings`) 시각을 1년 뒤로 옮겨도 저장한 비교가 남는다(보관 기간 없음).
- [ ] T064 [P] [US4] `frontend/tests/HistoryStatesEmptyText.test.tsx` — `components/history/HistoryStates.HistoryContent`의 빈 목록 문구 속성 (F9)
  - 속성이 없으면 지금 문구("아직 실행한 시뮬레이션이 없습니다."), 주면 그 문구.
- [ ] T065 [P] [US4] `frontend/tests/SavedComparisons.test.tsx` — `components/compare/SavedComparisons` (FR-016~FR-019, F9)
  - 줄: 이름, "자산군 · 대상 이름들"(셋 넘으면 "외 N개"), 시작일·방식, 저장 시각(`formatKst`). "불러오기"(`aria-label="{이름} 불러오기"`)·"×"(`aria-label="{이름} 삭제"`).
  - 안내 "이 기기의 로컬 DB에 저장됩니다. 지울 때까지 남습니다." — 보관 기간 문장이 없다. 빈 목록 "아직 저장한 비교가 없습니다.".
  - 불러오기 실패 `role="alert"` + "다시 시도", 삭제·저장 실패 `role="alert"` 문구.
- [ ] T066 [P] [US4] `frontend/tests/SaveComparisonForm.test.tsx` — `components/compare/SaveComparisonForm` (FR-016, F9)
  - 열면 이름 칸에 자동 이름. 빈 이름(공백만)이면 저장 단추가 꺼진다. 취소. 저장은 앞뒤 공백을 뺀 이름으로 `onSave`.
- [ ] T067 [P] [US4] `frontend/tests/compareStoreSaved.test.ts` — 저장 슬라이스 (FR-012a, FR-016~FR-019, SC-006, SC-007, data-model 5.2)
  - 저장은 결과가 있고 흐리지 않고 막히지 않았을 때만(수집 중인 대상이 남아도 된다). 본문 = `run.condition`(정규 조건) + 이름.
  - 성공하면 `entries`가 응답 목록. 실패하면 `saveError`, 결과·실행 상태는 그대로.
  - 불러오기: 자산군·방식·입력·대상을 채우고 곧바로 실행(같은 질의). 불러온 대상이 지금 막히면(`unknown_coin`) 막힘 칸.
  - 삭제, 목록 받기 실패·다시 시도. 어디에서도 `/api/history` `PUT`이 없다.
- [ ] T068 [P] [US4] `frontend/tests/ComparePageSaved.test.tsx` — 화면 끝에서 끝까지(대역 T060) (FR-012a, FR-016~FR-019)
  - 실행 → 저장(이름 고침) → 목록에 보인다 → 다시 그려도(새 렌더) 목록이 있다 → 불러오면 같은 질의로 요청 → 삭제하면 빠진다.
  - 흐린 동안 저장 단추가 꺼지고 "다시 실행한 뒤 저장할 수 있습니다". 막힘이면 저장 단추가 꺼진다.

- [ ] T083 [P] [US4] `backend/tests/unit/test_saved_comparison_service.py` — 메모리 안 가짜 저장소(`SavedComparisonRepository` Protocol 충족)로 `api/services/saved_comparison` (FR-016, FR-018, SC-006, 헌법 원칙 IV)
  - 저장은 정규화된 조건 글과 이름을 저장소에 넘기고 201 본문 `{entry, entries}`를 만든다.
  - 검증 실패면 저장소를 부르지 않고 `InvalidComparison`.
  - 삭제는 없는 `id`도 저장소에 맡기고 남은 목록을 돌려준다.
  - (반복 2026-10-08 — `/speckit-analyze` C2로 더한 태스크. 번호는 이어 붙였다)

### Implementation for User Story 4

- [ ] T069 [US4] `backend/src/db/models.py`(`SavedComparison`) · `backend/src/db/migrations/versions/<rev>_저장한_비교.py`(`down_revision = "a6d2f9c41b83"`) (FR-016, data-model 1)
  - `id BigInteger PK autoincrement`, `name String(100) NOT NULL`, `asset_class Enum("stock","crypto","deposit","realestate", native_enum=False, length=16, name="comparison_asset_class") NOT NULL`,
    `condition Text NOT NULL`, `saved_at DateTime(timezone=False) NOT NULL`, `ix_saved_comparison_list (saved_at, id)`.
  - 마이그레이션 상수는 파일 안에 둔다(012 선례). 코드에 날짜 리터럴을 두지 않는다(`test_no_hardcoded_dates`).
  - 개발 DB에 `alembic upgrade head`를 올린다.
- [ ] T070 [US4] `backend/src/repository/saved_comparison.py`(신규) — `list_entries`(`saved_at` 내림차순, `id` 내림차순, `populate_existing`)·`add`(새 `id`를 돌려준다)·`remove`(없는 `id`도 조용히) — `SavedComparisonRepository` Protocol(T072)의 시그니처를 따른다 (FR-016, FR-018)
- [ ] T071 [US4] `backend/src/api/services/comparison_conditions.py`(신규, 순수) — data-model 2의 검증·정규화·직렬화, `InvalidComparison`(칸을 밝힌 메시지) (FR-004, FR-016, SC-006)
- [ ] T072 [US4] `backend/src/api/services/saved_comparison.py`(신규) — `class SavedComparisonRepository(Protocol)`(`list_entries`·`add`·`remove`)을 두고 목록·저장·삭제 함수가 저장소를 인자로 받는다(헌법 원칙 IV), `utc_now()`(테스트가 바꾼다), 목록·저장(201 본문)·삭제 본문, 각 함수가 커밋 (FR-016~FR-018)
- [ ] T073 [US4] `backend/src/api/routes/saved_comparison.py`(신규 — `GET`·`POST`·`DELETE /{id}`) · `backend/src/api/errors.py`(`InvalidComparison`) · `backend/src/api/main.py`(처리기 422 `invalid_comparison`, 저장 라우터를 비교 라우터보다 **먼저**) — 경로가 `src.repository.saved_comparison` 모듈을 서비스에 넘긴다 (contracts/rest-api.md 2~6)
- [ ] T074 [US4] `frontend/src/lib/compareApi.ts`(저장 경로 셋 — 공통 요청 함수) · `frontend/src/lib/types.ts`(`SavedComparison`·목록 응답) (FR-016~FR-018)
- [ ] T075 [US4] `frontend/src/components/history/HistoryStates.tsx` — `HistoryContent`에 선택 속성 `emptyText`(처음 값 = 지금 문구) (F9)
- [ ] T076 [US4] `frontend/src/components/compare/SaveComparisonForm.tsx`·`SavedComparisons.tsx`(신규) (FR-016~FR-019, F9)
- [ ] T077 [US4] `frontend/src/stores/compareStore.ts`(저장 슬라이스 — data-model 5.2, 불러오기 → 채우고 실행) · `frontend/src/app/compare/page.tsx`(`TableWithHistory` 배치 — 오른쪽 저장한 비교, 저장 단추·이름 칸) (FR-016~FR-019, F9)
- [ ] T078 [US4] 검증 — quickstart 2(저장 API 손 확인)·5-8·5-11 (FR-016~FR-019, SC-006)
  - 다른 브라우저 문맥에서 같은 목록이 보인다. 백엔드를 멈추면 목록 받기 실패와 다시 시도가 보인다.
  - 확인으로 만든 저장한 비교를 지우고 전후 목록이 같음을 본다. quickstart 실행 기록에 적는다.

**Checkpoint**: US4 완결 — 저장한 비교가 지울 때까지 남고, 불러오면 같은 조건으로 다시 실행된다.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T079 성능을 잰다 (SC-004, research R13-13, quickstart 4)
  - 받아 둔 주식 10개(국내·미국 섞음) × 20년 일시금 원화, 원화 원금 가상자산 10개 × 가능한 최장 일시금 — "비교 실행"부터 표·그래프가 다 보일 때까지.
  - 5초 넘으면 대상별 응답 시간을 기록하고 멈추고 보고한다.
- [ ] T080 불변 대조 (FR-020, SC-009, quickstart 6)
  - 서버를 띄우고 T001의 입력으로 메뉴 경로를 다시 받아 `summary`·`condition`·`/series`를 견준다. 표 `rows`는 견주지 않는다.
  - 다른 키·값이 있으면 멈추고 보고한다(부동산은 같은 KST 날짜이거나 날짜 차이만이어야 한다).
- [ ] T081 문서를 갱신한다
  - `CLAUDE.md` "현재 상태" 표에 013 한 줄을 더한다.
  - 주의 문단: 비교 경로는 메뉴 경로의 짝이고 같은 함수를 같은 차례로 부른다, 비교는 이력을 쓰지 않는다, 비용 몫(`simulation/comparison_costs.py`)과 `accrued_tax`·`open_tax`,
    `resolve_rate` 이분 탐색, `saved_comparison`(보관 기간 없음 — 개발 DB `alembic upgrade head`), 저장 라우터를 먼저 등록, 부동산 스토어 생성기의 비교 인스턴스, 비교 스토어의 대상별 구독,
    화면 테스트의 저장 대역(`tests/setup.ts`).
  - `README.md` 기능 설명, `spec.md` Status.
- [ ] T082 품질 게이트를 돌린다(서버를 내린 채) — 백엔드 `pytest -q --cov=src`(커버리지 80% 이상)·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .` (헌법 품질 게이트, SC-009)
  - 통과 수와 종료 코드를 Notes에 적는다.
  - 이 기능 전 커밋(`71003d4`)과 견주어 바뀌거나 지워진 기존 테스트 파일이 승인 목록(T006·T039)과 `tests/setup.ts`(더하기만)뿐인지 `git diff --stat --diff-filter=MD`로 확인한다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작한다. **T001·T002는 다른 모든 코드 변경보다 먼저다.**
- **Foundational (Phase 2)**: T002 뒤. 기능상으로 스토리를 막지 않지만 T079(성능)가 기댄다.
- **US1 (Phase 3)**: T002 뒤. **T006(승인)이 T022와 이 페이즈의 테스트 커밋을 막는다.** 백엔드(T007~T011·T023~T027)와 화면(T012~T021·T028~T037)은 나란히 할 수 있다. MVP다.
- **US2 (Phase 4)**: US1 뒤(같은 비교 경로 모듈·스토어·부품). **T039(승인)가 이 페이즈의 테스트 커밋을 막는다.**
- **US3 (Phase 5)**: US1 뒤. US2와는 파일이 겹친다(`compareStore.ts`·`page.tsx`·`CompareTable.tsx`) — 차례로 한다.
- **US4 (Phase 6)**: 백엔드(T061~T063·T083·T069~T073)는 T002 뒤면 시작할 수 있다. 화면(T064~T068·T074~T077)은 US1 뒤, **T060(대역)이 T077보다 먼저다.**
- **Polish (Phase 7)**: 모든 스토리 뒤

스토리를 하나씩 끝내려면 US1 → US2 → US3 → US4 차례다.

### Within Each Phase

- 테스트(⚠️) 작성 → 구현(작업 트리) → 전체 스위트로 **실제로 실패한** 기존 테스트 목록 → 승인(있으면) → 승인된 기존 테스트 수정 → 구현을 치우고
  (`git stash push -u -- backend/src frontend/src`) 최초 실패 확인 → 테스트 커밋(최초 실패 요약) → 구현 되돌림 → 구현 커밋(통과 결과)
- 승인할 목록이 없을 것이 분명한 페이즈(US3·US4)는 구현 전에 테스트를 커밋해도 된다 — 구현 뒤 목록 밖의 실패가 나오면 결함으로 보고 멈춘다
- 백엔드는 순수 계산 → 저장소 → 서비스 → 라우트, 화면은 순수 함수·부품 → 스토어 → 화면 순서다.

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/simulation/comparison_costs.py` | T024(US1), T047(US2) |
| `backend/src/api/services/comparison_metrics.py` | T025(US1), T048(US2) |
| `backend/src/api/routes/comparison.py` | T026(US1), T049(US2) |
| `backend/src/api/main.py` | T027(US1), T073(US4) |
| `frontend/src/lib/types.ts` | T028(US1), T074(US4) |
| `frontend/src/lib/compareApi.ts` | T034(US1), T050(US2), T074(US4) |
| `frontend/src/stores/compareStore.ts` | T035(US1), T050(US2), T057(US3), T077(US4) |
| `frontend/src/app/compare/page.tsx` | T037(US1), T057(US3), T077(US4) |
| `frontend/src/components/compare/CompareTable.tsx` | T036(US1), T050(US2), T057(US3) |
| `frontend/src/components/compare/CompareConditionForm.tsx` | T036(US1), T050(US2) |
| `frontend/src/stores/realEstateStore.ts`·`stockStore.ts` | T033, T032 |
| `frontend/tests/setup.ts`(더하기만) | T060 |
| `specs/013-…/quickstart.md`(실행 기록) | T038, T051, T058, T078, T079, T080 |

### Parallel Opportunities

- Foundational T004는 혼자다.
- US1 테스트 T007~T021은 다른 파일이라 함께 쓴다. 구현의 순수 모듈 T029~T031도 함께 한다.
- US2 테스트 T040~T045는 함께 쓴다.
- US3 테스트 T052~T054는 함께 쓴다.
- US4 테스트 T061~T068·T083은 함께 쓴다(화면 쪽은 T060 뒤). US4 백엔드는 US1 화면 작업과 나란히 할 수 있다.

---

## Parallel Example: Phase 3 (US1 테스트)

```text
Task: "T007 test_deposit_accrued_tax.py — 진행 중 회차의 경과 세금"
Task: "T008 test_comparison_costs.py — 일시금·정기예금·부동산 비용 몫"
Task: "T009 test_comparison_metrics.py — 주 값·현재 가치·원금·잠정·환율·lineEnd"
Task: "T010 test_comparison_identity.py — 비교 경로 넷 ↔ 메뉴 경로"
Task: "T011 test_comparison_api.py — comparison 블록과 메뉴 값의 짝"
Task: "T012 decimalOrder.test.ts · T013 compareCondition.test.ts · T014 compareBlock.test.ts"
Task: "T015 registerStock.test.ts · T016 compareRealEstatePicker.test.ts · T017 InstitutionChecklist.test.tsx"
Task: "T018 compareStore.test.ts · T019 CompareTable.test.tsx · T020 ComparePage.test.tsx · T021 compareNoClientFinance.test.ts"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1(기준 응답·기준 게이트·DB 머리) → Phase 2(환율 찾기 이분 탐색)
2. Phase 3 (US1) — **멈추고 검증**(T038): 주식·가상자산 일시금·정기예금·부동산의 비교 표가 메뉴와 같은 값이고, 막힘·수집 중·흐림이 동작하며, 이력이 그대로다.

### Incremental Delivery

1. MVP(US1) — 같은 조건의 비교 표(승인 A — T006)
2. US2 — 적립식·정기 적금(승인 B — T039)
3. US3 — 그래프
4. US4 — 저장·불러오기
5. Polish — 성능·불변 대조·문서·게이트

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(013): <페이즈>`
     - 그 페이즈의 새 테스트와 **승인된 기존 테스트 변경**을 담는다(승인 날짜를 적는다).
     - **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는 예정된 것이다.
     - 구현을 먼저 해 둔 경우(승인 목록을 만들려고)는 구현을 잠시 치워(`git stash push -u -- backend/src frontend/src`) 실패를 확인한 뒤 커밋하고 되돌린다(012와 같다).
  2. **구현 커밋** — `feat(013): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다.
  - 테스트가 없는 태스크만 있는 페이즈(기준 기록, 브라우저 확인, 문서)는 한 번 커밋한다(`docs(013): …`).
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다.** 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2).
- 설계 중 spec이 바뀌면(FR·SC) plan의 추적성 표와 이 파일의 참조를 같은 작업 단위에서 고친다(헌법 명세 작성 규약).
- 커밋 전에 비밀 검사 스크립트를 돌린다. `.env`가 추적되지 않는지, 스테이징된 내용에 키·DB 비밀번호가 없는지, `.venv/`·`node_modules/`·`.next/`·`logs/`
  경로가 없는지 본다.
- 개발 서버를 띄운 채 통합 테스트를 돌리지 않는다(같은 MySQL 스키마를 다시 만든다).
- **2026-10-08 T001 기준 응답**: 저장소 밖 작업 폴더(`013-baseline/before/`)에 메뉴 표 경로 첫 쪽의 머리(`rows` 제외)와 `/series`를 저장했다(`end=2026-09-30` 고정).
  주식 KRX 005930.KS·NYSE XLK(원화 원금), 가상자산 BTC, 정기예금 시중은행, 부동산 헬리오시티 30평대, 적립식 주식(국내 매달)·가상자산(매일), 적금 시중은행 — 8개. 12:34Z
- **2026-10-08 T002 기준 게이트(서버를 내린 채)**: 백엔드 2,838 passed(커버리지 96.14%, 8분 56초), mypy 230 파일·ruff(`--no-cache`) 통과 / 프론트엔드
  166 파일·1,421 passed, tsc·eslint — 모두 종료 코드 0
- **2026-10-08 T003**: 개발 DB 머리 리비전 `a6d2f9c41b83`(head)
- **2026-10-08 T006 승인(사용자)**: 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만들었다 — 백엔드 0건(2,915 passed,
  커버리지 96.36%), 화면 6건(2개 파일) — 모두 research R13-16 목록 안이고 까닭은 FR-001(투자 비교가 링크가 됨) 하나다. `Sidebar.test.tsx` 넷(준비 안 된 항목
  `["대시보드"]`, 준비중 1개, 포커스 예 "대시보드", 링크 목록에 `/compare`), `noUnbuiltAssetRoutes.test.ts` 둘(`UNBUILT = ["dashboard"]`, 사이드바 경로에 `/compare`).
  같은 파일의 API 호출 검사(`/api/(compare|dashboard)\b`)는 실패하지 않아 그대로 둔다(비교 경로는 `/api/comparison`). `TopBarTitle.test.ts`는 고치지 않고 통과.
  고친 줄 위에 `013 승인 2026-10-08` 주석
- **2026-10-08 T015 파일 이름**: 새 테스트를 처음에 `tests/stockSelection.test.ts`로 만들다 006의 같은 이름 테스트(메뉴 스토어의 등록)를 덮어쓴 것을 곧바로 알아챘다 —
  `git checkout`으로 되돌리고 새 테스트는 `tests/registerStock.test.ts`로 따로 두었다(기존 파일 변경 없음)
- 커밋 메시지는 한국어이고 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`을 단다. 푸시는 요청이 있을 때만 한다.

## 요구사항 ↔ 태스크

모든 FR·SC가 하나 이상의 태스크에 참조된다(헌법 명세 작성 규약).

| 요구사항 | 태스크 |
|----------|--------|
| FR-001 | T006, T020, T022, T037, T038 |
| FR-002 | T018, T020, T035, T036 |
| FR-003 | T015, T016, T017, T020, T032, T033, T036, T038 |
| FR-004 | T013, T017, T018, T020, T030, T035, T036, T061, T071 |
| FR-005 | T010, T019, T026, T036 |
| FR-006 | T039, T043, T044, T045, T049, T050, T051 |
| FR-007 | T013, T030, T036, T044, T045, T050 |
| FR-008 | T010, T026, T036, T038 |
| FR-009 | T010, T018, T026, T034, T035 |
| FR-010 | T014, T018, T020, T031, T035, T036, T038, T044 |
| FR-011 | T007, T008, T009, T010, T011, T019, T021, T023, T024, T025, T026, T027, T028, T036, T040, T041, T042, T043, T045, T046, T047, T048, T049, T050 |
| FR-012 | T012, T019, T029, T036, T057 |
| FR-012a | T013, T018, T020, T030, T035, T036, T044, T054, T057, T067, T068 |
| FR-013 | T014, T018, T019, T020, T031, T035, T036, T054 |
| FR-014 | T014, T019, T020, T031, T036 |
| FR-015 | T009, T025, T042, T048, T052, T053, T054, T055, T056, T057, T058 |
| FR-016 | T060, T061, T062, T063, T064, T066, T067, T068, T069, T070, T071, T072, T073, T074, T075, T076, T077, T078, T083 |
| FR-017 | T063, T067, T068, T077, T078 |
| FR-018 | T063, T065, T067, T068, T070, T072, T073, T074, T076, T078, T083 |
| FR-019 | T063, T065, T067, T068, T076, T077, T078 |
| FR-020 | T001, T010, T018, T026, T035, T043, T067, T080 |
| SC-001 | T007, T008, T009, T010, T011, T038, T040, T041, T043, T051 |
| SC-002 | T010, T018, T043 |
| SC-003 | T014, T018, T038 |
| SC-004 | T004, T005, T079 |
| SC-005 | T009, T052, T053, T058 |
| SC-006 | T061, T063, T067, T071, T078, T083 |
| SC-007 | T010, T018, T038, T067 |
| SC-008 | T020, T038 |
| SC-009 | T001, T002, T004, T080, T082 |
