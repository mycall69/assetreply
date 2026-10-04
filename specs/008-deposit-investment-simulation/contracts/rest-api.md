# REST API: 예금 투자 시뮬레이션

**Feature**: `008-deposit-investment-simulation` | 근거: [research.md](../research.md), [data-model.md](../data-model.md)

모든 경로는 `/api/deposit/*`다. 프론트엔드 프록시(`next.config.ts`)는 006부터 `/api/*` 전체를 넘긴다 — 바꿀 것이 없다.

**금액·금리·세율·수익률은 모두 문자열**이다(JSON number는 IEEE 754 — 헌법 원칙 VI, 001부터의 규약). 오류 본문은 기존 규약
`{"status": "...", "message": "..."}`을 따른다. 날짜는 **한국 시간 달력**의 `YYYY-MM-DD`다(FR-018).

**투자처 키**: `commercial_bank`(시중은행) · `savings_bank`(저축은행) · `credit_union`(신협) · `mutual_finance`(상호금융) ·
`saemaul`(새마을금고). 출처의 통계표·항목 코드는 응답에 나오지 않는다(헌법 원칙 II, research R8-1).

---

## `GET /api/deposit/institutions` — 투자처 목록 (FR-003, FR-006)

라디오 버튼의 이름·설명과, 받아 둔 범위가 있으면 그 범위를 준다.

```json
{
  "institutions": [
    { "key": "commercial_bank", "name": "시중은행", "description": "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함",
      "firstMonth": "2012-01", "latestMonth": "2026-08", "checkedOn": "2026-10-04" },
    { "key": "savings_bank", "name": "저축은행", "description": "상호저축은행 정기예금(1년) 평균",
      "firstMonth": null, "latestMonth": null, "checkedOn": null }
  ],
  "source": "한국은행 경제통계시스템(ECOS)",
  "basis": "신규취급액 기준 가중평균"
}
```

- 순서는 화면 순서(시중은행 → 저축은행 → 신협 → 상호금융 → 새마을금고). 기본 선택은 첫째다(FR-003)
- `firstMonth`·`latestMonth`·`checkedOn` — 받은 적이 없으면 `null`. 받기 전에는 시작 가능 날짜를 모른다(research R8-12)

---

## `GET /api/deposit/simulation` — 시뮬레이션 표·보드 (FR-002~FR-007, FR-011, FR-021~FR-035)

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `institution` | 예 | 투자처 키 |
| `start` | 예 | `YYYY-MM-DD` |
| `principal` | 예 | 원 단위 정수 문자열(> 0, 쉼표 없음 — 006 FR-025) |
| `principalCurrency` | 아니오 | 주어지면 `KRW`여야 한다(FR-004). 이력·직접 요청 방어 |
| `end` | 아니오 | 기본 **오늘(한국 시간)**(FR-026) |

행은 많아야 한 해에 15줄 남짓이다(30년이어도 수백 줄) — **한 번에 모두** 보낸다. 주식·가상자산의 `before`·`limit`이 없다.

### 200 응답

숫자는 research R8-7 참조값 1에서 가져왔다.

```json
{
  "institution": { "key": "commercial_bank", "name": "시중은행" },
  "condition": { "start": "2020-01-15", "principal": "10000000", "interestTaxRate": "0.154000" },
  "summary": {
    "principal": "10000000", "profit": "1557207", "returnRate": "0.155721",
    "asOf": "2026-10-04", "isFinal": true,
    "currentTerm": { "joinedOn": "2026-01-15", "maturesOn": "2027-01-15", "rate": "2.84", "rateMonth": "2026-01",
                     "principal": "11361267", "provisional": false },
    "provisionalFrom": null,
    "stopped": null,
    "recheckFailed": null
  },
  "terms": [
    { "no": 1, "joinedOn": "2020-01-15", "maturesOn": "2021-01-15", "rate": "1.62", "rateMonth": "2020-01",
      "provisional": false, "principal": "10000000", "interest": "162000", "tax": "24948", "afterTax": "137052" }
  ],
  "rows": [
    { "date": "2026-10-01", "kind": "month", "rate": "2.84", "rateMonth": "2026-01", "provisional": false,
      "principal": "11361267", "interest": "…", "tax": "…", "afterTax": "…", "balance": "…", "profit": "…", "returnRate": "…" },
    { "date": "2026-01-15", "kind": "reinvest", "rate": "2.84", "rateMonth": "2026-01", "provisional": false,
      "principal": "11361267", "interest": "0", "tax": "0", "afterTax": "0",
      "balance": "11361267", "profit": "1361267", "returnRate": "0.136127" },
    { "date": "2026-01-15", "kind": "maturity", "rate": "3.06", "rateMonth": "2025-01", "provisional": false,
      "principal": "11074573", "interest": "338881", "tax": "52187", "afterTax": "286694",
      "balance": "11361267", "profit": "1361267", "returnRate": "0.136127" },
    { "date": "2020-01-15", "kind": "join", "rate": "1.62", "rateMonth": "2020-01", "provisional": false,
      "principal": "10000000", "interest": "0", "tax": "0", "afterTax": "0",
      "balance": "10000000", "profit": "0", "returnRate": "0.000000" }
  ]
}
```

