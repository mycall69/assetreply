# Data Model: 예금 투자 시뮬레이션

**Feature**: `008-deposit-investment-simulation` | **Date**: 2026-10-04 | 근거: [research.md](./research.md)

**신규 테이블 6개, 기존 테이블 변경 없음.** 환율(001)·주식·가상자산 테이블과 합치지 않는다 — 같은 ECOS 출처여도 환율은 일별·통화별이고
금리는 월별·투자처별이다. 점유도 자산군끼리 공유하지 않는다(005 research R5-7). 스키마는 Alembic 마이그레이션 하나로 만든다(헌법 DB 운영
규약 — 현재 head `b7e3c9d14a26` 다음). 금리·세율은 `DECIMAL`(헌법 원칙 VI). 시각은 UTC로 넣는다(006·007과 같다). **달**은 그 달 1일의
`DATE`로 둔다 — 문자열(`YYYYMM`)로 두면 범위 비교가 문자열 비교가 된다.

형식 이름: `RATE_PCT` = `DECIMAL(7, 4)`(연 %, research R8-11), `SPREAD` = `DECIMAL(9, 6)`(기존), `TS` = `DATETIME`(UTC).

**투자처는 테이블이 아니다.** 다섯 개로 고정이고(FR-003) 출처의 통계표·항목 코드는 ECOS 어댑터 안에만 있다(research R8-1). DB에는
투자처 키(`VARCHAR(24)` — `commercial_bank` 등)만 둔다.

---

## 1. `deposit_rate` — 월별 금리 (FR-008, FR-009, FR-019)

| 열 | 형식 | 규칙 |
|----|------|------|
| `institution` | VARCHAR(24) NOT NULL | 투자처 키 |
| `month` | DATE NOT NULL | 그 달 1일(한국 시간 달력) |
| `rate` | RATE_PCT NOT NULL | 연 %, 출처 값 그대로(`3.39`) |
| `source` | VARCHAR(16) NOT NULL | `ecos` |
| `ingested_at` | TS NOT NULL | |

- 기본 키 `(institution, month)` — upsert로 멱등(헌법 원칙 V)
- **발표된 달만** 있다. 미발표 달은 행이 없다 — 잠정 금리는 저장하지 않는다(research R8-8)
- 결측 = 그 투자처의 첫 달과 마지막 달 사이에 행이 없는 달(FR-019). 실측 결측은 0개다(research R8-1)
- 이미 있는 달을 다시 받으면 **바꾸지 않는다** — 값이 다르면 사건만 남긴다(research R8-4)

## 2. `deposit_raw_response` — 받은 원본 (FR-009, 헌법 원칙 V)

| 열 | 형식 | 규칙 |
|----|------|------|
| `id` | BIGINT PK | |
| `institution` | VARCHAR(24) NULL | 금리 요청이면 투자처 키. **항목 목록이면 NULL** — 통계표 하나가 여러 투자처를 덮는다(analyze I2) |
| `endpoint` | VARCHAR(24) NOT NULL | `item_list` / `search` |
| `source_ref` | VARCHAR(32) NOT NULL | 어댑터가 주는 **불투명한** 출처 참조(예: 통계표, 통계표/항목). 저장소는 해석하지 않는다(헌법 원칙 II) |
| `requested_from` / `requested_to` | DATE NULL | 금리 요청의 구간(항목 확인이면 NULL) |
| `status_code` | SMALLINT NOT NULL | |
| `result_code` | VARCHAR(16) NULL | `RESULT.CODE`(`INFO-200` 등) — 정상 응답이면 NULL |
| `body` | LONGTEXT NOT NULL(`Text(16_777_215)` — utf8mb4에서 LONGTEXT, 005~007과 같다) | 응답 본문 그대로. **요청 URL은 담지 않는다**(인증키가 경로에 있다 — FR-014) |
| `received_at` | TS NOT NULL | |

- 지우지 않는다. 크기: 한 투자처 전체 시계열 응답이 수십 KB, 하루 확인은 많아야 5회 — 1년에 수 MB 수준이다(007 data-model과 같은 정책:
  1GB를 넘으면 정리 정책을 따로 정한다)

## 3. `deposit_coverage` — 받은 구간과 확인한 날 (FR-006, FR-009, FR-010)

| 열 | 형식 | 규칙 |
|----|------|------|
| `institution` | VARCHAR(24) PK | |
| `first_month` | DATE NOT NULL | 받은 시계열의 첫 달 — **시작 가능 날짜**(그 달 1일, FR-006) |
| `latest_month` | DATE NOT NULL | **마지막으로 발표된 달**(받은 시계열의 마지막 달). 그 뒤는 미발표 |
| `checked_on` | DATE NOT NULL | 마지막으로 출처를 확인한 날(**한국 시간**). 오늘이면 같은 날 다시 부르지 않는다(FR-010) |
| `updated_at` | TS | |

