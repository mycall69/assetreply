# REST API 계약 — 신설·변경분

**Feature**: 002-fx-analysis-workspace | **Date**: 2026-08-30

001의 엔드포인트는 그대로 유지된다. 이 문서는 **신설·변경분만** 다룬다.
공통 오류 형식과 상태 코드 매핑은 [001 rest-api.md](../../001-fx-rate-history/contracts/rest-api.md)를 따른다.

**전역 규약** — 금액·비율은 모두 **문자열**로 주고받는다. JSON `number`는 IEEE 754라
`Decimal` 정밀도가 손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.

---

## 신설 `GET /api/fx/latest`

요약 영역이 쓴다. 현재 통화의 가장 최근 값과 직전 대비 변화를 반환한다 (FR-011~014).

**Query**: `currency` (필수, `USD`|`JPY`|`EUR`)

### 200 — 값이 있음

```json
{
  "currency": "USD",
  "quotePair": "USD/KRW",
  "date": "2026-08-30",
  "baseRate": "1354.200000",
  "quoteUnit": 1,
  "isProvisional": true,
  "fetchedAt": "2026-08-30T14:23:11Z",
  "change": {
    "comparedTo": "2026-08-29",
    "absolute": "-2.000000",
    "percent": "-0.15",
    "direction": "down"
  }
}
```

- `isProvisional`이 `true`면 오늘 잠정값이다. 화면은 이를 확정값과 구분해 표시해야 한다(FR-014).
- `fetchedAt`은 잠정값일 때만 의미가 있다. 마지막으로 받아온 시각이다(FR-038).
- `change.comparedTo`는 **직전 고시일**이다. 요약이 잠정값일 때 비교 대상은 직전 확정값이다(FR-013).
- `direction`은 `up` | `down` | `flat`. 색에만 의존하지 않도록 방향을 값으로 내려준다.

### 200 — 값이 아직 없음

```json
{ "currency": "USD", "status": "no_data", "message": "아직 수집된 데이터가 없습니다." }
```

### 202 — 수집이 필요하고 임계값을 초과

조회 구간에 미수집이 있고 필요한 구간이 임계값을 넘으면, 001의 자동 수집 규칙을 그대로
적용해 백그라운드 수집을 시작하고 진행 상태를 반환한다(FR-048). 응답 형식은 001의
`GET /api/fx/rates` 202와 같으며 `progressUrl`로 진행률을 구독한다.

### 404 — 지원하지 않는 통화

001의 `unknown_currency` 형식과 상태 코드를 그대로 따른다.

---

## 신설 `GET /api/fx/daily`

일자별 상세 표가 쓴다. 매매기준율과 **파생 환율 4종을 서버가 산출해** 함께 반환한다
(FR-020~026, research R2-5).

**Query**

| 이름 | 필수 | 기본값 | 설명 |
|------|:----:|--------|------|
| `currency` | ✓ | — | 통화 코드 |
| `before` | | 없음 | 이 날짜 **미만**의 고시일만 반환. 더 과거를 이어 볼 때 쓴다(FR-026) |
| `limit` | | 설정값(30) | 반환할 최대 행 수 |

### 200

```json
{
  "currency": "USD",
  "quoteUnit": 1,
  "appliedSpread": {
    "cashBuy": "0.001800", "cashSell": "0.001800",
    "remitSend": "0.000500", "remitReceive": "0.000500"
  },
  "spreadBasis": "current",
  "rows": [
    {
      "date": "2026-08-30",
      "baseRate": "1354.200000",
      "isProvisional": true,
      "derived": {
        "cashBuy": "1356.64", "cashSell": "1351.76",
        "remitSend": "1354.88", "remitReceive": "1353.52"
      }
    },
    {
      "date": "2026-08-29",
      "baseRate": "1356.100000",
      "isProvisional": false,
      "derived": { "cashBuy": "1358.54", "cashSell": "1353.66",
                   "remitSend": "1356.78", "remitReceive": "1355.42" }
    }
  ],
  "hasMore": true,
  "oldestReturned": "2026-07-18"
}
```

