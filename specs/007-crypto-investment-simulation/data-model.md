# Data Model: 가상자산 투자 시뮬레이션

**Feature**: `007-crypto-investment-simulation` | **Date**: 2026-10-03 | 근거: [research.md](./research.md)

**신규 테이블 11개, 기존 테이블 변경 없음.** 주식(005·006) 테이블과 합치지 않는다 — 출처·식별·정밀도가 다르고, 점유를 자산군끼리
공유하지 않는다(005 research R5-7). 스키마는 Alembic 마이그레이션 하나로 만든다(헌법 DB 운영 규약). 금액·비율·가격은 모두 `DECIMAL`
(헌법 원칙 VI). 시각은 UTC로 넣는다 — DB의 `now()` 기본값은 DB 서버 시간대가 끼어든다(006과 같다).

형식 이름: `CPRICE` = `DECIMAL(36, 14)`(R7-13), `CVOLUME` = `DECIMAL(38, 8)`, `SPREAD` = `DECIMAL(9, 6)`(기존), `TS` = `DATETIME`(UTC).

---

## 1. `crypto_coin` — 코인 (FR-003~FR-006, FR-005a, FR-008)

코인 목록 한 줄이자 시뮬레이션의 대상이다. 주식처럼 "검색용 목록"과 "고른 종목"을 나누지 않는다 — 목록의 `instrument_id`가 곧 일봉
API의 식별자라 고른 뒤 등록할 것이 없다(R7-4).

| 열 | 형식 | 규칙 |
|----|------|------|
| `id` | BIGINT PK auto | 화면·API가 쓰는 코인 id(`coinId`) |
| `source` | VARCHAR(32) NOT NULL | `investing` |
| `source_id` | VARCHAR(32) NOT NULL | 출처의 `instrument_id`(문자열로 둔다 — 출처 형식에 묶이지 않게) |
| `slug` | VARCHAR(128) NULL | 출처의 slug. 표시·이력 보조 |
| `symbol` | VARCHAR(32) NOT NULL | **유일하지 않다**(R7-4 — 169개 겹침) |
| `name_en` | VARCHAR(256) NOT NULL | 영문 판 이름 |
| `name_ko` | VARCHAR(256) NULL | 한국어 판 이름이 영문과 다르고 한글을 포함할 때만(FR-006, R7-4) |
| `quote_currency` | CHAR(3) NOT NULL | 시세 통화. 지금은 `USD`(R7-4) |
| `market_rank` | INT NULL | 시가총액 순위. 검색의 같은 순위 정렬에 쓴다(R7-6) |
| `status` | VARCHAR(8) NOT NULL default `listed` | `listed` / `missing` — **지우지 않는다**(FR-005a) |
| `first_available_date` | DATE NULL | 출처의 첫 일봉. **수집 중 발견**(R7-10, 헌법 — 상수 아님) |
| `first_seen_at` / `last_seen_at` | TS NOT NULL | 목록에 처음·마지막으로 보인 때 |
| `ingested_at` | TS NOT NULL | |

- 유일 키 `(source, source_id)`. 색인 `(status)`
- 목록 갱신이 upsert한다 — 이번 목록에 없는 행은 `status = missing`, 다시 보이면 `listed`
- 실패 양상: `symbol`로 식별하면 같은 심볼의 다른 코인 시세로 계산된다(FR-004) — 어떤 조회도 `symbol`을 키로 쓰지 않는다

## 2. `crypto_coin_refresh` — 목록 갱신 기록 (FR-005, FR-019)

판(`edition`)마다 한 행 — `en`(영문, 코인 목록), `ko`(한국어, 한글 이름). 006 `stock_listing_refresh`와 같은 열이다.

