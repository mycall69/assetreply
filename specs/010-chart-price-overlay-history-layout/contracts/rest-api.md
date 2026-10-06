# REST API 계약: 시계열 응답에 가격을 더한다

**Feature**: `010-chart-price-overlay-history-layout` | **Date**: 2026-10-05

반복 2까지는 새 경로가 없다. 네 시계열 경로의 **200 응답에 키를 더할 뿐**이다. 질의 매개변수·202(수집 중)·오류(400·404·409)·`gaps`·다운샘플·기존 키는 그대로다
(005~009 계약). 금액·가격·비율은 지금처럼 **문자열**이다(헌법 원칙 VI). 시뮬레이션(표) 경로는 바뀌지 않는다(FR-021) — **반복 3에서 둘이 바뀐다**: 주식 표 행에
`closePrice`가 생기고 잔고가 종가 평가다(FR-028, 아래 "반복 3"), 부동산에 단지 번호 경로가 생긴다(FR-029).

| 경로 | 더하는 키 |
|------|-----------|
| `GET /api/stocks/simulation/series` | `priceKind`·`priceCurrency`, 점의 `price`(반복 1: 수정 종가, `splits` 키 제거) |
| `GET /api/crypto/simulation/series` | `priceKind`·`priceCurrency`, 점의 `price` |
| `GET /api/deposit/simulation/series` | `priceKind`·`priceCurrency`(`null`), 점의 `price`·`priceMissing` |
| `GET /api/realestate/simulation/series` | `priceKind`·`priceCurrency`, 점의 `price`·`priceMissing`·`profit` |

## 공통 규칙

- `points[].price` — 그 점 날짜(부동산은 그 달)의 가격 문자열 또는 `null`. 키는 늘 있다.
- `points[].priceMissing` — `price`가 `null`일 때**만** 있다. `unpublished`(예금 — 아직 발표되지 않은 달), `missing`(예금 — 발표 기간 안인데 통계가 빈
  달), `no_trades`(부동산 — 그 평형의 그 달 거래 없음).
- `priceKind` — `stock_adjusted_close`(반복 1 — 처음은 `stock_open`) · `crypto_open` · `deposit_rate` · `apt_average`. 화면은 이것으로 범례 이름·형식을 고른다.
- `priceCurrency` — 가격의 통화. 주식은 종목 통화, 가상자산은 시세 통화, 부동산은 `KRW`, 예금은 `null`(단위는 연 %). **원금 통화와 관계없다** — 원화 원금으로
  미국 종목을 실행해도 `USD`다(Clarifications). 잔고·수익률의 기준은 지금처럼 `basisCurrency`(KRW).
- 가격 서식은 **표의 같은 값과 같은 함수**다 — 주식 `str()`(반복 1: 수정 종가 — 표에는 없다, R10-13), 가상자산 `format(…, "f")`(표 `openPrice`), 예금 `rate_text`(표 `rate`), 부동산
  원 정수 `str()`(표 `monthAverage`).
- 가격이 없는 날을 `gaps`에 넣지 않는다 — `gaps`는 잔고·수익률 선이 끊기는 자리다(research R10-2).
- 다운샘플된 점의 `price`는 그 점 날짜의 원래 값이다(FR-007).

## `GET /api/stocks/simulation/series`

반복 1(2026-10-05)의 형식이다 — 처음 형식(`priceKind "stock_open"`, 원주가 시가, `splits`)은 아래 "처음 형식"에 남긴다.

```json
{
  "from": "2020-01-02", "to": "2026-10-04", "principalCurrency": "KRW", "basisCurrency": "KRW",
  "priceKind": "stock_adjusted_close", "priceCurrency": "USD",
  "downsampled": false, "algorithm": "lttb", "sourcePointCount": 95,
  "points": [
    { "date": "2020-08-03", "balance": "14210345", "returnRate": "0.4210", "price": "108.9375" },
    { "date": "2020-09-01", "balance": "15342210", "returnRate": "0.5342", "price": "134.18" }
  ],
  "gaps": [ { "from": "2020-09-07", "to": "2020-09-07", "reason": "no_quote" } ]
}
```

- `price` = 그 날의 **분할만 반영한 수정 종가** — `close_raw ÷ ∏(numerator/denominator)`(효력일이 그 날 뒤 ~ 계산 끝인 분할, research R10-13). 분할 날에도 이어진다.
  배당은 소급하지 않는다. 표의 `openPrice`(매수 기준 원주가 시가)와 다른 값이다.
- `splits` 키는 없다(분할 표식 없음 — spec FR-008).
- 그 날 원주가 종가가 없으면 `price: null` + `priceMissing: "missing"`이다(지어내지 않는다). 점은 거래일이라 실제로는 생기지 않는다.
- 실패 양상(테스트가 잡는다): 원주가를 내면 분할 효력일 뒤 첫 점에서 분할 비율만큼 꺾인다. 출처 `close_adjusted`(배당 소급)를 내면 규칙 값과 다르다.

**처음 형식(반복 전)**: `priceKind "stock_open"`, `price` = 그 날 마지막 행의 `openPrice`(원주가 시가), `splits: [{date, numerator, denominator}]`.

