# REST API: 가상자산 투자 시뮬레이션

**Feature**: `007-crypto-investment-simulation` | 근거: [research.md](../research.md), [data-model.md](../data-model.md)

모든 경로는 `/api/crypto/*`다. 프론트엔드 프록시(`next.config.ts`)는 006부터 `/api/*` 전체를 넘긴다 — 바꿀 것이 없다.

**금액·비율·가격·수량은 모두 문자열**이다(JSON number는 IEEE 754 — 헌법 원칙 VI, 001부터의 규약). 오류 본문은 기존 규약
`{"status": "...", "message": "..."}`을 따른다.

---

## `GET /api/crypto/search` — 코인 검색 (FR-003~FR-006, FR-005, FR-005a)

로컬 코인 목록에서 찾는다. **출처를 부르지 않는다.** 목록 갱신 주기가 되었으면(일주일, data-model 2절) 갱신을 요청하되 **기다리지
않는다**(006 FR-017과 같다).

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `q` | 예 | 영문 이름·심볼·한글 이름·초성 (1자 이상) |
| `limit` | 아니오 | 기본 20, 최대 50 |

### 200 응답

```json
{
  "query": "ㅂㅌㅋㅇ",
  "results": [
    {
      "coinId": 17,
      "symbol": "BTC",
      "name": "Bitcoin",
      "nameKo": "비트코인",
      "slug": "bitcoin",
      "currency": "USD",
      "rank": 1,
      "listStatus": "listed",
      "firstAvailableDate": "2010-07-18",
      "match": "prefix"
    }
  ],
  "truncated": false,
  "list": {
    "state": "ready",
    "asOf": "2026-10-03T09:40:12Z",
    "koreanNames": { "state": "ready", "asOf": "2026-10-03T09:41:55Z" }
  }
}
```

- `nameKo` — 한글 이름이 있을 때만(없으면 `null`, FR-006)
- `rank` — 시가총액 순위(없으면 `null`). 같은 일치 종류 안에서 순위가 높은 코인이 먼저다(research R7-6)
- `listStatus: "missing"` — 목록에서 빠진 코인(FR-005a). 결과에 남기되 표시한다
- `firstAvailableDate` — 수집으로 발견한 첫 일봉(없으면 `null` — 아직 모른다, research R7-10)
- `list.state`: `ready` | `refreshing` | `never`(받은 적 없음) | `failed`(마지막 갱신 실패 — `reason`·`asOf`(이전 목록 기준)를 싣는다)
  - `reason`: `blocked` | `format` | `network` | `shrunk`
- `list.koreanNames` — 한국어 판의 상태. 실패해도 영문으로 찾는다(FR-006)
- 결과가 없어도 `list`는 항상 온다. **화면은 `results`가 비었을 때 `list`를 보고 "결과 없음"과 "목록 없음"을 가른다**

### 순서

정확 일치 → 앞부분 일치 → 포함. 같은 종류 안에서는 **시가총액 순위**(없으면 뒤) → 일치한 이름이 짧은 순 → 가나다·알파벳순 → 심볼.
같은 질의면 언제나 같은 순서다.

### 오류

| 상황 | 상태 | `status` |
|------|------|----------|
| `q`가 비었다 | 400 | `invalid_query` |

목록이 없거나 갱신이 실패해도 오류가 아니다 — 200에 `list`로 알린다(006과 같다).

---

## `GET /api/crypto/list/progress` — 목록 갱신 진행 (SSE) (FR-005b)

머리글은 다른 스트림과 같다(`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`). 프레임마다 DB를 새로 읽는다(006 R6-19).

- `snapshot`: `{"edition": "en", "pagesDone": 12, "pagesExpected": 37, "coinsSeen": 1200}` — `pagesExpected`는 이전 갱신의 코인 수로
  어림한 값(처음이면 `null`). 판이 바뀌면(`en` → `ko`) `pagesDone`이 0부터 다시 센다
- `completed`: `{"asOf": "2026-10-03T09:41:55Z", "coins": 3654, "koreanNames": "ready"}`
- `failed`: `{"reason": "blocked", "message": "…"}` — `reason`은 검색 응답의 `list.reason`과 같다
- 갱신 중이 아니면 마지막 상태를 한 번 보내고 닫는다(`completed` 또는 `failed`, 받은 적이 없으면 `idle`)

검색 칸은 `list.state`가 `never`·`refreshing`일 때 구독하고, `completed`를 받으면 검색을 다시 보낸다.

---

## `GET /api/crypto/simulation` — 시뮬레이션 표 (FR-002, FR-007~FR-009, FR-013, FR-022~FR-042)

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `coinId` | 예 | 검색 결과의 `coinId` |
| `start` | 예 | `YYYY-MM-DD` |
| `principal` | 예 | 문자열 금액 (> 0) |
| `principalCurrency` | 예 | `KRW` 또는 코인의 시세 통화(`USD`) |
| `end` | 아니오 | 기본 **UTC 어제**(마지막으로 마감된 UTC 하루, FR-022) |
| `before` | 아니오 | 이 날짜 미만의 행만(스크롤 이어 보기, 005 FR-029) |
| `limit` | 아니오 | 기본 30, 최대 200 |

