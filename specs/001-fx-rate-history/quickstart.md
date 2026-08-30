# Quickstart: FX 환율 축적·조회·시각화

**Feature**: 001-fx-rate-history | **Date**: 2026-08-30

이 기능이 실제로 동작함을 끝에서 끝까지 확인하는 검증 가이드다. 구현 코드는 담지 않는다 —
상세는 [data-model.md](./data-model.md)와 [contracts/](./contracts/)를 참조한다.

## 사전 준비

| 항목 | 요구 |
|------|------|
| Python | 3.14.x (헌법 v4.1.0) |
| Node.js | pnpm 또는 npm 사용 가능 |
| MySQL | 8.0+ 기동 중, 빈 데이터베이스 1개 (검증 환경은 9.6.0) |
| ECOS 인증키 | 루트 `.env`의 `ECOS_API_KEY` ([ecos.bok.or.kr](https://ecos.bok.or.kr) 발급) |

> **인증키**: `.env`에만 두고 저장소에 커밋하지 않는다 (헌법 원칙 II).
> `.gitignore`가 `.env`를 제외하고 `.env.example`만 추적한다.

### 환경 변수

**저장소 루트**의 `.env` (`.gitignore`에 포함되어 있음). `.env.example`을 복사해 채운다

```bash
ECOS_API_KEY=<발급받은 키>
DB_HOST=localhost
DB_PORT=3306
DB_NAME=assetreplay
DB_USER=<사용자>
DB_PASSWORD=<비밀번호>
```

### 데이터베이스 생성

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS assetreplay \
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

앱 전용 계정을 쓰려면 함께 생성한다(권장 — 앱이 `root`로 접속하지 않게 된다).

```bash
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'assetreplay'@'localhost' IDENTIFIED BY '<비밀번호>'; \
  GRANT ALL PRIVILEGES ON assetreplay.* TO 'assetreplay'@'localhost'; FLUSH PRIVILEGES;"
```

> MySQL 8.0+의 기본 인증은 `caching_sha2_password`이며, 접속에 `cryptography` 패키지가
> 필요하다(research R10). 의존성에 포함되어 있으므로 별도 조치는 필요 없다.

### 설치

Python 실행은 반드시 `.venv/` 내에서 하며, 인터프리터를 직접 호출한다 (헌법 "Python 가상환경 [필수]").

```bash
# 백엔드 — Python 3.14 가상환경
uv venv backend/.venv --python 3.14
VIRTUAL_ENV=backend/.venv uv pip install -e "backend[dev]"
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head   # 스키마 마이그레이션 (research R9)

# 프론트엔드
cd frontend && npm install
```

Windows에서는 `backend\.venv\Scripts\python`을 사용한다.
`uv` 대신 표준 `venv`를 쓰려면 Python 3.14 인터프리터로 직접 생성한다.

## 품질 게이트 (네트워크 불필요)

머지 전 전부 통과해야 한다. **ECOS에 접속하지 않고 통과해야 한다** (헌법 원칙 III).

```bash
backend/.venv/bin/python -m pytest --cov=src --cov-fail-under=80
backend/.venv/bin/python -m mypy --strict src
cd frontend && npm test && npm run typecheck
```

네트워크를 끊고 실행해도 결과가 같아야 한다. 실패한다면 어딘가에서 실제 API를 호출하고 있다는 뜻이다.

```bash
# 단일 테스트 실행 예
backend/.venv/bin/python -m pytest tests/unit/test_spread_calc.py::test_현금_살때_가산 -v
backend/.venv/bin/python -m pytest tests/contract -v      # ECOS 계약 테스트만
```

## 실행

```bash
# 스크립트 사용 (권장) — 이미 떠 있으면 재시작한다
./be-start.sh      # http://localhost:8080
./fe-start.sh      # http://localhost:3030

# 직접 실행
backend/.venv/bin/python -m uvicorn src.api.main:app --reload --port 8080
cd frontend && npm run dev -- --port 3030     # http://localhost:3030
```

브라우저 UI는 **3030만** 쓴다. `next.config.ts`의 rewrite가 `/api/fx/*`를 8080으로
프록시하므로 동일 출처가 되어 CORS 설정이 필요 없다(research R13). 아래 `curl` 예시는
백엔드를 직접 때리므로 8080을 쓰며, `localhost:3030/api/fx/...`로도 같은 결과가 나온다.

---

## 검증 시나리오

### 1. 최초 백필과 진행률 (US4 / FR-008, FR-034, SC-009)

```bash
curl -X POST localhost:8080/api/fx/collect -H 'Content-Type: application/json' -d '{"currency":"USD"}'
# → 202 { "jobs": [{ "currency": "USD", "jobId": 1, "joinedExisting": false }] }

curl -N localhost:8080/api/fx/progress?jobId=1
```

**기대**: `progress` 이벤트가 **10초를 넘기지 않고** 반복 도착하며 `chunksDone`이 증가한다.
완료 시 `completed` 이벤트에 `status: "succeeded"`.
365일 청크이므로 `chunksTotal`은 약 32다 (research R2).

### 2. 중단 후 재개 (FR-011, SC-004)

백필 도중 서버를 강제 종료한 뒤 재기동하고 같은 요청을 다시 보낸다.

**기대**: 새 작업의 `rangeStart`가 `fx_coverage.covered_through + 1`이다. 이미 받은 구간을
다시 요청하지 않는다. `fx_rate` 총 행 수에 중복이 없다.

```sql
SELECT currency_code, COUNT(*), COUNT(DISTINCT quote_date) FROM fx_rate GROUP BY currency_code;
-- 두 카운트가 같아야 한다 (PK가 보장하지만 명시적으로 확인)
```

### 3. 통화별 단일 작업 (FR-015a, FR-015b, SC-010)

USD 수집이 진행 중인 상태에서:

```bash
curl -X POST localhost:8080/api/fx/collect -d '{"currency":"USD"}'   # → joinedExisting: true
curl -X POST localhost:8080/api/fx/collect -d '{"currency":"JPY"}'   # → 새 작업 생성됨
```

**기대**: USD는 새 작업이 만들어지지 않고 기존 작업에 합류한다. JPY는 차단되지 않는다 (FR-015c).

```sql
-- 잠금 테이블이 통화당 1행만 허용한다 (research R6)
SELECT COUNT(*) FROM fx_collection_lock WHERE currency_code='USD';   -- 항상 1 이하
SELECT currency_code, job_id, heartbeat_at FROM fx_collection_lock;  -- 진행 중 작업 확인
```

### 4. 날짜 조회와 파생 환율 (US1, US2 / FR-016, FR-022, FR-027)

```bash
curl "localhost:8080/api/fx/rates/USD?date=2005-03-15"
```

**기대**: `status: "quoted"`, `baseRate`와 `derived` 4종, `appliedSpread`가 함께 온다.
값은 모두 **문자열**이다. 같은 요청을 반복하면 항상 같은 값이 온다 (SC-003).

**성능 (SC-001)**: 수집이 완료된 날짜의 조회는 **3초 이내**여야 한다.

```bash
curl -o /dev/null -s -w 'total: %{time_total}s\n' "localhost:8080/api/fx/rates/USD?date=2005-03-15"
```

계산 검증: `cashBuy == baseRate × (1 + cashBuy 스프레드)`를 소수 2자리 반올림 기준으로 손으로 확인한다.

### 5. 고시 없는 날 (FR-018, FR-018a, SC-007)

```bash
curl "localhost:8080/api/fx/rates/USD?date=2005-03-19"   # 토요일
```

**기대**: `status: "no_quote"`. 최상위에 `baseRate`가 **없다**. 직전 영업일 값은 `reference`
안에만 있고 `note`가 "요청하신 날짜의 값이 아님"을 밝힌다. 임의로 만들어낸 값은 어디에도 없다.

### 6. JPY 100엔 단위 (FR-007)

```bash
curl "localhost:8080/api/fx/rates/JPY?date=2020-06-15"
```

**기대**: `quoteUnit: 100`. `baseRate`는 100엔당 원화 값이며, USD와 같은 축으로 오인되지 않도록
UI에 단위가 함께 표시된다.

### 7. 스프레드 변경 반영 (US2 / FR-021, FR-025, SC-008)

```bash
curl -X PUT localhost:8080/api/fx/spreads/USD -H 'Content-Type: application/json' \
  -d '{"cashBuy":"0.005","cashSell":"0.005","remitSend":"0.001","remitReceive":"0.001"}'
curl "localhost:8080/api/fx/rates/USD?date=2005-03-15"     # derived 값이 바뀌어야 함

curl -X PUT localhost:8080/api/fx/spreads/USD -d '{"cashBuy":"-0.1", ...}'   # → 422
```

**기대**: 유효한 값은 즉시 반영되고, 범위를 벗어난 값은 `422`로 거부되며 기존 값이 유지된다.
`baseRate`는 변하지 않는다 — 파생 환율은 저장되지 않고 조회 시 계산되기 때문이다.

**성능 (SC-008)**: 스프레드 변경 후 갱신된 파생 환율 확인까지 **2초 이내**여야 한다.
UI에서 값을 저장한 시점부터 화면의 파생 환율이 바뀔 때까지를 측정한다.

### 8. 차트 시계열과 결측 표현 (US3 / FR-032, FR-033, SC-006)

```bash
curl "localhost:8080/api/fx/series?currency=USD&from=1964-05-04&to=2026-08-29&maxPoints=2000"
```

**기대**:
- `downsampled: true`, `algorithm: "lttb"`, `sourcePointCount`가 약 16,500
- `points`의 모든 값이 `fx_rate`에 실제로 존재하는 값이다 (**새로 만들어낸 값이 없다**)
- `gaps`가 `no_quote`와 `not_collected`를 구분해 담고 있다

원본 대조 검증:

```sql
-- points의 임의 표본이 실제 저장 값과 일치하는지 확인
SELECT quote_date, base_rate FROM fx_rate WHERE currency_code='USD' AND quote_date IN ('1997-12-23','2008-11-24');
```

**성능 (SC-006)**: UI에서 축적 전 구간(USD 62년) 차트를 확대·이동·값 확인했을 때 **1초 이내**에 반응해야 한다.
브라우저 개발자 도구의 Performance 탭에서 조작 시작부터 프레임 갱신 완료까지를 측정하고,
`/api/fx/series` 응답 시간을 Network 탭에서 함께 기록한다.

결측 구간은 선으로 이어지지 않아야 한다.

### 9. 차트가 유발하는 자동 수집 (FR-032a)

데이터가 비어 있는 상태에서 UI 차트 기간을 "전체"로 선택한다.

**기대**: 빈 차트가 아니라 진행 상태 화면으로 전환되고(구간이 임계값 30일 초과), 수집 완료 후
차트가 채워진다. 최근 며칠만 비어 있는 경우에는 대기 후 바로 그려진다 (FR-035).

### 10. 정정 발표 처리 (FR-003a, FR-003b, SC-003)

특정 날짜의 `fx_rate.base_rate`를 임의로 바꾼 뒤 그 구간을 재수집한다.

**기대**: 값이 출처 기준으로 되돌아오고 `updated_at`이 갱신된다. `ingested_at`은 최초 값을 유지한다.
`fx_raw_response`에는 이전·이후 응답이 **모두** 남아 있어 갱신 전 값을 추적할 수 있다.

```sql
SELECT COUNT(*) FROM fx_raw_response WHERE currency_code='USD' AND requested_from <= '2005-03-15' AND requested_to >= '2005-03-15';
-- 재수집 횟수만큼 누적되어야 한다 (자동 정리 없음 — FR-004a)
```

### 11. 호출 한도 소진 (FR-013, FR-007)

`ecos.retry_max_attempts`를 1로 낮추고 `INFO-300` 픽스처를 반환하는 스텁 소스로 교체해 수집한다.

**기대**: 작업이 `partial` 또는 `failed`로 종료되고 `lastError`에 사유가 남는다.
**이미 커밋된 구간의 데이터와 커버리지는 그대로 유효하다.** 조회는 계속 동작한다.

```bash
curl "localhost:8080/api/fx/jobs?status=failed"     # 이력이 영구 보관됨 (FR-038a)
```

실패한 작업 전건에 대해 실패 사유와 대상 구간을 별도 도구 없이 화면에서 확인할 수 있어야 한다 (SC-011).

```bash
```

### 12. 수집률 검증 (SC-002)

전체 백필 완료 후, 저장된 고시일 수를 출처가 보고한 전체 건수와 대조한다.

```sql
SELECT currency_code, COUNT(*) AS stored FROM fx_rate GROUP BY currency_code;
```

**기대**: 각 통화의 저장 건수가 출처 응답의 `list_total_count`(원본 응답 기록에서 확인 가능)와
일치한다. 차이가 있으면 어느 청크에서 누락됐는지 `fx_collection_job` 이력과 `fx_raw_response`의
요청 구간을 대조해 특정한다.

### 13. 한도 소진 없이 백필 완료 (SC-005)

전 통화 백필을 처음부터 끝까지 1회 수행한다.

```bash
curl "localhost:8080/api/fx/jobs?status=failed"
curl "localhost:8080/api/fx/jobs?status=partial"
```

**기대**: 두 조회 모두 호출 한도(`INFO-300`)를 사유로 하는 작업이 **0건**이다.
0건이 아니라면 `ecos.chunk_days`를 늘려(호출 수 감소) 또는 `ecos.chunk_delay_ms`를 늘려 재시도하고,
확인된 실제 한도를 research R1의 후속 과제에 기록한다.

---

## 완료 판정

| 확인 항목 | 근거 |
|-----------|------|
| 위 11개 시나리오 전부 기대대로 동작 | US1~US4, FR 전반 |
| 네트워크 없이 전체 테스트 통과, 커버리지 80%+ | 헌법 원칙 III |
| mypy strict, TypeScript strict 통과 | 품질 게이트 |
| 코드 전체에서 금융 계산에 `float` 미사용 | 헌법 원칙 VI |
| `simulation/`이 `repository`·`api`를 임포트하지 않음 | 헌법 원칙 IV |
| DB 접근이 전부 ORM 경유이며 원시 SQL에 사유 주석이 있음 | 헌법 v4.1.0 |
| 방언 구문이 `db/dialect.py` 밖에 없음 | 헌법 v4.1.0 |
| 커넥션 풀이 적용되어 있고 풀 크기·타임아웃이 설정값임 | 헌법 v4.1.0 |
