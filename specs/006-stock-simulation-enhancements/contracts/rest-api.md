# REST API 계약 — 006

**Feature**: `006-stock-simulation-enhancements` | **Date**: 2026-10-02

005의 계약(`specs/005-stock-investment-simulation/contracts/rest-api.md`)에서 **바뀌는 것과 새로 생기는
것만** 적는다. 금액·비율은 005와 같이 문자열이다.

| 엔드포인트 | 상태 |
|------------|------|
| `GET /api/stocks/search` | **바뀜** — 로컬 목록(국내·미국)만 |
| `GET /api/stocks/search/external` | **신규** — 일본(TSE)만, 외부 출처 |
| `POST /api/stocks/selection` | **신규** — 고른 종목을 등록 |
| `GET /api/stocks/simulation`, `GET /api/stocks/simulation/series` | **바뀜** — 오류 2종, 202에 환율 상태 |
| `GET /api/fx/series`·`/daily`·`/rates`·`/latest`의 202 (001) | **바뀜** — `jobId`가 `null`일 수 있음, `state`·`busyWith` 추가 (FR-046a) |

---

## `GET /api/stocks/search` — 로컬 목록 검색

국내(KOSPI·KOSDAQ·ETF·리츠)와 미국(NYSE·NASDAQ·AMEX)의 검색용 목록에서 찾는다. **외부 출처를
부르지 않는다**(FR-027). 그날 처음 들어온 검색이면 갱신을 요청하되 **기다리지 않는다**(FR-017).

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `q` | 예 | 한글명·초성·혼용·영문명·코드·티커 (1자 이상) |
| `limit` | 아니오 | 기본 20, 최대 50 |

### 200 응답

```json
{
  "query": "ㅅㅅㅈㅈ",
  "results": [
    {
      "listingId": 1021,
      "country": "KR",
      "market": "KRX",
      "symbol": "005930.KS",
      "code": "005930",
      "name": "삼성전자",
      "nameEn": null,
      "currency": "KRW",
      "kind": "stock",
      "listedOn": "1975-06-11",
      "listingStatus": "listed",
      "match": "prefix"
    }
  ],
  "truncated": true,
  "lists": [
    { "unit": "KOSPI",  "state": "ready",      "asOf": "2026-10-02T00:05:12Z" },
    { "unit": "NASDAQ", "state": "refreshing", "asOf": "2026-10-01T00:07:40Z" },
    { "unit": "AMEX",   "state": "never",      "asOf": null,
      "reason": "auth_missing", "action": "set_credentials" }
  ]
}
```

- `market`·`symbol`은 **005의 시세 식별자**다(research R6-6). 이력과 시뮬레이션은 이것을 쓴다.
- `listedOn`은 국내만. **시작 가능 날짜가 아니라 하한**이다(FR-005a). 화면은 시작일이 이보다 이르면
  실행 전에 알린다(FR-005).
- `listingStatus: "missing"` — 목록에서 빠진 종목(FR-019). 결과에 남기되 표시한다(FR-025).
- `kind` — `stock` \| `etf` \| `reit`. 미국 ETF도 `etf`다.
- `truncated` — 상한에서 잘렸으면 `true`(FR-024).
- `lists` — 단위마다 상태와 기준 시각(FR-028, FR-029). 상태 값은 data-model 2절.
  `reason`: `auth_missing` \| `auth_failed` \| `rate_limit` \| `network` \| `invalid`.
  `action`: `set_credentials` \| `wait` \| `retry_later` — 사용자가 할 일(FR-028a).
- 결과가 없어도 `lists`는 항상 온다. **화면은 `results`가 비었을 때 `lists`를 보고 "결과 없음"과
  "목록 없음"을 가른다**(FR-028, SC-006).

### 순서 (FR-023)

정확 일치 → 앞부분 일치 → 포함. 같은 순위 안에서는 일치한 이름이 짧은 순 → 가나다·알파벳순 →
시장 → 코드. **같은 질의면 언제나 같은 순서다**(SC-003).

