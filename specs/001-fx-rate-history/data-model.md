# Phase 1 Data Model: FX 환율 축적·조회·시각화

**Feature**: 001-fx-rate-history | **Date**: 2026-08-30

spec.md의 Key Entities를 저장 구조로 구체화한다.

- 모든 금액·비율 컬럼은 `DECIMAL`이며 `FLOAT`/`DOUBLE`을 사용하지 않는다(헌법 원칙 VI).
  ORM 필드는 `Numeric(정밀도, 스케일, asdecimal=True)`로 선언한다(research R7).
- 아래 타입 표기는 논리 스키마다. 실제 정의는 **ORM 모델**(`db/models.py`)이며 DDL은 Alembic이
  생성한다(헌법 v4.1.0, research R9).
- 표준 SQL에 없는 구문(멱등 upsert, 통화별 단일 작업 잠금)은 각각 `db/dialect.py`와 잠금 테이블로
  격리한다(research R12, R6).

---

## 엔티티 관계

```text
currency (통화 마스터)
   │ 1
   ├──────< fx_rate            (통화·날짜별 매매기준율)
   ├──────< fx_raw_response    (원본 응답, 영구 보관)
   ├──────1 fx_coverage        (수집 완료 구간)
   ├──────1 fx_spread          (스프레드 설정)
   ├──────1 fx_collection_lock (통화별 단일 작업 잠금)
   └──────< fx_collection_job  (수집 작업 이력)
```

---

## 1. `currency` — 통화 마스터

축적 대상 통화와 고시 단위를 보관한다. 고시 단위를 값과 분리해 두는 이유는 JPY가 100엔당으로
고시되기 때문이다(FR-007).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `code` | `CHAR(3)` | PK | `USD`, `JPY`, `EUR` |
| `display_name` | `VARCHAR(50)` | NOT NULL | 표시 이름 |
| `quote_unit` | `SMALLINT` | NOT NULL | 고시 기준 단위. USD/EUR=1, JPY=100 |
| `source_item_code` | `VARCHAR(20)` | NOT NULL | 출처의 항목 식별자 |
| `first_available_date` | `DATE` | NULL 허용 | 출처가 실제로 값을 제공하기 시작한 날. 수집 중 발견되어 기록 (research R3) |

**초기 데이터**: USD(unit 1), JPY(unit 100), EUR(unit 1).

**검증 규칙**
- `quote_unit`은 1 이상
- `source_item_code`가 출처에서 변경되면 이름 대조로 재확인 후 갱신 (FR-015).
  대조 실패 시 수집을 중단하며 값을 저장하지 않는다.

---

## 2. `fx_rate` — 환율 시계열 레코드

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `currency_code` | `CHAR(3)` | PK, FK → `currency.code` | |
| `quote_date` | `DATE` | PK | 고시일 |
| `base_rate` | `DECIMAL(18,6)` | NOT NULL | 매매기준율. `quote_unit` 기준의 원화 값 |
| `quote_unit` | `SMALLINT` | NOT NULL | 저장 시점의 고시 단위 스냅샷 |
| `source` | `VARCHAR(30)` | NOT NULL | 데이터 출처 식별자 (FR-004) |
| `ingested_at` | `DATETIME(6)` | NOT NULL | 최초 수집 시각 (FR-004) |
| `updated_at` | `DATETIME(6)` | NOT NULL | 마지막 갱신 시각 (FR-003a) |

**키**: `PRIMARY KEY (currency_code, quote_date)` — 멱등 upsert의 근거 (FR-003, 헌법 원칙 V)

**검증 규칙**
- `base_rate > 0`
- `quote_date`는 `currency.first_available_date` 이상, 오늘 미만 (FR-002, FR-019)
- 동일 키에 다른 값이 수신되면 `base_rate`와 `updated_at`을 갱신한다 (FR-003a).
  `ingested_at`은 최초 값을 유지한다.
- 갱신되더라도 대응하는 `fx_raw_response`는 삭제하지 않는다 (FR-003b)

**설계 주의**: `quote_unit`을 `currency`에서 조인하지 않고 행에 복제한다. 출처가 고시 단위를
변경하더라도 과거 행의 값이 어떤 단위로 해석되어야 하는지가 보존되어야 하기 때문이다
(헌법 원칙 V — 값의 의미 고정).

---

## 3. `fx_raw_response` — 원본 응답 기록

