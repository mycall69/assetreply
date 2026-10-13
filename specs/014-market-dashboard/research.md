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
  - 지난 거래일의 **늦은 확정**도 같은 꼴이다(실측 T062 — 2026-10-10 00:42 KST에 받은 ^N225의 10-09 봉이 `close: null`, `regularMarketTime`은 10-09 15:45 JST).
    응답에서 휴일 자리 표시와 구별되지 않아 같은 규칙(저장하지 않음)이고, 다음 현지 날짜의 겹쳐 받기(5일)가 채운다(spec FR-019)
  - 버린 대안: 커버리지 끝을 마지막 값이 있는 날로 당긴다 — 주말·휴일마다 워커 주기(30분)로 같은 청크를 다시 받아 호출이 는다
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
- **마지막 성공 값**: 지표마다 메모리에 둔다. 실패하면 그 값과 기준 시각을 "새로 받지 못함"과 함께 보인다(FR-009). 앱을 다시 띄우면 없다
- **실패 기록**(반복 2026-10-10): 출처 실패는 `collection.log`에 사건 한 줄이다 — 응답 전체 실패 `market_quotes_failed{kind, detail}`, 일부 지표만 실패 `market_quotes_partial{failed: {지표: 종류}}`.
  실패 기억(10초) 안의 재요청은 출처를 부르지 않으므로 남기지 않는다. 성공은 남기지 않는다(30초마다 — 로그가 넘친다)
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
- 429를 받은 쪽이 `pause(백오프)`하면 그동안 **모두의 다음 요청**이 기다린다 — 기다림은 그 요청의 재시도 백오프다(지수 + 지터, 기준 `MARKET_RETRY_BASE_DELAY_MS` 1초:
  1·2·4초 + 0~1초). 카드 경로와 이력 수집 사이에 우선순위는 없다 — 관문을 온 차례로 지난다(spec FR-019)
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

> **반복 2026-10-10b**: 단위(점 묶기)는 차트에서 없어지고 보는 기간 8개(일·주 장중, 그 밖 일봉 전부)로 대체됐다(spec FR-011·FR-012, data-model §5). 점 한도·LTTB(아래)는 그대로이고 주·월 대표일 규칙은 일자별 표로 옮겼다(R14-21).

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
  - 호스트가 정확히 같아야 한다(하위 도메인 불허). 되돌리기를 따라가지 않고, 질의 매개변수는 원문 그대로다(spec FR-022)
- **목록 표지**: `kr` 응답의 `articles` 칸, `us` `div[data-testid=topic-stream]` 안의 `div[data-testid=stream-card]`, `jp` `mainNewsCategory.title.name == "ヘッドライン"`.
  없거나 다르면 `parse_empty`다 — 다른 목록으로 물러나지 않는다(spec FR-020)
- **시각**:
  - `kr`: 정확한 KST — UTC로 바꿔 낸다
  - `us`: 글자 그대로(`publishedText`). 칸의 받은 시각이 기준이다
  - `jp`: 오늘이면 `currentDateTime`의 JST 날짜 + 시각(정확), 지난 날이면 날짜만(`publishedDate`). 연도는 기준 날짜에서 추정한다(달이 기준보다 뒤면 지난해)
    - `currentDateTime`이 없거나 읽을 수 없으면 칸을 받은 시각의 JST가 기준이다
    - 오늘 꼴(`"H:MM"`)인데 기준보다 한 시간 넘게 뒤면 전날이다 — 자정 직후의 쪽에 어제 늦은 시각이 남는다(한 시간은 출처 시계의 작은 어긋남을 오늘로 두는 여유)
- **0건 = 실패**(`reason: "parse_empty"` — "읽지 못함"). 구조가 바뀐 신호다(FR-024)
- **요청 머리**: 브라우저형 UA는 필수다. `us`는 aiohttp 기본 UA·`curl`이면 곧바로 429였다(실측). `NEWS_USER_AGENT`(기본은 주식 클라이언트와 같은 꼴), `Accept-Language`는 칸마다(ko-KR·en-US·ja-JP)
- **응답 머리 한도**: `us` 화면의 `Content-Security-Policy` 머리 한 줄이 약 19.5KB다(실측 T081). aiohttp 기본(8,190바이트)이면 본문 전에 400 오류라 세션을 `max_field_size` 64KB로 연다
- **실패 분류**: 연결 오류·시간 초과·5xx는 한 번 더 시도(기본 2번), 403 `blocked`·429 `rate_limited`는 곧바로, 그 밖의 4xx는 `connection`이다(질의 형식이 바뀌어 거절돼도 같다)
- **실패 기록**(반복 2026-10-10): 출처를 부를 때마다 `collection.log`에 `news_fetch{source, status: ok|failed, items | reason·detail}` 한 줄이다 — 캐시 안의 재요청은 남지 않는다(SC-008 확인 수단)
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

## R14-17 변화 까닭의 시황 출처 (반복 2026-10-10b — 실측 2026-10-10, 사용자 승인 2026-10-10)

**Decision** — 지표마다 출처 하나(갈래 둘):

| 지표 | 출처 | 거르는 낱말(제목) |
|------|------|-------------------|
| KOSPI | 네이버 증권 뉴스 포커스 `sid=401`(시황·전망) | 코스피 |
| KOSDAQ | 같다 | 코스닥 |
| 다우 · 나스닥 · S&P 500 | 네이버 뉴스 포커스 `sid=403`(해외 증시) | 다우·나스닥·S&P 각각 + "뉴욕증시"·"뉴욕 증시" |
| 필라델피아 반도체 | 같다 | 필라델피아·반도체지수·반도체 지수 |
| WTI | 같다 | 유가·WTI·원유 |
| 달러 · 엔 · 유로 | 네이버 뉴스 포커스 `sid=429`(환율) | 달러("원·달러"·"원/달러" 포함) · 엔화·엔저·원·엔·원/엔 · 유로 |
| 니케이 · 항셍 · 상해 · 금 · VIX | Yahoo Finance 종목 뉴스 `/quote/{심볼}/news/`(영어) | 거르지 않는다 — 그 종목의 목록이다 |

- **네이버 뉴스 포커스**(`GET https://stock.naver.com/api/domestic/news/focus?sid=&page=1&pageSize=50&date=YYYYMMDD`)
  - 뉴스 화면 "뉴스 포커스"가 부르는 내부 API다(주요뉴스 `list`와 같은 호스트). `date`(한국 날짜)가 없으면 빈 목록이다(실측 — `enableFallback`도 비었다)
  - 칸: `title`·`subcontent`(요약 — 원문)·`officeHName`(언론사)·`date`(`YYYYMMDDHHMMSS` 한국 시간)·`url`(`https://n.news.naver.com/mnews/article/…` — 허용 호스트 `n.news.naver.com`)
  - 사흘치 실측(10-06~08, 쪽당 50): 401 300개 중 코스피 119·코스닥 58, 403 313개 중 미국 지수 56·유가 17, 429 75개 중 환율 38. 니케이·항셍·상해·금·VIX는 0~2 — 그래서 그 다섯은 Yahoo다
  - 한국 오늘과 어제 두 날짜를 부른다(마지막 세션이 어제 밤인 미국·환율 기사가 오늘 날짜에 실린다)
- **Yahoo Finance 종목 뉴스**: `div[data-testid=news-stream]` 안의 `stream-card` 12개. 제목은 `h3`를 감싼 링크의 `title`, 언론사·시각은 `div.publishing`("Investing.com • 18h ago" — 상대 표기뿐). Latest News(`topic-stream`·`span.publisher`)와 꼴이 달라 파서를 따로 둔다
  - 상대 시각("4m ago"·"18h ago"·"yesterday"·"2 days ago")은 받은 시각에서 빼 게시 시각을 어림한다. 읽을 수 없으면 그 줄은 고르지 않는다
  - 실측: 항셍·원화 목록은 그 시장 기사가 대부분, 원유는 섞임. 니케이·상해·금·VIX도 `news-stream`·12개
- **고르는 규칙**: 게시 시각 ≥ 마지막 세션 날짜(그 시장 현지 0시) — 지난 변화의 기사는 뺀다. 출처 차례로 위에서부터 최대 3개, 같은 제목은 한 번
- **robots.txt·약관**: 네이버 `stock.naver.com` `Disallow: /`(주요뉴스와 같은 이탈 — 약관이 자동 수집 금지), Yahoo `finance.yahoo.com/quote/`는 robots 허용(`/quote/*/earnings/*` 일부만 금지) — 약관이 자동 수집 금지(Latest News와 같다)
- **승인**: 사용자 2026-10-10 — "네이버 + Yahoo 종목"(plan Complexity Tracking)

**Alternatives considered**(사용자에게 제시함 — 2026-10-10): 네이버만(다섯 지표가 늘 "찾지 못함") · Yahoo 종목 뉴스만(한국 지수도 영어) · 변화 까닭 빼기. 그 전(define): 받아 둔 뉴스에서 고르기 · AI 요약 문장. Yahoo!ファイナンス 市況(`/news/category/market`)은 404였다

## R14-18 시가·고가·저가 — 원본에서 되살린다 (반복 2026-10-10b)

**Decision**:
- `market_indicator_daily`에 `open_price`·`high_price`·`low_price`(`DECIMAL(20,6)` NULL) 열을 더한다(Alembic 리비전 하나)
- 새 날은 `parse_daily`가 `indicators.quote[0].open/high/low`를 함께 내고 저장소가 함께 넣는다. 0·null은 NULL이다(옛 일봉 — 0으로 메우지 않는다)
- **이미 저장한 날은 저장해 둔 원본 응답(`market_indicator_raw` — 254개)에서 되살린다**
  - 워커 첫 바퀴 앞에 한 번 돌고 멱등이다(NULL인 날만 채운다)
  - 같은 날이 원본 여럿에 있으면 가장 늦게 받은 원본이다. 원본에 없으면 NULL로 둔다
- 개정 표(`market_close_revision`)는 종가만이다 — 시가·고가·저가는 새 날만 넣고 덮지 않는다(spec FR-017)
- 결측 가드(`test_no_interpolation`)에 걸리는 글자(`backfill`·"이전 값")를 쓰지 않는다 — "되살리기"·"채우기"

**실측(T095 — 2026-10-10)**: 개발 DB 원본 254개(12개 지표 13만 3천여 행)에 시가·고가·저가가 **모두 있다** — 빈 값·0이 0건이다(S&P 500 1927-12-30부터, 니케이 1965-01-05부터). 그래도 빈 값·0을 NULL로 두는 규칙은 지킨다(출처가 바꿀 수 있다).

**Rationale**: 원칙 V가 원본과 정규화를 따로 저장하라는 까닭이 이것이다. 다시 받으면 약 250회·8분이고 출처 부하가 든다.
**Alternatives considered**: 전체 다시 받기 · 열 없이 표에서 원본을 그때 파싱(요청 경로에서 MB 단위 JSON 해석 — 원칙 I)

## R14-19 장중 시세 (반복 2026-10-10b — 실측 2026-10-10, 사용자 승인 2026-10-10)

