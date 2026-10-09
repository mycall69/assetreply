# Research: 014 대시보드

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Date**: 2026-10-09

조사 셋(2026-10-09 실측)을 정리한다:
- Yahoo 차트·spark 엔드포인트로 15개 심볼 탐침
- 뉴스 세 출처의 구조와 robots.txt·약관 확인
- 기존 코드 구조

원본 응답은 저장소 밖의 세션 임시 폴더(`scratchpad/014-yahoo/raw/`, `014-news/`)에 있다. 계약 테스트 픽스처는 구현 때 그 본문을 줄여 `backend/tests/contract/fixtures/market/`·`fixtures/news/`에 옮긴다 — 본문만 옮기고 주소는 옮기지 않는다.

---

## R14-1 지표 출처 — Yahoo 차트(이력)·spark(현재 시세)

**Decision**:
- 환율을 뺀 12개 지표의 일별 이력은 005가 쓰는 Yahoo 비공식 차트 엔드포인트(`/v8/finance/chart/{symbol}`)로 받는다
- 15개 지표의 현재 시세는 같은 호스트의 `/v7/finance/spark` **한 번**으로 받는다(시장 환율 셋 포함)
- 심볼 ↔ 지표 대응은 수집 계층 한 파일(`ingestion/yahoo/market_symbols.py`)에만 둔다(011 `installment_items.py`와 같은 격리)

| 지표 id | 이름 | Yahoo 심볼 | 통화·종류 | 시간대(`exchangeTimezoneName`) | 첫 일봉(실측) | 일봉 수 |
|---------|------|-----------|-----------|-------------------------------|---------------|---------|
| `kospi` | KOSPI | `^KS11` | KRW 지수 | Asia/Seoul | 1996-12-11 | 7,489 |
| `kosdaq` | KOSDAQ | `^KQ11` | KRW 지수 | Asia/Seoul | 2000-10-16 | 6,486 |
| `dow` | 다우존스 산업평균 | `^DJI` | USD 지수 | America/New_York | 1992-01-02 | 8,754 |
| `nasdaq` | 나스닥 종합 | `^IXIC` | USD 지수 | America/New_York | 1971-02-05 | 14,036 |
| `sp500` | S&P 500 | `^GSPC` | USD 지수 | America/New_York | 1927-12-30 | 24,810 |
| `sox` | 필라델피아 반도체 | `^SOX` | USD 지수 | America/New_York | 1994-05-04 | 8,163 |
| `nikkei225` | 니케이 225 | `^N225` | JPY 지수 | Asia/Tokyo | 1965-01-05 | 15,808 |
| `hangseng` | 항셍 | `^HSI` | HKD 지수 | Asia/Hong_Kong | 1986-12-31 | 10,068 |
| `shanghai` | 상해 종합 | `000001.SS` | CNY 지수 | Asia/Shanghai | 1997-07-02 | 7,261 |
| `wti` | WTI 원유 선물 | `CL=F` | USD 선물 | America/New_York | 2000-08-23 | 6,641 |
| `gold` | 금 선물 | `GC=F` | USD 선물 | America/New_York | 2000-08-30 | 6,636 |
| `vix` | VIX | `^VIX` | USD 지수 | America/Chicago | 1990-01-02 | 9,594 |
| `usd` | 달러 | 카드 `KRW=X` | KRW 환율 | Europe/London | (이력은 ECOS) | — |
| `jpy` | 엔(100엔) | 카드 `JPYKRW=X` × 100 | KRW 환율 | Europe/London | (이력은 ECOS) | — |
| `eur` | 유로 | 카드 `EURKRW=X` | KRW 환율 | Europe/London | (이력은 ECOS) | — |

- 15개 모두 HTTP 200이었다. 쿠키·crumb·인증키가 필요 없다(기존 클라이언트와 같은 UA `Mozilla/5.0 (compatible; AssetReplay/1.0)`)
- `/v7/finance/quote`는 401(crumb 필요)이라 쓰지 않는다. `/v8/finance/spark`는 필드가 모자라다(`currentTradingPeriod` 없음)
- `JPYKRW=X`는 **1엔당 원**(8.449)이다. 카드는 100엔당으로 보이므로 `Decimal`로 100을 곱한다(정확 — 반올림 없음). `KRW=X`는 1달러당, `EURKRW=X`는 1유로당이다
- 첫 일봉 날짜는 코드에 두지 않는다. 처음 받는 응답의 `meta.firstTradeDate`로 발견해 커버리지에 기록한다(헌법 도메인 범위). 위 표는 실측 기록일 뿐이다

