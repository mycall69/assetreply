---

description: "Task list for 014-market-dashboard"
---

# Tasks: 대시보드 — 오늘의 시장 지표 15개와 과거 추이, 세 나라의 경제 뉴스

**Input**: Design documents from `/specs/014-market-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 다음 순서를 지킨다.
- 테스트 작성 → **실패 확인** → 구현 순서다.
- **테스트를 구현보다 먼저 커밋한다.** 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes).
- **구현 뒤 테스트가 실패하면 멈추고 실패 목록과 원인 판단을 먼저 보고한다.** 원인이 테스트 쪽으로 보여도 같다. 이전에 통과하던 테스트가 실패로 바뀐 경우도 같다(006 D2).
- 외부 출처는 저장한 응답 본문 픽스처로 계약 테스트한다 — **전체 스위트는 네트워크 없이 통과한다.**

**Organization**: 사용자 스토리별로 묶는다.
- US1(오늘의 시장 지표 카드, P1)이 MVP다.
- US2(지표 화면과 이력, P2)는 US1의 카드·현재 시세 캐시 위에 더한다(잠정 꼬리·머리 값).
- US3(뉴스, P3)는 백엔드가 US1·US2와 무관하고, 화면은 US1의 대시보드 위에 칸을 더한다.
- 지표 목록·설정·Yahoo 관문·이력 테이블·저장소는 Foundational이다. 카드의 전일 종가(US1)와 이력 수집(US2)이 함께 쓴다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US11 — US4~US11은 반복 2026-10-10c·10d·10e·10f(·10g)·2026-10-11·2026-10-11b·2026-10-11c)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python은 `backend/.venv/bin/python`을 직접 호출한다(헌법 — Python 가상환경 필수).
- 린트는 `ruff check --no-cache`(CLAUDE.md)다. 테스트를 먼저 쓸 때 임포트는 구현 뒤 기준(전부 `src.*` 묶음)으로 정렬한다.
- Next 16은 `frontend/AGENTS.md`대로 `frontend/node_modules/next/dist/docs/`를 먼저 읽는다 — 동적 경로의 `params`·`searchParams`는 Promise, `redirect`는 `next/navigation`이다.

## 이 기능에서 특히 조심할 것

- **다섯 메뉴·비교·수집은 바뀌지 않는다**(FR-026, SC-010)
  - `YahooStockClient`에는 **기본값 `None`인 선택 인자 `gate`만** 더한다. 기존 계약 테스트(`tests/contract/test_yahoo_client.py` 등)는 고치지 않고 통과해야 한다(R14-10).
  - 주식 파서(`ingestion/yahoo/parse.py`)·`period_table.py`·`PerformanceChart.tsx`·`FxChart.tsx`·`lib/format.ts`는 고치지 않는다. 부르기·더하기만 한다.
  - T001이 기준 응답을 남기고 T084가 대조한다.
- **대시보드는 ECOS를 부르지 않는다**(FR-018)
  - 환율 그래프는 `repository/fx_rate`를 읽기만 한다. 모자라면 외환의 `collection_gate.ensure_background_job`에 넘긴다.
  - 환율 카드는 시장 환율(Yahoo spark)이고 **저장하지 않는다** — `fx_rate`에 쓰지 않는다.
- **가드 테스트에 걸리는 글자**
  - `test_no_interpolation`은 `backend/src`(마이그레이션 제외)에서 `backfill`·`fillna`·`ffill`·`bfill`·`interpolate`·"전일 값"·"이전 값"·"직전 값"을 **글자째로** 찾는다. 이름·주석·문구에 쓰지 않는다:
    - 처음 받는 오래된 청크 → `older_chunks`·"과거 구간"
    - 화면 문구 "전일 값: 출처(이력에 아직 없음)"는 **프론트엔드에만** 둔다(서버 응답은 `previous.from` 코드)
    - 백엔드 주석은 "전일 종가"로 쓴다
  - `test_no_hardcoded_dates`는 `src`(마이그레이션 포함)의 ISO 날짜 리터럴과 `date(1927, …)` 호출을 막는다. 첫 거래일은 `firstTradeDate`에서 발견한다. 거래 시간표는 시각(`time(9, 0)`)뿐이다.
  - `test_no_float`(`simulation`·`repository`·`db`). 출처 JSON은 `json.loads(body, parse_float=Decimal)`로 읽어 `float`를 만들지 않는다.
  - `test_layer_boundaries` — `simulation`은 `api`·`repository`·`db`·`ingestion`을 부르지 않는다. 심볼 대응은 `ingestion/yahoo/market_symbols.py`에만 둔다.
  - `test_worker_isolation` — `worker`는 `api.routes`를 부르지 않는다.
  - `test_dialect_isolation` — 방언 문법은 `db/dialect.py`뿐이다(커버리지 갱신은 `upsert`, 종가는 "새 날만 삽입"이라 방언 없음).
- **값을 만들지 않는다**(원칙 V)
  - 휴장일 행을 만들지 않는다. 종가 `null` 행·오늘(현지) 봉은 저장하지 않는다.
  - 바뀐 확정 값을 덮어쓰지 않는다(개정 표).
  - 등락률을 못 내면 `null` + 까닭이다(0으로 메우지 않는다).
- **날짜는 `zoneinfo`다**(R14-3) — 응답의 `gmtoffset`으로 날짜를 바꾸지 않는다. 겨울 CL=F 자정 행 픽스처가 이를 지킨다.
- **차트 테스트의 모의 객체**(CLAUDE.md 010·011)
  - 새 `IndicatorChart`는 자기 테스트 파일에서 필요한 API(`timeScale().setVisibleLogicalRange` 등)를 모의한다. 페이지 테스트는 `@/components/dashboard/IndicatorChart`를 통째로 모의한다.
  - 기존 차트 테스트의 모의에는 손대지 않는다. "N passed"만 보지 말고 **종료 코드**를 본다(011 T036).
- **바뀌는 기존 테스트는 research R14-16의 목록이고, 승인을 받은 뒤에만 고친다**(T018)
  - 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만든다(013 T006과 같은 절차).
  - 목록 밖의 실패는 결함으로 보고 멈춘다.
- **원칙 II 이탈의 장치를 지킨다**(plan Complexity Tracking — 사용자 승인 2026-10-09)
  - 뉴스는 저장하지 않는다(메모리 캐시만). 칸마다 10분에 많아야 한 번이다.
  - Yahoo는 관문을 지난다. robots 금지 경로(`/xhr` 등)를 부르지 않는다.
  - 픽스처는 **본문만** 옮긴다(주소·머리 없이). 화면·README에 출처를 밝힌다.
- **키·비밀번호를 출력하거나 셸 인자로 넘기지 않는다.**
  - 앱 DB 사용자는 `CREATE DATABASE` 권한이 없다 — 마이그레이션은 `alembic upgrade head`로만 한다.
  - `.env`는 고치지 않는다 — 임시 백엔드는 환경 변수로 덮는다.
- **개발 서버를 띄운 채 통합 테스트를 돌리지 않는다**(같은 MySQL 스키마를 다시 만든다).
- **실측 확인은 사용자 데이터를 바꾸지 않는다.**
  - 빈 DB 백필 측정(T062)은 임시 백엔드 + 임시 DB 이름으로 한다. 앱 DB 사용자가 DB를 만들 수 없으면 `assetreplay_test`를 쓰고, 끝나면 통합 테스트가 다시 만든다.
  - 개발 DB의 대시보드 표는 지우지 않는다.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 구현 전의 기준(불변 대조용 응답·기존 검사 통과 상태·DB 머리)과 의존성

- [X] T001 구현 전 기준 응답을 남긴다 (FR-026, SC-010, quickstart 6)
  - 서버를 띄운다(`./start.sh`).
  - 013의 기준 스크립트(작업용 임시 폴더의 `013-baseline/fetch.py`)로 다섯 메뉴·비교 경로 응답을 `014-baseline/before/`에 받는다.
  - 외환 `/api/fx/latest?currency=USD|JPY|EUR`, `/api/fx/series`(USD 2025-01-01~2026-09-30)도 받는다.
  - 받은 시각을 `meta.json`에 적는다.
- [X] T002 구현 전 기존 검사의 통과 상태를 기록한다 (SC-010)
  - 서버를 내린다(`./stop.sh`).
  - 백엔드 `pytest -q --cov=src`·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수와 종료 코드를 Notes에 적는다. 실패가 있으면 기능 전 실패로 기록하고 멈추고 보고한다.
- [X] T003 개발 DB의 머리 리비전이 `b3e7d5a1c924`인지 확인한다(`backend/.venv/bin/python -m alembic current`). 다르면 멈추고 보고한다 (data-model 1)
- [X] T004 `backend/pyproject.toml`에 `tzdata`를 더하고 `.venv`에 설치한다 (plan Technical Context — 크로스 플랫폼, R14-3)
  - 기존 설치 방식(`.venv/bin/python -m pip install -e .` 등 — `pyproject.toml`·README의 안내를 따른다)으로 설치한다.
  - 맥·리눅스에서는 시스템 시간대가 먼저라 동작이 바뀌지 않는다.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 지표 목록·설정·Yahoo 관문·이력 테이블·저장소·출처 픽스처. US1(카드의 이력 전일)과 US2(이력 수집·그래프)가 함께 쓴다.

**⚠️ CRITICAL**: US1·US2는 이 페이즈 뒤다. US3(뉴스)는 설정(T011) 뒤면 시작할 수 있다.

### Preparation

- [X] T005 Yahoo 픽스처를 옮긴다 — `backend/tests/contract/fixtures/market/` + `README.md` (FR-017, FR-009, R14-1)
  - 작업용 임시 폴더 `scratchpad/014-yahoo/raw/`의 본문만 옮긴다. 주소·응답 머리는 옮기지 않는다.
  - 크기는 줄인다(구간을 잘라도 JSON 구조는 그대로).
  - 옮길 것:
    - `spark_v7_1d.json`(15개 — 한 심볼을 지운 사본 `spark_v7_missing_one.json`도)
    - `q_r1d_1d_KS11.json`(휴장)·`q_r1d_1d_N225.json`·`q_r1d_1d_GSPC.json`·`q_r1d_1d_CL_F.json`·`q_r1d_1d_KRW_X.json`·`q_r1d_1d_000001.SS.json`(깨진 전일)
    - `chunk_KS11_2024_2025.json`
    - `p0_CL_F.json` — 겨울 자정 행과 2020-04-20 음수 종가가 든 구간
    - `p0_KS11.json` — `null` 행이 든 구간
    - `q_p_GSPC_open.json`(오늘 부분 봉)
    - `neg_GSPC.json` — 1927년 첫 구간만
  - 429 본문은 짧은 문자열 파일로 둔다.
  - README 표에 파일·받은 날(2026-10-09)·요청 종류(차트 청크·spark·range=1d)·담긴 상황을 적는다.

### Tests for Foundational ⚠️

- [X] T006 [P] `backend/tests/unit/test_market_indicators.py` — `simulation/market_indicators` (FR-003, FR-015, FR-018, data-model 2)
  - 정확히 15개이고 `order` 1~15다.
  - 묶음 `korea`·`us`·`asia`·`fx`·`commodity`의 구성·차례가 data-model 2 표와 같다.
  - 단위 글자: 포인트·원·원(100엔당)·USD/배럴·USD/트로이온스.
  - `kind`: `index`·`fx`·`future`·`volatility`.
  - 결측 묶음: `krx`(kospi·kosdaq), `us_equity`(넷), `cme`(wti·gold). 나머지는 `None`.
  - 이력 원천: `fx` 셋만 외환이다. 주석: `future` → `future_roll`, `fx` → `market_fx`.
  - `get(id)`는 없는 id에 `None`이다.
  - 이 모듈은 출처 심볼을 담지 않는다 — `"^"`·`"=F"`·`"=X"` 글자가 없다.
- [X] T007 [P] `backend/tests/unit/test_settings_market.py` — `config/settings` (FR-006, FR-008, FR-019, FR-023, data-model 8)
  - data-model 8 표의 모든 env(24개)에 값이 없으면 표의 기본값이다(예: `MARKET_CHUNK_DAYS=730`, `MARKET_QUOTE_CACHE_SECONDS=30`, `MARKET_HOLIDAY_DETECT_SECONDS=3600`, `DASHBOARD_SERIES_MAX_POINTS=30000`, `NEWS_CACHE_SECONDS=600`, `YAHOO_MAX_CONCURRENT_REQUESTS=2`).
  - 값을 주면 그 값이다. 최솟값(`minimum=`) 아래는 거절한다(기존 `_env_int` 관례).
  - `NEWS_*_URL` 기본값이 R14-13의 요청 주소다.
- [X] T008 [P] `backend/tests/contract/test_yahoo_gate.py` — `ingestion/yahoo/gate` (FR-019, FR-026, R14-10)
  - 동시 자리는 `YAHOO_MAX_CONCURRENT_REQUESTS`를 넘지 않는다.
  - 한 쪽이 `pause(s)`하면 그동안 다른 쪽의 `slot()`이 기다린다. 대기는 호출 시점의 `asyncio.sleep`을 찾는다 — 테스트가 가로챈다(`EcosGate` 테스트와 같은 꼴).
  - 이벤트 루프마다 관문이 따로다.
  - `YahooStockClient(settings, session=스텁)`(gate 없음)은 429 뒤 재시도·백오프가 지금 그대로다.
  - `YahooStockClient(settings, session=스텁, gate=관문)`은 429에 관문을 쉬게 하고, 같은 스텁 응답에서 돌려주는 `ChartFetch`가 gate 없을 때와 같다.
- [X] T009 [P] `backend/tests/integration/test_market_schema.py` — 마이그레이션·모델 (FR-017, SC-006, data-model 1)
  - 새 리비전의 `down_revision == "b3e7d5a1c924"`. `upgrade`·`downgrade`가 된다.
  - `market_indicator_daily`: PK `(indicator_id, trade_date)`, `indicator_id` `String(32)`, `close` `DECIMAL(20,6)` NOT NULL, `source` `String(64)` NOT NULL, `ingested_at` 기본값.
  - `market_indicator_raw.body`는 `Text(16_777_215)`(utf8mb4에서 LONGTEXT — 005·007 원본 표와 같다, T009 실측으로 고침), `(indicator_id, received_at)` 색인.
  - `market_indicator_coverage`: `indicator_id` PK, `first_day`·`covered_from`·`covered_through` NULL 허용, `last_failure_kind` `String(32)`, `last_failure_message` `String(500)`.
  - `market_close_revision`: `stored_close`·`source_close` `DECIMAL(20,6)`, 같은 `(indicator_id, trade_date, source_close)`는 한 번만(유일 색인).
  - 기존 `test_금액_컬럼에_부동소수점이_없다`가 새 표에도 통과한다.
- [X] T010 [P] `backend/tests/integration/test_market_repository.py` — `repository/market_daily` (FR-005, FR-017, FR-019, SC-003, SC-006, data-model 1)
  - `store_closes`: 없는 날만 넣고, 넣은 수를 돌려준다.
  - 있는 날의 값이 같으면 아무것도 하지 않는다. 다르면 저장 값은 그대로 두고 `market_close_revision` 한 줄을 넣는다. 같은 개정을 다시 받아도 한 줄이다. 개정 목록을 돌려준다.
  - `store_raw`는 본문을 그대로 넣는다.
  - `record_coverage`는 요청 범위를 기존 연속 구간과 합친다(받은 범위만 — 실패한 청크는 넣지 않는다). `first_day` 기록, 실패 기록·성공 기록이 된다.
  - `closes(id, start, end)`는 날짜 차례다. `previous_close(id, before)`는 `before`보다 앞선 마지막 행이다.
  - `coverage_reaches(id, day)`는 `covered_through ≥ day`다.

### Implementation for Foundational

- [X] T011 `backend/src/config/settings.py` + 저장소 루트 `.env.example` — data-model 8 표의 설정을 그 이름·기본값 그대로 더한다 (FR-006, FR-008, FR-019, FR-023)
  - `# ── 014 대시보드 ──` 묶음에 둔다. 초 단위 env는 기존 도우미(`_env_seconds_ms` 등)의 관례를 따른다.
  - `.env.example`에 줄마다 한국어 설명을 단다.
- [X] T012 [P] `backend/src/simulation/market_indicators.py` — 고정 15개(data-model 2): `Indicator`(frozen dataclass), `INDICATORS`, `get(id)`, 묶음 이름표. 출처 심볼 없음 (FR-003, FR-015, FR-018)
- [X] T013 [P] `backend/src/ingestion/yahoo/market_symbols.py` — 지표 id ↔ 차트·spark 심볼·값 배수(`jpy` = `Decimal(100)`, 나머지 1). 대응의 유일한 곳이다 (FR-003, FR-018, R14-1)
- [X] T014 `backend/src/ingestion/yahoo/gate.py` + `backend/src/ingestion/yahoo/client.py` (FR-019, FR-026, R14-10)
  - `YahooGate(limit)`의 `slot()`·`pause(seconds)`, `get_yahoo_gate(settings)`(이벤트 루프마다 하나 — `ingestion/ecos/gate.py`와 같은 꼴).
  - `YahooStockClient.__init__`에 키워드 인자 `gate: YahooGate | None = None`을 더한다. `_get`은 gate가 있으면 `slot()` 안에서 보내고, 429면 백오프만큼 `pause`한다. 없으면 지금 그대로다.
- [X] T015 `backend/src/db/models.py` + `backend/src/db/migrations/versions/<12hex>_대시보드_지표.py` — data-model 1의 테이블 넷 (FR-017, FR-019, SC-006)
  - 형·제약을 data-model 1 그대로 둔다: `PRICE = Numeric(20, 6)`, `String(32)`·`String(64)`·`String(500)`, `Text(16_777_215)`(LONGTEXT), `TS = DateTime(timezone=False)`, 개정 유일 색인.
  - 독스트링 관례: 제목(014)·설명·Revision ID·Revises·Create Date.
- [X] T016 `backend/src/repository/market_daily.py` — T010의 함수들 (FR-005, FR-017, FR-019, SC-006)
  - `SOURCE = "yahoo:chart"`.
  - 종가는 ORM 조회 + 삽입(1000개씩). 커버리지는 `db/dialect.upsert`(`preserve=()`).
  - 개정은 유일 색인 충돌을 무시하지 않고 미리 조회해 거른다(방언 문법 없음).
- [X] T017 `backend/src/api/main.py` + `backend/src/api/routes/stock_search.py` — 관문을 주식 클라이언트에 넘긴다 (FR-019, FR-026, R14-10)
  - `lifespan`의 `YahooStockClient(settings, gate=get_yahoo_gate(settings))`, 검색 경로의 요청마다 클라이언트도 같다.
  - 주식 수집 통합 테스트·검색 테스트가 고치지 않고 통과한다.

**Checkpoint**: T006~T010 통과. 기존 주식·외환 테스트가 그대로 통과한다. 개발 DB에 `alembic upgrade head`.

---

## Phase 3: User Story 1 - 오늘의 시장 지표를 한 화면에서 본다 (Priority: P1) 🎯 MVP

**Goal**:
- `/dashboard`(최상위 `/`도 그리로 간다)에 오늘 날짜(KST·요일)와 지표 15개 카드를 다섯 묶음으로 보인다.
- 카드는 현재 값·전일 대비 차이·등락률·기준 시각·장 상태(다섯)·잠정·지연·주석을 보인다.
- 전일은 그 시장의 현지 날짜 기준 직전 거래일 종가다 — 저장된 이력에서 읽고, 없으면 출처 값과 그 표시다.
- 카드마다 따로 실패한다. 보이는 동안 60초마다 다시 받는다.

**Independent Test**: 2026-10-09(한글날) 오후 2시 30분 픽스처·가짜 시계로 다음을 확인한다(spec US1 Independent Test, quickstart 1·3·4·5-1~5-3).
- KOSPI·KOSDAQ "휴장"과 10-08 종가, 10-07 대비가 보인다.
- 니케이는 장중 ⏳ 잠정이다.
- 미국은 10-08(현지) 종가로 "마감"이다.
- 이력 행이 있으면 `previous.from = "history"`다.

### Tests for User Story 1 ⚠️

- [X] T018 [US1] 기존 테스트 변경 승인을 받는다 — research R14-16의 목록 (FR-001)
  - 절차: 이 페이즈의 테스트(T019~T030)를 쓰고 구현(T031~T040)을 마친다. 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만든다.
  - 예상:
    - `frontend/tests/Sidebar.test.tsx` — 준비 안 된 항목 `["대시보드"]` → 없음, "준비중" 1 → 0, 대시보드 `li`의 초점 대상 0 단언 삭제, 링크 목록에 `/dashboard`
    - `frontend/tests/noUnbuiltAssetRoutes.test.ts` — `UNBUILT = ["dashboard"]` → `[]`, 링크 목록에 `/dashboard`, API 호출 금지 정규식에서 `dashboard`
    - (표가 전체를 고정하면) `frontend/tests/TopBarTitle.test.ts`
  - 테스트마다 "지금 단언 → 새 단언"으로 보이고 승인을 받는다. 고친 줄에 `// 014 승인 YYYY-MM-DD`를 단다. 목록 밖의 실패는 결함으로 보고 멈춘다.
- [X] T019 [P] [US1] `backend/tests/unit/test_market_session.py` — `simulation/market_session` (FR-006, FR-007, SC-009, R14-7, data-model 3)
  - **krx**: 출처 세션 시작이 10-08인데 현지 오늘이 10-09 → `holiday`. 거래일 08:30 → `pre_open`, 10:00 → `open`, 15:31 → `closed`(출처의 15:00을 쓰지 않는다).
  - **tse**: 11:45 → `break`. **hkex**: 12:30 → `break`. **sse**: 12:00 → `break`.
  - **us_equity 서머타임**: 2026-03-09(월) 한국 22:30 → `open`, 2026-03-06(금) 한국 22:30 → `pre_open`. 2026-11-02(월) 한국 23:30 → `open`, 22:45 → `pre_open`.
  - **cme**: 금 17:30 뉴욕 → `closed`, 토 → `holiday`, 일 18:30 → `open`이고 `trading_date`는 다음 월요일. 평일 17:30 → `break`(쉼).
  - **fx**: 토 → `holiday`, 일 17:30 뉴욕 → `open`.
  - **cboe**: 08:00 시카고 → `pre_open`.
  - **갱신 없는 세션**(I1 — R14-7): cme 성탄절에 일정상 세션 안이고 값 시각이 전날 세션이면 시작 30분 뒤 `pre_open`, 2시간 뒤 `holiday`다. fx 1월 1일도 같다.
    값 시각이 이번 세션 시작 뒤면 `open`이다.
  - 주말은 늘 `holiday`다.
