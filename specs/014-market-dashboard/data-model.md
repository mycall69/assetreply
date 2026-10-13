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

## 11. 비교 대상의 표시 이름 (반복 2026-10-10e — FR-032, 화면 파생 값 — 저장하지 않음)

`lib/compareCondition.targetName(target)` 하나가 투자 비교 화면의 모든 이름 자리(칩·표·막힘 안내·범례·커서 상자·막대·모달 머리·저장한 비교 목록·화면 읽기 이름)에 이름을 준다.

| 대상 | 이름 | 예 |
|------|------|-----|
| 주식 | `nameWithCode({market, symbol, name})` — `lib/displayCode`(006 FR-025, 시세 식별자에서 표시 코드로 되돌림) | `삼성전자(005930)`·`S&P 500 뱅가드 ETF(VOO)`·`…(BRK-B)`·`도요타자동차(7203)` |
| 가상자산 | `coinNameWithSymbol({name, nameKo, symbol})` — `lib/displayCode`의 새 함수: `${nameKo ?? name}(${symbol})` | `비트코인(BTC)`·`BitShares(BTS)` |
| 예금 | 투자처 이름(그대로) | `새마을금고` |
| 부동산 | `단지 평형`(그대로) | `헬리오시티아파트 30평대(국평)` |

- 대상이 이미 가진 칸(주식 `market`·`symbol`, 코인 `symbol`)으로 만든다 — 저장한 비교의 조건(`saved_comparison.condition`)·비교 경로 응답은 바뀌지 않는다. 이 반복 전에 저장한 비교도 불러오면 티커가 붙는다
- 코인 검색 결과 줄(`components/crypto/CoinSearch`)의 맨 앞 이름도 `coinNameWithSymbol`이다 — 비교 화면과 가상자산 메뉴가 같은 부품이다. 줄 오른쪽 `심볼 · 통화 #순위`는 그대로
- 최종 지표 막대(`CompareMetricBars`)의 이름 칸은 줄임(…)이 그대로이고 `title`에 전체 이름을 단다

## 12. 상장일 (반복 2026-10-10f — FR-033)

| 칸 | 꼴 | 뜻 |
|----|-----|-----|
| `stock.first_trade_date` | `DATE NULL`(새 열 — Alembic 리비전 하나) | Yahoo 차트 `meta.firstTradeDate`(초)를 **거래소 시간대**(`zoneinfo` — 014 R14-3)의 날짜로. 표시 전용 — 시작일 하한(`first_available_date`)·시작일 판정과 별개 |
| 검색 행 `firstTradedOn` | 날짜 \| `null` | `/api/stocks/search`·`/api/stocks/search/external`의 행마다 — 그 시세 식별자(`market`·`symbol`)의 `stock.first_trade_date`. 종목이 없거나 모르면 `null`. 검색은 출처를 부르지 않는다 |
| 검색 행 `listedOn` | 그대로 | 키움 국내 상장일(시작일 하한 — 006 FR-005a). 미국은 늘 `null`(목록에 칸이 없다) |
| 코인 검색 행 `firstAvailableDate` | 그대로 | 수집으로 알게 된 첫 일봉(007 R7-10) |
| 고른 대상 `listing` | `{ date, basis }` \| `null` | (반복 2026-10-10g — FR-034) `GET /api/stocks/listing-date`·`/api/crypto/listing-date`의 본문. `comparison.listing`과 같은 규칙·같은 글자. 저장하지 않는 파생 값(주식의 첫 거래일 채우기 말고) |
| `comparison.listing` | `{ date, basis }` \| `null` | 비교 블록. 주식 `listing`(키움 `listed_on`) → `first_trade`(`stock.first_trade_date`) → `null`, 코인 `first_bar`(`crypto_coin.first_available_date`) → `null`. 예금·부동산 블록은 `null` |

