# Contract: REST — 005

**Feature**: 005-stock-investment-simulation | **Date**: 2026-09-27

001~004가 세운 규약을 잇는다.

- 금액·비율은 모두 **문자열**이다. JSON `number`는 IEEE 754라 `Decimal` 정밀도가
  손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.
- 정상 상태에 값을 두지 않는다. **없으면 키를 생략**한다 — 화면이 존재 여부가 아니라
  내용을 검사하게 되면 판정이 흔들린다.
- 미수집 구간이 있으면 `202`로 진행 상태를 준다.

---

## `GET /api/stock/search` — 종목 검색

사용자가 코드를 직접 입력하지 않도록 한다 (FR-002a).

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `q` | 예 | 종목 이름 또는 코드의 일부 |
| `limit` | 아니오 | 기본 20, 1~50 |

### 응답

```json
{
  "query": "삼성",
  "results": [
    { "market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW" },
    { "market": "KRX", "symbol": "005935.KS", "name": "삼성전자우", "currency": "KRW" }
  ]
}
```

**`market`과 `currency`를 함께 내려준다**(FR-002b). 같은 이름이 여러 시장에 있을 수 있고,
통화가 다르면 환전 여부와 수익률 기준이 달라진다.

### 오류

| 상황 | 상태 | `status` |
|------|------|----------|
| `q`가 비었거나 너무 짧다 | 400 | `invalid_query` |
| 출처가 응답하지 않는다 | 502 | `source_unavailable` |
| 출처의 호출 한도 소진 | 503 | `source_rate_limited` |

**검색 실패와 "결과 없음"을 구별한다.** 출처가 죽었는데 빈 목록을 주면 사용자는 그 종목이
존재하지 않는다고 읽는다.

---

## `GET /api/stock/simulation` — 시뮬레이션 실행과 표 페이지

### 질의 매개변수

| 이름 | 필수 | 기본 | 설명 |
|------|------|------|------|
| `market` | 예 | — | 시장 |
| `symbol` | 예 | — | 종목 식별자 |
| `start` | 예 | — | 투자 시작 날짜 |
| `principal` | 예 | — | 투자 원금. **문자열** |
| `principalCurrency` | 예 | — | `KRW` · `USD` · `JPY` · `EUR` |
| `reinvest` | 아니오 | `true` | 배당 재투자 여부 |
| `before` | 아니오 | — | 이 날짜 **미만**만 반환 (004의 커서 방식) |
| `limit` | 아니오 | 30 | 1~200 |

`principal`을 문자열로 받는 이유는 응답과 같다 — 경계에서 정밀도를 잃지 않는다.

### 200 응답

```json
{
  "stock": { "market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW" },
  "condition": {
    "start": "2021-08-01",
    "principal": "86997",
    "principalCurrency": "KRW",
    "reinvest": true,
    "tradeFeeRate": "0.000150",
    "dividendTaxRate": "0.154000"
  },
  "summary": {
    "principal": "86997",
    "profit": "120777",
    "returnRate": "1.388300",
    "asOf": "2024-08-01",
    "isFinal": true
  },
  "rows": [
    {
      "date": "2024-08-01",
      "kind": "month_first",
      "openPrice": "201500.000000",
      "boughtShares": 0,
      "heldShares": 1,
      "cash": "6274",
      "principal": "86997",
      "balance": "201500",
      "profit": "120777",
      "returnRate": "1.388300"
    },
    {
      "date": "2024-06-27",
      "kind": "dividend",
      "openPrice": "229500.000000",
      "dividendPerShare": "300.000000",
      "dividendYield": "0.001307",
      "boughtShares": 0,
      "heldShares": 1,
      "cash": "6274",
      "principal": "86997",
      "balance": "229500",
      "profit": "148777",
      "returnRate": "1.710100"
    }
  ],
  "hasMore": true,
  "oldestReturned": "2024-06-27"
}
```

### 외화 종목의 추가 필드

원금 통화와 종목 통화가 다르면 다음이 더해진다.

```json
{
  "exchange": {
    "rate": "1305.420000",
    "rateDate": "2021-08-02",
    "kind": "cash_buy_discounted",
    "spreadDiscount": "0.90"
  },
  "rows": [
    { "date": "2024-08-01", "fxRate": "1338.500000", "fxRateDate": "2024-08-01", "…": "…" }
  ]
}
```

| 필드 | 의미 |
|------|------|
| `exchange` | **초기 환전** 1회에 쓴 환율. 현금 살 때에 우대를 적용한 값 (FR-019~021) |
| `exchange.rateDate` | 그 환율의 날짜. 투자 시작일과 다를 수 있다 (FR-022) |
| `fxRate`·`fxRateDate` | 그 행의 **평가 환산**에 쓴 매매기준율과 날짜 (FR-041b, FR-041c) |

