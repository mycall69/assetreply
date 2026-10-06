# REST API 계약 (011)

**Date**: 2026-10-06 | **Research**: [../research.md](../research.md) R11-7·R11-9·R11-10

공통 규약은 005~010 그대로다.
- 금액·비율·환율은 **문자열**이다. 해당이 없으면 키를 두지 않는다 — 0과 "없음"을 구별한다.
- 날짜는 ISO 날짜, 달은 `YYYY-MM`이다.
- 오류 본문은 `{status, message, …}`이다.
- 미수집이면 202 + 진행 URL이다(진행 스트림은 자산군마다 기존 그대로).

일시금(`/api/stocks/simulation`·`/api/crypto/simulation`)과 정기예금(`/api/deposit/simulation`) 경로는 **바뀌지 않는다**. 예외는 주식 보드의 `saleCost`다.
세율이 설정값에서 온다(반복 4의 키 모양 그대로).

## 1. 주식 적립식 — `GET /api/stocks/recurring-simulation`

| 매개변수 | 필수 | 뜻 |
|----------|------|----|
| `market`, `symbol` | ✓ | 일시금과 같다 |
| `start` | ✓ | 시작일 = 첫 예정 납입일 |
| `amount` | ✓ | 한 번 납입액(원금 통화, 문자열, > 0) — 일시금의 `parse_principal` 규칙 |
| `principalCurrency` | ✓ | `KRW` 또는 종목 통화(006 FR-050) |
| `frequency` | ✓ | `daily` · `weekly` · `monthly` · `yearly`. 밖이면 400 `invalid_query`("주기는 daily · weekly · monthly · yearly 중 하나여야 합니다") — 기본값으로 바꾸지 않는다 |
| `reinvest` | | 기본 `true`(일시금과 같다) |
| `end`, `before`, `limit` | | 일시금과 같다(끝 기본 어제, 커서 페이지, 1~200 기본 30) |

검증·판정 순서는 일시금과 같다. 원금 통화 형식 → 종목 → 조합 → 수집 전 시작 가능 날짜(`before_listing` 400 — 일시금의 처리기 그대로) → 수집 판정(202, 일시금의 `collecting_body`
그대로) → 계산.

**200**:

```jsonc
{
  "stock": {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
  "condition": {
    "mode": "recurring", "start": "2024-01-15", "amount": "500000", "principalCurrency": "KRW",
    "frequency": "monthly", "reinvest": true,
    "tradeFeeRate": "0.000150", "dividendTaxRate": "0.154000"
  },
  "summary": {
    "contributed": "16500000",        // 넣은 납입의 합(원금 통화)
    "contributedKrw": "16500000",     // 수익률의 분모(원화) — 납입마다 그날 값의 합
    "contributions": 33,              // 넣은 납입 횟수(예정일 기준 — 미뤄 합쳐진 것도 하나씩)
    "pendingAfterEnd": 0,             // 계산 끝 뒤 거래일로 미뤄져 아직 넣지 않은 납입 횟수
    "heldShares": 240,
    "pending": "12345",               // 매수 대기금(종목 통화)
    "dividendCash": "0",              // 배당 현금(매수 대기금에 아직 들어가지 않은 세후 배당 — 재투자 끔은 계속, 켬은 재투자일까지. 종목 통화)
    "totalKrw": "17890000",           // 원화 총자산 = (잔고 + 매수 대기금 + 배당 현금) × 기준일 환율
    "buyFeeTotal": "2470",            // 매수 수수료 합(원화 — 행마다 그 행 매매기준율)
    "dividendTaxTotal": "38000",      // 배당 소득세 합(원화)
    "saleCost": {"fee": "2680", "tax": "35760", "total": "38440", "taxKind": "transaction_tax",
                 "taxRate": "0.0020", "gain": null, "deduction": null},
    "feeTotal": "5150",               // 매수 수수료 합 + 매도 수수료
    "taxTotal": "73760",              // 배당 소득세 합 + 매도 세금
    "profit": "1390000",              // 보유 중(원화) = 총자산 − 분모
    "returnRate": "0.084242",
    "profitAfterSale": "1351560",     // profit − saleCost.total
    "returnRateAfterSale": "0.081912",
    "asOf": "2026-10-05", "isFinal": true
  },
  "rows": [
    {"date": "2026-09-15", "kind": "contribution", "openPrice": "71200", "closePrice": "71800",
     "contribution": "500000", "boughtShares": 7, "tradeFee": "74", "heldShares": 240,
     "pending": "12345", "dividendCash": "0", "contributed": "16500000", "contributedKrw": "16500000",
     "balance": "17232000", "profit": "744345", "returnRate": "0.045112"},
    {"date": "2026-08-18", "kind": "contribution", "deferred": ["2026-08-15"], "...": "…"},
    {"date": "2026-08-14", "kind": "dividend", "dividendPerShare": "361", "dividendTotal": "84474",
     "dividendTax": "13009", "dividendTotalNet": "71465", "...": "…"}
  ],
  "hasMore": true, "oldestReturned": "2026-03-04"
}
```