**Rationale**:
- 사용자가 승인했다(2026-10-09 — 원칙 II 이탈의 확장, plan Complexity Tracking)
- 공식 출처(ECOS·KRX)는 KOSPI·KOSDAQ만 있고, 해외 지수·선물·VIX·장중 값은 무료 공식 API가 마땅하지 않다
- 005가 이미 같은 엔드포인트를 쓰므로 어댑터의 오류 분류·백오프를 함께 쓸 수 있다

**Alternatives considered**:
- ECOS 주가지수(KOSPI·KOSDAQ 일별): 해외 지수가 없다. 한 화면에 출처가 둘이면 장중 값·장 상태 판정이 갈린다
- `range=max`: 일봉을 주지 않고 1mo·3mo로 낮춰 준다(실측) — 버렸다

## R14-2 일봉 백필 — `period1/period2` 2년 청크, 새것부터

**Decision**:
- **청크와 요청 형태**: `interval=1d&period1&period2`로 받는다. 기존 주식과 같은 2년 청크다(설정 `MARKET_CHUNK_DAYS` — 기본 730)
- **청크 차례**:
  - 첫 청크는 **어제(그 시장 현지)에서 끝나는 최근 2년**이다. 그 응답의 `firstTradeDate`로 첫 날을 기록한다
  - 그 뒤 청크는 첫 날까지 거꾸로 받는다
  - 1970년 이전 구간의 `period1`은 음수 epoch다 — 발견한 `firstTradeDate`에서 계산한다(상수를 두지 않는다)
- **지표 사이 순서**: 열두 지표 모두의 최근 청크를 먼저 받고(카드의 전일 종가가 곧 이력에서 나온다 — R14-8), 그다음 남은 백필 청크를 지표마다 돌아가며 받는다
- **이어 받기도 같은 청크 길이로 나눈다**: 앱이 오래 꺼져 있었으면 커버리지 끝에서 현지 어제까지를 2년씩 받는다. 앞쪽부터 받고, 겹침 5일은 첫 청크에만 둔다
- **분량**: 전체는 약 250청크다. 청크 사이 간격(`MARKET_CHUNK_DELAY_MS` — 기본 1500)과 Yahoo 관문(R14-10)을 따르므로 처음 백필은 약 7분이다

**Rationale**:
- 2년 청크는 실측으로 1d다. 재개·멱등 단위로도 작다(한 번에 받으면 S&P 500이 2.6MB)
- 커버리지가 연속 구간 하나(`covered_from`~`covered_through`)라, 새것부터 받아도 구간이 앞으로만 늘고 이어 받기는 뒤로만 는다

**Alternatives considered**:
- 오래된 것부터: 처음 몇 분 동안 카드의 전일 종가가 이력에 없다
- 한 번에 전체: 실패하면 처음부터 다시 받는다

## R14-3 거래일 날짜 — `zoneinfo`로 바꾼다(고정 오프셋 금지)

**Decision**:
- 일봉 시각(UTC epoch)을 그 시장의 현지 날짜로 바꿀 때 `meta.exchangeTimezoneName`(IANA 이름)과 `zoneinfo`를 쓴다
- 응답의 `gmtoffset`(응답 시점의 오프셋 하나)은 쓰지 않는다

**Rationale**: 실측으로 선물·외환 일봉의 시각은 현지 00:00이다(CL·GC는 뉴욕 0시, FX는 런던 0시). 고정 오프셋으로 바꾸면 서머타임이 다른 계절의 행이 하루 앞당겨진다 — 겨울 백필에서 CL=F 4,227/6,641행, FX 3,505/5,966행이 그랬다(실측).
- 기존 주식 파서(`ingestion/yahoo/parse.py`의 `_local_date` — 고정 `gmtoffset`)는 고치지 않는다(FR-026). 주식 일봉 시각은 현지 09:00·09:30이라 한 시간 어긋나도 날짜가 바뀌지 않는다

**Alternatives considered**: 기존 `parse_chart`를 함께 쓴다 — 분할 되살리기(`restore_unadjusted`)와 시가 필수 판정이 지수에 맞지 않고, 날짜 변환도 틀린다

## R14-4 확정·잠정·개정