- **쓰는 때**: 비어 있을 때만 쓰고 덮어쓰지 않는다(출처가 다른 날짜를 주어도 — 개정은 남기지 않는다, 표시 전용)
  - 등록(`POST /api/stocks/selection`): 그 종목의 `first_trade_date`가 없고 **앱 수명주기의 공유 시세 클라이언트가 있으면** 차트 `range=1d`의 `meta`만 한 번 받는다 — Yahoo 관문, 짧은 시간 초과
    (설정), 실패·시간 초과·`firstTradeDate` 없음이면 비워 둔 채 등록을 마친다. 등록 응답은 바뀌지 않는다
  - 주식 수집(`worker/stock_runner.collect_range`): 청크 응답의 `ChartData.first_trade_date`가 있고 종목의 값이 비었으면 쓴다 — 추가 요청 없음
  - 투자 비교(`routes/comparison._stock_listing` — 주식 일시금·적립식): 상장일을 낼 때 키움 상장일이 없고 모르면 등록과 같은 규칙으로 한 번 받는다(사용자 보고 2026-10-10 — 저장한 비교는
    등록을 거치지 않는다)
  - 고른 대상의 상장일(`GET /api/stocks/listing-date` — 반복 2026-10-10g): 투자 비교와 같은 규칙 — 서비스 `stock_selection.stock_listing` 하나를 두 경로가 함께 쓴다
- **고르기 규칙**(순수 함수 하나 — `simulation/listing_date.py`): 주식 `(listed_on, first_trade_date) → listing | first_trade | None`, 코인 `first_available_date → first_bar | None`
- **화면**: 검색 결과 줄은 기준을 밝힌 날짜 — 주식 `listedOn`이면 `상장 YYYY-MM-DD`, 없고 `firstTradedOn`이면 `첫 거래 YYYY-MM-DD`, 코인 `firstAvailableDate`면 `첫 일봉 YYYY-MM-DD`(없으면 그 글자를 뺀다 —
  T158: Yahoo 첫 거래일은 출처의 시세 시작일이라 오래된 종목은 상장일보다 늦다). 비교 표는 `comparison.listing` — 열은 `method`가 일시금·적립식일 때만. (반복 2026-10-10g) 메뉴의 고른
  줄은 종목명 밑에 같은 글자, 모르면 `상장일 —`(고른 대상 `listing` — 대상이 바뀔 때·그 결과나 시작 가능 날짜 안내가 올 때 묻는다)

## 13. 투자 성과표의 처음 단위 (반복 2026-10-11 — FR-035, 화면 상태 — 저장하지 않음)

| 스토어 | 칸 | 처음 값 | 첫 표 요청 |
|--------|----|---------|------------|
| `stores/fxWorkspaceStore.ts` | `period` | `monthly`(전 `daily`) | `/api/fx/daily?currency=USD&period=monthly`(외환은 늘 `period`를 싣는다) |
| `stores/stockStore.ts` | `tablePeriod` | `monthly`(전 `daily`) | `/api/stocks/simulation?…&period=monthly`·`/api/stocks/recurring-simulation?…&period=monthly` |
| `stores/cryptoStore.ts` | `tablePeriod` | `monthly`(전 `daily`) | `/api/crypto/simulation?…&period=monthly`·`/api/crypto/recurring-simulation?…&period=monthly` |
| `stores/compareDetailStore.ts` | `period`(닫힘 상태 `CLOSED`) | `monthly`(전 `daily`) — 열 때마다 | 주식·가상자산(`pageable`)만 메뉴 표 경로 + `&period=monthly`. 예금·부동산은 그대로(`period` 없음) |

- `lib/tablePeriod.periodQuery`는 그대로다 — 일이면 싣지 않는다(서버 기본이 일). 이어 받기는 `&before=…` 뒤에 붙는다(지금과 같다)
- 시계열 요청(`/series`)·보드·차트·이력 조건(012)은 단위와 무관하다 — 이력 식별자·저장 조건에 단위가 없다
- 대상 밖: `stores/indicatorTableStore.ts`(대시보드 지표 표 — 처음 `daily` 그대로), 예금·부동산 스토어(단추 없음)

## 14. 비교 블록의 현재 가치 선 (반복 2026-10-11b — FR-036, 저장하지 않음)