- [X] T020 [P] [US1] `backend/tests/unit/test_market_quote.py` — `simulation/market_quote` (FR-004, FR-005, FR-007, SC-003, R14-8, R14-9, data-model 4)
  - **휴장 KS11**: 값 10-08 종가, 이력 전일 10-07 → 차이·등락률(`quantize_rate` 자리)이 나오고 0이 아니다.
  - **장중**: 값 − 이력의 `sessionDate` 앞 마지막 종가다.
  - **이력이 닿지 않음**(커버리지 끝 < `sessionDate − 1일`) → `from = "source"`, `date = None`, 값 − `fulldayChange` 사용.
  - **상해**: `chartPreviousClose = 0.0002050505` + `fulldayChange` → 맞는 전일. `fulldayChange`가 없으면 `chartPreviousClose`다.
  - **환율**: 늘 `source_fx`. `jpy`는 8.449 → `844.900000`(×100 정확).
  - **전일 −37.63** → `changeRate None` + `"non_positive_base"`, 차이는 나온다.
  - **`direction`**: up·down·flat.
  - **`provisional`**: `open`·`break` 참, 오늘 `closed` 참, 지난 거래일 `closed`·`holiday`·`pre_open` 거짓.
  - **지연**: 장중 받은 시각 − 값 시각 = 600초 → `delayMinutes = 10`, 120초 → `None`, 닫힌 장은 `None`.
  - 금액·비율 결과는 모두 `Decimal`이다.
- [X] T021 [P] [US1] `backend/tests/contract/test_yahoo_market_quotes.py` — `ingestion/yahoo/market` 시세 쪽 (FR-009, FR-018, R14-6)
  - `spark_v7_1d.json` → 15개 `SourceQuote`(가격·값 시각·`fulldayChange`·`chartPreviousClose`·세션 시작·시간대)를 `Decimal`로 읽는다.
  - 빠진 한 심볼만 `chart?range=1d&interval=1d`로 다시 부른다(요청 기록). spark가 429이면 다시 부르지 않고 관문을 쉬게 한다.
  - 요청 질의는 `symbols`가 15개, `range=1d`·`interval=1d`다.
  - 깨진 본문은 `invalid_body`, 404는 `not_found`다.
- [X] T022 [P] [US1] `backend/tests/unit/test_market_quotes_service.py` — `api/services/market_quotes` (FR-008, FR-009, SC-007, R14-6)
  - 가짜 `MarketQuoteSource`·`MarketHistoryRepository`를 쓴다.
  - 30초 안 두 호출 = 출처 한 번. 동시에 온 두 호출도 한 번이다(단일 비행). 31초 뒤는 다시 부른다.
  - 출처 실패는 10초만 기억한다. 마지막 성공 값이 있으면 그 지표는 `stale: true` + `failure`, 없으면 `status: "failed"` + `quote: None`이다.
  - 한 심볼만 빠지면 그 지표만 실패다.
  - 이력 전일·커버리지를 저장소 Protocol로 읽는다.
- [X] T023 [P] [US1] `backend/tests/integration/test_dashboard_quotes_api.py` — `GET /api/dashboard/quotes` (FR-003, FR-004, FR-005, FR-009, FR-018, SC-003, contracts A1)
  - 스텁 출처를 쓴다. 응답은 15개이고 `order` 차례다. 칸 이름·형이 contracts A1과 같다(값은 문자열).
  - `market_indicator_daily`에 10-07 행 + 커버리지를 두면 `previous.from = "history"`이고 `date = 2026-10-07`이다. 행을 지우면 `"source"`다.
  - 환율 셋은 `source_fx`이고 `notes`에 `market_fx`, 선물 둘은 `future_roll`이다.
  - `refreshAfterSeconds`는 설정값이다. 출처 전체 실패여도 200이다.
  - `fx_rate`에 아무것도 쓰지 않는다(행 수 전후 같음).
- [X] T024 [P] [US1] `frontend/tests/kstClock.test.ts` — `lib/kstClock` (FR-002, R14-15)
  - 브라우저 시간대를 `America/New_York`로 두어도 한국 날짜·요일이다(`2026년 10월 9일 (금)`).
  - 한국 23:59:30에서 다음 자정까지 30초다.
- [X] T025 [P] [US1] `frontend/tests/TodayHeader.test.tsx` — `components/dashboard/TodayHeader` (FR-002, FR-008)
  - 가짜 시계로 한국 자정을 넘기면 날짜 글자가 바뀐다.
  - 받은 시각과 [새로고침] 단추가 있고, 누르면 `onRefresh`가 불린다(contracts D1).
- [X] T026 [P] [US1] `frontend/tests/IndicatorCard.test.tsx` — `components/dashboard/IndicatorCard`·`QuoteStateLine` (FR-004, FR-005, FR-006, FR-007, FR-009, FR-015, FR-018, SC-009, contracts D2)
  - **상태**: 다섯 상태의 글자와 ⏳·`확정 전`·`약 10분 지연`이 보인다.
  - **색**: 오르면 ▲·`text-red-700`, 내리면 ▼·`text-blue-700`, flat은 회색·화살표 없음이다.
  - **전일**: `previous.from = "source"` → "전일 값: 출처(이력에 아직 없음)", `source_fx` → "런던 0시 기준"이다.
  - **주석**: `market_fx`·`future_roll`의 문구가 보인다.
  - **실패**: `stale` → "새로 받지 못함" + 기준 시각 + [다시 시도], `failed` → "—" + 까닭 + [다시 시도]다.
  - **등락률 없음**: `changeRate null` → "—"와 설명(`title`)이다.
  - **형식**: 등락률은 `formatPercent`(천 단위 쉼표), 값은 `formatRate`다.
  - **링크**: 카드는 `href="/dashboard/{id}"`이고 접근 이름은 "{이름} 추이 보기"다.
- [X] T027 [P] [US1] `frontend/tests/marketQuotesStore.test.ts` — `stores/marketQuotesStore` (FR-008, FR-009)
  - `startPolling`이 `refreshAfterSeconds`마다 부른다(가짜 시계).
  - `visibilityState = "hidden"`이면 부르지 않고, `visibilitychange`로 보이면 곧바로 부른다.
  - 늦게 온 옛 응답(`seq`)은 버린다. `retry(id)`는 같은 경로를 다시 부른다.
  - `stopPolling` 뒤에는 부르지 않는다.
  - `startPolling`을 두 번 불러도 타이머는 하나다(대시보드 → 지표 화면으로 옮겨도 갱신이 두 번 걸리지 않는다 — U1).
- [X] T028 [P] [US1] `frontend/tests/DashboardPage.test.tsx` — `app/dashboard/page.tsx` (FR-001, FR-003, FR-008, FR-009, contracts D1)
  - 묶음 다섯이 이름표(한국·미국·일본·중국·환율·원자재·변동성)와 함께 `order` 차례로 보인다.
  - 한 지표 `failed`에도 나머지 14개가 보인다.
  - 출처 줄(Yahoo Finance·한국은행 ECOS)이 있다.
  - 사이드바의 "대시보드"는 `/dashboard` 링크이고 선택된 상태다(`AppShell`과 함께 그릴 때).
  - [새로고침]을 누르면 시세 경로가 한 번 더 불리고, 뉴스 경로는 불리지 않는다(U3 — contracts D1).
- [X] T029 [P] [US1] `frontend/tests/RootRedirect.test.tsx` — `app/page.tsx`가 `next/navigation`의 `redirect("/dashboard")`를 부른다(모의). 옛 안내 글("준비 중입니다")이 없다 (FR-001)
- [X] T030 [P] [US1] `frontend/tests/dashboardNoClientFinance.test.ts` — `components/dashboard/`·`stores/marketQuotesStore.ts`·`stores/indicatorSeriesStore.ts`·`stores/newsStore.ts`·`lib/dashboardApi.ts`에 `Number(`·`parseFloat(`·`parseInt(`가 없다 (FR-004, 원칙 VI — 013 `compareNoClientFinance`와 같은 꼴)
  - 차트의 그리기 전용 변환은 `IndicatorChart.tsx` 한 파일만 허용하고, 사유 주석을 요구한다.

### Implementation for User Story 1

- [X] T031 [P] [US1] `backend/src/simulation/market_session.py` — R14-7 표의 시간표(`time` 값)·`trading_date`·`market_state`·`MarketState`. `zoneinfo` (FR-006, FR-007, SC-009)
- [X] T032 [P] [US1] `backend/src/simulation/market_quote.py` — `compose_quote(indicator, source_quote, history_previous, coverage_through, now, fetched_at, settings값)` → `MarketQuote`(data-model 4). `Decimal`과 `quantize_rate` (FR-004, FR-005, FR-007, SC-003)
- [X] T033 [US1] `backend/src/ingestion/yahoo/market_parse.py`(시세 쪽) + `backend/src/ingestion/yahoo/market.py`(`YahooMarketClient.fetch_quotes(symbols)`) (FR-009, FR-018, R14-6)
  - `async with`로 세션을 연다(UA·`Accept: application/json` — 주식 클라이언트와 같은 꼴). 늘 `YahooGate`를 지난다.
  - 재시도·백오프는 `MARKET_RETRY_*`, 오류 분류는 `ingestion/yahoo/errors.raise_for_response`를 쓴다.
  - spark에 빠진 심볼만 차트 `range=1d`로 받는다. 본문은 `json.loads(parse_float=Decimal)`로 읽는다.
- [X] T034 [US1] `backend/src/api/services/market_quotes.py` — Protocol `MarketQuoteSource`·`MarketHistoryRepository`, 캐시(30초)·단일 비행(`asyncio.Lock`)·실패 기억(10초)·지표별 마지막 성공 값, 응답 JSON 조립(contracts A1) (FR-005, FR-008, FR-009, SC-007)
- [X] T035 [US1] `backend/src/api/routes/dashboard_quotes.py` + `backend/src/api/main.py` (FR-003, FR-009, contracts A1)
  - `lifespan`에서 `YahooMarketClient`를 열고 닫는다. 시세 서비스를 앱 상태에 둔다.
  - 라우터는 기존 라우터 뒤에 등록한다.
- [X] T036 [P] [US1] `frontend/src/lib/types.ts`(대시보드 시세 타입 — contracts A1) + `frontend/src/lib/dashboardApi.ts`(`fetchQuotes` — 공통 `request`) (FR-003, FR-004)
- [X] T037 [P] [US1] `frontend/src/lib/kstClock.ts` — `Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", … })`, `msUntilNextKstMidnight(now)` (FR-002, R14-15)
- [X] T038 [US1] `frontend/src/stores/marketQuotesStore.ts` — data-model 7 (`load`·`startPolling`·`stopPolling`·`retry`, `seq`, `document.visibilityState`) (FR-008, FR-009)
- [X] T039 [US1] `frontend/src/components/dashboard/TodayHeader.tsx`·`IndicatorGroups.tsx`·`IndicatorCard.tsx`·`QuoteStateLine.tsx` — contracts D1·D2. 값은 서버 문자열에 형식만 입힌다. `TodayHeader`의 [새로고침]은 `marketQuotesStore.load()`다 (FR-002, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-015, FR-018)
- [X] T040 [US1] 화면 경로를 붙인다 (FR-001, R14-14, contracts D6)
  - `frontend/src/app/dashboard/page.tsx`(마운트에 `load`·`startPolling`, 언마운트에 `stopPolling`).
  - `frontend/src/app/page.tsx` → `redirect("/dashboard")`(옛 안내 자리 삭제).
  - `frontend/src/components/shell/Sidebar.tsx` → `{ label: "대시보드", href: "/dashboard" }`.
  - `frontend/src/components/shell/TopBar.tsx` → `["/dashboard", "대시보드"]`를 `/`보다 앞에.
- [X] T041 [US1] 실측 확인 — quickstart 5-1~5-3을 헤드리스 Chrome(CDP)으로 확인하고 `quickstart.md` 8에 기록한다 (FR-001, FR-005, FR-006, SC-003)
  - 휴장일이 아니면 주말 또는 다른 시장의 휴장으로 5-3을 확인한다.
  - 카드의 현재 값을 출처의 같은 순간 값과 대조한다.

**Checkpoint**: 대시보드에 카드 15개가 보이고, 상태·전일·실패가 규칙대로다. 다른 메뉴는 그대로다.

---

## Phase 4: User Story 2 - 지표를 눌러 과거 추이를 일·주·월·년 단위로 본다 (Priority: P2)

**Goal**:
- 백그라운드 워커가 12개 지표의 일별 확정 종가를 출처 최대 기간까지 받는다. 과거 구간을 받고, 하루 한 번 이어 받고, 개정을 남긴다.
- 지표 화면 `/dashboard/{id}?unit=`이 머리 값(카드와 같은 스토어)과 일·주·월·년 추이를 보인다(결측 끊김, 📅·⏳, 잠정 꼬리).
- 받는 중이면 진행, 실패하면 다시 시도다. 환율은 외환의 ECOS 이력이다.

**Independent Test**: KOSPI 이력을 받아 둔 상태에서 KOSPI 카드를 누른다(spec US2 Independent Test, quickstart 1~4·5-4~5-6).
- 첫 날부터 어제까지의 일 단위 선이 보인다.
- "월"을 누르면 매달 마지막 거래일 종가 선으로 바뀌고, 주소에 `unit=monthly`가 남는다.
- 커서 값이 같은 날 출처의 종가와 같다.

### Tests for User Story 2 ⚠️

- [X] T042 [P] [US2] `backend/tests/contract/test_yahoo_market_client.py` — `ingestion/yahoo/market` 일봉 쪽 (FR-017, FR-019, R14-2, R14-3, R14-4)
  - 겨울 CL=F 자정 행이 뉴욕 날짜다(하루 앞당겨지지 않는다 — `gmtoffset`과 다른 결과를 단언).
  - 종가 `null` 행을 버린다. `firstTradeDate`를 읽는다. 2020-04-20 −37.63을 그대로 읽는다.
  - 오늘(현지) 봉은 `today_bar`로 따로 내고 확정 목록에 넣지 않는다.
  - 청크 요청이 `interval=1d&period1&period2`다. 1970년 이전은 음수 `period1`이다(1927 구간 픽스처).
  - 숫자가 `Decimal`이다.
- [X] T043 [P] [US2] `backend/tests/unit/test_market_gaps.py` — `simulation/market_gaps` (FR-014, SC-005, R14-5)
  - 다우만 빈 평일 → `missing`, 넷 다 빈 평일 → 휴장이다.
  - SOX 첫 날 전에는 다우와 견주지 않는다.
  - 상해 국경절(10-01~10-08 빈 평일) → 휴장, 15일 공백 → 그 사이 평일 `missing`이다.
  - 주말은 늘 휴장, 커버리지 밖은 판정하지 않는다. 결과 구간이 연속 날짜로 합쳐진다.
- [X] T044 [P] [US2] `backend/tests/unit/test_indicator_periods.py` — `simulation/indicator_periods` (FR-011, FR-012, FR-013, SC-005, data-model 5)
  - **대조**: 같은 거래일 목록에서 주·월 대표일이 012 `period_table.build_table`의 대표일과 같다.
  - **년**: 12-31 이하 마지막 거래일이다.
  - **`shifted`**: 금요일 휴장 → 목요일 대표 + `shifted`, 말일·12-31도 같다.
  - **`ongoing`**: 이번 주·달·해의 점이 `ongoing`이다.
  - **잠정 꼬리**: 일 단위는 마지막 점이 `provisional`이다. 주 단위는 그 주 대표가 꼬리이면 `provisional` + `ongoing`이다.
  - **빈 기간**: 거래일이 없는 주는 점이 없다.
- [X] T045 [P] [US2] `backend/tests/unit/test_market_runner_plan.py` — `worker/market_runner`의 할 일 계획(순수 부분) (FR-017, FR-019, R14-2, R14-11)
  - 커버리지 없음 → "최근 청크"(현지 어제에서 끝나는 730일)다.
  - `first_day`가 있고 `covered_from > first_day` → 그 앞 730일 청크(첫 날에서 멈춤)다.
  - `covered_through < 현지 어제` → 이어 받기(겹침 5일)이고, 같은 현지 날짜 안에서는 한 번뿐이다.
  - 여러 지표의 차례: 최근 청크 → 이어 받기 → 과거 구간을 지표마다 돌아가며.
  - **오래 꺼짐**(U2 — R14-2): `covered_through`가 현지 어제보다 1,000일 앞이면 이어 받기 청크 둘(730일 + 나머지)이고, 겹침 5일은 첫 청크에만 있다.
  - 이름에 `backfill` 글자를 쓰지 않는다(가드).
- [X] T046 [P] [US2] `backend/tests/integration/test_market_worker.py` — `worker/market_worker`·`market_runner` (FR-016, FR-017, FR-019, SC-006, R14-11)
  - 스텁 `YahooMarketClient`를 쓴다.
  - **첫 바퀴**: 12개 지표의 최근 청크와 `first_day`가 기록된다.
  - **중단과 재개**: 한 청크를 실패시키면 커버리지에 그 범위가 없고 `last_failure_*`가 남는다. 다음 지표는 계속된다. 다음 바퀴에 그 청크부터 받는다.
  - **개정**: 겹친 날 값이 바뀐 응답이면 저장 값 그대로 + 개정 한 줄 + `collection.log`의 `market_close_revised`다.
  - **원본**: 같은 현지 날짜에 두 번 돌려도 원본 행이 늘지 않는다.
  - **깨우기**: 이벤트가 곧바로 한 바퀴를 돈다.
  - **취소**: 루프 취소는 클라이언트를 닫지 않는다 — 현재 시세 서비스와 함께 쓰는 클라이언트라 `lifespan`이 연다·닫는다(구현 중 바꿈 2026-10-10. 워커가 닫으면 카드 시세가 함께 멈춘다).
- [X] T047 [P] [US2] `backend/tests/integration/test_dashboard_series_api.py` — A2·A3·A4 (FR-010, FR-012, FR-014, FR-016, FR-018, SC-002, SC-004, contracts A2~A4)
  - **202**: 과거 구간이 남으면 `collecting` + `progress`, 실패 뒤 성공이 없으면 `failed` + `failure`다.
  - **200**: 단위 넷의 점·`gaps`(결측만)·`tailPending`이 나온다.
  - **잠정 꼬리**: 시세 캐시의 `sessionDate`가 마지막 저장일보다 뒤면 붙는다. 환율에는 붙지 않는다.
  - **점 한도**: `DASHBOARD_SERIES_MAX_POINTS`를 작게 덮으면 `downsampled: true`이고, 고른 점이 실제 행의 값이다.
  - **환율**: `usd`의 점이 같은 날 `/api/fx/series`의 `baseRate`와 같다. 외환 커버리지가 모자라면 `ensure_background_job`의 수집 표를 실은 202다(ECOS 스텁 호출 0).
  - **입력 검사**: 틀린 `unit` → daily, 없는 id → 404다.
  - **`POST …/collect`**: 202이고 워커 이벤트가 켜진다.
  - **SSE**: `snapshot`·`completed`·`failed`가 나온다(커버리지 행을 바꿔 가며).
  - **수집 상태**(C1 — FR-019): 완성 뒤 실패 기록이 마지막 성공보다 뒤면 200 + `history.lastFailure{kind, message, at}`, 성공이 더 뒤면 `null`이다. `lastSuccessAt`은 커버리지 행의 값이다.
    환율은 외환 커버리지의 마지막 갱신 시각이고 `lastFailure`는 `null`이다.
- [X] T048 [P] [US2] `frontend/tests/indicatorSeriesStore.test.ts` — `stores/indicatorSeriesStore` (FR-010, FR-011, FR-016)
  - 202 → 진행 구독(모의 `EventSource`) → `completed`에 다시 요청 → `ready`다.
  - `setUnit`이 주소 바꾸기 콜백을 부른다.
  - 늦은 옛 단위 응답(`seq`)을 버린다.
  - 404 → `not_found`다. `retryCollect`가 POST를 부른다. `close`가 구독을 끊는다.
- [X] T049 [P] [US2] `frontend/tests/IndicatorChart.test.tsx` — `components/dashboard/IndicatorChart` (FR-011, FR-012, FR-013, FR-014, contracts D3)
  - 이 파일 안에서 `lightweight-charts`를 모의한다(`setVisibleLogicalRange` 포함).
  - **선 나눔**: `gaps` 구간마다 `LineSeries`가 나뉜다. 휴장(빈 날)은 나뉘지 않는다.
  - **잠정**: `provisional` 점은 연한 색 계열에 있다.
  - **처음 범위**: 일 = 마지막 약 250점, 주 260, 월 240, 년 전체다.
  - **커서 상자**: 날짜·형식 입힌 값·`📅 옮김`·`⏳ 끝나지 않은 구간`·`⏳ 잠정`이 보인다.
- [X] T050 [P] [US2] `frontend/tests/IndicatorPage.test.tsx` — 지표 화면 (FR-010, FR-011, FR-015, FR-016, FR-018, contracts D3·D4)
  - `IndicatorChart`·`next/navigation`을 모의한다.
  - **머리 값**: `marketQuotesStore`의 같은 지표 값이다.
  - **단위 단추**: `aria-pressed`이고 누르면 `router.replace("?unit=monthly", { scroll: false })`다.
  - **받는 중**: 그래프 없음 + 진행 글자다. **실패**: 까닭 + [다시 시도]다.
  - **없는 지표**: "없는 지표입니다"와 대시보드 링크다.
  - **주석**: 환율 머리에 "ECOS 매매기준율 — 카드의 시장 환율과 다른 계열", 선물 머리에 근월물 주석이다. `tailPending`이면 "최근 구간 받는 중"이다.
  - **돌아가기**: "← 대시보드로" 링크가 있다.
  - **머리 갱신**(U1 — FR-010): 마운트에 `marketQuotesStore.startPolling`, 언마운트에 `stopPolling`이 불린다(모의 스토어 호출 기록).
  - **수집 상태**(C1 — FR-019): 완성 + `lastFailure`면 그래프와 함께 머리에 "최근 이어 받기 실패 — {까닭} · {시각}" + [다시 시도]가 보인다. 머리에 "마지막 수집 {시각}"이 있다.