**Decision**:
- `GET /v8/finance/chart/{symbol}?range=1d&interval=5m`(일) · `?range=5d&interval=30m`(주) — 005 이탈의 같은 엔드포인트, 같은 사용자 에이전트(`ingestion/yahoo/market.py`의 `_USER_AGENT` — 브라우저형 UA로 부르면 곧바로 429였다, 실측)
- 실측(2026-10-10 토요일 03시 KST): S&P 500 1일 79점(10-09 13:30~20:00 UTC — 장 시간만), 5일 66점(10-05~10-09). KOSPI 1일 73점(마지막 세션). WTI 1일 205점(밤 세션 포함). 달러 5일 240점 중 빈 점 24, 엔 1일 288점 중 빈 점 114
- 점은 `{time(UTC), value}`이고 모두 잠정이다. **빈 종가는 건너뛴다**(선을 끊지 않는다 — spec FR-014). 엔은 ×100
- 저장하지 않는다(원본도 — 확정 값의 근거가 아니다)
- 그날의 고가·저가(`meta.regularMarketDayHigh/Low`)는 주지만 시가는 없다 — 표의 오늘 잠정 행의 시가·고가·저가는 "—"로 둔다(D9의 "없으면 —". 고가·저가만 보이면 시가 없는 행이 된다)
- 캐시: 지표·기간마다 메모리 일 60초·주 300초, 단일 비행, 실패 10초 기억. 관문(`YahooGate`)을 함께 지난다
- **승인**: 사용자 2026-10-10

## R14-20 모달 주소 — Next 16 가로채기·병렬 경로 (반복 2026-10-10b — T096 문서 확인 2026-10-10)

`node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/intercepting-routes.md`·`parallel-routes.md`(Modals 예):

**Decision**:
- `app/dashboard/layout.tsx`가 `children`과 `modal` 슬롯을 그린다. `app/dashboard/@modal/default.tsx`는 `null`이다 — 없으면 새로고침 때 슬롯이 404다(문서)
- `app/dashboard/@modal/(.)[indicator]/page.tsx` — 대시보드 안에서 카드(`<Link href="/dashboard/{id}">`)를 누른 부드러운 이동을 가로채 모달을 연다. `(.)`는 슬롯이 아니라 경로 조각 기준이다(`@modal`은 조각이 아니다)
- `app/dashboard/[indicator]/page.tsx` — 새로고침·주소 직접 입력(딱딱한 이동)은 가로채지 않는다. 이 페이지가 **대시보드 + 같은 모달**을 그린다(슬롯은 `default`)
- 닫기: 가로챈 모달은 `router.back()`(문서의 방식 — 뒤로 가기와 같다), 직접 연 모달은 `router.replace("/dashboard")`(앞 쪽이 다른 사이트일 수 있다). 포커스는 그 카드(`[data-indicator]` 안 링크)로 — 013 `SimulationModal`과 같다
- 카드의 주소는 `/dashboard/{id}`(기간 없음 = 1년)다. 기간을 고르면 `router.replace("?range=…", { scroll: false })` — 가로챈 모달 안에서도 같은 쪽에 머문다
- 사이드바(`startsWith("/dashboard")`)·상단 바 제목 판정은 바뀌지 않는다

## R14-21 일자별 표 행 (반복 2026-10-10b)

**Decision**:
- 순수 모듈 `simulation/indicator_table.py`가 012 `simulation/period_table.py`의 기준일(`period_bounds`·`anchor_of`·`is_ongoing`)과 쪽 나누기(`page`)를 부른다 — `period_table`은 고치지 않는다
- 주·월 행:
  - 시가 = 기간 첫 거래일 시가, 고가 = 최댓값, 저가 = 최솟값(값이 없는 날은 빼고 셈 — 모두 없으면 null)
  - 종가 = 대표일 종가, 대비 = 앞 기간 대표 종가와의 차이
- 일 행의 대비는 직전 거래일 종가다. 결측은 일 단위에서 결측 구간 행(`market_gaps`)이다
- 오늘(현지) 잠정 행은 현재 시세 캐시의 값이다. 시가·고가·저가는 출처 meta가 주면 잠정, 없으면 null
- 환율 표는 외환 고시 이력이다. 시가·고가·저가는 null이다
- 쪽: 최신부터 `limit`(기본 30·최대 200), `before`, `hasMore`, `oldestReturned` — 주식 일자별 표(012)와 같다

## R14-22 앞 구간 스크롤 — 한 번 받고 처음 범위만 정한다 (반복 2026-10-10c)

- **결정**: 기간 단추는 **처음 보이는 범위**다(spec FR-011 — 요청 2026-10-10c)
  - 일봉 기간(`1m`~`all`)의 그래프 본문은 **저장된 일봉 전부**다(지금의 `all`과 같은 점) + `windows`(기간 → 시작일 — `simulation/indicator_range.range_start`, `all`은 `null`).
    화면은 같은 본문으로 월~모두를 오간다 — 전환에 요청이 없다
  - 처음 범위는 **점의 차례**로 놓는다 — `timeScale().setVisibleLogicalRange({from: 창 시작 이상 첫 점의 차례, to: 마지막 차례})`. 차례는 휴장을 건너 같은 폭이고, 이 API는
    014 차트 테스트의 모의에 이미 있다(`setVisibleRange`는 없다). 창 안에 점이 없으면 마지막 점들을 보인다
  - 왼쪽으로 끌기·축소는 라이브러리 기본 동작이다. 막대 간격 하한 0.01px(T123)이라 "모두"까지 축소된다
  - 장중: 일 `range=5d&interval=5m`(최근 5세션), 주 `range=1mo&interval=30m`(최근 1개월)을 받는다. `window{from,to}`는 순수 모듈 `simulation/intraday_window.py`가 점의 시장 현지 날짜
    (`market_session`의 시간대 — 환율은 런던 0시 경계)로 가른 마지막 세션(일)·최근 5세션(주)이다. 세션은 점이 있는 날뿐이다
  - 장중 선은 확정 선과 같은 진한 실선이다(명확화 2026-10-10c) — 잠정은 커서 상자·범례로
- **까닭**: 기간마다 자른 점을 받으면 왼쪽이 빈 칸이다(요청의 실패 양상). 기간마다 전부를 다시 받으면 "모두"(약 1MB) 전환마다 0.3초 넘게 걸린다 — 한 번 받으면 전환은 범위만이다.
  S&P 2만 5천 점은 그리기 한도(3만) 안이다
- **출처 한도**: Yahoo 5분·30분 간격은 최근 60일까지다. **T128 실측(2026-10-10 11:4x KST 토요일)** — 같은 엔드포인트·같은 사용자 에이전트로 모두 200:

  | 지표 | `range=5d&interval=5m` | `range=1mo&interval=30m` |
  |------|------------------------|--------------------------|
  | S&P(`^GSPC`) | 391점·빈 종가 0·5세션(10-05~10-09)·34KB | 287점·빈 0·22세션(09-10~10-09)·27KB |
  | KOSPI(`^KS11`) | 361점·빈 0·5세션(10-01~10-08 — 한글날 없음) | 229점·빈 4·19세션 |
  | 달러(`KRW=X`) | 1,440점·빈 179·5세션·115KB | 1,056점·빈 38·22세션·91KB |
  | 엔(`JPYKRW=X`) | 1,440점·빈 138 | 1,056점·빈 31 |

  - 출처 `meta.exchangeTimezoneName`은 지수가 거래소 시간대, 환율이 `Europe/London`이다 — 세션을 그 시장 현지 날짜(`market_session` — 환율은 런던 0시)로 가르는 규칙과 같다
  - 빈 종가는 지금처럼 건너뛴다(`parse_intraday`). 세션은 점이 있는 날뿐이다
- **T124 기간만 읽기**: 그래프 경로가 다시 전부를 읽으므로 빠진다. 결측 판정의 `since`는 함수에 남는다(동등성 테스트는 T132 승인 목록)
- **대안**:
  - 기간마다 받기(지금) — 전환마다 요청, 왼쪽 빈 칸
  - 왼쪽 끝에 닿으면 더 받기(라이브러리 범위 사건 구독·이어 붙이기) — 2만 5천 점이면 한 번에 충분하고, 사건 구독은 기존 차트 모의를 넓혀야 한다
  - 장중을 60일까지 — 환율 5분 간격이 약 1만 7천 점(사용자가 5세션·1개월을 골랐다)

## R14-23 블랙 배경 — 색 변수 재정의 (반복 2026-10-10c)

- **결정**: Tailwind v4는 색을 CSS 변수(`--color-gray-500` 등)로 내보내고 유틸리티(`text-gray-500` 등)가 그 변수를 읽는다. **`.dark` 아래에서 변수를 다시 정의**해 팔레트를 바꾼다
  - 컴포넌트 클래스 글자가 그대로다 → 밝은 화면·014 전 화면 테스트가 그대로다(FR-026)
  - 회색 계열은 뒤집는다(`white` ↔ 아주 어두운 바탕 `#0b0f14` 계열, `gray-50` ↔ `gray-900` 쪽). 강조 색(상승 빨강·하락 파랑·경고 노랑·성공 초록)의 옅은 바탕(`-50`·`-100`·`-200`)은
    어두운 바탕용 값, 진한 글자(`-700`·`-800`·`-900`)는 밝은 글자용 값으로 — 색 뜻(상승 빨강·하락 파랑)은 그대로다. 본문 글자 대비 4.5:1(SC-015)
  - `@custom-variant dark (&:where(.dark, .dark *));` — 변수로 안 되는 곳(그림자·`bg-black/40` 같은 투명도 등)만 `dark:`를 쓴다
  - `<html>`에 `dark` 클래스. `app/layout.tsx`의 `<head>` 인라인 스크립트가 **그리기 전에** 브라우저 저장소(`assetreplay.theme`)를 읽어 단다 — 새로고침에 밝은 화면이 번쩍이지 않는다.
    React가 다시 붙일 때 클래스가 달라 경고가 나지 않게 `<html suppressHydrationWarning>`
  - 상태는 `stores/themeStore.ts`(Zustand) — 처음 값은 스크립트가 단 클래스에서 읽는다. 저장소 읽기·쓰기 실패는 밝게·오류 없음
  - 차트 다섯 종: `lib/chartTheme.ts`의 팔레트(배경·글자·격자·선·잠정 선)를 테마마다 두고, 테마를 효과 의존성에 넣어 **다시 만든다** — `applyOptions`는 005~013 차트 테스트의 인라인 모의에
    없어 실행 중에 쓰면 그 테스트가 깨진다(CLAUDE.md 010 주의). 밝은 팔레트는 지금 선택 값과 같다
  - 가드: `darkPaletteGuard` 테스트가 src가 쓰는 색 유틸리티(`bg|text|border|ring|divide|from|to|fill|stroke` × 색 × 단계, `white`·`black`)를 모두 찾아 `.dark` 블록에 그 변수의 재정의가
    있는지 본다 — 빠뜨리면 그 부품만 밝게 남아 글자가 묻힌다(FR-030 실패 양상, `globals.css`의 옛 주석)
  - 단추: 상단 바 오른쪽 끝(수집 표시기 오른쪽), `role="switch"`·`aria-checked`·이름 "블랙 배경". 상단 바는 `sticky top-0`(스크롤해도 위), 모달(`z-50`)보다 아래다
