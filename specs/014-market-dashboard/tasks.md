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
- **[Story]**: 소속 사용자 스토리 (US1~US3)
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

- [ ] T005 Yahoo 픽스처를 옮긴다 — `backend/tests/contract/fixtures/market/` + `README.md` (FR-017, FR-009, R14-1)
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

- [ ] T006 [P] `backend/tests/unit/test_market_indicators.py` — `simulation/market_indicators` (FR-003, FR-015, FR-018, data-model 2)
  - 정확히 15개이고 `order` 1~15다.
  - 묶음 `korea`·`us`·`asia`·`fx`·`commodity`의 구성·차례가 data-model 2 표와 같다.
  - 단위 글자: 포인트·원·원(100엔당)·USD/배럴·USD/트로이온스.
  - `kind`: `index`·`fx`·`future`·`volatility`.
  - 결측 묶음: `krx`(kospi·kosdaq), `us_equity`(넷), `cme`(wti·gold). 나머지는 `None`.
  - 이력 원천: `fx` 셋만 외환이다. 주석: `future` → `future_roll`, `fx` → `market_fx`.
  - `get(id)`는 없는 id에 `None`이다.
  - 이 모듈은 출처 심볼을 담지 않는다 — `"^"`·`"=F"`·`"=X"` 글자가 없다.
- [ ] T007 [P] `backend/tests/unit/test_settings_market.py` — `config/settings` (FR-006, FR-008, FR-019, FR-023, data-model 8)
  - data-model 8 표의 모든 env(24개)에 값이 없으면 표의 기본값이다(예: `MARKET_CHUNK_DAYS=730`, `MARKET_QUOTE_CACHE_SECONDS=30`, `MARKET_HOLIDAY_DETECT_SECONDS=3600`, `DASHBOARD_SERIES_MAX_POINTS=30000`, `NEWS_CACHE_SECONDS=600`, `YAHOO_MAX_CONCURRENT_REQUESTS=2`).
  - 값을 주면 그 값이다. 최솟값(`minimum=`) 아래는 거절한다(기존 `_env_int` 관례).
  - `NEWS_*_URL` 기본값이 R14-13의 요청 주소다.
- [ ] T008 [P] `backend/tests/contract/test_yahoo_gate.py` — `ingestion/yahoo/gate` (FR-019, FR-026, R14-10)
  - 동시 자리는 `YAHOO_MAX_CONCURRENT_REQUESTS`를 넘지 않는다.
  - 한 쪽이 `pause(s)`하면 그동안 다른 쪽의 `slot()`이 기다린다. 대기는 호출 시점의 `asyncio.sleep`을 찾는다 — 테스트가 가로챈다(`EcosGate` 테스트와 같은 꼴).
  - 이벤트 루프마다 관문이 따로다.
  - `YahooStockClient(settings, session=스텁)`(gate 없음)은 429 뒤 재시도·백오프가 지금 그대로다.
  - `YahooStockClient(settings, session=스텁, gate=관문)`은 429에 관문을 쉬게 하고, 같은 스텁 응답에서 돌려주는 `ChartFetch`가 gate 없을 때와 같다.
- [ ] T009 [P] `backend/tests/integration/test_market_schema.py` — 마이그레이션·모델 (FR-017, SC-006, data-model 1)
  - 새 리비전의 `down_revision == "b3e7d5a1c924"`. `upgrade`·`downgrade`가 된다.
  - `market_indicator_daily`: PK `(indicator_id, trade_date)`, `indicator_id` `String(32)`, `close` `DECIMAL(20,6)` NOT NULL, `source` `String(64)` NOT NULL, `ingested_at` 기본값.
  - `market_indicator_raw.body`는 MEDIUMTEXT, `(indicator_id, received_at)` 색인.
  - `market_indicator_coverage`: `indicator_id` PK, `first_day`·`covered_from`·`covered_through` NULL 허용, `last_failure_kind` `String(32)`, `last_failure_message` `String(500)`.
  - `market_close_revision`: `stored_close`·`source_close` `DECIMAL(20,6)`, 같은 `(indicator_id, trade_date, source_close)`는 한 번만(유일 색인).
  - 기존 `test_금액_컬럼에_부동소수점이_없다`가 새 표에도 통과한다.
- [ ] T010 [P] `backend/tests/integration/test_market_repository.py` — `repository/market_daily` (FR-005, FR-017, FR-019, SC-003, SC-006, data-model 1)
  - `store_closes`: 없는 날만 넣고, 넣은 수를 돌려준다.
  - 있는 날의 값이 같으면 아무것도 하지 않는다. 다르면 저장 값은 그대로 두고 `market_close_revision` 한 줄을 넣는다. 같은 개정을 다시 받아도 한 줄이다. 개정 목록을 돌려준다.
  - `store_raw`는 본문을 그대로 넣는다.
  - `record_coverage`는 요청 범위를 기존 연속 구간과 합친다(받은 범위만 — 실패한 청크는 넣지 않는다). `first_day` 기록, 실패 기록·성공 기록이 된다.
  - `closes(id, start, end)`는 날짜 차례다. `previous_close(id, before)`는 `before`보다 앞선 마지막 행이다.
  - `coverage_reaches(id, day)`는 `covered_through ≥ day`다.

### Implementation for Foundational

- [ ] T011 `backend/src/config/settings.py` + 저장소 루트 `.env.example` — data-model 8 표의 설정을 그 이름·기본값 그대로 더한다 (FR-006, FR-008, FR-019, FR-023)
  - `# ── 014 대시보드 ──` 묶음에 둔다. 초 단위 env는 기존 도우미(`_env_seconds_ms` 등)의 관례를 따른다.
  - `.env.example`에 줄마다 한국어 설명을 단다.