| 열 | 형식 | 규칙 |
|----|------|------|
| `edition` | VARCHAR(4) PK | `en` / `ko` |
| `as_of` | TS NULL | **온전히 받아 교체한 마지막 시각**. 실패·일부면 바뀌지 않는다 |
| `as_of_date` | DATE NULL | `as_of`의 한국 시간 날짜 — 주기 판정 |
| `row_count` | INT NULL | 교체한 코인 수 — 50% 축소 검사의 기준(R7-4) |
| `attempt_date` | DATE NULL | 마지막 시도의 한국 시간 날짜 — 실패 뒤 "다음 날" 판정 |
| `attempts` | SMALLINT NOT NULL default 0 | 그날 시도 수 |
| `last_attempt_at` / `last_failed_at` | TS NULL | |
| `last_error_kind` | VARCHAR(16) NULL | `blocked` / `format` / `network` / `shrunk` |
| `last_error` | VARCHAR(512) NULL | 사유. 요청 헤더를 싣지 않는다 |

**갱신 판정**(순수 함수): `en`의 `as_of_date`가 없거나 오늘(한국 시간) − `as_of_date` ≥ 7일이고, 오늘 이미 시도하지 않았으면 갱신한다
(FR-005, 사용자 결정 2026-10-03). `ko`는 `en`과 함께 받는다.

## 3. `crypto_list_lock` — 갱신 점유와 진행 (FR-005b)

| 열 | 형식 | 규칙 |
|----|------|------|
| `scope` | VARCHAR(16) PK | `coins` 하나 |
| `started_at` / `heartbeat_at` | TS NOT NULL | 오래된 점유는 회수(006과 같다) |
| `edition` | VARCHAR(4) NULL | 지금 받는 판(`en`/`ko`) |
| `pages_done` | SMALLINT NOT NULL default 0 | 그 판에서 받은 쪽 수 |
| `coins_seen` | INT NOT NULL default 0 | 그 판에서 받은 코인 수 |

기본 키 INSERT 충돌이 곧 "이미 갱신 중"이다(006 `stock_listing_lock`과 같은 수단). 갱신 줄이 쪽마다 진행 열과 `heartbeat_at`을 고치고,
진행 스트림(`/api/crypto/list/progress`)이 프레임마다 이 행을 읽는다. 갱신이 끝나면 행을 지운다 — 행이 없으면 갱신 중이 아니다
(research R7-11, analyze C2).

## 4. `crypto_list_raw_body` · `crypto_list_raw` — 목록 원본 (헌법 원칙 V)

006 `stock_listing_raw_body`·`stock_listing_raw`와 같은 구조. **같은 본문은 한 번만**(SHA-256), **지우지 않는다**. 헤더는 담지 않는다.

| 테이블 | 열 |
|--------|-----|
| `crypto_list_raw_body` | `sha256` VARCHAR(64) PK, `body` MEDIUMTEXT, `first_stored_at` TS |
| `crypto_list_raw` | `id` BIGINT PK, `edition` VARCHAR(4), `batch_started_at` TS, `page_no` SMALLINT, `status_code` SMALLINT, `body_sha256` FK, `fetched_at` TS |

## 5. `crypto_daily` — 일봉 (FR-010, FR-012, FR-012a, FR-021~FR-023)

| 열 | 형식 | 규칙 |
|----|------|------|
| `coin_id` | BIGINT FK PK | |
| `day` | DATE PK | **UTC 날짜**(R7-3) |
| `open` / `high` / `low` / `close` | CPRICE NOT NULL | 출처 원값 문자열 그대로(R7-3) — `float`·반올림 없음 |
| `volume` | CVOLUME NULL | 출처가 빈 값·`-`로 준 날은 `NULL`(FR-012a) — 0이 아니다 |
| `source` | VARCHAR(64) NOT NULL | `investing:historical` |
| `ingested_at` | TS NOT NULL | |

- `(coin_id, day)` 복합 기본 키 + upsert — 멱등·재개(헌법 원칙 V)
- **마감된 UTC 하루만 들어온다** — 계산 끝(UTC 어제)보다 뒤의 행은 정규화에서 버린다(FR-022, R7-3). 그래서 잠정 열이 없다
- 결측은 행이 없는 것으로 표현한다 — 채우지 않는다(헌법 원칙 V)

## 6. `crypto_raw_response` — 일봉 원본 (FR-012)

| 열 | 형식 | 규칙 |
|----|------|------|
| `id` | BIGINT PK | |
| `coin_id` | BIGINT FK | |
| `requested_from` / `requested_to` | DATE | 요청한 구간(청크) |
| `status_code` | SMALLINT | |
| `body` | MEDIUMTEXT | 응답 본문 그대로(오늘 일봉 포함) |
| `received_at` | TS | |