### 오류

| 상황 | 상태 | `status` |
|------|------|----------|
| `q`가 비었다 | 400 | `invalid_query` |

목록이 없거나 갱신이 실패해도 **오류가 아니다** — 200에 `lists`로 알린다. 오류로 내면 화면이 "검색
실패"로만 보이고 무엇을 해야 하는지 말할 자리가 없다.

---

## `GET /api/stocks/search/external` — 일본 종목 검색

005의 외부 출처 검색이다. **결과에서 TSE만 남긴다**(FR-026). 국내·미국 종목은 로컬 검색이 맡는다.

### 질의 매개변수

`q`(필수), `limit`(기본 20).

### 200 응답

```json
{
  "query": "toyota",
  "results": [
    { "market": "TSE", "symbol": "7203.T", "name": "Toyota Motor Corporation",
      "currency": "JPY", "kind": "stock" }
  ]
}
```

### 오류

005와 같다 — 출처 장애 `502 source_unavailable`, 한도 `503 source_rate_limited`. 화면은 이 실패를
**일본 영역에만** 표시한다(FR-027).

---

## `POST /api/stocks/selection` — 고른 종목 등록

검색 결과 하나를 받아 종목을 등록하고, 이후 요청이 쓸 식별을 돌려준다(FR-030, FR-030a, FR-030b,
research R6-17).

### 요청

로컬 결과:

```json
{ "source": "listing", "listingId": 1021 }
```

일본 결과:

```json
{ "source": "external", "market": "TSE", "symbol": "7203.T",
  "name": "Toyota Motor Corporation", "currency": "JPY" }
```

### 200 응답

```json
{ "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
  "currency": "KRW", "listedOn": "1975-06-11" }
```

- 미국: 같은 티커의 종목이 이미 있으면 **거래소가 달라도 그 종목**을 돌려준다(FR-030a).
- 이미 등록된 종목이면 새로 만들지 않는다(FR-030, SC-007).

### 오류

| 상황 | 상태 | `status` |
|------|------|----------|
| `listingId`가 없다 | 404 | `unknown_listing` |
| `external`인데 시장이 TSE가 아니거나 통화가 JPY가 아니다 | 400 | `invalid_query` |

---

## `GET /api/stocks/simulation`·`/series` — 바뀌는 점

질의 매개변수와 200 응답은 005와 같다. 다음이 바뀐다.

### 1. 원금 통화 (FR-050~050d)

`principalCurrency`는 `KRW` 또는 **종목 통화**여야 한다. `EUR`은 더 이상 받지 않는다.

| 상황 | 상태 | `status` |
|------|------|----------|
| 원화도 종목 통화도 아니다 | 400 | `currency_pair_not_allowed` |

```json
{ "status": "currency_pair_not_allowed",
  "message": "원금 통화는 KRW 또는 종목 통화(USD)여야 합니다: EUR",
  "allowed": ["KRW", "USD"] }
```

**어느 경로로 들어온 요청이든 같은 판정**을 거친다 — 이력에서 다시 실행한 요청도 마찬가지다(FR-050a).

### 2. 시작 가능 날짜 (FR-005, FR-005a)

`400 before_listing`의 본문에 **시작 가능 날짜**를 싣는다. 화면이 그 날짜로 옮기는 수단을 그린다.

```json
{ "status": "before_listing",
  "message": "2000-01-04부터 시세가 있습니다. 그 이전은 계산할 수 없습니다.",
  "startableFrom": "2000-01-04",
  "basis": "price_start" }
```

- `basis: "listing"` — 목록의 상장일보다 이르다. **시세를 받기 전에** 낸다.
- `basis: "price_start"` — 수집 범위가 시작일을 덮는데 시작 월에 일봉이 없다. 시세를 받은 뒤 낸다.

**시작일을 몰래 옮기지 않는다**(005 FR-005, SC-013a).