- [ ] T012 [P] `backend/src/simulation/market_indicators.py` — 고정 15개(data-model 2): `Indicator`(frozen dataclass), `INDICATORS`, `get(id)`, 묶음 이름표. 출처 심볼 없음 (FR-003, FR-015, FR-018)
- [ ] T013 [P] `backend/src/ingestion/yahoo/market_symbols.py` — 지표 id ↔ 차트·spark 심볼·값 배수(`jpy` = `Decimal(100)`, 나머지 1). 대응의 유일한 곳이다 (FR-003, FR-018, R14-1)
- [ ] T014 `backend/src/ingestion/yahoo/gate.py` + `backend/src/ingestion/yahoo/client.py` (FR-019, FR-026, R14-10)
  - `YahooGate(limit)`의 `slot()`·`pause(seconds)`, `get_yahoo_gate(settings)`(이벤트 루프마다 하나 — `ingestion/ecos/gate.py`와 같은 꼴).
  - `YahooStockClient.__init__`에 키워드 인자 `gate: YahooGate | None = None`을 더한다. `_get`은 gate가 있으면 `slot()` 안에서 보내고, 429면 백오프만큼 `pause`한다. 없으면 지금 그대로다.
- [ ] T015 `backend/src/db/models.py` + `backend/src/db/migrations/versions/<12hex>_대시보드_지표.py` — data-model 1의 테이블 넷 (FR-017, FR-019, SC-006)
  - 형·제약을 data-model 1 그대로 둔다: `PRICE = Numeric(20, 6)`, `String(32)`·`String(64)`·`String(500)`, MEDIUMTEXT `Text(16_777_215)`, `TS = DateTime(timezone=False)`, 개정 유일 색인.
  - 독스트링 관례: 제목(014)·설명·Revision ID·Revises·Create Date.
- [ ] T016 `backend/src/repository/market_daily.py` — T010의 함수들 (FR-005, FR-017, FR-019, SC-006)
  - `SOURCE = "yahoo:chart"`.
  - 종가는 ORM 조회 + 삽입(1000개씩). 커버리지는 `db/dialect.upsert`(`preserve=()`).
  - 개정은 유일 색인 충돌을 무시하지 않고 미리 조회해 거른다(방언 문법 없음).
- [ ] T017 `backend/src/api/main.py` + `backend/src/api/routes/stock_search.py` — 관문을 주식 클라이언트에 넘긴다 (FR-019, FR-026, R14-10)
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

- [ ] T018 [US1] 기존 테스트 변경 승인을 받는다 — research R14-16의 목록 (FR-001)
  - 절차: 이 페이즈의 테스트(T019~T030)를 쓰고 구현(T031~T040)을 마친다. 구현을 작업 트리에 둔 채 전체 스위트를 돌려 **실제로 실패한** 기존 테스트로 목록을 만든다.
  - 예상:
    - `frontend/tests/Sidebar.test.tsx` — 준비 안 된 항목 `["대시보드"]` → 없음, "준비중" 1 → 0, 대시보드 `li`의 초점 대상 0 단언 삭제, 링크 목록에 `/dashboard`
    - `frontend/tests/noUnbuiltAssetRoutes.test.ts` — `UNBUILT = ["dashboard"]` → `[]`, 링크 목록에 `/dashboard`, API 호출 금지 정규식에서 `dashboard`
    - (표가 전체를 고정하면) `frontend/tests/TopBarTitle.test.ts`
  - 테스트마다 "지금 단언 → 새 단언"으로 보이고 승인을 받는다. 고친 줄에 `// 014 승인 YYYY-MM-DD`를 단다. 목록 밖의 실패는 결함으로 보고 멈춘다.
- [ ] T019 [P] [US1] `backend/tests/unit/test_market_session.py` — `simulation/market_session` (FR-006, FR-007, SC-009, R14-7, data-model 3)
  - **krx**: 출처 세션 시작이 10-08인데 현지 오늘이 10-09 → `holiday`. 거래일 08:30 → `pre_open`, 10:00 → `open`, 15:31 → `closed`(출처의 15:00을 쓰지 않는다).
  - **tse**: 11:45 → `break`. **hkex**: 12:30 → `break`. **sse**: 12:00 → `break`.
  - **us_equity 서머타임**: 2026-03-09(월) 한국 22:30 → `open`, 2026-03-06(금) 한국 22:30 → `pre_open`. 2026-11-02(월) 한국 23:30 → `open`, 22:45 → `pre_open`.
  - **cme**: 금 17:30 뉴욕 → `closed`, 토 → `holiday`, 일 18:30 → `open`이고 `trading_date`는 다음 월요일. 평일 17:30 → `break`(쉼).
  - **fx**: 토 → `holiday`, 일 17:30 뉴욕 → `open`.
  - **cboe**: 08:00 시카고 → `pre_open`.
  - **갱신 없는 세션**(I1 — R14-7): cme 성탄절에 일정상 세션 안이고 값 시각이 전날 세션이면 시작 30분 뒤 `pre_open`, 2시간 뒤 `holiday`다. fx 1월 1일도 같다.
    값 시각이 이번 세션 시작 뒤면 `open`이다.
  - 주말은 늘 `holiday`다.
- [ ] T020 [P] [US1] `backend/tests/unit/test_market_quote.py` — `simulation/market_quote` (FR-004, FR-005, FR-007, SC-003, R14-8, R14-9, data-model 4)
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
- [ ] T021 [P] [US1] `backend/tests/contract/test_yahoo_market_quotes.py` — `ingestion/yahoo/market` 시세 쪽 (FR-009, FR-018, R14-6)
  - `spark_v7_1d.json` → 15개 `SourceQuote`(가격·값 시각·`fulldayChange`·`chartPreviousClose`·세션 시작·시간대)를 `Decimal`로 읽는다.
  - 빠진 한 심볼만 `chart?range=1d&interval=1d`로 다시 부른다(요청 기록). spark가 429이면 다시 부르지 않고 관문을 쉬게 한다.
  - 요청 질의는 `symbols`가 15개, `range=1d`·`interval=1d`다.
  - 깨진 본문은 `invalid_body`, 404는 `not_found`다.
