# Data Model: 014 대시보드

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

## 1. 테이블 (Alembic 리비전 하나, `down_revision = "b3e7d5a1c924"`)

금액·지수 열은 `PRICE = Numeric(20, 6)`(models.py의 기존 형)이다. 시각은 UTC `DateTime(timezone=False)`(`TS`)다. 열거형은 비원생(`native_enum=False`)이다.

### 1.1 `market_indicator_daily` — 확정 종가(정규화)

| 열 | 형 | 제약 | 뜻 |
|----|----|------|----|
| `indicator_id` | `String(32)` | PK | 지표 id(§2 — `kospi`·`sp500` 등, 환율 셋은 없다) |
| `trade_date` | `Date` | PK | **그 시장의 현지 거래일**(R14-3 — `zoneinfo`) |
| `close` | `PRICE` | NOT NULL | 종가. 음수 가능(WTI 2020-04-20 −37.63) |
| `open_price` · `high_price` · `low_price` | `PRICE` | NULL | 반복 2026-10-10b — 그 날의 시가·고가·저가. 출처가 주지 않거나 0이면 NULL(0으로 메우지 않는다 — 옛 일봉) |
| `source` | `String(64)` | NOT NULL | `"yahoo:chart"` |
| `ingested_at` | `TS` | server_default now | 처음 저장 시각 |

- 유일성은 복합 PK `(indicator_id, trade_date)`다
- 저장은 **없는 날만 넣는다**. 있는 날은 값을 견줘 다르면 개정(§1.4)이고 덮어쓰지 않는다 — `db/dialect.upsert`가 아니라 "있는 날 읽기 → 새 날만 삽입"이다(008 `deposit_rate.store_rates`와 같다)
- 오늘(현지)·종가 `null` 행은 넣지 않는다(R14-4)
- 시가·고가·저가(반복 2026-10-10b — R14-18):
  - 새 날을 넣을 때 함께 넣는다. 있는 날은 덮지 않는다 — 개정 기록(§1.4)은 종가만이다
  - 열이 생기기 전에 넣은 날(NULL)은 **저장해 둔 원본 응답(§1.2)에서 되살린다**. 멱등이고 다시 받지 않는다. 같은 날이 원본 여럿에 있으면 가장 늦게 받은 원본이다
  - 원본에도 없으면 NULL로 둔다

### 1.2 `market_indicator_raw` — 원본 응답

| 열 | 형 | 뜻 |
|----|----|----|
| `id` | `BigInteger` PK 자동 증가 | |
| `indicator_id` | `String(32)` | |
| `requested_from` · `requested_to` | `Date` | 청크 범위(현지 날짜) |
| `status_code` | `SmallInteger` | |
| `body` | `Text(16_777_215)`(utf8mb4에서 LONGTEXT — 005·007 원본 표와 같다) | 응답 본문 그대로 — 주소는 남기지 않는다 |
| `received_at` | `TS` | |

색인은 `(indicator_id, received_at)`이다. 하루 한 번 이어 받기라 지표마다 하루 한 줄 남짓 쌓인다(R14-4).

### 1.3 `market_indicator_coverage` — 수집 커버리지·상태

| 열 | 형 | 뜻 |
|----|----|----|
| `indicator_id` | `String(32)` PK | |
| `first_day` | `Date` NULL | 출처의 첫 거래일 — 처음 응답의 `firstTradeDate`에서 **발견해 기록**(코드에 날짜 없음) |
| `covered_from` · `covered_through` | `Date` NULL | 받은 연속 구간 하나. 받은 구간만 기록한다(FR-019) |
| `last_success_at` · `last_failure_at` | `TS` NULL | |
| `last_failure_kind` | `String(32)` NULL | `connection`·`rate_limited`·`blocked`·`invalid_body`·`not_found` |
| `last_failure_message` | `String(500)` NULL | `mask_secrets`를 거친 문구 |
| `updated_at` | `TS` | |