| 칸 | 꼴 | 뜻 |
|----|-----|-----|
| `comparison.valueLine` | `{ points, afterSaleValue }` | 비교 경로 일곱의 200 응답에만. 메뉴 응답·`series`·`summary`·`lineEnd`와 블록의 다른 칸은 그대로 |
| `valueLine.points[]` | `{ date, value }` — `value`는 소수 문자열(원) | `series.points`와 **같은 날짜·같은 차례로 하나씩**(다운샘플링 뒤의 그 날). 그 날의 원화 총자산 = 비교 표 "현재 가치"와 같은 뜻 |
| `valueLine.afterSaleValue` | 소수 문자열 \| `null` | 기준일에 판다고 가정한 금액 = `principal.krw` + 매도 후 투자 수익(`comparison.profit`). `mainBasis`가 `after_sale`일 때만 — 아니면 `null`(`lineEnd.afterSaleReturnRate`와 짝) |

- **값의 출처**(계산하지 않고 이미 낸 값에서 고른다 — 원칙 VI):

  | 방식 | 점의 `value` | 점 `balance`와 같은가 |
  |------|--------------|------------------------|
  | 주식 일시금 | 그 날 마지막 행의 KRW 원금 + 투자 수익(`fx_convert.evaluate_krw` — (잔고 + 예수금) × 매매기준율) | 아니다 — 점 `balance`는 보유분만(`balance_krw`) |
  | 가상자산 일시금 | 그 날 행의 KRW 원금 + 투자 수익(같은 함수 — 매수 뒤 남은 현금 포함) | 아니다 — 같은 까닭 |
  | 주식·가상자산 적립식 | 점 `balance`(원화 총자산 — 잔고 + 매수 대기금 + 배당 현금, 011) | 같다 |
  | 정기예금 | 점 `balance`(그 날 잔고) | 같다 |
  | 정기 적금 | 점 `balance` | 같다 |
  | 부동산 | 점 `balance`(그 달 평가액) | 같다 |

- 마지막 점이 기준일이면 그 `value`는 `comparison.currentValue`와 같은 글자다(같은 값에서 고른다). 마지막 점이 기준일보다 앞이면 화면이 기준일의 `currentValue`까지 잇는다(수익률 선의 `lineEnd`와 같은 자리)
- 화면 타입은 `ComparisonBlock.valueLine?`(선택 키 — 014 전 응답 모양의 대역은 키가 없고, 그러면 현재 가치 선을 그리지 않는다)

## 15. 수익률 그래프의 확대 상태 (반복 2026-10-11b — FR-037, 화면 상태 — 저장하지 않음)

| 상태 | 칸 | 보이는 것 | 다음 |
|------|----|-----------|------|
| `idle` | — | 처음 범위(`fitContent`), 단추 없음 | 누름(날짜 앎) → `picking` |
| `picking` | `start`(날짜 글자) | 오른쪽 위 `시작 YYYY-MM-DD · 끝 지점을 누르세요` + [취소] | 다른 날 누름 → `zoomed`(`setVisibleRange`), 같은 날·[취소]·Esc → 앞 상태(`idle` 또는 `zoomed`) |
| `zoomed` | `from`·`to`(앞뒤 정렬, 양 끝 포함) | 두 날 사이, 오른쪽 위 [리셋] | 누름 → `picking`(더 확대), [리셋] → `idle`(`fitContent`) |

- 차트를 다시 만들면(시계열·대상·이력 항목·테마가 바뀜) `idle`이다 — 훅이 차트를 만드는 효과와 같은 의존성으로 상태를 비운다
- 누름은 차트 칸의 DOM 이벤트다(잡기 단계). 누른 자리의 날짜는 커서 추적(`subscribeCrosshairMove`의 `time`)이 마지막으로 준 값이고, 커서가 칸을 떠나면 비운다(날짜를 모르면 누름을 무시한다).
  커서를 쫓지 않는 이력 수익률 비교는 누를 때 `timeScale().coordinateToTime(화면 x − 칸 왼쪽)`으로 묻는다(왼쪽 가격 축이 없다).
- 고르는 동안의 Esc는 `window` 잡기 단계에서 받아 전파를 멈춘다 — 고르기만 취소하고 투자 비교 모달(`document`의 Esc)은 닫지 않는다.
  눌렀다 뗀 사이 4px 넘게 움직이면 끌기(라이브러리의 옮기기)라 누름이 아니다
