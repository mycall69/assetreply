# Implementation Plan: FX 환율 축적·조회·시각화

**Branch**: `001-fx-rate-history` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fx-rate-history/spec.md`

## Summary

한국은행 ECOS에서 USD·JPY·EUR의 원화 매매기준율을 **통화별 출처 제공 최초일**부터 축적하고
(FR-002), 날짜별 조회와 기간별 차트를 제공한다. 스프레드를 설정하면 4종 파생 환율을 함께 산출한다.

기술적 접근은 **수집 계층의 견고함**에 집중한다. ECOS는 오류를 HTTP 200으로 반환하고 호출 한도가
있으므로, 응답 본문의 `RESULT` 코드 검사와 365일 단위 청크·청크별 커밋·중단 후 재개를 수집기의
기본 구조로 삼는다. 호출 한도 수치가 외부에서 확인되지 않았으므로, 한도를 전제하지 않고
설정값 + 런타임 백오프 + 보수적 기본값의 3중 방어로 대응한다(research R1).

도메인 계산(스프레드 적용)은 DB·HTTP에 의존하지 않는 순수 함수로 분리하여 `Decimal`로 계산한다.
차트 다운샘플링은 원본에 없는 값을 만들지 않는 LTTB를 사용한다(research R5).

저장 계층은 **RDBMS 교체 가능성**을 전제로 설계한다. 비동기 ORM과 커넥션 풀을 사용하고, 표준 SQL에
없는 두 지점(멱등 upsert, 통화별 단일 작업 잠금)을 각각 방언 헬퍼 한 곳과 표준 잠금 테이블로
격리한다(research R6, R12).

## Technical Context

**Language/Version**: Python 3.14.x (백엔드), TypeScript 5.0+ (프론트엔드)

**Primary Dependencies**: FastAPI, aiohttp, SQLAlchemy 2.x (async), Alembic, aiomysql 드라이버
(백엔드) / Next.js 16+, React 19+, Zustand, Lightweight Charts, Tailwind CSS (프론트엔드)

**Storage**: MySQL 8.0+ (InnoDB, utf8mb4)를 현재 기본 DB로 사용하되 **RDBMS 교체 가능성을 전제**로
설계한다. 접근은 비동기 ORM 세션 + 커넥션 풀, 스키마 변경은 Alembic (research R9, R10)

**Testing**: pytest + pytest-asyncio (백엔드) / Vitest + React Testing Library (프론트엔드).
전체 스위트는 네트워크 없이 통과해야 하며, ECOS는 저장된 응답 픽스처로 계약 테스트

**Target Platform**: Windows 11 / Linux / macOS. 파일 경로는 `pathlib`, 플랫폼 종속 코드는 어댑터 분리

**Project Type**: Web application (backend + frontend 분리)

**Performance Goals**:
- 수집된 날짜 조회 3초 이내 (SC-001)
- 축적 전 구간(최장 62년) 차트 조작 1초 이내 (SC-006)
- 스프레드 변경 후 재산출 2초 이내 (SC-008)
- 수집 진행률 갱신 공백 10초 이내 (SC-009)

**Constraints**:
- 금융 계산에 `float` 금지, DB 금액 컬럼과 **ORM 필드 매핑** 모두 `FLOAT`/`DOUBLE` 금지 (헌법 VI)
- DB 접근은 ORM 경유 필수, 원시 SQL은 사유 주석과 함께 예외적으로만 (헌법 v4.1.0)
- DB 종속 문법(upsert 구문·생성 컬럼·부분 인덱스)은 방언 추상화 뒤로 격리 (헌법 v4.1.0)
- 요청 처리 경로에 동기 블로킹 호출 금지 (헌법 I)
- 테스트 커버리지 80% 이상, mypy strict 통과, TypeScript `strict: true` + `any` 금지
- 결측치 임의 보간 금지 (헌법 V) — 차트 다운샘플링 알고리즘 선택까지 구속

**Scale/Scope**:
- 환율 시계열: USD 약 16,500 + JPY 약 13,100 + EUR 약 8,600 ≈ **38,200 행**
  (통화별 제공 최초일부터 누적. USD 62년 / JPY 49년 / EUR 32년)
- 원본 응답 기록: 백필 약 146건(USD 63 + JPY 50 + EUR 33) + 일별 증분. 기한 없이 보관 (FR-004a)
- 개인 사용 규모. 다중 사용자 동시 접속 부하는 범위 밖

## Constitution Check

*GATE: Phase 0 이전 통과 필수. Phase 1 설계 후 재확인.*

헌법 v4.1.0의 9개 원칙에 대한 게이트. 각 항목은 구현 리뷰에서 판정 가능해야 한다.

| # | 원칙 | 게이트 | Phase 0 | Phase 1 |
|---|------|--------|:-------:|:-------:|
| I | 비동기 우선 | ECOS 호출은 `aiohttp`, DB는 **비동기 ORM 세션**(SQLAlchemy async + aiomysql 드라이버). 요청 경로에 `requests`/동기 드라이버/`time.sleep` 없음. 청크 간 대기는 `asyncio.sleep` | PASS | PASS |
| II | 데이터 소스 격리 | ECOS 어댑터가 `RESULT`/`TIME`/`DATA_VALUE`를 도메인 타입으로 변환. 도메인·저장 계층에 ECOS 타입 미노출. rate limit·재시도·청크 크기는 설정 선언. 인증키는 `ECOS_API_KEY` 환경변수 | PASS | PASS |
| III | TDD [필수] | 테스트 선행 커밋. 최초 실패는 예정된 것이므로 중단하지 않음. **구현 후에도 실패가 남으면 즉시 중단하고 원인을 사용자에게 보고**(회귀 포함). 커버리지 80%+. ECOS 계약 테스트 픽스처 10종(contracts/ecos-adapter.md 픽스처 표). 네트워크 없이 전체 통과 | PASS | PASS |
| IV | 모듈화 | 계층 분리: ingestion / repository / simulation / api / ui. 스프레드 산출은 DB·HTTP 무의존 순수 함수. 상위 계층은 Protocol 의존 | PASS | PASS |
| V | 데이터 정합성·재현성 | 원본 응답 분리 저장·영구 보관. `(currency, quote_date)` 유니크 + upsert. `source`/`ingested_at` 기록. 보간 금지(차트 포함). 청크별 커밋으로 재개 가능 | PASS | PASS |
| VI | 금융 계산 정확성 | 전 계산 `Decimal`. ORM 필드는 `Numeric(asdecimal=True)` → `DECIMAL(18,6)`/`DECIMAL(9,6)`. 반올림은 표시 단계 1회(`ROUND_HALF_UP`, 2자리). 참조값 테스트 동반 | PASS | PASS |
| VII | 반응형 UI | Zustand 상태 관리. 진행률 SSE 스트리밍. Lightweight Charts + 서버측 LTTB 다운샘플링 | PASS | PASS |
| VIII | 한국어 문서화 | 주석·docstring·커밋 메시지·설계 문서 한국어. 식별자는 원어 | PASS | PASS |
| — | 축적 범위 (v4.1.0) | 통화별 탐색 시작일은 설정값(`ECOS_PROBE_START_*`). 실제 최초 제공일은 수집 중 발견해 `currency.first_available_date`에 기록. **코드·스키마에 날짜 하드코딩 없음** — `test_no_hardcoded_dates.py`가 기계적으로 검사 | PASS | PASS |
| IX | MVP 점진 개발 | FX 단독 수직 슬라이스. 복수 통화 차트 비교·수익률 계산·인증은 범위 밖(spec Out of Scope). 공휴일 캘린더 미도입. ORM은 헌법 v4.1.0의 MUST이므로 YAGNI 예외 | PASS | PASS |

**Phase 0 판정: 통과.** 위반 없음.

**Phase 1 재확인 판정: 통과.** 설계 산출물이 게이트를 유지한다. 특히 네 지점에서 헌법이
설계를 직접 결정했다:

- **원칙 V가 다운샘플링 알고리즘을 결정** — 평균·OHLC 집계는 원본에 없는 값을 생성하므로
  "임의 보간 금지"에 걸린다. 원본 포인트를 선택만 하는 LTTB를 채택했다(research R5).
- **원칙 V + IX가 영업일 판정 방식을 결정** — 별도 공휴일 캘린더 대신 수집 커버리지와 값 존재
  여부로 판정한다. 캘린더를 두면 실제 고시와 어긋날 때 진실을 판정할 수 없고, 새 데이터 소스가
  하나 늘어난다(research R8).
- **v3.0.0의 DB 종속 문법 금지가 동시성 제어를 뒤집었다** — MySQL 생성 컬럼 + 유니크 인덱스 대신
  표준 SQL만 쓰는 잠금 테이블 + 하트비트로 재설계했다(research R6).
- **v3.0.0의 ORM MUST가 마이그레이션 도구 결정을 뒤집었다** — 순수 SQL + 자체 러너에서 Alembic으로
  전환했다. ORM이 필수가 되면서 이전 기각 사유가 소멸했다(research R9).

## Project Structure

### Documentation (this feature)

```text
specs/001-fx-rate-history/
├── spec.md                          # 기능 명세 (완료)
├── plan.md                          # 이 문서
├── research.md                      # Phase 0 산출물
├── data-model.md                    # Phase 1 산출물
├── quickstart.md                    # Phase 1 산출물
├── contracts/                       # Phase 1 산출물
│   ├── rest-api.md                  # 조회·스프레드·수집·차트 HTTP 계약
│   ├── sse-progress.md              # 수집 진행률 스트림 계약
│   ├── ui-chart.md                  # 차트 상호작용 계약
│   ├── ui-sketches.md               # 화면별 UI 스케치 (정보 구조·상태 배치)
│   └── ecos-adapter.md              # ECOS 어댑터 내부 계약 + 픽스처 목록
├── research-inputs/
│   └── ecos-api-notes.md            # 기존 구현에서 검증된 ECOS 사실
├── checklists/
│   └── requirements.md              # 명세 품질 체크리스트 (16/16 통과)
└── tasks.md                         # Phase 2 (/speckit-tasks 산출물 — 이 명령은 생성하지 않음)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                   # 의존성·mypy strict·pytest 커버리지 게이트
├── alembic.ini                      # Alembic 설정 (연결 URL은 env.py가 루트 .env에서 주입)
├── src/
│   ├── config/                      # 설정 선언 (rate limit, 청크 크기, 임계값, 보관 기간)
│   ├── ingestion/
│   │   ├── protocols.py             # FxRateSource Protocol — 도메인이 의존하는 인터페이스
│   │   ├── ecos/                    # ECOS 어댑터 (원칙 II: 이 경계 밖으로 ECOS 타입 미노출)
│   │   │   ├── client.py            # aiohttp 호출, RESULT 코드 판별, 재시도·백오프
│   │   │   ├── parser.py            # 응답 → 도메인 타입 변환
│   │   │   ├── item_mapping.py      # 항목코드 검증·재탐색 (FR-015)
│   │   │   └── errors.py            # INFO-100/200/300, 비-JSON 오류 분류
│   │   ├── collector.py             # 청크 분할, 청크별 커밋, 재개
│   │   └── orchestrator.py          # 백그라운드 작업 오케스트레이션, 통화 간 병행
│   ├── repository/
│   │   ├── fx_rate.py               # 시계열 upsert·조회
│   │   ├── raw_response.py          # 원본 응답 영구 보관
│   │   ├── coverage.py              # 수집 커버리지
│   │   ├── spread.py                # 스프레드 설정
│   │   ├── job.py                   # 수집 작업 이력
│   │   └── collection_lock.py       # 통화별 단일 작업 잠금 (research R6, 표준 SQL만)
│   ├── simulation/
│   │   ├── spread_calc.py           # 파생 환율 산출 (순수 함수, Decimal)
│   │   └── downsample.py            # LTTB (순수 함수)
│   ├── api/
│   │   ├── routes/                  # FastAPI 라우터
│   │   ├── services/                # 조회 오케스트레이션 (repository + simulation 조합)
│   │   │   ├── rate_query.py        # 날짜 조회, no_quote 판정, 직전 영업일
│   │   │   ├── series_query.py      # 시계열 + gaps 산출
│   │   │   └── collection_gate.py   # 동기/백그라운드 임계값 분기 (FR-035b)
│   │   └── progress.py              # SSE 진행률 스트림
│   └── db/
│       ├── engine.py                # SQLAlchemy async 엔진 + 커넥션 풀 (헌법 v4.1.0 MUST)
│       ├── session.py               # 비동기 세션 팩토리 / 의존성 주입
│       ├── models.py                # ORM 모델 — Numeric(asdecimal=True) 매핑
│       ├── dialect.py               # 방언 격리: 멱등 upsert 헬퍼 (research R12)
│       └── migrations/              # Alembic env.py + versions/ (research R9)
└── tests/
    ├── contract/                    # ECOS 응답 픽스처 기반 계약 테스트
    │   └── fixtures/                # 정상 / INFO-200 / INFO-100 / INFO-300 / 비-JSON HTML
    ├── integration/                 # 수집→저장→조회 경로, 재개, 동시성
    └── unit/                        # spread_calc, downsample, 파서, 청크 분할

