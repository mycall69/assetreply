# REST API 계약: 014 대시보드

접두사는 `/api/dashboard`다. 값·차이·등락률은 모두 **문자열 Decimal**이다(원칙 VI) — 화면은 형식만 입힌다. 시각은 ISO 8601 UTC(`Z`), 날짜는 그 시장의 현지 날짜(`YYYY-MM-DD`)다.
오류 본문은 기존 관례 `{"status": "...", "message": "..."}`(`api/main.py`의 `_json`)를 따른다.

## A0. 실패 종류 — 경로마다 같은 이름은 같은 뜻이다(반복 2026-10-10)

| 이름 | 뜻 | 쓰는 곳 |
|------|----|---------|
| `connection` | 연결 오류·시간 초과·5xx. 지표 출처는 HTTP 200이어도 오류 칸(`chart.error`)이 있으면 이것이다(주식 005와 같은 분류 — 다시 시도한다). 뉴스는 403·429 밖의 4xx도 이것이다 | A1 `failure.kind` · A2/A4 `kind` · A5 `failure.reason` |
| `rate_limited` | 429 — 출처가 요청을 제한했다. 지표 출처는 Yahoo 관문 전체가 물러선다 | A1 · A2/A4 · A5 |
| `blocked` | 403(지표는 401도) — 출처가 막았다. 기다려도 풀리지 않는다(사용자 에이전트 설정) | A1 · A2/A4 · A5 |
| `invalid_body` | 본문을 읽을 수 없다 — JSON이 아니거나(지표·한국 뉴스) 상태 JSON이 깨졌다(일본 뉴스) | A1 · A2/A4 · A5 |
| `not_found` | 404 또는 그 심볼의 값이 비었다 — 출처에 그 지표가 없다 | A1 · A2/A4 |
| `parse_empty` | 기사를 하나도 읽지 못했다 — 목록 표지가 없거나 0건(출처 화면이 바뀐 신호). 1~9건은 실패가 아니다 | A5 |
| `fx_collection` | 그 통화의 마지막 외환 수집(001)이 실패했다 — 문구는 외환 수집 기록의 것이다(FR-018) | A2/A4(환율만) |

반복 2026-10-10b: A2 장중(`1d`·`5d`)·A7·A8의 실패도 위 이름을 쓴다(A8의 목록 표지 없음은 `parse_empty`).

반복 2026-10-11d: 기준금리 수집(A14·A15의 `failure.kind`)은 `connection`(403·429 밖의 4xx 포함 — `pageSize` 상한 400도 이것)·`rate_limited`·`blocked`·`invalid_body`(JSON 배열이 아님·행의
금리를 읽을 수 없음)·`not_found`(목록에 그 은행이 없음·결정 이력 404)를 쓴다. A16은 A8과 같다.

## A1. `GET /api/dashboard/quotes` — 지표 15개의 현재 시세

같은 순간의 요청은 서버 캐시(R14-6)를 함께 쓴다. 출처가 실패해도 **200**이다 — 실패는 지표마다 `status: "failed"`로 싣는다(FR-009).

```json
{
  "fetchedAt": "2026-10-09T05:30:12Z",
  "refreshAfterSeconds": 60,
  "source": "Yahoo Finance",
  "indicators": [
    {
      "id": "kospi", "name": "KOSPI", "group": "korea", "order": 1,
      "unit": "포인트", "kind": "index",
      "market": { "key": "krx", "timezone": "Asia/Seoul" },
      "notes": [],
      "status": "ok",
      "quote": {
        "value": "6625.930000", "valueTime": "2026-10-08T11:05:00Z", "sessionDate": "2026-10-08",
        "state": "holiday", "provisional": false, "delayMinutes": null,
        "previous": { "close": "6803.900000", "date": "2026-10-07", "from": "history" },
        "change": "-177.970000", "changeRate": "-0.026157", "changeRateBlank": null, "direction": "down"
      },
      "stale": false,
      "failure": null
    },
    {
      "id": "jpy", "name": "엔(100엔)", "group": "fx", "order": 11, "unit": "원(100엔당)", "kind": "fx",
      "market": { "key": "fx", "timezone": "Europe/London" },
      "notes": ["market_fx"],
      "status": "ok",
      "quote": {
        "value": "844.900000", "valueTime": "2026-10-09T05:24:00Z", "sessionDate": "2026-10-09",
        "state": "open", "provisional": true, "delayMinutes": null,
        "previous": { "close": "846.100000", "date": null, "from": "source_fx" },
        "change": "-1.200000", "changeRate": "-0.001418", "changeRateBlank": null, "direction": "down"
      },
      "stale": false, "failure": null
    }
  ]
}
```

- `notes`: `future_roll`(선물 근월물 연속 — FR-015), `market_fx`(시장 환율 — 매매기준율과 다를 수 있음, 출처 기준 런던 0시 — FR-018)
- `state`: `pre_open`·`open`·`break`·`closed`·`holiday`(data-model §3)
- `previous.from`:
  - `history`: 저장된 이력 — `date`가 있다
  - `source`: 이력이 아직 닿지 않음 — `date: null`, 화면이 "전일 값: 출처(이력에 아직 없음)"을 보인다
  - `source_fx`: 시장 환율 — 늘 출처