### Implementation for User Story 2

- [X] T051 [US2] `backend/src/ingestion/yahoo/market_parse.py`(일봉 쪽) + `backend/src/ingestion/yahoo/market.py`(`fetch_daily(symbol, date_from, date_to)` → 확정 종가·오늘 봉·`firstTradeDate`·원본 본문) (FR-017, FR-019, R14-2~R14-4)
  - 날짜는 `zoneinfo.ZoneInfo(meta["exchangeTimezoneName"])`로 바꾼다.
  - 청크 사이 간격은 `MARKET_CHUNK_DELAY_MS`다.
- [X] T052 [P] [US2] `backend/src/simulation/market_gaps.py` — R14-5 (FR-014, SC-005)
- [X] T053 [P] [US2] `backend/src/simulation/indicator_periods.py` — data-model 5(주·월은 `period_table.period_bounds`를 부른다, 년 추가) (FR-011, FR-012, FR-013, SC-005)
- [X] T054 [US2] `backend/src/worker/market_runner.py` — 할 일 계획(순수 함수) + 청크 실행 (FR-017, FR-019, SC-006, R14-11)
  - 청크마다 원본 → 종가(새 날만·개정) → 커버리지 순으로 저장하고 커밋한다.
  - 실패 기록은 `mask_secrets`를 거친다. `collection.log` 사건은 `market_chunk`·`market_close_revised`·`market_chunk_failed`다.
  - 이어 받기도 `MARKET_CHUNK_DAYS`로 나눈다(R14-2 — 오래 꺼졌다 켜진 경우).
- [X] T055 [US2] `backend/src/worker/market_worker.py` + `backend/src/api/main.py` (FR-019, R14-11)
  - `market_worker_loop`는 `MARKET_COLLECT_INTERVAL_SECONDS` 주기 + `asyncio.Event` 깨우기다. 한 지표의 실패가 루프를 끝내지 않는다.
  - `lifespan`의 아홉째 태스크로 둔다. 종료 때 취소한다.
- [X] T056 [US2] `backend/src/api/services/indicator_series.py` — `MarketHistoryRepository`로 이력을 읽는다 (FR-012, FR-014, FR-016, FR-018, FR-019, SC-002, SC-004)
  - 환율은 `repository/fx_rate.series`·커버리지를 읽는다.
  - 단위 묶기·결측·잠정 꼬리(시세 서비스의 캐시)·한도 LTTB(`simulation/downsample.lttb`)·`tailPending`·202 판정을 한다.
  - 수집 상태 `history.lastSuccessAt`·`lastFailure`(contracts A2 — FR-019)를 커버리지 행에서 싣는다.
- [X] T057 [US2] `backend/src/api/routes/dashboard_series.py` + `backend/src/api/main.py` — A2·A3·A4. SSE는 `api/collection_stream.SSE_HEADERS`·`format_sse`, 2초 폴링(`session.rollback()`). 200 응답에 수집 상태(`history.lastSuccessAt`·`lastFailure`)를 싣는다 (FR-010, FR-016, FR-019, contracts A2~A4)
- [X] T058 [P] [US2] `frontend/src/lib/dashboardApi.ts`(`fetchSeries`·`requestCollect`) + `frontend/src/lib/dashboardProgressStream.ts`(`subscribeIndicatorProgress`) + `frontend/src/lib/types.ts`(그래프 타입 — contracts A2·A4) (FR-010, FR-016)
- [X] T059 [US2] `frontend/src/stores/indicatorSeriesStore.ts` — data-model 7 (FR-010, FR-011, FR-016)
- [X] T060 [US2] `frontend/src/components/dashboard/IndicatorHeader.tsx`·`UnitPicker.tsx`·`IndicatorChart.tsx`·`SeriesCollecting.tsx` — contracts D3·D4 (FR-010~FR-016, FR-018)
  - `IndicatorChart`는 새 부품이다. `FxChart`·`PerformanceChart`를 고치지 않는다.
- [X] T061 [US2] `frontend/src/app/dashboard/[indicator]/page.tsx` — 서버 컴포넌트가 `params`·`searchParams`(Promise)를 풀어 클라이언트 부품(`components/dashboard/IndicatorView.tsx`)에 `id`·`unit`을 넘긴다. 틀린 단위는 `daily`다. `IndicatorView`는 마운트에 `marketQuotesStore.load()`·`startPolling()`, 언마운트에 `stopPolling()`을 부른다(머리 값도 보이는 동안 다시 받는다) (FR-008, FR-010, FR-011, R14-14)
- [X] T062 [US2] 실측 확인 — quickstart 5-4~5-6을 확인하고 `quickstart.md` 8에 기록한다 (FR-010, FR-016, FR-017, FR-018, SC-004, SC-006)
  - **5-5**: 임시 백엔드(환경 변수로 DB 이름·포트를 덮는다)의 빈 표에서 처음 과거 구간 수집 시간·청크 수·429 유무를 잰다.
  - 저장된 첫 날을 지표마다 출처 `firstTradeDate`와 대조한다.

**Checkpoint**: 지표 화면에서 일·주·월·년이 동작하고, 받는 중·실패·없는 지표가 규칙대로다. 환율 그래프가 외환 메뉴와 같다.

---

## Phase 5: User Story 3 - 오늘의 주요 경제 뉴스를 세 나라에서 10개씩 본다 (Priority: P3)

**Goal**:
- 대시보드 아래에 세 칸이 보인다: 네이버 증권 주요뉴스, Yahoo Finance Latest News, Yahoo!ファイナンス ヘッドライン.
- 칸마다 10개, 원문 제목·언론사·시각·유료 표시가 있다. 누르면 새 탭이다.
- 저장하지 않고 메모리에 10분 둔다. 칸마다 따로 실패하고, 0건 = 실패다.

**Independent Test**: 대시보드를 열면 세 목록이 각 출처 목록의 위쪽 최대 10개를 같은 차례로 보이고, 줄을 누르면 새 탭으로 열린다(spec US3 Independent Test, quickstart 2~4·5-7·5-8).

### Preparation for User Story 3

- [X] T063 [US3] 뉴스 픽스처를 옮긴다 — `backend/tests/contract/fixtures/news/` + `README.md` (FR-020, R14-13)
  - 작업용 임시 폴더 `scratchpad/014-news/`의 본문만 옮긴다(주소·머리 없이).
  - 옮길 것:
    - `naver_api_mainnews_p1_s20.json` — MBN 중복 두 건 포함, 15개로 줄인 사본
    - `yahoo_us_latest.html` — 목록 부분과 광고 칸을 남기고 나머지 마크업을 줄이되 선택자 구조는 그대로
    - `yahoo_us_latest_noua.html` — 429 본문
    - `yahoo_jp_headline.html` — `__PRELOADED_STATE__`가 든 줄을 남기고 줄인다
  - 구조가 바뀐 본문 셋을 만든다: 목록 칸 없는 HTML, `articles` 없는 JSON, 상태 키 없는 HTML.
  - README 표에 받은 날·요청 종류·담긴 상황을 적는다.

### Tests for User Story 3 ⚠️

- [X] T064 [P] [US3] `backend/tests/contract/test_news_naver.py` — `ingestion/news/naver` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - 주요뉴스 15개 → 같은 제목은 한 번(MBN), 위에서부터 10개다.
  - 칸: 제목 원문·언론사, `datetime` KST → UTC, 링크 `https://n.news.naver.com/article/{officeId}/{articleId}`.
  - `n.news.naver.com` 밖 링크가 없다.
  - 요청 질의: `category=MAINNEWS`·`page=1`·`pageSize=15`. UA·`Accept-Language: ko-KR`이 붙는다.
  - `articles` 없는 본문 → `parse_empty`, 403 → `blocked`, 429 → `rate_limited`, 연결 오류 → `connection`이다.
- [X] T065 [P] [US3] `backend/tests/contract/test_news_yahoo_us.py` — `ingestion/news/yahoo_us` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - 스트림 카드 10개, 광고 칸(`ad-container`) 제외다.
  - 칸: `a[title]` 제목·`href` 절대 주소·`span.publisher`·`span.published-date` 글자 그대로(`publishedText`), `publishedAt`은 `None`.
  - `finance.yahoo.com` 밖·`javascript:` 링크 줄은 버리고, 상대 주소는 절대 주소로 바꾼다(가공 본문).
  - 목록 칸 없는 HTML → `parse_empty`, 429 본문 → `rate_limited`다.
- [X] T066 [P] [US3] `backend/tests/contract/test_news_yahoo_jp.py` — `ingestion/news/yahoo_jp` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - `__PRELOADED_STATE__` → `title.name == "ヘッドライン"` 목록의 위 10개다.
  - **시각**: `"22:20"` + `currentDateTime`의 JST 날짜 → `publishedAt`, `"10/8"` → `publishedDate`. 기준이 1월인데 `"12/30"`이면 지난해다.
  - `isPaidArticle` → `paid`다.
  - `finance.yahoo.co.jp` 밖 링크 줄은 버린다.
  - 상태 키 없는 HTML → `parse_empty`다.
- [X] T067 [P] [US3] `backend/tests/unit/test_news_cache.py` — `api/services/news_cache` (FR-023, FR-024, R14-13)
  - 가짜 `NewsSource`와 가짜 시계를 쓴다.
  - **성공 캐시**: 600초 안 재요청은 출처 0회, 601초 뒤는 1회다.
  - **실패 기억**: 60초 → 연속 실패 120 → 240 → 480 → 600(상한)이고, 성공하면 처음으로 돌아간다. 남은 시간이 `retryAfterSeconds`다.
  - **단일 비행**: 동시 두 요청 = 출처 한 번이다.
  - **칸 사이**: 한 칸의 실패가 다른 칸에 영향이 없다.
- [X] T068 [P] [US3] `backend/tests/integration/test_dashboard_news_api.py` — A5 (FR-020, FR-023, FR-024, SC-007, SC-008, contracts A5)
  - 칸 셋의 성공 본문 칸 이름이 contracts A5와 같다(`sourceName`·`sourceUrl`·`list`·`items`).
  - 한 칸 실패여도 200이고 `status: "failed"` + `failure`다. 다른 칸은 성공이다.
  - 틀린 `source`는 404다. 캐시 안 재요청은 출처 스텁 호출 0이다.
- [X] T069 [P] [US3] `frontend/tests/newsStore.test.ts` — `stores/newsStore` (FR-024)
  - `loadAll`이 셋을 동시에 부르고 온 것부터 상태를 바꾼다.
  - `retry(source)`는 그 칸만 다시 부른다.
- [X] T070 [P] [US3] `frontend/tests/NewsSection.test.tsx` — `components/dashboard/NewsSection`·`NewsColumn` (FR-020, FR-021, FR-022, FR-024, FR-025, SC-008, contracts D5)
  - **칸 머리**: 나라·출처 이름(출처 화면 링크 — 새 탭)·목록 이름·받은 시각이다.
  - **링크**: 줄마다 `target="_blank"`·`rel="noopener noreferrer"`다.
  - **시각**: `publishedAt` → 한국 `HH:mm`(오늘 아니면 `MM-DD HH:mm`), `publishedDate` → `MM-DD`, `publishedText`는 그대로다.
  - **유료**: `paid`면 "유료"를 단다.
  - **실패**: `parse_empty` → "읽지 못함 — 출처 화면이 바뀌었을 수 있음" + [다시 시도]다. 그 밖의 실패 → 까닭 + [다시 시도], `retryAfterSeconds`가 남았으면 "n초 뒤 다시 시도할 수 있습니다"다.
  - **적음**: 10개보다 적으면 있는 만큼이다.
- [X] T071 [P] [US3] `frontend/tests/DashboardPageNews.test.tsx` — 대시보드에 뉴스 칸 (FR-024, SC-001, SC-007)
  - 뉴스 응답을 붙잡아 둔 채(풀지 않은 Promise) 카드 15개가 먼저 보인다.
  - 세 칸이 응답 차례대로 채워진다. 한 칸 실패에도 다른 칸·카드가 그대로다.

### Implementation for User Story 3

- [X] T072 [US3] `backend/src/ingestion/news/types.py`(`NewsItem`·`NewsList` — data-model 6) + `errors.py`(실패 종류) + `client.py`(`NewsClient` — 공통 aiohttp 세션, `NEWS_USER_AGENT`, 칸마다 `Accept-Language`, 타임아웃·재시도) (FR-020, FR-024)
- [X] T073 [P] [US3] `backend/src/ingestion/news/naver.py` — 요청 + 순수 파서(`json`) (FR-020, FR-021, FR-022, R14-13)
- [X] T074 [P] [US3] `backend/src/ingestion/news/yahoo_us.py` — 요청 + 순수 파서(`html.parser.HTMLParser` 상속 — `data-testid` 기준, 해시 클래스 `yf-*` 금지) (FR-020, FR-021, FR-022, R14-13)
- [X] T075 [P] [US3] `backend/src/ingestion/news/yahoo_jp.py` — 요청 + 순수 파서(`window.__PRELOADED_STATE__ =` 뒤를 `json.JSONDecoder().raw_decode`) (FR-020, FR-021, FR-022, R14-13)
- [X] T076 [US3] `backend/src/api/services/news_cache.py` — Protocol `NewsSource`, 칸마다 캐시·실패 백오프·단일 비행, 응답 JSON(contracts A5) (FR-023, FR-024)
- [X] T077 [US3] `backend/src/api/routes/dashboard_news.py` + `backend/src/api/main.py` — `lifespan`의 `NewsClient`, 라우터 등록 (FR-020, FR-024, contracts A5)
- [X] T078 [US3] `frontend/src/lib/dashboardApi.ts`(`fetchNews`) + `frontend/src/lib/types.ts`(뉴스 타입) + `frontend/src/stores/newsStore.ts` — data-model 7 (FR-024)
- [X] T079 [US3] `frontend/src/components/dashboard/NewsSection.tsx`·`NewsColumn.tsx` + `frontend/src/app/dashboard/page.tsx`(뉴스 칸·출처 줄) — contracts D1·D5 (FR-020~FR-022, FR-024, FR-025)
- [X] T080 [US3] 파싱 시간을 잰다 — 픽스처 본문 셋을 파서로 100번 돌린 평균 (원칙 I, plan Constitution Check)
  - 한 번이 50ms를 넘는 파서는 `run_in_executor`로 옮기고 계약 테스트를 다시 돌린다.
  - 결과를 Notes에 적는다.
- [X] T081 [US3] 실측 확인 — quickstart 5-7·5-8(임시 백엔드에서 `NEWS_US_URL`을 없는 주소로 덮어 한 칸 실패)을 확인하고 `quickstart.md` 8에 기록한다 (FR-020, FR-022, FR-024, SC-007, SC-008)
  - 10분 안 다시 열기에서 출처 호출이 없음을 서버 로그로 본다.

**Checkpoint**: 세 칸이 따로 보이고 따로 실패한다. 카드가 뉴스를 기다리지 않는다.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T082 성능을 잰다 (SC-001, SC-002, FR-012, quickstart 7)
  - 이력을 받아 둔 상태에서 `/dashboard` 탐색 시작부터 카드 15개가 그려질 때까지 잰다(2초 이내).
  - `/dashboard/sp500`의 일 단위 그래프가 그려질 때까지, 단위 전환까지 잰다(각 1초 이내).
  - 응답 크기·서버 시간·`setData` 시간을 적는다. 넘으면 멈추고 보고한다.
- [X] T083 화면 폭 확인 — quickstart 5-9(1440px·1024px에서 카드 줄바꿈·뉴스 칸 쌓임·가로 넘침 없음). 결과를 `quickstart.md` 8에 적는다 (FR-003, FR-020)
- [X] T084 불변 대조 (FR-026, SC-010, quickstart 6)
  - 서버를 띄우고 T001의 입력으로 다시 받아 `014-baseline/after/`와 견준다. 부동산은 KST 날짜 차이만 허용한다.
  - 외환 `/latest`·`/series`가 같다(그날 새 고시가 생겼으면 그 날짜 차이만).
  - 다른 키·값이 있으면 멈추고 보고한다.
- [X] T085 문서를 갱신한다 (FR-025, FR-026)
  - `CLAUDE.md`:
    - "현재 상태" 표에 014 한 줄을 더한다.
    - 원칙 II 이탈 목록에 014 넷(Yahoo 확장·네이버 내부 API·Yahoo US HTML·Yahoo JP 내장 JSON)을 더한다.
    - 주의 문단: 대시보드 수집 워커(아홉째 태스크)·Yahoo 관문을 주식과 함께 씀, 대시보드는 ECOS를 부르지 않음, 시장 환율은 저장하지 않음, `zoneinfo` 날짜, 가드 글자(`backfill`·"전일 값"), 개발 DB `alembic upgrade head`.
  - `README.md`: 기능 설명과 출처 표기(Yahoo Finance·한국은행 ECOS·네이버 증권·Yahoo Finance·Yahoo!ファイナンス).
  - `spec.md` Status를 갱신한다.
- [X] T086 품질 게이트를 돌린다(서버를 내린 채) (헌법 품질 게이트, SC-010)
  - 백엔드 `pytest -q --cov=src`(커버리지 80% 이상)·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수와 종료 코드를 Notes에 적는다.
  - 이 기능 전 커밋(`90e848b`)과 견주어 바뀌거나 지워진 기존 테스트 파일이 승인 목록(T018)뿐인지 `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests`로 확인한다.

---

## Phase 7: 반복 2026-10-10 — 출처·실패 요구 보강 (체크리스트 `checklists/sources.md`)

**Goal**: 체크리스트 37개의 권장 수정안을 반영한다. 문서로 지금 동작을 확정하고, 검토 중 찾은 결함 둘을 고친다.
- 환율 지표 화면이 외환 진행 스트림(사건 이름·모양이 다름)을 구독해 진행이 비고, 외환 수집이 실패해도 "받는 중"에 머물며, 다시 물을 때마다(15초) 외환 수집을 다시 요청한다
- 카드·뉴스 출처의 실패와 뉴스 출처 호출이 운영자가 볼 수 있는 로그에 남지 않는다

**Independent Test**: 외환 이력이 모자란 통화의 지표 화면이 대시보드 진행 경로로 진행을 보이고, 마지막 외환 수집이 실패했으면 "외환 수집 실패"와 그 문구를 보이며 외환 수집을 다시 요청하지 않는다. `collection.log`에 뉴스 출처 호출과 카드 출처 실패가 한 줄씩 남는다.

- [X] T087 문서 보강 — `spec.md`(원칙 II 보관 범위, FR-005·FR-009·FR-016·FR-018·FR-019·FR-020~FR-024, SC-001·SC-007·SC-011, Assumptions·Dependencies), `research.md`(R14-4·R14-6·R14-10·R14-13), `contracts/rest-api.md`(A0 실패 종류 표, A2·A4 환율), `contracts/ui-wireframes.md`(D4), `plan.md` 추적성, README·`.env.example`(차단 복구) (FR-005, FR-009, FR-016, FR-018~FR-024, SC-001, SC-007, SC-011)
- [X] T088 [P] `backend/tests/integration/test_dashboard_series_api.py` — 환율 경로 (FR-016, FR-018)
  - 이력이 모자라면 202 `collecting`이고 `progressUrl`은 `/api/dashboard/indicators/{id}/progress`, `progress`는 외환 커버리지다(014의 기존 기대 `"/api/fx/collection/stream?…"`을 바꾼다 — 결함을 담고 있었다).
  - 마지막 외환 수집 작업이 `failed`(또는 오류 있는 `partial`)이고 점유·큐가 없으면 202 `failed` + `failure{kind: "fx_collection", message, at}`이고 외환 수집 요청이 0번이다.
  - 큐가 그 통화를 처리 중이면 실패 기록이 있어도 `collecting`이다.
  - 진행 SSE(`stream_body`): 환율은 외환 커버리지의 `snapshot`, 실패 조건이면 `failed{kind: "fx_collection"}`, 이력이 충분해지면 `completed`다.
- [X] T089 [P] `backend/tests/unit/test_news_cache.py`·`backend/tests/unit/test_market_quotes_service.py` — 출처 사건 (FR-009, FR-023, SC-008)
  - 뉴스: 출처를 부를 때마다 `news_fetch` 한 줄(성공 `items`, 실패 `reason`)이고, 캐시·실패 기억 안의 재요청은 0줄이다.
  - 카드: 응답 전체 실패는 `market_quotes_failed{kind, detail}` 한 줄, 실패 기억 안의 재요청은 0줄, 일부 지표만 실패면 `market_quotes_partial{failed}` 한 줄이다. 성공만이면 0줄이다.
- [X] T090 [P] `frontend/tests/IndicatorPage.test.tsx` — 환율 그래프의 `fx_collection` 실패 (FR-016, FR-018)
  - "이력을 받지 못했습니다 — 외환 수집 실패"와 외환 수집 기록의 문구, [다시 시도]가 보인다.
- [X] T091 `backend/src/api/services/indicator_series.py`(`fx_state` — 외환 커버리지·작업·점유·큐로 완성·받는 중·실패를 판정, 실패면 요청하지 않음) + `backend/src/api/routes/dashboard_series.py`(경로에 큐 상태를 넘기고, 진행 SSE의 환율 갈래) (FR-016, FR-018)
- [X] T092 `backend/src/api/services/news_cache.py`(`news_fetch`)·`backend/src/api/services/market_quotes.py`(`market_quotes_failed`·`market_quotes_partial`) — `collection.log` 사건 (FR-009, FR-023)
- [X] T093 `frontend/src/components/dashboard/IndicatorHeader.tsx`(`FAILURE_LABELS`에 `fx_collection`) + `frontend/src/stores/indicatorSeriesStore.ts`(외환 진행 스트림 주석 정리) (FR-016, FR-018)
- [X] T094 게이트(서버를 내린 채)와 `CLAUDE.md`(대시보드 사건 이름·환율 경로) (SC-007, SC-010)

---

## Phase 8: 반복 2026-10-10b — 지표 모달·기간 8개·변화 까닭·일자별 표 (spec Iterations)

