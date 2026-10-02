# Data Model: 주식 시뮬레이션 개선 — 시작일·종목 검색·환전

**Feature**: `006-stock-simulation-enhancements` | **Date**: 2026-10-02

신규 테이블 5개. **005·001의 테이블은 구조를 바꾸지 않는다.** 005의 `stock`에 컬럼을 더하지 않으며,
특히 목록의 상장일을 `stock.first_available_date`에 복사하지 않는다(research R6-8).

시각은 UTC로 저장한다(헌법 시계열 불변식). "오늘"의 판정만 한국 시간 날짜로 한다(spec Assumptions).

---

## 1. `stock_listing` — 검색용 종목

시세를 담지 않는다. 시세는 005의 `stock_price`가 담는다(FR-012).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BIGINT | PK, 자동 증가 | |
| `country` | CHAR(2) | NOT NULL | `KR` \| `US` |
| `code` | VARCHAR(16) | NOT NULL | 국내 종목코드(6자리) 또는 미국 티커. **출처 표기 그대로** |
| `unit` | VARCHAR(8) | NOT NULL | 지금 속한 단위: `KOSPI`·`KOSDAQ`·`KR_ETF`·`KR_REIT`·`NYSE`·`NASDAQ`·`AMEX` |
| `name_ko` | VARCHAR(128) | NULL 허용 | 한글 종목명. 미국 종목은 출처가 비워 줄 수 있다 |
| `name_en` | VARCHAR(256) | NULL 허용 | 영문 종목명. 미국만 |
| `kind` | VARCHAR(8) | NOT NULL | `stock` \| `etf` \| `reit` |
| `listed_on` | DATE | NULL 허용 | 상장일. 국내만. **시작 가능 날짜가 아니라 하한이다**(FR-005a) |
| `status` | VARCHAR(8) | NOT NULL, 기본 `listed` | `listed` \| `missing`("목록에서 빠짐") |
| `first_seen_at` | TIMESTAMP | NOT NULL | 처음 목록에서 본 시각 |
| `last_seen_at` | TIMESTAMP | NOT NULL | 마지막으로 목록에서 본 시각 |
| `source` | VARCHAR(32) | NOT NULL | `kiwoom:ka10099` \| `kiwoom:usa10099` |
| `ingested_at` | TIMESTAMP | NOT NULL, 기본 now | |

**키**: `UNIQUE (country, code)`. 단위는 키가 아니다 — 이전상장으로 단위가 바뀌어도 같은 종목이다
(FR-019a, research R6-4). **인덱스**: `(unit, status)` — 단위별 "빠짐" 표시에 쓴다.

**검증 규칙**

- `code`는 비어 있을 수 없다. 국내는 6자리여야 한다. 어기는 행이 있으면 그 단위의 갱신 전체를
  `invalid`로 실패시킨다 — 한 행을 조용히 버리면 그 종목만 "빠짐"이 된다.
- `name_ko`와 `name_en`이 둘 다 비면 찾을 수 없는 종목이 된다. 티커로는 찾히므로 저장은 한다.
- **목록의 `lastPrice`·`listCount`는 저장하지 않는다.** 정렬에 가격을 쓰지 않기로 했고
  (Clarifications Q4), 저장하면 시세가 두 출처에서 섞일 자리가 생긴다(FR-012).

**상태 전이**

```
          (그 단위 갱신에서 보임)
 없음 ──────────────────────────► listed
                                   │  ▲
  (지금 속한 단위의 갱신에서 안 보임) │  │ (어느 단위의 갱신에서든 다시 보임 — 단위도 갱신)
                                   ▼  │
                                  missing
```

**지우지 않는다**(FR-019). `missing`은 "지워진 것"이 아니라 "최근 목록에 없다"는 사실이다.

---

## 2. `stock_listing_refresh` — 목록 갱신 기록