- `changeRate: null` + `changeRateBlank: "non_positive_base"`: 전일 종가가 0 이하
- `stale: true`: 이번 요청에 출처가 실패해 **마지막 성공 값**을 보인다. `failure`가 함께 온다. 화면은 "새로 받지 못함"과 그 값의 기준 시각을 보인다
- `status: "failed"`이고 `quote: null`: 받은 값이 한 번도 없다. `failure`는 `{ "kind": "connection"|"rate_limited"|"blocked"|"invalid_body"|"not_found", "message": "..." }`다
- 차례는 `order`다(FR-003). 응답은 늘 15개다

## A2. `GET /api/dashboard/indicators/{id}/series?range=1d|5d|1m|1y|5y|10y|20y|all`

- **반복 2026-10-10b**: 질의는 보는 기간 `range`다(기본·틀리면 `1y` — 400을 내지 않는다). 옛 질의 `unit`은 무시한다(spec FR-010·D8)
  - 일봉 기간(`1m`·`1y`·`5y`·`10y`·`20y`·`all`)은 그 기간의 **일봉 전부**다 — 아래 200·202 꼴 그대로이고 점은 묶지 않는다(`shifted`·`ongoing`은 오지 않는다). **반복 2026-10-10c 대체**: 기간과 무관하게 저장된 일봉 전부 + `windows`(아래)
  - 장중 기간(`1d`·`5d`)은 장중 시세다(저장 안 함 — 202가 없다, 수집과 무관):
    `{ "indicator", "range", "intraday": true, "fetchedAt", "session": {"from", "to"}, "points": [{ "time": "2026-10-09T13:35:00Z", "value": "7801.250000", "provisional": true }], "notes" }`
    — 실패면 200 + `status: "failed"`, `points: []`, `failure{reason, message, retryAfterSeconds}`(A0)
  - 환율의 장중은 시장 환율이고 `notes`에 `market_fx`가 있다(일봉 기간은 지금처럼 ECOS)
- **반복 2026-10-10c — 기간은 처음 보이는 범위다**(spec FR-011·R14-22):
  - 일봉 기간의 `points`는 기간과 무관하게 **저장된 일봉 전부**다(지금의 `all`과 같은 점·`gaps`·`sourcePointCount`·`downsampled`). `range`는 처음 범위이고 본문에 그대로 싣는다
  - `windows` 추가 — 기간마다 처음 보이는 범위의 시작일: `{ "1m": "2026-09-09", "1y": "2025-10-09", "5y": "2021-10-09", "10y": "2016-10-09", "20y": "2006-10-09", "all": null }`
    (시장 현지 오늘에서 1개월·n년 전 — 없는 날은 그 달 말일). 화면은 이 본문 하나로 월~모두를 오간다
  - 장중 받는 범위: `1d` = 출처 `range=5d&interval=5m`(최근 5세션), `5d` = `range=1mo&interval=30m`(최근 1개월). `window: {"from", "to"}`(UTC ISO) 추가 — 처음 보이는 범위(마지막 세션 ·
    최근 5세션, 시장 현지 날짜로 가름 — 환율은 런던 0시 경계). `session`은 받은 점 전체의 처음·끝이다. 실패 본문은 `window: null`
- (반복 2026-10-10b 전) `unit`이 없거나 틀리면 `daily`였다 — 위로 대체
- 없는 `id`면 **404** `{"status": "unknown_indicator", "message": "..."}`다

### 200 — 백필 완성

```json
{
  "indicator": { "id": "sp500", "name": "S&P 500", "unit": "포인트", "kind": "index", "group": "us",
                 "market": { "key": "us_equity", "timezone": "America/New_York" }, "notes": [] },
  "unit": "monthly",
  "history": { "source": "yahoo", "firstDate": "1927-12-30", "lastDate": "2026-10-08", "tailPending": false,
               "lastSuccessAt": "2026-10-09T04:30:02Z", "lastFailure": null },
  "points": [
    { "date": "1927-12-30", "value": "17.660000" },
    { "date": "2026-09-30", "value": "7702.110000" },
    { "date": "2026-10-09", "value": "7765.360000", "ongoing": true, "provisional": true }
  ],
  "gaps": [ { "from": "2001-09-11", "to": "2001-09-11", "reason": "missing" } ],
  "downsampled": false,
  "sourcePointCount": 1186
}
```

- 점의 선택 칸 `shifted`·`ongoing`·`provisional`은 참일 때만 붙는다(외환 `/series`의 `isProvisional`과 같은 관례)
- `gaps`는 결측(R14-5)뿐이다. 휴장은 넣지 않는다 — 선이 이어진다
- `history.source`: `yahoo`이거나, 환율은 `ecos`(외환 메뉴의 매매기준율 — 머리에 "카드의 시장 환율과 다른 계열"을 밝힌다)
- `tailPending: true`: 커버리지 끝이 그 시장 현지 어제에 닿지 않았다. 머리에 "최근 구간 받는 중"을 보인다
- `lastSuccessAt`·`lastFailure`: 수집 상태(FR-019 — 원칙 V 커버리지 조회)
  - `lastFailure`는 마지막 성공보다 뒤에 실패가 있을 때 `{ "kind", "message", "at" }`이고, 없으면 `null`이다. 그래프는 그대로 보이고 머리에 실패 줄이 보인다
  - 환율은 외환 커버리지의 마지막 갱신 시각이고 `lastFailure`는 `null`이다(외환 수집 표가 따로 있다)