- **T128(c) 확인(2026-10-10)**: 개발 서버가 내는 `globals` CSS(38.9KB)에서 유틸리티가 변수를 읽는다 — `.text-gray-500 { color: var(--color-gray-500) }`·`.bg-white { background-color: var(--color-white) }`·
  `.bg-amber-50`·`.border-gray-200`·`.text-white`·`.bg-gray-900` 모두 같다(`var(--color-…)` 74곳). 변수는 `@layer theme`의 `:root, :host`에 있다(`--color-gray-500`은 16진수와 `lab()` 두 벌).
  **층 밖(unlayered)의 `.dark` 규칙이 층 안의 `:root` 선언을 이긴다** → `globals.css`의 `.dark { --color-…: … }`로 팔레트가 바뀐다
  - 투명도 변형(`bg-white/95`·`bg-black/40`)은 먼저 값이 박히고 `@supports (color-mix)`에서 변수를 섞는다 — 현대 브라우저는 변수 쪽이다. 막(`bg-black/40`)은 블랙에서도 그대로 어둡게 둔다
  - `@theme inline`인 `--color-background`·`--color-foreground`(이 저장소가 더한 것)는 값이 박힌다 — `:root`의 `--background`·`--foreground`를 `.dark`에서 함께 바꾼다
- **대안**:
  - 컴포넌트마다 `dark:` 변형(수백 곳) — 범위가 크고 밝은 화면 클래스까지 흔든다
  - CSS `filter: invert(1) hue-rotate(180deg)` — 한 줄이지만 차트·상승 빨강·하락 파랑·스크린샷의 색 뜻이 뒤집힌다
  - OS 설정(`prefers-color-scheme`) 따르기 — 사용자가 "처음 밝게, 고르면 기억"을 골랐다(명확화 2026-10-10c)

## R14-24 외환 일자별 표의 등락 (반복 2026-10-10d)

- **결정**: 서버가 `/api/fx/daily` 행마다 등락(`change`)을 `Decimal`로 계산해 싣는다(원칙 VI). 화면은 글자에 기호·색·부호만 입힌다
  - `components/fx/DailyTable.tsx`·`lib/csv.ts`는 이미 `noClientSideFinance` 가드(`Number(`·`parseFloat(`·`parseInt(` 금지)의 대상이다 — 화면 계산이 끼어들면 그 가드가 깬다
- **비교 대상 = 그 쪽의 바로 아래 행**: 일 = 직전 고시일, 주·월 = 직전 주·달의 대표값(`period_page`가 내는 행 — 주식 일자별 표·지표 표의 "전 기간 대비"와 같은 뜻)
  - 쪽의 마지막 행은 `daily_page`가 `hasMore` 판정을 위해 **이미 한 건 더 읽는 행**과 견준다 — 추가 질의가 없다. 그 행이 없으면 저장된 첫 고시라 `null`이다
  - 쪽을 넘겨 받을 때(`before`)도 같은 규칙이라 경계 행이 "—"가 되지 않는다(FR-031 실패 양상)
- **계산 = `/api/fx/latest`의 `_change`를 순수 모듈 `simulation/fx_change.py`로 옮겨 함께 쓴다**(원칙 IV)
  - 같은 반올림(`quantize(Decimal("0.01"))`)이라 요약 칸과 표의 맨 위 행은 같은 두 날이면 같은 글자다
  - `/latest`의 대상 고르기(잠정 값 → 직전 **확정** 값)와 응답 글자는 그대로다. 지금 `_change`는 직전 값이 0이면 `percent`를 `"0"`으로 낸다 — 순수 함수는 `None`을 내고
    `/latest` 경로만 지금 글자(`"0"`)로 바꿔 응답을 지킨다. 표는 `null`("—")이다. 매매기준율이 0 이하인 고시는 실제로 없다(ECOS)
  - 화면 타입은 `LatestChange`를 그대로 두고 `DailyChange`(`percent: string | null`)를 더한다 — 요약 칸(`RateSummary`)의 타입이 흔들리지 않는다
- **CSV는 두 열을 맨 끝(004의 `원래 기준일,진행 중` 뒤)에 붙인다**: 기존 열의 차례가 그대로라 001·004의 머리 테스트(`날짜,…,확정 여부`·`확정 여부,원래 기준일,진행 중` 이어짐)와
  기존에 받은 파일을 읽던 도구가 그대로다. 값은 서버 글자 그대로, 없으면 빈 칸
  - **바뀌는 기존 단언 하나**(apply 중 확인 2026-10-10 — define의 "014 전 테스트 불변" 전제를 고침): `frontend/tests/csv.test.ts`의 "진행 중 여부가 열로 남는다"가 줄 **끝**이
    `예`·`아니오`인지 본다(`/예$/`). 두 열이 뒤에 붙으면 줄 끝이 등락 칸이 된다 → 진행 중 열을 **차례(9번째 칸)**로 보게 고친다 — T144 승인(뜻은 같다: 진행 중 여부가 열로 남는다)
  - 진행 중 앞(확정 여부 뒤)에 끼우면 004 머리 단언(`확정 여부,원래 기준일,진행 중`)이 깨지고 기존 파일 읽기의 열 차례가 바뀐다. 표와 같은 자리(송금 받을 때 뒤)면 001 머리
    단언까지 깨진다. 응답에 `change`가 있을 때만 열을 더하는 조건부 머리는 같은 화면의 파일 모양이 응답에 따라 달라져 고르지 않았다
- **형식**: 등락폭은 매매기준율과 같은 `formatRate`에 ▲/▼(같으면 기호 없이 `0.00`), 등락율은 서버의 소수 둘째 자리 글자에 부호(`+`)와 `%`만. 색은 요약 칸과 같은 빨강·파랑(블랙 배경의
  재정의 값 — R14-23, `darkPaletteGuard`가 지킨다), 같음은 회색
- **대안**:
  - 화면에서 이웃 행으로 계산 — 원칙 VI 위반이고 쪽의 마지막 행이 비교 대상을 몰라 "—"가 된다
  - 늘 직전 고시일 대비 — 주·월 행이 기간의 변화가 아니라 대표일 하루의 변화가 된다. 사용자가 "바로 아래 행"을 골랐다(명확화 2026-10-10d)
  - 쪽마다 직전 행을 따로 질의 — `hasMore`용 한 건이 이미 그 행이라 질의만 는다
  - CSV 두 열을 표와 같은 자리(송금 받을 때 뒤)에 — 기존 열 차례가 바뀌어 001 머리 테스트와 기존 파일 읽기가 깨진다

## R14-25 투자 비교의 티커 표시 (반복 2026-10-10e)

- **결정**: 투자 비교 화면의 대상 이름을 화면의 **한 함수**(`lib/compareCondition.targetName`)에서 만든다 — 이름 자리가 모두 이 함수를 거친다(칩 `TargetChips`, 표·막힘 안내·범례·막대·모달 머리 — `app/compare/page.tsx`의
  `rows`, 저장 목록 `SavedComparisons.targetsText`). 자리마다 붙이면 빠뜨린 자리에서 같은 대상이 다른 이름으로 보인다
  - 주식은 006의 `nameWithCode`(시세 식별자에서 표시 코드로 되돌림 — `.KS`·`.KQ`·`.T` 뗌, 미국 그대로)라 메뉴 검색·고른 종목과 같은 글자다
  - 코인은 `lib/displayCode`의 새 `coinNameWithSymbol` — `${nameKo ?? name}(${symbol})`. 코인 검색 결과 줄의 맨 앞 이름도 이 함수다
- **서버·저장 불변**: 대상 칸에 이미 `market`·`symbol`(주식)·`symbol`(코인)이 있다 — 비교 경로 응답과 저장한 비교의 조건(`saved_comparison`)을 바꾸지 않는다. 이 반복 전에 저장한 비교도 그릴 때
  이름을 만들어 티커가 붙는다(옮기기 없음)
- **코인 검색 부품은 메뉴와 함께 쓴다**(013 R13-9의 같은 부품): 비교 화면만 바꾸는 속성을 두면 같은 코인이 두 화면에서 다른 줄이 된다. 주식 검색이 두 화면에서 이미 `이름(코드)`로 같은 것과
  맞춘다. 줄 오른쪽의 `심볼 · 통화 #순위`는 그대로다 — 007 화면·테스트 불변을 앞세워 심볼이 두 번 보이는 것을 받아들인다
- **최종 지표 막대의 이름 칸**(apply 중 확인 2026-10-10): 막대 줄은 `grid-cols-[10rem_1fr_8rem]`이고 이름이 `truncate`다 — `미국 대형 성장주 뱅가드 ETF(VUG)`(약 200px)는 10rem(160px)을 넘어
  티커가 가려진다. 칸을 넓히면 막대 자리가 줄어 다른 대상과의 견주기가 흔들리므로 줄임은 그대로 두고 `title`에 전체 이름을 단다. 수익률 범례는 `flex-wrap`이라 줄을 바꿔 온전히 보인다
- **화면 읽기 이름**: 같은 함수의 이름이 단추 이름에도 들어간다(`… 빼기`·`… 투자 시뮬레이션`) — 이름이 비슷한 ETF를 화면 읽기로도 구별한다. 014 전 013 테스트가 이 이름으로 단추를 찾으므로
  바뀐다(T152 승인)
- **대안**:
  - 서버가 표시 이름을 낸다 — 비교 경로 응답·저장 조건이 바뀌고, 화면이 이미 가진 칸으로 충분하다
  - 자리마다 티커를 붙인다 — 빠뜨린 자리가 생긴다(실패 양상)
  - 코인 검색 결과 오른쪽의 심볼을 지운다 — 007 메뉴 화면·테스트가 더 바뀐다
  - 화면 읽기 이름은 이름만 둔다 — 보이는 글자와 읽히는 이름이 달라진다

## R14-26 주식·가상자산의 상장일 (반복 2026-10-10f)

- **확인한 사실**(define 2026-10-10):
  - 국내: 키움 목록의 `regDay` → `stock_listing.listed_on` → 검색 `listedOn`(삼성전자 `1975-06-11`)
  - **미국: 키움 미국 목록(`usa10099`)에 상장일 칸이 없다**(원본 칸 `stk_cd`·`stk_nm`·`stk_enm`·`isEtf`·`mkgb`·`upgb`·`stex_tp` — `parse_us`가 `listed_on=None`). 실제 응답에서 VOO `listedOn: null`
  - 일본: 외부 검색 결과(Yahoo)에 상장일이 없다
  - Yahoo 차트 `meta.firstTradeDate`: 주식 어댑터가 `ChartData.first_trade_date`로 읽지만 **저장하지 않는다**. `stock.first_available_date`는 문서상 "시세 출처가 준 시세 시작일"이나 쓰는 곳이 없다.
    삼성전자 픽스처의 `firstTradeDate`(171644400) = 1975-06-11 KST — 키움 상장일과 같다
  - 가상자산: 코인 목록 원본에 상장일·출시일 칸이 없다(007 R7-10). 첫 일봉은 시작일을 그보다 앞으로 잡아 수집했을 때만 기록된다 — 지금 비트코인 `2010-07-18`·이더리움 `2016-03-10`, 대부분 `null`