- [ ] T022 [P] [US1] `backend/tests/unit/test_market_quotes_service.py` — `api/services/market_quotes` (FR-008, FR-009, SC-007, R14-6)
  - 가짜 `MarketQuoteSource`·`MarketHistoryRepository`를 쓴다.
  - 30초 안 두 호출 = 출처 한 번. 동시에 온 두 호출도 한 번이다(단일 비행). 31초 뒤는 다시 부른다.
  - 출처 실패는 10초만 기억한다. 마지막 성공 값이 있으면 그 지표는 `stale: true` + `failure`, 없으면 `status: "failed"` + `quote: None`이다.
  - 한 심볼만 빠지면 그 지표만 실패다.
  - 이력 전일·커버리지를 저장소 Protocol로 읽는다.
- [ ] T023 [P] [US1] `backend/tests/integration/test_dashboard_quotes_api.py` — `GET /api/dashboard/quotes` (FR-003, FR-004, FR-005, FR-009, FR-018, SC-003, contracts A1)
  - 스텁 출처를 쓴다. 응답은 15개이고 `order` 차례다. 칸 이름·형이 contracts A1과 같다(값은 문자열).
  - `market_indicator_daily`에 10-07 행 + 커버리지를 두면 `previous.from = "history"`이고 `date = 2026-10-07`이다. 행을 지우면 `"source"`다.
  - 환율 셋은 `source_fx`이고 `notes`에 `market_fx`, 선물 둘은 `future_roll`이다.
  - `refreshAfterSeconds`는 설정값이다. 출처 전체 실패여도 200이다.
  - `fx_rate`에 아무것도 쓰지 않는다(행 수 전후 같음).
- [ ] T024 [P] [US1] `frontend/tests/kstClock.test.ts` — `lib/kstClock` (FR-002, R14-15)
  - 브라우저 시간대를 `America/New_York`로 두어도 한국 날짜·요일이다(`2026년 10월 9일 (금)`).
  - 한국 23:59:30에서 다음 자정까지 30초다.
- [ ] T025 [P] [US1] `frontend/tests/TodayHeader.test.tsx` — `components/dashboard/TodayHeader` (FR-002, FR-008)
  - 가짜 시계로 한국 자정을 넘기면 날짜 글자가 바뀐다.
  - 받은 시각과 [새로고침] 단추가 있고, 누르면 `onRefresh`가 불린다(contracts D1).
- [ ] T026 [P] [US1] `frontend/tests/IndicatorCard.test.tsx` — `components/dashboard/IndicatorCard`·`QuoteStateLine` (FR-004, FR-005, FR-006, FR-007, FR-009, FR-015, FR-018, SC-009, contracts D2)
  - **상태**: 다섯 상태의 글자와 ⏳·`확정 전`·`약 10분 지연`이 보인다.
  - **색**: 오르면 ▲·`text-red-700`, 내리면 ▼·`text-blue-700`, flat은 회색·화살표 없음이다.
  - **전일**: `previous.from = "source"` → "전일 값: 출처(이력에 아직 없음)", `source_fx` → "런던 0시 기준"이다.
  - **주석**: `market_fx`·`future_roll`의 문구가 보인다.
  - **실패**: `stale` → "새로 받지 못함" + 기준 시각 + [다시 시도], `failed` → "—" + 까닭 + [다시 시도]다.
  - **등락률 없음**: `changeRate null` → "—"와 설명(`title`)이다.
  - **형식**: 등락률은 `formatPercent`(천 단위 쉼표), 값은 `formatRate`다.
  - **링크**: 카드는 `href="/dashboard/{id}"`이고 접근 이름은 "{이름} 추이 보기"다.
- [ ] T027 [P] [US1] `frontend/tests/marketQuotesStore.test.ts` — `stores/marketQuotesStore` (FR-008, FR-009)
  - `startPolling`이 `refreshAfterSeconds`마다 부른다(가짜 시계).
  - `visibilityState = "hidden"`이면 부르지 않고, `visibilitychange`로 보이면 곧바로 부른다.
  - 늦게 온 옛 응답(`seq`)은 버린다. `retry(id)`는 같은 경로를 다시 부른다.
  - `stopPolling` 뒤에는 부르지 않는다.
  - `startPolling`을 두 번 불러도 타이머는 하나다(대시보드 → 지표 화면으로 옮겨도 갱신이 두 번 걸리지 않는다 — U1).
- [ ] T028 [P] [US1] `frontend/tests/DashboardPage.test.tsx` — `app/dashboard/page.tsx` (FR-001, FR-003, FR-008, FR-009, contracts D1)
  - 묶음 다섯이 이름표(한국·미국·일본·중국·환율·원자재·변동성)와 함께 `order` 차례로 보인다.
  - 한 지표 `failed`에도 나머지 14개가 보인다.
  - 출처 줄(Yahoo Finance·한국은행 ECOS)이 있다.
  - 사이드바의 "대시보드"는 `/dashboard` 링크이고 선택된 상태다(`AppShell`과 함께 그릴 때).
  - [새로고침]을 누르면 시세 경로가 한 번 더 불리고, 뉴스 경로는 불리지 않는다(U3 — contracts D1).
- [ ] T029 [P] [US1] `frontend/tests/RootRedirect.test.tsx` — `app/page.tsx`가 `next/navigation`의 `redirect("/dashboard")`를 부른다(모의). 옛 안내 글("준비 중입니다")이 없다 (FR-001)
- [ ] T030 [P] [US1] `frontend/tests/dashboardNoClientFinance.test.ts` — `components/dashboard/`·`stores/marketQuotesStore.ts`·`stores/indicatorSeriesStore.ts`·`stores/newsStore.ts`·`lib/dashboardApi.ts`에 `Number(`·`parseFloat(`·`parseInt(`가 없다 (FR-004, 원칙 VI — 013 `compareNoClientFinance`와 같은 꼴)
  - 차트의 그리기 전용 변환은 `IndicatorChart.tsx` 한 파일만 허용하고, 사유 주석을 요구한다.

### Implementation for User Story 1