- 순수 규칙(`lib/chartZoom.ts`): 두 날 정렬, 같은 날 판정, 끌기 판정(거리), 상태 전이

## 16. 확대 구간의 일 단위 자료 (반복 2026-10-11c — FR-038·FR-039, 저장하지 않음)

| 칸 | 꼴 | 뜻 |
|----|-----|-----|
| 질의 `viewFrom`·`viewTo` | 날짜 둘(둘 다 또는 둘 다 없음, `viewFrom` ≤ `viewTo`) | 주식·가상자산 시계열 경로 여덟(메뉴 넷·비교 넷). 계산 구간은 그대로, 점만 그 구간 ∩ 계산 구간의 시세일마다 |
| 구간 점(주식 일시금) | 시계열 점 그대로의 꼴 | 그 날 `rows`(월·사건 행)가 있으면 그날의 마지막 행(원래 점과 같은 값), 없으면 `daily`의 그날 행을 `convert`(일자별 표 "일" 행과 같은 상태) |
| 구간 점(주식 적립식) | 같은 꼴(+ `principal`) | 그 날 `views`가 있으면 그날의 마지막 보기, 없으면 `daily`의 그날 행을 `view_of` |
| 구간 점(가상자산) | 같은 꼴 | 일봉 그대로(`daily` — 원래 시계열이 줄이기 전의 점) |
| 구간 `gaps` | 지금과 같은 꼴 | 그 구간에서 다시 판정(휴장 잇기·미수집·출처 결측) |
| 비교 `valueLine` | 지금과 같은 꼴 | 같은 구간 점마다 — 주식 일시금은 그 날 상태의 원화 원금 + 투자 수익 |

- 화면 상태(그래프 부품 안 — 스토어에 두지 않는다): `detail = { range, data }`(받은 구간과 그 자료) · `detailState`(`loading`·`failed`·`ready`) · 요청 차례 번호. 확대 상태(15)의 `zoomed`와
  함께 산다 — 받은 자료로 다시 그려도 `zoomed`를 비우지 않는다. 시계열·대상·테마가 바뀌거나 [리셋]이면 `detail`을 버린다
- 끼워 그리기(`lib/chartDetail` — 순수): 원래 점 가운데 [from, to] 밖의 점 + 받은 점(날짜 차례), `gaps`는 원래 것과 받은 것을 합친다(같은 구간은 한 번). 비교의 `valueLine.points`도 같은 규칙
- 확대 단추 자리: `{ right: 오른쪽 가격 축 폭 + 8, top: 4 }`(px) — 축 폭은 처음 누를 때 `priceScale("right").width()`로 잰다

## 17. 기준금리 결정 (반복 2026-10-11d — FR-040~FR-043)

새 테이블 셋 — Alembic 리비전 하나(`down_revision = "a6c2e8f41b93"` — 주식 첫 거래일). 시각은 UTC `TS`, 열거형은 비원생이다. 금리는 `Numeric(8, 4)`(출처는 소수 둘째 자리 — 넉넉히 넷).

### 17.1 `policy_rate_decision` — 결정 이력(정규화)

| 열 | 형 | 제약 | 뜻 |
|----|----|------|----|
| `id` | BIGINT | PK | |
| `bank` | VARCHAR(8) | NOT NULL | 은행 id(`fed`·`bok`·`ecb`·`boe`·`boj` — 17.4) |
| `decided_on` | DATE | NOT NULL | 결정일 — 출처 시각(`localTradedAt`, 한국 시각)의 **한국 날짜** |
| `announced_at` | TS | NULL | 발표 시각(UTC). 출처의 자리 표시 시각(`23:59:59`)이면 NULL — 시각을 만들지 않는다 |
| `rate` | Numeric(8, 4) | NOT NULL | 결정한 금리(%). 마이너스 가능(일본 2016 −0.10) |
| `source` | VARCHAR(32) | NOT NULL | `naver_standard_interest` |
| `ingested_at` | TS | NOT NULL | 처음 저장한 시각 |