**Decision**:
- **확정**: 그 시장의 현지 날짜가 지난 날의 종가만 확정으로 저장한다. 오늘(현지)의 봉은 장중에도 응답에 있지만(실측: 개장 3분 뒤 S&P 오늘 봉) 저장하지 않는다 — 원본 응답에는 남는다(007과 같다)
- **값 없는 행**: 종가가 `null`인 행(실측: 1996-12-25·01-01 등 휴일 자리 표시. 지금도 CL 2025-05-26, VIX 2020년 뒤 64행)은 저장하지 않는다(R14-5의 휴장)
- **개정**:
  - 이어 받기는 최근 `MARKET_RECHECK_OVERLAP_DAYS`(기본 5)일을 겹쳐 받는다
  - 겹친 날의 확정 값이 출처에서 바뀌었으면 **덮어쓰지 않는다**. `market_close_revision`에 한 줄(지표·날짜·저장 값·출처 값·발견 시각)을 남기고 `collection.log`에 `market_close_revised`를 쓴다
  - 008은 로그만 남겼다. 이번에는 SC-006("개정 기록 없이 바뀐 사례 0건")을 조회로 확인하려고 표를 둔다
- **저장 시점**: 하루 한 번이다 — 그 지표의 현지 어제가 커버리지 끝보다 뒤일 때만 부른다. 워커가 30분마다 깨어 보더라도 원본 응답은 지표마다 하루 한 줄만 쌓인다

**Rationale**: 원칙 V — 확정 값의 재현성과, 잠정 → 확정 전환의 추적. 장중 봉을 확정 구간에 섞으면 다음 날 값이 바뀐다.

## R14-5 휴장·결측 판정

**Decision**: 커버리지 안의 날에 저장된 값이 없으면 이렇게 판정한다(순수 함수 `simulation/market_gaps.py`).

| 조건 | 판정 | 그래프 |
|------|------|--------|
| 주말 | 휴장 | 점 없음, 선 이어짐 |
| 같은 시장 묶음의 다른 지표가 그 날 값이 있음 | **결측** | 선 끊김 |
| 이웃 두 값 사이가 14일 초과 | 그 사이 평일 **결측** | 선 끊김 |
| 그 밖의 평일 | 휴장 | 점 없음, 선 이어짐 |

- 같은 시장 묶음: `krx`(kospi·kosdaq), `us_equity`(dow·nasdaq·sp500·sox), `cme`(wti·gold)
- 니케이·항셍·상해·VIX는 홀로다 — 이웃 판정만 한다. VIX는 미국 주식 지수와 달력이 거의 같지만, 실측 빈 행(2020년 뒤 64행)이 있어 묶으면 결측을 과하게 낸다
- 묶음 판정은 두 지표의 커버리지가 겹치는 구간에서만 한다(SOX는 1994년부터라 그 전의 다우와 견주지 않는다)
- 14일은 가장 긴 연휴(중국 국경절·춘절 — 주말 포함 9~10일)보다 길다. 9·11 뒤 미국 휴장(6일)은 묶음 모두 비어 휴장이다

**Rationale**: 출처가 휴장일 달력을 주지 않는다. 005는 "커버리지 안 빈 날 = 휴장"으로 두어 결측을 낼 수 없었다. 같은 시장의 다른 지표는 같은 거래소 달력을 따르므로, 한쪽만 비면 출처 결측이다.

**Alternatives considered**: `exchange_calendars` 패키지 — pandas가 딸려 오고 의존성이 무겁다. 거래소 달력의 갱신 책임도 생긴다.

## R14-6 현재 시세 — spark 한 번, 서버 캐시, 단일 비행

**Decision**:
- **받기**: `GET /v7/finance/spark?symbols={15개}&range=1d&interval=1d` 한 번으로 받는다(실측 200·17KB)
- **쓰는 필드**: 심볼마다 차트와 같은 `meta`를 준다
  - `regularMarketPrice`, `regularMarketTime`(epoch), `chartPreviousClose`, `fulldayChange`(가격 − 전일 종가)
  - `currentTradingPeriod.regular{start,end}`, `exchangeTimezoneName`
- **캐시**:
  - 서버 메모리에 `MARKET_QUOTE_CACHE_SECONDS`(기본 30) 동안 둔다
  - 같은 순간의 요청은 한 번만 부른다(단일 비행 잠금 — 탭이 여럿이어도 FR-008)
  - 실패는 `MARKET_QUOTE_FAILURE_CACHE_SECONDS`(기본 10)만 기억한다
- **빠진 심볼**: spark 응답에 없거나 값이 깨진 심볼만 `chart?range=1d&interval=1d`로 따로 부른다. spark 자체가 실패하면(429·5xx) 따로 부르지 않는다 — 한도 신호를 키우지 않는다
- **마지막 성공 값**: 지표마다 메모리에 둔다. 실패하면 그 값과 기준 시각을 "새로 받지 못함"과 함께 보인다(FR-009)
- **저장하지 않는다**: 현재 시세는 DB에 넣지 않는다(시장 환율 포함 — 명확화 2). 잠정 → 확정 추적은 R14-4의 청크 원본·개정 표다(plan Complexity Tracking)