frontend/
├── src/
│   ├── app/                         # Next.js App Router 페이지
│   ├── components/                  # 조회 폼, 결과 카드, 차트, 진행률, 스프레드 설정
│   ├── stores/                      # Zustand 스토어
│   └── lib/                         # API 클라이언트, SSE 구독
└── tests/
```

**Structure Decision**: 헌법 원칙 IV가 요구하는 5계층(수집 / 저장 / 도메인 계산 / API / UI)을
디렉토리 경계로 그대로 옮긴 웹 애플리케이션 구조를 채택한다. 계층 위반이 임포트 경로에서
바로 드러나게 하는 것이 목적이다.

두 가지 경계가 특히 중요하다.

- `ingestion/ecos/`는 ECOS 고유 개념이 존재할 수 있는 유일한 곳이다. 이 밖으로 나가는 값은
  `protocols.py`가 정의한 도메인 타입이어야 한다(원칙 II).
- `simulation/`은 `repository`와 `api`를 임포트하지 않는다. DB와 HTTP 없이 단독 테스트가
  가능해야 하며, 이것이 불가능해지면 원칙 IV 위반이다.
- `api/services/`는 `repository`와 `simulation`을 조합해 응답을 만드는 자리다. 계산 로직을
  여기 두지 않는다 — 계산은 `simulation/`의 순수 함수여야 하고, 여기서는 호출만 한다.
- `db/dialect.py`는 **DB 방언 구문이 존재할 수 있는 유일한 곳**이다. `repository/`의 다른 모듈이나
  상위 계층에서 `on_duplicate_key_update` 같은 방언 API를 직접 호출하면 헌법 v4.1.0 위반이다.

## Traceability

spec의 모든 요구사항이 어느 설계 산출물에서 다뤄지는지 대응시킨다. `/speckit-tasks`가 태스크를
누락 없이 도출하기 위한 근거다.

| 요구사항 | 다루는 산출물 |
|----------|---------------|
| FR-001~004b (수집·원본 보관) | data-model `fx_rate`·`fx_raw_response`, contracts/ecos-adapter |
| FR-003 (멱등 upsert의 이식성) | research R12, `db/dialect.py` |
| FR-003a/b (정정 처리) | data-model `fx_rate` 갱신 규칙, quickstart 시나리오 10 |
| FR-005~009 (청킹·설정값) | research R1·R2, contracts/ecos-adapter 설정 표 |
| FR-010~013 (청크별 커밋·재개·백오프·중단) | data-model `fx_collection_job` 상태 전이·`fx_coverage`, quickstart 시나리오 2·11 |
| FR-015a~c (통화별 단일 작업) | research R6, data-model `fx_collection_lock` 잠금 테이블 |
| FR-014 (오류를 정상 응답으로 반환) | contracts/ecos-adapter 오류 분류표, 픽스처 `info_*`·`blocked_page.html` |
| FR-015 (항목 매핑 변경) | contracts/ecos-adapter 항목 매핑 검증 |
| FR-016~020 (조회) | contracts/rest-api `GET /api/fx/rates`, research R8 |
| FR-017 (범위 밖 자동 수집) | contracts/rest-api 202 응답 |
| FR-021~027 (스프레드·파생 환율) | data-model `fx_spread`·도메인 계산, research R7, contracts/rest-api |
| FR-023 (계산식) | data-model 도메인 계산 절 |
| FR-028~033 (차트) | contracts/rest-api `GET /api/fx/series`, contracts/ui-chart, research R5 |
| FR-029~031 (기간 선택·가리키기·이동) | contracts/ui-chart, contracts/ui-sketches S3 |
| UI 상태별 화면 배치 | contracts/ui-sketches S1~S7 |
| FR-034~035b (진행률·대기 임계값) | contracts/sse-progress, research R4 |
| FR-036~038b (수집 이력·보관) | data-model `fx_collection_job` 보관 정책, contracts/rest-api `GET /api/fx/jobs` |
| FR-038 (실패 기록 미삭제) | data-model 보관 정책 — `failed`·`partial`은 정리 대상에서 제외 |
| SC-001·006·008·009 (성능) | plan Performance Goals, contracts/sse-progress, contracts/ui-chart |
| SC-002 (수집률 100%) | quickstart 시나리오 12 |
| SC-003 (재현성) | data-model `fx_rate`, quickstart 시나리오 4·10 |
| SC-004 (재개·중복 0) | quickstart 시나리오 2 |
| SC-005 (한도 초과 실패 0회) | research R1·R2, quickstart 시나리오 13 |
| SC-007 (임의 생성 값 0건) | contracts/rest-api `no_quote`, research R5, quickstart 시나리오 5·8 |
| SC-010 (동시 작업 1 이하) | research R6, data-model `fx_collection_lock`, quickstart 시나리오 3 |
| SC-011 (실패 사유 사후 확인) | contracts/rest-api `GET /api/fx/jobs`, quickstart 시나리오 11 |

## Complexity Tracking

> Constitution Check에 위반이 없으므로 비워 둔다.

정당화가 필요한 헌법 위반 없음.