- [ ] T031 [P] [US1] `backend/src/simulation/market_session.py` — R14-7 표의 시간표(`time` 값)·`trading_date`·`market_state`·`MarketState`. `zoneinfo` (FR-006, FR-007, SC-009)
- [ ] T032 [P] [US1] `backend/src/simulation/market_quote.py` — `compose_quote(indicator, source_quote, history_previous, coverage_through, now, fetched_at, settings값)` → `MarketQuote`(data-model 4). `Decimal`과 `quantize_rate` (FR-004, FR-005, FR-007, SC-003)
- [ ] T033 [US1] `backend/src/ingestion/yahoo/market_parse.py`(시세 쪽) + `backend/src/ingestion/yahoo/market.py`(`YahooMarketClient.fetch_quotes(symbols)`) (FR-009, FR-018, R14-6)
  - `async with`로 세션을 연다(UA·`Accept: application/json` — 주식 클라이언트와 같은 꼴). 늘 `YahooGate`를 지난다.
  - 재시도·백오프는 `MARKET_RETRY_*`, 오류 분류는 `ingestion/yahoo/errors.raise_for_response`를 쓴다.
  - spark에 빠진 심볼만 차트 `range=1d`로 받는다. 본문은 `json.loads(parse_float=Decimal)`로 읽는다.
- [ ] T034 [US1] `backend/src/api/services/market_quotes.py` — Protocol `MarketQuoteSource`·`MarketHistoryRepository`, 캐시(30초)·단일 비행(`asyncio.Lock`)·실패 기억(10초)·지표별 마지막 성공 값, 응답 JSON 조립(contracts A1) (FR-005, FR-008, FR-009, SC-007)
- [ ] T035 [US1] `backend/src/api/routes/dashboard_quotes.py` + `backend/src/api/main.py` (FR-003, FR-009, contracts A1)
  - `lifespan`에서 `YahooMarketClient`를 열고 닫는다. 시세 서비스를 앱 상태에 둔다.
  - 라우터는 기존 라우터 뒤에 등록한다.
- [ ] T036 [P] [US1] `frontend/src/lib/types.ts`(대시보드 시세 타입 — contracts A1) + `frontend/src/lib/dashboardApi.ts`(`fetchQuotes` — 공통 `request`) (FR-003, FR-004)
- [ ] T037 [P] [US1] `frontend/src/lib/kstClock.ts` — `Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", … })`, `msUntilNextKstMidnight(now)` (FR-002, R14-15)
- [ ] T038 [US1] `frontend/src/stores/marketQuotesStore.ts` — data-model 7 (`load`·`startPolling`·`stopPolling`·`retry`, `seq`, `document.visibilityState`) (FR-008, FR-009)
- [ ] T039 [US1] `frontend/src/components/dashboard/TodayHeader.tsx`·`IndicatorGroups.tsx`·`IndicatorCard.tsx`·`QuoteStateLine.tsx` — contracts D1·D2. 값은 서버 문자열에 형식만 입힌다. `TodayHeader`의 [새로고침]은 `marketQuotesStore.load()`다 (FR-002, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-015, FR-018)
- [ ] T040 [US1] 화면 경로를 붙인다 (FR-001, R14-14, contracts D6)
  - `frontend/src/app/dashboard/page.tsx`(마운트에 `load`·`startPolling`, 언마운트에 `stopPolling`).
  - `frontend/src/app/page.tsx` → `redirect("/dashboard")`(옛 안내 자리 삭제).
  - `frontend/src/components/shell/Sidebar.tsx` → `{ label: "대시보드", href: "/dashboard" }`.
  - `frontend/src/components/shell/TopBar.tsx` → `["/dashboard", "대시보드"]`를 `/`보다 앞에.
- [ ] T041 [US1] 실측 확인 — quickstart 5-1~5-3을 헤드리스 Chrome(CDP)으로 확인하고 `quickstart.md` 8에 기록한다 (FR-001, FR-005, FR-006, SC-003)
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

- [ ] T042 [P] [US2] `backend/tests/contract/test_yahoo_market_client.py` — `ingestion/yahoo/market` 일봉 쪽 (FR-017, FR-019, R14-2, R14-3, R14-4)
  - 겨울 CL=F 자정 행이 뉴욕 날짜다(하루 앞당겨지지 않는다 — `gmtoffset`과 다른 결과를 단언).
  - 종가 `null` 행을 버린다. `firstTradeDate`를 읽는다. 2020-04-20 −37.63을 그대로 읽는다.
  - 오늘(현지) 봉은 `today_bar`로 따로 내고 확정 목록에 넣지 않는다.
  - 청크 요청이 `interval=1d&period1&period2`다. 1970년 이전은 음수 `period1`이다(1927 구간 픽스처).
  - 숫자가 `Decimal`이다.
- [ ] T043 [P] [US2] `backend/tests/unit/test_market_gaps.py` — `simulation/market_gaps` (FR-014, SC-005, R14-5)
  - 다우만 빈 평일 → `missing`, 넷 다 빈 평일 → 휴장이다.
  - SOX 첫 날 전에는 다우와 견주지 않는다.
  - 상해 국경절(10-01~10-08 빈 평일) → 휴장, 15일 공백 → 그 사이 평일 `missing`이다.
  - 주말은 늘 휴장, 커버리지 밖은 판정하지 않는다. 결과 구간이 연속 날짜로 합쳐진다.
- [ ] T044 [P] [US2] `backend/tests/unit/test_indicator_periods.py` — `simulation/indicator_periods` (FR-011, FR-012, FR-013, SC-005, data-model 5)
  - **대조**: 같은 거래일 목록에서 주·월 대표일이 012 `period_table.build_table`의 대표일과 같다.
  - **년**: 12-31 이하 마지막 거래일이다.
  - **`shifted`**: 금요일 휴장 → 목요일 대표 + `shifted`, 말일·12-31도 같다.
  - **`ongoing`**: 이번 주·달·해의 점이 `ongoing`이다.
  - **잠정 꼬리**: 일 단위는 마지막 점이 `provisional`이다. 주 단위는 그 주 대표가 꼬리이면 `provisional` + `ongoing`이다.
  - **빈 기간**: 거래일이 없는 주는 점이 없다.