색인 `(received_at)`. 005 `stock_raw_response`와 같은 이유로 처음부터 `MEDIUMTEXT`다.

## 7. `crypto_coverage` — 수집 구간 (FR-010, FR-011)

| 열 | 형식 |
|----|------|
| `coin_id` | BIGINT FK PK |
| `covered_from` / `covered_through` | DATE |
| `updated_at` | TS |

**요청한 구간**을 기록한다 — 일봉이 없던 구간도 다시 받으러 가지 않는다(005와 같다). 빠진 구간 판정은 005의 `missing_ranges`를 쓴다.

## 8. `crypto_collection_job` · `crypto_collection_lock` — 수집 작업과 점유 (FR-013, FR-014)

005 `stock_collection_job`·`stock_collection_lock`과 같은 열(종목 자리에 `coin_id`). 작업 상태는 기존 `JobStatus`. 점유는 코인마다
하나(기본 키 INSERT 충돌 = 이미 진행 중). 진행(받은 날 / 받을 날)은 작업의 구간과 커버리지로 계산한다(006 FR-045a와 같다).

`last_error`에는 사유 종류(`blocked`/`format`/`network`/`empty`)와 문구를 남긴다(FR-020).

## 9. `crypto_setting` — 가상자산 설정 (FR-032, FR-033)

| 열 | 형식 | 규칙 |
|----|------|------|
| `id` | SMALLINT PK default 1 | 전역 단일 행 |
| `trade_fee_rate` | SPREAD NOT NULL | 기본 **0.001000**(0.1%). 0 ≤ 값 < 1 |
| `updated_at` | TS | |

행이 없으면 기본값을 쓴다(`isDefault: true`) — 006 `stock_setting`과 같다. 주식 설정과 합치지 않는다(FR-032).

---

## 저장하지 않는 것

### 시뮬레이션 결과 (FR-025~FR-031, FR-037~FR-044)

일봉·설정·환율의 함수라 저장하지 않는다(005 R5-9). 순수 함수의 출력 —

- **행**(월 첫 일봉 스냅샷): 날짜, 시가, 구매 수량, 보유 수량, 예수금, 투자금, 잔고, 투자 수익, 수익율, 매매 수수료(매수 행만), 1일 결측
  여부(그 달 1일 일봉이 없어 다른 날이 행이 됨, FR-030)
- **KRW 평가**(시세 통화가 KRW가 아니면): 그 행의 매매기준율과 날짜, 잔고 KRW, 투자 수익·수익율은 KRW 기준(R7-8)
- **요약**: 투자 원금, 원금 KRW(원금 통화가 KRW가 아니면), 투자 수익, 수익률, 어느 날짜까지인가, 끊겼는가(FR-024), 매수일

수량은 소수 8자리, 계산은 `Decimal`이다. 버림 규칙은 research R7-7.

### 이력 항목 (FR-045, FR-046)

브라우저 저장소에, **주식 이력과 다른 키로** 둔다. 코인 id·심볼·이름(영문·한글)·slug, 시작일, 원금, 원금 통화, 저장 시각. 결과 수치는
없다(005와 같다). 다시 실행할 때 코인 id가 없거나(`unknown_coin`) 원금 통화 조합이 막히면 사유와 할 일이 보인다.

---

## 상태 전이

**코인 목록 상태**: `listed` ⇄ `missing`. 갱신마다 이번 목록에 있으면 `listed`, 없으면 `missing`. 행은 지우지 않는다.

**수집 작업**: 005와 같다 — `RUNNING` → `SUCCEEDED` / `FAILED`. 실패하면 점유를 풀고 사유를 남긴다. 다음 실행이 빠진 구간만 다시 받는다.

**목록 갱신**: 주기가 되면(2절) 첫 검색이 요청 → 갱신 줄이 점유 → `en` 37쪽 → `ko` 37쪽 → 축소 검사 → 한 트랜잭션 교체 → `as_of`
갱신. `en`이 실패하면 아무것도 바꾸지 않는다. `ko`만 실패하면 `en`으로 교체하고 한글 이름은 이전 값을 둔다(R7-4).