**Goal**:
- 지표 화면을 대시보드 위의 **주소 있는 모달**(`/dashboard/{id}?range=`)로 바꾼다
- 차트를 **보는 기간 8개**로 바꾼다. 일·주는 장중(저장 안 함), 월 이상은 저장된 일봉 전부다
- 모달 머리에 **변화 까닭**(시황 기사 1~3개 — 출처 글자 그대로, 새 탭)을 둔다
- 차트 아래 **일자별 표**(시가·고가·저가·종가·대비·등락률 — 일·주·월)를 둔다
- 일봉에 시가·고가·저가를 더하고 원본에서 되살린다

**Independent Test**(spec US2 Independent Test):
- KOSPI 카드 → 대시보드 위 모달, 주소 `/dashboard/kospi`(1년)
- "모두"는 1996년부터 일봉 전부다
- 표의 첫 줄 시가·고가·저가·종가가 같은 날 원본과 같다
- 까닭 기사가 새 탭으로 열린다
- Esc·바깥·뒤로·닫기로 닫히고 포커스가 카드로 돌아온다

**완료 작업 영향**:
- T047~T050·T053·T056~T062·T082·T083의 산출물을 다시 손댄다
- 014가 만든 테스트가 바뀌는 목록은 T111에서 승인받는다
- 014 전의 기존 테스트는 바뀌지 않아야 한다(FR-026)

### Preparation (반복 2026-10-10b)

- [X] T095 [US2] 출처 실측과 원칙 II 재승인 — `research.md` R14-17·R14-19, `plan.md` Complexity Tracking, `backend/tests/contract/fixtures/market/`·`fixtures/news/commentary/` + README (FR-027, FR-028)
  - 15개 지표마다 시황 기사 목록(네이버 증권 시황 분류·Yahoo Finance `/quote/{심볼}/news/`·Yahoo!ファイナンス 市況)과 장중 질의(`interval=5m&range=1d`·`interval=30m&range=5d`)를 실측한다.
    적을 것: 요청 머리, 목록 표지, 허용 도메인, robots.txt·약관, 점 수·지연, 세션 밖 점
  - Complexity Tracking의 새 줄 둘을 채우고 **사용자 재승인**을 받는다. 승인이 안 되면 그 갈래(T102·T103·T112·T113·T116·T118의 해당 부분)를 빼고 나머지로 간다
  - 픽스처는 본문만이다(주소·머리·토큰 없음). 원본 254개의 `open`·`high`·`low` 칸 실측(옛 구간 0·null 비율)도 R14-18에 적는다
- [X] T096 [P] [US2] 모달 경로 확인 — `node_modules/next/dist/docs/`의 가로채기(`(.)`)·병렬(`@modal`) 경로와 `default.tsx`, 사이드바·제목 판정 불변. `research.md` R14-20 (FR-010)

### Foundational (반복 2026-10-10b) — 시가·고가·저가 저장

- [X] T097 [P] [US2] `backend/tests/integration/test_market_schema.py`·`test_market_repository.py` — 새 열 셋이 `DECIMAL(20,6)` NULL이고, 저장소가 시가·고가·저가를 새 날에만 넣고 있는 날은 덮지 않는다(종가 개정 규칙 불변) (FR-017, SC-014)
- [X] T098 [P] [US2] `backend/tests/integration/test_market_ohlc_restore.py` — 원본에서 되살리기 (FR-017, FR-019, SC-014)
  - NULL인 날이 원본의 같은 날 값(소수 6자리)으로 채워진다. 두 번 돌려도 같다(멱등). 원본에 없는 날·0은 NULL이다
  - 같은 날이 원본 여럿에 있으면 가장 늦게 받은 원본이다. 종가·개정 표는 바뀌지 않는다
  - 가드(`test_no_interpolation`)에 걸리는 글자가 src에 없다
- [X] T099 [US2] `backend/src/db/migrations/versions/<rev>_대시보드_시가.py` + `backend/src/db/models.py` + `backend/src/repository/market_daily.py`(시가·고가·저가 저장·읽기) — 개발 DB `alembic upgrade head` (FR-017)
- [X] T100 [US2] 원본에서 되살리기 — `backend/src/repository/market_daily.py`(되살리기 함수) + `backend/src/worker/market_runner.py`(첫 바퀴 앞에 한 번, 멱등) + `backend/src/ingestion/yahoo/market_parse.py`(`parse_daily`가 OHLC를 낸다) (FR-017, FR-019)

### Tests for 반복 2026-10-10b ⚠️

- [X] T101 [P] [US2] `backend/tests/contract/test_yahoo_market_client.py` — 일봉 청크의 시가·고가·저가(0·null → None, 소수 6자리, 엔 ×100 아님 — 지표는 환율이 아님) (FR-017, SC-014)
- [X] T102 [P] [US2] `backend/tests/contract/test_yahoo_market_intraday.py` — `fetch_intraday(id, "1d"|"5d")`의 요청 질의·점(시각 UTC·값)·세션 밖 점·환율 심볼, 관문을 지남, 429 (FR-028)
- [X] T103 [P] [US2] `backend/tests/contract/test_news_commentary.py` — 출처마다 시황 목록 파싱(제목·요약 원문·게시 시각·허용 도메인), 목록 표지 없음 → `parse_empty` (FR-027, FR-022, SC-013)
- [X] T104 [P] [US2] `backend/tests/unit/test_indicator_table.py`·`test_indicator_range.py`·`test_indicator_commentary_select.py`·`test_indicator_intraday_cache.py` (FR-011~FR-014, FR-027~FR-029, SC-012)
  - 표: 주·월 OHLC 묶기 — 시가 = 첫 거래일, 고가·저가 = 최대·최소, 종가 = 대표일, 대비 = 앞 기간, 📅·⏳, 빈 기간 없음, null 칸
  - 기간: 일봉 자르기(1m·1y·5y·10y·20y·all — 현지 오늘 기준)
  - 까닭: 마지막 세션 이후·위에서부터 3개·없으면 `none`
  - 장중 캐시: 60초·300초
- [X] T105 [P] [US2] `backend/tests/integration/test_dashboard_series_api.py`(`range`)·`test_dashboard_table_api.py`(A7)·`test_dashboard_commentary_api.py`(A8) (FR-011, FR-012, FR-016, FR-018, FR-027~FR-029)
  - A2: 기간 8개, `unit` 무시, 장중은 202 없음
  - A7: 쪽 넘기기·`period` 400·202 같은 판정·결측 행·오늘 잠정 행·환율 행(OHLC null)
  - A8: 성공·`none`·실패 200·틀린 id 404
- [X] T106 [P] [US2] `frontend/tests/IndicatorModal.test.tsx` — 모달 (FR-010)
  - 카드 누름 → 모달 + 주소. Esc·바깥·닫기·뒤로 → 닫힘 + 포커스 카드(`data-indicator`)
  - 없는 지표 안내. 모달 동안 카드 갱신 계속. `next/navigation`·`IndicatorChart` 모의
- [X] T107 [P] [US2] `frontend/tests/RangePicker.test.tsx`·`frontend/tests/IndicatorChart.test.tsx` — 기간 단추 8개(`aria-pressed`, 주소 `range`), 장중 점의 잠정 선·커서 시각, 일봉 기간은 `fitContent`(처음 범위 없음) (FR-011, FR-012, FR-028, SC-002)
- [X] T108 [P] [US2] `frontend/tests/IndicatorTable.test.tsx`·`frontend/tests/indicatorTableStore.test.ts` (FR-013, FR-014, FR-016, FR-029, SC-012)
  - 표: 일·주·월 단추, 칸 일곱, 📅·⏳·잠정, 결측 구간 행, null → "—", 환율 머리 "고시 — 하루 한 값"
  - 스토어: 더 받기(`before`), 늦은 응답 `seq`
- [X] T109 [P] [US2] `frontend/tests/IndicatorCommentary.test.tsx` — 줄(제목·요약·출처·시각), 링크 `target="_blank"`·`rel="noopener noreferrer"`, `none` → "변화를 다룬 기사를 찾지 못했습니다", 실패·다시 시도 (FR-027, FR-022, SC-013)
- [X] T110 [P] [US2] `frontend/tests/Sidebar.test.tsx`·`frontend/tests/TopBarTitle.test.ts`·`frontend/tests/noUnbuiltAssetRoutes.test.ts`가 **고치지 않고** 통과하는지 확인 — 모달 경로에서 사이드바 "대시보드"·제목 "대시보드" (FR-010)
- [X] T111 [US2] 014가 만든 테스트의 변경 승인 — 구현을 작업 트리에 둔 뒤 실제 실패 목록을 만들어 승인받는다(T018과 같은 절차). 예상: `IndicatorPage.test.tsx`(→ 모달)·`IndicatorChart.test.tsx`(처음 범위·단위)·`indicatorSeriesStore.test.ts`(`setUnit` → `setRange`)·`test_indicator_periods.py`(년)·`test_dashboard_series_api.py`(`unit` → `range`). 구현을 치워 실패를 확인한 뒤 `test(014)` (FR-010~FR-013)

### Implementation for 반복 2026-10-10b

- [X] T112 [US2] `backend/src/ingestion/yahoo/market.py`·`market_parse.py` — `fetch_intraday`(관문·재시도·429), 일봉 OHLC (FR-017, FR-028)
- [X] T113 [P] [US2] `backend/src/ingestion/news/commentary.py`(+ 출처별 파서 — 기존 Yahoo 스트림 카드 파서 재사용) — 시황 기사 요청·파싱, 허용 도메인 (FR-027)
- [X] T114 [P] [US2] `backend/src/simulation/indicator_table.py`(순수 — 표 행, `period_table` 기준일·쪽) + `backend/src/simulation/indicator_periods.py`(년 지움 — D7) (FR-013, FR-014, FR-029)
- [X] T115 [US2] `backend/src/api/services/indicator_series.py` + `backend/src/api/routes/dashboard_series.py` — `range`(일봉 자르기·장중 갈래), `unit` 무시 (FR-011, FR-012, FR-014, FR-018)
- [X] T116 [P] [US2] `backend/src/api/services/indicator_intraday.py` — 장중 캐시(일 60초·주 300초)·단일 비행, 환율은 시장 환율 (FR-028)
- [X] T117 [US2] `backend/src/api/services/indicator_table.py` + `backend/src/api/routes/dashboard_table.py` — A7(쪽·`period`·202 같은 판정·오늘 잠정 행·환율 행) (FR-013, FR-016, FR-018, FR-029)
- [X] T118 [US2] `backend/src/api/services/indicator_commentary.py` + `backend/src/api/routes/dashboard_commentary.py` + `backend/src/api/main.py`(라우터 둘·까닭 캐시) + `backend/src/config/settings.py`(data-model §8 새 설정) — A8 (FR-027)
- [X] T119 [P] [US2] `frontend/src/lib/types.ts`·`frontend/src/lib/dashboardApi.ts` — `range`·표·까닭 (FR-011, FR-027, FR-029)
- [X] T120 [US2] `frontend/src/stores/indicatorSeriesStore.ts`(`range`)·`indicatorTableStore.ts`·`indicatorCommentaryStore.ts` — data-model §7 (FR-011, FR-016, FR-027, FR-029)
- [X] T121 [US2] `frontend/src/components/dashboard/IndicatorModal.tsx`·`RangePicker.tsx`·`IndicatorTable.tsx`·`IndicatorCommentary.tsx` + `IndicatorChart.tsx`(기간·장중)·`IndicatorView.tsx`·`IndicatorHeader.tsx`, `UnitPicker.tsx` 지움 — contracts D3·D4·D7·D8 (FR-010~FR-012, FR-027~FR-029, FR-025)
- [X] T122 [US2] `frontend/src/app/dashboard/layout.tsx`·`@modal/default.tsx`·`@modal/(.)[indicator]/page.tsx`·`[indicator]/page.tsx` — 모달 슬롯(R14-20), 새로고침·직접 입력은 대시보드 + 모달 (FR-010)

### Polish (반복 2026-10-10b)

- [X] T123 [US2] 실측 — quickstart 5-10~5-15를 확인하고 `quickstart.md` 8에 기록한다 (FR-010, FR-011, FR-017, FR-018, FR-027~FR-029, SC-013, SC-014)
- [X] T124 성능 — SC-002(모달 그래프·기간 전환 — S&P "모두")·SC-012(표 첫 쪽·단위 전환) (SC-002, SC-012)
- [X] T125 불변 대조 — `014-baseline/fetch.py`로 메뉴·비교·외환 응답을 다시 받아 견준다 (FR-026, SC-010)
- [X] T126 문서 — `CLAUDE.md`(현재 상태 014 줄·원칙 II 이탈 수·주의 문단 — 모달 경로·장중·까닭·되살리기), `README.md`(화면 설명·출처), `.env.example`(새 설정), `spec.md` Status (FR-025)
- [X] T127 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111)뿐인지 `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 9: 반복 2026-10-10c — 차트 앞 구간 스크롤·장중 실선·블랙 배경 (spec Iterations)

**Goal**:
- 지표 모달 차트의 보는 기간을 **처음 보이는 범위**로 바꾼다 — 일봉 기간은 저장된 일봉 전부를 한 번 받아 왼쪽으로 끌면 첫 날까지, 월~모두 전환은 다시 받지 않는다
- 장중은 일 = 최근 5세션 5분(처음 마지막 세션)·주 = 최근 1개월 30분(처음 최근 5세션)을 받고, 선은 확정 선과 같은 진한 실선이다
- 상단 바 오른쪽 끝에 늘 보이는 **블랙 배경** 단추 — 전 화면·차트 다섯 종, 브라우저에 기억, 깜빡임 없음(US4 — FR-030)

**Independent Test**(spec US2 시나리오 5·6, US4 Independent Test):
- S&P "1년"에서 왼쪽으로 끌면 1년 앞 일봉이 이어서 보이고 1927년까지 간다. 월~모두를 오가도 그래프 요청이 없다
- "일"은 처음 마지막 세션, 끌면 앞 네 세션. "주"는 처음 5세션, 끌면 1개월. 진한 실선
- 아무 화면에서 "블랙 배경" → 전 화면·차트가 어둡고 읽힌다. 새로고침에도 첫 그림부터 블랙. 다시 누르면 밝고, 밝은 화면은 이 반복 전과 같다

**완료 작업 영향**(사용자에게 알림 2026-10-10):
- 구현 T115·T116·T119~T121·T124를 다시 손댄다(T124의 기간만 읽기는 그래프 경로에서 빠진다)
- 014가 만든 테스트가 바뀌는 목록은 T132에서 승인받는다. 014 전 테스트는 바뀌지 않아야 한다(FR-026 — 색 변수 재정의라 클래스가 그대로)

### Preparation (반복 2026-10-10c)

- [X] T128 실측·기준선 — `research.md` R14-22·R14-23, `backend/tests/contract/fixtures/market/` + README, 작업용 임시 폴더의 기준선 스크린샷 (FR-011, FR-026, FR-028, FR-030)
  - (a) Yahoo `range=5d&interval=5m`·`range=1mo&interval=30m`(S&P·KOSPI·USD·JPY)의 점 수·null·세션 경계를 잰다. 픽스처(본문만) `intraday_GSPC_5d_5m.json`·`intraday_GSPC_1mo_30m.json`·
    `intraday_KRW_X_1mo_30m.json`을 남긴다
  - (b) **밝은 테마 기준선 스크린샷**(1440px, 헤드리스 Chrome) — 대시보드·지표 모달·외환·가상자산·주식·예금·부동산·투자 비교·설정. 구현 전에 찍는다(T139가 견준다)
  - (c) 빌드된 CSS의 유틸리티가 색 변수(`var(--color-…)`)를 쓰는지, `.dark` 재정의가 유틸리티에 닿는지 작은 확인으로 본다 — 안 되면 R14-23의 대안으로 돌아가 사용자에게 알린다

### Tests for 반복 2026-10-10c ⚠️

- [X] T129 [P] [US2] 백엔드 테스트 — 최초 실패 확인 (FR-011, FR-012, FR-028)
  - `backend/tests/contract/test_yahoo_market_intraday.py` — 일 `range=5d&interval=5m`·주 `range=1mo&interval=30m` 질의, 새 픽스처의 점(빈 종가 건너뜀·엔 ×100)
  - 새 `backend/tests/unit/test_intraday_window.py` — 마지막 세션·최근 5세션(시장 현지 날짜, 환율은 런던 0시 경계), 휴장 섞임(점 있는 날만), 점 없음 → `None`
  - `backend/tests/integration/test_dashboard_range_api.py` — 일봉 기간은 일봉 전부 + `windows`(기간 → 시작일, `all` → `null`), `range`는 처음 범위, 장중 본문의 `window`
- [X] T130 [P] [US2] 프론트 테스트 — 최초 실패 확인 (FR-011, FR-012, SC-002)
  - 새 `frontend/tests/IndicatorChartWindow.test.tsx` — 처음 범위 = `setVisibleLogicalRange({from: 창 시작 이상 첫 점의 차례, to: 마지막 차례})`, 창 안에 점이 없으면 마지막 점들,
    장중 진한 실선(확정 선 색·`lineStyle` 실선)·`window`, 기간 바꾸면 범위만(다시 그리지 않음)
  - `frontend/tests/indicatorSeriesStore.test.ts` — 월~모두 사이 전환은 다시 받지 않고 `range`·주소만, 장중 ↔ 일봉·장중끼리는 받는다
- [X] T131 [P] [US4] 테마 테스트 — 최초 실패 확인 (FR-030, SC-015)
  - 새 `frontend/tests/themeStore.test.ts` — 처음 밝게, `toggle`이 `html.dark`와 저장소(`assetreplay.theme`)를 함께 바꿈, 저장소 읽기·쓰기 실패면 밝게·오류 없음
  - 새 `frontend/tests/ThemeToggle.test.tsx` — 상단 바 오른쪽 끝에 늘 있음, `role="switch"`·이름 "블랙 배경"·`aria-checked`, 키보드(Space·Enter)
  - 새 `frontend/tests/themeScript.test.ts` — 깜빡임 방지 스크립트(글자)가 저장값 `dark`면 `dark` 클래스를 달고, 없거나 틀리거나 저장소 오류면 달지 않는다
  - 새 `frontend/tests/chartTheme.test.tsx` — 블랙이면 차트 다섯 종(`FxChart`·`PerformanceChart`·`ComparisonChart`·`CompareReturnChart`·`IndicatorChart`)이 어두운 팔레트(배경·글자·격자)로
    만들어지고, 테마를 바꾸면 다시 만들어진다. 밝으면 선택 값이 지금과 같다 — 이 파일 안에서 `lightweight-charts`를 모의한다
  - 새 `frontend/tests/darkPaletteGuard.test.ts` — src가 쓰는 색 유틸리티(`bg`·`text`·`border`·`ring`·`divide`·`from`·`to`·`fill`·`stroke` × 색 × 단계, `white`·`black`)마다
    `app/globals.css`의 `.dark` 블록에 그 색 변수의 재정의가 있다

### Implementation for 반복 2026-10-10c

- [X] T132 [US2] 014가 만든 테스트의 변경 승인 — 구현을 작업 트리에 둔 뒤 실제 실패 목록으로 승인받는다(T111과 같은 절차). 예상: `test_dashboard_range_api.py`(1년·5년·동등성)·
  `test_dashboard_series_api.py`(`sourcePointCount`)·`test_yahoo_market_intraday.py`(범위 질의)·`IndicatorChartRange.test.tsx`(처음 범위·연한 선)·`IndicatorChart.test.tsx`(범위)·
  `indicatorSeriesStore.test.ts`(기간 바꾸면 다시 받음). 구현을 치워 실패를 확인한 뒤 `test(014)` (FR-011, FR-012, FR-028)
- [X] T133 [US2] 백엔드 — `backend/src/ingestion/yahoo/market.py`(`_INTRADAY` 일 `5d·5m`·주 `1mo·30m`), 새 `backend/src/simulation/intraday_window.py`(순수 — 세션 창),
  `backend/src/api/services/indicator_intraday.py`(`window`), `backend/src/api/services/indicator_series.py`(일봉 기간 = 일봉 전부 + `windows` — T124의 기간만 읽기는 그래프에서 뺀다) — contracts A2 (FR-011, FR-012, FR-028)
- [X] T134 [US2] 프론트 — `frontend/src/lib/types.ts`·`frontend/src/lib/dashboardApi.ts`(`windows`·`window`), `frontend/src/stores/indicatorSeriesStore.ts`(일봉 본문 한 벌·월~모두는 범위만),
  `frontend/src/components/dashboard/IndicatorChart.tsx`(창 → `setVisibleLogicalRange`, 장중 진한 실선, 바닥 글자) — contracts D3 (FR-011, FR-012, SC-002)
- [X] T135 [US4] 테마 — 새 `frontend/src/stores/themeStore.ts`·`frontend/src/components/shell/ThemeToggle.tsx`, `frontend/src/components/shell/TopBar.tsx`(오른쪽 끝·스크롤해도 위),
  `frontend/src/app/layout.tsx`(깜빡임 방지 스크립트·`suppressHydrationWarning`), `frontend/src/app/globals.css`(`.dark` 팔레트 재정의·`@custom-variant dark` — 옛 "다크 모드 미지원" 주석
  대체) — contracts D6·D9 (FR-030, FR-026)
- [X] T136 [US4] 차트 테마 — 새 `frontend/src/lib/chartTheme.ts` + `frontend/src/components/FxChart.tsx`·`stock/PerformanceChart.tsx`·`stock/ComparisonChart.tsx`·`compare/CompareReturnChart.tsx`·
  `dashboard/IndicatorChart.tsx` — 테마를 효과 의존성에 넣어 다시 만든다(`applyOptions`·라이브러리 열거형을 실행 중에 쓰지 않는다), 밝은 테마의 선택 값은 지금과 같다 (FR-030, SC-015)

### Polish (반복 2026-10-10c)

- [X] T137 [US2] [US4] 실측 — quickstart 5-16~5-19를 확인하고 `quickstart.md` 8에 기록한다(헤드리스 Chrome) (FR-011, FR-012, FR-028, FR-030, SC-015)
- [X] T138 성능 — SC-002(모달 열기 — 일봉 전부를 받고 1년이 보이는 그래프 1초, 월~모두 전환은 요청 없이 0.3초, 장중) 다시 잰다 (SC-002)
- [X] T139 불변 대조 — `014-baseline/fetch.py`로 메뉴·비교·외환 응답, T128 기준선과 **밝은 테마 스크린샷**을 견준다(상단 바 단추 자리 밖 차이 0) (FR-026, SC-010, SC-015)
- [X] T140 문서 — `CLAUDE.md`(현재 상태 014 줄·블랙 테마 주의 문단 — 색 변수 재정의·차트 다시 만들기·가드), `README.md`(테마·차트 스크롤), `spec.md` Status (FR-025, FR-030)
- [X] T141 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132)뿐인지 `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 10: 반복 2026-10-10d — 외환 일자별 표의 등락폭·등락율 (spec Iterations)