- `rows`는 **최신순**이다. `kind`: `join`(가입) | `month`(매달 1일) | `maturity`(만기) | `reinvest`(재예치)(FR-033). 같은 날이면
  `reinvest`가 `maturity`보다 앞(최신순)이다. 가입일·만기일이 1일이면 그날 `month` 행이 없다. 계산 끝(오늘)의 값은 행이 아니라
  `summary`다(주식·가상자산과 같다)
- `interest`·`tax`·`afterTax` — `month` 행은 그날까지의 **경과분**, `maturity` 행은 **만기 이자**, `join`·`reinvest` 행은 0(FR-032)
- `balance` = `principal` + `afterTax`(경과분·만기분). `reinvest` 행의 `principal` = 같은 날 `maturity` 행의 `principal` + `afterTax`(SC-004)
- `rate`는 출처 문자열 그대로(연 %, `"3.2"`처럼 끝의 0이 없을 수 있다). `rateMonth`는 그 금리의 달 — 잠정이면 대신 쓴 달(FR-024)
- `summary.provisionalFrom` — 잠정 회차가 시작된 날짜(가입일 또는 재예치일), 없으면 `null`. 잠정이면 그 날짜 이후의 `terms`·`rows`가 모두
  `provisional: true`(FR-007, FR-024, research R8-8)
- `summary.stopped` — 결측으로 계산이 멈췄을 때만 `{"date": "2024-03-15", "reason": "rate_missing", "month": "2024-03"}`. 이때
  `isFinal: false`, `asOf`는 그 만기일이다(FR-024, FR-035). 미발표는 멈추지 않는다(잠정)
- `summary.currentTerm` — 계산 끝에 진행 중인 회차(멈췄으면 `null`)
- `summary.recheckFailed` — 오늘 미발표 달을 다시 확인하려다 실패했을 때만 `{"kind": "network", "reason": "…"}`. 결과는 받아 둔 금리로
  계산한 것이고(미발표 달은 잠정), 화면은 실패 사실과 사유를 보드 아래에 보인다(FR-016)
- 금액은 모두 **원 단위 정수** 문자열(FR-023). 수익률은 소수 6자리

### 202 — 수집 중 (FR-010, FR-011)

필요한 달 중 받지 않은 달이 있고 **오늘(한국 시간) 아직 확인하지 않았으면** 202다. 결과를 싣지 않는다.

```json
{
  "status": "collecting",
  "institution": "commercial_bank",
  "jobId": 3,
  "missingFrom": "2026-09", "missingThrough": "2026-10",
  "progressUrl": "/api/deposit/progress?jobId=3"
}
```

- 오늘 이미 확인했는데 여전히 없는 달은 **미발표**다 — 202가 아니라 200(잠정)으로 간다(research R8-3)
- `missingFrom`·`missingThrough`는 **늘** 있다 — 그 실행에 필요한 구간(시작 달 ~ 이번 달) 중 받지 않은 첫 달과 마지막 달. 받은 적이 없는
  투자처는 시작 달 ~ 이번 달이다(data-model 4절, analyze I1)

### 오류

| 상황 | 상태 | `status` | 본문 추가 |
|------|------|----------|-----------|
| 원금이 정수가 아니거나 0 이하, 날짜 형식 | 400 | `invalid_query` | |
| 투자처 키가 다섯 밖 | 400 | `unknown_institution` | `allowed` (FR-003) |
| `principalCurrency`가 `KRW`가 아니다 | 400 | `currency_not_allowed` | `allowed: ["KRW"]` (FR-004) |
| 시작일이 오늘(한국 시간)보다 늦다 | 400 | `start_after_end` | `lastDay` (FR-005) |
| 시작일이 그 투자처의 첫 달보다 이르다 | 409 | `before_first_month` | `startableFrom`(첫 달 1일) (FR-006) |
| 시작 달이 결측 | 409 | `rate_missing` | `month` (FR-007, FR-019) |
| 수집을 마쳤는데 그 투자처의 금리가 하나도 없다 | 404 | `no_rate_data` | |

출처 오류(인증·한도·형식·연결)는 **수집 작업의 실패**로 드러난다(진행 스트림의 `failed`). 다음 실행의 판정(FR-016):

- **받아 둔 금리로 답할 수 있으면**(커버리지가 있고 빠진 달이 모두 마지막 발표 달 뒤) — 오늘 그 투자처의 확인 작업이 실패했으면 202를
  다시 내지 않고 200으로 계산한다. 빠진 달은 잠정, `summary.recheckFailed`에 사유. `checked_on`은 성공했을 때만 갱신하므로 **다음 날** 다시
  확인한다 — 같은 날 실행마다 202가 되풀이되지 않는다