- [ ] T045 [P] [US2] `backend/tests/unit/test_market_runner_plan.py` — `worker/market_runner`의 할 일 계획(순수 부분) (FR-017, FR-019, R14-2, R14-11)
  - 커버리지 없음 → "최근 청크"(현지 어제에서 끝나는 730일)다.
  - `first_day`가 있고 `covered_from > first_day` → 그 앞 730일 청크(첫 날에서 멈춤)다.
  - `covered_through < 현지 어제` → 이어 받기(겹침 5일)이고, 같은 현지 날짜 안에서는 한 번뿐이다.
  - 여러 지표의 차례: 최근 청크 → 이어 받기 → 과거 구간을 지표마다 돌아가며.
  - **오래 꺼짐**(U2 — R14-2): `covered_through`가 현지 어제보다 1,000일 앞이면 이어 받기 청크 둘(730일 + 나머지)이고, 겹침 5일은 첫 청크에만 있다.
  - 이름에 `backfill` 글자를 쓰지 않는다(가드).
- [ ] T046 [P] [US2] `backend/tests/integration/test_market_worker.py` — `worker/market_worker`·`market_runner` (FR-016, FR-017, FR-019, SC-006, R14-11)
  - 스텁 `YahooMarketClient`를 쓴다.
  - **첫 바퀴**: 12개 지표의 최근 청크와 `first_day`가 기록된다.
  - **중단과 재개**: 한 청크를 실패시키면 커버리지에 그 범위가 없고 `last_failure_*`가 남는다. 다음 지표는 계속된다. 다음 바퀴에 그 청크부터 받는다.
  - **개정**: 겹친 날 값이 바뀐 응답이면 저장 값 그대로 + 개정 한 줄 + `collection.log`의 `market_close_revised`다.
  - **원본**: 같은 현지 날짜에 두 번 돌려도 원본 행이 늘지 않는다.
  - **깨우기**: 이벤트가 곧바로 한 바퀴를 돈다.
  - **취소**: 루프 취소가 클라이언트를 닫는다.
- [ ] T047 [P] [US2] `backend/tests/integration/test_dashboard_series_api.py` — A2·A3·A4 (FR-010, FR-012, FR-014, FR-016, FR-018, SC-002, SC-004, contracts A2~A4)
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
- [ ] T048 [P] [US2] `frontend/tests/indicatorSeriesStore.test.ts` — `stores/indicatorSeriesStore` (FR-010, FR-011, FR-016)
  - 202 → 진행 구독(모의 `EventSource`) → `completed`에 다시 요청 → `ready`다.
  - `setUnit`이 주소 바꾸기 콜백을 부른다.
  - 늦은 옛 단위 응답(`seq`)을 버린다.
  - 404 → `not_found`다. `retryCollect`가 POST를 부른다. `close`가 구독을 끊는다.
- [ ] T049 [P] [US2] `frontend/tests/IndicatorChart.test.tsx` — `components/dashboard/IndicatorChart` (FR-011, FR-012, FR-013, FR-014, contracts D3)
  - 이 파일 안에서 `lightweight-charts`를 모의한다(`setVisibleLogicalRange` 포함).
  - **선 나눔**: `gaps` 구간마다 `LineSeries`가 나뉜다. 휴장(빈 날)은 나뉘지 않는다.
  - **잠정**: `provisional` 점은 연한 색 계열에 있다.
  - **처음 범위**: 일 = 마지막 약 250점, 주 260, 월 240, 년 전체다.
  - **커서 상자**: 날짜·형식 입힌 값·`📅 옮김`·`⏳ 끝나지 않은 구간`·`⏳ 잠정`이 보인다.
- [ ] T050 [P] [US2] `frontend/tests/IndicatorPage.test.tsx` — 지표 화면 (FR-010, FR-011, FR-015, FR-016, FR-018, contracts D3·D4)
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

- [ ] T051 [US2] `backend/src/ingestion/yahoo/market_parse.py`(일봉 쪽) + `backend/src/ingestion/yahoo/market.py`(`fetch_daily(symbol, date_from, date_to)` → 확정 종가·오늘 봉·`firstTradeDate`·원본 본문) (FR-017, FR-019, R14-2~R14-4)
  - 날짜는 `zoneinfo.ZoneInfo(meta["exchangeTimezoneName"])`로 바꾼다.
  - 청크 사이 간격은 `MARKET_CHUNK_DELAY_MS`다.
- [ ] T052 [P] [US2] `backend/src/simulation/market_gaps.py` — R14-5 (FR-014, SC-005)
- [ ] T053 [P] [US2] `backend/src/simulation/indicator_periods.py` — data-model 5(주·월은 `period_table.period_bounds`를 부른다, 년 추가) (FR-011, FR-012, FR-013, SC-005)
- [ ] T054 [US2] `backend/src/worker/market_runner.py` — 할 일 계획(순수 함수) + 청크 실행 (FR-017, FR-019, SC-006, R14-11)
  - 청크마다 원본 → 종가(새 날만·개정) → 커버리지 순으로 저장하고 커밋한다.
  - 실패 기록은 `mask_secrets`를 거친다. `collection.log` 사건은 `market_chunk`·`market_close_revised`·`market_chunk_failed`다.
  - 이어 받기도 `MARKET_CHUNK_DAYS`로 나눈다(R14-2 — 오래 꺼졌다 켜진 경우).
- [ ] T055 [US2] `backend/src/worker/market_worker.py` + `backend/src/api/main.py` (FR-019, R14-11)
  - `market_worker_loop`는 `MARKET_COLLECT_INTERVAL_SECONDS` 주기 + `asyncio.Event` 깨우기다. 한 지표의 실패가 루프를 끝내지 않는다.
  - `lifespan`의 아홉째 태스크로 둔다. 종료 때 취소한다.
- [ ] T056 [US2] `backend/src/api/services/indicator_series.py` — `MarketHistoryRepository`로 이력을 읽는다 (FR-012, FR-014, FR-016, FR-018, FR-019, SC-002, SC-004)
  - 환율은 `repository/fx_rate.series`·커버리지를 읽는다.
  - 단위 묶기·결측·잠정 꼬리(시세 서비스의 캐시)·한도 LTTB(`simulation/downsample.lttb`)·`tailPending`·202 판정을 한다.
  - 수집 상태 `history.lastSuccessAt`·`lastFailure`(contracts A2 — FR-019)를 커버리지 행에서 싣는다.