- `kind`: `contribution` · `dividend` · `reinvest` · `month_first`. `month_first`는 그 달 첫 거래일에 납입 행이 없을 때만 있다. 같은 날의 다른 사건은 행을 따로
  둔다(키 `${date}:${kind}`).
- `deferred`: 그 행으로 미뤄진 **원래 예정일**들. 그날이 예정일이기도 하면 그날은 싣지 않는다. 미뤄진 것이 없으면 키가 없다.
- 해외 종목:
  - 행에 `balanceKrw`·`fxRate`·`fxRateDate`(평가 — 그 행 매매기준율)를 싣는다.
  - 원화 원금의 납입 행에는 `exchangeRate`·`exchangeRateDate`(환전 — 현금 살 때 환율 + 90% 우대)도 싣는다.
  - 종목 통화 원금의 납입 행은 원화 분모에 그날 매매기준율을 쓰며, 그 값이 `fxRate`다.
- `saleCost`는 일시금 보드와 **같은 함수·같은 설정**이다(§5). 세금은 늘 값이 있다.
- 오류: 일시금과 같다(분석 F1 — 환율 오류는 둘이다).
  - `before_listing`(400 — 일시금 처리기 그대로. 처음 409로 잘못 적었다, T026 구현 중 고침)
  - `fx_not_available_before`(409) — **수집 전 판정**: 환율 출처의 시작이 시작일보다 늦다(일시금의 `collecting_body`가 내는 것 그대로)
  - `fx_unavailable`(409) — **계산 중**: 어느 납입일에든 그날 이전의 확정 환율이 하나도 없다(`FxUnavailable` — 그 납입을 빼고 계산하지 않는다)
  - `currency_pair_not_allowed`(400), `unknown_stock`(404), `invalid_query`(400)

### `GET /api/stocks/recurring-simulation/series`

같은 매개변수 + `maxPoints`. 응답은 일시금 시계열과 같은 모양이다. 점에 `principal`(그날까지의 원화 분모)이 더해진다.

```json
{"from": "2024-01-15", "to": "2026-10-05", "principalCurrency": "KRW", "basisCurrency": "KRW",
 "priceKind": "stock_adjusted_close", "priceCurrency": "KRW", "downsampled": false, "algorithm": "lttb",
 "sourcePointCount": 52,
 "points": [{"date": "2024-01-15", "balance": "500000", "returnRate": "0", "principal": "500000",
             "price": "73200"}],
 "gaps": []}
```

점은 표의 행 날짜다(날마다 마지막 상태 하나). `balance`는 원화 총자산이고, `price`는 010 반복 1의 분할만 반영한 수정 종가다.

## 2. 가상자산 적립식 — `GET /api/crypto/recurring-simulation`

| 매개변수 | 필수 | 뜻 |
|----------|------|----|
| `coinId`, `start`, `principalCurrency` | ✓ | 일시금과 같다 |
| `amount`, `frequency` | ✓ | §1과 같다 |
| `end`, `before`, `limit` | | 일시금과 같다(끝 기본 UTC 어제) |

**200**: `coin`·`condition`(`mode`, `start`, `amount`, `principalCurrency`, `frequency`, `tradeFeeRate`)·`summary`·`rows`·`hasMore`·`oldestReturned`.

- `summary`: `contributed`, `contributedKrw`, `contributions`, `pendingAfterEnd`, `heldQuantity`, `pending`, `totalKrw`, `buyFeeTotal`, `saleCost`, `feeTotal`,
  `taxTotal`, `profit`, `returnRate`, `profitAfterSale`, `returnRateAfterSale`, `asOf`, `isFinal`.
- `saleCost`: `{"fee": "…", "tax": "0", "total": "…", "taxKind": "not_yet_taxed"}`. 기준일이 2027-01-01 이후면
  `{"fee": "…", "tax": null, "total": null, "taxKind": "outside_rules"}`이고, `taxTotal`·`profitAfterSale`·`returnRateAfterSale`은 `null`이다.
