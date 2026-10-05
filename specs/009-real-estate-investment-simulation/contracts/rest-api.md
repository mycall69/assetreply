# REST API: 부동산 투자 시뮬레이션

**Feature**: `009-real-estate-investment-simulation` | 근거: [research.md](../research.md), [data-model.md](../data-model.md)

모든 경로는 `/api/realestate/*`다. 프론트엔드 프록시는 `/api/*` 전체를 넘긴다 — 바꿀 것이 없다.

**금액·면적·비율은 모두 문자열**이다(헌법 원칙 VI, 001부터의 규약). 오류 본문은 `{"status": "...", "message": "..."}`. 날짜는 한국 시간 달력
`YYYY-MM-DD`, 달은 `YYYY-MM`. 출처의 응답 형식(XML 필드명·게이트웨이 사유)은 응답에 나오지 않는다(헌법 원칙 II).

**평형 구분 키**: `10`(10평대) · `20`(20평대) · `30k`(30평대 국평) · `30l`(30평대 대형) · `40`(40평대) · `50`(50평대) · `60`(60평대 이상).

---

## `GET /api/realestate/regions?parent=` — 행정구역 (FR-002, FR-015)

`parent`가 없으면 시·도, 시·도 코드면 시·군·구, 시·군·구 코드면 법정동을 준다.

```json
{
  "items": [
    { "code": "1171010700", "name": "가락동", "level": "umd" },
    { "code": "1171010800", "name": "문정동", "level": "umd" }
  ],
  "refreshedAt": "2026-10-05T01:12:00Z"
}
```

- 목록을 한 번도 받지 않았으면 **202** `{"status": "collecting", "kind": "region", "jobId": 7, "progressUrl": "/api/realestate/progress?jobId=7"}` —
  화면은 진행을 보이고 끝나면 다시 요청한다. 그 작업이 실패하면 진행 스트림의 `failed`(종류·사유)를 화면이 경고로 보인다(FR-015 — 빈 풀다운만
  두지 않는다). 다음 요청은 다시 202로 새 작업을 시작한다. 30일(`APT_LIST_REFRESH_DAYS`)이 지났으면 받아 둔 목록으로 200을 주고 백그라운드로
  다시 받는다 — 그 갱신이 실패해도 받아 둔 목록을 그대로 준다.
- **현존 코드만** 준다(`retired_at` 없음 — 개편으로 사라진 코드는 출처가 0건을 주므로 보이지 않는다, research R9-3).
- 이름순(가나다). 시·군·구는 일반시 아래 구를 "수원시 장안구"처럼 붙인 이름이다.
- 오류: 모르는 `parent` → 400 `unknown_region`.

## `GET /api/realestate/complexes?umd=` — 단지 목록 (FR-003, 사용자 결정 Q1)

```json
{
  "umd": { "code": "1171010700", "name": "가락동", "lawdCd": "11710" },
  "items": [
    { "complexId": 12, "name": "헬리오시티", "jibun": "913", "moveInYear": 2018, "households": 9510, "sources": ["kapt", "trade"] },
    { "complexId": 31, "name": "현진타워", "jibun": "140-2", "moveInYear": 2004, "households": null, "sources": ["trade"] }
  ],
  "details": { "pending": false, "progressUrl": null },
  "trades": { "state": "collecting", "jobId": 9, "monthsDone": 120, "monthsTotal": 250,
              "progressUrl": "/api/realestate/progress?jobId=9", "failure": null }
}
```

- 처음 요청하면(또는 그 동의 목록을 받은 지 30일이 지났으면) 단지 목록 자료(1회 호출)로 곧바로 이름을 준다. 기본 정보(세대수·사용승인
  연도)는 백그라운드로 채운다(새 단지만) — `details.pending`이면 화면이 진행을 구독하고 끝나면 다시 요청한다.
- 그 시·군·구의 실거래를 받은 적이 없으면 수집을 시작하고 `trades.state = "collecting"` — 받으면 단지 목록 자료에 없던 단지(`sources:
  ["trade"]`)가 더해진다. 처음 고르는 시·군·구는 전체 이력(약 280회)을 받는다(하루 한도로 30곳 남짓 — research R9-5). 이미 진행 중이면 그 작업의
  `jobId`를 준다(새 작업 없음, FR-012).
