# REST API 계약 (012)

**Date**: 2026-10-06 | **Research**: [../research.md](../research.md) R12-5~R12-11

공통 규약은 005~011 그대로다.
- 금액·비율·환율은 **문자열**이다. 해당이 없으면 키를 두지 않는다.
- 날짜는 ISO 날짜, 시각은 UTC ISO 시각(`Z`)이다.
- 오류 본문은 `{status, message, …}`이다.

**바뀌지 않는 것**: 시계열 경로(`…/series`)는 질의·응답 모두 그대로다. 표 경로 응답의 `summary`·`condition`·`stock`/`coin`·`exchange`도 그대로다(spec FR-007·FR-017).
외환 경로는 그대로다.

## 1. 표 경로 넷 — 기간 단위

대상 경로:
- `GET /api/stocks/simulation`
- `GET /api/crypto/simulation`
- `GET /api/stocks/recurring-simulation`
- `GET /api/crypto/recurring-simulation`

### 1.1 질의

| 매개변수 | 필수 | 뜻 |
|----------|------|----|
| `period` | | `daily` · `weekly` · `monthly`. 기본 `daily`. 밖이면 400 `invalid_query`("기간 단위는 daily · weekly · monthly 중 하나여야 합니다") — 기본값으로 바꾸지 않는다 |
| 그 밖 | | 지금 그대로(`before`·`limit`·`end`·…). 적립식의 `frequency`는 납입 주기이고 `period`와 다르다 |

### 1.2 응답의 바뀌는 곳

```jsonc
{
  "period": "weekly",              // 받은 단위를 그대로 싣는다 — 화면이 늦은 응답을 가른다
  "summary": { … },                // 그대로 — 단위와 무관하다(US5 — 일시금 둘은 totalKrw를 더한다, 아래)
  "rows": [ … ],                   // 아래 1.3
  "hasMore": true,
  "oldestReturned": "2026-08-21"   // 마지막 행의 커서 날짜(결측 구간 행은 처음 날짜)
}
```

- **US5(반복 2026-10-07)** — 주식·가상자산 **일시금** 표 경로의 `summary`에 `totalKrw`(문자열 — 기준일의 원화 총자산, 매도 비용 전)를 더한다.
  적립식 두 경로의 `summary.totalKrw`는 011부터 있다(그대로). 다른 키와 `/series`는 바뀌지 않는다(data-model 4.1).

  ```jsonc
  "summary": { "principal": "10000000", "profit": "4630000", "totalKrw": "14630000", … }   // totalKrw − (principalKrw ?? principal) = profit
  ```

### 1.3 행

| `kind` | 경로 | 뜻 | 키 |
|--------|------|----|----|
| `buy` | 일시금 둘 | 첫 매수(첫 평가일) — 단위와 무관하게 늘 있다 | 지금 매수 행(그 달 첫 거래일 행)의 키 그대로(`boughtShares`/`boughtQuantity`·`tradeFee` 등) |
| `dividend` | 주식 둘 | 배당락 | 지금 그대로 |
| `reinvest` | 주식 둘 | 재투자 | 지금 그대로 |
| `contribution` | 적립식 둘 | 납입(미뤄진 납입 `deferred` 포함) | 지금 그대로 |
| `period` | 넷 | 기간 행 — 대표일의 하루 평가 | 지금 월 행(`month_first`)의 키 그대로. 매수 칸은 0·수수료 없음 |
| `missing` | 가상자산 둘, `period=daily`만 | 연속된 출처 결측 구간 하나 — 값 없음 | `date`(처음)·`dateTo`(끝)만 |

**표시 키** — `period` 행과, 대표일의 마지막 사건 행에만 붙는다.

| 키 | 있을 때 | 뜻 |
|----|---------|----|
| `shiftedFrom` | 대표일 ≠ 기준일 | 원래 기준일(주 = 그 주 금요일, 월 = 그 달 말일). 없으면 옮겨지지 않았다 |
| `isOngoing` | 주·월에서 구간 끝 > 계산 끝 | 항상 `true`. 없으면 끝난 구간이다 |

**없어지는 것**
- 표 행의 `kind: "month_first"` — 계산 모듈 안에서는 주식 차트의 재료로 남는다
- 가상자산 표 행의 `firstDayMissing`(◇) — spec FR-008

**차례**: 최신순이다. 같은 날 행의 차례는 지금과 같다(일시금은 배당 → 재투자, 적립식은 늦은 사건이 위). 같은 날의 행은 한 쪽에 붙잡는다 — `limit`보다 조금
많을 수 있다. 결측 구간 행은 그 구간의 자리(끝 다음 날 행과 처음 전날 행 사이)에 온다.

예 — 미국 주식 일시금, `period=weekly`, 계산 끝 2026-10-05(월), 10-05에 일봉 있음:

```jsonc
"rows": [
  {"date": "2026-10-05", "kind": "period", "shiftedFrom": "2026-10-09", "isOngoing": true, "openPrice": "…", "closePrice": "…", "heldShares": 120, …},
  {"date": "2026-10-02", "kind": "period", …},                        // 금요일 — 표시 없음
  {"date": "2026-09-29", "kind": "dividend", "dividendPerShare": "0.26", …},   // 사건 행 — 늘 있다
  {"date": "2026-09-26", "kind": "period", …}
]
```