## `GET /api/crypto/simulation/series`

```json
{
  "from": "2024-01-15", "to": "2026-10-04", "principalCurrency": "KRW", "basisCurrency": "KRW",
  "priceKind": "crypto_open", "priceCurrency": "USD",
  "points": [ { "date": "2024-01-15", "balance": "1000000", "returnRate": "0", "price": "42511.10000000" } ],
  "gaps": [ { "from": "2024-03-02", "to": "2024-03-03", "reason": "source_missing" } ]
}
```

- `price` = 그 일봉(UTC 하루)의 시가 — 표의 `openPrice`. 점은 일봉이 있는 날만이라 `price`는 `null`이 아니다. 출처 결측 날은 지금처럼 점이 없고 `gaps`다.

## `GET /api/deposit/simulation/series`

```json
{
  "from": "2024-01-10", "to": "2026-10-05", "principalCurrency": "KRW", "basisCurrency": "KRW",
  "priceKind": "deposit_rate", "priceCurrency": null, "provisionalFrom": "2026-09-01",
  "points": [
    { "date": "2024-01-10", "balance": "10000000", "returnRate": "0", "price": "3.71" },
    { "date": "2026-09-01", "balance": "10912345", "returnRate": "0.0912", "price": null, "priceMissing": "unpublished" }
  ],
  "gaps": []
}
```

- `price` = 점 날짜의 달에 발표된 그 투자처의 금리(연 %) — 시뮬레이션이 그 달 가입·재예치에 읽는 바로 그 값(`rates[달]`). 표의 `rate`(회차의 적용 금리)와는 다른
  값일 수 있다(만기까지 고정이므로).
- 마지막 발표 달 뒤의 달 → `null` + `unpublished`. 계산은 지금처럼 마지막 발표 달 금리로 잠정이고(`provisionalFrom`), 대신 쓴 그 금리를 `price`에 넣지 않는다.
- 발표 기간 안인데 통계가 빈 달(만기 사이라 계산이 멈추지 않은 달) → `null` + `missing`.
- 실패 양상: 대신 쓴 금리를 `price`로 내면 미발표 달에 금리가 발표된 것처럼 보인다(원칙 V). 경로가 금리를 넘기기를 잊으면 모든 점이 `unpublished`가 된다 —
  `build_series`의 금리 인자를 필수로 두어 막는다(research R10-5).

## `GET /api/realestate/simulation/series`

```json
{
  "from": "2021-03-15", "to": "2026-10-05", "principalCurrency": "KRW", "basisCurrency": "KRW",
  "priceKind": "apt_average", "priceCurrency": "KRW", "provisionalFrom": "2025-11-01",
  "points": [
    { "date": "2021-03-15", "balance": "2023166667", "returnRate": "-0.040307", "estimated": false, "provisional": false,
      "profit": "-85000000", "price": "2023166667" },
    { "date": "2021-04-01", "balance": "2031250000", "returnRate": "-0.036473", "estimated": true, "provisional": false,
      "profit": "-77000000", "price": null, "priceMissing": "no_trades" }
  ],
  "gaps": []
}
```

- `price` = 그 달 실거래가 평균(같은 단지·같은 평형 구분, 해제·사라진 거래 제외) — 표의 `monthAverage`. 첫 점(매입일)은 매입 달, 끝점(계산 끝)은 그 달의 값.
- `profit` = 투자 수익(원) — 표의 `profit`, 끝점은 `summary.profit`.
- 거래 없는 달 → `null` + `no_trades`. 그 점의 `balance`·`returnRate`는 지금처럼 적용 시세(추정 포함 — `estimated`)다.
- 시세 없음 달은 지금처럼 점이 없고 `gaps`(`no_price`)다.
- 실패 양상: 적용 시세를 `price`에 넣으면 거래가 없던 달에 실거래가 있던 것처럼 보인다(FR-011).

## 계약 테스트가 확인하는 것 (tasks)

- 네 경로 모두 — 점마다 `price`가 표(또는 예금은 그 달 금리)의 같은 날 값과 같다(SC-001). `price`가 `null` ⇔ `priceMissing`이 있다.
- 다운샘플(`maxPoints`를 작게) — 줄인 점의 `price`가 그 날짜의 원래 값이다(FR-007).
- 주식 — 분할이 있는 종목의 효력일 앞뒤 점의 `price` 비율이 원주가 시세 변동만큼(분할 비율만큼 꺾이지 않음), `splits` 키 없음(반복 1).
- 예금 — `unpublished`(마지막 발표 달 뒤)·`missing`(발표 기간 안 빈 달) 각 하나.
- 부동산 — `no_trades` 달의 `balance`·`returnRate`가 표와 같고 `price`가 `null`. `profit`이 표와 같다.
- 기존 `gaps` 정확 비교 테스트는 바꾸지 않고 통과한다.

## 반복 3 (2026-10-06)

### `GET /api/stocks/simulation` — 행에 `closePrice`, 잔고는 종가 평가 (FR-028)