- UNIQUE(`bank`, `decided_on`) — 멱등 저장(새 날만 넣는다). 이미 있는 날의 금리가 다르면 **덮지 않고** `policy_rate_revised` 사건(17.5)
- 동결도 결정이다. 발표 전 행(`isRelease:false`·`closePrice:"-"`)은 넣지 않는다
- 같은 응답에 같은 `decided_on`이 둘: 금리가 같으면 하나(실제 시각 행 — 자리 표시 행보다 먼저), 다르면 그 날을 넣지 않고 `policy_rate_conflict`
- 전회대비는 저장하지 않는다 — 조회 때 같은 은행의 직전 `decided_on` 행과의 차이(`simulation/policy_rate`)

### 17.2 `policy_rate_raw` — 원본 응답(본문만)

| 열 | 형 | 제약 | 뜻 |
|----|----|------|----|
| `id` | BIGINT | PK | |
| `kind` | Enum(`list`·`calendars`) | NOT NULL | 목록 · 결정 이력 쪽 |
| `bank` | VARCHAR(8) | NULL | `calendars`의 은행 |
| `page` | INT | NULL | `calendars`의 쪽 |
| `body` | MEDIUMTEXT | NOT NULL | 응답 본문 그대로 — 요청 주소·머리 없이 |
| `source` | VARCHAR(32) | NOT NULL | |
| `fetched_at` | TS | NOT NULL | |

### 17.3 `policy_rate_bank` — 은행 상태(커버리지)

| 열 | 형 | 제약 | 뜻 |
|----|----|------|----|
| `bank` | VARCHAR(8) | PK | |
| `next_meeting_on` | DATE | NULL | 목록의 `nextReleaseKoreaDate`(한국 날짜). 오늘(한국)보다 이르면 NULL로 둔다 |
| `history_complete` | BOOL | NOT NULL 기본 false | 처음 받기(결정 이력 전부)가 끝났다 — 짧은 쪽까지 받은 뒤에만 true |
| `last_overlap_on` | DATE | NULL | 마지막으로 첫 쪽을 겹쳐 받은 한국 날짜(하루 한 번 규칙) |
| `last_success_at` | TS | NULL | |
| `last_failure_at` | TS | NULL | |
| `failure_kind` | VARCHAR(16) | NULL | contracts A0의 다섯(`connection`·`rate_limited`·`blocked`·`invalid_body`·`not_found`) |
| `failure_message` | VARCHAR(255) | NULL | 본문·머리 없이 |

- 실패는 성공이 지우지 않는다(지표 커버리지와 같다 — T207) — 화면이 시각을 견준다: "받는 중" = 받은 결정이 없고 성공보다 늦은 실패도 없다, "최근 갱신 실패" = 받은 결정이 있고
  `last_failure_at` > `last_success_at`. 목록이 성공한 바퀴에서 할 일이 없는 은행(새 결정도 겹쳐 받기도 없음)도 성공을 남긴다 — 앞 바퀴의 실패가 풀린다

### 17.4 은행 표 (T207 — 지표와 같은 나눔: 도메인 `simulation/policy_rate.BANKS`(id·이름·금리 종류·국기·차례), 출처 국가 코드 `ingestion/naver_rate/banks.py`, 까닭 낱말 `ingestion/news/commentary.BANK_WORDS` — 각각 한 곳)

| id | 출처 `nationType` | 이름(화면) | 금리 종류 | 국기 | 차례 |
|----|-------------------|------------|-----------|------|------|
| `fed` | `USA` | 미국연방준비은행 | 연방기금금리 목표 범위 상단 | 🇺🇸 | 1 |
| `bok` | `KOR` | 한국은행 | 기준금리 | 🇰🇷 | 2 |
| `ecb` | `EUZ` | 유럽중앙은행 | 주요 재융자 금리 | 🇪🇺 | 3 |
| `boe` | `GBR` | 영국은행 | Bank Rate | 🇬🇧 | 4 |
| `boj` | `JPN` | 일본은행 | 단기 정책금리 | 🇯🇵 | 5 |