- 행: `date`, `kind`(`contribution` · `month_first`), `openPrice`, `contribution?`, `deferred?`, `boughtQuantity`(`.8f`), `heldQuantity`, `pending`, `contributed`,
  `contributedKrw`, `balance`, `balanceKrw?`, `profit`, `returnRate`, `tradeFee?`, `firstDayMissing?`, `fxRate?`·`fxRateDate?`, `exchangeRate?`·`exchangeRateDate?`.

- 오류: §1과 같다 — `before_listing`, `fx_not_available_before`(수집 전), `fx_unavailable`(계산 중), `currency_pair_not_allowed`, `unknown_coin`(404),
  `invalid_query`.
- 계산 끝은 일시금 라우트의 `calculation_end`(min(`end`, UTC 어제))를 그대로 쓴다. 통합 테스트는 그 모듈의 `utc_yesterday`를 바꿔 2027년 기준일을 만든다
  (분석 C1).

`/series`는 007 일시금 시계열과 같은 모양이다. 점은 일봉마다이고 `principal`이 더해진다. 출처 결측 구간은 `gaps`의 `source_missing`이다.

## 3. 정기 적금 — `GET /api/deposit/installment-simulation`

| 매개변수 | 필수 | 뜻 |
|----------|------|----|
| `institution` | ✓ | 적금이 있는 투자처만 — `commercial_bank` · `mutual_finance`. 다른 셋은 400 `installment_not_available`(`{status, message, allowed}`), 모르는 키는 400 `unknown_institution` |
| `start` | ✓ | 첫 적금 가입일 |
| `amount` | ✓ | 월 납입액(원 단위 양의 정수 문자열 — 008 `parse_won`) |
| `end` | | 기본 오늘(한국 시간), 그보다 늦으면 오늘 |

수집 판정은 두 계열을 함께 본다(research R11-9).

**202**: 008과 같은 모양에 `series`가 더해진다. `institution`은 투자처 키다 — 수집은 금리 계열 키(`…_isav`)로 돌지만 응답에 그 키를 싣지 않는다(research R11-2).

```json
{"status": "collecting", "institution": "commercial_bank", "series": "installment", "jobId": 41,
 "missingFrom": "2003-01", "missingThrough": "2026-10", "progressUrl": "/api/deposit/progress?jobId=41"}
```

끝나면 화면이 다시 요청한다. 정기예금 쪽이 남았으면 다시 202(`series: "deposit"`)다.

**409**:
- `before_first_month`: `startableFrom` = max(적금 첫 달, 정기예금 첫 달 − 1년)
- `rate_missing`: 첫 적금 가입 달이 결측일 때

**200**:

```jsonc
{
  "institution": {"key": "commercial_bank", "name": "시중은행"},
  "condition": {"product": "installment", "start": "2015-01-15", "amount": "1000000",
                "interestTaxRate": "0.154000",
                "installmentItem": "예금은행 정기적금(1~2년 만기) 평균",
                "depositItem": "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함"},   // 008 투자처 설명 그대로
  "summary": {
    "contributed": "141000000",       // 낸 회차 × 월 납입액(새 돈만)
    "installments": 141,              // 낸 회차 수(T043 구현 때 더함)
    "interestTotal": "…", "taxTotal": "…", "afterTaxTotal": "…",   // 만기된 계약(적금 + 정기예금)의 합
    "installmentAfterTax": "…", "depositAfterTax": "…",   // 세후 이자 합의 구성(적금 · 정기예금) — 보드가 더하지 않는다(T045 때 더함)
    "installmentValue": "…", "depositValue": "…", "balance": "…",   // 기준일 평가(경과 이자 포함)
    "profit": "…", "returnRate": "…", "asOf": "2026-10-06", "isFinal": true,
    "currentInstallment": {"no": 12, "joinedOn": "2026-01-15", "maturesOn": "2027-01-15", "rate": "3.1",
                           "rateMonth": "2026-01", "provisional": false, "paid": 10},
    "currentDeposit": {"no": 11, "joinedOn": "2026-01-15", "maturesOn": "2027-01-15", "rate": "2.9",
                       "rateMonth": "2026-01", "provisional": false, "principal": "…"},
    "provisionalFrom": null, "stopped": null, "recheckFailed": null
  },
  "contracts": [{"no": 1, "joinedOn": "2015-01-15", "maturesOn": "2016-01-15", "rate": "2.4",
                 "rateMonth": "2015-01", "provisional": false, "monthly": "1000000", "paid": 12,
                 "interest": "156000", "tax": "24024", "afterTax": "131976", "amount": "12131976"}],
  "deposits": [{"no": 1, "joinedOn": "2016-01-15", "maturesOn": "2017-01-15", "rate": "1.7",
                "rateMonth": "2016-01", "provisional": false, "principal": "12131976",
                "fromDeposit": "0", "fromInstallment": "12131976",
                "interest": "…", "tax": "…", "afterTax": "…"}],
  "rows": [{"date": "2026-10-15", "kind": "installment", "contractNo": 12, "installmentNo": 10,
            "amount": "1000000", "rate": "3.1", "rateMonth": "2026-01", "provisional": false,
            "contributed": "…", "installmentValue": "…", "depositValue": "…", "balance": "…",
            "profit": "…", "returnRate": "…"}]
}
```