- **T158 실측**(2026-10-10 21:28 KST — 차트 `range=1d&interval=1d`, 응답 약 1.3KB·0.18~0.48초, 본문 픽스처 `fixtures/stock/chart_meta_{VOO,005930_KS,7203_T}.json`):

  | 종목 | `firstTradeDate`(UTC) | 거래소 시간대 날짜 | 실제 |
  |------|------------------------|--------------------|------|
  | VOO | 2010-09-09T13:30 | 2010-09-09 | 첫 거래일과 같다 |
  | SPY · QQQ · VUG · VGT · XLK | 1993-01-29 · 1999-03-10 · 2004-01-30 · 2004-01-30 · 1998-12-22 | 같음 | 첫 거래일과 같다 |
  | BRK-B · AAPL | 1996-05-09 · 1980-12-12 | 같음 | 첫 거래일과 같다 |
  | 005930.KS · 000660.KS | 2000-01-04T00:00 | 2000-01-04 | **출처의 국내 시세 시작일**(삼성전자 상장 1975-06-11 — 키움) |
  | 7203.T | 1999-05-06T00:00 | 1999-05-06 | **출처의 일본 시세 시작일**(도요타 상장 1949년) |
  | 없는 티커 | 404 `Not Found` | — | — |

  - **결론**: `firstTradeDate`는 "Yahoo가 시세를 가진 첫 날"이다 — 그보다 늦게 상장한 종목만 상장일과 같다. 그래서 화면은 기준을 줄 안에서 밝힌다: 검색 결과 줄 `상장 …`(키움)·`첫 거래 …`(Yahoo)·
    `첫 일봉 …`(코인), 비교 표는 "상장일" 열에 기준 작은 글자와 `title`. 이 반복 전 픽스처 `chart_full.json`의 `firstTradeDate`(1975)는 옛 응답이다 — 지금 출처는 2000-01-04를 준다
  - 시간대: 표의 모든 종목에서 `zoneinfo`(거래소 시간대)와 고정 오프셋(`gmtoffset`)의 날짜가 같았다. 그래도 `zoneinfo`를 쓴다 — 출처가 현지 자정을 주면 서머타임 오프셋 차이로 하루 어긋난다
- **결정**:
  - 고르기: 주식 키움 `listed_on`(기준 `listing`) → `stock.first_trade_date`(`first_trade`) → 없음, 코인 `first_available_date`(`first_bar`) → 없음 — 순수 모듈 `simulation/listing_date.py`
  - 저장: **새 열 `stock.first_trade_date`**(표시 전용). `first_available_date`에 쓰면 `require_start_available`의 `price_start` 거절이 수집 전에 일어나 메뉴의 시작일 판정·거절 날짜가 바뀐다(FR-026)
  - 채우기: (1) 등록 — 모를 때만, `range=1d` 차트 한 번(meta만), 주식 관문(`YahooGate`), 짧은 시간 초과(설정), **앱 수명주기의 공유 시세 클라이언트가 있을 때만**(apply 중 확인 — 등록 경로에 지금 클라이언트가 없다. 새로 만들면
    lifespan 없이 도는 006 등록 테스트가 실제 출처를 부른다), 실패·시간 초과·`firstTradeDate` 없음이면 비운 채 등록 성공(응답 불변) (2) `worker/stock_runner.collect_range` — 청크 응답의 `first_trade_date`가 있고 비었으면 기록(추가 요청 없음)
  - 비었을 때만 쓰고 덮어쓰지 않는다 — 표시 전용이라 개정을 남기지 않는다
  - 검색은 출처를 부르지 않는다 — 검색 응답 둘은 저장된 `stock.first_trade_date`만(`market`·`symbol`로 찾음)
  - **API·화면 칸 이름은 `firstTradedOn`이다**(구현 중 확인 2026-10-10): 출처 칸 이름(`firstTradeDate`)을 그대로 쓰면 005 가드
    `test_layer_boundaries.test_시세_출처_필드명이_어댑터_밖에_없다`(`STOCK_SOURCE_TOKENS`)가 막는다 — 출처 고유 개념이 어댑터 밖으로 새는 것(원칙 II)이다.
    가드를 고치지 않고 이름을 우리 것으로 짓는다 — 키움 상장일 `listedOn`과 짝이다
  - 날짜: 거래소 시간대(`zoneinfo` — 014 R14-3). 주식 어댑터의 지금 변환(`gmtoffset`)을 쓰면 서머타임에 하루 어긋날 수 있다 — T158에서 미국 ETF 몇을 재 견준다
  - 비교 블록: `comparison.listing{date, basis}` — 주식·가상자산 경로 넷(일시금·적립식 × 주식·가상자산)에서 라우트가 가진 종목·코인으로 계산, 예금·부동산 `null`
  - 화면: 비교 표의 상장일 열은 `method`가 일시금·적립식일 때(주식·가상자산)만 — 예금·부동산 표는 그대로
- **사용자 보고(2026-10-10) — 채우는 때 셋째**: 저장한 비교 "미국 주요 레버리지 3개"(TQQQ·QLD·SOXL)를 불러오면 상장일이 모두 "—"였다. 저장한 비교·이력 다시 실행은 등록을 거치지
  않고, 이미 어제까지 받아 둔 종목은 새 수집 청크도 없다 — 등록·청크 두 때가 모두 일어나지 않는다(`collection.log`에 `stock_first_trade` 없음). 그래서 **비교 경로가 상장일을 낼 때도** 키움
  상장일이 없고 모르면 같은 규칙(공유 클라이언트·한 번만·실패 허용)으로 받아 둔다(`routes/comparison._stock_listing`). 고친 뒤 불러오자마자 TQQQ 2010-02-11·QLD 2006-06-21·SOXL 2010-03-11
  — 받아 두면 다시 부르지 않는다
- **대안**:
  - 검색 결과마다 출처를 부른다 — 검색 한 번에 요청 수십 개라 요청 제한(429)이 주식 수집을 막는다
  - 코인 첫 일봉 탐색(이분 탐색 약 13회 × 코인) — 간격 제한(`INVESTING_MIN_INTERVAL_SECONDS`)으로 느리고 출처 부담이 크다
  - `first_available_date` 재사용 — 메뉴의 시작일 판정이 바뀐다
  - 새 출처(CoinMarketCap 등) — 원칙 II 새 이탈
  - 등록을 출처 실패에 묶는다 — 출처가 막히면 종목을 고를 수 없다

## R14-27 고른 종목·코인 줄의 상장일 (반복 2026-10-10g)

- **사용자 보고(2026-10-10)**: 주식 메뉴에서 QLD를 고른 줄("QQQ 2배 프로셰어즈 ETF(QLD) NYSE · USD")에 상장일이 없다. 10f는 드롭다운 결과 줄의 오른쪽 정보 칸에만 넣었고, 고른 줄은
  `StockSearchResult`(시장·심볼·이름·통화)로 그려 상장일 자료가 없다
- **결정**: 고른 대상의 상장일을 읽는 경로 둘(`GET /api/stocks/listing-date`·`/api/crypto/listing-date` — A11)을 두고, 고른 줄을 그리는 검색 부품이 대상이 바뀔 때와 그 대상의 결과가
  올 때 묻는다. 주식 경로는 비교 경로의 헬퍼(키움 → 첫 거래일, 모르면 한 번 받아 둠)를 서비스 `stock_selection.stock_listing`으로 옮겨 함께 쓴다(같은 대상이면 같은 글자)
- **근거**:
  - 고른 줄이 생기는 길이 둘이다 — 등록(`selectStock`)과 이력 다시 실행(`rerunHistory` — 등록 없음, 010). 등록 응답에만 실으면 이력 다시 실행은 늘 빈다(10f의 저장한 비교 결함과 같은 꼴)
  - 코인의 첫 일봉은 실행의 수집이 알게 한다 — 고를 때 한 번만 물으면 처음 고른 코인은 실행 뒤에도 "—"다. 결과가 올 때 다시 묻는다(결과가 비는 것은 묻지 않는다 — 실행마다 한 번). **시작 가능 날짜 안내도 신호다**(구현 중 확인 2026-10-10) — 첫 일봉을
    모르던 코인을 첫 일봉보다 이른 날로 실행하면 수집이 첫 일봉을 알게 한 뒤 결과 대신 안내(`before_listing`)가 온다. 결과만 보면 그 코인은 날짜를 알고도 "—"다
  - 요청은 공통 요청 함수를 직접 부른다(012 이력 클라이언트와 같은 까닭 — 시뮬레이션 응답을 모의한 테스트가 이 요청을 가로채면 무관한 단언이 흔들린다). 화면 테스트는 `tests/setup.ts`
    대역이 답한다(이력·저장한 비교 대역과 같은 틀 — 네트워크 없음)
  - 등록 응답의 `listedOn`(시작일 하한 — 006 FR-005a)은 그대로 둔다 — 첫 거래일을 거기 섞으면 미국 종목의 시작일 안내가 바뀐다
- **대안**:
  - 등록 응답에 `firstTradedOn`을 싣는다 — 이력 다시 실행·코인이 빠지고 등록 응답(A10 — 불변)이 바뀐다
  - 고른 값(`StockSearchResult`·`CoinRef`)에 상장일을 넣는다 — 이력 항목(012 DB)에는 없어 옛 항목이 빈다. 조건 식별자 계산에 섞일 위험도 있다
  - 검색 경로(`/api/stocks/search?q=심볼`)로 다시 찾는다 — 이름·초성 검색이라 심볼 하나를 정확히 고르지 못한다
  - 드롭다운 결과 줄도 종목명 밑으로 옮긴다 — 요청 범위 밖이고 목록 높이가 두 배다

## R14-28 투자 성과표의 처음 단위 월 (반복 2026-10-11)

- **사용자 요청(2026-10-11)**: "외환,가상자산,예금,투자비교의 투자 성과표는 기간 설정이 일,주,월 중에서 기본이 일로 나오는 데 이것을 월로 변경해줘"
- **결정**: 일·주·월 단추가 있는 표 넷(외환 일자별 환율 표, 가상자산·주식 일자별 투자 성과, 투자 비교 모달의 주식·가상자산 표)의 **화면 스토어 처음 값**을 `monthly`로 바꾸고, 비교 모달이
  **열 때의 표 요청에도** 단위를 싣는다(주식·가상자산만). 서버의 기본(`period` 없음 = 일)은 그대로다
- **근거**:
  - 코드에서 단추가 있는 표를 찾았다 — `PeriodTabs`를 쓰는 곳은 외환 화면, `PeriodTableSection`(주식·가상자산 메뉴, 비교 모달 `StockDetail`·`CryptoDetail`)뿐이다. 예금 표(`DepositPerformanceTable`·
    `InstallmentTable`)는 단추가 없고 행이 이미 가입·월·만기·재예치다 — 요청의 "예금"에는 바꿀 것이 없다. 대시보드 지표 표(`indicatorTableStore`)는 투자 성과표가 아니다
  - 주식은 요청 목록에 없지만 함께 바꾼다(권장안) — 가상자산과 같은 부품(`PeriodTableSection`)이고, 비교 모달의 주식 표가 월이 되면 같은 종목이 메뉴(일)와 모달(월)에서 처음 단위가 다르다
  - 비교 모달은 지금 열 때의 표 요청에 단위를 싣지 않는다(`load`가 메뉴 경로 그대로 — 단위는 `setPeriod`·`loadMore`만). 처음 값만 바꾸면 탭은 "월"인데 행은 날마다다(FR-035 실패 양상)
  - 서버 기본을 바꾸지 않는다 — 비교 경로·메뉴 경로의 짝 대조(013 `test_comparison_identity*`), `014-baseline` 기준 스크립트, 서버 테스트가 `period` 없는 요청을 일 표로 본다. 화면만 바꾸면
    응답·계약이 그대로다
  - 단위는 지금처럼 세션 상태다(004·012) — 저장하지 않는다. 처음 값만 바뀌므로 "일"을 고른 사용자의 다시 실행이 그대로다