- [ ] T057 [US2] `backend/src/api/routes/dashboard_series.py` + `backend/src/api/main.py` — A2·A3·A4. SSE는 `api/collection_stream.SSE_HEADERS`·`format_sse`, 2초 폴링(`session.rollback()`). 200 응답에 수집 상태(`history.lastSuccessAt`·`lastFailure`)를 싣는다 (FR-010, FR-016, FR-019, contracts A2~A4)
- [ ] T058 [P] [US2] `frontend/src/lib/dashboardApi.ts`(`fetchSeries`·`requestCollect`) + `frontend/src/lib/dashboardProgressStream.ts`(`subscribeIndicatorProgress`) + `frontend/src/lib/types.ts`(그래프 타입 — contracts A2·A4) (FR-010, FR-016)
- [ ] T059 [US2] `frontend/src/stores/indicatorSeriesStore.ts` — data-model 7 (FR-010, FR-011, FR-016)
- [ ] T060 [US2] `frontend/src/components/dashboard/IndicatorHeader.tsx`·`UnitPicker.tsx`·`IndicatorChart.tsx`·`SeriesCollecting.tsx` — contracts D3·D4 (FR-010~FR-016, FR-018)
  - `IndicatorChart`는 새 부품이다. `FxChart`·`PerformanceChart`를 고치지 않는다.
- [ ] T061 [US2] `frontend/src/app/dashboard/[indicator]/page.tsx` — 서버 컴포넌트가 `params`·`searchParams`(Promise)를 풀어 클라이언트 부품(`components/dashboard/IndicatorView.tsx`)에 `id`·`unit`을 넘긴다. 틀린 단위는 `daily`다. `IndicatorView`는 마운트에 `marketQuotesStore.load()`·`startPolling()`, 언마운트에 `stopPolling()`을 부른다(머리 값도 보이는 동안 다시 받는다) (FR-008, FR-010, FR-011, R14-14)
- [ ] T062 [US2] 실측 확인 — quickstart 5-4~5-6을 확인하고 `quickstart.md` 8에 기록한다 (FR-010, FR-016, FR-017, FR-018, SC-004, SC-006)
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

- [ ] T063 [US3] 뉴스 픽스처를 옮긴다 — `backend/tests/contract/fixtures/news/` + `README.md` (FR-020, R14-13)
  - 작업용 임시 폴더 `scratchpad/014-news/`의 본문만 옮긴다(주소·머리 없이).
  - 옮길 것:
    - `naver_api_mainnews_p1_s20.json` — MBN 중복 두 건 포함, 15개로 줄인 사본
    - `yahoo_us_latest.html` — 목록 부분과 광고 칸을 남기고 나머지 마크업을 줄이되 선택자 구조는 그대로
    - `yahoo_us_latest_noua.html` — 429 본문
    - `yahoo_jp_headline.html` — `__PRELOADED_STATE__`가 든 줄을 남기고 줄인다
  - 구조가 바뀐 본문 셋을 만든다: 목록 칸 없는 HTML, `articles` 없는 JSON, 상태 키 없는 HTML.
  - README 표에 받은 날·요청 종류·담긴 상황을 적는다.

### Tests for User Story 3 ⚠️

- [ ] T064 [P] [US3] `backend/tests/contract/test_news_naver.py` — `ingestion/news/naver` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - 주요뉴스 15개 → 같은 제목은 한 번(MBN), 위에서부터 10개다.
  - 칸: 제목 원문·언론사, `datetime` KST → UTC, 링크 `https://n.news.naver.com/article/{officeId}/{articleId}`.
  - `n.news.naver.com` 밖 링크가 없다.
  - 요청 질의: `category=MAINNEWS`·`page=1`·`pageSize=15`. UA·`Accept-Language: ko-KR`이 붙는다.
  - `articles` 없는 본문 → `parse_empty`, 403 → `blocked`, 429 → `rate_limited`, 연결 오류 → `connection`이다.
- [ ] T065 [P] [US3] `backend/tests/contract/test_news_yahoo_us.py` — `ingestion/news/yahoo_us` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - 스트림 카드 10개, 광고 칸(`ad-container`) 제외다.
  - 칸: `a[title]` 제목·`href` 절대 주소·`span.publisher`·`span.published-date` 글자 그대로(`publishedText`), `publishedAt`은 `None`.
  - `finance.yahoo.com` 밖·`javascript:` 링크 줄은 버리고, 상대 주소는 절대 주소로 바꾼다(가공 본문).
  - 목록 칸 없는 HTML → `parse_empty`, 429 본문 → `rate_limited`다.
- [ ] T066 [P] [US3] `backend/tests/contract/test_news_yahoo_jp.py` — `ingestion/news/yahoo_jp` (FR-020, FR-021, FR-022, FR-024, SC-007, SC-008)
  - `__PRELOADED_STATE__` → `title.name == "ヘッドライン"` 목록의 위 10개다.
  - **시각**: `"22:20"` + `currentDateTime`의 JST 날짜 → `publishedAt`, `"10/8"` → `publishedDate`. 기준이 1월인데 `"12/30"`이면 지난해다.
  - `isPaidArticle` → `paid`다.
  - `finance.yahoo.co.jp` 밖 링크 줄은 버린다.
  - 상태 키 없는 HTML → `parse_empty`다.
- [ ] T067 [P] [US3] `backend/tests/unit/test_news_cache.py` — `api/services/news_cache` (FR-023, FR-024, R14-13)
  - 가짜 `NewsSource`와 가짜 시계를 쓴다.
  - **성공 캐시**: 600초 안 재요청은 출처 0회, 601초 뒤는 1회다.
  - **실패 기억**: 60초 → 연속 실패 120 → 240 → 480 → 600(상한)이고, 성공하면 처음으로 돌아간다. 남은 시간이 `retryAfterSeconds`다.
  - **단일 비행**: 동시 두 요청 = 출처 한 번이다.
  - **칸 사이**: 한 칸의 실패가 다른 칸에 영향이 없다.