정규화된 시계열과 분리 저장하며 기한 없이 보관한다 (FR-004a, FR-004b).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `BIGINT` | PK, AUTO_INCREMENT | |
| `currency_code` | `CHAR(3)` | NOT NULL, FK | |
| `requested_from` | `DATE` | NOT NULL | 요청 구간 시작 |
| `requested_to` | `DATE` | NOT NULL | 요청 구간 끝 |
| `http_status` | `SMALLINT` | NOT NULL | |
| `result_code` | `VARCHAR(20)` | NULL 허용 | 출처가 본문으로 반환한 상태 코드 |
| `body` | `LONGTEXT` | NOT NULL | 응답 원문 |
| `received_at` | `DATETIME(6)` | NOT NULL | |
| `job_id` | `BIGINT` | NULL 허용, FK → `fx_collection_job.id` | |

**인덱스**: `(currency_code, requested_from, requested_to)`, `(received_at)`

**보관 정책**: 자동 정리 없음. 값이 갱신된 경우 갱신 전 값을 추적하는 유일한 근거다 (SC-003).

---

## 4. `fx_coverage` — 수집 커버리지

통화당 한 행. "어디까지 수집을 **시도해 완료했는지**"를 기록한다. 값이 있는지 여부와는 별개이며,
이 구분이 고시 없는 날을 미수집으로 오인해 반복 요청하는 것을 막는다 (FR-006).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `currency_code` | `CHAR(3)` | PK, FK | |
| `covered_from` | `DATE` | NOT NULL | 수집 완료 구간 시작. 고정값이 아니며 통화마다 다르다 (FR-002) |
| `covered_through` | `DATE` | NOT NULL | 수집 완료 구간 끝 |
| `last_updated_at` | `DATETIME(6)` | NOT NULL | |

**설계 결정 — 왜 구간 하나인가**: 백필이 통화별 탐색 시작일부터 순차 진행되고 중단 시 마지막 완료 청크의
다음부터 재개하므로(FR-011), 커버리지에 구멍이 생기지 않는다. 구간 세그먼트 테이블은 발생하지 않는
상황을 위한 복잡도이므로 채택하지 않는다(헌법 원칙 IX, YAGNI).

**파생 판정** (research R8 — 별도 휴장일 캘린더를 두지 않는 근거)
- **고시 없는 날**: `covered_from ≤ D ≤ covered_through` 인데 `fx_rate`에 행이 없는 날
- **미수집**: `D > covered_through` 또는 `D < covered_from`
- **직전 영업일**: 커버리지 구간 안에서 `fx_rate` 행이 존재하는, `D` 미만의 최대 `quote_date`

---

## 5. `fx_spread` — 스프레드 설정

통화당 한 행. 사용자 계정 개념이 없으므로 시스템 전역이다 (spec Assumptions).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `currency_code` | `CHAR(3)` | PK, FK | |
| `cash_buy` | `DECIMAL(9,6)` | NOT NULL | 현금 살 때 |
| `cash_sell` | `DECIMAL(9,6)` | NOT NULL | 현금 팔 때 |
| `remit_send` | `DECIMAL(9,6)` | NOT NULL | 송금 보낼 때 |
| `remit_receive` | `DECIMAL(9,6)` | NOT NULL | 송금 받을 때 |
| `updated_at` | `DATETIME(6)` | NOT NULL | |

**검증 규칙**: 네 컬럼 모두 `>= 0 AND < 1` (FR-025). 범위를 벗어나면 거부하고 기존 값 유지.

**초기값** (FR-024)

| 통화 | cash_buy | cash_sell | remit_send | remit_receive |
|------|----------|-----------|------------|---------------|
| USD | 0.001800 | 0.001800 | 0.000500 | 0.000500 |
| JPY | 0.002000 | 0.002000 | 0.000600 | 0.000600 |
| EUR | 0.002000 | 0.002000 | 0.000600 | 0.000600 |

**시간 축 없음**: 시점별 이력을 관리하지 않는다 (FR-026, Clarifications). 조회 결과에는 산출에
사용된 스프레드 값이 함께 담겨(FR-026a), 결과가 어떤 가정 위에 있는지 드러난다.

---

## 6. `fx_collection_job` — 수집 작업 이력

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `BIGINT` | PK, AUTO_INCREMENT | |
| `currency_code` | `CHAR(3)` | NOT NULL, FK | |
| `range_start` | `DATE` | NOT NULL | 대상 구간 시작 |
| `range_end` | `DATE` | NOT NULL | 대상 구간 끝 |
| `status` | `ENUM` | NOT NULL | `running` / `succeeded` / `partial` / `failed` |
| `chunks_total` | `INT` | NOT NULL | |
| `chunks_done` | `INT` | NOT NULL, 기본 0 | |
| `started_at` | `DATETIME(6)` | NOT NULL | |
| `finished_at` | `DATETIME(6)` | NULL 허용 | |
| `last_error` | `TEXT` | NULL 허용 | 실패 사유 (FR-036) |