- **대안**:
  - 서버 기본을 월로 — 응답·계약·대조가 바뀌고 `period=daily`를 새로 싣게 된다
  - 고른 단위를 브라우저에 저장 — 요청은 처음 값이고, 012가 세션 상태로 정했다(저장하면 이력 조건과 섞일 일은 없지만 범위 밖)
  - 주식은 그대로 — 같은 부품·비교 모달과 처음 단위가 갈린다

## R14-29 수익률 추이의 현재 가치 축 (반복 2026-10-11b)

- **사용자 요청(2026-10-11)**: "투자 비교의 수익율 추이 그래프의 왼쪽 Y에는 현재 가치가 표시되도록 해줘"
- **결정**: 투자 비교 수익률 추이(`CompareReturnChart`)에 왼쪽 가격 축을 켜고 대상마다 **현재 가치 가는 선**(1px, 그 대상의 색·선 모양, 원화 축 형식 `axisPriceFormat(0)`)을 그린다. 값은
  비교 경로 일곱이 블록에 더하는 **`comparison.valueLine`**(`points` — `series.points`와 같은 날마다 원화 총자산, `afterSaleValue` — 매도 후 금액)이다. 수익률 굵은 선은 오른쪽 축 그대로다
- **근거**:
  - 지금 차트는 오른쪽 축 하나다(`rightPriceScale`만). 메뉴 성과 추이(`PerformanceChart`)는 잔고 왼쪽·수익률 오른쪽이라, 같은 읽기를 비교 차트에도 준다
  - 시계열 점의 `balance`는 자산군마다 뜻이 다르다 — 주식·가상자산 **일시금은 보유분만의 원화 평가**(`stock_series._one_per_day`의 `balance_krw`, `crypto_series`의 `balance_krw` — 예수금·매수 뒤
    남은 현금 제외), 적립식은 원화 총자산(`recurring_series` — 잔고 + 매수 대기금 + 배당 현금), 정기예금·적금은 잔고, 부동산은 평가액이다. 비교 표 "현재 가치"(`comparison_metrics._current_value`)는
    일시금이면 `totalKrw`(잔고 + 예수금)라 점 `balance`로 그리면 선 끝이 표와 다르다. 일시금의 값은 그 날 마지막 행의 KRW 원금 + 투자 수익(`fx_convert.evaluate_krw`가 이미 낸 수익 —
    (잔고 + 예수금) × 매매기준율 − KRW 원금)에서 고른다 — 새 계산이 아니다
  - 화면이 원금 × (1 + 수익률)로 셈하면 원칙 VI·`compareNoClientFinance` 위반이고, 수익률이 소수 6자리로 잘린 값이라 금액이 원 단위로 어긋난다
  - **매도 후 금액 점**을 함께 둔다 — 오른쪽 축에는 매도 후 수익률 점이 있어 축 범위가 그만큼 넓다. 왼쪽 축에 짝이 없으면 두 축의 비율이 달라 일시금(원금이 같아 금액 = 원금 × (1 + 수익률))의
    두 선이 겹치지 않고 어긋나 보인다. 짝이 있으면 두 축의 최소·최대가 같은 비율로 맞아 겹친다(라이브러리 자동 맞춤이 축마다 같은 여백)
  - 키는 `lineEnd`가 아니라 새 `valueLine`이다 — `lineEnd`를 통째로 견주는 013 단위 테스트(`test_comparison_metrics.py`·`_recurring.py`)가 있다. 블록 전체·키 집합을 견주는 테스트는 없다
  - 메뉴 응답·`series`는 바꾸지 않는다 — 013의 짝 대조(`test_comparison_identity*`)와 `014-baseline` 메뉴 파일이 그대로다. 크기는 대상 10개 × 점 1,000개 이하다(`maxPoints`)
  - 화면 타입은 선택 키(`valueLine?`)다 — 014 전 응답 모양의 화면 픽스처는 키가 없고, 그러면 현재 가치 선을 그리지 않아 기존 비교 차트 테스트의 시리즈 목록이 그대로다
- **대안**:
  - 왼쪽 축을 수익률의 다른 눈금(원금 × (1 + 수익률))으로만 — 적립식(원금이 날마다 다름)·부동산(대상마다 매입가가 다름)에서 선에 맞지 않는 금액을 읽는다. 화면 계산이기도 하다
  - 점 `balance`를 그대로 — 일시금 선 끝이 표 "현재 가치"와 예수금만큼 다르다
  - 메뉴 시계열 점에 `value`를 실음 — 메뉴 응답이 바뀐다(요청 밖)
  - 수익률/현재 가치 전환 단추 — 요청은 왼쪽 축에 함께 보이는 것이다

## R14-30 수익률 그래프의 두 지점 확대 (반복 2026-10-11b)

- **사용자 요청(2026-10-11)**: "모든 수익율 추이 그래프에 2개의 지점을 선택하면 확대가 되도록 해줘. 확대가 된 경우 그래프 오른쪽 위의 리셋 버튼을 누르면 다시 원복 되도록 해야해"
- **결정**: 수익률 선이 있는 세 그래프(`CompareReturnChart`·`PerformanceChart`·`ComparisonChart`)에 공용 훅 하나(`hooks/useChartZoom` + 순수 `lib/chartZoom` + 부품 `ChartZoomControls`)를 단다.
  누름은 **차트 칸의 DOM 이벤트**, 누른 날짜는 이미 쓰는 **커서 추적**(`subscribeCrosshairMove`의 `time` — 마지막 값, 칸을 떠나면 비움), 확대는 **둘째 누름에서만** `timeScale().setVisibleRange`,
  리셋은 이미 있는 `fitContent`다
- **근거**:
  - "모든 수익률 추이 그래프" — 코드에서 수익률 선을 그리는 차트는 셋이다(`createChart`를 부르는 다섯 중 `FxChart`는 환율, `IndicatorChart`는 지표이고 기간 단추·처음 보이는 범위(R14-22)가
    따로 있다). 성과 추이는 네 메뉴와 비교 모달이 같은 부품이다
  - 기존 차트 테스트 17파일의 모의는 `createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`뿐이다(CLAUDE.md 010). `subscribeClick`이나 마운트 때의
    `setVisibleRange`·`subscribeVisibleLogicalRangeChange`를 부르면 그 파일들이 함께 깨진다. 누름 처리에서만 부르면 누르지 않는 기존 테스트는 그대로다
  - 두 번 누르기 — 끌기는 라이브러리 기본 옮기기(`handleScroll`)라 끌어 고르기와 겹친다. 눌렀다 뗀 사이 4px 넘게 움직이면 옮기기로 보고 누름으로 세지 않는다(DOM `click`은 움직여도 온다)
  - 리셋은 처음 범위(`fitContent`)다 — 단계를 기억하면 두 번 확대한 뒤 처음으로 돌아오는 단추가 없다. 리셋은 휠 확대·옮기기도 함께 되돌린다(같은 처음 범위)
  - 첫 지점 표시는 상태 줄 글자만이다 — 세로선을 화면 좌표로 그리면 끌어 옮길 때 자리가 어긋나고, 차트 안 표식(`createSeriesMarkers`)은 모의에 없다
  - 차트를 다시 만들면(시계열·대상·테마) 확대 상태를 비운다 — 새 차트는 `fitContent`로 시작하는데 [리셋]이 남으면 확대된 것처럼 보인다
  - 확대는 화면만이다 — 받은 점(다운샘플링 그대로)을 보인다. 확대 범위로 다시 받으면 요청·응답 계약이 생긴다(범위 밖)
- **대안**:
  - 끌어 고르기(사각형) — 옮기기와 충돌해 옮기기를 끄면 지금의 휠·끌기 탐색이 바뀐다
  - `subscribeClick` — 마운트 때 부르므로 기존 모의가 깨진다(옵셔널 호출로 숨기면 모의와 실제가 다른 길을 탄다)
  - 휠·옮기기를 감지해 [리셋]을 보임 — `subscribeVisibleLogicalRangeChange`(마운트 때)가 필요하다. 요청은 두 지점 확대 뒤의 리셋이다
- **구현 중 정한 것**(T188·T189 준비):
  - 이력 수익률 비교(`ComparisonChart`)는 커서를 쫓지 않는다 — 그릴 때 `subscribeCrosshairMove`를 더하면 그것이 없는 화면 테스트 모의(`CryptoHistoryList`)가 깨진다.
    그래서 **누를 때** `coordinateToTime(화면 x − 칸 왼쪽)`으로 묻는다(왼쪽 가격 축이 없어 칸의 왼쪽 끝이 그래프 칸의 시작이다). 라이브러리는 넣은 점의 날짜 글자(`originalTime`)를 돌려준다
  - 투자 비교 모달은 `document`에서 Esc를 받아 닫는다. 확대 훅이 `window` 거품 단계에서 받으면 모달이 먼저 닫혀, 고르기를 무르려다 결과 화면을 잃는다 — 고르는 동안에는 `window` 잡기
    단계에서 받아 전파를 멈춘다(첫 Esc = 고르기 취소, 다음 Esc = 모달 닫기)
- **터치**: 라이브러리의 터치는 길게 눌러야 커서가 따라온다 — 짧은 탭에 커서 날짜가 없으면 누름을 무시한다(직전 날짜로 고르지 않는다). 개인용 데스크톱 전제이고, 실측(T189)에서 확인만 한다

## R14-31 확대 구간의 일 단위 자료와 확대 단추 자리 (반복 2026-10-11c)

- **사용자 보고(2026-10-11)**: 투자 비교 수익률 추이를 확대한 그림 — "월단위 간격이 자연 스럽지 않아.. 리셋 버튼도 너무 내려와 있어서 숫자를 가리고 있어. 확대해서 월단위 간격으로 보여야
  하면은 월과 월 사이의 데이타를 일단위 데이타로 적용해서 더 자세히 볼 수 있도록 해줘. 주식,가상자산,환율,지수 등 일 단위로 볼 수 있는 모든 그래프에 적용해줘"
- **원인**: 주식 시계열(`stock_series._one_per_day`·`recurring_series.build_stock_series`)은 매달 첫 거래일·사건 날의 행뿐이다(005 — 차트 재료). 라이브러리의 시간 축은 점의 차례로 간격을
  잡아, 확대하면 몇 개의 점이 같은 간격으로 벌어지고 사건 날 눈금(`23일`·`25일`)이 달 사이에 끼어 들쭉날쭉하다. 가상자산·외환은 일봉·고시일 전부지만 길면 2,000점(비교 1,000점)으로 줄인다
- **결정**: 시계열 경로 여덟(주식·가상자산 메뉴 넷·비교 넷)에 **보기 구간 질의**(`viewFrom`·`viewTo`) — 계산은 그대로, 점만 그 구간의 시세일마다. 주식은 일자별 표 "일" 행과 같은
  규칙(`stock_simulation.table`의 `day_state` — 사건·월 행이 있는 날은 그날의 마지막 행, 그 밖은 `daily`의 그날 행을 `convert`)으로 고른다. 화면은 확대가 끝나면 구간을 받아 끼운다 — 주식은
  늘, 가상자산·외환은 받은 자료가 줄여졌을 때만(외환은 이미 있는 `from`·`to`), 지표는 받지 않는다(일봉 전부). 확대 단추는 오른쪽 가격 축 폭(누를 때 `priceScale("right").width()`) + 8px 왼쪽