**Goal**:
- 외환 메뉴의 일자별 환율 표(일·주·월) 오른쪽 끝(송금 받을 때 뒤)에 **등락폭·등락율** — 바로 아래 행 대비(일 = 직전 고시일, 주·월 = 직전 대표값)(US5 — FR-031)
- 서버가 `/api/fx/daily` 행마다 `change`를 `Decimal`로 싣고 화면은 형식만 입힌다. 계산은 `/api/fx/latest`와 같은 순수 함수다(`/latest` 응답 불변)
- 내려받기(CSV)의 맨 끝(004의 진행 중 뒤)에 같은 두 열

**Independent Test**(spec US5 Independent Test):
- 외환 USD 일 표 첫 쪽 30행의 등락이 이웃 행 매매기준율의 차·비율과 같다. 아래로 더 받은 뒤 앞 쪽 마지막 행에도 값이 있다
- 주·월로 바꾸면 직전 대표값 대비다. CSV 맨 끝에 두 열이 있고 앞 열은 그대로다. `/api/fx/latest`의 `change`는 014 전과 같다

**완료 작업 영향**: 없음 — 014의 다른 화면·경로는 그대로다. 014 전 테스트는 단언 하나가 바뀔 것으로 본다 — `frontend/tests/csv.test.ts`의 "진행 중 여부가 열로 남는다"(줄 끝 `/예$/` → 진행 중 열의 차례).
나머지 외환 테스트는 키 부분집합 검사·CSV 머리 이어짐·선택 칸이라 그대로다 — 실제 실패 목록은 T144

### Tests for 반복 2026-10-10d ⚠️

- [X] T142 [P] [US5] 백엔드 테스트 — 최초 실패 확인 (FR-031, SC-016)
  - 새 `backend/tests/unit/test_fx_change.py` — 오름·내림·같음(`direction`), `absolute`는 저장 정밀도 그대로, `percent`는 소수 둘째 자리(반올림 경계), 직전 없음 → `None`,
    직전 0 이하 → `percent` `None`
  - 새 `backend/tests/integration/test_fx_daily_change.py` — 일: 바로 아래 행(직전 고시일 — 휴장 건너뜀) 대비, 쪽 경계 행 = 쪽 너머 한 건 대비(`before`로 다음 쪽을 받아 견줌),
    저장된 첫 고시 `null`, 주·월: 직전 대표값 대비(대표일의 하루 전이 아님), 잠정 행(바로 아래 행 대비·`isProvisional` 그대로), `/api/fx/latest`의 `change`가 그대로
- [X] T143 [P] [US5] 프론트 테스트 — 최초 실패 확인 (FR-031)
  - 새 `frontend/tests/DailyTableChange.test.tsx` — 두 열이 송금 받을 때 오른쪽(머리 차례), ▲·빨강/▼·파랑/0·회색, 등락폭 `formatRate`, 등락율 부호·%(서버 글자에 부호만),
    `change`가 없거나 `null`이면 두 칸 "—", `percent`만 `null`이면 등락율만 "—", 잠정 ⚠ 그대로
  - 새 `frontend/tests/csvChange.test.ts` — 맨 끝 두 열(`…,확정 여부,원래 기준일,진행 중,등락폭,등락율`), 서버 문자열 그대로, 없으면 빈 칸

### Implementation for 반복 2026-10-10d

- [X] T144 [US5] 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록. 예상: `frontend/tests/csv.test.ts`의 "진행 중 여부가 열로 남는다"(줄 끝 `/예$/` → 진행 중 열의 차례)
  하나(뜻은 같다 — 진행 중 여부가 열로 남는다). T111과 같은 절차로 승인받고(`014 승인 2026-10-10`) 구현을 치워 실패를 확인한 뒤 `test(014)`. 목록 밖의 실패는 결함으로
  보고 멈춘다 (FR-026)
- [X] T145 [US5] 백엔드 — 새 `backend/src/simulation/fx_change.py`(순수 — `/latest`의 `_change`를 옮김), `backend/src/api/routes/latest.py`(그 함수를 부름 — 대상 고르기·응답 불변),
  `backend/src/api/services/daily_query.py`(쪽 너머 한 건을 쪽 마지막 행의 비교 대상으로 — 추가 질의 없음), `backend/src/api/routes/daily.py`(행의 `change`) — contracts A9 (FR-031)
- [X] T146 [US5] 프론트 — `frontend/src/lib/types.ts`(`DailyChange`, `PeriodRow.change?: DailyChange | null`), `frontend/src/components/fx/DailyTable.tsx`(오른쪽 끝 두 열),
  `frontend/src/lib/csv.ts`(맨 끝 두 열) — contracts D10 (FR-031)

### Polish (반복 2026-10-10d)

- [X] T147 [US5] 실측 — quickstart 5-20(외환 USD·JPY 일·주·월, 더 받기 경계, 잠정 행, CSV, 블랙 배경에서 두 열 대비)을 확인하고 `quickstart.md` 8에 기록한다(헤드리스 Chrome)
  (FR-031, SC-016)
- [X] T148 불변 대조 — `014-baseline/fetch.py`(외환 `/latest`·`/series` 차이 0, 메뉴·비교 차이 0)와 `/api/fx/daily` 행이 `change`만 더해졌는지 (FR-026, SC-010, SC-016)
- [X] T149 문서 — `CLAUDE.md`(현재 상태 014 줄·외환 표 주의), `README.md`(외환 표 설명), `spec.md` Status (FR-031)
- [X] T150 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 11: 반복 2026-10-10e — 투자 비교의 티커 표시 (spec Iterations)

**Goal**:
- 투자 비교 화면(013)의 주식·가상자산 대상 이름을 **"이름(티커)"**로 — 칩·표·막힘 안내·범례·커서 상자·막대·모달 머리·저장한 비교 목록·화면 읽기 이름(US6 — FR-032)
- 코인 검색 결과 줄의 맨 앞 이름도 같은 꼴(가상자산 메뉴와 같은 부품). 주식 검색 결과는 이미 `이름(코드)`다
- 화면만이다 — 서버·계산·저장한 비교의 조건은 그대로다

**Independent Test**(spec US6 Independent Test):
- 비교 화면에 VOO·SPY·QQQ·삼성전자(주식), 비트코인·이더리움(가상자산)을 더해 칩·표·범례·막대·모달·저장 목록이 모두 "이름(티커)"다. 저장했다 불러와도 같다
- 코인 검색 결과의 맨 앞이 `비트코인(BTC)`다(비교 화면·가상자산 메뉴). 예금·부동산 이름은 그대로, 메뉴·비교 응답은 이 반복 전과 같다

**완료 작업 영향**: 없음 — 014의 화면·경로는 그대로다. 014 전 013 테스트가 바뀔 것으로 본다(`compareCondition.test.ts`의 `targetName`, 이름으로 단추·글자를 찾는 비교 화면 테스트) —
실제 실패 목록은 T152

### Tests for 반복 2026-10-10e ⚠️

- [X] T151 [P] [US6] 화면 테스트 — 최초 실패 확인 (FR-032, SC-017)
  - 새 `frontend/tests/compareTargetTicker.test.ts` — `targetName`: KRX `삼성전자(005930)`(`.KS` 뗌)·코스닥 `.KQ`·미국 `S&P 500 뱅가드 ETF(VOO)`·`BRK-B` 그대로·일본 `.T` 뗌, 코인 한글 이름 `비트코인(BTC)`·
    한글 이름 없음 `BitShares(BTS)`, 예금·부동산 그대로. `coinNameWithSymbol`
  - 새 `frontend/tests/ComparePageTicker.test.tsx` — 비교 화면의 칩·표·범례·막대(`title` 전체 이름)·막힘 안내·모달 머리·저장 목록이 같은 "이름(티커)", 화면 읽기 이름(`… 빼기`·`… 투자 시뮬레이션`),
    이 반복 전 꼴로 저장한 조건을 불러와도 티커 — 이 파일 안에서 `lightweight-charts`를 모의한다
  - 새 `frontend/tests/CoinSearchTicker.test.tsx` — 검색 결과 줄 맨 앞 `비트코인(BTC)` 뒤 `Bitcoin`, 한글 이름 없으면 `BitShares(BTS)`, 오른쪽 `BTC · USD` 그대로, 주식 검색 결과는 이미
    `이름(코드)`(회귀 확인)

### Implementation for 반복 2026-10-10e

- [X] T152 [US6] 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록. 예상: `frontend/tests/compareCondition.test.ts`(`targetName`), 이름으로 단추·글자를 찾는 013
  화면 테스트(`ComparePage*.test.tsx`·`SimulationModal.test.tsx`·`SavedComparisons.test.tsx` 등). T111과 같은 절차로 승인받고(`014 승인 2026-10-10`) 구현을 치워 실패를 확인한 뒤
  `test(014)`. 목록 밖의 실패는 결함으로 보고 멈춘다 (FR-026)
- [X] T153 [US6] 화면 — `frontend/src/lib/displayCode.ts`(`coinNameWithSymbol`), `frontend/src/lib/compareCondition.ts`(`targetName` — 주식 `nameWithCode`, 코인 `coinNameWithSymbol`),
  `frontend/src/components/crypto/CoinSearch.tsx`(검색 결과 줄의 맨 앞 이름), `frontend/src/components/compare/CompareMetricBars.tsx`(이름 칸 `title`) — contracts D11 (FR-032)

### Polish (반복 2026-10-10e)

- [X] T154 [US6] 실측 — quickstart 5-21(비교 화면 주식 — 화면 그림의 ETF 여섯 + 삼성전자, 가상자산 — 비트코인·이더리움, 칩·표·범례·막대·모달·저장 후 불러오기, 코인 검색 결과, 가상자산 메뉴
  검색 결과, 블랙 배경, 1024px 칩 줄바꿈)을 확인하고 `quickstart.md` 8에 기록한다(헤드리스 Chrome) (FR-032, SC-017)
- [X] T155 불변 대조 — `014-baseline/fetch.py`(메뉴·비교 응답 차이 0 — 서버를 고치지 않았다)와 가상자산 메뉴 화면이 검색 결과 줄 말고 같은지 (FR-026, SC-010, SC-017)
- [X] T156 문서 — `CLAUDE.md`(현재 상태 014 줄·013 비교 화면 이름 주의), `README.md`(투자 비교 설명), `spec.md` Status (FR-032)
- [X] T157 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 12: 반복 2026-10-10f — 주식·가상자산의 상장일 (spec Iterations)

**Goal**:
- 주식·가상자산의 **상장일**을 검색 결과 줄(주식·가상자산 메뉴·투자 비교)과 투자 비교 표(주식·가상자산)의 새 열(대상과 기준일 사이)에 보인다(US7 — FR-033)
- 국내 키움 상장일, 미국·일본 Yahoo `firstTradeDate`(새 열 `stock.first_trade_date` — 표시 전용), 코인 첫 일봉. 모르면 비운다. 검색은 출처를 부르지 않는다

**Independent Test**(spec US7 Independent Test):
- 삼성전자 검색 `상장 1975-06-11`. VOO를 고른 뒤 비교 표 상장일 = Yahoo 첫 거래일 + `첫 거래일`, 비트코인 `2010-07-18` + `첫 일봉`, 모르는 코인 "—"
- 예금·부동산 표에는 열이 없다. 메뉴 시뮬레이션 응답·등록 응답은 이 반복 전과 같다

**완료 작업 영향**: 없음 — 014의 화면·경로는 그대로다. 014 전 테스트(검색·등록 응답 키, 비교 표 머리·열 수 등)가 바뀔 수 있다 — 실제 실패 목록은 T161

### Preparation (반복 2026-10-10f)

- [X] T158 실측·픽스처 — Yahoo 차트 `range=1d`(VOO·삼성전자·도요타)의 `meta.firstTradeDate`·응답 크기·시간을 재고 본문만 픽스처로(`backend/tests/contract/fixtures/stock/chart_meta_*.json` + README),
  미국 ETF 몇의 첫 거래일을 기록 — `research.md` R14-26 (FR-033)

### Tests for 반복 2026-10-10f ⚠️

- [X] T159 [P] [US7] 백엔드 테스트 — 최초 실패 확인 (FR-033, SC-018)
  - 새 `backend/tests/unit/test_listing_date.py` — 고르기 규칙(키움 → 첫 거래일 → 없음, 코인 첫 일봉 → 없음)
  - 새 `backend/tests/contract/test_yahoo_first_trade.py` — meta만 받기(`range=1d`), 거래소 시간대 날짜, `firstTradeDate` 없음 → `None`, 404·429
  - 새 `backend/tests/integration/test_stock_first_trade.py` — 스키마(`first_trade_date` DATE NULL), 등록 때 모르면 한 번 받아 저장·알면 부르지 않음·출처 실패/시간 초과/클라이언트 없음이어도 등록 성공·
    응답 불변, `collect_range` 청크의 기록(비었을 때만 — 덮지 않음), `first_available_date`·시작일 거절 불변
  - 새 `backend/tests/integration/test_listing_date_api.py` — 검색 두 응답의 `firstTradedOn`(저장된 종목만, 출처 호출 0), 비교 블록 `listing`(국내 `listing`·미국 `first_trade`·코인 `first_bar`·모름
    `null`·예금·부동산 `null`), 메뉴 시뮬레이션 응답 불변
- [X] T160 [P] [US7] 화면 테스트 — 최초 실패 확인 (FR-033)
  - 새 `frontend/tests/StockSearchListing.test.tsx` — 결과 줄 `상장 …`(국내 `listedOn`)·`첫 거래 …`(`firstTradedOn`), 둘 다 없으면 글자 없음
  - 새 `frontend/tests/CoinSearchListing.test.tsx` — `첫 일봉 …`(`firstAvailableDate`), 없으면 글자 없음
  - 새 `frontend/tests/CompareTableListing.test.tsx` — 주식·가상자산 표의 머리 차례(대상 · 상장일 · 기준일 …), 날짜·기준 작은 글자(`첫 거래일`·`첫 일봉`·키움은 없음), "—"·`title`, 정렬(비운 칸 끝),
    예금·부동산 열 없음

### Implementation for 반복 2026-10-10f

- [X] T161 [US7] 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(예상: 검색·등록 응답 키 견주기, 비교 표 머리·열 수). T111과 같은 절차로 승인받고
  (`014 승인 2026-10-10`) 구현을 치워 실패를 확인한 뒤 `test(014)`. 목록 밖의 실패는 결함으로 보고 멈춘다 (FR-026)
- [X] T162 [US7] 백엔드 — 새 마이그레이션 `backend/src/db/migrations/versions/<rev>_주식_첫_거래일.py`, `backend/src/db/models.py`, `backend/src/repository/stock.py`, 새 `backend/src/simulation/listing_date.py`,
  `backend/src/ingestion/yahoo/client.py`, `backend/src/api/services/stock_selection.py`·`backend/src/api/routes/stock_selection.py`, `backend/src/worker/stock_runner.py`, `backend/src/api/routes/stock_search.py`,
  `backend/src/api/services/comparison_metrics.py`·`backend/src/api/routes/comparison.py` — contracts A10 (FR-033)
- [X] T163 [US7] 화면 — `frontend/src/lib/types.ts`, `frontend/src/components/stock/StockSearch.tsx`, `frontend/src/components/crypto/CoinSearch.tsx`, `frontend/src/components/compare/CompareTable.tsx`,
  `frontend/src/stores/compareStore.ts`(정렬 키) — contracts D12 (FR-033)

### Polish (반복 2026-10-10f)

- [X] T164 [US7] 실측 — 개발 DB `alembic upgrade head`, quickstart 5-22(삼성전자·VOO·SPY·QQQ·도요타 검색·고르기·비교 표, 비트코인·이더리움·모르는 코인, 등록 출처 실패를 임시 백엔드로, 정렬, 블랙 배경, 1024px)를
  확인하고 `quickstart.md` 8에 기록한다(헤드리스 Chrome) (FR-033, SC-018)
- [X] T165 불변 대조 — `014-baseline/fetch.py`(메뉴 시뮬레이션 응답 차이 0, 비교 응답은 `comparison.listing`만 더해짐), 검색 응답은 `firstTradedOn`만 더해짐, 등록 응답 불변 (FR-026, SC-010, SC-018)
- [X] T166 문서 — `CLAUDE.md`(현재 상태 014 줄·상장일 주의 — 새 열·`first_available_date`와 다름·등록 실패 허용·lifespan 클라이언트만·검색은 출처를 부르지 않음), `README.md`, `spec.md` Status (FR-033)
- [X] T167 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

## Phase 13: 반복 2026-10-10g — 고른 종목·코인 줄의 상장일 (spec Iterations — 사용자 보고)

**Goal**:
- 주식·가상자산 메뉴에서 고른 종목·코인 줄(검색 칸 아래)의 종목명 밑에 상장일을 보인다(US7 — FR-034). 등록 뒤·이력 다시 실행 뒤 모두, 실행으로 알게 되면 결과·시작 가능 날짜 안내가 온 뒤
- 고른 대상의 상장일 경로 둘(A11) — 주식은 비교 경로와 같은 함수(모르면 한 번 받아 둠)

**Independent Test**(spec US7 수용 시나리오 8):
- 주식 메뉴에서 QLD를 고르면 고른 줄 밑 `첫 거래 2006-06-21`, 삼성전자 `상장 1975-06-11`, 이력 다시 실행 뒤에도 같다. 비트코인 `첫 일봉 2010-07-18`
- 등록·검색·메뉴 시뮬레이션 응답은 이 반복 전과 같다

**완료 작업 영향**: 없음 — 10f의 결과 줄·비교 표·첫 거래일 저장은 그대로다(비교 경로의 헬퍼는 서비스로 옮길 뿐 값 불변). 고른 줄을 그리는 014 전 테스트가 바뀔 수 있다 — 실제 실패
목록은 T170

### Tests for 반복 2026-10-10g ⚠️

- [X] T168 [P] [US7] 백엔드 테스트 — 새 `backend/tests/integration/test_selected_listing_api.py`(A11 — 국내 `listing`·미국 `first_trade`(출처 호출 0)·모르면 한 번 받아 저장·실패해도 200
  `listing: null`·없는 종목 404·다른 거래소 같은 티커, 코인 `first_bar`·`null`·404, 비교 블록 `listing`과 같은 글자). 최초 실패 확인 (FR-034, SC-019)
- [X] T169 [P] [US7] 화면 테스트 — 새 `frontend/tests/SelectedListing.test.tsx`·`frontend/tests/support/listingStub.ts`, `frontend/tests/setup.ts`(대역 한 겹 — 이력·저장 대역과 같은 틀,
  `014 승인 2026-10-10`). 주식·코인 고른 줄 아래 글자·`title`, 모름 `상장일 —`, 묻는 동안·실패면 줄 없음, 대상이 바뀌면 다시 묻고 늦은 답은 버림, 결과 신호가 오면 다시 묻고 비면 묻지 않음,
  이력 다시 실행 뒤 줄, 시작 가능 날짜 안내도 신호, 비교 화면 검색은 묻지 않음. 최초 실패 확인 (FR-034)

### Implementation for 반복 2026-10-10g

- [X] T170 [US7] 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(결과: **없음** — 백엔드 3,440·화면 2,036 통과, 바뀐 기존 테스트 파일은 T169의 `tests/setup.ts` 대역 한 겹뿐). T161과 같은 절차(`014 승인 2026-10-10`)로 승인하고 구현을 치워 실패를 확인한 뒤
  `test(014)`. 목록 밖의 실패는 결함으로 보고 멈춘다 (FR-026)
- [X] T171 [US7] 백엔드 — `backend/src/api/services/stock_selection.py`(`stock_listing` — `routes/comparison._stock_listing`을 옮김), `backend/src/api/routes/stock_selection.py`
  (`GET /api/stocks/listing-date`), `backend/src/api/routes/crypto_search.py`(`GET /api/crypto/listing-date`), `backend/src/api/routes/comparison.py` — contracts A11 (FR-034)
- [X] T172 [US7] 화면 — 새 `frontend/src/lib/listingApi.ts`·`frontend/src/hooks/useSelectedListing.ts`, `frontend/src/lib/listingDate.ts`, `frontend/src/components/ListingText.tsx`,
  `frontend/src/components/stock/StockSearch.tsx`, `frontend/src/components/crypto/CoinSearch.tsx`, `frontend/src/app/stocks/page.tsx`·`frontend/src/app/crypto/page.tsx`(결과·안내 신호) — contracts D13 (FR-034)

### Polish (반복 2026-10-10g)

- [X] T173 [US7] 실측 — quickstart 5-23(QLD·삼성전자·도요타 고르기, 이력 다시 실행, 비트코인, 첫 일봉을 모르는 코인 → 실행 뒤, 블랙 배경)을 헤드리스 Chrome으로 확인하고 `quickstart.md` 8에
  기록한다 (FR-034, SC-019)
- [X] T174 불변 대조·문서 — `014-baseline/fetch.py`(기준 29파일 — 부동산 기준일·`meta` 말고 차이 0), 등록·검색 응답 그대로. `CLAUDE.md`(014 줄·상장일 주의), `README.md`, `spec.md` Status
  (FR-026, SC-010, SC-019)
- [X] T175 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T170)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 14: 반복 2026-10-11 — 투자 성과표의 처음 단위 월 (spec Iterations — 사용자 요청)

**Goal**:
- 외환·가상자산·주식 메뉴와 투자 비교 모달(주식·가상자산)의 일자별 표를 처음부터 "월"로 보인다(US8 — FR-035). 고른 단위는 화면 세션에서 남는다
- 서버의 표 경로는 그대로다 — 화면이 처음 요청부터 `period=monthly`를 싣는다