- 마지막 잠정 점은 지표가 환율이 아닐 때 현재 시세 캐시에서 붙인다(R14-12)
- 점 수가 `DASHBOARD_SERIES_MAX_POINTS`를 넘으면 LTTB로 줄이고 `downsampled: true`다

### 202 — 백필 중 · 실패

```json
{
  "status": "collecting",
  "indicator": { "id": "sp500", "name": "S&P 500" },
  "progress": { "firstDay": "1927-12-30", "coveredFrom": "2010-01-04", "coveredThrough": "2026-10-08",
                "remainingDays": 29957 },
  "failure": null,
  "progressUrl": "/api/dashboard/indicators/sp500/progress"
}
```

- `status: "failed"`: 마지막 수집이 실패했고 그 뒤 성공이 없다. `failure{kind, message, at}`를 싣는다. 화면은 까닭과 "다시 시도"(A3)를 보인다
- `firstDay: null`: 아직 첫 응답 전이다
- 환율(`usd`·`jpy`·`eur`)은 외환의 커버리지를 본다(대시보드가 ECOS를 부르지 않는다 — FR-018). 반복 2026-10-10에 바꿨다 — 전에는 외환 진행 스트림 주소를 실었다:
  - 모자라면 외환 수집 경로(`collection_gate.ensure_background_job`)에 요청하고 `status: "collecting"` + `jobId`(있으면)다. **`progressUrl`은 다른 지표와 같은 A4 경로**
    (`/api/dashboard/indicators/usd/progress`)이고 `progress`는 외환 커버리지다 — `firstDay`(통화의 첫 고시일)·`coveredFrom`·`coveredThrough`·`remainingDays`(빠진 날 수)
  - 그 통화의 마지막 외환 수집 작업이 `failed`·`partial`(오류 있음)이고 지금 받는 중(점유·큐)이 아니면 `status: "failed"` + `failure{kind: "fx_collection", message, at}`다.
    **이때 외환 수집을 요청하지 않는다** — 다시 요청은 A3(다시 시도)뿐이다

## A3. `POST /api/dashboard/indicators/{id}/collect` — 다시 시도

- **202** `{"status": "queued"}`: 워커를 곧바로 깨운다(R14-11). 이미 받는 중이어도 202다(두 번 받지 않는다)
- 환율이면 외환 수집 경로에 요청을 넘기고 그 수집 표를 돌려준다
- 없는 `id`면 404다

## A4. `GET /api/dashboard/indicators/{id}/progress` — SSE

`text/event-stream`, 머리는 `api/collection_stream.SSE_HEADERS`다. 2초마다 커버리지 행을 읽는다(007 `crypto_progress`와 같다).
환율은 외환 커버리지·외환 수집 작업을 읽어 같은 세 사건을 낸다 — 이력이 충분해지면 `completed`, A2의 실패 조건이면 `failed{kind: "fx_collection"}`(반복 2026-10-10).

| 사건 | data |
|------|------|
| `snapshot` | `{ "firstDay", "coveredFrom", "coveredThrough", "remainingDays" }` |
| `completed` | `{ "id" }` — 백필이 완성됐다. 화면이 A2를 다시 부른다 |
| `failed` | `{ "id", "kind", "message" }` — 마지막 시도가 실패했다 |

## A5. `GET /api/dashboard/news/{source}` — 뉴스 목록 (`source` = `kr`·`us`·`jp`)

출처가 실패해도 **200**이다 — 칸마다 따로 실패한다(FR-024). 틀린 `source`면 404다.

```json
{
  "source": "kr",
  "sourceName": "네이버 증권",
  "sourceUrl": "https://stock.naver.com/news",
  "list": "주요뉴스",
  "status": "ok",
  "fetchedAt": "2026-10-09T13:12:30Z",
  "items": [
    { "rank": 1, "title": "\"하루에 1조 벌었는데…\" 한국 개미들 다시 '미장' 가는 이유 [분석+]",
      "url": "https://n.news.naver.com/article/015/0005340952", "publisher": "한국경제",
      "publishedAt": "2026-10-09T13:12:14Z", "publishedDate": null, "publishedText": null, "paid": false }
  ],
  "failure": null
}
```

- `us`: `sourceName` "Yahoo Finance", `sourceUrl` https://finance.yahoo.com/topic/latest-news/, `list` "Latest News"(주요 목록이 없음). `publishedText` `"4m ago"`, `publishedAt: null`
- `jp`: `sourceName` "Yahoo!ファイナンス", `sourceUrl` https://finance.yahoo.co.jp/news, `list` "ヘッドライン". 오늘 기사는 `publishedAt`, 지난 날은 `publishedDate`. 유료면 `paid: true`
- 실패: `status: "failed"`, `items: []`, `failure: { "reason": "connection"|"blocked"|"rate_limited"|"parse_empty"|"invalid_body", "message", "retryAfterSeconds" }`
  - 실패 기억이 남은 동안의 재요청은 출처를 부르지 않고 같은 실패와 남은 시간을 돌려준다(R14-13)
  - `parse_empty`는 기사를 하나도 읽지 못했다는 뜻이다 — 화면은 "읽지 못함 — 출처 화면이 바뀌었을 수 있음"이다(0건을 "뉴스 없음"으로 보이지 않는다)
- `items`는 1~10개다. 10개보다 적으면 있는 만큼이다
- 강제로 다시 받는 질의는 없다 — 성공 캐시(기본 10분) 안의 재요청은 늘 캐시다(US3 시나리오 6). 화면의 "다시 시도"는 실패 칸에만 있고 같은 경로를 다시 부른다