- **근거**:
  - 날마다의 상태는 이미 있다 — 012의 일자별 표 "일"이 같은 `daily`·`convert`·`view_of`를 쓴다. 새 계산이 없어 원칙 VI·IV를 지키고, 사건 날의 값이 원래 점과 글자까지 같아 끼운 경계에서
    선이 튀지 않는다
  - `end`(계산 끝)를 구간 끝으로 바꿔 부르면 기준일·매도 비용·적립식 분모가 바뀐다 — 보기 구간은 계산과 따로 된 질의여야 한다
  - 질의가 없으면 응답이 지금과 같다 — 013 대조(`test_comparison_identity*`)·`014-baseline`·014 전 테스트가 그대로다. 메뉴 시계열을 늘 날마다로 바꾸면(대안) 모든 차트 응답이 바뀐다
  - 받은 자료로 차트를 다시 만든다 — 분할된 시리즈(결측·잠정 구간마다)의 `setData`를 하나하나 바꾸기보다 같은 그리기 함수로 다시 그리는 편이 단순하다. 확대 상태는 시계열·테마가 바뀔 때만 비우고,
    다시 그린 뒤 `setVisibleRange(받은 구간)`을 다시 놓는다
  - 지표 [리셋]은 `fitContent`가 아니라 그 기간의 처음 보이는 범위(`showWindow`)다 — 기간 단추의 뜻을 지킨다
  - 축 폭은 금액 축(`1,600,000,000`)·수익률 축(`16,000.00`)·환율 축마다 다르다 — 고정값이면 다시 가린다. 누를 때만 재 그릴 때의 모의가 그대로다
- **대안**:
  - 메뉴 시계열을 늘 날마다(줄여서) — 모든 응답·014 전 테스트가 바뀌고, 긴 기간은 여전히 줄인 점이다
  - 확대 구간을 화면에서 메우기(직선 보간) — 원칙 V 위반(지어낸 값)
  - 단추를 그래프 위 머리 줄로 — 그래프마다 머리 줄이 없거나(성과 추이) 늘 빈 자리를 차지한다
  - 지표 장중(1일·5일)까지 확대 — 시각이 초 단위 숫자라 날짜 규칙과 다르고, 이미 5분·30분 간격이다(대상 밖)

## R14-32 기준금리 출처 (반복 2026-10-11d — define 실측 2026-10-11 18:2x KST, T202 다시 잼 18:4x KST, 사용자 승인 2026-10-11)

**Decision** — 네이버 증권 기준금리 화면(`stock.naver.com/market/marketindex/bondAndInterest/standardInterest`)이 부르는 **내부 API** 둘(화면 JS 번들에서 찾음 — 함수 이름 "기준금리 단건 조회"):

- **목록** `GET https://stock.naver.com/api/securityService/marketindex/standardInterest` — 은행 17개의 배열
  - 칸: `nationType`(USA·KOR·EUZ·GBR·JPN·CHN·CAN·AUS·…)·`name`·`reutersCode`(`USFOMC=ECIX`·`KROCRT=ECIX`·`EUECBR=ECIX`·`GBBOEI=ECIX`·`JPINTN=ECIX`)·`closePrice`(`"4.00"`)·`fluctuations`
    (상승 `"0.25"` — 부호 없음, 하락 `"-0.25"`)·`fluctuationsType.name`(RISING·FALLING·UNCHANGED)·`localTradedAt`(한국 시각 ISO — `2026-09-17T03:00:00+09:00`)·`statementSource`(FOMC·
    The Bank of Korea·ECB·Bank of England·Bank of Japan)·`nextReleaseKoreaDate`(`"20261029"` — 한국 날짜. 아르헨티나는 지난 `20250201`을 준다)
  - 실측 값(2026-10-11): 미국 4.00 ▲0.25 09-17 03:00 · 한국 3.00 ▲0.25 08-27 10:00 · 유럽 2.65 ▲0.25 09-10 21:15 · 영국 3.75 0.00 09-17 20:00 · 일본 1.25 ▲0.25 09-18 23:59 — 스크린샷과 같다
- **결정 이력** `GET …/standardInterest/{nationType}/calendars?page=&pageSize=` — 행 `localTradedAt`·`closePrice`·`fluctuations`·`fluctuationsType`·`isRelease`
  - **`pageSize`는 60 이하**다 — 100이면 400 `{"detailCode":"HttpError","message":"Bad Request","result":"getStandardInterestCalendars.pageSize: must be less than or equal to 60"}`
  - **동결 결정도 행이다**(`0.00`·UNCHANGED). 아직 발표 전인 다음 결정이 맨 위에 `isRelease:false`·`closePrice:"-"`로 오기도 한다(KOR 2026-10-22 10:00·EUZ 2026-10-29 22:15 — USA·GBR·JPN은 없다)
  - 깊이: 다섯 모두 **2016-01부터** — USA 87·KOR 91(+ 예정 1)·EUZ 87(+ 예정 1)·GBR 91·JPN 89 행, 은행마다 쪽 60 × 2
  - 시각: 옛 행은 자리 표시 `23:59`(날짜만 안다), 근래는 실제 발표 시각 — FOMC 03:00·04:00, 한은 10:00, ECB 20:45~22:15, BOE 20:00·20:02·21:00, BOJ 11:54·12:19·13:00(모두 한국 시각)
  - 이웃 결정의 차이 = `fluctuations`: USA·KOR·EUZ·GBR 0건 불일치, **JPN 2건** — 2026-09-18이 두 행(11:54·23:59, 같은 1.25)이라 생긴 차이다
- **계열의 뜻**(실제 정책금리와 대조): 미국 2016-01 0.50 = 연방기금금리 **목표 범위 상단**(0.25~0.50). 유럽 2025-06-05 2.15(▼0.25) = **주요 재융자 금리**(그때 예금금리 2.00). 일본 2016 −0.10 =
  마이너스 금리 시기의 단기 정책금리. **유럽 2016-01~03의 0.00은 실제 MRO(0.05 — 2016-03-10에 0.00)와 다르다** — 출처 값 그대로 보이고 고치지 않는다
- **robots.txt·약관**: `stock.naver.com` `User-agent: *` `Disallow: /` — 주요뉴스·뉴스 포커스(R14-13·R14-17)와 같다. 네이버 약관·네이버파이낸셜 약관 제10조 ① 6이 자동 수집을 금지한다 →
  014의 같은 갈래 이탈의 **새 경로**다. T202에서 다시 재고 사용자 승인을 받는다(plan Complexity Tracking)
- 날짜·저장 규칙은 spec FR-040·FR-043, DM17이다 — 결정일 = `localTradedAt`의 한국 날짜, 자리 표시 시각은 NULL, 같은 날 두 행(같은 값 하나·다른 값 충돌), 발표 전 행은 예정

**T202 실측(2026-10-11 18:4x KST — 다섯 은행 전부, 본문은 픽스처 `backend/tests/contract/fixtures/policy_rate/`)**:

| 은행 | 쪽(60) | 결정 행 | 발표 전 행 | 자리 표시 시각(23:59:59) | 같은 날 두 행 | 가장 옛 결정 |
|------|--------|---------|-----------|--------------------------|---------------|--------------|
| 미국 | 2(10,274B·4,621B) | 87 | 없음 | 42 | 없음 | 2016-01-28 0.50 |
| 한국 | 2(10,229B·5,498B) | 91 | 2026-10-22 10:00 | 46 | 2017-05-25(23:59 둘 — 1.25) | 2016-01-14 1.50 |
| 유럽 | 2(10,229B·4,817B) | 87 | 2026-10-29 22:15 | 41 | 2021-09-09(20:45 둘 — 0.00) | 2016-01-21 0.00 |
| 영국 | 2(10,272B·5,326B) | 91 | 없음 | 45 | 2019-05-02(23:59 둘)·2024-02-01(21:00 둘) | 2016-01-14 0.50 |
| 일본 | 2(10,334B·5,018B) | 89 | 없음 | 86 | 2026-09-18(11:54:04·23:59:59)·2026-06-16(12:19·23:59) | 2016-01-29 −0.10 |

- **같은 날 두 행은 여섯 날이고 모두 같은 값이다** — "같은 값은 한 행(실제 시각을 자리 표시보다 먼저)" 규칙이 다 덮는다. 다른 값의 같은 날은 실측에 없다(가공 픽스처로 시험한다)
- 응답 시간은 쪽마다 0.05~0.19초, 목록 18,899B·0.10초. 마지막 쪽 다음은 `[]`(2바이트). 다섯 은행 처음 받기 = 목록 1 + 결정 이력 10회
- 결정 이력의 차례는 최신부터(발표 전 행이 맨 위). 목록의 일본 `localTradedAt`은 자리 표시(`23:59:59`)이고 결정 이력에는 실제 시각 행이 있다 — 결정은 결정 이력에서만 읽는다(목록은 다음 결정일·새 결정 알림)
- robots.txt 다시 확인(18:4x): `User-agent: *` `Disallow: /`

**승인**: 사용자 2026-10-11 — `/speckit-implement` "T202~T212 모두 구현해줘. 선택 해야 하는 항목은 모두 추천값으로 선택해줘."(define·apply 보고에서 이 경로가 원칙 II 새 이탈이고 T202에서 승인받는다고 밝힌 뒤 — 권장안 = 네이버 증권 기준금리 내부 API). plan Complexity Tracking

**Rationale**: 스크린샷의 표(결정일마다·동결 포함·예정 행)를 그대로 만들 수 있는 출처가 이것 하나다. 다섯 은행이 한 꼴·한 출처라 어댑터 하나다.

**Alternatives considered**:
- **ECOS `902Y006`**(국제 주요국 중앙은행 정책금리 — 공식, 같은 인증키): 26개국, **월별**(`CYCLE M` — 일본 194601~·유로 199901~·한국 199905~202607). 결정일·동결 결정·다음 결정일이 없어 "금리 추이"
  표를 만들 수 없고, 한국이 두 달 늦다. 대시보드는 ECOS를 부르지 않는다(FR-018 — 외환 한도)
- **은행별 공식 출처 다섯**(FRED `DFEDTARU`·ECB Data Portal `FM.D.U2.EUR.4F.KR.MRR_FR.LEV`·BOE IADB `IUDBEDR`·BOJ 시계열·ECOS `722Y001`): 꼴 다섯·FRED 키 하나 더, 날마다 수준만이라 동결 결정이
  없다(변한 날만 안다)
- 메모리 캐시만(저장 없음): 출처가 10년만 준다 — 쌓이지 않는다(014 원래 요청 "주요 지표는 로컬 DB")

## R14-33 기준금리의 변화 까닭 — 최근 결정 날의 기사 (반복 2026-10-11d)

**Decision**:
- 출처는 이미 승인된 **네이버 증권 뉴스 포커스**(R14-17의 엔드포인트 — `/api/domestic/news/focus?sid=&page=1&pageSize=50&date=YYYYMMDD`)다. 분류 **404(채권·선물)**를 더한다 — 같은
  엔드포인트의 다른 분류라 새 경로가 아니다(T202에서 함께 밝힌다)