- 변화 까닭의 은행 낱말(FR-042 — `commentary.BANK_WORDS`) — `fed` 연준·FOMC·파월 / `bok` 한은·한국은행·금통위 / `ecb` ECB·유럽중앙은행 / `boe` 영란은행·BOE·영국 중앙은행 / `boj` 일본은행·BOJ·日銀·일은

### 17.5 수집 사건 (수집 로그 `logs/collection.log` — 표 없음)

| 사건 | 칸 |
|------|----|
| `policy_rate_fetch` | 종류(`list`·`calendars`)·은행·쪽·결과(성공·실패 종류)·행 수 |
| `policy_rate_revised` | 은행·결정일·저장값·출처의 새 값 |
| `policy_rate_conflict` | 은행·결정일·두 값 |

### 17.6 응답 꼴 (contracts A14~A16)

- 칸 행: `bank`·`name`·`flag`·`rateKind`·`rate`(문자열 — `"4.00"`)·`change`(문자열, 첫 결정이면 `null`)·`direction`(`up`·`down`·`flat`·`null`)·`decidedOn`·`announcedAt`(ISO UTC 또는
  `null`)·`nextMeetingOn`·`state`(`ready`·`collecting`·`failed`)·`failure`(`{kind, message, at}` 또는 `null`)·`lastSuccessAt`
- 모달: 칸 행 + `decisions[]`(최신부터 전부 — `decidedOn`·`announcedAt`·`rate`·`change`·`direction`) + `firstDecidedOn`·`lastDecidedOn`
- 변화 까닭: A8과 같은 `items[]`·`failure` + `decisionDate`

## 18. 투자 비교 설정 (반복 2026-10-13 — FR-044·FR-045)

새 테이블 하나 — Alembic 리비전 하나(`down_revision = "e9f3b7c2a4d1"` — 기준금리). 시각은 UTC `TS`다. 012 `history_setting`과 같은 꼴(전역 단일 행)이다.

### 18.1 `comparison_setting` — 투자 비교의 최대 대상 수

| 열 | 형 | 제약 | 뜻 |
|----|----|------|----|
| `id` | SMALLINT | PK, 기본 1 | 늘 1(단일 행) |
| `max_targets` | SMALLINT | NOT NULL | 화면의 더하기 한도 — 2~100. 범위 검증은 서비스(`api/services/comparison_settings`)다 — DB `CHECK` 없음(다른 설정 테이블과 같다) |
| `updated_at` | TS | `server_default now()`, `onupdate now()` | 마지막 저장 시각 |

- 행이 없으면 기본 **20**이다 — 읽기가 행을 만들지 않는다(`history_setting`과 같다). 저장은 `db/dialect.upsert` 한 행(`id = 1`)
- 저장소 `repository/comparison_setting.py` — 읽기(없으면 `None`)·저장(upsert). 기본값·범위는 저장소가 모른다(서비스 한 곳)

### 18.2 규칙 상수 (한 곳씩)

| 상수 | 값 | 자리 | 뜻 |
|------|----|------|----|
| `MIN_TARGETS` | 2 | `api/services/comparison_conditions` | 비교 조건 검증의 아래 끝(013 그대로) |
| `MAX_TARGETS` | **100**(10 → 100) | `api/services/comparison_conditions` | 비교 조건 검증의 위 끝 — **설정 값이 아니다**(FR-045). 저장한 비교가 이 검증을 지난다 |
| `MAX_DEPOSIT_TARGETS` | 5 | `api/services/comparison_conditions` | 예금 투자처 수(013 그대로) |
| `MIN_SETTING`·`MAX_SETTING` | 2 · `MAX_TARGETS` | `api/services/comparison_settings` | 설정의 범위 — 위 끝은 검증의 끝과 같은 상수를 쓴다(둘이 어긋나면 설정한 수만큼 더한 비교를 저장할 수 없다) |
| `DEFAULT_SETTING` | 20 | `api/services/comparison_settings` | 행이 없을 때 |
| `MAX_CONDITION_BYTES` | 65,535 | `api/services/saved_comparison` | 저장할 조건 글(직렬화한 JSON, UTF-8)의 끝 — MySQL TEXT 열의 크기 |

- 설정 값의 형: JSON **정수**만이다 — 불리언(`true`)·소수(`20.5`)·문자열(`"20"`)·`null`은 거절(Python의 `bool`은 `int`의 하위형이라 따로 막는다)