**Rationale**: 15개를 1분마다 따로 부르면 하루 2만 회가 넘는다. spark 한 번이면 같은 상태 판정 입력을 다 준다.

**Alternatives considered**:
- 심볼마다 `chart?range=1d` 15회
- `/v8/finance/spark`(필드 부족)

## R14-7 장 상태·거래일 판정

**Decision**: 순수 모듈 `simulation/market_session.py`. 시장마다 거래 시간표를 두고, 오늘이 거래일인지는 출처의 세션 날짜로 판정한다.

| 시장 키 | 시간대 | 세션(현지) | 비고 |
|---------|--------|-----------|------|
| `krx` | Asia/Seoul | 09:00–15:30 | 출처 regular는 15:00으로 준다(실측) — 믿지 않는다 |
| `tse` | Asia/Tokyo | 09:00–11:30, 12:30–15:30 | 점심 휴장 |
| `hkex` | Asia/Hong_Kong | 09:30–12:00, 13:00–16:00 | 점심 휴장 |
| `sse` | Asia/Shanghai | 09:30–11:30, 13:00–15:00 | 점심 휴장 |
| `us_equity` | America/New_York | 09:30–16:00 | 서머타임은 `zoneinfo` |
| `cboe` | America/Chicago | 08:30–15:15 | VIX 정규 시간 |
| `cme` | America/New_York | 일 18:00 → 다음 날 17:00, 매일 17:00–18:00 쉼 | 18:00 뒤는 다음 거래일. 금 17:00~일 18:00 주말 |
| `fx` | America/New_York | 일 17:00 → 금 17:00(24시간) | 거래일 경계는 출처 일봉의 런던 0시 |

- 상태(spec FR-006):
  - **휴장**: 출처의 `currentTradingPeriod.regular.start`의 현지 날짜가 현지 오늘보다 앞이다. 실측으로 KS11은 한글날에 지난 거래일(10-08) 세션을 가리켰고, 미국은 장 전에 오늘 세션을 가리켰다. 주말도 휴장이다. 선물·외환은 regular가 의미 없다(00:00–23:59) — 시간표의 주말과 아래 "갱신 없는 세션"으로 본다
  - **갱신 없는 세션 = 휴장**(모든 시장, 특히 `cme`·`fx`):
    - 조건: 시간표상 세션 안인데, 값의 시각(`regularMarketTime`)이 **이번 세션 시작보다 앞**이다
    - 판정: 세션 시작 뒤 `MARKET_HOLIDAY_DETECT_SECONDS`(기본 3600)가 지났으면 `holiday`, 그 전이면 `pre_open`이다
    - 근거: 출처가 선물·외환의 세션을 00:00–23:59로 주어 거래소 휴일(성탄절·추수감사절·성금요일)을 알 수 없다. 대신 그날 체결이 없다는 사실로 판정한다
    - 한계: 조기 마감일(예: 마틴 루서 킹의 날 CME 정오 마감)에는 마감 뒤에도 "장중"이다 — 기준 시각이 멈춘 것으로 보인다
  - **개장 전·장중·점심 휴장·마감**: 오늘이 거래일이면 지금 현지 시각을 시간표와 견준다
  - `cme`·`fx`처럼 밤을 넘는 세션은 그 세션의 거래일(18:00·17:00 뒤는 다음 평일)로 날짜를 잡는다
- 세션 날짜(`sessionDate`): 값의 시각(`regularMarketTime`)을 위 규칙으로 바꾼 거래일이다. 휴장이면 마지막 거래일이다
- 거래 시간표는 시각뿐이라 날짜 하드코딩 검사(`test_no_hardcoded_dates`)에 걸리지 않는다. 시장 제도가 바뀌면(도쿄 2024-11 15:30 연장 같은) 이 표를 고친다

**Rationale**: 출처가 시장 상태 필드를 주지 않는다(실측). 출처의 세션 날짜는 거래소 달력을 반영하므로 오늘이 휴장인지 알려 주지만, 세션 시각은 틀린다.

## R14-8 전일 종가와 등락

**Decision**:
- **전일 종가**:
  - 기본은 DB에서 읽는다. `sessionDate`보다 앞선 마지막 저장 종가와 그 날짜다(`previous.from = "history"`). 단, 커버리지 끝이 `sessionDate − 1일` 이상일 때만이다 — 이력이 그 날까지 닿아 있어야 한다
  - 이력이 닿지 않으면(처음 백필 전, 하루 이어 받기 전) 출처 값을 쓴다: `regularMarketPrice − fulldayChange`, 없으면 `chartPreviousClose`. 이때 `previous.from = "source"`이고 날짜는 `null`이다. 카드가 "전일 값: 출처(이력에 아직 없음)"을 보인다
  - 실측으로 `000001.SS`의 `chartPreviousClose`는 `0.0002050505`로 깨져 있다. `fulldayChange`로 역산하면 맞다 — 그래서 `fulldayChange`가 먼저다
