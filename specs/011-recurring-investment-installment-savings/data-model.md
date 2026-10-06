# Data Model: 주식·가상자산 적립식 투자, 예금 정기 적금, 주식 매도 세금 설정 (011)

**Date**: 2026-10-06 | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

계산 결과는 저장하지 않는다(005 R5-9). 이 문서는 (1) 새로 저장하는 것, (2) 순수 계산의 입출력, (3) 브라우저 이력 항목을 적는다. 금액·비율은 모두
`Decimal`이고 API 경계에서는 문자열이다(헌법 원칙 VI).

## 1. 저장

### 1.1 `stock_setting` — 열 셋 추가 (마이그레이션 1개, `down_revision = "e3b9c4d27f61"`)

| 열 | 타입 | NULL | 뜻 | 기본값(코드 — NULL이면) |
|----|------|------|----|------------------------|
| `sale_tax_rate_domestic` | `SPREAD` Numeric(9,6) | 허용 | 국내 매도 세율(증권거래세 + 농어촌특별세 실질) | `Decimal("0.0020")` |
| `capital_gains_rate_foreign` | `SPREAD` | 허용 | 해외 양도소득세율(지방소득세 포함) | `Decimal("0.22")` |
| `capital_gains_deduction_foreign` | `WON` Numeric(15,0) | 허용 | 해외 연간 기본공제(원) | `Decimal("2500000")` |

- **NULL = 기본값**이다 — 010 반복 5의 `apt_setting.residence_ratio`와 같은 규칙. 기존 행(수수료·배당 세율만 저장한 행)은 그대로 읽힌다.
- 기본값의 자릿수는 010 반복 4의 표 값과 같다 — 기본 설정의 보드 응답 문자열이 바뀌지 않는다(research R11-7).
- 검증: 세율 `0 ≤ x < 1`, 소수 6자리 이하. 공제 `0 ≤ x`, 정수 원, 15자리 이하. 벗어나면 저장하지 않는다(422 `invalid_setting`).
- 저장소 함수(새로): `get_sale_tax(session) -> SaleTaxSettings`, `save_sale_tax(session, *, domestic, foreign_rate, foreign_deduction)`.
  `SaleTaxSettings(domestic, foreign_rate, foreign_deduction, is_default)`. 기존 `get_settings`·`save_settings`는 바뀌지 않는다.

### 1.2 예금 금리 — 새 금리 계열 키 (스키마 변경 없음)

`deposit_rate`·`deposit_coverage`·`deposit_collection_job`·`deposit_collection_lock`·`deposit_raw_response`의 `institution` 열은 이제 **금리 계열 키**다
(research R11-2). 값의 뜻:

| 키 | 투자처 | 상품 |
|----|--------|------|
| `commercial_bank`, `savings_bank`, `credit_union`, `mutual_finance`, `saemaul` | 그 투자처 | 1년 정기예금(008 그대로) |
| `commercial_bank_isav` | 시중은행 | 정기적금(1-2년) |
| `mutual_finance_isav` | 상호금융 | 정기적금(만기 구분 없음) |

- 금리·커버리지의 규칙(발표된 달만 저장, 받은 구간, `checked_on`은 성공 때만, 겹쳐 받은 달의 수정은 사건만)은 008 그대로다.
- (투자처, 상품) → 계열 키의 대응은 예금 서비스에 있다. 계열 키 → 출처 항목의 대응은 ECOS 어댑터에만 있다(`INSTALLMENT_SERIES`).

## 2. 순수 계산 (`backend/src/simulation/`)

모두 DB·HTTP 없이 단독으로 검사한다(헌법 원칙 IV). 이름은 구현에서 바뀔 수 있으나 칸의 뜻은 이 표를 따른다.

### 2.1 `contribution_schedule.py` — 납입 일정·납입마다의 환전 (주식·가상자산)

| 이름 | 칸 | 뜻 |
|------|----|----|
| `Frequency` | `"daily" \| "weekly" \| "monthly" \| "yearly"` | 주기 |
| `scheduled_dates(start, end, frequency, *, trading_days)` | → `list[date]` | 예정일(R11-3). `daily`면 `trading_days`(주식) 또는 달력일(가상자산 — 호출부가 정한다) |
| `ScheduledContribution` | `on: date`, `scheduled: tuple[date, ...]` | 실제 납입일과 거기로 모인 예정일들(첫째가 그날이면 미뤄짐 없음) |
| `assign(scheduled, available_days)` | → `(list[ScheduledContribution], pending_after_end: int)` | 예정일 → 시세가 있는 첫날. 계산 끝까지 날이 없으면 `pending_after_end`로 센다 |
| `Contribution` | `on`, `scheduled`, `amount: Decimal`(종목·코인 통화), `basis_krw: Decimal`(원화 분모 증분), `fx_rate: Decimal \| None`, `fx_rate_date: date \| None`, `fx_kind: "cash_buy_discounted" \| "base" \| None` | 납입 하나(R11-5). 예정일 n개가 모였으면 금액은 납입액 × n |
| `fund(contributions, amount, *, principal_currency, quote_currency, lookup, spread)` | → `list[Contribution]` | 환전·원화 분모. 그날 이전 확정 환율이 없으면 `FxUnavailable` 성격의 예외 |