- `rows.kind`: `installment` · `month` · `installment_maturity` · `deposit_maturity` · `deposit_join`. 만기 행에는 `interest`·`tax`·`afterTax`가 있다. 가입 행에는
  `fromDeposit`·`fromInstallment`가 있다. 모든 행을 한 번에 준다(008과 같다 — 20년 약 500행).
  - `contractNo`는 그 행의 계약 번호다 — 적금 행(납입·적금 만기)은 적금, 정기예금 행(만기·가입)은 정기예금의 번호다. 월 행은 `null`이다.
  - 월 행에는 `rate`·`amount`가 없다(두 상품의 금리가 다르다 — 적용 금리는 계약 행에 있다).
- `contracts`·`deposits`는 **만기된** 계약만이다(008 `terms`와 같다). 진행 중인 것은 `summary.currentInstallment`·`currentDeposit`이다.
- 위 예의 수치는 모양을 보이는 자리다. 기대값은 단위 테스트의 손계산이 정한다.

### `GET /api/deposit/installment-simulation/series`

008 시계열과 같은 모양이다. `priceKind: "installment_rate"`, `price` = 그 달 발표 적금 금리(`unpublished`·`missing`은 `priceMissing`). 점에 `principal`(누적 납입)과
`depositRate`(그 달 발표 정기예금 금리 — 없으면 키 없음)가 더해진다.

## 4. 투자처 목록 — `GET /api/deposit/institutions` (키 더함)

투자처마다 `installment`를 더한다. 기존 키는 그대로다.

```json
{"key": "commercial_bank", "name": "시중은행", "description": "…", "firstMonth": "2012-01", "latestMonth": "2026-08", "checkedOn": "2026-10-06",
 "installment": {"available": true, "description": "예금은행 정기적금(1~2년 만기) 평균",
                 "firstMonth": "2003-01", "latestMonth": "2026-08", "checkedOn": "2026-10-06",
                 "startableFrom": "2011-01-01"}}
{"key": "savings_bank", "...": "…",
 "installment": {"available": false, "reason": "출처(ECOS)에 이 투자처의 정기적금 금리 통계가 없습니다."}}
```

받기 전에는 `firstMonth`·`latestMonth`·`checkedOn`·`startableFrom`이 `null`이다. `startableFrom`은 두 계열의 커버리지가 다 있을 때만 값이 있다.

## 5. 주식 매도 세금 설정 — `GET/PUT /api/stocks/settings/sale-tax`

```json
{"saleTaxRateDomestic": "0.0020", "capitalGainsRateForeign": "0.22", "capitalGainsDeductionForeign": "2500000",
 "isDefault": true,
 "defaults": {"saleTaxRateDomestic": "0.0020", "capitalGainsRateForeign": "0.22", "capitalGainsDeductionForeign": "2500000"}}
```

- `PUT` 본문은 세 키를 **모두** 받는다. 빠진 키를 기본값으로 채우지 않는다. 기본값으로 되돌리기는 화면이 `defaults`를 보낸다.
- 검증 실패는 422 `invalid_setting`이다. 저장하지 않고 기존 값을 유지한다.
  - 세율: 0 이상 1 미만, 소수 6자리 이하
  - 공제: 0 이상의 정수, 15자리 이하
  - 숫자가 아닌 값·`null`
- 저장된 값은 DB 자릿수(6자리)로 돌아온다(예: `"0.001500"`). 기본값에서 벗어났는지는 `isDefault`가 알린다.
- 기존 `GET/PUT /api/stocks/settings`(수수료·배당 세율)는 바뀌지 않는다.

**일시금 보드에의 반영**(`GET /api/stocks/simulation`의 `summary.saleCost`):
- 국내: `taxRate`는 국내 매도 세율이다.
- 해외: `taxRate`는 양도소득세율, `deduction`은 기본공제다.
- 모든 기준일에 같은 값이고, `outside_table`은 더는 나오지 않는다.
- 기본 설정이면 010 반복 4의 2026년 응답과 문자열까지 같다.