- 커버리지는 **성공한 요청의 범위**다 — 휴장으로 새 행이 없어도 요청한 날까지 `covered_through`가 늘어난다(007 `record_coverage`와 같다)
- **백필 완성** = `first_day`가 있고 `covered_from ≤ first_day`다. 그래프 경로는 백필이 완성되지 않았으면 202를 준다(FR-016)
- **끝쪽 지연** = `covered_through < 그 시장 현지 어제`. 그래프는 200으로 보이되 `tailPending: true`("최근 구간 받는 중")를 싣는다. 카드의 전일 종가는 출처 값으로 물러난다(R14-8)

### 1.4 `market_close_revision` — 확정 값 개정

| 열 | 형 | 뜻 |
|----|----|----|
| `id` | `BigInteger` PK 자동 증가 | |
| `indicator_id` · `trade_date` | `String(32)` · `Date` | |
| `stored_close` · `source_close` | `PRICE` · `PRICE` | 저장된 확정 값 · 다시 받은 출처 값 |
| `detected_at` | `TS` | |

같은 `(indicator_id, trade_date, source_close)`는 한 번만 넣는다 — 겹쳐 받을 때마다 같은 개정이 쌓이지 않게 한다.

## 2. 지표 목록 (코드 상수 — 고정 15개, FR-003)

도메인 쪽(`simulation/market_indicators.py`)은 출처 심볼을 모른다. 심볼은 수집 계층(`ingestion/yahoo/market_symbols.py`)에만 있다.

| id | 이름 | 묶음(`group`) | 차례 | 시장 키 | 단위 | 종류(`kind`) | 이력 | 결측 묶음 |
|----|------|---------------|------|---------|------|--------------|------|-----------|
| `kospi` | KOSPI | `korea` | 1 | `krx` | 포인트 | `index` | 대시보드 표 | `krx` |
| `kosdaq` | KOSDAQ | `korea` | 2 | `krx` | 포인트 | `index` | 대시보드 표 | `krx` |
| `dow` | 다우존스 산업평균 | `us` | 3 | `us_equity` | 포인트 | `index` | 대시보드 표 | `us_equity` |
| `nasdaq` | 나스닥 종합 | `us` | 4 | `us_equity` | 포인트 | `index` | 대시보드 표 | `us_equity` |
| `sp500` | S&P 500 | `us` | 5 | `us_equity` | 포인트 | `index` | 대시보드 표 | `us_equity` |
| `sox` | 필라델피아 반도체 | `us` | 6 | `us_equity` | 포인트 | `index` | 대시보드 표 | `us_equity` |
| `nikkei225` | 니케이 225 | `asia` | 7 | `tse` | 포인트 | `index` | 대시보드 표 | — |
| `hangseng` | 항셍 | `asia` | 8 | `hkex` | 포인트 | `index` | 대시보드 표 | — |
| `shanghai` | 상해 종합 | `asia` | 9 | `sse` | 포인트 | `index` | 대시보드 표 | — |
| `usd` | 달러 | `fx` | 10 | `fx` | 원 | `fx` | 외환 `fx_rate` USD | (외환 규칙) |
| `jpy` | 엔(100엔) | `fx` | 11 | `fx` | 원(100엔당) | `fx` | 외환 `fx_rate` JPY | (외환 규칙) |
| `eur` | 유로 | `fx` | 12 | `fx` | 원 | `fx` | 외환 `fx_rate` EUR | (외환 규칙) |
| `wti` | WTI 원유 | `commodity` | 13 | `cme` | USD/배럴 | `future` | 대시보드 표 | `cme` |
| `gold` | 금 | `commodity` | 14 | `cme` | USD/트로이온스 | `future` | 대시보드 표 | `cme` |
| `vix` | VIX | `commodity` | 15 | `cboe` | 포인트 | `volatility` | 대시보드 표 | — |

- 묶음 이름(화면): `korea` 한국, `us` 미국, `asia` 일본·중국, `fx` 환율, `commodity` 원자재·변동성
- 카드 주석(`notes`):
  - `future`: "선물 근월물 연속 — 만기 교체로 끊김이 있을 수 있음"(FR-015)
  - `fx`: "시장 환율 — 외환 메뉴의 매매기준율과 다를 수 있음"(FR-018)