### 200 응답

숫자는 형식을 보이기 위한 예시다(계산값이 아니다).

```json
{
  "coin": { "coinId": 17, "symbol": "BTC", "name": "Bitcoin", "nameKo": "비트코인", "currency": "USD" },
  "condition": {
    "start": "2020-01-15", "principal": "10000000", "principalCurrency": "KRW",
    "tradeFeeRate": "0.001000"
  },
  "summary": {
    "principal": "10000000",
    "profit": "71284413", "returnRate": "7.128441",
    "asOf": "2026-10-02", "isFinal": true,
    "boughtOn": "2020-01-01"
  },
  "exchange": { "rate": "1158.000000", "rateDate": "2019-12-31", "kind": "cash_buy_discounted", "spreadDiscount": "0.9" },
  "rows": [
    {
      "date": "2026-10-01", "kind": "month_first",
      "openPrice": "83553.94531250000000",
      "boughtQuantity": "0", "heldQuantity": "1.19842631",
      "cash": "0.00", "principal": "10000000",
      "balance": "100132.61", "balanceKrw": "135749793",
      "profit": "125749793", "returnRate": "12.574979",
      "fxRate": "1355.700000", "fxRateDate": "2026-10-01"
    },
    {
      "date": "2020-01-01", "kind": "month_first",
      "openPrice": "7196.39111328125000",
      "boughtQuantity": "1.19842631", "heldQuantity": "1.19842631",
      "tradeFee": "8.62…", "cash": "0.00…",
      "principal": "10000000", "balance": "8624.…", "balanceKrw": "…", "profit": "…", "returnRate": "…",
      "fxRate": "1156.400000", "fxRateDate": "2019-12-31"
    }
  ],
  "hasMore": true,
  "oldestReturned": "2024-05-01"
}
```

- 행은 **매달 첫 일봉**뿐이다(FR-038). `kind`는 언제나 `month_first`
- `firstDayMissing: "2021-03-01"` — 그 달 1일 일봉이 출처에 없어 `date`가 다른 날이 된 행에만 싣는다(FR-030, research R7-9)
- `tradeFee` — 매수가 있는 행에만(시세 통화). 해당 없으면 **키가 없다**(006과 같은 규약)
- `boughtQuantity`·`heldQuantity` — 소수 8자리 문자열(FR-026)
- `openPrice` — 출처 원값 그대로(소수 14자리, research R7-3). 표시 자릿수는 화면이 정한다(FR-040)
- **열별 통화**(006 FR-066과 같다): `openPrice`·`tradeFee`·`cash`·`balance`는 시세 통화, `balanceKrw`는 KRW, `principal`은 입력한 원금
  통화, `profit`·`returnRate`는 **KRW 기준**(FR-035)
- `summary.principalKrw` — 원금 통화가 KRW가 아니면(첫 매수일 매매기준율로 평가, FR-035)
- `summary.boughtOn` — 실제 매수일(시작 월 1일, 결측이면 그 달의 첫 일봉, FR-030)
- `summary.isFinal: false` — 일봉이 계산 끝보다 먼저 끊겼다(FR-024). `asOf`가 마지막 일봉 날짜
- `exchange` — 원화 원금일 때만(FR-034). 달러 원금이면 없다(006 FR-052와 같다)
- 환전·평가 환율은 **확정 환율만** 쓴다. 그 날짜에 잠정 환율만 있으면 이전 확정 고시일의 값이고, `fxRateDate`·`exchange.rateDate`가 그
  날짜다(FR-035, research R7-8)

### 202 — 수집 중 (FR-013, FR-036)

일봉과 환율 중 하나라도 비면 202다. **결과를 싣지 않는다.**

```json
{
  "status": "collecting",
  "coinId": 17,
  "jobId": 8,
  "missingFrom": "2020-01-01", "missingThrough": "2026-10-02",
  "progressUrl": "/api/crypto/progress?jobId=8",
  "fx": { "currency": "USD", "state": "queued", "busyWith": null,
          "missingFrom": "2020-01-01", "missingThrough": "2026-10-02" }
}
```

- 일봉이 다 있으면 `jobId`·`progressUrl`·`missingFrom`·`missingThrough`가 없다. 환율이 다 있으면 `fx`가 없다(006 contracts 5절과 같다)
- 환율 판정은 **원금 통화와 관계없이** 시세 통화가 KRW가 아니면 한다(006 FR-068)

### 오류