```json
{"rows": [{"date": "2026-10-01", "kind": "month_first", "openPrice": "330.000000", "closePrice": "330.320007",
           "heldShares": 119, "balance": "39308.08…", "profit": "…", "returnRate": "…", "…": "…"}]}
```

- `closePrice` — 그 행 날짜의 **원주가 종가**(저장소 `close_raw`) 문자열. 늘 있다(종가가 없는 일봉은 쓰지 않는다 — 원칙 V).
- `balance` = `heldShares` × `closePrice`(종목 통화). `profit`·`returnRate`와 원화 환산 값(`balanceKrw` 등)이 이 잔고를 따른다. 매수(`boughtShares`)·
  수수료·`dividendYield`(÷ `openPrice`)는 그대로 시가다.
- 시계열(`/series`)의 `balance`·`returnRate`도 같은 잔고다(표와 차트가 같은 계산 — FR-002). 점의 `price`(분할만 반영한 수정 종가)는 그대로다.

### `GET /api/realestate/complexes/{complexId}/naver` — Npay 부동산 단지 화면 주소 (FR-029)

```json
{"complexId": 4, "status": "found", "url": "https://fin.land.naver.com/complexes/111515", "reason": null}
{"complexId": 17, "status": "not_found", "url": null, "reason": null}
{"complexId": 4, "status": "failed", "url": null, "reason": "rate_limited"}
```

- 200 — 세 상태. `found`는 저장한 번호(처음이면 출처에서 찾아 저장한 뒤). `not_found`는 같은 법정동에서 고를 후보가 없거나 여럿(저장 — 정해진 날 수 뒤 다시
  찾는다). `failed`는 출처 실패(`reason`: `blocked`(403)·`rate_limited`(429가 재시도 끝까지)·`network`·`format`) — **저장하지 않는다**.
- 400 `unknown_complex` — 모르는 단지(다른 부동산 경로와 같다, 009). 합쳐진 단지는 합쳐 받은 단지로 찾는다(응답의 `complexId`는 요청한 값).
- 출처 응답 형식·검색어·원본은 응답에 싣지 않는다(어댑터 밖으로 나가지 않는다 — 원칙 II).
- 계약 테스트: 저장된 응답 픽스처(헬리오시티·미륭·개포자이·리센츠)로 파싱과 고르기, 가짜 클라이언트로 저장·재사용(두 번째 요청에 출처 호출 0)·실패 미저장·
  못 찾음 다시 찾기·모르는 단지 400.

## 반복 4 (2026-10-06) — `GET /api/stocks/simulation`의 `summary` (FR-030)

```json
"summary": {"principal": "10000000", "profit": "46493910.88…", "returnRate": "4.649391", "asOf": "2026-10-02", "isFinal": true,
            "saleCost": {"fee": "8445", "tax": "112608", "total": "121053", "taxKind": "transaction_tax", "taxRate": "0.0020",
                         "gain": null, "deduction": null},
            "profitAfterSale": "46372857", "returnRateAfterSale": "4.637285"}
```

- 해외 종목: `taxKind "capital_gains_tax"`, `taxRate "0.22"`, `gain`(원화 양도차익)·`deduction`(`"2500000"`). 차익이 공제 이하·손실이면 `tax "0"`.
- 기준일이 세율 표 밖: `taxKind "outside_table"`, `tax`·`total`·`profitAfterSale`·`returnRateAfterSale`이 `null`(`fee`는 있다).
- `profit`·`returnRate`(보유 중)와 표의 행·시계열은 그대로다.

## 반복 5 (2026-10-06) — 부동산 매도비용·거주 기간 비율 (FR-031)

### `GET /api/realestate/simulation`의 `summary`

```json
"saleCost": {"brokerage": "…", "incomeTax": "…", "localTax": "…", "total": "…", "kind": "high_price",
             "gain": "…", "taxableGain": "…", "ltsdRate": "0.400000", "holdingYears": 5, "residenceYears": 5, "basePerOwner": "…"},
"profitAfterSale": "…", "returnRateAfterSale": "…"
```

- `kind`: `exempt`(12억 이하 비과세 — 세금 0), `high_price`(12억 초과분만 과세), `taxed`(비과세 요건 밖 — 2년 이상 보유했으나 거주 2년 미만), `short_term`(2년 미만 — 60%·70%),
  `no_gain`(차익 0 이하 — 세금 0), `outside_table`(기준일이 규칙 밖 — `incomeTax`·`localTax`·`total`·`profitAfterSale`·`returnRateAfterSale`이 `null`).
- 평가액(`value`·`profit`)을 모르면(시세 없음) `saleCost`·`profitAfterSale`·`returnRateAfterSale` 키가 없다. 기존 키는 그대로다. `condition.residenceRatio`를 더한다.

### `GET`·`PUT /api/realestate/settings/residence`

- `GET` → `{"residenceRatio": "1.000000", "isDefault": true}`. `PUT {"residenceRatio": "0.5"}` → 저장한 값. 0 이상 1 이하의 소수 문자열(소수 6자리까지), 그 밖은 400
  `invalid_setting`(보유세 기준 비율과 같은 꼴). 기존 `/api/realestate/settings`는 바뀌지 않는다.