**규약**

- 고시가 없는 날은 **행을 만들지 않는다**(FR-021). 날짜가 연속하지 않는 것이 정상이다.
- `spreadBasis: "current"`는 파생값이 "현재 스프레드를 과거에 적용한 가정"임을 뜻한다(FR-024).
  화면은 이를 문구로 드러내야 한다.
- `hasMore`가 `true`면 `oldestReturned`를 다음 요청의 `before`로 보내 이어 받는다.
- `derived`는 표시용 반올림(소수 2자리)이 적용된 값이다. 반올림은 여기서 한 번만 일어난다.
- `baseRate`는 저장 정밀도 그대로다. 내려받기가 이 값을 쓴다(FR-045).
- 요청 구간에 미수집이 있으면 001의 자동 수집 규칙을 적용한다. 임계값을 넘으면 `202`로
  진행 상태를 반환한다(FR-048). 형식은 `GET /api/fx/latest`의 202와 같다.
- 선택 날짜가 현재 응답 범위 밖이면 클라이언트가 `before`를 그 날짜 다음날로 지정해 다시
  요청한다(FR-022a).

---

## 신설 `POST /api/fx/today/refresh`

오늘 하루치만 다시 받아온다 (FR-036~040).

**Body**: `{ "currency": "USD" }`

### 200 — 갱신됨

```json
{
  "currency": "USD",
  "status": "updated",
  "date": "2026-08-30",
  "baseRate": "1354.200000",
  "isProvisional": true,
  "fetchedAt": "2026-08-30T14:23:11Z",
  "joinedExisting": false
}
```

### 200 — 오늘 고시가 없음

```json
{
  "currency": "USD",
  "status": "no_quote_today",
  "date": "2026-08-30",
  "message": "오늘은 아직 고시가 없습니다.",
  "fetchedAt": "2026-08-30T14:23:11Z"
}
```

값을 만들어내거나 인접일 값으로 대체하지 않는다(FR-039).

### 200 — 진행 중인 요청에 합류

같은 통화의 새로고침이 이미 진행 중이면 새 요청을 만들지 않고 그 결과를 사용한다(FR-036b).
응답은 `updated` 또는 `no_quote_today`와 같되 `joinedExisting: true`다.

### 502 / 503 — 외부 실패

001의 오류 형식을 따른다. 이 경우에도 저장된 과거 데이터와 이미 표시 중인 값은 유효하다(FR-040).

**동시성**: 이 엔드포인트는 대량 수집 작업과 **독립적으로** 동작한다. 수집이 진행 중이라는
이유로 거부하지 않는다(FR-036a). 잠금은 `scope='today_refresh'`를 쓴다(research R2-8).

**호출 비용**: 1회 요청이 외부 호출 1회를 소비한다(SC-008).

---

## 신설 `POST /api/fx/spreads/restore`

스프레드를 기본값으로 되돌린다 (FR-031, FR-032).

**Body**

```json
{ "currency": "USD" }
```

`currency`를 생략하면 전 통화를 대상으로 한다. 복원 범위는 호출자가 명시해야 하며, 화면은
실행 전에 그 범위를 사용자에게 알리고 확인을 받아야 한다(FR-032).

### 200

```json
{
  "restored": ["USD"],
  "failed": [],
  "spreads": [
    { "currency": "USD", "cashBuy": "0.001800", "cashSell": "0.001800",
      "remitSend": "0.000500", "remitReceive": "0.000500" }
  ]
}
```

응답은 복원 후의 값을 그대로 담아 화면이 별도 재조회 없이 갱신할 수 있게 한다.

### 200 — 일부만 복원됨 (FR-031a)

전 통화 복원 중 일부가 실패해도 **성공한 복원을 되돌리지 않는다.** 실패한 통화를 함께 알린다.

```json
{
  "restored": ["USD", "EUR"],
  "failed": [{ "currency": "JPY", "reason": "저장에 실패했습니다." }],
  "spreads": [ /* 복원 시도 후 전 통화의 실제 값 */ ]
}
```