- `trades.state`: `none`(아직 시작하지 않음) · `collecting` · `collected` · `failed`. **`collected`는 받아 둔 시·군·구다** — 첫 달부터 잠정 기간 앞
  달까지 모든 달을 받았다(data-model 5절). 화면은 이 값으로 확인 실패 뒤 다시 요청할지 정한다. `failed`는 마지막 작업이 실패했고 그 뒤 다 받은 적이
  없을 때이고 `failure: {"kind", "reason"}`를 함께 준다(FR-014 — 다시 열어도 사유가 보인다). 그 밖에는 `failure: null`.
- `jibun`은 화면이 같은 동의 같은 이름 단지를 가를 때 쓴다(FR-003). 다른 행에 합쳐진 단지(`merged_into`)는 목록에 나오지 않는다.
- 정렬: 가구수 내림차순, 같으면 이름순(가구수를 모르는 단지는 뒤). `households`는 모르면 `null` — 지어내지 않는다.
- 오류: 모르는 `umd`·사라진 `umd` → 400 `unknown_region`. 단지 목록 자료를 받지 못함 → 200 + `items`(실거래 단지만) + `listError: {"kind",
  "reason"}` — 빈 목록 대신 사유를 보인다(FR-015).
- **단지 id를 받는 모든 경로**(`areas`, `simulation`, `simulation/series`)는 합쳐진 단지의 옛 id를 받으면 `merged_into`를 따라가 같은 단지로
  답한다(data-model 2절 — 이력이 옛 id를 가지고 있을 수 있다).

## `GET /api/realestate/complexes/{complexId}/areas` — 평형 구분 (FR-004, FR-005)

```json
{
  "complexId": 12,
  "taxRulesFrom": "2006-01-01",
  "buckets": [
    { "key": "30k", "label": "30평대(국평)", "minArea": "70", "maxArea": "85", "maxInclusive": true,
      "trades": 789, "firstMonth": "2019-01", "lastMonth": "2026-09", "startableFrom": "2019-01-01" },
    { "key": "50", "label": "50평대", "minArea": "135", "maxArea": "165", "maxInclusive": false,
      "trades": 4, "firstMonth": "2020-09", "lastMonth": "2025-03", "startableFrom": "2020-09-01" },
    { "key": "60", "label": "60평대 이상", "minArea": "165", "maxArea": null, "maxInclusive": false,
      "trades": 0, "firstMonth": null, "lastMonth": null, "startableFrom": null }
  ]
}
```

- 일곱 구분을 늘 모두 준다(거래 0인 구분 포함 — 화면이 비활성으로 보인다). 거래 수·첫 달은 해제·사라짐을 뺀 값이다.
- `startableFrom` = `firstMonth`의 1일과 `taxRulesFrom`(세법 표의 첫 날) 중 늦은 날(FR-005). 2005-12에 첫 거래가 있는 구분은 `2006-01-01`이다.
- 실거래를 아직 받지 않았으면 202(수집 중, 위와 같은 모양).

## `GET /api/realestate/simulation` — 시뮬레이션 (FR-005~FR-007, FR-016~FR-030)

### 질의 매개변수

| 이름 | 필수 | 설명 |
|------|------|------|
| `complexId` | 예 | 단지 |
| `area` | 예 | 평형 구분 키 |
| `buyDate` | 예 | `YYYY-MM-DD`, 오늘(한국 시간) 이하 |
| `buyPrice` | 아니오 | 원 단위 정수 문자열(> 0, 쉼표 없음). 없으면 매입 달의 시세 |
| `principalCurrency` | 아니오 | 주어지면 `KRW`여야 한다(FR-007) |

### 200 응답

숫자는 모양을 보이기 위한 예다(헬리오시티 30평대(국평), 2021-03-15 매입).