**Independent Test**(spec US8):
- 외환 메뉴를 새로 열면 표의 "월"이 선택돼 있고 요청이 `period=monthly`다. 가상자산·주식 실행·이력 다시 실행, 비교 모달(주식·가상자산)도 같다
- "일"을 고른 뒤 다시 실행하면 "일"이 남는다. 예금·부동산 모달·대시보드 지표 표는 그대로다

**완료 작업 영향**: 없음 — 014의 화면·경로는 그대로다. 004·012·013의 처음 단위가 바뀐다(FR-026 예외). 처음 값·처음 요청 글자를 단언하는 014 전 테스트가 바뀐다 — 범위 확인(구현을
작업 트리에 둔 전체 스위트)에서 12파일 22개, 실제 목록은 T177

### Tests for 반복 2026-10-11 ⚠️

- [X] T176 [P] [US8] 화면 테스트 — 새 `frontend/tests/TablePeriodDefault.test.tsx`. 외환 화면 처음 "월" 탭·첫 표 요청 `period=monthly`, 주식·가상자산 스토어 처음 값 `monthly`·처음 실행(일시금·적립식)
  표 요청 `&period=monthly`·시계열 요청에는 없음, 화면의 "월" 탭, 이력 다시 실행도 월, "일"로 바꾼 뒤 다시 실행하면 `period` 없음(고른 단위 유지), 비교 모달 열기의 표 요청 `&period=monthly`(주식·
  가상자산 — 예금·부동산은 없음)·모달 "월" 탭·닫고 다시 열면 월, 대시보드 지표 표 처음 `daily`. 최초 실패 확인 (FR-035, SC-020)

### Implementation for 반복 2026-10-11

- [X] T177 [US8] 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(결과: 범위 확인과 같은 **12파일 22개** — 승인 뒤 229파일 2,060 통과. 범위 확인: 12파일 22개 — `stockStoreTablePeriod`·`cryptoStoreTablePeriod`의 처음 단위 단언, 처음 표 요청
  글자에 `&period=monthly`가 붙은 `cryptoStore`·`stockStoreRecurring`·`cryptoStoreRecurring`·`stockStoreRerun`·`StocksPageRecurring`·`CryptoPageRecurring`·`StocksPageRerun`·`compareDetailStore`·
  `ComparePageSimulate`, 응답 단위를 대조하는 `fxWorkspaceScroll`의 상태). T161과 같은 절차(`014 승인 2026-10-11`)로 승인하고 구현을 치워 실패를 확인한 뒤 `test(014)`. 목록 밖의 실패는
  결함으로 보고 멈춘다 (FR-026)
- [X] T178 [US8] 화면 — `frontend/src/stores/fxWorkspaceStore.ts`·`stores/stockStore.ts`·`stores/cryptoStore.ts`(처음 값 `monthly`), `frontend/src/stores/compareDetailStore.ts`(닫힘 상태 `monthly`,
  열 때의 표 요청에 `periodQuery` — `pageable`일 때만), `frontend/src/lib/tablePeriod.ts`(설명) — DM13, contracts D14 (FR-035)

### Polish (반복 2026-10-11)

- [X] T179 [US8] 실측 — quickstart 5-24(외환 새로 열기 USD·JPY, 가상자산·주식 일시금·적립식 실행·이력 다시 실행·"일"로 바꾼 뒤 다시 실행, 비교 모달 주식·가상자산·예금, 대시보드 지표 표, 블랙 배경)를
  헤드리스 Chrome으로 확인하고 `quickstart.md` 8에 기록한다 (FR-035, SC-020)
- [X] T180 불변 대조·문서 — `014-baseline/fetch.py`(기준 29파일 — 부동산 기준일·`meta` 말고 차이 0, 서버 변경 없음), `CLAUDE.md`(014 줄·표 단위 주의), `README.md`, `spec.md` Status (FR-026, SC-010, SC-020)
- [X] T181 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T177)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 15: 반복 2026-10-11b — 수익률 추이의 현재 가치 축·두 지점 확대 (spec Iterations — 사용자 요청)

**Goal**:
- 투자 비교 수익률 추이의 왼쪽 축에 대상마다의 현재 가치(원화) 가는 선을 보인다(US9 — FR-036). 값은 비교 블록의 `valueLine`(서버 — 시계열 점과 같은 날마다 원화 총자산 + 매도 후 금액)
- 수익률 선이 있는 세 그래프(투자 비교 수익률 추이·메뉴와 비교 모달의 성과 추이·메뉴 이력 수익률 비교)에서 두 번 눌러 확대하고 오른쪽 위 [리셋]으로 처음 범위로 되돌린다(US10 — FR-037)

**Independent Test**(spec US9·US10):
- 투자 비교 주식 일시금(삼성전자·QLD)의 왼쪽 축이 원화이고 선 끝 금액이 표 "현재 가치"와 같다. 적립식은 가는 선이 납입으로 오른다. 커서 상자에 현재 가치가 있다
- 세 그래프에서 두 날을 누르면 그 사이만 보이고, [리셋]이면 처음 범위다. 외환·대시보드 그래프는 그대로다

**완료 작업 영향**: 없음 — 014의 화면·경로는 그대로다. 013 비교 블록에 `valueLine` 키 하나(메뉴 응답·`series`·`summary`·`lineEnd` 불변), 005·010·011·013 차트 셋에 누르기 확대·[리셋]이
더해진다(FR-026 예외). 블록 전체·키 집합·`lineEnd` 밖을 견주는 014 전 백엔드 테스트는 없고, 화면 픽스처에 `valueLine`이 없으면 현재 가치 선을 그리지 않는다 — 실제 목록은 T185

### Tests for 반복 2026-10-11b ⚠️

- [X] T182 [P] [US9] 백엔드 테스트 — 새 `backend/tests/integration/test_comparison_value_line.py`(비교 경로 일곱 — `valueLine.points`의 날짜·차례 = `series.points`, 주식 일시금은 예수금이
  있는 날 점 `balance`와 다르고 KRW 원금 + 그 날 투자 수익과 같음, 가상자산 일시금 같은 규칙, 적립식·정기예금·적금·부동산은 점 `balance`, 마지막 점이 기준일이면 `currentValue`와 같은 글자,
  `afterSaleValue` = `principal.krw` + 매도 후 투자 수익·매도 후 기준이 아니면 `null`, 메뉴 경로와의 대조 — `series`·`summary`·`lineEnd`와 블록의 다른 칸 불변, 메뉴 응답에 키 없음)·새
  `backend/tests/unit/test_comparison_value_line.py`(`comparison_block`의 `valueLine` 모양, 금액 문자열에 지수 표기 없음). 최초 실패 확인 (FR-036, SC-021)
- [X] T183 [P] [US9] 화면 테스트 — 새 `frontend/tests/CompareReturnChartValue.test.tsx`(왼쪽 가격 축 보임, 대상마다 `priceScaleId "left"`·`lineWidth 1`·그 대상의 색·선 모양의 현재 가치 선,
  원화 축 형식(소수 없음), 결측 구간 끊기·잠정 연한 색이 수익률 선과 같은 자리, 기준일까지 `currentValue`로 잇기, 매도 후 금액 점(`afterSaleValue`, 없으면 없음), 커서 상자 대상 줄의
  `₩` 현재 가치·기준일 줄, 축 설명 `compare-axes`, `valueLine`이 없으면 현재 가치 선·왼쪽 축 없음, 비교 화면이 블록의 `valueLine`·`currentValue`를 넘김). 최초 실패 확인 (FR-036, SC-021)
- [X] T184 [P] [US10] 화면 테스트 — 새 `frontend/tests/ChartZoom.test.tsx`(세 그래프 `CompareReturnChart`·`PerformanceChart`·`ComparisonChart` — 커서 날짜가 있을 때 첫 누름이면 오른쪽 위
  상태 줄 `시작 … · 끝 지점을 누르세요`·[취소], 둘째 누름이면 `timeScale().setVisibleRange({ from, to })`(앞뒤 정렬), 상태 줄 대신 [리셋], [리셋]이면 `fitContent`·단추 사라짐, 확대 안
  다시 확대·리셋은 처음, 같은 날·[취소]·Esc 취소, 4px 넘게 움직인 누름 무시, 커서 날짜를 모르면 무시, 시계열·테마가 바뀌면 처음 범위·단추 없음, 그릴 때 `setVisibleRange`·`subscribeClick`
  0회, 확대·리셋의 요청 0회, `FxChart`·`IndicatorChart`에는 확대 단추 없음)·새 `frontend/tests/chartZoom.test.ts`(순수 규칙 — 정렬·같은 날·끌기 거리·상태 전이). 최초 실패 확인 (FR-037, SC-022)

### Implementation for 반복 2026-10-11b

- [X] T185 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(결과: **없음** — 백엔드 3,460·화면 232파일 2,122 통과, 바뀐 기존 테스트 파일 없음). T161과 같은 절차(`014 승인 2026-10-11(반복 2026-10-11b T185)`)로 승인하고 구현을 치워 실패를 확인한 뒤
  `test(014)`. 목록 밖의 실패는 결함으로 보고 멈춘다 (FR-026)
- [X] T186 [US9] 백엔드 — `backend/src/api/services/comparison_metrics.py`(`comparison_block(..., value_points=…)` → `valueLine` — `afterSaleValue`는 `principal.krw` + 매도 후 수익),
  `backend/src/api/routes/comparison.py`(일곱 경로 — 메뉴 함수·`series_json` 불변), 필요하면 새 `backend/src/api/services/comparison_values.py`(시계열 점 날짜마다 원화 총자산 고르기 —
  일시금은 그 날 마지막 행의 KRW 원금 + 투자 수익, 나머지는 점 `balance`) — DM14, contracts A12 (FR-036)
- [X] T187 [US9] 화면 — `frontend/src/lib/types.ts`(`ComparisonBlock.valueLine?`), `frontend/src/components/compare/CompareReturnChart.tsx`(왼쪽 축·현재 가치 가는 선·기준일 잇기·매도 후 금액 점·
  커서 상자·축 설명), `frontend/src/app/compare/page.tsx`(차트 항목에 `valueLine`·`currentValue`) — DM14, contracts D15 (FR-036)
- [X] T188 [US10] 화면 — 새 `frontend/src/lib/chartZoom.ts`·`frontend/src/hooks/useChartZoom.ts`·`frontend/src/components/ChartZoomControls.tsx`, `frontend/src/components/compare/CompareReturnChart.tsx`,
  `frontend/src/components/stock/PerformanceChart.tsx`, `frontend/src/components/stock/ComparisonChart.tsx` — DM15, contracts D16 (FR-037)

### Polish (반복 2026-10-11b)

- [X] T189 [US9] [US10] 실측 — quickstart 5-25(투자 비교 주식 일시금 삼성전자·QLD·적립식·예금·부동산의 왼쪽 축·선 끝 = 표 현재 가치·커서 상자, 확대: 비교 수익률 추이·주식·가상자산·예금·부동산
  메뉴 성과 추이·이력 수익률 비교·비교 모달 성과 추이에서 두 지점·리셋·취소·Esc·끌기, 외환·대시보드 그래프 그대로, 블랙 배경 대비)를 헤드리스 Chrome으로 확인하고 `quickstart.md` 8에 기록한다
  (FR-036, FR-037, SC-021, SC-022)
- [X] T190 불변 대조·문서 — `014-baseline/fetch.py`(기준 29파일 — 메뉴 파일 차이 0, `*.comparison.json`은 `comparison.valueLine`을 빼면 차이 0, 부동산 기준일·`meta` 말고), `CLAUDE.md`(014 줄·
  차트 확대·비교 블록 주의), `README.md`, `spec.md` Status (FR-026, FR-036, SC-010, SC-021)
- [X] T191 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T177·T185)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 16: 반복 2026-10-11c — 확대 구간의 일 단위 자료·확대 단추 자리 (spec Iterations — 사용자 보고)

**Goal**:
- 일 단위로 볼 수 있는 그래프에서 확대하면 그 구간을 날마다의 점으로 다시 그린다(US11 — FR-038). 서버는 보기 구간 질의, 화면은 받아서 끼우기
- 외환 추이·지표 일봉 그래프에도 두 지점 확대, 확대 단추는 오른쪽 가격 축 밖(FR-039)

**Independent Test**(spec US11):
- 주식 메뉴(삼성전자 2024-01-02)를 확대하면 그 구간의 거래일마다 점이고 값이 일자별 표 "일" 행과 같다. 투자 비교(주식 여럿)·외환(긴 기간)·지표(1년)도 확대된다. [리셋]은 처음 범위
- [리셋]·상태 줄이 오른쪽 축 숫자를 가리지 않는다. 질의 없는 응답·예금·부동산·장중 그래프는 그대로다

**완료 작업 영향**: FR-037(T184·T188)의 "요청 없음"·"외환·대시보드는 대상 밖"·단추 자리가 바뀐다 — `ChartZoom.test.tsx`의 해당 단언은 T195에서 실제 실패 목록으로 승인한다

### Tests for 반복 2026-10-11c ⚠️

- [X] T192 [P] [US11] 백엔드 테스트 — 새 `backend/tests/integration/test_series_view_window.py`(메뉴 넷·비교 넷 — 질의 있으면 그 구간 ∩ 계산 구간의 시세일마다 점(주식 일시금·적립식: 빠진
  거래일·남는 날 0, 값 = 같은 조건 표 `period=daily` 행의 잔고·수익률, 사건 날 값 = 원래 점), 가상자산: 원래 일봉의 그 구간 그대로(줄이지 않음), 구간 `gaps`, `maxPoints` 넘으면 줄임,
  비교 `valueLine` 날짜 = 구간 점·주식 일시금 값 = 원금 + 그 날 수익, 한쪽만·`viewFrom` > `viewTo` 400 `invalid_query`, 질의 없으면 응답 불변(대조))·새 `backend/tests/unit/test_series_view_window.py`
  (`view_window` 검증·자르기). 최초 실패 확인 (FR-038, SC-023)
- [X] T193 [P] [US11] 화면 테스트 — 새 `frontend/tests/chartDetail.test.ts`(끼워 그리기·`gaps` 합치기·`valueLine` 끼우기·덮음 판정)·새 `frontend/tests/ChartZoomDetail.test.tsx`(세 수익률
  그래프·외환 — 확대가 끝나면 구간 받기 함수를 그 범위로 부름, 받은 점으로 다시 그리고 `setVisibleRange(범위)` 유지, 받는 중·실패 상태 줄, 늦은 응답 버림, [리셋]이면 원래 점·`fitContent`, 받은
  구간 안 다시 확대는 받지 않음, 받기 함수가 없으면 지금처럼, 화면 연결 — 주식 메뉴는 늘·가상자산·외환은 `downsampled`일 때만·투자 비교 주식 대상·이력 비교·비교 모달, 예금·부동산은 받기 함수 없음,
  구간 요청 주소의 `viewFrom`·`viewTo`·`maxPoints=5000`). 최초 실패 확인 (FR-038, SC-023)
- [X] T194 [P] [US11] 화면 테스트 — 새 `frontend/tests/ChartZoomPlacement.test.tsx`(확대 단추·상태 줄의 자리 = 오른쪽 축 폭 + 8px·위 4px, 축 폭은 처음 누를 때만 `priceScale("right").width()`,
  외환 추이·지표 일봉 그래프의 두 지점 확대·취소·리셋, 지표 [리셋] = 그 기간의 `setVisibleLogicalRange` 처음 범위(모두면 `fitContent`), 지표 기간 바꾸면 확대 풀림, 장중은 단추 없음).
  최초 실패 확인 (FR-039, SC-024)

### Implementation for 반복 2026-10-11c

- [X] T195 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(결과: **`ChartZoom.test.tsx` 하나** — 29개가 모의의 `priceScale` 없음·"대상 밖" 단언으로 실패, 백엔드 3,504·화면 2,156 통과 뒤 승인. 014 전 테스트 변경 없음). T161과 같은 절차
  (`014 승인 2026-10-11(반복 2026-10-11c T195)`)로 승인하고 구현을 치워 실패를 확인한 뒤 `test(014)`. 목록 밖의 실패는 결함으로 보고 멈춘다 (FR-026)
- [X] T196 [US11] 백엔드 — `backend/src/api/services/series_query.py`(`view_window`), `backend/src/api/services/stock_series.py`·`recurring_series.py`·`crypto_series.py`(구간 점 빌더 — 날마다
  상태에서 고르기), `backend/src/api/services/comparison_values.py`(구간 점의 원화 총자산), `backend/src/api/routes/stock_series.py`·`stock_recurring.py`·`crypto_series.py`·`crypto_recurring.py`·
  `comparison.py`(질의 둘) — DM16, contracts A13 (FR-038)
- [X] T197 [US11] 화면 — 새 `frontend/src/lib/chartDetail.ts`·`frontend/src/lib/seriesDetail.ts`, `frontend/src/hooks/useChartZoom.ts`(확대 끝 알림·사용자 리셋·축 폭)·
  `frontend/src/components/ChartZoomControls.tsx`(자리·받는 중/실패 줄), `frontend/src/components/compare/CompareReturnChart.tsx`·`components/stock/PerformanceChart.tsx`·
  `components/stock/ComparisonChart.tsx`(받은 자료 끼우기), 스토어(`stockStore`·`cryptoStore`·`compareStore`·`compareDetailStore` — 시계열 경로 기억)와 화면(`app/stocks`·`app/crypto`·`app/compare`·
  비교 모달) — DM16, contracts D17 (FR-038, FR-039)
- [X] T198 [US11] 화면 — `frontend/src/components/FxChart.tsx`·`components/fx/TrendChart.tsx`(두 지점 확대·구간 받기 — `fxWorkspaceStore`), `frontend/src/components/dashboard/IndicatorChart.tsx`
  (일봉 그래프의 두 지점 확대 — [리셋] = 기간 처음 범위, 기간 바꾸면 풀림) — DM16, contracts D17 (FR-039)

### Polish (반복 2026-10-11c)

- [X] T199 [US11] 실측 — quickstart 5-26(주식 메뉴·투자 비교(주식 여럿)·비교 모달·이력 비교·가상자산(줄여진 긴 기간)·외환(긴 기간)·지표(1년) 확대 → 구간 점 간격·값 = 표 "일" 행·리셋, 받는 중·
  실패, 단추가 축과 겹치지 않음(밝은·블랙), 예금·부동산·장중 그대로)을 헤드리스 Chrome으로 확인하고 `quickstart.md` 8에 기록한다 (FR-038, FR-039, SC-023, SC-024)
- [X] T200 불변 대조·문서 — `014-baseline/fetch.py`(기준 29파일 — 질의 없는 응답 차이 0), `docs/implementation-notes.md`(§5 확대 절)·`CLAUDE.md`(014 줄·색인), `README.md`, `spec.md` Status
  (FR-026, FR-038, SC-010, SC-023)
- [X] T201 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T177·T185·T195)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

---

## Phase 17: 반복 2026-10-11d — 대시보드 기준금리 (spec Iterations — 사용자 요청)

**Goal**:
- 대시보드의 환율 묶음과 원자재·변동성 묶음 사이에 다섯 중앙은행의 기준금리 칸(금리·전회대비·기준 일자)을 보이고(US12 — FR-040), 은행을 누르면 주소 있는 모달에 계단선 그래프·"금리 추이" 표·
  변화 까닭을 보인다(FR-041·FR-042). 결정 이력은 로컬 DB에 쌓는다(FR-043)

**Independent Test**(spec US12):
- 대시보드의 기준금리 칸 다섯 행이 출처(네이버 증권 기준금리)의 금리·전회대비·기준 일자와 같고, 은행 다섯의 모달 표가 결정 이력(동결 포함)과 같다. 까닭은 그 은행의 최근 결정 기사뿐이다
- 처음 기동은 "받는 중" → 채워짐, 출처가 막히면 받아 둔 값 + "최근 갱신 실패". 지표 카드·지표 모달·뉴스·외환은 그대로다

**완료 작업 영향**: 손대는 완료 산출물은 `IndicatorGroups.tsx`(환율 뒤 자리)·`IndicatorModal.tsx`(은행 id면 금리 화면)·`api/main.py`(lifespan 열째)·`ingestion/news/commentary.py`(은행 출처)다.
014가 만든 대시보드 화면 테스트의 요청 모의가 바뀔 수 있다 — T206에서 실제 실패 목록으로 승인한다. **원칙 II 새 경로는 T202 승인 전에 구현하지 않는다**

### Source & approval (반복 2026-10-11d)

- [X] T202 출처 실측·픽스처·**원칙 II 승인** — (a) 네이버 기준금리 목록·결정 이력(다섯 은행의 깊이·`pageSize` 상한 60·자리 표시 시각·같은 날 두 행·발표 전 행·다음 결정일·계열의 뜻·응답 크기·
  시간)과 뉴스 포커스 404·403·429의 결정 날 기사(은행마다 "은행 낱말 + 금리 낱말"로 고른 수)를 재고, robots·약관을 확인해 `research.md` R14-32·R14-33을 실측값으로 고친다. (b) 픽스처
  `backend/tests/contract/fixtures/policy_rate/`(본문만 — 주소·머리 없이: 목록, 은행마다 결정 이력 첫 쪽 일부, 같은 날 두 행·발표 전 행·하락 행·마이너스 금리가 든 조각, 결정 날 뉴스 포커스
  조각) + README 표. (c) `plan.md` Complexity Tracking의 새 표를 실측으로 채우고 **사용자에게 승인을 받는다** — 승인되지 않으면 T203 이후를 하지 않고 멈춘다 (FR-040, FR-042, FR-043)

### Tests for 반복 2026-10-11d ⚠️

- [X] T203 [P] [US12] 계약 테스트 — 새 `backend/tests/contract/test_policy_rate_parse.py`(목록·결정 이력 픽스처: 금리 `Decimal`·하락 부호·발표 전 행 → 결정 아님·자리 표시 시각 → 시각 없음·한국 날짜·
  같은 날 같은 값 하나(실제 시각)/다른 값 충돌·다음 결정일·실패 종류 다섯(contracts A0 — 400 `pageSize` 상한 포함)). 최초 실패 확인 (FR-043, SC-026)