- **환율 카드**는 늘 출처 값이다(`previous.from = "source_fx"` — 이력이 ECOS라 다른 계열, 명확화 2). 출처의 하루 경계는 런던 0시이고 그 전일 종가는 오늘 시가와 같다(실측). 카드가 "출처 기준 — 런던 0시"를 밝힌다
- **차이·등락률**:
  - 차이 = 값 − 전일 종가, 등락률 = 차이 ÷ 전일 종가(`Decimal`, `quantize_rate`와 같은 자리)
  - 전일 종가가 0 이하이면 등락률은 `null` + `rateBlank: "non_positive_base"`다
  - 휴장이면 값 = 마지막 거래일 종가, 전일 = 그 전 거래일 종가(같은 규칙)

**Rationale**: FR-005·SC-003(카드의 전일 = 그래프의 같은 날 값)을 구조로 지킨다. 출처의 깨진 값에서도 카드를 지킨다.

## R14-9 지연 표시

**Decision**:
- 장중·점심 휴장에서 `받은 시각 − regularMarketTime`이 `MARKET_DELAY_NOTICE_SECONDS`(기본 180)보다 크면 `delayMinutes`(내림)를 낸다. 화면은 "약 N분 지연"이다
- 장이 닫힌 뒤에는 내지 않는다

**Rationale**: 출처가 지연 여부를 주지 않는다. 실측 지연은 CL·GC 약 10분, VIX 약 15분이었다. 지수마다 지연을 상수로 두면 출처가 바꿀 때 틀린다.

## R14-10 Yahoo 관문 — 주식과 함께 지킨다

**Decision**: `ingestion/yahoo/gate.py`의 `YahooGate`를 둔다(008 `EcosGate`와 같은 꼴 — 이벤트 루프마다 하나).
- 동시 요청 수: `YAHOO_MAX_CONCURRENT_REQUESTS`(기본 2)
- 429를 받은 쪽이 `pause(백오프)`하면 그동안 **모두의 다음 요청**이 기다린다
- 대시보드 클라이언트(`YahooMarketClient`)는 늘 관문을 지난다
- 주식 클라이언트(`YahooStockClient`)에는 **선택 인자** `gate`를 더한다. 기본값 `None`은 지금 동작 그대로다(기존 계약 테스트 불변). 두 곳은 관문을 넘긴다:
  - `lifespan`의 주식 워커 클라이언트
  - 검색 경로의 요청마다 클라이언트
- 주식 수집의 값·차례·청크는 바뀌지 않는다. 관문이 붙어도 바뀌는 것은 동시 요청 수와 429 때 기다림뿐이다

**Rationale**: spec FR-019("같은 출처면 호출 간격·한도를 함께 지킨다")를 지키기 위해서다. 클라이언트마다 세마포어를 따로 가지면 합친 호출을 아무도 보지 않는다(008 R8-6과 같은 까닭).

**Alternatives considered**:
- 대시보드만 따로 늦춘다 — 주식 백필과 겹치면 합이 커진다
- 주식 클라이언트를 대시보드와 함께 쓴다 — 파서·요청 형태가 다르다(R14-3)

## R14-11 수집 워커

**Decision**: `worker/market_worker.py`의 `market_worker_loop`를 `lifespan`의 아홉째 태스크로 둔다. 다른 자산군 워커와 따로다.
- **깨는 때**:
  - `MARKET_COLLECT_INTERVAL_SECONDS`(기본 1800)마다 깬다
  - "다시 시도"(`POST …/collect`)가 이벤트로 곧바로 깨운다
- **한 바퀴**:
  - 지표마다 할 일을 정한다(백필 청크·이어 받기·없음)
  - 다음 차례로 받는다:
    1. 최근 청크가 없는 지표들
    2. 이어 받기
    3. 백필 청크(지표마다 돌아가며)
  - 청크마다 원본 → 종가 → 커버리지 순으로 저장하고 커밋한다(007 `crypto_runner`와 같다)
- **실패**:
  - 커버리지 행에 마지막 실패 시각·종류·문구를 남기고 다음 지표로 간다
  - 한 지표의 실패가 루프를 끝내지 않는다
  - 실패 문구는 `mask_secrets`를 거친다(키는 없지만 같은 관례)