| 상황 | 상태 | `status` | 본문 추가 |
|------|------|----------|-----------|
| 원금이 숫자가 아니거나 0 이하, 날짜 형식 | 400 | `invalid_query` | |
| 원금 통화가 KRW도 시세 통화도 아니다 | 400 | `currency_pair_not_allowed` | `allowed` (FR-007) |
| 시작일이 첫 일봉보다 이르다 | 400 | `before_listing` | `startableFrom`, `basis: "price_start"` (FR-008) |
| 시작일이 계산 끝보다 늦다 | 400 | `start_after_end` | `lastDay` (FR-009) |
| `coinId`가 없다 | 404 | `unknown_coin` | `action: "reselect"` |
| 수집을 마쳤는데 일봉이 없다 | 404 | `no_price_data` | (005와 같다 — 예: Doge Killer, research R7-3) |
| 환율 구간을 수집으로 채울 수 없다 | 409 | `fx_not_available_before` | 006 contracts 6절과 같다 |
| 환율을 수집했는데 값이 없다 | 409 | `fx_unavailable` | 006과 같다 |

출처 차단·형식 오류는 **수집 작업의 실패**로 드러난다(진행 스트림의 `failed`, 아래). 시뮬레이션 요청은 실패한 구간을 다시 수집하려
202를 낸다 — 사용자가 다시 실행하면 다시 시도한다(005 FR-047a와 같다).

---

## `GET /api/crypto/simulation/series` — 차트 시계열 (FR-043, FR-044)

질의 매개변수는 표와 같고(`before`·`limit` 대신 `maxPoints`), 202·오류도 표와 같다.

```json
{
  "from": "2020-01-15", "to": "2026-10-02",
  "principalCurrency": "KRW", "basisCurrency": "KRW",
  "downsampled": true, "algorithm": "lttb", "sourcePointCount": 2467,
  "points": [ { "date": "2020-01-01", "balance": "9984231", "returnRate": "-0.001577" } ],
  "gaps": [ { "from": "2021-03-01", "to": "2021-03-01", "reason": "source_missing" } ]
}
```

- **점은 일봉마다**다(표는 월 행). 잔고는 KRW(`balanceKrw`), 수익률은 KRW 기준 — 표의 행·보드와 같은 계산 — 표의 행과 같은 날짜의 점은 그 행과 같은 값, 끝점은 보드와 같은 날짜·값(FR-044)
- `gaps.reason`: `not_collected`(미수집 — 200에는 없다, 202로 막힌다) | `source_missing`(**받은 구간 안의 출처 결측 — 끊어 그린다**,
  FR-023, research R7-9). 주식·외환의 `no_quote`(휴장 — 잇는다)는 가상자산에 없다

---

## `GET /api/crypto/progress?jobId=` — 수집 진행 (SSE) (FR-013)

006 `GET /api/stocks/progress`와 같은 사건과 머리글(`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`)이다.

- `snapshot`: `{"jobId", "status", "chunksDone", "chunksTotal", "daysDone", "daysTotal", "missingFrom", "missingThrough"}`
- `completed`: `{"jobId"}`
- `failed`: `{"jobId", "reason", "kind"}` — `kind`: `blocked` | `format` | `network` | `empty`(FR-020)

---

## `GET`·`PUT /api/crypto/settings` — 가상자산 거래 수수료율 (FR-032, FR-033)

```json
{ "tradeFeeRate": "0.001000", "isDefault": true }
```

- `PUT` 본문 `{"tradeFeeRate": "0.002"}` — 0 ≤ 값 < 1, 문자열. 아니면 `422 invalid_setting`
- 주식 설정(`/api/stocks/settings`)과 따로다

---

## 출처(investing.com) — 이 기능이 부르는 외부 API (research R7-1, R7-3, R7-4)

계약 테스트가 고정하는 것. 저장된 실제 응답 픽스처로 검증한다(헌법 원칙 III).

| 용도 | 요청 | 헤더 |
|------|------|------|
| 코인 목록 | `GET https://endpoints.investing.com/pd-instruments/v1/crypto/coins?sort=rank&order=asc&limit=100&domain_id={1\|18}[&cursor=]` | User-Agent |
| 일봉 | `GET https://api.investing.com/api/financialdata/historical/{instrument_id}?start-date=&end-date=&time-frame=Daily&add-missing-rows=false` | User-Agent, `domain-id: www` |

- 목록 응답 `{"coins": [...], "next_page_cursor": string | null}` — 쓰는 필드: `instrument_id`, `slug`, `symbol`, `name`, `rank`
- 일봉 응답 `{"data": [...], "summary": {...}}` — 쓰는 필드: `rowDateTimestamp`, `last_openRaw`, `last_maxRaw`, `last_minRaw`,
  `last_closeRaw`, `volume`, `volumeRaw`
- 403(본문 `403` 또는 HTML) = 차단(`blocked`), 400 = 요청 형식(`format`), 429·5xx = 재시도