수집 계층 대응(`market_symbols.py`):

| id | 차트·spark 심볼 | 값 배수 |
|----|-----------------|---------|
| `kospi`…`vix` | R14-1 표 | 1 |
| `usd` | `KRW=X` | 1 |
| `jpy` | `JPYKRW=X` | **100**(1엔당 → 100엔당) |
| `eur` | `EURKRW=X` | 1 |

## 3. 시장 거래 시간 (`simulation/market_session.py` — 순수)

R14-7 표가 상수다. 함수는 둘이다:
- `trading_date(market, instant_utc) -> date`: 밤을 넘는 세션(`cme` 18:00, `fx` 17:00 — 뉴욕)의 다음 거래일 규칙을 따른다
- `market_state(market, now_utc, source_session_start_utc) -> MarketState`

`MarketState`는 다섯 값이다:

| 값 | 화면 | 잠정 | 판정 |
|----|------|------|------|
| `pre_open` | 개장 전 | 아니다(지난 거래일 확정 값) | 오늘이 거래일이고 첫 세션 전 |
| `open` | 장중 | ⏳ 잠정 | 세션 안 |
| `break` | 점심 휴장 | ⏳ 잠정 | 두 세션 사이 |
| `closed` | 마감 | 오늘 종가면 ⏳ 확정 전 | 마지막 세션 뒤 |
| `holiday` | 휴장 | 아니다 | 출처 세션 날짜 < 현지 오늘, 주말, 또는 세션 안인데 값이 이번 세션 시작보다 앞이고 시작 뒤 `MARKET_HOLIDAY_DETECT_SECONDS` 경과(R14-7) |

## 4. 현재 시세 카드 (`simulation/market_quote.py` — 순수, 저장하지 않음)

입력:
- 지표(§2)
- 출처 시세 — `price`, `market_time`, `full_day_change`, `chart_previous_close`, `session_start`
- `now`, `fetched_at`
- 이력 전일 — `sessionDate` 앞의 마지막 저장 종가와 날짜, 커버리지 끝

출력(`MarketQuote`, API `quote` 블록 — contracts A1):

| 칸 | 형 | 규칙 |
|----|----|------|
| `value` | 문자열 Decimal | 출처 가격 × 배수(엔 100) |
| `valueTime` | ISO UTC | `regularMarketTime` |
| `sessionDate` | 날짜 | 값의 거래일(§3) — 휴장이면 마지막 거래일 |
| `state` | `MarketState` | §3 |
| `provisional` | bool | `open`·`break`, 또는 `closed`이면서 `sessionDate`가 현지 오늘 |
| `delayMinutes` | int · null | R14-9 |
| `previous.close` · `previous.date` · `previous.from` | 문자열 · 날짜/null · `history`/`source`/`source_fx` | R14-8 |
| `change` | 문자열 Decimal | `value − previous.close` |
| `changeRate` | 문자열 Decimal · null | `change ÷ previous.close`(`quantize_rate`). 전일 ≤ 0이면 null |
| `changeRateBlank` | `"non_positive_base"` · null | |
| `direction` | `up`·`down`·`flat` | 차이의 부호 |

## 5. 그래프 점 (반복 2026-10-10b — 기간 8개)

차트는 **점을 묶지 않는다**. 기간(`range`)이 고르는 것은 보는 범위와 점의 출처다:

| `range` | 점의 출처 | 점 |
|---------|-----------|-----|
| `1d` | 장중 시세(R14-19 — 5분, 저장 안 함) | `{time, value, provisional: true}` — `time`은 ISO UTC |
| `5d` | 장중 시세(30분, 저장 안 함) | 같다 |
| `1m`·`1y`·`5y`·`10y`·`20y` | 저장된 일봉(§1.1) — 기간의 시작일(현지 오늘에서 1개월·n년 전) 이후(**반복 2026-10-10c 대체** — 아래 표: 일봉 전부 + `windows`) | `{date, value, provisional?}` |
| `all` | 저장된 일봉 전부 | 같다 |