- **점유**: 백엔드가 단일 워커이고(`--workers 1`) 대시보드 수집은 이 루프 하나뿐이라 DB 점유를 두지 않는다. 같은 지표를 동시에 받는 경로가 없다
- **진행**: SSE `GET /api/dashboard/indicators/{id}/progress`가 2초마다 커버리지 행을 읽어 `snapshot`(받은 기간·첫 날·남은 일수), `completed`, `failed`를 보낸다(007 `crypto_progress`와 같다 — 브로드캐스터 없음)

## R14-12 그래프의 단위와 점

**Decision**:
- **묶기**: 순수 모듈 `simulation/indicator_periods.py`가 일·주·월·년을 만든다
  - 주·월은 012 `period_table.period_bounds`(월~일 주, 달력 월)를 그대로 부르고 같은 대표일 규칙(주 = 금요일 이하 마지막 거래일, 월 = 말일 이하 마지막 거래일)을 쓴다
  - 년은 새로 더한다 — 12-31 이하 마지막 거래일
  - `period_table`의 `PeriodUnit`은 고치지 않는다(주식·가상자산 표 경로의 400 검증 불변)
- **점의 칸**:
  - `date`(대표일), `value`(문자열)
  - 대표일이 기간 끝(금·말일·12-31)과 다르면 `shifted: true` → 📅
  - 끝나지 않은 기간이면 `ongoing: true` → ⏳ 끝나지 않은 구간
  - 잠정 점이면 `provisional: true`
- **오늘 잠정 점**:
  - 환율이 아닌 지표는 현재 시세(R14-6 캐시)의 `sessionDate`가 저장된 마지막 날보다 뒤이고 장중·점심 휴장·마감(확정 전)이면, 그 값을 `provisional` 점으로 끝에 붙인다
  - 환율은 외환 이력의 `is_provisional`을 그대로 쓴다(시장 환율을 붙이지 않는다 — 다른 계열)
- **끊김**: R14-5의 결측 구간을 `gaps[{from,to,reason:"missing"}]`로 낸다. 화면은 012·FxChart처럼 구간에서 선을 나눈다. 휴장은 `gaps`에 넣지 않는다(선이 이어진다)
- **점 수**:
  - 단위의 **전체 기간**을 보낸다. `DASHBOARD_SERIES_MAX_POINTS`(기본 30,000)를 넘을 때만 LTTB로 줄인다(`simulation/downsample.lttb` — 실제 점을 고른다)
  - 가장 긴 일 단위(S&P 500 약 2만 5천 점)도 줄이지 않는다
  - Lightweight Charts는 보이는 논리 범위만 그린다. 처음 범위는 화면이 정한다: 일 1년, 주 5년, 월 20년, 년 전체 — 마지막 N점으로 `setVisibleLogicalRange`
- **환율 이력**:
  - 외환의 `repository/fx_rate.series(confirmed_only=False)`와 커버리지를 읽는다
  - 커버리지 밖 구간이 있으면 외환의 지금 경로(`collection_gate.ensure_background_job`)로 수집을 요청하고 202를 준다 — 대시보드가 ECOS를 부르지 않는다(FR-018)
  - 엔은 외환과 같은 100엔 단위다

**Rationale**:
- 2,000점으로 줄이면(외환 메뉴 기본) 일 단위의 최근 1년이 20점 남짓이 되어 단위의 뜻이 사라진다
- 범위마다 다시 받는 방식은 화면의 끌기·확대에 맞춰 범위 구독(`subscribeVisibleLogicalRangeChange`)과 이어 붙이기가 필요해 복잡도가 크다
- 로컬 서버에서 1MB 안팎의 응답은 SC-002(1초)를 지킨다 — quickstart 7에서 잰다

**Alternatives considered**:
- 2,000점 LTTB
- 범위별 지연 로딩
- 서버가 처음 범위만 원해상도, 나머지는 줄임(같은 축에 밀도가 달라 시간 간격이 뒤틀린다)

## R14-13 뉴스 — 세 어댑터

**Decision**: `ingestion/news/`에 출처마다 어댑터 하나와 순수 파서를 둔다.
- HTTP 세션 하나를 `lifespan`이 연다(`NewsClient` — UA·타임아웃·재시도 설정)
- 파서는 표준 라이브러리만 쓴다(`json`, `html.parser`) — 새 의존성 없음