- 날짜는 그 은행의 **최근 결정일(한국)과 다음 날**이다. 분류 차례 404 → 403(해외 증시) → 429(환율)
- 게시 시각이 **최근 결정의 발표 시각 30분 전 이후**인 기사만(시각을 모르면 결정일 0시 이후 — T202 실측으로 더함). 게시 시각을 모르는 기사는 고르지 않는다
- 고르기: 제목에 **은행 낱말**(DM17.4)과 **금리 낱말**(금리·동결·인상·인하)이 **둘 다** 있어야 한다. 분류·출처 차례로 위에서부터 최대 3개, 같은 제목 한 번(`normalize_title`)
- 같은 (분류, 날짜) 응답은 은행 사이에 한 번만 받는다(FOMC·BOE가 같은 날일 때). 메모리 캐시는 지표 까닭과 같은 설정(기본 10분)
- **과거 날짜도 준다**(실측): 2026-08-27·09-17·09-10·2025-12-11 모두 기사가 있다(`articleTotal`은 0으로 오지만 `articles`가 차 있다 — 칸을 믿지 않는다)

**실측(define — 2026-10-11)**: 낱말 하나(금리 낱말)로 세면 결정 날 404·403·429·401에 9~26개가 걸린다. 은행 낱말을 함께 보면:
- 한은 2026-08-27 — 404 "[속보]한은 금리 인상 결정에…"·"한은 '연속 인상'에도 증권가 '점도표 쇼크없다' 안도", 429 "'백투백' 금리 인상한 한은…". 은행 낱말만이면 429 "한은 총재 '환율 아직 높아…'"도
  걸린다(금리 결정 기사가 아니다 — 금리 낱말이 없다)
- FOMC 2026-09-17(한국) — 404 "매파 FOMC에도 국채 단기물 중심 제한적 약세…", 403 "연준 매파 기조에도 코스피 강보합…", 429 "美 금리 인상에 환율 13.6원 급등…"(은행 낱말 없음 → 빠진다)
- **T202 실측(은행마다 최근 결정일·다음 날 × 분류 404·403·429, 같은 (분류, 날짜)는 한 번)**: 은행 낱말 + 금리 낱말로 고른 기사 수 — 미국 8(은행 낱말만이면 11개 더)·한국 11(17개 더)·
  유럽 4·영국 **0**·일본 1("美 압박에 올린 BOJ 금리…" — 429). 영국은 "찾지 못함"이 정상이다(한국 언론이 BOE 동결을 거의 다루지 않는다 — 문장을 만들지 않는다)
- **결정 전 기사는 빼야 한다**: 결정 날 아침의 "금통위 앞두고…"는 결정의 까닭이 아니라 전망이다. 결정의 실제 발표 시각을 알면 **그 시각 이후에 게시된 기사만** 고르고, 시각을 모르면(자리 표시)
  결정일(한국) 0시 이후다. 실측의 고른 기사는 모두 발표 뒤다(한은 10:00 → 10:42·14:48·15:34, FOMC 03:00 → 08:17·09:38·11:59)
- **발표 시각은 어림이다** — 한은 2026-08-27의 출처 시각은 10:00인데 429에 "한은, 기준금리 3%로 연속 인상…"이 09:52다(실제 발표는 그보다 조금 앞). 그래서 기준은 발표
  시각 **30분 전**이다 — 결정 날 아침의 전망 기사(05:51 "한은 오늘 기준금리 또 올릴까…", 전날 "내일 금통위…")는 여전히 빠진다

**Rationale**: 지표의 "마지막 세션 이후" 규칙(R14-17)은 날마다 움직이는 값의 규칙이다. 결정은 몇 주에 한 번이라 그 규칙이면 결정 뒤 며칠이 지나면 늘 "찾지 못함"이다.
**Alternatives considered**: 지표 규칙 그대로(위 까닭으로 버림) · 중앙은행 결정문(통화정책방향·FOMC statement — 출처 다섯·꼴 다섯·영문) · Yahoo 종목 뉴스(금리 심볼이 없다)

## R14-34 계단선과 원칙 V (반복 2026-10-11d)

**Decision**: 금리 모달의 그래프는 **계단선**이다 — 점은 결정일에만 있고(저장된 결정 그대로), 선은 다음 결정까지 수평이다(Lightweight Charts 선 옵션 `lineType: 1` — WithSteps).
- 정책금리는 다음 결정까지 그 값이 **효력**을 갖는다 — 계단은 그 뜻을 그린 것이지 빈 날의 값을 만든 것이 아니다. **날마다의 값을 만들어 저장하거나 응답에 싣지 않는다**(원칙 V — 전일 값 복사 금지와 다르다)
- 스크린샷(네이버)의 결정 점 사이 사선은 결정 사이에 금리가 서서히 변한 것처럼 보이므로 쓰지 않는다
- 점 위의 값 글자는 넣지 않는다 — "모두"(10년 약 90점)에서 겹친다. 커서 상자가 결정일·금리·전회대비다
- 마지막 결정 뒤 오늘까지의 수평 꼬리는 그리지 않는다(마지막 점에서 끝난다 — 받지 않은 날의 값을 만들지 않는다)

**Alternatives considered**: 사선(스크린샷 그대로 — 위 까닭으로 버림) · 날마다 점을 만들어 보냄(원칙 V 위반 소지·점 수 30배)

## R14-35 투자 비교 대상 수 설정의 자리와 서버 끝 (반복 2026-10-13)

**사실**(define 조사 2026-10-13):
- 끝 10은 두 곳에 박혀 있다 — 서버 `api/services/comparison_conditions.MAX_TARGETS = 10`(저장한 비교의 조건 검증 `_targets()` — 2~10개, 예금 ≤5)과 화면 `lib/compareCondition.maxTargets(asset)`(예금 5·나머지 10 —
  `compareStore.addTarget`의 알림·`TargetChips` 안내). 비교 경로 일곱(`/api/comparison/<자산군>/…`)은 대상 하나씩이라 대상 수를 모른다
- 설정 화면(`app/settings/page.tsx`)은 절마다 서버 `GET`·`PUT`이고(스프레드·주식·주식 매도 세금·가상자산·예금·부동산 둘·최근 시뮬레이션 이력 — 이력이 맨 아래 F7), 값은 MySQL 단일 행 테이블이다(012 `history_setting` 등)
- 설정·저장한 비교의 틀린 값은 **422**다 — `InvalidSetting` → `invalid_setting`, `InvalidComparison` → `invalid_comparison`(`api/main.py`). 화면은 저장 실패를 "저장하지 못했습니다 — {서버 메시지}"로 보인다
- `saved_comparison.condition`은 MySQL TEXT(65,535바이트)다. 조건 글은 `json.dumps(…, ensure_ascii=False)`라 한글이 3바이트다. 글자 칸마다 200자(`MAX_TEXT`)까지라 이론상 100개 × 최대 길이는 TEXT를 넘고,
  MySQL 엄격 모드는 넘는 글을 오류(500)로 거절한다. 개발 DB의 저장한 비교는 7개, 가장 큰 것이 대상 8개다

**Decision**:
- 설정은 **로컬 DB 새 테이블 `comparison_setting`**(단일 행)과 설정 화면의 새 절 "투자 비교"(부동산 뒤·이력 앞)다. 행이 없으면 20
- **서버 검증의 끝은 100**(예금 5)이고 설정 값이 아니다. 설정은 화면의 더하기 한도다 — 설정을 낮춰도 저장한 비교를 불러오고·실행하고·다시 저장할 수 있다. 설정의 위 끝(`MAX_SETTING`)은 검증의 끝과 같은 상수를 쓴다
- 설정보다 대상이 많은 저장한 비교는 **자르지 않는다** — 모두 채우고 알린다(더하기만 막는다)
- 저장 길이는 열을 바꾸지 않고 **서비스 가드**(UTF-8 65,535바이트 초과 → 422 `invalid_comparison` 칸 `condition`)다
- 오류 꼴은 기존 둘을 그대로 쓴다(define의 400·`condition_too_long`을 apply에서 422·기존 이름으로 고침 — 새 오류 이름·새 처리기를 만들지 않는다)

**Rationale**: 설정 화면의 다른 절이 모두 서버 값이라 한 절만 브라우저에 두면 혼자 다르다(012가 이력을 브라우저에서 DB로 옮긴 까닭과 같다). 검증의 끝을 설정 값으로 하면 "설정 낮춤 → 저장한 비교 다시 저장"이 막힌다.
TEXT를 MEDIUMTEXT로 바꾸면 013 스키마 테스트(`("text","NO")`)가 바뀌고, 현실 크기(대상당 약 80~250바이트 → 100개 약 8~25KB)는 TEXT 안이다

**Alternatives considered**:
- 브라우저 저장소(테마처럼) — 설정 화면에서 혼자 다르다
- 서버가 설정 값으로 검증 — 설정을 낮추면 다시 저장 불가
- `.env` 설정 — 화면에서 바꿀 수 없다("설정에서"라는 요청과 다르다)
- 기존 `history_setting`에 열 추가 — 뜻이 다른 설정을 섞고 012 스키마 테스트가 바뀐다
- MEDIUMTEXT 마이그레이션 — 위 스키마 테스트, 현실 크기로 필요 없음
- 400 `condition_too_long` — 저장한 비교의 다른 틀린 값(422)과 다르게 보인다

## R14-36 대상이 많을 때의 연결 한도 (반복 2026-10-13)

**사실**(define 조사 2026-10-13):
- 화면은 Next.js 개발 서버를 거친다(`NEXT_PUBLIC_API_BASE_URL` 빈 값 — 같은 주소) — HTTP/1.1이고 Chrome은 같은 주소에 연결 **6개**까지다. `EventSource` 진행 구독도 그 6개를 쓴다. `apiClient`에는 시간 제한이 없다
- 지금 `compareStore.runComparison`은 대상 전부를 `Promise.all`로 한꺼번에 요청하고, 202(수집 중)면 대상마다 진행 구독을 연다(주식·가상자산·예금·부동산 진행, 외환은 `subscribeCollection` — `MAX_COLLECTING_REPEATS=3`).
  확대 구간 자료(`lib/seriesDetail.compareDetailLoader`)도 `Promise.allSettled`로 한꺼번에다. 013에서도 수집 중 대상이 6개를 넘으면 같은 증상(구독이 연결을 다 차지 — 다른 요청이 오류 없이 멈춤)이 난다
- 서버는 단일 워커라 계산이 동시성으로 빨라지지 않는다 — 대상 하나의 비교 요청 0.06~0.13초, 응답 58~91KB(개발 서버, 받아 둔 VOO·VUG·SPY 일시금 실측) → 100개면 서버 계산 약 10~15초
- 주식·가상자산·예금·부동산 진행 경로는 프레임마다 DB의 작업 상태를 읽어 첫 스냅샷을 내고, 이미 끝난 작업이면 곧바로 `completed`다(`api/routes/stock_progress.py`·`crypto_progress.py` 등 — 늦게 붙어도 완료를
  받는다). 외환 수집 스트림의 늦은 연결은 T217에서 확인한다

**Decision**: 비교 요청 한 번에 **3개**, 진행 구독 한 번에 **2개**(합 5 — 하나를 화면의 다른 요청에 남긴다), 확대 구간 요청 한 번에 **3개**. 나머지는 **대상 차례**로 기다린다. 한도는 상수(순수 `lib/concurrency`)이고
설정이 아니다. 결과는 응답 차례가 아니라 대상 자리에 채운다(늦게 온 응답이 다른 대상 자리에 들어가지 않는다 — 지금의 `runSeq`·대상 키 그대로)