- 일봉 기간의 오늘 잠정 꼬리(현재 시세)·외환 잠정 고시는 지금과 같다(`provisional`)
- 점이 `DASHBOARD_SERIES_MAX_POINTS`를 넘을 때만 LTTB(R14-12)
- 결측 구간(`simulation/market_gaps.py` — R14-5)은 일봉 기간에 그대로다. 장중은 결측 판정을 하지 않는다

**반복 2026-10-10c — 기간은 처음 보이는 범위다**(R14-22):

| `range` | 받는 점 | 처음 보이는 범위 |
|---------|---------|------------------|
| `1d` | 장중 `range=5d`·5분(최근 5세션, 저장 안 함) | `window` = 마지막 세션(시장 현지 날짜) |
| `5d` | 장중 `range=1mo`·30분(최근 1개월, 저장 안 함) | `window` = 최근 5세션 |
| `1m`·`1y`·`5y`·`10y`·`20y`·`all` | **저장된 일봉 전부**(지금의 `all`과 같은 점) | `windows[range]`(시작일 — `all`은 `null`) |

- 일봉 본문의 `windows`는 `{"1m": 시작일, "1y": …, "5y": …, "10y": …, "20y": …, "all": null}` — 시작일 규칙은 지금과 같다(`simulation/indicator_range.range_start` — 현지 오늘에서 1개월·n년 전,
  없는 날은 그 달 말일). 화면은 같은 본문으로 월~모두를 오간다
- 장중 본문의 `window`는 `{from, to}`(UTC ISO) — 순수 모듈 `simulation/intraday_window.py`가 점의 시장 현지 날짜(`market_session`의 시간대, 환율은 런던 0시 경계)로 세션을 가른다.
  세션은 점이 있는 날뿐이다(빈 날을 꾸미지 않는다). 점이 없으면 `null`
- 화면은 처음 범위를 **점의 차례**로 놓는다(`setVisibleLogicalRange` — 창 시작 이상인 첫 점의 차례 ~ 마지막 차례). 창 안에 점이 없으면 마지막 점들이다

## 5a. 일자별 표 행 (`simulation/indicator_table.py` — 순수, 반복 2026-10-10b)

`build_rows(bars, period, today_local, provisional_today) -> TableRow[]` — `period`는 `daily`·`weekly`·`monthly`(012 `period_table`의 기준일·쪽 나누기 규칙을 쓴다 — R14-21).

| 칸 | 형 | 뜻 |
|----|----|----|
| `date` | 날짜 | 대표일 — 일: 그 날 / 주: 금요일 이하 마지막 거래일 / 월: 말일 이하 마지막 거래일 |
| `open` · `high` · `low` | 문자열 Decimal · null | 일: 그 날 / 주·월: 첫 거래일 시가 · 기간 최댓값 · 기간 최솟값(값이 하나도 없으면 null). 환율은 늘 null |
| `close` | 문자열 Decimal | 대표일 종가 |
| `change` · `changeRate` | 문자열 Decimal · null | 앞 행(일: 직전 거래일, 주·월: 앞 기간 대표 종가)과의 차이·비율. 앞 행이 없으면 null, 앞 종가가 0 이하면 `changeRate` null |
| `shiftedFrom` | 날짜 · 없음 | 대표일 ≠ 기간 끝(금·말일) → 원래 기준일 — 📅 (주식 일자별 표와 같은 꼴) |
| `isOngoing` | true · 없음 | 기간 끝 > 현지 오늘 → ⏳ |
| `provisional` | bool | 오늘(현지) 잠정 행(카드 값 — 시가·고가·저가는 null, R14-19), 또는 외환 잠정 고시 |

- 결측(§5)은 일 단위에서 결측 구간 행 `{kind: "missing", date, dateTo}`이다. 휴장은 행이 없다
- 행은 012 `api/services/table_rows`(`table_page`·`row_body`)로 만든다 — 주식 일자별 표와 같은 쪽 나누기·꼴
- 쪽은 최신부터 `limit`(기본 30·최대 200)개, `before`(그 날짜 미만) — 주식 일자별 표(012)와 같다. 하루가 두 쪽에 갈리지 않는다