- [ ] T068 [P] [US3] `backend/tests/integration/test_dashboard_news_api.py` — A5 (FR-020, FR-023, FR-024, SC-007, SC-008, contracts A5)
  - 칸 셋의 성공 본문 칸 이름이 contracts A5와 같다(`sourceName`·`sourceUrl`·`list`·`items`).
  - 한 칸 실패여도 200이고 `status: "failed"` + `failure`다. 다른 칸은 성공이다.
  - 틀린 `source`는 404다. 캐시 안 재요청은 출처 스텁 호출 0이다.
- [ ] T069 [P] [US3] `frontend/tests/newsStore.test.ts` — `stores/newsStore` (FR-024)
  - `loadAll`이 셋을 동시에 부르고 온 것부터 상태를 바꾼다.
  - `retry(source)`는 그 칸만 다시 부른다.
- [ ] T070 [P] [US3] `frontend/tests/NewsSection.test.tsx` — `components/dashboard/NewsSection`·`NewsColumn` (FR-020, FR-021, FR-022, FR-024, FR-025, SC-008, contracts D5)
  - **칸 머리**: 나라·출처 이름(출처 화면 링크 — 새 탭)·목록 이름·받은 시각이다.
  - **링크**: 줄마다 `target="_blank"`·`rel="noopener noreferrer"`다.
  - **시각**: `publishedAt` → 한국 `HH:mm`(오늘 아니면 `MM-DD HH:mm`), `publishedDate` → `MM-DD`, `publishedText`는 그대로다.
  - **유료**: `paid`면 "유료"를 단다.
  - **실패**: `parse_empty` → "읽지 못함 — 출처 화면이 바뀌었을 수 있음" + [다시 시도]다. 그 밖의 실패 → 까닭 + [다시 시도], `retryAfterSeconds`가 남았으면 "n초 뒤 다시 시도할 수 있습니다"다.
  - **적음**: 10개보다 적으면 있는 만큼이다.
- [ ] T071 [P] [US3] `frontend/tests/DashboardPageNews.test.tsx` — 대시보드에 뉴스 칸 (FR-024, SC-001, SC-007)
  - 뉴스 응답을 붙잡아 둔 채(풀지 않은 Promise) 카드 15개가 먼저 보인다.
  - 세 칸이 응답 차례대로 채워진다. 한 칸 실패에도 다른 칸·카드가 그대로다.

### Implementation for User Story 3

- [ ] T072 [US3] `backend/src/ingestion/news/types.py`(`NewsItem`·`NewsList` — data-model 6) + `errors.py`(실패 종류) + `client.py`(`NewsClient` — 공통 aiohttp 세션, `NEWS_USER_AGENT`, 칸마다 `Accept-Language`, 타임아웃·재시도) (FR-020, FR-024)
- [ ] T073 [P] [US3] `backend/src/ingestion/news/naver.py` — 요청 + 순수 파서(`json`) (FR-020, FR-021, FR-022, R14-13)
- [ ] T074 [P] [US3] `backend/src/ingestion/news/yahoo_us.py` — 요청 + 순수 파서(`html.parser.HTMLParser` 상속 — `data-testid` 기준, 해시 클래스 `yf-*` 금지) (FR-020, FR-021, FR-022, R14-13)
- [ ] T075 [P] [US3] `backend/src/ingestion/news/yahoo_jp.py` — 요청 + 순수 파서(`window.__PRELOADED_STATE__ =` 뒤를 `json.JSONDecoder().raw_decode`) (FR-020, FR-021, FR-022, R14-13)
- [ ] T076 [US3] `backend/src/api/services/news_cache.py` — Protocol `NewsSource`, 칸마다 캐시·실패 백오프·단일 비행, 응답 JSON(contracts A5) (FR-023, FR-024)
- [ ] T077 [US3] `backend/src/api/routes/dashboard_news.py` + `backend/src/api/main.py` — `lifespan`의 `NewsClient`, 라우터 등록 (FR-020, FR-024, contracts A5)
- [ ] T078 [US3] `frontend/src/lib/dashboardApi.ts`(`fetchNews`) + `frontend/src/lib/types.ts`(뉴스 타입) + `frontend/src/stores/newsStore.ts` — data-model 7 (FR-024)
- [ ] T079 [US3] `frontend/src/components/dashboard/NewsSection.tsx`·`NewsColumn.tsx` + `frontend/src/app/dashboard/page.tsx`(뉴스 칸·출처 줄) — contracts D1·D5 (FR-020~FR-022, FR-024, FR-025)
- [ ] T080 [US3] 파싱 시간을 잰다 — 픽스처 본문 셋을 파서로 100번 돌린 평균 (원칙 I, plan Constitution Check)
  - 한 번이 50ms를 넘는 파서는 `run_in_executor`로 옮기고 계약 테스트를 다시 돌린다.
  - 결과를 Notes에 적는다.
- [ ] T081 [US3] 실측 확인 — quickstart 5-7·5-8(임시 백엔드에서 `NEWS_US_URL`을 없는 주소로 덮어 한 칸 실패)을 확인하고 `quickstart.md` 8에 기록한다 (FR-020, FR-022, FR-024, SC-007, SC-008)
  - 10분 안 다시 열기에서 출처 호출이 없음을 서버 로그로 본다.

**Checkpoint**: 세 칸이 따로 보이고 따로 실패한다. 카드가 뉴스를 기다리지 않는다.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T082 성능을 잰다 (SC-001, SC-002, FR-012, quickstart 7)
  - 이력을 받아 둔 상태에서 `/dashboard` 탐색 시작부터 카드 15개가 그려질 때까지 잰다(2초 이내).
  - `/dashboard/sp500`의 일 단위 그래프가 그려질 때까지, 단위 전환까지 잰다(각 1초 이내).
  - 응답 크기·서버 시간·`setData` 시간을 적는다. 넘으면 멈추고 보고한다.
- [ ] T083 화면 폭 확인 — quickstart 5-9(1440px·1024px에서 카드 줄바꿈·뉴스 칸 쌓임·가로 넘침 없음). 결과를 `quickstart.md` 8에 적는다 (FR-003, FR-020)
- [ ] T084 불변 대조 (FR-026, SC-010, quickstart 6)
  - 서버를 띄우고 T001의 입력으로 다시 받아 `014-baseline/after/`와 견준다. 부동산은 KST 날짜 차이만 허용한다.
  - 외환 `/latest`·`/series`가 같다(그날 새 고시가 생겼으면 그 날짜 차이만).
  - 다른 키·값이 있으면 멈추고 보고한다.