### 2.2 `recurring_stock.py` — 주식 적립식

| 이름 | 칸 |
|------|----|
| `RecurringCondition` | `fee_rate`, `tax_rate`(배당 소득세), `reinvest: bool`, `reinvest_lag_days: int`(기본값 없음 — 2) |
| `RecurringRow` | `date`, `kind: "contribution" \| "dividend" \| "reinvest" \| "month_first"`, `open_price`, `close_price`, `contribution: Decimal \| None`(그 행의 납입액 — 납입 행만), `deferred: tuple[date, ...]`(그 행으로 미뤄진 원래 예정일 — 그날 예정분 제외), `bought_shares: int`, `held_shares: int`, `pending: Decimal`(매수 대기금), `dividend_cash: Decimal`(배당 현금 — 매수 대기금에 아직 들어가지 않은 세후 배당. 재투자 켬이면 재투자일에 비워진다), `contributed: Decimal`(누적 납입, 종목 통화), `basis_krw: Decimal`(누적 원화 분모), `balance`(= 보유 × 종가), `total`(= 잔고 + 매수 대기금 + 배당 현금), `trade_fee: Decimal \| None`, `dividend_per_share`, `dividend_total`, `dividend_tax`, `dividend_total_net`(배당 행만), `fx_rate`·`fx_rate_date`(납입 행 — 환전 또는 평가에 쓴 값) |
| `RecurringOutcome` | `rows`(최신순), `latest: RecurringRow \| None`(마지막 거래일의 평가 — 보드), `pending_after_end: int`, `buy_fee_total`, `dividend_tax_total`(종목 통화 — 원화 합은 서비스가 행 환율로) |
| `simulate_recurring_stock(bars, dividends, splits, contributions, condition)` | → `RecurringOutcome` |

불변식(단위 테스트): 모든 매수 뒤 `pending < 1주 × 시가 × (1 + 수수료율)`(SC-003), `pending ≥ 0`, `dividend_cash`는 매수에 쓰이지 않는다 — 재투자 켬이면
재투자일에만 매수 대기금으로 옮겨진다(SC-004, 분석 B1),
`contributed`의 마지막 값 = 납입액 × 실제로 넣은 예정일 수(SC-002).

### 2.3 `recurring_crypto.py` — 가상자산 적립식

| 이름 | 칸 |
|------|----|
| `RecurringCryptoRow` | `date`, `kind: "contribution" \| "month_first"`, `open_price`, `contribution`, `deferred`, `bought_quantity`(소수 8자리), `held_quantity`, `pending`, `contributed`, `basis_krw`, `balance`(= 보유 × 시가), `total`, `trade_fee`, `fx_rate`, `fx_rate_date`, `first_day_missing: date \| None`(007과 같다) |
| `RecurringCryptoOutcome` | `rows`(최신순), `latest`, `daily`(오름차순 — 일봉마다 평가, 차트), `pending_after_end`, `buy_fee_total` |
| `simulate_recurring_crypto(bars, contributions, *, fee_rate, first_available)` | → `RecurringCryptoOutcome` |

### 2.4 `stock_sale_cost.py` — 세율 인자로 (변경)

`domestic_sale_cost(sale_krw, *, fee_rate, tax_rate) -> SaleCost`, `foreign_sale_cost(*, sale_krw, sell_fee_krw, acquisition_krw, buy_fees_krw, rate,
deduction) -> SaleCost`. `SaleCost`(fee, tax, total, tax_kind `"transaction_tax" | "capital_gains_tax"`, tax_rate, gain, deduction)는 그대로이고 `tax`·`total`은
이제 늘 값이 있다. 원 미만 버림(`floor_won`)은 그대로다. `TRANSACTION_TAX`·`CAPITAL_GAINS`·`transaction_tax_rate`·`OUTSIDE_KIND`는 없어진다.

### 2.5 `crypto_sale_cost.py` — 가상자산 매도 비용 (새)

`CryptoSaleCost(fee: Decimal, tax: Decimal | None, total: Decimal | None, tax_kind: "not_yet_taxed" | "outside_rules")`.
`crypto_sale_cost(sale_krw, *, fee_rate, day)` — 수수료 = floor(평가액 × 수수료율). 세금 = 시행일(2027-01-01) 전이면 0, 그 뒤면 `None`. 시행일은 이 모듈의 법령
상수다(`_LEGAL_DATE_MODULES` — 승인 필요, research R11-7).