단위마다 한 행. **기준 시각은 온전히 받은 마지막 시각**이다(spec Key Entities).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `unit` | VARCHAR(8) | PK | |
| `as_of` | TIMESTAMP | NULL 허용 | 목록 기준 시각. 한 번도 온전히 받지 못했으면 NULL |
| `as_of_date` | DATE | NULL 허용 | `as_of`의 한국 시간 날짜. "오늘 받았나"의 판정 근거(FR-013) |
| `row_count` | INT | NULL 허용 | 마지막으로 온전히 받은 종목 수. 축소 검사의 기준(FR-018a) |
| `attempt_date` | DATE | NULL 허용 | 시도 횟수를 센 한국 시간 날짜 |
| `attempts` | SMALLINT | NOT NULL, 기본 0 | `attempt_date`의 시도 횟수(FR-013a) |
| `last_attempt_at` | TIMESTAMP | NULL 허용 | |
| `last_failed_at` | TIMESTAMP | NULL 허용 | 재시도 간격의 기준 |
| `last_error_kind` | VARCHAR(16) | NULL 허용 | `auth` \| `rate_limit` \| `network` \| `invalid` |
| `last_error` | VARCHAR(512) | NULL 허용 | 사유. **키·토큰·인증 헤더를 담지 않는다**(FR-060) |

**화면에 보이는 단위 상태**(FR-028, FR-029) — 저장하지 않고 위 값과 점유·메모리 상태로 계산한다.

| 상태 | 조건 | 검색이 하는 말 |
|------|------|----------------|
| `ready` | `as_of_date` = 오늘 | 기준 시각 |
| `refreshing` | 점유가 있다 | "갱신 중 — {기준 시각} 목록으로 답함" 또는 목록이 없으면 "받는 중" |
| `stale` | `as_of_date` < 오늘, 갱신 중 아님 | 기준 시각(어제 이전) |
| `failed` | 마지막 시도가 실패, `as_of` 이후 | 사유 + 기준 시각 |
| `auth_blocked` | 프로세스 메모리의 인증 실패 막힘 | "인증 실패 — 인증 정보를 확인하세요"(할 일, FR-028a) |
| `never` | `as_of` NULL, 갱신 중 아님 | "목록을 받지 못함" + 사유 + 할 일 |

---

## 3. `stock_listing_lock` — 갱신 점유

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `unit` | VARCHAR(8) | PK | **기본 키 INSERT 충돌이 곧 "이미 갱신 중"**(헌법 DB 운영 규약) |
| `started_at` | TIMESTAMP | NOT NULL | |
| `heartbeat_at` | TIMESTAMP | NOT NULL | 쪽을 받을 때마다 갱신 |

**정체 회수**: 기동 시 모든 점유를 푼다(단일 프로세스). 실행 중에는 심장박동이 설정한 시간(기본
10분 — 미국 목록의 분당 제한을 넉넉히 넘는 값)보다 오래되면 회수한다. 회수하지 않으면 프로세스가
죽은 뒤 그 단위는 다시 갱신할 수 없다.

---

## 4. `stock_listing_raw` — 원본 응답의 쪽 기록

헌법 원칙 V의 "원본과 정규화의 분리 저장". **목록 응답만** 담는다(FR-061). 본문은 4a의 테이블에
**한 번만** 두고 여기서는 해시로 가리킨다(research R6-13).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BIGINT | PK, 자동 증가 | |
| `unit` | VARCHAR(8) | NOT NULL | |
| `batch_started_at` | TIMESTAMP | NOT NULL | 한 번의 갱신을 묶는 값 |
| `page_no` | SMALLINT | NOT NULL | 1부터 |
| `status_code` | SMALLINT | NOT NULL | HTTP 상태 |
| `body_sha256` | CHAR(64) | NOT NULL, FK → `stock_listing_raw_body.sha256` | 본문의 해시 |
| `fetched_at` | TIMESTAMP | NOT NULL | |

## 4a. `stock_listing_raw_body` — 원본 응답 본문

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `sha256` | CHAR(64) | PK | 본문의 SHA-256(16진수 소문자) |
| `body` | MEDIUMTEXT | NOT NULL | 응답 본문 그대로. **요청·응답 헤더는 담지 않는다** — 인증 헤더가 섞인다 |
| `first_stored_at` | TIMESTAMP | NOT NULL | 이 본문을 처음 받은 시각 |