**Rationale**: 단일 워커라 동시 요청을 늘려도 서버 시간이 줄지 않는다 — 3개면 왕복 지연을 가리기에 넉넉하고(100개 × 약 0.1초 + 왕복), 구독 둘이 연결을 오래 잡아도 요청 셋과 화면의 다른 요청 하나가 남는다

**Alternatives considered**: 한도 없음(위 멈춤) · 요청 6(구독 자리가 없다) · 대상 하나씩(왕복 지연이 쌓여 100개 30초를 넘을 수 있다) · 서버에 묶음 경로(비교 경로 일곱 = 메뉴 경로의 짝이라는 013 불변을 깬다 —
`test_comparison_identity*`) · HTTP/2(개발 서버 설정을 바꿔야 하고 백엔드 직접 연결과 다르다)

## R14-37 대상 100개 그래프의 구별 (반복 2026-10-13)

**사실**: `CompareReturnChart.tsx`는 색 10개(`PALETTE`·`DARK_PALETTE`)를 `index % 10`, 선 모양을 `index % 2`(실선 0·점선 2)로 고른다 — 짝이 10개뿐이라 1번째와 11번째가 색·모양까지 같다. 커서 상자는
대상 전부를 한 줄씩이다(대상 100개면 100줄). 기존 테스트 "대상 10개는 색 10개가 모두 다르고 선 모양이 번갈아다"가 있다

**Decision**:
- 색 10 × 선 모양 2 = **짝 20** — 첫 10개는 그대로, 11~20번째는 같은 색에 선 모양을 뒤집는다(`(index + ⌊index / 10⌋) % 2`). 21번째부터 짝이 되풀이되고 범례·커서 상자의 이름으로 가른다. 현재 가치 가는 선도 같은 짝
- 대상 11개 이상의 커서 상자는 **커서 세로 자리에 가장 가까운 10개** — 그 날 수익률 점의 좌표(`priceToCoordinate`)와 커서 `point.y`의 거리로 고르고, 그 10개를 그 날 수익률 높은 차례로 보이며 끝 줄 "외 N개 — 비교 표에
  모두 있습니다". `priceToCoordinate`는 **커서 움직임 처리 안에서만** 부른다(그릴 때 부르면 기존 차트 모의가 깨진다 — CLAUDE.md 010). 대상 10개 이하는 지금 그대로(대상 전부·대상 차례)

**Rationale**: 첫 10개를 바꾸지 않아 013의 그림·테스트가 그대로이고, 커서 상자가 10줄을 넘지 않아 지금 크기 그대로다. 가리키는 선의 이름을 바로 읽는다

**Alternatives considered**: 색 20개(서로 구별되는 색상 수가 모자라고 블랙 배경 대비 4.5:1을 다시 재야 한다) · 점선 종류 다섯(2px에서 점선·긴 점선·성긴 점선이 잘 갈리지 않는다) · 상자 여러 단(100개면 그래프를 덮는다) ·
범례 눌러 강조(요청 밖 — 다음 반복 후보)

## R14-38 투자 성과표의 등락 — 열 해석·비교 기준·분할·폭 (반복 2026-10-13b)

**사실**(define 조사 2026-10-13 — 코드·개발 서버 실측, 읽기만):
- 주식·가상자산 × 일시금·적립식 네 표가 한 행 조립 함수(`api/services/table_rows.table_page` — 012)를 쓴다. 서비스가 계산 기간의 시세일 전부·사건 묶음·하루 상태 함수를 넘기고 `period_table.build_table`이
  전체 항목을 만든 뒤 `page`가 자른다 — **쪽을 자르기 전의 전체 항목이 서버에 있다**. 일 단위 행은 시세일마다이고, 사건(첫 매수·배당락·재투자·납입)이 있는 날은 그날의 기간 행 대신 사건 묶음이다
- 투자 비교 모달(013 반복 2026-10-09b)은 메뉴와 같은 부품(`StockDetail`·`CryptoDetail` → 네 표 부품)·같은 경로를 쓴다. 비교 블록(`/api/comparison/…`)에는 행이 없다
- 주식 표의 시작가·종가는 원주가다(010 FR-028). 분할 기록(`SplitOn`)이 결과에 있고, 010의 `split_adjust.split_restated_close`(그 날 뒤 효력 분할의 누적 비율로 나눔 — 소수 6자리 `ROUND_HALF_UP`)와
  `unit_price.split_ratio`(누적 비율 글자 `"분자:분모"`)가 같은 규칙을 이미 쓴다
- 외환 표의 등락(R14-24)은 순수 `simulation/fx_change.rate_change` 하나 — 등락폭 저장 정밀도, 등락률 소수 둘째 자리(`ROUND_HALF_EVEN`), 직전 0 이하면 비율 없음
- 폭(1440×1000, 개발 서버 이력 다시 실행, 본문 칸 1,166px — 표 상자는 칸 폭까지·넘치면 안에서 스크롤):

  | 표 | 지금 폭 | 더할 열 | 예상 |
  |----|---------|---------|------|
  | 주식 일시금 국내(삼성전자 1천만 원) | 1,071px | 넷(약 +230px) | 넘침 약 135px |
  | 주식 일시금 해외(SOXL 1억 원) | 1,283px — **이미 넘침** | 넷 | 넘침 약 350px |
  | 주식 적립식 국내(삼성전자 매월) | 1,050px | 넷 | 넘침 약 115px |
  | 가상자산 일시금(비트코인) | 859px | 둘(약 +120px) | 들어감 |
  | 가상자산 적립식(비트코인 매월) | 951px | 둘 | 들어감 |

**Decision**:
- **열**: 가격 열마다 바로 오른쪽에 그 가격의 등락폭·등락률 — 주식 `시작가 | 등락폭 | 등락률 | 종가 | 등락폭 | 등락률`, 가상자산 `시가 | 등락폭 | 등락률`. 화면 읽기 이름에 가격을 밝힌다
- **비교 기준**: 직전 기간의 대표값 — 행 날짜가 속한 기간의 바로 앞, 시세일이 있는 가장 가까운 기간의 대표일(012 대표일 규칙). 사건 행도 같은 규칙, 같은 날은 같은 값, 첫 기간 `null`
- **계산 자리**: `table_rows.table_page`가 전체 항목에서 비교 날짜를 찾고(쪽 경계에 추가 질의 없음) 잘라 낸 쪽의 행만 계산한다. 비교 날짜는 순수 `period_table`, 분할 맞춤은 새 순수
  `simulation/price_change` — 등락은 외환과 같은 `rate_change`
- **분할**: 효력일 ∈ (비교 날짜, 행 날짜]인 분할·병합의 누적 비율로 비교 가격을 맞추고(× 분모/분자) 비율을 싣는다. 배당락은 맞추지 않는다
- **폭**: 가상자산 두 표는 1440px 가로 스크롤 없음 유지. 주식 두 표는 표 안 가로 스크롤을 허용하고(006 FR-069·010 SC-004·011 SC-010의 예외), 네 표의 날짜 칸을 고정한다
- **이름**: "등락률". 외환 표의 "등락율"은 그대로
- **0 이하 가격**(실측 중 고침 — T226): 주식·가상자산 표는 어느 쪽 가격이든 0 이하면 그 가격의 등락이 없음(`null`)이다 — 실측에서 개발 DB 삼성전자 2026-10-06 시가 0(주식 159,939행
  가운데 하나, 가상자산 22,909행에는 없음)이 −100%·이튿날 ▲269,500(비율 "—")으로 보였다. 외환 `rate_change`의 "직전 0 이하면 비율만 없음"은 음수 값이 있을 수 있는 계열(WTI)의 규칙이다
- **분할 비율의 키**(구현 중 고침 — T223): `split: {"ratio": "분자:분모"} | null`(013 `unitPrice.split`과 같은 꼴). define의 `splitRatio`는 Yahoo 응답 필드명이라 005 가드(`test_layer_boundaries`)가 막는다

**Rationale**:
- 열 — 요청이 주식에 "시가,종가 오른쪽에", 가상자산에 "시가 오른쪽에"다. "가격마다 바로 오른쪽"이 두 자산군에 한 규칙이고, 어느 가격의 등락인지 이웃 열로 읽힌다. 시작가는 매수 가격(적립식은
  시가 매수)이라 그 움직임에도 뜻이 있다
- 비교 기준 — 외환 FR-031의 "주·월 = 직전 주·달의 대표값"과 같은 뜻이다. 외환 표에는 사건 행이 없어 "바로 아래 행"과 같았지만, 성과 표에는 사건 행이 낀다 — 적립식 월 표는 달마다 납입 행이 있어
  "바로 아래 행"이면 달 끝 행이 같은 달 납입 행(며칠 전)과, 납입 행이 지난달 끝(하루이틀 전)과 견주게 된다. 계산 시작 전 시세와 견주면 사용자가 고른 기간 밖의 값이 표에 들어온다
- 계산 자리 — 화면에는 `Decimal`이 없고(원칙 VI), 화면은 쪽 너머 행을 모른다. 같은 함수라 외환 표·요약 칸과 같은 반올림이다
- 분할 — 원주가 그대로면 1:4 분할 날이 −75%로 보인다(폭락으로 오독). 맞추는 것은 시장 시세표의 기준가 조정과 같고, 010이 차트에 쓴 비율 규칙을 그대로 쓴다. 배당은 010 차트처럼 소급하지 않는다 —
  배당락일의 하락은 실제 가격 변화다
- 폭 — 주식 표는 두 열(종가 기준)이라도 국내 일시금이 약 20px 넘쳐 1440px 기준을 어느 꼴로도 지킬 수 없고, 해외 대금액 표는 이미 넘친다. 날짜 칸 고정은 가로로 밀 때 행을 잃지 않게 한다(013 비교 표의
  오른쪽 고정 칸 `STICKY_END`가 앞선 예)
- 이름 — 표준 표기이고 대시보드 지표 표(반복 2026-10-10b)와 같다. 외환 표는 반복 2026-10-10d가 사용자 글자로 정했고 FR-026이 그 화면을 지킨다

**Alternatives considered**:
- 열 — 종가 뒤 두 열만(종가 기준 — 시장 시세표의 전일 대비 관행, 폭 약 +115px). define 보고에서 사용자에게 밝혔다
- 비교 기준 — 바로 아래 행(위 실패 양상) · 기간 행끼리만 견주고 사건 행은 "—"(배당락·납입 날의 움직임이 사라진다) · 계산 시작 전 저장 시세와 견줌(추가 질의·기간 밖 값)
- 계산 자리 — 화면 계산(원칙 VI·쪽 경계) · 저장(원칙 V의 원본·정규화 분리와 무관한 파생 값 — 다시 계산하면 된다)
- 분할 — 분할 날 "—"(그날의 실제 움직임이 사라진다) · 원주가 그대로(오독) · 수정주가 열로 바꿈(010 FR-028 — 잔고를 평가한 가격이 표에서 사라진다)
- 폭 — 등락을 가격 칸 둘째 줄에(모든 행 높이 두 배) · 다른 열 줄이기(배당 금액 칸은 006 FR-067의 세전·세후 두 값) · 날짜 칸을 고정하지 않음(가로로 밀면 행을 잃는다)