### 2.6 `installment_ladder.py` — 적금 → 정기예금 사다리

| 이름 | 칸 |
|------|----|
| `InstallmentContract` | `no`, `joined_on`, `matures_on`, `rate`, `rate_month`, `provisional`, `monthly: Decimal`, `paid: int`(낸 회차 수 — 만기면 12), `interest`, `tax`, `after_tax`, `amount`(만기 금액 = 납입 합 + 세후 이자 — 만기된 계약만) |
| `LadderDeposit` | `no`, `joined_on`, `matures_on`, `rate`, `rate_month`, `provisional`, `principal`, `from_deposit: Decimal`(앞 정기예금의 만기 금액 — 첫 정기예금은 0), `from_installment: Decimal`(그날 만기된 적금의 만기 금액), `interest`, `tax`, `after_tax` |
| `LadderRow` | `date`, `kind: "installment" \| "month" \| "installment_maturity" \| "deposit_maturity" \| "deposit_join"`, `installment_no: int \| None`(회차 1..12 — 납입 행), `contract_no`, `amount`(그 행의 납입액·만기 금액·가입 원금), `rate`, `rate_month`, `provisional`, `interest`, `tax`, `after_tax`(만기 행), `contributed`(누적 납입 — 새 돈만), `installment_value`(적금 쪽 평가), `deposit_value`(정기예금 쪽 평가), `balance`(= 둘의 합), `profit`, `return_rate` |
| `LadderSummary` | `contributed`, `interest_total`, `tax_total`, `after_tax_total`, `balance`, `installment_value`, `deposit_value`, `profit`, `return_rate`, `as_of`, `is_final`, `provisional_from`, `stopped: Stopped \| None`(008 `Stopped` 그대로), `current_installment`, `current_deposit` |
| `simulate_installment_ladder(*, monthly, start, end, installment_rates, installment_first, installment_latest, deposit_rates, deposit_first, deposit_latest, tax_rate)` | → `LadderOutcome(contracts, deposits, rows(최신순), summary)` |

예외: `BeforeFirstMonth(startable_from)` — 시작 가능 날짜는 max(적금 첫 달, 정기예금 첫 달 − 1년)(R11-9). `RateMissing(month)` — 첫 적금의 가입 달이 결측이다.
같은 날의 행 순서(최신순 표에서 위 → 아래): 새 적금 첫 회 납입 → 정기예금 가입 → 정기예금 만기 → 적금 만기.

## 3. 브라우저 이력 (`frontend/src/lib/*History.ts`, `localStorage` `:v1` 그대로)

| 이력 | 더하는 선택 칸 | 없을 때의 뜻 | 항목 식별자 |
|------|----------------|--------------|-------------|
| 주식 `HistoryCondition` | `mode?: "recurring"`, `frequency?: Frequency` | 일시금 | 일시금은 지금 그대로. 적립식은 뒤에 `\|recurring:{frequency}` |
| 가상자산 `CryptoHistoryCondition` | 같음 | 일시금 | 같음 |
| 예금 `DepositHistoryCondition` | `product?: "installment"` | 정기예금 | 적금은 뒤에 `\|installment` |

- 금액 칸(`principal`)은 방식에 따라 뜻이 바뀐다 — 일시금 원금 / 적립식 한 번 납입액 / 적금 월 납입액.
- 다시 실행은 빠진 칸을 기본값으로 채운다(`mode ?? lump_sum`, `frequency ?? "monthly"`, `product ?? "deposit"`) — `undefined`가 입력으로 복사되지 않는다.
- 알 수 없는 `frequency`·`product` 값(손으로 고친 저장소 등)은 서버가 400으로 막고 화면이 사유를 보인다(spec FR-002) — 화면이 기본값으로 바꾸지 않는다.

## 4. 화면 상태 (`frontend/src/stores/`)

| 스토어 | 더하는 상태 | 뜻 |
|--------|-------------|----|
| `stockStore` | `plan: {mode: "lump_sum" \| "recurring", frequency: Frequency}` | 투자 방식. `input`(다섯 칸)은 그대로 |
| | `recurring: RecurringResult \| null` | 적립식 결과(행·요약·조건·`hasMore`·`oldestReturned`·시계열·시계열 오류) |
| `cryptoStore` | `plan`, `recurring` | 같음 |
| `depositStore` | `product: "deposit" \| "installment"` | 상품 |
| | `installment: InstallmentResult \| null` | 적금 결과(행·요약·조건·계약·정기예금·시계열) |

방식·상품을 바꾸면 두 결과를 모두 비운다 — 한쪽 결과가 남아 다른 방식의 조건과 함께 보이지 않게 한다(008 D2 — 투자처를 바꾸면 비우는 것과 같은 이유).