```json
{
  "complex": { "complexId": 12, "name": "헬리오시티", "umdName": "가락동" },
  "area": { "key": "30k", "label": "30평대(국평)" },
  "condition": {
    "buyDate": "2021-03-15", "buyPrice": "2023166667", "buyPriceSource": "market",
    "buyPriceWindow": { "months": 1, "trades": 6, "estimated": false },
    "holdingTaxBaseRatio": "0.600000",
    "assumptions": ["부부 5:5 공동 소유", "1세대 1주택", "세법: 시행일별 표"]
  },
  "acquisition": {
    "acquisitionTax": "60695000", "educationTax": "6069500", "ruralTax": "0",
    "brokerageFee": "18208500", "total": "84973000",
    "rules": { "acquisition": "2020-01-01", "brokerage": "2015-04-01" }
  },
  "summary": {
    "buyPrice": "2023166667", "invested": "2108139667",
    "propertyTaxTotal": "28111520", "comprehensiveTaxTotal": "4316880", "holdingTaxTotal": "32428400",
    "value": "2450000000", "valueMonth": "2026-10", "valueWindow": { "months": 3, "trades": 41 },
    "estimated": true, "provisional": true,
    "profit": "309431933", "returnRate": "0.146780", "asOf": "2026-10-05",
    "taxGaps": []
  },
  "rows": [
    { "month": "2026-10", "trades": 0, "monthAverage": null,
      "price": "2450000000", "window": 3, "windowTrades": 41, "estimated": true, "provisional": true,
      "acquisition": null, "propertyTax": null, "comprehensiveTax": null,
      "cumulativeCost": "117401400", "value": "2450000000", "profit": "309431933", "returnRate": "0.146780" },
    { "month": "2026-09", "trades": 14, "monthAverage": "2441428571",
      "price": "2441428571", "window": 1, "windowTrades": 14, "estimated": false, "provisional": true,
      "acquisition": null,
      "propertyTax": { "amount": "3104390", "rule": "2026-06-01", "installment": "2/2",
                       "basis": { "month": "2026-06", "price": "2400000000", "window": 1, "windowTrades": 9,
                                  "estimated": false, "provisional": true } },
      "comprehensiveTax": null, "cumulativeCost": "117401400",
      "value": "2441428571", "profit": "300860504", "returnRate": "0.142714" }
  ]
}
```

- `rows`는 **최신순**, 매입 달부터 이번 달까지 한 달에 한 줄. 매입 달 행의 `acquisition`에 취득 비용 항목이 있다.
- `monthAverage`는 그 달 실거래 평균(없으면 `null` — 위 2026-10은 아직 거래가 없어 8~10월 3개월 창의 추정이다), `price`는 적용 시세(창 `window`개월,
  창 안 거래 `windowTrades`건). 그 달에 거래가 있으면 늘 1개월 창이다(FR-016). `window > 1`이면
  `estimated: true`. 창에 잠정 달(최근 12개월)이 있으면 `provisional: true`.
- 시세 없음 달은 `price`·`value`·`profit`·`returnRate`가 `null`이다(0이 아니다, FR-026).
- `propertyTax`는 7월·9월 행에만(`installment` `"1/2"`·`"2/2"`, 일괄이면 `"1/1"`), `comprehensiveTax`는 12월 행에만. 다른 달은 `null`(0과 구별, FR-028).
  `rule`은 적용한 세법 표의 시행일. `basis`는 보유세 기준 시세(그해 6월의 적용 시세 — 달·시세·창·건수·추정·잠정)다 — 추정·잠정이면 화면이 세금
  칸에 그 사실을 보인다(FR-021). 종부세도 같은 `basis`를 가진다.
- `summary.taxGaps`: 6월 시세가 없어 보유세를 계산하지 못한 해들(예: `[2019]`) — 화면이 경고한다(research R9-7).
- 계산 끝(이번 달)의 시세가 없으면 `summary.value`가 `null`이고 `summary.lastPricedMonth`가 마지막으로 시세가 있던 달이다.
- 금액은 원 단위 정수 문자열, 수익률은 소수 6자리.

### 202 — 수집 중 (FR-011)

```json
{ "status": "collecting", "kind": "trade", "lawdCd": "11710", "jobId": 9,
  "monthsDone": 120, "monthsTotal": 250, "progressUrl": "/api/realestate/progress?jobId=9" }
```

