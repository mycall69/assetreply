# Contract: REST API

**Feature**: 001-fx-rate-history | **Date**: 2026-08-30

모든 응답은 `application/json; charset=utf-8`. 금액·비율은 **문자열**로 직렬화한다 —
JSON `number`는 IEEE 754 배정밀도라 `Decimal` 정밀도가 클라이언트에서 손실될 수 있고,
이는 헌법 원칙 VI를 API 경계에서 무력화한다.

---

## GET `/api/fx/rates/{currency}`

특정 날짜의 매매기준율과 파생 환율을 조회한다. (FR-016, FR-020, FR-022)

**Path**: `currency` — `USD` | `JPY` | `EUR`
**Query**: `date` (필수, `YYYY-MM-DD`)

### 200 — 고시 존재

```json
{
  "status": "quoted",
  "currency": "USD",
  "date": "2005-03-15",
  "quoteUnit": 1,
  "baseRate": "1012.30",
  "derived": {
    "cashBuy":      "1014.12",
    "cashSell":     "1010.48",
    "remitSend":    "1012.81",
    "remitReceive": "1011.79"
  },
  "appliedSpread": {
    "cashBuy": "0.001800", "cashSell": "0.001800",
    "remitSend": "0.000500", "remitReceive": "0.000500"
  },
  "spreadBasis": "current",
  "source": "ECOS:731Y001"
}
```

`spreadBasis: "current"`는 현재 설정된 스프레드를 과거 날짜에 적용한 가정 비교임을 나타낸다
(FR-026, FR-026a). `quoteUnit: 100`이면 `baseRate`는 100단위당 원화다(JPY).

### 200 — 고시 없는 날 (FR-018, FR-018a, FR-018b)

```json
{
  "status": "no_quote",
  "currency": "USD",
  "date": "2005-03-19",
  "message": "해당일에는 고시가 없습니다.",
  "reference": {
    "kind": "previous_business_day",
    "date": "2005-03-18",
    "quoteUnit": 1,
    "baseRate": "1010.90",
    "note": "요청하신 2005-03-19의 값이 아닙니다."
  }
}
```

`baseRate`와 `derived`가 최상위에 **없다**. 참고 값은 `reference` 안에만 존재하며,
클라이언트가 주 결과와 혼동할 수 없는 구조다.

### 202 — 수집이 필요하고 임계값을 초과 (FR-035a)

```json
{
  "status": "collecting",
  "currency": "USD",
  "date": "2005-03-15",
  "jobId": 42,
  "missingDays": 7834,
  "progressUrl": "/api/fx/progress?jobId=42"
}
```

필요 구간이 임계값(기본 30일) 이하이면 수집을 마친 뒤 `200`을 반환한다 (FR-035).

> **단계 조건**: `progressUrl`이 가리키는 SSE 엔드포인트는 User Story 4에서 구현된다.
> US1·US3만 인도된 상태에서는 이 필드를 응답에 포함하지 않는다. 클라이언트는 필드 부재를
> "진행률 구독 불가"로 해석하고 수집 중 안내만 표시한다.

### 400 — 조회 가능 범위 밖 (FR-019)

```json
{
  "status": "out_of_range",
  "message": "조회 가능한 범위를 벗어났습니다.",
  "availableFrom": "1964-05-04",
  "availableThrough": "2026-08-29"
}
```

---

## GET `/api/fx/series`

차트용 시계열을 조회한다. (FR-028, FR-032, FR-032a, FR-033)

**Query**: `currency` (필수), `from`, `to` (필수), `maxPoints` (선택, 기본 2000)

### 200

```json
{
  "currency": "USD",
  "quoteUnit": 1,
  "from": "1964-05-04",
  "to": "2026-08-29",
  "downsampled": true,
  "algorithm": "lttb",
  "sourcePointCount": 8412,
  "points": [
    { "date": "1964-05-04", "baseRate": "255.00" },
    { "date": "1997-12-23", "baseRate": "1962.00" }
  ],
  "gaps": [
    { "from": "2020-01-24", "to": "2020-01-27", "reason": "no_quote" },
    { "from": "2026-08-01", "to": "2026-08-29", "reason": "not_collected" }
  ]
}
```

**계약상 보증**
- `points`의 모든 값은 저장된 원본 값이다. 다운샘플링은 **선택만 하며 값을 생성하지 않는다**
  (헌법 원칙 V, research R5).
- `gaps`는 결측 구간을 명시한다. 클라이언트는 이 구간을 선으로 잇지 않는다 (FR-032, FR-032b).
- `reason`은 `no_quote`(고시 없음)와 `not_collected`(미수집)를 구분한다.

### 202 — 요청 구간에 미수집이 있고 임계값 초과 (FR-032a)

`/api/fx/rates`의 202와 동일한 형태.

---

## GET `/api/fx/spreads` · PUT `/api/fx/spreads/{currency}`

스프레드 설정 조회·변경. (FR-021, FR-025)

**PUT 요청 본문**

```json
{ "cashBuy": "0.0018", "cashSell": "0.0018", "remitSend": "0.0005", "remitReceive": "0.0005" }
```

### 422 — 허용 범위 위반

```json
{
  "status": "invalid_spread",
  "message": "스프레드는 0 이상 1 미만이어야 합니다.",
  "violations": [{ "field": "cashBuy", "value": "-0.1" }]
}
```

기존 값은 변경되지 않는다 (FR-025).

---

## GET `/api/fx/coverage`

통화별 수집 완료 구간. (FR-004, FR-005)

```json
{
  "coverage": [
    {
      "currency": "USD",
      "coveredFrom": "1964-01-01",
      "coveredThrough": "2026-08-29",
      "firstAvailableDate": "1964-05-04",
      "lastUpdatedAt": "2026-08-30T01:12:44.120Z"
    }
  ]
}
```

---

## POST `/api/fx/collect`

수집을 명시적으로 시작한다.

**요청**: `{ "currency": "USD" }` (생략 시 전 통화)

### 202 — 시작됨 / 진행 중 작업에 합류 (FR-015b)

```json
{ "jobs": [{ "currency": "USD", "jobId": 42, "joinedExisting": false }] }
```

`joinedExisting: true`는 이미 진행 중인 작업이 있어 새 작업을 만들지 않고 합류했음을 뜻한다.

---

## GET `/api/fx/jobs`

수집 작업 이력. (FR-037)

**Query**: `currency` (선택), `status` (선택), `limit` (기본 50)

```json
{
  "jobs": [
    {
      "jobId": 41, "currency": "JPY", "status": "partial",
      "rangeStart": "1964-01-01", "rangeEnd": "2026-08-29",
      "chunksTotal": 32, "chunksDone": 18,
      "startedAt": "2026-08-30T00:03:01.000Z",
      "finishedAt": "2026-08-30T00:19:52.000Z",
      "lastError": "호출 한도 초과(INFO-300)가 반복되어 중단했습니다."
    }
  ]
}
```

실패·부분 성공 이력은 영구 보관된다 (FR-038a).

---

## 공통 오류

| 상태 | `status` | 상황 |
|------|----------|------|
| 400 | `out_of_range` | 조회 범위 밖 (FR-019) |
| 404 | `unknown_currency` | 지원하지 않는 통화 |
| 422 | `invalid_spread` | 스프레드 범위 위반 |
| 502 | `source_unavailable` | 출처 응답이 유효하지 않음 (비-JSON 등) |
| 503 | `source_rate_limited` | 출처 호출 한도 소진 (FR-013). 저장된 데이터는 유효 |