- [X] T204 [P] [US12] 백엔드 테스트 — 새 `backend/tests/unit/test_policy_rate_rules.py`(전회대비·방향·첫 결정 `null`·예정일이 오늘(한국)보다 이르면 없음), 새
  `backend/tests/integration/test_policy_rate_worker.py`(처음 전부 — 짧은 쪽에서 끝남, 중간 실패는 끝남으로 기록하지 않고 다음 바퀴에 이어 받음, 새 결정이 보이면 첫 쪽, 하루 한 번 겹쳐 받기,
  개정은 덮지 않고 `policy_rate_revised`, 같은 날 충돌 `policy_rate_conflict`, 은행마다 따로 실패, 깨우기, 원본 본문만), 새 `backend/tests/integration/test_dashboard_rates_api.py`(A14~A17 —
  차례·값·한국 날짜·받는 중·실패·받아 둔 값 + 최근 갱신 실패·없는 은행 404·칸 경로가 출처를 부르지 않음), 새 `backend/tests/unit/test_policy_rate_commentary.py`(결정일·다음 날, 분류 차례
  404 → 403 → 429, 은행 낱말·금리 낱말 둘 다, 최대 3·같은 제목 한 번, 같은 (분류, 날짜) 한 번, 찾지 못함·실패·0건 읽기, 캐시). 최초 실패 확인 (FR-040~FR-043, SC-025, SC-026)
- [X] T205 [P] [US12] 화면 테스트 — 새 `frontend/tests/PolicyRateTable.test.tsx`(환율 묶음 뒤·원자재·변동성 앞, 다섯 행·국기·`4.00%`·▲▼·`0.00` 색·`09. 17.`·칸 머리, 받는 중 5초 뒤 다시·
  실패·받아 둔 값 + 최근 갱신 실패·[다시 시도] = 깨우기, 행 누르면 `/dashboard/fed?range=1y`, 화면 계산 없음), 새 `frontend/tests/RateModal.test.tsx`(머리·금리 종류·다음 결정 예정·저장된 기간,
  계단선(라인 종류)·결정 점·커서 상자, 기간 넷·처음 1년·바꾸면 처음 범위, 두 지점 확대·[리셋] = 기간 처음 범위, 표 = 예정 행 + 결정 전부(최신부터), 까닭 줄·찾지 못함·실패, 블랙 배경,
  닫으면 그 은행 행으로 포커스, 없는 은행). 최초 실패 확인 (FR-040~FR-042, SC-025, SC-026)

### Implementation for 반복 2026-10-11d

- [X] T206 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(예상: 014가 만든 대시보드 화면 테스트의 요청 모의만 — **결과: 화면 0, 백엔드 넷** — lifespan 태스크 수를 9로 박은 `test_apt_worker`·`test_crypto_worker`·`test_deposit_worker`(014 전 파일이지만 014가 2026-10-10에 이미 같은 단언을 8 → 9로 고쳐 승인한 줄 — 9 → 10, 바뀐 기존 파일 수 그대로 30)와 014가 만든 `test_stock_first_trade`의 "첫 거래일 리비전이 머리"(머리는 새 `test_policy_rate_worker::Test스키마`가 본다). 권장안대로 같은 선례로 승인, 화면 테스트는 바뀌지 않았다). T195와 같은 절차
  (`014 승인 2026-10-11(반복 2026-10-11d T206)`)로 승인하고 구현을 치워 실패를 확인한 뒤 `test(014)`. 014 전 테스트가 실패하면 결함으로 보고 멈춘다 (FR-026)
- [X] T207 [US12] 백엔드 저장·수집 — Alembic 리비전(`policy_rate_decision`·`policy_rate_raw`·`policy_rate_bank` — down `a6c2e8f41b93`), `backend/src/db/models.py`,
  새 `backend/src/repository/policy_rate_repository.py`, 새 `backend/src/ingestion/naver_rate/`(`client.py`·`parse.py`·`banks.py`), 새 `backend/src/worker/policy_rate_worker.py`·`policy_rate_runner.py`(한 바퀴 — 할 일 없는 은행도 목록 성공이면 성공)·
  `backend/src/api/main.py`(lifespan 열째), `backend/src/config/settings.py`·`.env.example`(`POLICY_RATE_*`), 개발 DB `alembic upgrade head` — DM17 (FR-043)
- [X] T208 [US12] 백엔드 조회·까닭 — 새 `backend/src/simulation/policy_rate.py`(순수), 새 `backend/src/api/routes/dashboard_rates.py`(A14~A17), `backend/src/ingestion/news/commentary.py`(은행 출처 —
  결정일·다음 날·분류 404 → 403 → 429·낱말 둘 다), 새 `backend/src/api/services/policy_rate_commentary.py`·`policy_rates.py`(칸·모달 본문) — contracts A14~A17 (FR-040~FR-042)
- [X] T209 [US12] 화면 — `frontend/src/lib/types.ts`, 새 `frontend/src/stores/policyRateStore.ts`, 새 `frontend/src/components/dashboard/PolicyRateTable.tsx`·`RateView.tsx`·`RateChart.tsx`·
  `RateTable.tsx`, `components/dashboard/IndicatorGroups.tsx`(환율 뒤 자리), `components/dashboard/IndicatorModal.tsx`(은행 id면 `RateView`·포커스 복귀 `data-rate`)·`RangePicker.tsx`(금리 기간 넷),
  `app/dashboard/page.tsx`, `lib/dashboardApi.ts`·새 `lib/rateFormat.ts`, `components/dashboard/IndicatorCommentary.tsx`(없을 때 글자) — contracts D18 (FR-040~FR-042)

### Polish (반복 2026-10-11d)

- [X] T210 [US12] 실측 — quickstart 5-27(처음 기동 받는 중 → 다섯 행, 값 = 출처 목록, 은행 다섯 모달 — 표 = 결정 이력·예정 행, 그래프 계단선·기간·확대, 까닭 = 그 은행 기사, 블랙 배경, 출처 막힘)을
  헤드리스 Chrome으로 확인하고 `quickstart.md` 8에 기록한다 (FR-040~FR-043, SC-025, SC-026)
- [X] T211 불변 대조·문서 — `014-baseline/fetch.py`(기준 29파일 — 차이 0), `docs/implementation-notes.md` §7(기준금리 절), `CLAUDE.md`(014 줄·lifespan 열째·원칙 II 이탈 수), `README.md`(기능·데이터 출처),
  `INSTALL.md`(첫 수집·업데이트의 014 테이블), `spec.md` Status (FR-026, SC-010)
- [X] T212 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T177·T185·T195·T206)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests` (SC-010)

## Phase 18: 반복 2026-10-13 — 투자 비교의 대상 수 설정 (US13 — Priority P13, spec Iterations — 사용자 요청)

**Goal**:
- 설정 화면의 새 절 "투자 비교"에서 최대 대상 수(정수 2~100, 기본 20 — 로컬 DB)를 정하고(US13 — FR-044), 투자 비교 화면은 그 수만큼 대상을 더한다(FR-045). 서버 검증의 끝은 100(예금 5)이다
- 대상이 100개까지 늘어도 요청 3·진행 구독 2·확대 구간 요청 3의 차례 한도, 선 모양 짝 20, 대상 11개 이상의 커서 상자(가까운 10개 + "외 N개")로 실행·그래프가 깨지지 않는다(FR-046)

**Independent Test**(spec US13):
- 설정을 바꾸지 않으면 21번째가 막히고 "최대 20개", 100으로 저장하면 100개까지 더해진다. 범위 밖·정수 아님은 422와 칸 오류로 저장되지 않는다
- 받아 둔 주식 100개 일시금이 30초 안에 다 채워지고 동시 연결이 5개를 넘지 않는다. 대상 20개의 선 짝이 모두 다르고, 대상 30개 커서 상자는 11줄이다. 대상 10개 이하 비교 값은 그대로다

**완료 작업 영향**: **013 FR-004의 "최대 10개"를 대체한다**(013 산출물은 고치지 않는다 — FR-044가 대체를 밝힌다). 손대는 완료 산출물은 `comparison_conditions.py`(끝 100)·`saved_comparison.py`(길이 가드)·
`api/main.py`(라우터)·`compareCondition.ts`·`compareStore.ts`·`seriesDetail.ts`·`TargetChips.tsx`·`CompareReturnChart.tsx`·`app/compare/page.tsx`·`app/settings/page.tsx`다. 끝(10)을 박은 기존 테스트는 T215에서
실제 실패 목록으로 승인한다

### Tests for 반복 2026-10-13 ⚠️

- [X] T213 [P] [US13] 백엔드 테스트 — 새 `backend/tests/unit/test_comparison_settings_rules.py`(설정 검증: 2·20·100 됨, 1·101·`True`·`20.5`·`"20"`·`None`·없는 칸 거절 — `InvalidSetting`, 기본 20, 본문
  A18의 네 칸), 새 `backend/tests/unit/test_comparison_target_limit.py`(`validate_condition` — 대상 100개 됨·101개 거절 `targets: 2~100개여야 합니다: 101개`·예금 6개 거절·1개 거절, 저장 길이 —
  직렬화 글 65,535바이트(UTF-8 — 한글 3바이트로 경계를 맞춤) 됨·65,536바이트 거절 `condition:`·거절이면 저장소를 부르지 않음), 새 `backend/tests/integration/test_comparison_settings_api.py`
  (행 없음 `GET` = 20·`defaultMaxTargets` 20·`minTargets` 2·`limitTargets` 100, `PUT` 저장·다시 읽기, 범위 밖·정수 아님 422 `invalid_setting`·값 그대로, 저장한 비교 대상 100개 `POST /api/comparison/saved` 201·
  목록에서 100개 그대로, 설정을 10으로 낮춰도 30개 저장 됨, 101개 422 `invalid_comparison`, 스키마 — `comparison_setting` 열·형·head = 새 리비전, `/api/comparison/settings`가 비교 라우터에 잡히지 않음).
  임포트는 구현 뒤 기준(`src.*` 묶음)으로 정렬. 최초 실패 확인 (FR-044, FR-045, SC-027)
- [X] T214 [P] [US13] 화면 테스트 — 새 `frontend/tests/CompareSettingsSection.test.tsx`(처음 값 = 서버 값, 저장 → `PUT` 본문 정수, 범위 밖·소수·빈 칸 → 칸 오류·요청 없음 또는 서버 422 메시지, 저장 실패에도
  칸 값 그대로, 다른 절과 상태를 나누지 않음, 안내 글자), 새 `frontend/tests/compareTargetLimit.test.tsx`(스토어 — 설정 값만큼 더함·알림 글자에 그 값, 예금 min(5, 설정), 설정 읽기 실패 → 20 +
  알림, 설정보다 많은 저장한 비교 → 전부 채움 + 알림·더하기 막힘·빼서 설정 이하면 알림 사라짐, 대상 10개 실행의 동시 요청 ≤3·대상 차례로 채움·늦게 온 응답이 제 자리, 수집 중 대상 다섯의 진행 구독
  ≤2·끝나면 다음 차례·늦게 연 구독의 `completed`로 다시 요청, `compareDetailLoader` 동시 ≤3, 순수 `lib/concurrency`의 차례·한도), 새 `frontend/tests/CompareReturnChartMany.test.tsx`(대상 20개 짝(색·선 모양)
  20개 모두 다름·첫 10개는 지금 그대로, 대상 30개 커서 상자 = 가까운 10줄 + "외 20개 — 비교 표에 모두 있습니다"·수익률 높은 차례, 대상 10개 상자는 지금 그대로, 그릴 때 새 차트 API 0 — 모의는 파일
  인라인). 최초 실패 확인 (FR-044~FR-046, SC-027, SC-028)

### Implementation for 반복 2026-10-13

- [X] T215 기존 테스트 변경 승인 — 구현을 작업 트리에 둔 뒤 전체 스위트의 실제 실패 목록(예상: `backend/tests/unit/test_comparison_conditions.py`의 대상 11개 거절 줄 → 101개,
  `frontend/tests/compareStore.test.ts`·`frontend/tests/ComparePage.test.tsx`의 "11번째"·"최대 10개" → 기본 설정의 21번째·"최대 20개", 014 `backend/tests/integration/test_policy_rate_worker.py`의 head →
  새 리비전)을 `014 승인 2026-10-13(반복 2026-10-13 T215)`으로 승인하고, `git stash push -u -- backend/src frontend/src`로 구현을 치워 새 테스트의 실패를 확인한 뒤 `test(014)`. 예상 밖 기존 테스트가
  실패하면 결함으로 보고 멈춘다 (FR-026)
- [X] T216 [US13] 백엔드 — Alembic 리비전(`comparison_setting` — `id SMALLINT PK 기본 1`·`max_targets SMALLINT NOT NULL`·`updated_at TS`, down `e9f3b7c2a4d1`), `backend/src/db/models.py`
  (`ComparisonSetting`), 새 `backend/src/repository/comparison_setting.py`(읽기 — 없으면 `None`, 저장 upsert), 새 `backend/src/api/services/comparison_settings.py`(검증 — JSON 정수 2~100·불리언 거절,
  기본 20, 본문 A18), 새 `backend/src/api/routes/comparison_settings.py`(A18 — `backend/src/api/main.py`에 비교 라우터보다 먼저 등록), `backend/src/api/services/comparison_conditions.py`(`MAX_TARGETS`
  10 → 100·docstring), `backend/src/api/services/saved_comparison.py`(조건 글 UTF-8 65,535바이트 가드 — 422 `invalid_comparison` 칸 `condition`), 개발 DB `alembic upgrade head` — DM18 (FR-044, FR-045)
- [X] T217 [US13] 화면 — `frontend/src/lib/types.ts`(`CompareSettings`), `frontend/src/lib/compareApi.ts`(설정 읽기·저장), `frontend/src/lib/compareCondition.ts`(`maxTargets(asset, limit)`),
  새 `frontend/src/lib/concurrency.ts`(대상 차례 한도 — 순수), `frontend/src/stores/compareStore.ts`(`limit`·`loadLimit`·D5·D6 알림·요청 3·구독 2), `frontend/src/lib/seriesDetail.ts`(`compareDetailLoader` 3),
  `frontend/src/app/compare/page.tsx`(열 때 한도 읽기·칩 한도), `frontend/src/components/compare/TargetChips.tsx`(안내), `frontend/src/components/compare/CompareReturnChart.tsx`(선 모양 짝 20·대상 11개 이상
  커서 상자 — `priceToCoordinate`는 커서 움직임에서만), 새 `frontend/src/components/settings/CompareSettingsSection.tsx`, `frontend/src/app/settings/page.tsx`(부동산 뒤·이력 앞),
  `frontend/tests/setup.ts`(설정 대역 — 기본 20) — contracts D19 (FR-044~FR-046)

### Polish (반복 2026-10-13)

- [X] T218 [US13] 실측 — quickstart 5-28(설정 기본 20·저장·범위 밖, 비교 화면 21번째 알림, 100으로 바꾼 뒤 받아 둔 주식 100개 일시금의 실행 시간·첫 줄 시간·동시 연결 수(CDP `Network` 사건)·그래프 짝·
  커서 상자·막대·표, 저장·불러오기·조건 글 바이트, 설정을 10으로 낮춘 뒤 불러오기 알림, 수집 중 대상 여럿의 구독 차례, 블랙 배경 대비)를 헤드리스 Chrome으로 확인하고 `quickstart.md` 8에 기록한다.
  받아 둔 종목이 100개보다 적으면 임시 백엔드(테스트 DB에 합성 일봉 100종목 — 출처를 부르지 않음, 개발 DB를 바꾸지 않음)로 잰다 (FR-044~FR-046, SC-027, SC-028)
- [X] T219 불변 대조·문서 — `014-baseline/fetch.py`(기준 — 대상 10개 이하 비교 응답 차이 0), `docs/implementation-notes.md` §6(투자 비교의 대상 수 설정·연결 한도·선 짝·커서 상자), `CLAUDE.md`(013·014 줄 —
  대상 수), `README.md`(투자 비교 기능 — 2~100, 설정), `INSTALL.md`(업데이트 — 새 테이블 `alembic upgrade head`), `spec.md` Status (FR-026, SC-010, SC-028)
- [X] T220 게이트(서버를 내린 채) — 백엔드·프론트엔드 전체, mypy·ruff·tsc·eslint, 바뀐 기존 테스트 파일이 승인 목록(T018·US2·T111·T132·T144·T152·T161·T169·T177·T185·T195·T206·**T215**)뿐인지
  `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests`(30 → 승인한 수) (SC-010)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작한다. **T001·T002는 다른 모든 코드 변경보다 먼저다.**
- **반복 2026-10-10 (Phase 7)**: Phase 6 뒤. T087(문서) → 테스트 T088~T090(함께 — 최초 실패 확인 뒤 `test(014)`) → 구현 T091~T093 → T094
- **반복 2026-10-10b (Phase 8)**: Phase 7 뒤
  1. T095(출처 실측·**원칙 II 재승인**) → T096
  2. 시가 기반 — 테스트 T097·T098 → 구현 T099·T100
  3. 테스트 T101~T110(함께 — 최초 실패 확인) → 구현 T112~T122 → T111(014 테스트 변경 승인 — 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  4. T123~T127
  - 승인이 안 된 갈래는 빠진다(T095)
- **반복 2026-10-10c (Phase 9)**: Phase 8 뒤
  1. T128(실측·픽스처·**밝은 테마 기준선 스크린샷 — 구현 전에**·색 변수 확인)
  2. 테스트 T129~T131(함께 — 최초 실패 확인) → 구현 T133~T136 → T132(014 테스트 변경 승인 — 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  3. T137~T141
  - T128(c)에서 색 변수 재정의가 닿지 않으면 멈추고 사용자에게 알린다(R14-23 대안)
- **반복 2026-10-10d (Phase 10)**: Phase 9 뒤
  1. 테스트 T142·T143(함께 — 최초 실패 확인) → 구현 T145·T146 → T144(실제 실패 목록 — 있으면 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T147~T150
- **반복 2026-10-10e (Phase 11)**: Phase 10 뒤
  1. 테스트 T151(최초 실패 확인) → 구현 T153 → T152(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T154~T157
- **반복 2026-10-10f (Phase 12)**: Phase 11 뒤
  1. T158(실측·픽스처) → 테스트 T159·T160(함께 — 최초 실패 확인) → 구현 T162·T163 → T161(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T164(개발 DB `alembic upgrade head` 먼저)~T167
- **반복 2026-10-10g (Phase 13)**: Phase 12 뒤
  1. 테스트 T168·T169(함께 — 최초 실패 확인) → 구현 T171·T172 → T170(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T173~T175
- **반복 2026-10-11 (Phase 14)**: Phase 13 뒤
  1. 테스트 T176(최초 실패 확인) → 구현 T178 → T177(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T179~T181
- **반복 2026-10-11b (Phase 15)**: Phase 14 뒤
  1. 테스트 T182·T183·T184(함께 — 최초 실패 확인) → 구현 T186 → T187 → T188(`CompareReturnChart.tsx`는 T187 뒤 T188) → T185(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T189~T191
- **반복 2026-10-11c (Phase 16)**: Phase 15 뒤
  1. 테스트 T192·T193·T194(함께 — 최초 실패 확인) → 구현 T196 → T197 → T198 → T195(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T199~T201
- **반복 2026-10-11d (Phase 17)**: Phase 16 뒤
  1. T202(출처 실측·픽스처·**원칙 II 승인** — 승인 전에는 아래를 하지 않는다)
  2. 테스트 T203·T204·T205(함께 — 최초 실패 확인) → 구현 T207 → T208 → T209 → T206(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  3. T210(개발 DB `alembic upgrade head` 먼저)~T212
- **반복 2026-10-13 (Phase 18)**: Phase 17 뒤(마이그레이션은 기준금리 리비전 뒤)
  1. 테스트 T213·T214(함께 — 최초 실패 확인) → 구현 T216 → T217(T216의 경로) → T215(실제 실패 목록 — 승인, 구현을 치워 실패 확인 뒤 `test(014)`) → 구현 커밋
  2. T218(개발 DB `alembic upgrade head` 먼저)~T220
- **Foundational (Phase 2)**: T002·T004 뒤. US1·US2를 막는다. US3는 T011(설정) 뒤면 시작할 수 있다.
- **US1 (Phase 3)**: Foundational 뒤. **T018(승인)이 이 페이즈의 테스트 커밋을 막는다** — T031~T040 구현을 작업 트리에 둔 뒤 목록을 만든다. 백엔드(T019~T023·T031~T035)와 화면(T024~T030·T036~T040)은 나란히 할 수 있다. MVP다.
- **US2 (Phase 4)**: US1 뒤(시세 서비스의 캐시가 잠정 꼬리·머리 값을 준다. `main.py`·`types.ts`·`dashboardApi.ts`가 겹친다). 승인 목록이 없을 것으로 본다 — 구현 뒤 목록 밖의 실패는 결함으로 보고 멈춘다.
- **US3 (Phase 5)**: 백엔드(T063~T068·T072~T077)는 T011 뒤면 US1·US2와 나란히 할 수 있다(`main.py`는 차례로). 화면(T069~T071·T078·T079)은 US1의 `app/dashboard/page.tsx` 뒤다.
- **Polish (Phase 6)**: 모든 스토리 뒤

스토리를 하나씩 끝내려면 US1 → US2 → US3 차례다.

### Within Each Phase

- 테스트(⚠️) 작성 → 구현(작업 트리) → 전체 스위트로 **실제로 실패한** 기존 테스트 목록 → 승인(있으면) → 승인된 기존 테스트 수정 → 구현을 치우고
  (`git stash push -u -- backend/src frontend/src`) 최초 실패 확인 → 테스트 커밋(최초 실패 요약) → 구현 되돌림 → 구현 커밋(통과 결과)
- 승인할 목록이 없을 것이 분명한 페이즈(Foundational·US2·US3)는 구현 전에 테스트를 커밋해도 된다 — 구현 뒤 목록 밖의 실패가 나오면 결함으로 보고 멈춘다
- 백엔드는 순수 계산 → 수집 어댑터 → 저장소 → 서비스 → 라우트·워커, 화면은 순수 함수·부품 → 스토어 → 화면 순서다.
- 픽스처 준비(T005·T063)는 그 페이즈의 계약 테스트보다 먼저다.

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T017(Foundational), T035(US1), T055·T057(US2), T077(US3), T118(반복 2026-10-10b) |
| `backend/src/ingestion/yahoo/market.py`·`market_parse.py` | T033(US1), T051(US2) |
| `backend/src/ingestion/yahoo/client.py` | T014 |
| `backend/src/config/settings.py`·`.env.example` | T011 |
| `frontend/src/lib/types.ts`·`lib/dashboardApi.ts` | T036(US1), T058(US2), T078(US3) |
| `frontend/src/app/dashboard/page.tsx` | T040(US1), T079(US3) |
| `frontend/src/components/shell/Sidebar.tsx`·`TopBar.tsx`·`app/page.tsx` | T040 |
| `frontend/tests/Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`·(`TopBarTitle.test.ts`) | T018(승인 뒤에만) |
| `specs/014-…/quickstart.md`(실행 기록) | T041, T062, T081, T082, T083, T084, T123~T127, T137~T141, T147·T148, T154·T155, T164·T165 |
| `frontend/src/components/dashboard/IndicatorChart.tsx` | T060·T121(이전), T134·T136(반복 2026-10-10c — 차례로) |
| `frontend/src/components/shell/TopBar.tsx`·`app/layout.tsx`·`app/globals.css` | T040(이전), T135 |
| `backend/src/api/routes/latest.py`·`api/services/daily_query.py`·`api/routes/daily.py` | T145(반복 2026-10-10d — 001·004 파일) |
| `frontend/src/components/fx/DailyTable.tsx`·`lib/csv.ts` | T146(반복 2026-10-10d — 001·004 파일) |
| `frontend/src/lib/types.ts` | T036·T058·T078·T134(이전), T146 |
| `frontend/src/lib/compareCondition.ts`·`lib/displayCode.ts`·`components/compare/CompareMetricBars.tsx` | T153(반복 2026-10-10e — 013·006 파일) |
| `frontend/src/components/crypto/CoinSearch.tsx` | T153(반복 2026-10-10e — 007 파일, 가상자산 메뉴와 함께 씀), T163 |
| `backend/src/api/services/stock_selection.py`·`api/routes/stock_selection.py`·`api/routes/stock_search.py`·`worker/stock_runner.py`·`ingestion/yahoo/client.py` | T162(반복 2026-10-10f — 005·006 파일) |
| `backend/src/api/services/comparison_metrics.py`·`api/routes/comparison.py` | T162(반복 2026-10-10f — 013 파일) |
| `frontend/src/components/stock/StockSearch.tsx`·`components/compare/CompareTable.tsx`·`stores/compareStore.ts`·`lib/types.ts` | T163(반복 2026-10-10f) |
| `backend/src/api/services/stock_selection.py`·`api/routes/stock_selection.py`·`api/routes/comparison.py`·`api/routes/crypto_search.py` | T162(이전), T171(반복 2026-10-10g) |
| `frontend/src/components/stock/StockSearch.tsx`·`components/crypto/CoinSearch.tsx`·`lib/listingDate.ts`·`components/ListingText.tsx` | T163(이전), T172(반복 2026-10-10g) |
| `frontend/tests/setup.ts` | T169(반복 2026-10-10g — 대역 한 겹) |
| `frontend/src/stores/fxWorkspaceStore.ts`·`stores/stockStore.ts`·`stores/cryptoStore.ts`·`stores/compareDetailStore.ts` | T178(반복 2026-10-11 — 004·012·013 파일) |
| `backend/src/api/services/comparison_metrics.py`·`api/routes/comparison.py` | T162·T171(이전), T186(반복 2026-10-11b — 013 파일) |
| `frontend/src/components/compare/CompareReturnChart.tsx` | T187 → T188(반복 2026-10-11b — 차례로, 013 파일) |
| `frontend/src/components/stock/PerformanceChart.tsx`·`components/stock/ComparisonChart.tsx` | T188(반복 2026-10-11b — 005·010·011 파일, 네 메뉴·비교 모달이 함께 씀) |
| `frontend/src/lib/types.ts`·`app/compare/page.tsx` | T163(이전), T187(반복 2026-10-11b) |
| `frontend/src/hooks/useChartZoom.ts`·`components/ChartZoomControls.tsx`·차트 셋 | T188(이전), T197 → T198(반복 2026-10-11c — 차례로) |
| `backend/src/api/routes/comparison.py`·`api/services/comparison_values.py` | T186(이전), T196(반복 2026-10-11c) |
| `backend/src/api/main.py` | T118·T207(이전), T216(반복 2026-10-13 — 라우터 등록) |
| `backend/src/api/services/comparison_conditions.py`·`api/services/saved_comparison.py` | T216(반복 2026-10-13 — 013 파일) |
| `frontend/src/stores/compareStore.ts`·`components/compare/CompareReturnChart.tsx`·`lib/seriesDetail.ts`·`app/compare/page.tsx` | T163·T187·T188·T197(이전), T217(반복 2026-10-13) |
| `frontend/tests/setup.ts` | T169(이전), T217(반복 2026-10-13 — 설정 대역) |
| `backend/tests/integration/test_policy_rate_worker.py`·`unit/test_comparison_conditions.py`·`frontend/tests/compareStore.test.ts`·`ComparePage.test.tsx` | T215(반복 2026-10-13 — 승인 뒤에만) |

### Parallel Opportunities

- Foundational 테스트 T006~T010은 함께 쓴다. 구현 T012·T013은 함께 한다.
- US1 테스트 T019~T030은 다른 파일이라 함께 쓴다. 순수 모듈 T031·T032와 화면 lib T036·T037도 함께 한다.
- US2 테스트 T042~T050은 함께 쓴다. 순수 모듈 T052·T053은 함께 한다.
- US3 테스트 T064~T071은 함께 쓴다. 어댑터 T073~T075는 함께 한다. US3 백엔드는 US1·US2 화면 작업과 나란히 할 수 있다.

---

## Parallel Example: Phase 3 (US1 테스트)

```text
Task: "T019 test_market_session.py — 다섯 상태·서머타임·밤 넘는 세션"
Task: "T020 test_market_quote.py — 이력 전일·출처 물러남·상해·엔 ×100·음수 전일·지연"
Task: "T021 test_yahoo_market_quotes.py — spark 15개·빠진 심볼·429"
Task: "T022 test_market_quotes_service.py — 캐시·단일 비행·실패 기억·stale"
Task: "T023 test_dashboard_quotes_api.py — A1·이력 전일·fx_rate 무변경"
Task: "T024 kstClock.test.ts · T025 TodayHeader.test.tsx · T026 IndicatorCard.test.tsx"
Task: "T027 marketQuotesStore.test.ts · T028 DashboardPage.test.tsx · T029 RootRedirect.test.tsx · T030 dashboardNoClientFinance.test.ts"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1(기준 응답·기준 게이트·DB 머리·tzdata) → Phase 2(지표 목록·설정·관문·테이블·저장소·픽스처)
2. Phase 3 (US1) — **멈추고 검증**(T041): 카드 15개가 다섯 상태·전일 규칙·실패 분리대로 보이고, 다른 메뉴는 그대로다.