202가 되는 경우(FR-010, FR-011):

- 그 시·군·구의 받지 않은 달이 있다(첫 달 탐색이 끝나지 않은 경우 포함)
- 최근 3개월의 잠정 달을 **오늘** 확인하지 않았다
- 4~12개월 전의 잠정 달을 **이번 달** 확인하지 않았다(그 달의 첫 실행에서 9~10회)

같은 시·군·구의 수집이 이미 진행 중이면 그 작업의 `jobId`를 준다(새 작업 없음, FR-012). 판정은 **단지의 현재 `lawd_cd`**로 한다 — 개편으로
그 코드가 사라졌고 아직 새 코드로 갱신되지 않았으면 409 `region_retired`다(data-model 2절).

**받아 둔 시·군·구**(첫 달부터 잠정 기간 앞 달까지 모든 달을 받았다 — data-model 5절)에서 오늘의 실패가 **잠정 달 다시 받기뿐**이면 200 +
`summary.recheckFailed: {"kind", "reason"}`다(008과 같다 — 같은 날 202를 되풀이하지 않는다). **받지 않은 확정 달이 하나라도 있으면 실패가
있었어도 202다** — 새 작업이 이어 받고, 한도에 닿았으면 그 작업이 곧바로 `rate_limited`로 실패해 화면이 사유를 보인다. 중간까지만 받은 시·군·구에
200을 주면 부분 결과가 된다(FR-011).

### 오류

| 상황 | 상태 | `status` | 본문 추가 |
|------|------|----------|-----------|
| 매개변수 형식(날짜·금액·평형 키) | 400 | `invalid_query` | |
| 모르는 단지 | 400 | `unknown_complex` | |
| 원화가 아닌 원금 | 400 | `currency_not_allowed` | `allowed: ["KRW"]` |
| 매입일이 오늘보다 늦다 | 400 | `start_after_end` | `lastDay` |
| 매입일이 시작 가능 날짜보다 이르다 | 409 | `before_first_trade` | `startableFrom`, `basis`: `first_trade`(첫 거래 달) · `tax_rules`(세법 표 시작) (FR-005) |
| 매입 달 시세 없음 + 매입가 없음 | 409 | `no_price_at_purchase` | `month` (FR-006) |
| 그 평형 구분의 거래가 없다 | 409 | `no_trades_in_area` | |
| 세법 표가 그 날짜를 덮지 않는다(보유 중의 과세기준일 — 매입일은 위 `before_first_trade`가 먼저 막는다) | 409 | `tax_rule_not_covered` | `tax`, `date` (FR-023) |
| 단지의 시·군·구 코드가 개편으로 사라졌고 새 코드로 아직 받지 않았다 | 409 | `region_retired` | `lawdCd` (FR-002) — `areas`·`simulation/series`도 같다 |

## `GET /api/realestate/simulation/series` — 차트 (FR-031)

질의 매개변수·202·오류는 표와 같다.

```json
{
  "from": "2021-03-15", "to": "2026-10-05", "principalCurrency": "KRW", "basisCurrency": "KRW",
  "downsampled": false, "algorithm": "lttb", "sourcePointCount": 68,
  "points": [ { "date": "2021-03-15", "balance": "2023166667", "returnRate": "-0.040307", "estimated": false, "provisional": false },
              { "date": "2021-04-01", "balance": "2031250000", "returnRate": "-0.036473", "estimated": false, "provisional": false } ],
  "gaps": [],
  "provisionalFrom": "2025-11-01"
}
```

- 점은 매달이고 값은 표의 그 달 평가액·수익률과 같다. **첫 점의 날짜는 매입일**이고(그 달 1일이 매입일보다 앞서지 않게) 그 뒤는 매달 1일이다.
  끝점은 보드(계산 끝)다. 시세 없음 달은 점이 없고 `gaps`(`no_price` — 끊는다). 위 예(30평대(국평))에는 시세 없음 달이 없다 — 있으면
  `{"from": "2023-12-01", "to": "2025-01-01", "reason": "no_price"}`처럼 준다(헬리오시티 50평대의 예).