| 칸 | 요청 | 목록 | 칸 |
|----|------|------|----|
| `kr` | `GET https://stock.naver.com/api/domestic/news/list?category=MAINNEWS&page=1&pageSize=15`(내부 JSON API — 화면이 부르는 그 경로. HTML에는 목록이 없다) | "주요뉴스"(`MAINNEWS`), 최신순 | `title`, 언론사 `officeHname`, 시각 `datetime`(`"2026-10-09 22:12:14"` — 오프셋 없는 KST), 링크는 응답에 없어 `https://n.news.naver.com/article/{officeId}/{articleId}`로 만든다 |
| `us` | `GET https://finance.yahoo.com/topic/latest-news/`(SSR HTML) | 주요 목록이 없다 → 그 화면의 최신 목록(`div[data-testid=topic-stream] ul[data-testid=list-ds] > li` 가운데 `div[data-testid=stream-card]`가 있는 것 — 광고 칸 제외) | 제목 `section.story-item a[title]`, 링크 그 `href`(절대, 추적 매개변수 없음), 언론사 `span.publisher`, 시각 `span.published-date`(상대 표기만 — `4m ago`) |
| `jp` | `GET https://finance.yahoo.co.jp/news/headline`(SSR, `window.__PRELOADED_STATE__` JSON) | `mainNewsCategory.news.articles`에서 `title.name == "ヘッドライン"`인 목록, 한 쪽 20개, 시간순 | 제목 `headline`, 언론사 `mediaName`, 링크 `link`(절대), 시각 `createTime`(오늘 `"22:20"`, 지난 날 `"10/8"`), 기준 `pageInfo.currentDateTime`, 유료 `isPaidArticle` |

- **10개**: 같은 기사는 한 번만 센다 — 정규화한 제목(공백 접기)으로 거른다. 실측으로 네이버에 같은 제목이 다른 기사 번호로 두 번 나왔다. 그래서 네이버는 15개를 받아 거른 뒤 10개를 쓴다
- **허용 도메인**: `kr` `n.news.naver.com`, `us` `finance.yahoo.com`, `jp` `finance.yahoo.co.jp`. 그 밖이거나 https가 아니면 그 줄을 버린다(실측 50건 모두 각 도메인)
- **시각**:
  - `kr`: 정확한 KST — UTC로 바꿔 낸다
  - `us`: 글자 그대로(`publishedText`). 칸의 받은 시각이 기준이다
  - `jp`: 오늘이면 `currentDateTime`의 JST 날짜 + 시각(정확), 지난 날이면 날짜만(`publishedDate`). 연도는 기준 날짜에서 추정한다(달이 기준보다 뒤면 지난해)
- **0건 = 실패**(`reason: "parse_empty"` — "읽지 못함"). 구조가 바뀐 신호다(FR-024)
- **요청 머리**: 브라우저형 UA는 필수다. `us`는 aiohttp 기본 UA·`curl`이면 곧바로 429였다(실측). `NEWS_USER_AGENT`(기본은 주식 클라이언트와 같은 꼴), `Accept-Language`는 칸마다(ko-KR·en-US·ja-JP)
- **캐시**: 서버 메모리
  - 성공은 `NEWS_CACHE_SECONDS`(기본 600) 동안 둔다
  - 실패는 `NEWS_FAILURE_CACHE_SECONDS`(기본 60)부터 시작해, 연달아 실패하면 두 배씩 600까지 늘린다(백오프)
  - 칸마다 단일 비행이다. "다시 시도"는 실패 기억이 지난 뒤에만 출처를 부른다 — 남은 시간을 응답에 싣는다
- **경로**: `GET /api/dashboard/news/{kr|us|jp}` 셋이다. 화면은 셋을 동시에 부르고 온 것부터 그린다 — 가장 느린 출처가 다른 칸·카드를 막지 않는다(FR-024)

**robots.txt·약관**(원칙 II — 2026-10-09 확인, plan Complexity Tracking):

| 칸 | robots.txt | 약관 |
|----|------------|------|
| `kr` | stock.naver.com·m.stock.naver.com·n.news.naver.com 모두 `User-agent: *` `Disallow: /` | 네이버 이용약관(policy.naver.com/rules/service.html): 사전 허락 없는 자동화 수단(봇·스파이더·스크래퍼)으로 게시물 수집 금지. 네이버파이낸셜 서비스 이용약관 제10조 ① 6: "동의 없이 API 서버 등에 접근하거나 크롤링 … 정보를 수집 및 이용하는 행위" 금지 |
| `us` | `User-agent: *`에서 `/topic/` 허용(`/xhr`·`/caas/`·`/r/`·`/m/` 금지) | Yahoo Terms(legal.yahoo.com/us/en/yahoo/terms/otos): "access or collect data … using any automated means … for any purpose without our express, prior permission" 금지 |
| `jp` | `User-Agent: *`의 금지 다섯에 `/news`·`/news/headline` 없음 — 허용 | LINEヤフー 共通利用規約 8.3·14: 서비스가 예정한 이용 형태·제공 목적을 넘는 이용 금지(스크레이핑을 직접 언급하지 않음) |