### 18.3 저장한 비교 조건 길이

- `saved_comparison.condition`은 그대로 TEXT(013 스키마 테스트 `("text","NO")` 불변)다
- 서비스가 `validate_condition`의 직렬화 글(`ComparisonCondition.text` — `ensure_ascii=False`)의 UTF-8 바이트를 센다. 65,535를 넘으면 저장소를 부르지 않고 `InvalidComparison("condition: 저장할 조건이
  너무 깁니다 — {N}바이트(65,535바이트까지)")` → 422 `invalid_comparison`
- 현실 크기: 대상 하나 약 80~250바이트(이름·시장·심볼·코인 id·단지 id·면적) → 100개 약 8~25KB(T218에서 잰다). 글자 칸마다 200자(`MAX_TEXT`)까지라 이론상 100개 × 최대 길이는 끝을 넘는다

### 18.4 응답 꼴 (contracts A18)

- `GET`·`PUT /api/comparison/settings` → `{"maxTargets": 20, "defaultMaxTargets": 20, "minTargets": 2, "limitTargets": 100}` — `maxTargets`는 저장된 값(없으면 기본), 나머지 셋은 상수다
  (화면이 범위·안내를 서버 값으로 쓴다 — 화면에 2·20·100을 박지 않는다)

### 18.5 화면 상태 (Zustand — 저장하지 않음)

- `compareStore`: `limit`(설정 값 — 처음은 기본 20), `limitStatus`(`loading`·`ready`·`error`), `loadLimit()`(비교 화면을 열 때마다). 더하기 한도는 `maxTargets(asset, limit)`(예금은 min(5, limit))
- 실행의 차례 한도는 상수다(`lib/concurrency`) — 비교 요청 3·진행 구독 2·확대 구간 요청 3. 설정이 아니다(R14-36)

## 19. 투자 성과표 행의 등락 (반복 2026-10-13b — FR-047·FR-048, 저장하지 않음)

스키마 변경 없음. 메뉴 시뮬레이션 경로 넷(`/api/stocks/simulation`·`/api/stocks/recurring-simulation`·`/api/crypto/simulation`·`/api/crypto/recurring-simulation`)의 표 행에 더해지는 칸이다.
요청마다 계산하고 저장하지 않는다. 투자 비교 모달은 같은 경로를 부른다.

### 19.1 행 키

| 표 | 키 | 가격 |
|----|----|------|
| 주식 일시금·적립식 | `openChange` · `closeChange` | `openPrice`(시작가)·`closePrice`(종가) — 원주가 |
| 가상자산 일시금·적립식 | `openChange` | `openPrice`(시가) |

| 칸 | 꼴 | 뜻 |
|----|-----|-----|
| `…Change` | 객체 \| `null` | 직전 기간 대표값 대비(19.2). 비교 대상이 없으면(계산 기간의 첫 기간·그 가격이 없는 행) `null`, 두 가격 가운데 하나라도 0 이하면 `null`(출처가 비운 값 — T226 실측). **키는 늘 있다**(결측 구간 행 제외) |
| `….comparedTo` | 날짜 `YYYY-MM-DD` | 비교한 대표 행의 날짜 — 표에 보이는 그 행의 날짜다 |
| `….absolute` | `Decimal` 문자열 | 그 행 가격 − 비교 가격(분할을 맞췄으면 맞춘 값). 반올림하지 않는다 |
| `….percent` | `Decimal` 문자열 | `absolute` ÷ 비교 가격 × 100, 소수 둘째 자리(`ROUND_HALF_EVEN` — 외환 표와 같은 `rate_change`). 0 이하 가격이면 등락 전체가 `null`이라 이 칸은 늘 값이 있다(형은 외환과 같게 `null` 허용) |
| `….direction` | `"up"` · `"down"` · `"flat"` | `absolute`의 부호 |
| `….split` | `{"ratio": "10:1"}` \| `null` | 비교 가격을 맞춘 분할·병합의 누적 비율(분자:분모 — 010 `unit_price.split_ratio`와 같은 글자, 013 비교 블록 `unitPrice.split`과 같은 꼴). 맞추지 않았으면 `null`. 가상자산은 늘 `null` |