- `estimated`·`provisional`은 점마다. `provisionalFrom`은 잠정 기간(최근 12개월)의 첫 달(008과 같은 키).

## `GET /api/realestate/progress?jobId=` — 수집 진행 (SSE) (FR-011)

008과 같은 사건·머리글(`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`).

- `snapshot`: `{"jobId", "kind", "target", "status", "done", "total"}` — `trade`는 받은 달/받을 달, `complex_details`는 받은 단지/단지 수,
  `region`은 받은 쪽/쪽 수
- `completed`: `{"jobId"}`
- `failed`: `{"jobId", "kind", "reason"}` — `kind`: `auth` | `rate_limited` | `format` | `network`. `reason`에 인증키가 없다

## `GET`·`PUT /api/realestate/settings` — 보유세 기준 비율 (FR-034)

```json
{ "holdingTaxBaseRatio": "0.600000", "isDefault": true }
```

`PUT` 본문 `{"holdingTaxBaseRatio": "0.65"}` — 0 < 값 ≤ 1, 문자열, 소수 6자리까지(백분율 4자리). 아니면 `422 invalid_setting` — 넘는 자릿수를
반올림해 저장하지 않는다(FR-034).

---

## 출처 — 이 기능이 부르는 외부 API (research R9-1, R9-3)

모두 공공데이터포털(`https://apis.data.go.kr`)이고 같은 인증키(`DATA_API_KEY`)다. **인증키가 URL 질의(`serviceKey`)에 들어간다** — 로그·실패
사유·원본에 URL을 남기지 않고, 오류 문구는 키를 지운 뒤 `mask_secrets`를 거친다(FR-013).

| 용도 | 요청 | 응답에서 쓰는 것 | 하루 한도(설정) |
|------|------|------------------|-----------------|
| 실거래 | `/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev?LAWD_CD=&DEAL_YMD=&pageNo=&numOfRows=1000` (XML) | `aptSeq`·`umdCd`·`bonbun`·`bubun`·`aptNm`·`aptDong`·`floor`·`excluUseAr`·`dealAmount`·계약일·`cdealType`·`cdealDay`·`dealingGbn`, `totalCount` | 9,000 |
| 법정동 | `/1741000/StanReginCd/getStanReginCdList?type=json&pageNo=&numOfRows=1000` | `region_cd`·`sido_cd`·`sgg_cd`·`umd_cd`·`ri_cd`·`locatadd_nm` | 9,000 |
| 단지 목록 | `/1613000/AptListService4/getLegaldongAptList4?bjdCode=` | `kaptCode`·`kaptName`·`bjdCode` | 4,500(기본 정보와 함께) |
| 기본 정보 | `/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5?kaptCode=` | `kaptdaCnt`·`kaptUsedate`·`kaptAddr`·`bjdCode` | (위와 함께) |

- 실거래 `resultCode`는 `000`이 정상이다. 거래가 없으면 `totalCount 0`(오류가 아니다 — 틀린 코드도 0이라 요청은 행정구역 표의 코드로만 한다).
- 포털 게이트웨이가 막으면 HTTP 4xx + `OpenAPI_ServiceResponse`(사유 코드) — 20·30·31·32 인증, 22 한도, 12 서비스 없음(형식 — 엔드포인트가
  바뀌었다), 그 밖은 연결.
- 받은 행 수가 `totalCount`와 다르면 잘린 것이다 — 형식 오류로 실패시키고 받은 구간으로 기록하지 않는다.
- 연결 실패·HTTP 5xx는 지수 백오프 + 지터로 다시 시도한다 — `DATA_API_RETRY_MAX_ATTEMPTS`(4)회, 지연 `DATA_API_RETRY_BASE_DELAY_MS`(1000) × 2ⁿ
  (헌법 원칙 II — 설정). 인증 실패와 한도(사유 22·자체 한도)는 다시 시도하지 않는다.
- **현존 시·군·구 코드만 요청한다** — 출처는 과거 거래도 개편 뒤의 새 코드로만 주고, 사라진 코드에는 0건을 정상으로 준다(research R9-3 실측).