### 3. 종목 미등록 (FR-030b)

국내·미국 종목이 아직 등록되지 않았으면 **검색용 목록으로 등록한 뒤 진행**한다(이력 재실행 경로).
시세 식별자에서 목록을 찾는 규칙은 research R6-6의 **역변환**이다. 역변환으로 찾지 못하면 국내·미국도
`404 unknown_stock`에 `"action": "reselect"`를 싣는다. 일본 종목은 언제나 이렇게 답한다.

```json
{ "status": "unknown_stock",
  "message": "목록에서 찾을 수 없는 종목입니다: NYSE:BRK-B. 검색에서 다시 고르세요.",
  "action": "reselect" }
```

### 4. 시세 출처가 종목을 모를 때 (FR-032)

| 상황 | 상태 | `status` |
|------|------|----------|
| 시세 출처가 그 심볼을 모른다 | 404 | `price_symbol_unknown` (**신규**) |
| 받았는데 그 구간에 시세가 없다 | 404 | `no_price_data` (005 그대로) |

005는 앞의 경우도 `unknown_stock`으로 냈다. 둘을 섞으면 식별자 변환 결함이 "데이터 없는 종목"으로
위장된다.

출처가 모른다는 사실은 **수집 중에** 드러난다(research R6-6). 그래서 두 곳이 함께 바뀐다.

- 진행 스트림(`GET /api/stocks/progress`)의 `failed` 사건에 `status`를 싣는다:
  `{"jobId": 31, "reason": "시세 출처가 그 종목을 알지 못합니다.", "status": "price_symbol_unknown"}`.
  다른 실패는 005 그대로 `status`가 없다
- 그 뒤의 시뮬레이션 요청은 수집을 다시 시작하지 않고 `404 price_symbol_unknown`으로 답한다

### 5. 202 — 환율 상태 (FR-043~046)

원금이 원화이고 종목이 외화면, 주식 시세와 함께 **환율 범위**도 본다. 둘 중 하나라도 비면 202다.
둘 다 끝나기 전에는 결과를 내지 않는다(FR-045).

```json
{
  "status": "collecting",
  "market": "TSE", "symbol": "7203.T",
  "jobId": 31,
  "missingFrom": "2020-01-01", "missingThrough": "2026-10-01",
  "progressUrl": "/api/stocks/progress?jobId=31",
  "fx": {
    "currency": "JPY",
    "state": "waiting",
    "busyWith": "USD",
    "missingFrom": "2020-01-01",
    "missingThrough": "2026-10-01"
  }
}
```

- 주식 시세가 다 있으면 `jobId`·`progressUrl`·`missingFrom`·`missingThrough`가 없다.
- `fx.state`: `queued`(큐에 넣음) \| `collecting`(진행 중) \| `waiting`(**다른 통화의 수집 중** —
  `busyWith`에 그 통화, FR-046). 화면은 003의 수집 스트림(`/api/fx/collection/stream?currency=`)을
  구독하고, `waiting`이면 그 수집이 끝난 뒤 시뮬레이션을 다시 요청한다(research R6-10).

### 6. 수집으로 채울 수 없는 구간 (FR-043a)

| 상황 | 상태 | `status` | `reason` |
|------|------|----------|----------|
| 필요한 날짜가 출처의 최초 고시일 이전 | 409 | `fx_not_available_before` (**신규**) | `before_first_quote` |
| 필요한 날짜가 외환 수집의 탐색 시작일(설정) 이전 | 409 | `fx_not_available_before` | `before_probe_start` |

```json
{ "status": "fx_not_available_before",
  "reason": "before_first_quote",
  "message": "1971-01-04 이전의 JPY 환율은 출처에 없습니다.",
  "currency": "JPY", "availableFrom": "1971-01-04" }
```

```json
{ "status": "fx_not_available_before",
  "reason": "before_probe_start",
  "message": "JPY 환율 수집 범위가 2000-01-01부터로 설정되어 있습니다. 설정을 바꾸면 받을 수 있습니다.",
  "currency": "JPY", "availableFrom": "2000-01-01" }
```