**통화별 단일 작업 강제**는 아래 `fx_collection_lock` 테이블이 담당한다 (FR-015a, research R6).
생성 컬럼·부분 인덱스 같은 DB 종속 문법을 쓰지 않는다(헌법 v4.1.0).

**상태 전이**

```text
        생성
         │
         ▼
     [running] ──── 모든 청크 성공 ────▶ [succeeded]
         │
         ├───── 일부 청크 성공 후 중단 ──▶ [partial]
         │
         └───── 첫 청크부터 실패 ────────▶ [failed]
```

- `partial`과 `failed`의 구분 기준은 `chunks_done > 0` 여부다.
- 어떤 종료 상태든 이미 커밋된 청크의 데이터와 커버리지는 유효하다 (FR-013).
- 재실행은 새 작업을 생성하며, 시작점은 `fx_coverage.covered_through + 1`이다 (FR-011).

**보관 정책** (FR-038a, FR-038b)
- `failed`, `partial`: 기한 없이 보관
- `succeeded`: 설정된 보관 기간(기본 90일) 경과 후 정리 가능

---

## 7. `fx_collection_lock` — 통화별 단일 작업 잠금

표준 SQL만으로 "통화당 진행 중 작업 1개"를 강제한다 (FR-015a, research R6).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `currency_code` | `CHAR(3)` | PK, FK → `currency.code` | 기본 키가 곧 잠금 단위 |
| `job_id` | `BIGINT` | NOT NULL, FK → `fx_collection_job.id` | 잠금을 보유한 작업 |
| `acquired_at` | `DATETIME(6)` | NOT NULL | 획득 시각 |
| `heartbeat_at` | `DATETIME(6)` | NOT NULL | 마지막 생존 신호 |

**동작**

- **획득**: `INSERT`를 시도한다. 성공하면 잠금 획득, 기본 키 충돌로 실패하면 이미 진행 중인 작업이
  있는 것이다. 이때 `job_id`로 기존 작업을 찾아 그 완료를 구독한다 (FR-015b).
- **갱신**: 수집기가 청크를 커밋할 때마다(FR-010) `heartbeat_at`을 갱신한다. 추가 왕복이 없다.
- **해제**: 작업이 종료 상태로 전이할 때 `DELETE`한다.
- **스테일 회수**: `heartbeat_at`이 설정된 임계값보다 오래된 잠금은 회수 가능하다. 프로세스가
  비정상 종료해 잠금이 남는 경우를 처리한다.

**설계 근거**: 기본 키 `INSERT` 충돌은 모든 RDBMS에서 동일하게 동작하는 유일한 이식 가능 수단이다.
MySQL 생성 컬럼이나 PostgreSQL 부분 인덱스는 어느 쪽을 택해도 다른 DB에서 깨진다.
서로 다른 통화의 잠금은 서로 다른 행이므로 통화 간 병행(FR-015c)을 막지 않는다.

---

## 8. `alembic_version` — 마이그레이션 버전 (research R9)

Alembic이 생성·관리한다. 애플리케이션 코드가 직접 다루지 않는다.

---

## 도메인 계산 (저장하지 않음)

파생 환율은 어떤 테이블에도 저장하지 않는다 (spec Assumptions, FR-026a). 스프레드가 변경
가능하므로 미리 계산해 저장하면 즉시 무효가 되기 때문이다.

`simulation/spread_calc.py`의 순수 함수로 산출한다.

```text
현금 살 때    = base_rate × (1 + cash_buy)
현금 팔 때    = base_rate × (1 − cash_sell)
송금 보낼 때  = base_rate × (1 + remit_send)
송금 받을 때  = base_rate × (1 − remit_receive)
```

- 모든 연산은 `Decimal`. 중간 반올림 없음.
- 표시 직전 1회만 `quantize(Decimal('0.01'), ROUND_HALF_UP)` (research R7)
- 이 모듈은 `repository`·`api`를 임포트하지 않는다 (헌법 원칙 IV)

---

## 데이터 규모

| 테이블 | 예상 행 수 (통화별 제공 최초일부터 누적) |
|--------|----------------------|
| `fx_rate` | 약 38,200 (USD 약 16,500 + JPY 약 13,100 + EUR 약 8,600) |
| `fx_raw_response` | 백필 약 146건 + 일별 증분 누적 |
| `fx_coverage` | 3 |
| `fx_spread` | 3 |
| `fx_collection_job` | 백필 3건 + 증분 누적 (성공분은 90일 후 정리) |
| `fx_collection_lock` | 0~3 (진행 중 작업 수만큼) |