## A7. `GET /api/dashboard/indicators/{id}/table?period=daily|weekly|monthly&before=&limit=` — 일자별 표 (반복 2026-10-10b)

주식 일자별 표(012)와 같은 쪽 넘기기다. 틀린 `period`는 **400** `invalid_query`, 없는 `id`는 404다. 과거 구간이 다 받아지지 않았으면 A2와 같은 202다.

```json
{
  "indicator": { "id": "sp500", "name": "S&P 500", "unit": "포인트" },
  "period": "weekly",
  "rows": [
    { "kind": "period", "date": "2026-10-09", "open": null, "high": null, "low": null, "close": "7801.250000",
      "change": "35.890000", "changeRate": "0.004622", "isOngoing": true, "provisional": true },
    { "kind": "period", "date": "2026-10-02", "shiftedFrom": "2026-10-02", "open": "7701.000000", "high": "…", "low": "…", "close": "…",
      "change": "…", "changeRate": "…", "provisional": false },
    { "kind": "missing", "date": "2001-09-11", "dateTo": "2001-09-14" }
  ],
  "hasMore": true,
  "oldestReturned": "2026-04-17",
  "seriesNote": null
}
```

- 행 꼴은 data-model §5a다 — **주식 일자별 표(012 `table_rows.row_body`)와 같은 꼴**: `kind`(`period`·`missing`), 옮겼으면 `shiftedFrom`(원래 기준일), 끝나지 않았으면 `isOngoing: true`. 값은 문자열 Decimal, 없으면 `null`(화면 "—")
- 결측 구간 행(`kind: "missing"`, `date`~`dateTo`)은 `period=daily`에만 온다
- 오늘(현지) 잠정 행은 `provisional: true`이고 시가·고가·저가가 `null`이다(출처의 현재 시세가 시가를 주지 않는다 — R14-19)
- 환율: 외환 고시 이력, `open`·`high`·`low`는 늘 `null`, `seriesNote: "fx_fixing"`(화면 "고시 — 하루 한 값")
- `limit` 기본 30·최대 200, `before`는 그 날짜 미만. 하루가 두 쪽에 갈리지 않는다

## A8. `GET /api/dashboard/indicators/{id}/commentary` — 변화 까닭 (반복 2026-10-10b)

출처가 실패해도 **200**이다. 없는 `id`는 404다. 저장하지 않는다(메모리 10분).

```json
{
  "indicator": "kospi",
  "source": "네이버 증권",
  "sourceUrl": "https://stock.naver.com/news",
  "status": "ok",
  "fetchedAt": "2026-10-10T06:40:00Z",
  "sessionDate": "2026-10-08",
  "items": [
    { "title": "코스피, 외국인 매도에 2% 넘게 하락…6,600선 내줘", "summary": "…(출처 요약 원문)…", "publisher": "한국경제",
      "publishedAt": "2026-10-08T06:45:00Z", "publishedDate": null, "publishedText": null,
      "url": "https://n.news.naver.com/article/015/0005340000" }
  ],
  "failure": null
}
```

- `status`: `ok`(1~3개) · `none`(마지막 세션 이후의 기사가 없다 — 화면 "변화를 다룬 기사를 찾지 못했습니다", `items: []`) · `failed`(`failure` — A0, 목록 표지 없음은 `parse_empty`)
- `items`의 글자는 출처의 것 그대로다. 링크는 허용 도메인·https만이다(spec FR-022·FR-027)
- 출처 목록·주소는 research R14-17(T095 실측)이다

## A9. `GET /api/fx/daily` 행의 `change` — 외환 일자별 표의 등락 (반복 2026-10-10d — spec FR-031)

001·004 계약의 행에 칸 하나를 더한다. 다른 칸·차례·쪽 넘기기(`before`·`limit`·`hasMore`·`oldestReturned`)·`period`·202 본문은 그대로다.

```json
{
  "date": "2026-10-08",
  "baseRate": "1425.30",
  "isProvisional": false,
  "derived": { "…": "001 그대로" },
  "periodFrom": "2026-10-08",
  "periodTo": "2026-10-08",
  "isOngoing": false,
  "change": { "comparedTo": "2026-10-07", "absolute": "2.30", "percent": "0.16", "direction": "up" }
}
```

- `change`는 **늘 있다** — 비교 대상이 없으면(저장된 첫 고시) `null`이다(`isOngoing`처럼 "확인했고 없다"를 밝힌다)
- 비교 대상 = 그 쪽에서 바로 아래 행이다. 일 = 직전 고시일, 주·월 = 직전 주·달의 대표값. 쪽의 마지막 행은 `hasMore` 판정에 더 읽은 한 건(다음 쪽의 첫 행)과 견준다
- `absolute` = `baseRate` − 비교 행 `baseRate`(저장 정밀도), `percent` = `absolute` ÷ 비교 행 `baseRate` × 100(소수 둘째 자리 — `/api/fx/latest`의 `change`와 같은 함수). 비교 행이
  0 이하면 `percent`만 `null`이다. `direction`은 `up`·`down`·`flat`
- 저장하지 않는다(요청마다 계산 — data-model §10)
- `/api/fx/latest`의 `change`(요약 칸의 전일 대비)는 같은 꼴·같은 글자다 — 그 경로의 대상 고르기와 응답은 바뀌지 않는다

## A10. 상장일 (반복 2026-10-10f — spec FR-033)