맨 위 행은 이번 주(10-05~10-11)의 계산 기간 안 마지막 시세일 10-05다. 기준일(금요일 10-09)이 계산 끝 뒤라 옮겨졌고, 구간 끝(10-11)이 계산 끝 뒤라 진행 중이다.
국내 주식처럼 10-05가 휴장이면 이번 주 ∩ 계산 기간에 시세일이 없어 그 주의 행이 없다 — 맨 위는 앞 주의 대표일 10-02(금)이고 표시가 없다.

예 — 가상자산 일시금, `period=daily`, 10-02·10-03 결측:

```jsonc
"rows": [
  {"date": "2026-10-04", "kind": "period", …},
  {"date": "2026-10-02", "dateTo": "2026-10-03", "kind": "missing"},
  {"date": "2026-10-01", "kind": "period", …}
]
```

## 2. `GET /api/history/{asset}` — 이력 목록

`asset`은 `stock` · `crypto` · `deposit` · `realestate`다. 밖이면 404 `unknown_asset`.

목록을 읽기 전에 그 자산군의 기한 지난 항목을 지운다(research R12-10 — 조회가 쓰기를 하는 유일한 경우).

**200**:

```jsonc
{
  "entries": [                         // 마지막 실행 시각 내림차순
    {
      "id": "KRX|005930.KS|2020-01-02|10000000|KRW|R",   // 서버가 계산한 조건 식별자
      "stock": {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
      "start": "2020-01-02", "principal": "10000000", "principalCurrency": "KRW", "reinvest": true,
      "lastRunAt": "2026-10-06T09:12:00Z"
    }
  ],
  "retentionDays": 30                  // 무기한이면 null
}
```

항목의 조건 칸은 지금 화면 항목(`SimulationHistoryEntry` 등)과 같다(data-model 2). `savedAt` 대신 `lastRunAt`이다.

## 3. `PUT /api/history/{asset}` — 실행한 조건 저장

본문 `{"condition": { …data-model 2의 칸… }}`. 같은 식별자가 있으면 마지막 실행 시각·보관 기준 시각을 지금으로 바꾸고 맨 앞으로 온다.

- **200**: 2와 같은 본문(저장 뒤 목록)
- **422** `invalid_history`: 칸이 빠졌거나 형식이 틀리다. 메시지가 어느 칸인지 말한다
- 404 `unknown_asset`

## 4. `DELETE /api/history/{asset}?id=<식별자>` — 항목 삭제

- **200**: 2와 같은 본문. 없는 `id`도 200이다(이미 지워졌다 — 멱등).
- 400 `invalid_query`: `id`가 없다.

## 5. `POST /api/history/{asset}/import` — 브라우저 이력 옮기기

본문 `{"entries": [ …브라우저 키의 항목 그대로… ]}`. 항목의 `id`는 쓰지 않고 서버가 다시 계산한다. `savedAt`이 있으면 마지막 실행 시각으로 쓴다.

**200**:

```jsonc
{
  "imported": 5,     // 새로 넣은 항목 수
  "merged": 1,       // 이미 있던 조건과 합친 수(마지막 실행·보관 기준은 늦은 쪽)
  "skipped": 0,      // 검증에 실패해 건너뛴 수 — 화면이 0보다 크면 알린다
  "entries": [ … ], "retentionDays": 30          // 2와 같다
}
```

- 옮긴 항목의 보관 기준 시각은 옮긴 시각이다 — 마지막 실행이 기간보다 오래된 항목도 옮겨져 남는다(spec FR-013, 명확화 4).
- 400 `invalid_query`: 본문이 `{"entries": 배열}`이 아니다. 항목 하나하나의 검증 실패는 `skipped`로 센다 — 오류가 아니다.
- 화면은 2xx일 때만 브라우저 키를 지운다.

## 6. `GET` · `PUT /api/history/settings` — 보관 기간

경로 `/api/history/{asset}`보다 **먼저** 등록한다 — `settings`가 자산군 매개변수로 잡히지 않게 한다.

**GET 200**:

```jsonc
{"retentionDays": 30, "isDefault": true, "options": [7, 30, 90, 180, 365, null]}
```

**PUT** 본문 `{"retentionDays": 7}`(무기한은 `null`).
- **200**: GET 본문. 저장한 뒤 모든 자산군의 기한 지난 항목을 곧바로 지운다(spec FR-012 — 줄이면 곧바로 반영).
- **422** `invalid_setting`: `options` 밖이거나, 정수·`null`이 아니다(`true`·`"30"`·`30.0` 포함). 기본값으로 바꾸지 않는다.

## 7. 오류 처리기

| 예외 | 상태 | `status` |
|------|------|----------|
| `UnknownAsset` | 404 | `unknown_asset` |
| `InvalidHistory` | 422 | `invalid_history` — PUT의 조건 검증 실패 |
| `InvalidSetting`(있음) | 422 | `invalid_setting` |
| `InvalidQuery`(있음) | 400 | `invalid_query` |