### Incremental Delivery

1. MVP(US1) — 카드(승인 A — T018)
2. US2 — 이력 수집·지표 화면
3. US3 — 뉴스
4. Polish — 성능·화면 폭·불변 대조·문서·게이트
5. 반복 2026-10-10 — 출처·실패 요구 보강(Phase 7, 완료)
6. 반복 2026-10-10b — 지표 모달·기간 8개·변화 까닭·일자별 표(Phase 8). 원칙 II 재승인(T095)이 안 되면 까닭·장중을 빼고 모달·일봉 기간 6개·표만 낸다
7. 반복 2026-10-10c — 차트 앞 구간 스크롤·장중 실선(US2)과 블랙 배경(US4)(Phase 9). 둘은 따로 낼 수 있다 — 블랙 배경(T131·T135·T136)이 막히면(T128(c)) 차트 쪽만 낸다
8. 반복 2026-10-10d — 외환 일자별 표의 등락폭·등락율(US5)(Phase 10). 014의 다른 화면과 독립이다
9. 반복 2026-10-10e — 투자 비교의 티커 표시(US6)(Phase 11). 화면만이고 014의 다른 화면과 독립이다
10. 반복 2026-10-10f — 주식·가상자산의 상장일(US7)(Phase 12). 스키마 변경 하나 — 개발 DB `alembic upgrade head`
11. 반복 2026-10-10g — 고른 종목·코인 줄의 상장일(US7 확장)(Phase 13). 스키마 변경 없음 — 사용자 보고
12. 반복 2026-10-11 — 투자 성과표의 처음 단위 월(US8)(Phase 14). 화면만 — 사용자 요청
13. 반복 2026-10-11b — 수익률 추이의 현재 가치 축(US9)과 두 지점 확대(US10)(Phase 15). 비교 블록 키 하나 + 화면 — 사용자 요청. 둘은 따로 낼 수 있다(T186·T187과 T188)
14. 반복 2026-10-11c — 확대 구간의 일 단위 자료·외환/지표 확대·단추 자리(US11)(Phase 16). 시계열 경로의 선택 질의 둘 + 화면 — 사용자 보고
15. 반복 2026-10-11d — 대시보드 기준금리(US12)(Phase 17). 새 테이블 셋·새 워커·새 경로 넷 + 화면 — 사용자 요청. 원칙 II 새 경로라 T202 승인이 먼저다(승인되지 않으면 이 Phase는 빠진다)
16. 반복 2026-10-13 — 투자 비교의 대상 수 설정(US13)(Phase 18). 새 테이블 하나·새 경로 하나(GET·PUT) + 비교 화면의 차례 한도·선 짝·커서 상자 — 사용자 요청. 013 FR-004 대체

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(014): <페이즈>`
     - 그 페이즈의 새 테스트·픽스처와 **승인된 기존 테스트 변경**을 담는다(승인 날짜를 적는다).
     - **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는 예정된 것이다.
     - 구현을 먼저 해 둔 경우(승인 목록을 만들려고)는 구현을 잠시 치워(`git stash push -u -- backend/src frontend/src`) 실패를 확인한 뒤 커밋하고 되돌린다(013과 같다).
  2. **구현 커밋** — `feat(014): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다.
  - 테스트가 없는 태스크만 있는 페이즈·태스크(기준 기록, 실측 확인, 문서)는 한 번 커밋한다(`docs(014): …`).
  - 실측에서 찾은 결함은 `test(014)`(실패 확인) → `fix(014)` 두 커밋이다.
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다.** 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2).
- **커밋 전 확인**
  - `.env`가 추적되지 않는다. 스테이지에 키·비밀번호가 없다. `.venv/`·`node_modules/`·`.next/`·`logs/` 경로가 없다.
  - 작업용 비밀 검사 스크립트를 돌린다(푸시 때는 `"@{u}..HEAD"` 범위).
  - 커밋 메시지는 한국어이고 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`을 단다. 푸시는 요청이 있을 때만 한다.
- 기록:
  - T002 기준 게이트(2026-10-09, 서버를 내린 채): 백엔드 `pytest` 3,034 passed(9분 43초)·커버리지 96%·`mypy` 239파일 통과·`ruff` 통과, 프론트엔드 `vitest` 193파일 1,702 passed·`tsc`·`eslint` 통과(모두 종료 코드 0). 기준 응답(T001)은 작업용 임시 폴더 `014-baseline/before/` 29파일
  - T018 승인(2026-10-10 — 사용자 사전 승인 "중간에 승인이 필요하면 모두 승인"): 실제 실패 7개 = 예상 목록(R14-16)과 같다. `Sidebar.test.tsx` 넷(링크 아님 → 모든 항목 링크, 준비중 1 → 0, 초점 대상 0 → 링크 하나, 링크 목록 + `/dashboard`), `noUnbuiltAssetRoutes.test.ts` 셋(`UNBUILT` → `[]`, 경로 + `/dashboard`, API 정규식에서 `dashboard`). `TopBarTitle.test.ts`는 변경 없음
  - US2 구현(2026-10-10): 기존 테스트 승인 변경 5건(사용자 사전 승인) — lifespan 태스크 수 8 → 9(부동산·가상자산·예금 워커 테스트), SSE 머리글 검사에 지표 수집 진행·SSE 파일 목록에 `dashboard_series.py`. 예상 목록(R14-16)에 없던 변경이다 — 아홉째 태스크와 새 SSE 경로가 기존 테스트의 목록에 걸렸다. 구현을 치운 상태에서 5건 실패 확인 뒤 `test(014)` 커밋. `indicator_series`는 세션과 저장소 모듈을 받는다(외환 `series_query`와 같은 꼴 — 시세 캐시만 Protocol `QuoteLookup`). `lib/chartSeries.splitSeriesAtGaps`의 결측 인자를 사유 글자로 넓혔다(형만 — 지표의 `missing`도 끊는다, 동작 불변)
  - T080 파싱 시간(2026-10-10, 100번 평균): 네이버 JSON 10.7KB 0.09ms · Yahoo US 줄인 본 47KB 2.16ms(원본 952KB 14.35ms) · Yahoo JP 줄인 본 8.7KB 0.11ms(원본 86KB 0.14ms) — 모두 50ms 아래라 `run_in_executor`로 옮기지 않았다. 원본 두 본문에서도 줄인 본과 같은 10개를 읽는다
  - US3 구현(2026-10-10): 계약 테스트 T065의 기대 제목 하나를 고쳤다 — 출처 제목에 `&nbsp;`(U+00A0) 둘이 있는데 받아 적을 때 공백으로 보였다. 파서는 원문 그대로가 맞다(FR-021 — 같은 기사 가리기만 공백으로 접는다). 테스트 쪽 받아 적기 잘못이라 기대값을 고쳤다(사용자 사전 승인). 새 모듈이 생겨 ruff가 테스트 임포트 차례를 다시 정렬했다(I001)
  - 반복 2026-10-10(T087~T094 — 체크리스트 `checklists/sources.md` 반영): 게이트(서버를 내린 채) 백엔드 `pytest` 3,258 passed(10분 18초)·커버리지 96%·`mypy` 265파일·`ruff` 통과, 프론트엔드 `npm test` 206파일 1,814 passed·`tsc`·`eslint` 통과(모두 종료 코드 0)
    - 검토 중 찾은 결함 둘을 고쳤다: 환율 지표 화면이 외환 진행 스트림을 구독해 진행이 비고 외환 수집 실패가 보이지 않으며 다시 물을 때마다(15초) 외환 수집을 다시 요청함 → 대시보드 진행 경로·`fx_collection` 실패·재요청 안 함. 카드·뉴스 출처의 실패와 뉴스 호출이 로그에 없음 → `collection.log` 사건 셋
    - 014의 기존 기대 하나를 바꿨다(`test_환율_이력이_모자라면_외환_수집_경로`의 진행 주소 — 결함을 담고 있었다). 빨간 커밋 뒤 사건 칸 이름을 `message` → `detail`로 고쳤다(`LogRecord` 예약 이름 — 실제 로거가 예외를 낸다) — 실제 로거를 부르는 테스트를 더했다
    - 실측은 하지 않았다 — 개발 DB의 환율 이력이 충분해 외환 수집 실패 경로를 만들 수 없다(통합 테스트로만 확인)
  - T086 게이트(2026-10-10, 서버를 내린 채): 백엔드 `pytest` 3,246 passed(10분 28초)·커버리지 96%·`mypy` 265파일 통과·`ruff` 통과, 프론트엔드 `npm test` 206파일 1,813 passed·`tsc`·`eslint` 통과(모두 종료 코드 0)
    - `90e848b` 이후 바뀐 기존 테스트 파일은 여섯이고 지운 파일은 없다(`git diff --stat --diff-filter=MD`) — 승인 목록과 같다
      - T018 승인: `Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`
      - US2 승인: `test_apt_worker.py`·`test_crypto_worker.py`·`test_deposit_worker.py`·`test_progress_sse.py`
    - 실측 결함 셋은 `test(014)` → `fix(014)`로 고쳤다 — Yahoo 긴 응답 머리·받은 시각의 마이크로초(T081), 1024px 뉴스 칸(T083)

---

## 요구사항 ↔ 태스크

모든 FR·SC가 하나 이상의 태스크에 참조된다(헌법 명세 작성 규약).

| 요구사항 | 태스크 |
|----------|--------|
| FR-001 | T018, T028, T029, T040, T041 |
| FR-002 | T024, T025, T037, T039 |
| FR-003 | T006, T012, T013, T023, T028, T035, T036, T083 |
| FR-004 | T020, T023, T026, T030, T032, T036, T039 |
| FR-005 | T010, T016, T020, T023, T026, T032, T034, T039, T041, T087 |
| FR-006 | T007, T011, T019, T026, T031, T039, T041 |
| FR-007 | T019, T020, T026, T031, T032, T039 |
| FR-008 | T007, T011, T022, T025, T027, T028, T034, T038, T039, T061 |
| FR-009 | T005, T021, T022, T023, T026, T027, T028, T033, T034, T035, T038, T039, T087, T089, T092 |
| FR-010 | T047, T048, T050, T057, T058, T059, T060, T061, T062, T096, T106, T110, T111, T122, T123 |
| FR-011 | T044, T048, T049, T050, T053, T059, T060, T061, T104, T105, T107, T115, T119, T120, T121, T123, T124, T128, T129, T130, T132, T133, T134, T137 |
| FR-012 | T044, T047, T049, T053, T056, T060, T082, T104, T105, T107, T115, T121, T124, T129, T130, T132, T133, T134, T137 |
| FR-013 | T044, T049, T053, T060, T104, T108, T111, T114, T117 |
| FR-014 | T043, T047, T049, T052, T056, T060, T104, T105, T108, T114, T115 |
| FR-015 | T006, T012, T026, T039, T050, T060 |
| FR-016 | T046, T047, T048, T050, T056, T057, T058, T059, T060, T062, T087, T088, T090, T091, T093, T105, T106, T108, T117, T120 |
| FR-017 | T005, T009, T010, T015, T016, T042, T045, T046, T051, T054, T062, T097, T098, T099, T100, T101, T112, T123 |
| FR-018 | T006, T012, T013, T021, T023, T026, T033, T039, T047, T050, T056, T060, T062, T087, T088, T090, T091, T093, T105, T115, T117, T123 |
| FR-019 | T007, T008, T010, T011, T014, T015, T016, T017, T042, T045, T046, T047, T050, T051, T054, T055, T056, T057, T087, T098, T100 |
| FR-020 | T063, T064, T065, T066, T068, T070, T072, T073, T074, T075, T077, T079, T081, T083, T087 |
| FR-021 | T064, T065, T066, T070, T073, T074, T075, T079, T087 |
| FR-022 | T064, T065, T066, T070, T073, T074, T075, T079, T081, T087, T103, T109 |
| FR-023 | T007, T011, T067, T068, T076, T087, T089, T092 |
| FR-024 | T064, T065, T066, T067, T068, T069, T070, T071, T072, T076, T077, T078, T079, T081, T087 |
| FR-025 | T070, T079, T085, T121, T126, T140 |
| FR-026 | T001, T002, T008, T014, T017, T084, T085, T086, T125, T128, T135, T139, T144, T148, T152, T155, T161, T165, T169, T170, T174, T177, T180, T185, T190, T195, T200, T206, T211, T215, T219 |
| FR-027 | T095, T103, T104, T105, T109, T113, T118, T119, T120, T121, T123 |
| FR-028 | T095, T102, T104, T105, T107, T112, T116, T121, T123, T128, T129, T132, T133, T137 |
| FR-029 | T104, T105, T108, T114, T117, T119, T120, T121, T123, T124 |
| FR-030 | T128, T131, T135, T136, T137, T140 |
| FR-031 | T142, T143, T145, T146, T147, T149 |
| FR-032 | T151, T153, T154, T156 |
| FR-033 | T158, T159, T160, T162, T163, T164, T166 |
| FR-034 | T168, T169, T171, T172, T173, T174 |
| FR-035 | T176, T177, T178, T179, T180 |
| FR-036 | T182, T183, T185, T186, T187, T189, T190 |
| FR-037 | T184, T185, T188, T189 |
| FR-038 | T192, T193, T195, T196, T197, T198, T199, T200 |
| FR-039 | T194, T195, T197, T198, T199 |
| FR-040 | T202, T204, T205, T208, T209, T210 |
| FR-041 | T204, T205, T208, T209, T210 |
| FR-042 | T202, T204, T205, T208, T209, T210 |
| FR-043 | T202, T203, T204, T207, T210 |
| FR-044 | T213, T214, T215, T216, T217, T218 |
| FR-045 | T213, T214, T215, T216, T217, T218 |
| FR-046 | T214, T217, T218 |
| SC-001 | T071, T082, T087 |
| SC-002 | T047, T056, T082, T107, T124, T130, T138 |
| SC-003 | T010, T020, T023, T032, T041 |
| SC-004 | T047, T056, T062 |
| SC-005 | T043, T044, T052, T053 |
| SC-006 | T009, T010, T015, T016, T046, T054, T062 |
| SC-007 | T022, T034, T064, T065, T066, T068, T071, T081, T087, T094 |
| SC-008 | T064, T065, T066, T068, T070, T081, T089, T092 |
| SC-009 | T019, T026, T031 |
| SC-010 | T001, T002, T084, T086, T094, T125, T127, T139, T141, T148, T150, T155, T157, T165, T167, T174, T175, T180, T181, T190, T191, T200, T201, T211, T212, T215, T219, T220 |
| SC-011 | T062, T087 |
| SC-012 | T104, T108, T124 |
| SC-013 | T103, T109, T123 |
| SC-014 | T097, T098, T101, T123 |
| SC-015 | T128, T131, T136, T137, T139 |
| SC-016 | T142, T147, T148 |
| SC-017 | T151, T154, T155 |
| SC-018 | T159, T164, T165 |
| SC-019 | T168, T169, T173, T174 |
| SC-020 | T176, T179, T180 |
| SC-021 | T182, T183, T189, T190 |
| SC-022 | T184, T189 |
| SC-023 | T192, T193, T199, T200 |
| SC-024 | T194, T199 |
| SC-025 | T204, T205, T210 |
| SC-026 | T203, T204, T205, T210 |
| SC-027 | T213, T214, T218 |
| SC-028 | T214, T218, T219 |