- `GET /api/stocks/search` 행·`GET /api/stocks/search/external` 행에 `firstTradedOn: "2010-09-09" | null` — 그 시세 식별자의 저장된 Yahoo 첫 거래일(종목이 없거나 모르면 `null`). 검색은 출처를 부르지
  않는다. `listedOn`(키움 국내 상장일 — 시작일 하한)은 그대로다
- `GET /api/crypto/search` 행의 `firstAvailableDate`는 그대로다(화면이 상장일 — 첫 일봉 — 으로 쓴다)
- `POST /api/stocks/selection` 응답은 **그대로**다. 안에서 그 종목의 첫 거래일을 모르면 앱 수명주기의 공유 시세 클라이언트로 한 번 받는다(실패해도 등록 성공)
- 비교 블록(`/api/comparison/*`)에 `listing`:

```json
"listing": { "date": "2010-09-09", "basis": "first_trade" }
```

- `basis`: `listing`(키움 국내 상장일) · `first_trade`(Yahoo 첫 거래일) · `first_bar`(코인 첫 일봉). 모르면 `listing: null`. 예금·부동산 경로는 늘 `null`
- 주식 비교 경로(일시금·적립식)는 키움 상장일이 없고 첫 거래일을 모르면 응답 전에 한 번 받아 둔다(등록과 같은 규칙 — 실패해도 200, `listing: null`)
- 메뉴 시뮬레이션 응답(`/api/stocks/*`·`/api/crypto/*`)은 바뀌지 않는다

## A11. 고른 대상의 상장일 (반복 2026-10-10g — spec FR-034)

- `GET /api/stocks/listing-date?market=NYSE&symbol=QLD` → 200

```json
{ "market": "NYSE", "symbol": "QLD", "listing": { "date": "2006-06-21", "basis": "first_trade" } }
```

  - 고르기·채우기는 비교 블록의 `listing`(A10)과 같은 함수다 — 키움 상장일 → 첫 거래일. 둘 다 없으면 응답 전에 공유 시세 클라이언트로 한 번 받아 둔다(실패·시간 초과·클라이언트 없음이어도
    200 `listing: null`). `market`·`symbol`은 저장된 종목의 것이다(미국은 다른 거래소로 등록된 같은 티커 — 006 FR-030a)
  - 없는 종목은 404 `unknown_stock`(등록하지 않는다 — 실행이 등록한 뒤 다시 물으면 보인다). `market`·`symbol` 빠짐 422
- `GET /api/crypto/listing-date?coinId=1057391` → 200 `{ "coinId": 1057391, "listing": { "date": "2010-07-18", "basis": "first_bar" } }` — `first_available_date`, 모르면
  `listing: null`. 없는 코인 404 `unknown_coin`. 출처를 부르지 않는다
- 등록(`POST /api/stocks/selection`)·검색·메뉴 시뮬레이션 응답은 그대로다

## A12. 비교 블록의 현재 가치 선 (반복 2026-10-11b — spec FR-036)

- 비교 경로 일곱(`/api/comparison/{stocks,crypto,deposit,realestate}/simulation`·`stocks/recurring-simulation`·`crypto/recurring-simulation`·`deposit/installment-simulation`)의 200 응답
  `comparison`에 키 하나가 더해진다. 202·거절 본문, `summary`·`series`, 블록의 다른 칸(`lineEnd` 포함)은 그대로다

```json
"valueLine": {
  "points": [
    { "date": "2024-01-02", "value": "10000000" },
    { "date": "2024-02-01", "value": "10412345" },
    { "date": "2026-10-06", "value": "12596486" }
  ],
  "afterSaleValue": "12045573"
}
```

  - `points`: `series.points`와 **같은 날짜·같은 차례로 하나씩**(다운샘플링 뒤의 그 날). `value`는 그 날의 원화 총자산(원, 소수 문자열 — 지수 표기 없음)이고 비교 표 "현재 가치"
    (`currentValue`)와 같은 뜻이다
    - 주식·가상자산 일시금: 그 날 마지막 행의 KRW 원금 + 투자 수익(예수금·매수 뒤 남은 현금 포함) — 점 `balance`(보유분만)와 다를 수 있다
    - 주식·가상자산 적립식·정기예금·정기 적금·부동산: 점 `balance`와 같은 값
    - 마지막 점이 기준일이면 그 `value`는 `currentValue`와 같은 글자다
  - `afterSaleValue`: `principal.krw` + 매도 후 투자 수익(`comparison.profit`) — `mainBasis`가 `after_sale`일 때만, 아니면 `null`(`lineEnd.afterSaleReturnRate`와 짝)
  - 메뉴 경로(`/api/stocks/simulation/series` 등)의 응답에는 없다 — 메뉴 응답은 그대로다

## A13. 보기 구간 질의 (반복 2026-10-11c — spec FR-038)

- 대상 경로 여덟: `/api/stocks/simulation/series`·`/api/stocks/recurring-simulation/series`·`/api/crypto/simulation/series`·`/api/crypto/recurring-simulation/series`와
  `/api/comparison/stocks/simulation`·`stocks/recurring-simulation`·`crypto/simulation`·`crypto/recurring-simulation`