## 6. 뉴스 (`ingestion/news/types.py` — 저장하지 않음)

`NewsItem`:

| 칸 | 형 | 뜻 |
|----|----|----|
| `rank` | int | 1~10 |
| `title` | str | 원문 그대로 |
| `url` | str | 절대 https, 허용 도메인(R14-13) |
| `publisher` | str · null | |
| `publishedAt` | ISO UTC · null | 정확한 시각이 있을 때만(kr·jp 오늘) |
| `publishedDate` | 날짜 · null | 날짜만 있을 때(jp 지난 날) |
| `publishedText` | str · null | 상대 표기 글자 그대로(us) |
| `paid` | bool | 출처의 유료 표시(jp `isPaidArticle`) |

`NewsList`:
- 성공: `source`(`kr`·`us`·`jp`), `fetchedAt`, `items[]`
- 실패: `source`, `failure{reason, message, retryAfterSeconds}`. `reason`은 `connection`·`blocked`·`rate_limited`·`parse_empty`·`invalid_body`다

서버 메모리 캐시: 칸마다 `(성공 NewsList, 만료)` 또는 `(실패, 다시 시도 가능 시각, 연속 실패 수)`. 앱을 다시 띄우면 비어 있다.

## 6a. 변화 까닭 (`ingestion/news/commentary.py` — 저장하지 않음, 반복 2026-10-10b)

`CommentaryItem`: `title`(원문) · `summary`(출처 요약 원문 · null) · `publisher` · `publishedAt`·`publishedDate`·`publishedText`(뉴스 §6과 같은 셋 가운데 하나) · `url`(허용 도메인·https)

`IndicatorCommentary`:
- 성공: `indicator`, `source`(출처 이름), `sourceUrl`(출처 목록 화면), `fetchedAt`, `items[]`(0~3개)
  - `items`가 비면 `status: "none"` — 마지막 세션 이후의 기사가 없다("찾지 못함")
- 실패: `failure{reason, message, retryAfterSeconds}` — contracts A0. 목록 표지가 없거나 0건 읽기는 `parse_empty`

서버 메모리 캐시: 지표마다 성공 `DASHBOARD_COMMENTARY_CACHE_SECONDS`(기본 600), 실패는 뉴스와 같은 백오프(60 → 600).

## 7. 화면 상태 (Zustand)

| 스토어 | 상태 | 동작 |
|--------|------|------|
| `stores/marketQuotesStore.ts` | `status`(`idle`·`loading`·`ready`·`error`), `fetchedAt`, `refreshAfterSeconds`, `indicators[]`(contracts A1), `seq` | `load()` · `startPolling()`/`stopPolling()`(보이는 동안만 — R14-15) · `retry(id)`. 늦은 응답은 `seq`로 버린다 |
| `stores/indicatorSeriesStore.ts` | `id`, `range`(반복 2026-10-10b — `unit` 대체), `status`(`loading`·`ready`·`collecting`·`failed`·`not_found`·`error`), `series`, `progress`, `seq`. 반복 2026-10-10c: 일봉 본문 한 벌(`daily`)을 지표마다 들고 있다 | `open(id, range)` · `setRange(range)`(주소도 바꾼다 — 반복 2026-10-10c: 월~모두 사이는 다시 받지 않고 `range`만, 장중 ↔ 일봉·장중끼리는 받는다) · 202면 진행 SSE 구독 → `completed`에 다시 요청 · `retryCollect()`(POST collect) · `close()`(구독 끊기) |
| `stores/indicatorTableStore.ts` | `id`, `period`(`daily`·`weekly`·`monthly`), `status`, `rows[]`, `hasMore`, `oldestReturned`, `seq` | `open(id)` · `setPeriod(period)`(처음부터 다시) · `loadMore()`(`before = oldestReturned`) · `close()`. 늦은 응답은 `seq`로 버린다 |
| `stores/indicatorCommentaryStore.ts` | 지표마다 `{status, body, failure}` | `load(id)` · `retry(id)` |
| 모달 | 주소(`/dashboard/{id}?range=`)가 열림 상태다 — 스토어에 두지 않는다 | 닫으면 `router.back()`(대시보드 안에서 연 경우) 또는 `/dashboard`로 바꾸기, 포커스는 그 카드(`data-indicator`) |
| `stores/newsStore.ts` | 칸마다 `{status, list, failure}` | `loadAll()`(셋 동시) · `retry(source)` |
| `stores/themeStore.ts`(반복 2026-10-10c) | `theme`(`light`·`dark`) | `toggle()` · `set(theme)` — `<html>`의 `dark` 클래스와 브라우저 저장소(§9)를 함께 바꾼다. 처음 값은 깜빡임 방지 스크립트가 단 클래스에서 읽는다 |