**보존**: **지우지 않는다**(헌법 원칙 V, analyze C1). 같은 본문을 다시 받으면 4a에 새 행을 넣지 않고
쪽 기록만 남긴다 — 기본 키 충돌을 "이미 있음"으로 다룬다. **실패한 갱신의 원본도 남긴다** — 무엇이
잘못 왔는지 되짚는 근거가 그것이다. 두 테이블에는 삭제하는 질의를 두지 않는다(정적 검사, tasks T083).

---

## 5. 메모리 상태 (저장하지 않음)

| 이름 | 내용 | 수명 |
|------|------|------|
| 검색 색인 | 종목마다 정규화 이름·초성 열·식별 필드. 단위별 기준 시각의 최댓값을 버전으로 든다 | 버전이 바뀌면 다시 만든다(research R6-5) |
| 접근 토큰 | 키움 토큰과 만료 시각 | 만료 10분 전 갱신. **DB·파일·로그에 쓰지 않는다**(FR-061) |
| 인증 실패 막힘 | 단위 집합 | 프로세스 재시작까지(research R6-3, FR-013b) |

---

## 6. 읽기만 하는 기존 데이터

| 테이블 | 006이 쓰는 것 | 변경 |
|--------|---------------|------|
| `fx_rate` (001) | `base_rate`, **`quote_unit`** | 없음. 읽을 때 `quote_unit`으로 나눈다(FR-042, research R6-9) |
| `fx_coverage` (001) | `covered_from`, `covered_through` | 없음. 환율 판정의 근거(FR-043, FR-044) |
| `currency` (001) | **`first_available_date`** — 출처의 실제 최초 고시일(001 FR-002a) | 없음. "출처에 없음" 판정(FR-043a ①) |
| 설정 (001) | `ECOS_PROBE_START_*`·`ECOS_PROBE_FLOOR` → `probe_start(통화)` | 없음. "수집 범위 설정 밖" 판정(FR-043a ②) |
| `stock` (005) | `(market, symbol)`, 미국은 `symbol`로 먼저 찾기 | 없음(FR-030, FR-030a) |
| `stock_price`·`stock_coverage` (005) | 시작 월 일봉 존재, 수집 범위 | 없음(FR-005a) |

---

## 7. 설정 (`.env`, 저장소 루트)

헌법 원칙 II — 한도·재시도·비밀은 코드가 아니라 설정이다. `.env.example`에 키 이름만 더한다.

| 키 | 기본값 | 설명 |
|----|--------|------|
| `KIWOOM_MODE` | `real` | `real` \| `mock`. 도메인을 정한다(research R6-1) |
| `KIWOOM_APP_KEY` | (없음) | **비밀.** 비어 있으면 갱신을 시도하지 않고 `never` + "인증 정보 미설정"(FR-028a) |
| `KIWOOM_APP_SECRET` | (없음) | **비밀** |
| `KIWOOM_US_PAGE_DELAY_SECONDS` | `12` | 미국 목록 쪽 사이 간격. 분당 5회 제한(research R6-2) |
| `KIWOOM_KR_PAGE_DELAY_SECONDS` | `1` | 국내 목록 쪽 사이 간격 |
| `KIWOOM_MAX_RETRIES` | `3` | 한 요청 안의 재시도(네트워크·5xx만) |
| `LISTING_RETRY_INTERVAL_MINUTES` | `30` | 갱신 실패 뒤 다음 시도까지(FR-013a) |
| `LISTING_MAX_ATTEMPTS_PER_DAY` | `5` | 단위마다 하루 시도 상한(FR-013a) |
| `LISTING_SHRINK_THRESHOLD` | `0.5` | **새 건수 < 이전 건수 × 이 값**이면 교체하지 않는다(FR-018a). `Decimal`로 읽는다 |
| `LISTING_LOCK_STALE_MINUTES` | `10` | 점유 정체 판정 |

---

## 8. 원금 통화

| 상수 | 005 | 006 |
|------|-----|-----|
| 원금 통화 목록 | `KRW·USD·JPY·EUR` | **`KRW·USD·JPY`**(FR-050d) |
| 허용 조합 | 모두(교차는 잘못 계산) | **`{KRW, 종목 통화}`만**(FR-050) |

판정은 서버의 한 함수가 한다(research R6-11). 브라우저 이력(005)의 형식은 바꾸지 않는다 — 막힌
조합 항목도 그대로 읽힌다(FR-050c).