- 선택 질의 `viewFrom=YYYY-MM-DD&viewTo=YYYY-MM-DD` — 둘 다 또는 둘 다 없음. 하나만이거나 `viewFrom` > `viewTo`면 400 `invalid_query`. 계산(`start`·`end`·원금 등)은 그대로다
- 있으면 시계열 본문(`points`·`gaps`·`downsampled`·`sourcePointCount`)이 **[`viewFrom`, `viewTo`] ∩ 계산 구간의 시세일마다 점 하나**다
  - 주식 일시금: 그 날 행(월·배당락·재투자)이 있으면 그날의 마지막 행, 없으면 그 날 상태(일자별 표 `period=daily` 행과 같은 잔고·수익률·가격)
  - 주식 적립식: 같은 규칙(납입·배당·재투자 행 / 그 날 상태, `principal` 포함)
  - 가상자산 일시금·적립식: 일봉 그대로(줄이기 전)
  - `gaps`는 그 구간에서 다시 판정, 점이 `maxPoints`보다 많으면 그 안에서 줄인다(`downsampled: true`)
- 비교 경로는 같은 구간 점으로 `comparison.valueLine`을 낸다(A12 규칙). `summary`·블록의 다른 칸은 질의와 무관하다
- 202·거절은 지금과 같다(수집 판정이 먼저다). 외환 `/api/fx/series`는 이미 `from`·`to`를 받는다 — 경로 변경 없음

## A14. `GET /api/dashboard/rates` — 기준금리 칸 (반복 2026-10-11d — spec FR-040)

**DB만 읽는다** — 출처를 부르지 않는다(수집은 워커 — FR-043). 은행마다 따로 실패해도 **200**이다.

```json
{
  "source": "네이버 증권",
  "sourceUrl": "https://stock.naver.com/market/marketindex/bondAndInterest/standardInterest",
  "refreshAfterSeconds": 60,
  "banks": [
    { "bank": "fed", "name": "미국연방준비은행", "flag": "🇺🇸", "rateKind": "연방기금금리 목표 범위 상단",
      "rate": "4.00", "change": "0.25", "direction": "up", "decidedOn": "2026-09-17", "announcedAt": "2026-09-16T18:00:00Z",
      "nextMeetingOn": "2026-10-29", "state": "ready", "failure": null, "lastSuccessAt": "2026-10-11T09:30:00Z" },
    { "bank": "bok", "name": "한국은행", "flag": "🇰🇷", "rateKind": "기준금리",
      "rate": null, "change": null, "direction": null, "decidedOn": null, "announcedAt": null, "nextMeetingOn": null,
      "state": "collecting", "failure": null, "lastSuccessAt": null }
  ]
}
```

- `banks`는 늘 다섯이고 차례는 은행 표(DM17.4)다 — `fed`·`bok`·`ecb`·`boe`·`boj`
- `rate`·`change`는 서버 `Decimal`의 문자열이다(소수 둘째 자리 이상 — 저장값의 뜻 있는 자리). `change`는 저장된 직전 결정과의 차이, 첫 결정이면 `null`(`direction`도 `null`). `direction`:
  `up`·`down`·`flat`
- `decidedOn`은 한국 날짜, `announcedAt`은 UTC(자리 표시 시각이면 `null`), `nextMeetingOn`은 한국 날짜(없거나 오늘(한국)보다 이르면 `null`)
- `state`: `ready`(결정이 있다 — 실패가 있으면 `failure`도 실린다: "최근 갱신 실패"), `collecting`(받은 결정이 없고 실패도 없다), `failed`(받은 결정이 없고 실패했다). `failure`:
  `{ "kind": A0, "message": "…", "at": "ISO UTC" }`
- `refreshAfterSeconds`는 화면의 다시 읽기 주기(지표 카드와 같은 설정). 화면은 `collecting`이 있으면 5초 뒤 다시 읽는다

## A15. `GET /api/dashboard/rates/{bank}` — 금리 모달 (반복 2026-10-11d — spec FR-041)

없는 `bank`는 404 `{ "status": "unknown_bank", "message": "없는 은행입니다: …" }`다(지표 경로의 `unknown_indicator`와 같은 꼴). DB만 읽는다.

```json
{
  "bank": "bok", "name": "한국은행", "flag": "🇰🇷", "rateKind": "기준금리",
  "rate": "3.00", "change": "0.25", "direction": "up", "decidedOn": "2026-08-27", "announcedAt": "2026-08-27T01:00:00Z",
  "nextMeetingOn": "2026-10-22", "state": "ready", "failure": null, "lastSuccessAt": "2026-10-11T09:30:00Z",
  "firstDecidedOn": "2016-01-14", "lastDecidedOn": "2026-08-27",
  "decisions": [
    { "decidedOn": "2026-08-27", "announcedAt": "2026-08-27T01:00:00Z", "rate": "3.00", "change": "0.25", "direction": "up" },
    { "decidedOn": "2016-01-14", "announcedAt": null, "rate": "1.50", "change": null, "direction": null }
  ]
}
```

- 머리 칸은 A14 행과 같은 값이다(같은 함수)
- `decisions`는 **최신부터 전부**다(쪽을 나누지 않는다 — 은행마다 약 90행). 그래프와 표가 같은 배열을 쓴다. 다음 결정 예정은 `decisions`에 넣지 않는다(`nextMeetingOn`)
- 받는 중·실패는 A14와 같은 `state`·`failure`(`decisions: []`)

## A16. `GET /api/dashboard/rates/{bank}/commentary` — 금리 변화 까닭 (반복 2026-10-11d — spec FR-042)