`failed`가 비어 있지 않아도 상태 코드는 `200`이다. 부분 성공을 오류로 처리하면 화면이 성공한
복원까지 실패로 표시하게 된다. 호출자는 `failed`의 길이로 판정한다. `spreads`에는 성공·실패를
합쳐 **복원 시도 후의 실제 값**이 담기므로 화면은 이 값으로 그대로 갱신하면 된다.

상태 코드를 `207`로 나누지 않는 이유는 001이 쓰는 코드 집합(200/202/400/422/502/503)에 새
개념을 더하지 않기 위해서다.

---

## 변경 `GET /api/fx/spreads`

기본값과의 차이를 화면이 표시할 수 있도록(FR-033) 응답에 기본값을 함께 담는다.

```json
{
  "spreads": [
    {
      "currency": "USD",
      "cashBuy": "0.002500", "cashSell": "0.001800",
      "remitSend": "0.000500", "remitReceive": "0.000500",
      "isDefault": false
    }
  ],
  "defaults": [
    { "currency": "USD", "cashBuy": "0.001800", "cashSell": "0.001800",
      "remitSend": "0.000500", "remitReceive": "0.000500" }
  ]
}
```

통화 순서는 항상 `USD` → `JPY` → `EUR`다(FR-027).

---

## 변경 `GET /api/fx/series`

차트가 쓴다. 잠정 포인트를 구분할 수 있도록 필드를 더한다(FR-017a).

응답의 각 포인트에 `isProvisional`을 추가한다.

```json
{
  "points": [
    { "date": "2026-08-29", "baseRate": "1356.100000" },
    { "date": "2026-08-30", "baseRate": "1354.200000", "isProvisional": true }
  ]
}
```

- `isProvisional`은 `true`일 때만 포함한다. 대부분의 점에 붙지 않으므로 응답 크기에 거의
  영향이 없다.
- 다운샘플링을 적용해도 구간의 **마지막 점은 항상 포함**된다(FR-017b). 현재 LTTB 구현이 첫 점과
  끝 점을 보존하므로 별도 처리가 필요 없다(research R2-4).
- 파생 환율은 포함하지 않는다. 차트는 매매기준율만 그린다.

---

## 엔드포인트 요약

| 메서드 | 경로 | 상태 | 쓰는 곳 |
|--------|------|------|---------|
| GET | `/api/fx/latest` | 신설 | 요약 |
| GET | `/api/fx/daily` | 신설 | 상세 표, 내려받기 |
| POST | `/api/fx/today/refresh` | 신설 | 오늘 새로고침 |
| POST | `/api/fx/spreads/restore` | 신설 | 설정 — 기본값 복원 |
| GET | `/api/fx/spreads` | 변경 | 설정 — 기본값 비교 추가 |
| GET | `/api/fx/series` | 변경 | 차트 — 잠정 구분 추가 |
| GET | `/api/fx/rates/{currency}` | 유지 | **이번 화면에서 미사용** (001의 단일 날짜 조회로 존속) |
| GET | `/api/fx/coverage` | 유지 | 기간 프리셋 범위 + **선택 날짜 범위 판정** (FR-010) |
| POST | `/api/fx/collect` · `GET /api/fx/jobs` · `GET /api/fx/progress` | 유지 | 수집 현황 |

**`/api/fx/rates/{currency}`를 쓰지 않는 이유**: 선택 날짜 변경은 서버를 부르지 않는다
(contracts/ui-interaction 갱신 범위 표). 선택 날짜의 값은 이미 받아 둔 `daily` 응답 안에 있다.
이 엔드포인트를 호출하도록 구현하면 **오늘 날짜 선택 시 001의 `rate_query`가
`target >= today`를 범위 밖으로 판정해 거부한다** — 잠정값을 도입한 이 기능과 정면으로 충돌한다.
001의 이 규칙은 이번 범위에서 바꾸지 않는다.