- 결측 구간 행(`kind: "missing"` — 012)에는 키가 없다(`date`·`dateTo`·`kind` 그대로)
- 다른 키·차례·쪽(`hasMore`·`oldestReturned`)·202·요약·조건·시계열은 그대로다

### 19.2 비교 날짜 — 직전 기간의 대표일

- 행 날짜 `d`가 속한 기간(012 `period_bounds(d, unit)` — 일은 그날, 주는 월~일, 월은 1일~말일)의 **바로 앞 기간들 가운데 시세일이 있는 가장 가까운 기간**의 대표일이다. 대표일은 012 규칙
  그대로(주 = 그 주 ∩ 계산 기간의 금요일 이하 마지막 시세일, 없으면 그 주의 마지막 시세일 / 월 = 그 달 ∩ 계산 기간의 마지막 시세일 / 일 = 그날)
- 계산 기간 안(첫 매수일 ~ 계산 끝)만 본다 — 없으면 `null`(첫 기간)
- 일 단위는 직전 시세일이다 — 가상자산 출처 결측 구간(시세일이 없는 날)은 건너뛴다
- 같은 날짜의 행(사건 묶음)은 같은 비교 날짜·같은 값이다. 기간 사이에 낀 사건 행도 이 규칙이다(그 행이 속한 기간의 직전 기간)
- 순수 함수 하나(`simulation/period_table`)가 시세일 목록·단위·계산 끝으로 날짜 → 비교 날짜를 정한다. `table_rows.table_page`는 **쪽을 자르기 전의 전체 항목**에서 찾으므로 쪽의 마지막 행도
  쪽 너머의 비교 행을 얻는다(추가 질의 없음). 계산은 잘라 낸 쪽의 행(≤ `limit` 200)만이다(R12-7)

### 19.3 가격과 분할 맞춤

- 가격은 그 날짜의 하루 상태(`day_state` — 같은 날 행은 같은 가격)다. 주식 `open_price`·`close_price`(원주가), 가상자산 `open_price`(출처 원값 — 소수 14자리)
- 주식: 효력일이 (비교 날짜, 행 날짜]인 분할·병합이 있으면 비교 가격 × ∏(분모 / 분자) — 소수 6자리 `ROUND_HALF_UP`(010 `split_adjust.PRICE_QUANTUM`과 같다). 효력일이 비교 날짜 당일이면 비교 가격이 이미
  분할 뒤라 맞추지 않는다. 배당은 맞추지 않는다
- 계산 — 새 순수 모듈 `simulation/price_change.py`: 분할 맞춤 뒤 `fx_change.rate_change(current, Quote(compared_to, adjusted))`를 부르고 비율을 붙인다

### 19.4 화면 (형식만)

- 형: `PriceChange`(`comparedTo`·`absolute`·`percent: string | null`·`direction`·`split: { ratio: string } | null`). 네 행 형에 선택 키(`openChange?`·주식은 `closeChange?` — `PriceChange | null`) — 014 전 테스트
  픽스처에 없어도 된다(없으면 "—")
- 기호·색 상수 `lib/changeStyle.ts`(`TONE`·`ARROW` — 외환 `DailyTable`이 쓰던 값을 옮김), 칸 부품 `components/period/PriceChangeCells.tsx`(두 칸 — 형식 함수를 받는다: 주식 `formatRate`, 가상자산
  `formatPrice`)
- 칸 `title` = "{comparedTo} 대비". 분할을 맞춘 칸은 등락폭 뒤에 ✂ 표시 — `role="img"`·`aria-label`·`title` "{split.ratio} 분할 반영 — 직전 값을 분할 비율로 맞춰 견줬습니다"(기호만으로 전하지
  않는다 — 006 FR-041c의 📅와 같은 꼴). 글자는 contracts D20
- 날짜 칸 고정: 네 표의 첫 칸(머리·몸)은 `sticky left-0` + 불투명 배경(행 배경과 같은 색 — 배당락·재투자 행 포함, 블랙 배경은 `.dark` 색 변수)