A8과 같은 꼴이다(`sessionDate` 대신 `decisionDate`). 출처가 실패해도 **200**, 없는 `bank`는 404, 저장하지 않는다(메모리 — `DASHBOARD_COMMENTARY_CACHE_SECONDS`).

```json
{
  "bank": "bok", "source": "네이버 증권", "sourceUrl": "https://stock.naver.com/news",
  "status": "ok", "fetchedAt": "2026-10-11T09:40:00Z", "decisionDate": "2026-08-27",
  "items": [
    { "title": "[속보]한은 금리 인상 결정에…", "summary": "…(출처 요약 원문)…", "publisher": "…",
      "publishedAt": "2026-08-27T01:05:00Z", "publishedDate": null, "publishedText": null, "url": "https://n.news.naver.com/mnews/article/…" }
  ],
  "failure": null
}
```

- `status`: `ok`(1~3개) · `none`(화면 "최근 결정을 다룬 기사를 찾지 못했습니다") · `failed`(A0 — 목록 표지 없음은 `parse_empty`). 결정이 아직 없으면 `none`·`decisionDate: null`
- 고르기는 spec FR-042 — 결정일(한국)과 다음 날, 분류 404 → 403 → 429, 은행 낱말 + 금리 낱말 둘 다, 발표 시각 30분 전(모르면 결정일 0시) 이후 게시, 최대 3·같은 제목 한 번(R14-33)

## A17. `POST /api/dashboard/rates/collect` — 다시 시도 (반복 2026-10-11d)

수집 워커를 곧바로 깨운다 — **202** `{ "accepted": true }`. 출처를 이 요청 안에서 부르지 않는다. 화면은 5초 뒤 A14를 다시 읽는다.

## A18. `GET /api/comparison/settings` · `PUT /api/comparison/settings` — 투자 비교 설정 (반복 2026-10-13 — spec FR-044)

저장한 비교 라우터(`/api/comparison/saved`)처럼 **비교 라우터(`/api/comparison/<자산군>/…`)보다 먼저** 등록한다 — 뒤에 두면 `settings`가 자산군 매개변수로 잡힌다.

`GET` — 200(행이 없으면 기본):

```json
{ "maxTargets": 20, "defaultMaxTargets": 20, "minTargets": 2, "limitTargets": 100 }
```

- `maxTargets` — 저장된 최대 대상 수(없으면 `defaultMaxTargets`). 나머지 셋은 상수다 — 화면이 범위·안내를 이 값으로 그린다(화면에 2·20·100을 박지 않는다)

`PUT` — 본문 `{ "maxTargets": <정수> }` → 200 같은 꼴(저장 뒤 다시 읽은 값). 틀리면 저장하지 않고 **422**(다른 설정 경로와 같은 꼴):

```json
{ "status": "invalid_setting", "message": "최대 대상 수는 2~100 사이의 정수여야 합니다: 101" }
```

- 거절: 범위 밖(1·101), JSON 정수가 아님(`true`·`20.5`·`"20"`·`null`·칸 없음·본문이 객체가 아님). DB 실패는 다른 설정 경로와 같은 오류 꼴이다

## A19. 비교 조건 검증의 끝 (반복 2026-10-13 — spec FR-045)

- 저장한 비교(`POST /api/comparison/saved` — 013 contracts 2~6)의 `condition.targets`는 **2~100개**(예금 ≤5 — 013 그대로)다. 101개면 422 `invalid_comparison`(`"targets: 2~100개여야 합니다: 101개"`). 끝은 **설정 값이
  아니다** — 설정(A18)은 화면의 더하기 한도다
- 직렬화한 조건 글(UTF-8)이 **65,535바이트를 넘으면** 저장하지 않고 422 `invalid_comparison`(`"condition: 저장할 조건이 너무 깁니다 — {N}바이트(65,535바이트까지)"`). 목록·삭제 응답 꼴은 그대로다
- 비교 경로 일곱(`/api/comparison/<자산군>/…`)은 대상 하나씩이라 바뀌지 않는다

## A20. 주식·가상자산 일자별 표 행의 등락 (반복 2026-10-13b — spec FR-048)

메뉴 시뮬레이션 경로 넷의 표 행(`rows[]`)에 칸을 더한다 — `GET /api/stocks/simulation`·`GET /api/stocks/recurring-simulation`(005·011 — 주식 `openChange`·`closeChange`),
`GET /api/crypto/simulation`·`GET /api/crypto/recurring-simulation`(007·011 — 가상자산 `openChange`). 질의·다른 칸·차례·쪽 넘기기(`before`·`limit`·`hasMore`·`oldestReturned`)·`period`·요약·조건·202 본문은
그대로다. 투자 비교 모달은 같은 경로를 부른다. 시계열 경로(`…/series`)·비교 경로(`/api/comparison/…`)는 바뀌지 않는다.

```json
{
  "rows": [
    { "date": "2024-06-10", "kind": "period", "openPrice": "120.370000", "closePrice": "121.790000", "…": "005·010 그대로",
      "openChange":  { "comparedTo": "2024-06-07", "absolute": "0.600000", "percent": "0.50", "direction": "up", "splitRatio": "10:1" },
      "closeChange": { "comparedTo": "2024-06-07", "absolute": "0.902000", "percent": "0.75", "direction": "up", "splitRatio": "10:1" } },
    { "date": "2024-06-07", "kind": "period", "openPrice": "1197.700000", "closePrice": "1208.880000", "…": "…",
      "openChange":  { "comparedTo": "2024-06-06", "absolute": "-41.300000", "percent": "-3.33", "direction": "down", "splitRatio": null },
      "closeChange": { "comparedTo": "2024-06-06", "absolute": "-1.170000", "percent": "-0.10", "direction": "down", "splitRatio": null } },
    { "date": "2024-01-02", "kind": "buy", "openPrice": "492.440000", "closePrice": "481.680000", "…": "…", "openChange": null, "closeChange": null }
  ]
}
```