## 8. 설정 (`config/settings.py` — `.env.example`에 문서화)

| env | 기본 | 쓰임 |
|-----|------|------|
| `MARKET_SOURCE_BASE_URL` | `https://query1.finance.yahoo.com` | 대시보드 Yahoo 요청 |
| `MARKET_CHUNK_DAYS` | 730 | 백필 청크(R14-2) |
| `MARKET_CHUNK_DELAY_MS` | 1500 | 청크 사이 간격 |
| `MARKET_COLLECT_INTERVAL_SECONDS` | 1800 | 워커가 깨는 주기(R14-11) |
| `MARKET_RECHECK_OVERLAP_DAYS` | 5 | 이어 받기 겹침(R14-4) |
| `MARKET_RETRY_MAX_ATTEMPTS` · `MARKET_RETRY_BASE_DELAY_MS` · `MARKET_REQUEST_TIMEOUT_SECONDS` | 4 · 1000 · 20 | 재시도·백오프·타임아웃 |
| `MARKET_QUOTE_CACHE_SECONDS` · `MARKET_QUOTE_FAILURE_CACHE_SECONDS` | 30 · 10 | 현재 시세 캐시(R14-6) |
| `MARKET_DELAY_NOTICE_SECONDS` | 180 | 지연 표시(R14-9) |
| `MARKET_HOLIDAY_DETECT_SECONDS` | 3600 | 갱신 없는 세션의 휴장 판정(R14-7) |
| `DASHBOARD_REFRESH_SECONDS` | 60 | 화면의 카드 갱신 주기(응답 `refreshAfterSeconds`) |
| `DASHBOARD_SERIES_MAX_POINTS` | 30000 | 그래프 점 한도(R14-12) |
| `YAHOO_MAX_CONCURRENT_REQUESTS` | 2 | Yahoo 관문(R14-10) |
| `NEWS_USER_AGENT` | 브라우저형(주식 클라이언트와 같은 꼴) | 뉴스 요청(R14-13) |
| `NEWS_CACHE_SECONDS` · `NEWS_FAILURE_CACHE_SECONDS` · `NEWS_FAILURE_CACHE_MAX_SECONDS` | 600 · 60 · 600 | 뉴스 캐시·실패 백오프 |
| `NEWS_REQUEST_TIMEOUT_SECONDS` · `NEWS_RETRY_MAX_ATTEMPTS` | 10 · 2 | |
| `NEWS_KR_URL` · `NEWS_US_URL` · `NEWS_JP_URL` | R14-13의 요청 주소 | 출처 주소(바뀌면 설정으로) |
| `DASHBOARD_INTRADAY_DAY_CACHE_SECONDS` · `DASHBOARD_INTRADAY_WEEK_CACHE_SECONDS` | 60 · 300 | 반복 2026-10-10b — 장중 시세 캐시(R14-19) |
| `DASHBOARD_COMMENTARY_CACHE_SECONDS` | 600 | 변화 까닭 캐시(R14-17) |
| `DASHBOARD_TABLE_PAGE_LIMIT` | 30 | 일자별 표 한 쪽(최대 200) |
| 변화 까닭 출처 주소 | T095 실측 뒤 정함(R14-17) | 출처가 주소를 바꾸면 설정으로 |

