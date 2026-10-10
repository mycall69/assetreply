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

## A6. 불변

기존 경로의 응답은 바뀌지 않는다(FR-026):
- 외환: `/api/fx/*`
- 주식: `/api/stocks/*`
- 가상자산: `/api/crypto/*`
- 예금: `/api/deposit/*`
- 부동산: `/api/realestate/*`
- 이력: `/api/history/*`
- 비교: `/api/comparison/*`

대시보드 라우터는 기존 라우터 뒤에 등록한다.