**두 환율을 한 이름으로 합치지 않는다.** 초기 환전은 실제로 돈을 바꾸는 행위라 우대가
붙고, 평가는 값어치를 재는 것이라 매매기준율이다. 합치면 잔고가 매수 스프레드만큼 크게
나오는데 값은 그럴듯하다.

### 요약의 `asOf`와 `isFinal`

| 필드 | 의미 |
|------|------|
| `asOf` | 계산이 **어느 날짜까지**인지 |
| `isFinal` | `asOf`가 오늘이면 `true`. 시세가 끊겼으면 `false` |

FR-014b가 이 둘을 요구한다. 상장폐지·거래정지로 시세가 끊기면 `asOf`가 오늘이 아니고
`isFinal`이 `false`다. 화면은 이것으로 "오늘까지"라는 말을 쓸지 정한다.

**`isFinal`은 항상 명시한다.** "확인했고 아니다"와 "확인하지 않았다"가 구별되어야 한다.

### 월 행의 배당 칸

`kind`가 `month_first`이면 `dividendPerShare`·`dividendYield` **키가 없다**(FR-026).
0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다.

### 202 — 시세를 아직 받지 못했다

```json
{
  "status": "collecting",
  "market": "KRX",
  "symbol": "005930.KS",
  "jobId": 17,
  "missingFrom": "2021-08-01",
  "missingThrough": "2024-12-31",
  "progressUrl": "/api/stock/progress?jobId=17"
}
```

001·002가 정한 수집 중 응답 규약을 잇는다 (FR-047).

**부분 결과를 200으로 내려보내지 않는다**(FR-049). 받은 만큼만 계산한 수익률은 값이
멀쩡해 보이지만 틀린 값이며, 사용자는 그것을 최종 결과로 읽는다.

이미 같은 종목의 수집이 진행 중이면 **새 작업을 만들지 않고 그 `jobId`를 준다**(FR-048).

### 오류

| 상황 | 상태 | `status` |
|------|------|----------|
| 알 수 없는 시장·종목 | 404 | `unknown_stock` |
| `start`가 상장 이전 | 400 | `before_listing` |
| `principalCurrency`가 지원 밖 | 400 | `invalid_query` |
| 원금이 0 이하 | 400 | `invalid_query` |
| 환율이 없어 환산할 수 없다 | 409 | `fx_unavailable` |
| `limit` 범위 밖 | 422 | (프레임워크 기본 검증) |

**`before_listing`을 조용히 첫 거래일로 옮기지 않는다**(FR-005). 옮기면 사용자는 자신이
고른 날짜부터 계산됐다고 믿는다.

---

## `GET /api/stock/progress` — 수집 진행 (SSE)

003이 만든 수집 스트림과 같은 모양이다. `EventSource`의 자동 재연결에 의존하며
`error`에서 닫지 않는다.

| 이벤트 | 내용 |
|--------|------|
| `snapshot` | 대상 구간, 수집된 구간, 진행 중 종목 |
| `chunk_stored` | 구간 하나가 저장됨 |
| `completed` | 완료. 화면이 시뮬레이션을 다시 요청한다 |
| `failed` | 실패 사유 |

---

## `GET` · `PUT /api/stock/settings` — 수수료·세율

```json
{ "tradeFeeRate": "0.000150", "dividendTaxRate": "0.154000", "isDefault": true }
```

`PUT`으로 바꾼다. 002의 스프레드 설정과 같은 자리에 둔다 (FR-015, FR-016).

| 상황 | 상태 | `status` |
|------|------|----------|
| 값이 0 미만이거나 1 이상 | 422 | `invalid_setting` |

**설정이 바뀌면 이미 표시된 결과가 다시 제시되어야 한다**(FR-017). 서버는 저장만 하고,
재산출은 화면이 다시 요청해서 얻는다 — 결과를 저장하지 않으므로(research R5-9) 무효화할
캐시가 없다.

`isDefault`는 현재 값이 기본값과 같은지다. 002 FR-033과 같은 규약이다.

---

## 응답에 적용 조건을 싣는 이유

`condition`에 `tradeFeeRate`·`dividendTaxRate`가 들어가는 것은 FR-018의 요구다.

설정은 언제든 바뀐다. 결과만 남으면 **어느 조건에서 나온 수치인지 알 수 없고**, 내려받은
파일이나 화면 캡처를 나중에 보면 더 그렇다.