반복 2026-10-10c는 새 설정이 없다 — 장중 받는 범위(일 `5d`·주 `1mo`)는 어댑터의 대응표(`ingestion/yahoo/market.py`)이고 캐시 시간은 그대로다.

## 9. 화면 테마 선호 (반복 2026-10-10c — 브라우저에만, FR-030)

| 항목 | 값 |
|------|-----|
| 저장 위치 | 브라우저 저장소(`localStorage`) 키 `assetreplay.theme` — 서버·DB에 두지 않는다 |
| 값 | `"light"` · `"dark"`. 없거나 그 밖의 값·읽기 실패면 `"light"` |
| 적용 | `<html>`의 `dark` 클래스. `app/layout.tsx`의 `<head>` 인라인 스크립트가 **그리기 전에** 저장값을 읽어 단다(깜빡임 방지 — `suppressHydrationWarning`) |
| 바꾸기 | `themeStore.toggle()` — 클래스·저장소를 함께 바꾼다. 저장소 쓰기가 실패해도 지금 화면은 바뀐다(그 탭에서만 유지) |
| 차트 | `lib/chartTheme.ts`의 팔레트(배경·글자·격자·선) — 테마가 바뀌면 차트를 다시 만든다(R14-23) |


## 10. 외환 일자별 행의 등락 (반복 2026-10-10d — FR-031, 저장하지 않음)

`GET /api/fx/daily`(001·004)의 행마다 더해지는 칸이다. 요청마다 계산하고 저장하지 않는다.

| 칸 | 꼴 | 뜻 |
|----|-----|-----|
| `change` | 객체 \| `null` | 바로 아래 행 대비. 비교 대상이 없으면(저장된 첫 고시) `null` |
| `change.comparedTo` | 날짜 `YYYY-MM-DD` | 비교한 행의 날짜(주·월은 그 대표일) |
| `change.absolute` | `Decimal` 문자열 | 그 행 `baseRate` − 비교 행 `baseRate`(저장 정밀도 그대로 — 반올림하지 않는다) |
| `change.percent` | `Decimal` 문자열 \| `null` | `absolute` ÷ 비교 행 `baseRate` × 100, 소수 둘째 자리(`ROUND_HALF_EVEN` — `Decimal.quantize` 기본). 비교 행이 0 이하면 `null` |
| `change.direction` | `"up"` · `"down"` · `"flat"` | `absolute`의 부호 |

- **비교 대상**: 그 쪽에서 바로 아래 행이다 — 일 = 직전 고시일, 주·월 = 직전 주·달의 대표값(`period_page`의 행). 쪽의 마지막 행은 `hasMore` 판정을 위해 한 건 더 읽은
  행과 견준다(추가 질의 없음). 더 읽은 행이 없으면(저장된 첫 고시) `null`이다
- **계산 함수**: 순수 모듈 `simulation/fx_change.py` 하나 — `/api/fx/latest`의 `change`(요약 칸의 전일 대비)도 이 함수를 부른다. 꼴이 같고(`LatestChange`) 같은 두 날이면
  같은 글자다. `/latest`는 잠정 값을 직전 **확정** 값과 견주는 지금의 대상 고르기가 그대로이고 응답이 바뀌지 않는다
  - `/latest`의 지금 규칙은 직전 값이 0이면 `percent`를 `"0"`으로 낸다 — `/latest` 응답 불변을 위해 그 경로는 그대로 두고, 표 행은 `null`("—")이다. 매매기준율이 0 이하인
    고시는 실제로 없다(R14-24)
- **화면**: `PeriodRow.change?: DailyChange | null`(선택 칸 — 014 전 테스트의 행 픽스처에 없어도 된다). `DailyChange`는 `LatestChange`와 같은 꼴이고 `percent`만 `null`일
  수 있다(요약 칸의 `LatestChange`는 그대로). `change`가 없거나 `null`이면 두 칸 모두 "—", `percent`만 `null`이면 등락율만 "—"
- **CSV**: `…,확정 여부,원래 기준일,진행 중,등락폭,등락율`(맨 끝 — 004가 더한 두 열 뒤) — `absolute`·`percent` 글자 그대로, 없으면 빈 칸