둘 다 수집을 시작하지 않는다. 시작하면 끝나도 여전히 비어 다시 수집하게 된다. **두 사유를 섞지 않는다** —
`before_probe_start`를 `before_first_quote`로 말하면 설정으로 풀리는 제약이 영영 불가능한 것으로 읽힌다.
판정 근거는 `currency.first_available_date`(001)와 `probe_start(통화)`다(research R6-10).
**`before_probe_start`를 먼저 판정한다** — 기록된 최초 고시일은 수집한 범위 안의 첫 날이라, 탐색 시작일보다
앞은 출처에 있는지 모른다(analyze N2).

### 6a. 외환 화면의 202 — 바뀌는 점 (FR-046a)

001이 정한 외환 화면의 수집 중 응답이다. 006이 `ensure_background_job`을 고치면서 바뀐다(research R6-10).

```json
{ "status": "collecting", "currency": "JPY",
  "from": "2020-01-01", "to": "2026-10-01", "missingDays": 2465,
  "state": "queued", "jobId": null, "busyWith": null,
  "progressUrl": "/api/fx/collection/stream?currency=JPY" }
```

- `state`: `collecting`(실행 중 — `jobId`가 있다) \| `queued`(큐에 있다, 아직 작업 번호 없음) \| `waiting`
  (다른 통화 처리 중 — `busyWith`에 그 통화).
- `jobId`가 `null`이면 `progressUrl`은 003의 **통화별 스트림**이다. 작업이 시작되면 그 스트림이 진행을 보낸다.
- 큐가 거절해도 작업을 만들지 않는다 — 실행되지 않는 작업이 다시 생기는 것을 막는다.
- 통화별 스트림(`/api/fx/collection/stream`)의 `idle`·`snapshot`에 실리는 `busyWith`는 **프레임마다**
  큐의 지금 상태다(003은 연결할 때의 값을 끝까지 보냈다). `waiting`인 화면은 이 값이 비는 것을 보고
  다시 요청한다(research R6-10).

### 7. 엔화 환산 (FR-042)

응답 모양은 같다. **값이 바뀐다** — `exchange.rate`와 행의 `fxRate`는 **1엔당** 원화 값이다(예:
`9.000000`). 005는 100엔당 값(`900.000000`)을 1엔당으로 썼다.

---

## `GET /api/stocks/progress` — 받은 날 / 받을 날 (FR-045a) — 반복 2026-10-03

`snapshot` 사건에 두 필드를 더한다. 기존 필드는 그대로다(호환).

```json
{ "jobId": 127, "chunksDone": 1, "chunksTotal": 4,
  "rangeStart": "2020-01-01", "rangeEnd": "2026-10-02",
  "daysDone": 730, "daysTotal": 2467 }
```

- `daysTotal`: 작업 구간(`rangeStart`~`rangeEnd`, 양끝 포함)의 달력 일수
- `daysDone`: 그 구간 가운데 주식 커버리지가 덮는 달력 일수. 청크마다 커밋된 커버리지로 계산한다 — 작업 구간 앞뒤로
  이미 받아 둔 구간이 겹치면 처음부터 0보다 크다
- 화면은 `daysDone / daysTotal`을 3자리 쉼표로 보인다(`730 / 2,467일`)

## 모든 `text/event-stream` 응답의 머리글 (FR-045a) — 반복 2026-10-03

```
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
```

대상: `/api/stocks/progress`, `/api/fx/collection/stream`(003), 001의 진행 스트림. **`no-transform`이 없으면 중간
프록시가 압축하면서 이벤트를 모아 둔다** — 2026-10-03 실측으로 Next.js 개발 서버(3030)가 브라우저 요청에 gzip을 걸어
스트림이 끝날 때까지 이벤트가 도착하지 않았다(research R6-19).