- **답할 수 없으면**(받은 적이 없거나 커버리지 안에 받지 않은 달) — 007과 같이 다시 수집하려 202를 낸다. 사용자가 다시 실행하면 다시 시도한다

---

## `GET /api/deposit/simulation/series` — 차트 시계열 (FR-036)

질의 매개변수·202·오류는 표와 같다(`maxPoints` 추가, 기본 2000).

```json
{
  "from": "2020-01-15", "to": "2026-10-04",
  "principalCurrency": "KRW", "basisCurrency": "KRW",
  "downsampled": false, "algorithm": "lttb", "sourcePointCount": 94,
  "points": [ { "date": "2020-01-15", "balance": "10000000", "returnRate": "0.000000" } ],
  "gaps": [],
  "provisionalFrom": null
}
```

- 점은 **표의 행과 같은 날짜들**(가입·매달 1일·만기·재예치)에 **계산 끝**(보드의 `asOf`)을 더한 것이고 값도 같다. 같은 날의 만기·재예치는
  점 하나(잔고가 같다). 끝점은 보드와 같다(FR-036, SC-009)
- 주식·가상자산의 시계열 형식(`SimulationSeriesResponse`)에 `provisionalFrom` 하나를 더했다 — `PerformanceChart`·`ComparisonChart`를 그대로
  쓰기 위해서다. 주식·가상자산 응답에는 이 키가 없고 화면은 `null`로 읽는다
- `gaps`는 늘 비어 있다 — 결측은 계산을 멈추게 하므로 점 사이에 빈 구간이 생기지 않는다

---

## `GET /api/deposit/progress?jobId=` — 수집 진행 (SSE) (FR-011)

006·007의 진행 스트림과 같은 사건과 머리글(`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`)이다.

- `snapshot`: `{"jobId", "status", "institution", "monthsDone", "monthsTotal", "missingFrom", "missingThrough"}` — `monthsTotal`은 필요한 구간의
  달 수(처음부터 안다), `monthsDone`은 그중 받은 구간 안의 달 수. 미발표 달은 받을 수 없으므로 완료 때 `monthsDone < monthsTotal`일 수 있다
- `completed`: `{"jobId", "latestMonth"}` — 마지막으로 발표된 달. 화면은 진행 줄을 지우고 결과를 다시 요청한다
- `failed`: `{"jobId", "reason", "kind"}` — `kind`: `auth` | `rate_limited` | `format` | `network`(FR-016). `reason`에는 인증키가 없다
  (`mask_secrets`, FR-014)

---

## `GET`·`PUT /api/deposit/settings` — 예금 이자 소득세율 (FR-030, FR-031)

```json
{ "interestTaxRate": "0.154000", "isDefault": true }
```

- `PUT` 본문 `{"interestTaxRate": "0.095"}` — 0 ≤ 값 < 1, 문자열. 아니면 `422 invalid_setting`
- 주식(`/api/stocks/settings`)·가상자산(`/api/crypto/settings`) 설정과 따로다

---

## 출처(ECOS) — 이 기능이 부르는 외부 API (research R8-1, R8-3, R8-5)

001과 같은 출처·같은 인증키다. **인증키가 URL 경로에 들어간다** — 로그·실패 사유·원본에 URL을 남기지 않고, 오류 문구는
`mask_secrets`를 거친다(FR-014).

| 용도 | 요청 | 응답에서 쓰는 것 |
|------|------|------------------|
| 항목 확인 | `GET /api/StatisticItemList/{key}/json/kr/1/10000/{통계표}/` | `ITEM_CODE`·`ITEM_NAME`(이름 패턴 확인), `CYCLE = M` 행의 `START_TIME` |
| 금리 | `GET /api/StatisticSearch/{key}/json/kr/1/10000/{통계표}/M/{YYYYMM}/{YYYYMM}/{항목}` | `StatisticSearch.row[].TIME`(YYYYMM)·`DATA_VALUE`(연 %), `list_total_count` |

- 오류도 HTTP 200으로 온다 — `RESULT.CODE`를 본다: `INFO-200` = 구간에 값 없음(미발표, 오류 아님), `INFO-100` = 인증 실패(`auth`, 재시도
  안 함), `INFO-300` = 한도 초과(`rate_limited`, 관문 전체 백오프 — research R8-6), 그 밖 `ERROR-*` = `format`. JSON이 아니면 `network`
- `list_total_count` > 받은 행 수면 잘린 것이다 — 형식 오류로 실패시키고 받은 구간으로 기록하지 않는다(001 parser와 같다)
- `DATA_VALUE`는 쉼표를 지우고 `Decimal`로 읽는다. 숫자가 아니면 그 응답 전체가 형식 오류다(FR-017)