- 받은 구간은 `[first_month, latest_month]`이다. 그 안의 빈 달은 결측이고, 그 뒤의 달은 미발표다
- `checked_on`은 확인이 **성공했을 때만** 갱신한다. 오늘 확인이 실패했는지는 그 투자처의 오늘 작업 기록(`FAILED`)으로 판정한다 — 받아 둔
  금리로 답할 수 있으면 그날은 다시 202를 내지 않고, 다음 날 다시 확인한다(contracts 오류 절)

## 4. `deposit_collection_job` · `deposit_collection_lock` — 수집 작업과 점유 (FR-011, FR-012)

007 `crypto_collection_job`·`crypto_collection_lock`과 같은 열(코인 자리에 `institution`). 작업 상태는 기존 `JobStatus`. 점유는 투자처마다
하나(기본 키 INSERT 충돌 = 이미 진행 중, FR-012). 작업의 `range_start`·`range_end`(**NOT NULL**, 007과 같다)는 **그 실행에 필요한 구간**
(시작 달 1일 ~ 이번 달 1일, 한국 시간)이다 — 요청 때 늘 안다. 실제 요청 범위는 research R8-5를 따르지만(처음엔 `START_TIME`부터 전체 시계열,
다시 확인은 겹침 2개월부터) **진행(받은 달 / 받을 달)은 이 구간의 달로 센다**(analyze I1·U2). 받을 달에는 미발표 달도 들어가므로 완료 뒤
`받은 달 < 받을 달`일 수 있다 — 완료되면 진행 줄 대신 결과(미발표 달은 잠정)가 나온다.

`last_error`에는 사유 종류(`auth`/`rate_limited`/`format`/`network`)와 문구를 남긴다(FR-016). 문구는 `mask_secrets`를 거친다(FR-014).
기동 시 남은 점유는 풀고 그 작업을 `network`("실행 프로세스가 끝나 점유를 회수했습니다")로 마감한다(FR-012, 007 FR-014a와 같다).

## 5. `deposit_setting` — 예금 설정 (FR-030, FR-031)

| 열 | 형식 | 규칙 |
|----|------|------|
| `id` | SMALLINT PK default 1 | 전역 단일 행 |
| `interest_tax_rate` | SPREAD NOT NULL | 기본 **0.154000**(15.4%). 0 ≤ 값 < 1 |
| `updated_at` | TS | |

행이 없으면 기본값을 쓴다(`isDefault: true`) — 006 `stock_setting`·007 `crypto_setting`과 같다. 주식의 배당 소득세율과 합치지 않는다(FR-030).

---

## 저장하지 않는 것

### 시뮬레이션 결과 (FR-021~FR-036)

결과는 금리·세율·입력의 **함수**다 — 보관하면 금리가 발표되거나 세율이 바뀌었을 때 낡는다. 순수 함수
`simulation/deposit_rollover.py`가 만든다:

| 값 | 내용 |
|----|------|
| 회차(`Term`) | 번호, 가입일, 만기일, 금리, 금리의 달, 잠정 여부, 예치 원금, 이자, 세금, 세후 이자 |
| 행(`DepositRow`) | 날짜, 구분(`join`/`month`/`maturity`/`reinvest`), 금리, 금리의 달, 잠정 여부, 예치 원금, 이자·세금·세후 이자(경과분 또는 만기분), 잔고, 투자 수익, 수익률 |
| 요약 | 원금, 투자 수익, 수익률, 계산 끝, 확정 여부, 진행 중 회차, 잠정 시작일, 멈춤(날짜·사유·달) |

입력: 원금(정수 원), 시작일, 계산 끝(오늘, 한국 시간), 투자처의 `{달: 금리}`, 마지막 발표 달, 세율. **DB·HTTP 없이** 단독 테스트한다
(헌법 원칙 IV). 계산 규칙과 참조값은 research R8-7.

### 이력 항목 (FR-037, FR-038)

브라우저 저장소. 주식·가상자산과 **다른 키**(`assetreplay.depositHistory.v1`). 항목: 투자처 키, 시작일, 원금. 결과 수치는 없다.
기존 키(`assetreplay:stock-history:v1`·`assetreplay:crypto-history:v1`)와 형식이 다르지만 그대로 둔다 — 바꾸면 저장된 이력을 옮겨야 한다.
다음 자산군은 기존 형식(`assetreplay:<자산군>-history:v1`)을 따른다.

---

## 상태 전이

**금리의 달**: (없음) → **발표**(행이 생긴다). 행은 바뀌지 않는다. 미발표 달은 행이 없다 — 계산은 마지막 발표 달의 금리로 잠정
계산한다(research R8-8).

**커버리지**: (없음) → 처음 수집(항목 확인 + 전체 시계열) → `first_month`·`latest_month`·`checked_on` → 하루 한 번 다시 확인(겹침 3개월)
→ `latest_month`가 늘거나 그대로, `checked_on` = 오늘.

**수집 작업**: 005와 같다 — `RUNNING` → `SUCCEEDED` / `FAILED`. 실패하면 점유를 풀고 사유를 남긴다. 기동 시 남은 `RUNNING`은 `FAILED`
(`network`).

**회차**: 가입(확정 또는 잠정) → 만기 → 재예치(다음 회차). 잠정 회차의 뒤는 모두 잠정. 결측 달에 재예치해야 하면 멈춤.