**Rationale**: 사용자가 네 갈래(지표 출처 확장·뉴스 셋)를 모두 승인했다(2026-10-09). 개인 이용 전제의 잠정 결정이다. 요청은 칸마다 10분에 많아야 한 번이다. 저장·재배포는 하지 않고(목록은 메모리에만), 제목·링크만 보이고, 출처를 밝힌다.

**Alternatives considered**(사용자에게 제시함):
- 한국: 언론사 경제 RSS(연합뉴스·한국경제 — 실측 200). 네이버 주요뉴스 편집이 아니다
- 일본: Yahoo!ニュース 경제 RSS(실측 200·50건). finance.yahoo.co.jp가 아니고 헤드라인 편집도 아니다
- 미국: 공개 RSS 없음(실측 404)

## R14-14 화면 경로

**Decision**:
- **대시보드**: `/dashboard`. 최상위 `/`(`app/page.tsx`)는 `redirect("/dashboard")`로 옮긴다(Next 16 `next/navigation` — 서버 컴포넌트에서 307)
- **사이드바·제목**:
  - 사이드바의 선택 판정이 `current.startsWith(href)`라 `href: "/"`면 모든 화면에서 선택된다 — `/dashboard`로 둔다
  - 상단 바 제목 표에 `["/dashboard", "대시보드"]`를 `/`보다 앞에 더한다(지표 화면 `/dashboard/kospi`도 이 줄에 걸린다)
- **지표 화면**: `/dashboard/[indicator]?unit=weekly`
  - 페이지(서버 컴포넌트)가 `params`·`searchParams`(Next 16에서 Promise)를 풀어 클라이언트 부품에 넘긴다 — `useSearchParams`의 Suspense 경계가 필요 없다
  - 단위를 바꾸면 `router.replace("?unit=…", { scroll: false })`
  - 틀린 단위는 `daily`다. 없는 지표는 서버 경로의 404를 받아 "없는 지표" 안내다

## R14-15 화면의 갱신과 오늘 날짜

**Decision**:
- **오늘 날짜**: `Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year, month, day, weekday })`로 만든다. 다음 한국 자정까지의 시간으로 타이머를 걸어 날짜를 바꾼다(FR-002)
- **카드 갱신**:
  - 응답의 `refreshAfterSeconds`(설정 `DASHBOARD_REFRESH_SECONDS` — 기본 60)마다 다시 부른다
  - `document.visibilityState`가 `hidden`이면 멈춘다. `visibilitychange`로 다시 보이면 곧바로 부른다
  - 대시보드·지표 화면의 같은 스토어(`stores/marketQuotesStore.ts`)가 같은 경로를 쓴다 — 머리 값이 카드와 같다(FR-010)
- **뉴스**: 화면을 열 때 한 번 부른다. 칸마다 "다시 시도"가 있다. 자동 갱신은 없다 — 캐시가 10분이라 자동 갱신의 이득이 작다

## R14-16 바뀌는 기존 테스트(예상 — 구현 뒤 실제 실패 목록으로 승인)

| 파일 | 지금 단언 | 바뀌는 까닭 |
|------|-----------|-------------|
| `frontend/tests/Sidebar.test.tsx` | 38 `["대시보드"]`는 링크 아님 · 49 "준비중" 1개 · 57-59 대시보드 `li`의 초점 대상 0 · 68-70 링크 목록에 `/dashboard` 없음 | 대시보드가 링크가 된다(준비중 0개 — `getAllByText`가 던진다) |
| `frontend/tests/noUnbuiltAssetRoutes.test.ts` | 37 `UNBUILT = ["dashboard"]`(경로 폴더가 없어야 함) · 49 링크 목록 · 68 `/\/api\/(compare\|dashboard)\b/` 호출 금지 | `app/dashboard`와 `/api/dashboard` 호출이 생긴다 |
| `frontend/tests/TopBarTitle.test.ts` | 21 `["/", "대시보드"]` · 26-30 링크 메뉴마다 제목 = 이름 | 통과할 것으로 본다(`/dashboard` → "대시보드"). 표가 전체를 고정하면 바뀐다 |

- 백엔드: `lifespan` 태스크 수를 세는 테스트가 있으면 바뀐다(구현 때 확인)
- `YahooStockClient` 기존 계약 테스트는 `gate` 기본값 `None`이라 바뀌지 않아야 한다 — 바뀌면 멈추고 보고한다