- [ ] T085 문서를 갱신한다 (FR-025, FR-026)
  - `CLAUDE.md`:
    - "현재 상태" 표에 014 한 줄을 더한다.
    - 원칙 II 이탈 목록에 014 넷(Yahoo 확장·네이버 내부 API·Yahoo US HTML·Yahoo JP 내장 JSON)을 더한다.
    - 주의 문단: 대시보드 수집 워커(아홉째 태스크)·Yahoo 관문을 주식과 함께 씀, 대시보드는 ECOS를 부르지 않음, 시장 환율은 저장하지 않음, `zoneinfo` 날짜, 가드 글자(`backfill`·"전일 값"), 개발 DB `alembic upgrade head`.
  - `README.md`: 기능 설명과 출처 표기(Yahoo Finance·한국은행 ECOS·네이버 증권·Yahoo Finance·Yahoo!ファイナンス).
  - `spec.md` Status를 갱신한다.
- [ ] T086 품질 게이트를 돌린다(서버를 내린 채) (헌법 품질 게이트, SC-010)
  - 백엔드 `pytest -q --cov=src`(커버리지 80% 이상)·`mypy src`·`ruff check --no-cache src tests`, 프론트엔드 `npm test`·`npx tsc --noEmit`·`npx eslint .`를 돌린다.
  - 통과 수와 종료 코드를 Notes에 적는다.
  - 이 기능 전 커밋(`90e848b`)과 견주어 바뀌거나 지워진 기존 테스트 파일이 승인 목록(T018)뿐인지 `git diff --stat --diff-filter=MD 90e848b -- backend/tests frontend/tests`로 확인한다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작한다. **T001·T002는 다른 모든 코드 변경보다 먼저다.**
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
| `backend/src/api/main.py` | T017(Foundational), T035(US1), T055·T057(US2), T077(US3) |
| `backend/src/ingestion/yahoo/market.py`·`market_parse.py` | T033(US1), T051(US2) |
| `backend/src/ingestion/yahoo/client.py` | T014 |
| `backend/src/config/settings.py`·`.env.example` | T011 |
| `frontend/src/lib/types.ts`·`lib/dashboardApi.ts` | T036(US1), T058(US2), T078(US3) |
| `frontend/src/app/dashboard/page.tsx` | T040(US1), T079(US3) |
| `frontend/src/components/shell/Sidebar.tsx`·`TopBar.tsx`·`app/page.tsx` | T040 |
| `frontend/tests/Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`·(`TopBarTitle.test.ts`) | T018(승인 뒤에만) |
| `specs/014-…/quickstart.md`(실행 기록) | T041, T062, T081, T082, T083, T084 |

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
  - T018 승인: (구현 중 채움)
  - T080 파싱 시간: (구현 중 채움)
  - T086 게이트: (구현 중 채움)

---

## 요구사항 ↔ 태스크

모든 FR·SC가 하나 이상의 태스크에 참조된다(헌법 명세 작성 규약).

| 요구사항 | 태스크 |
|----------|--------|
| FR-001 | T018, T028, T029, T040, T041 |
| FR-002 | T024, T025, T037, T039 |
| FR-003 | T006, T012, T013, T023, T028, T035, T036, T083 |
| FR-004 | T020, T023, T026, T030, T032, T036, T039 |
| FR-005 | T010, T016, T020, T023, T026, T032, T034, T039, T041 |
| FR-006 | T007, T011, T019, T026, T031, T039, T041 |
| FR-007 | T019, T020, T026, T031, T032, T039 |
| FR-008 | T007, T011, T022, T025, T027, T028, T034, T038, T039, T061 |
| FR-009 | T005, T021, T022, T023, T026, T027, T028, T033, T034, T035, T038, T039 |
| FR-010 | T047, T048, T050, T057, T058, T059, T060, T061, T062 |
| FR-011 | T044, T048, T049, T050, T053, T059, T060, T061 |
| FR-012 | T044, T047, T049, T053, T056, T060, T082 |
| FR-013 | T044, T049, T053, T060 |
| FR-014 | T043, T047, T049, T052, T056, T060 |
| FR-015 | T006, T012, T026, T039, T050, T060 |
| FR-016 | T046, T047, T048, T050, T056, T057, T058, T059, T060, T062 |
| FR-017 | T005, T009, T010, T015, T016, T042, T045, T046, T051, T054, T062 |
| FR-018 | T006, T012, T013, T021, T023, T026, T033, T039, T047, T050, T056, T060, T062 |
| FR-019 | T007, T008, T010, T011, T014, T015, T016, T017, T042, T045, T046, T047, T050, T051, T054, T055, T056, T057 |
| FR-020 | T063, T064, T065, T066, T068, T070, T072, T073, T074, T075, T077, T079, T081, T083 |
| FR-021 | T064, T065, T066, T070, T073, T074, T075, T079 |
| FR-022 | T064, T065, T066, T070, T073, T074, T075, T079, T081 |
| FR-023 | T007, T011, T067, T068, T076 |
| FR-024 | T064, T065, T066, T067, T068, T069, T070, T071, T072, T076, T077, T078, T079, T081 |
| FR-025 | T070, T079, T085 |
| FR-026 | T001, T002, T008, T014, T017, T084, T085, T086 |
| SC-001 | T071, T082 |
| SC-002 | T047, T056, T082 |
| SC-003 | T010, T020, T023, T032, T041 |
| SC-004 | T047, T056, T062 |
| SC-005 | T043, T044, T052, T053 |
| SC-006 | T009, T010, T015, T016, T046, T054, T062 |
| SC-007 | T022, T034, T064, T065, T066, T068, T071, T081 |
| SC-008 | T064, T065, T066, T068, T070, T081 |
| SC-009 | T019, T026, T031 |
| SC-010 | T001, T002, T084, T086 |