(NVDA 일시금 일 단위의 꼴 — 값은 예시다. 2024-06-10 효력 10:1 분할이라 2024-06-07 가격을 ÷10 해 견준다: 1208.88 ÷ 10 = 120.888 → 121.79 − 120.888 = 0.902)

```json
{ "date": "2024-03-02", "kind": "period", "openPrice": "62431.652344", "…": "007 그대로",
  "openChange": { "comparedTo": "2024-03-01", "absolute": "1263.589844", "percent": "2.07", "direction": "up", "splitRatio": null } }
{ "date": "2024-02-27", "dateTo": "2024-02-28", "kind": "missing" }
```

- 키는 **늘 있다**(결측 구간 행 제외) — 비교 대상이 없으면 `null`이다(외환 A9의 `change`와 같다 — "확인했고 없다"). 가상자산 행에는 `closeChange`가 없다
- 비교 대상 = **직전 기간의 대표값**(data-model 19.2) — 일 = 직전 시세일(가상자산 출처 결측 구간은 건너뜀), 주·월 = 직전 주·달의 대표 행. 기간 사이의 사건 행(`buy`·`dividend`·`reinvest`·
  `contribution`)도 그 행이 속한 기간의 직전 기간 대표값이다. 같은 날 행은 같은 값. 계산 기간의 첫 기간은 `null`. 쪽의 마지막 행도 쪽 너머의 비교 행과 견준다(`comparedTo`가 다음 쪽 행의 날짜일 수 있다)
- `absolute` = 그 행 가격 − 비교 가격(분할을 맞췄으면 맞춘 값 — 소수 6자리 `ROUND_HALF_UP`), `percent` = `absolute` ÷ 비교 가격 × 100(소수 둘째 자리 — `/api/fx/daily`·`/api/fx/latest`와 같은 함수).
  비교 가격이 0 이하면 `percent`만 `null`. `direction`은 `up`·`down`·`flat`
- `splitRatio` = 효력일 ∈ (비교 날짜, 행 날짜]인 분할·병합의 누적 비율(`"분자:분모"` — 비교 블록 `unitPrice.split.ratio`와 같은 글자). 없거나 1:1이면 `null`. 배당은 맞추지 않는다
- 저장하지 않는다(요청마다 계산 — data-model §19)

## A6. 불변

기존 경로의 응답은 바뀌지 않는다(FR-026):
- 외환: `/api/fx/*` — (반복 2026-10-10d) 예외 하나: `/api/fx/daily`의 행에 `change`가 더해진다(A9). `/api/fx/latest`·`/api/fx/series`·수집 경로는 그대로다
- (반복 2026-10-10f) 주식 검색 응답 둘의 행에 `firstTradedOn`, 비교 블록에 `listing`만 더해진다(A10). 등록 응답·메뉴 시뮬레이션 응답은 그대로다
- (반복 2026-10-10g) 새 읽기 경로 둘(A11)이 더해진다. 기존 경로의 응답은 그대로다
- (반복 2026-10-11) 경로 변경이 없다 — 표 경로(`/api/fx/daily`·주식·가상자산 일시금·적립식)는 `period`가 없으면 그대로 일이다. 화면이 처음 요청부터 `period=monthly`를 싣는다(FR-035)
- (반복 2026-10-11b) 비교 경로 일곱의 200 `comparison`에 `valueLine`만 더해진다(A12). 메뉴 경로·비교 블록의 다른 칸은 그대로다. 그래프 확대(FR-037)는 요청이 없다
- (반복 2026-10-11c) 주식·가상자산 시계열 경로 여덟에 선택 질의 `viewFrom`·`viewTo`(A13) — 질의가 없으면 응답은 그대로다. 확대는 일 단위 그래프에서 구간을 받는다(FR-038)
- (반복 2026-10-11d) 새 경로 넷(A14~A17)만 더해진다. 대시보드의 지표·뉴스 경로(A1~A5·A7·A8)와 외환·다른 메뉴 경로의 응답은 그대로다
- (반복 2026-10-13) 새 경로 하나(A18 — `GET`·`PUT`)가 더해지고 저장한 비교의 대상 수 끝이 100·저장 길이 가드(A19)다. 비교 경로 일곱의 질의·응답·비교 블록, 저장한 비교 목록·삭제 응답 꼴은 그대로다
- (반복 2026-10-13b) 메뉴 시뮬레이션 경로 넷(주식·가상자산 일시금·적립식)의 표 행에 `openChange`·`closeChange`(가상자산은 `openChange`)만 더해진다(A20). 질의·다른 칸·쪽·요약·202와 시계열·비교 경로는 그대로다
- 주식: `/api/stocks/*`
- 가상자산: `/api/crypto/*`
- 예금: `/api/deposit/*`
- 부동산: `/api/realestate/*`
- 이력: `/api/history/*`
- 비교: `/api/comparison/*`

대시보드 라우터는 기존 라우터 뒤에 등록한다.
