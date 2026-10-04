---

description: "Task list for 007-crypto-investment-simulation"
---

# Tasks: 가상자산 투자 시뮬레이션

**Input**: Design documents from `/specs/007-crypto-investment-simulation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를 지킨다. **테스트를 구현보다
먼저 커밋한다** — 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes). **구현 뒤 테스트가 실패하면 원인이 테스트 쪽으로 보여도 멈추고
실패 목록과 원인 판단을 먼저 보고한다**(이전에 통과하던 테스트가 실패로 바뀐 경우도 같다 — 006 D2).

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US5)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수)

## 이 기능에서 특히 조심할 것

- **화면용 문자열을 읽으면 값이 조용히 틀린다**: 일봉의 `last_open` 등은 코인 자릿수로 반올림된다(2010 BTC 시가 `"0.0"`). **원값(`…Raw`)
  문자열을 `float` 없이 `Decimal`로** 읽는다 (research R7-3)
- **오늘 일봉이 마감 전에도 온다**: 정규화에서 UTC 어제보다 뒤의 행을 버린다. 버리지 않으면 같은 입력의 결과가 하루 동안 바뀐다 (FR-022)
- **한 요청에 약 5,000행에서 표시 없이 잘린다**: 청크 730일. 상한 근처 행 수는 형식 오류로 다룬다 — 잘린 구간을 받은 것으로 기록하지 않는다
- **심볼은 식별자가 아니다**: 169개가 겹친다. 어떤 조회도 심볼을 키로 쓰지 않는다 — `(source, source_id)`만 (FR-004)
- **403은 차단이다**: 재시도로 풀리지 않는다. 기본 사용자 에이전트는 403 — 사용자 에이전트는 설정이다 (research R7-1)
- **성공 픽스처만 있으면 방어선이 테스트되지 않는다**: 차단(403 본문 `403`), 일봉 없음(Doge Killer), 빈 거래량(BTC 2011-06), 오늘 일봉,
  아주 작은 가격(SHIB), 한국어 판 일부 실패를 각각 픽스처로 둔다. **픽스처는 실제 응답을 저장한 것**이다(T001)
- **실행 주체에는 그 주체를 거쳐야만 통과하는 테스트를 짝짓는다**(006 D1): 워커의 `lifespan` 등록, 검색이 목록 갱신을 요청하는 경로,
  시뮬레이션 요청이 수집을 시작하는 경로. 내부 함수를 직접 부르는 테스트는 주체가 빠져도 통과한다
- **주식 경로를 건드린다**(plan Complexity Tracking): `evaluate_krw`, `fx_currency_for(currency)`, `compute_gaps`의 사유, `SearchEntry.priority`,
  **`load_rates` 확정 환율 전용**(analyze C1). **006의 기존 테스트는 고치지 않고 통과해야 한다** — 고쳐야 한다면 멈추고 보고한다
- **읽지 못한 가격 행을 버리면 결측으로 위장된다**: 그 청크 전체를 형식 오류로 실패시킨다(FR-012a, analyze M2)
- **테스트는 네트워크 없이**(헌법 원칙 III, 소켓 차단 `conftest.py`). 출처를 부르는 것은 T001의 픽스처 저장 스크립트뿐이다

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 실제 응답 픽스처와 설정 자리

- [X] T001 출처의 **실제 응답**을 받아 `backend/tests/contract/fixtures/crypto/`에 저장한다 — aiohttp, 브라우저형 사용자 에이전트, 요청 사이
  1.5초(research R7-1). 받는 것: 목록 영문 첫 쪽(`coins_en_p1.json`)·마지막 쪽(`coins_en_last.json`, `next_page_cursor: null`), 목록 한국어
  첫 쪽(`coins_ko_p1.json`), BTC 2020-01-01~2021-12-31 청크(`btc_2020_2021.json`), BTC 최근 청크(오늘 일봉 포함, `btc_recent.json`), BTC
  2011-06-01~2011-07-31(빈 거래량, `btc_2011_06.json`), ETH 2015-06-01~2017-05-31(첫 일봉 2016-03-10을 걸침, `eth_first.json`), SHIB 최근
  (`shib_recent.json`), Doge Killer 최근(일봉 0행, `leash_empty.json`), 기본 사용자 에이전트의 403 본문(`blocked_403.txt`). 그리고 **전체
  목록에서 필요한 필드만 뽑은 `coins_all_compact.json`**(영문·한국어 각 37쪽에서 식별자·영문 이름·한글 이름·심볼·순위·slug, 약 300KB —
  실데이터에서 뽑은 파생 픽스처, analyze M1). 받은 날짜와 요청을 `fixtures/crypto/README.md`에 적는다. 스크립트는 저장소에 넣지 않는다
  (일회성) (FR-012, FR-018, SC-002, research R7-3·R7-4)
- [X] T002 [P] `.env.example`에 출처 설정 자리를 더한다 — `INVESTING_USER_AGENT`, `INVESTING_DOMAIN_ID`(`www`), `INVESTING_MIN_INTERVAL_SECONDS`
  (1.5), `INVESTING_MAX_RETRIES`, `INVESTING_BACKOFF_BASE_SECONDS`, `INVESTING_CHUNK_DAYS`(730), `CRYPTO_LIST_REFRESH_DAYS`(7),
  `CRYPTO_LIST_SHRINK_THRESHOLD`(0.5). 값의 의미를 주석으로. 비밀은 없다 (FR-016, FR-017)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 스키마, 출처 어댑터, 주식과 공유하는 규칙. 모든 스토리가 기댄다

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 어떤 스토리도 시작하지 않는다

### Tests for Phase 2 ⚠️

- [X] T003 [P] `backend/tests/contract/test_investing_parse.py` — T001 픽스처로: 목록 → 코인 행(`instrument_id`를 문자열 식별자로, 심볼·영문
  이름·순위·slug, `url` 빈 값 허용), 한국어 판의 이름이 **영문과 다르고 한글을 포함할 때만** 한글 이름(비트코인 ○, BNB ×), 마지막 쪽 커서 없음.
  일봉 → 날짜는 `rowDateTimestamp`의 UTC 날짜, 가격은 원값 문자열 그대로 `Decimal`(2010 BTC 시가 `0.04950999841094`, SHIB `0.00000579000016`),
  `volume`이 빈 값이면 거래량 `None`(0 아님), 계산 끝(주입한 UTC 오늘 − 1)보다 뒤의 행은 버림, **가격이 빠지거나 숫자가 아닌 행이 하나라도
  있으면 청크 전체가 형식 오류**(오류에 날짜·필드를 담고 일부 행만 돌려주지 않음, analyze M2), 4,900행 이상이면 형식 오류, 0행(Doge Killer)은
  빈 결과 (FR-006, FR-012, FR-012a, FR-021, FR-022, research R7-3·R7-4)
- [X] T004 [P] `backend/tests/contract/test_investing_client.py` — 가짜 세션으로: 목록 요청이 `limit=100`·`domain_id`·커서를 싣고 끝까지 넘기는지,
  일봉 요청이 `domain-id` 헤더와 날짜 매개변수를 싣는지, 모든 요청에 설정의 사용자 에이전트, 요청 사이 최소 간격(주입한 시계), **403은 재시도 없이
  차단 오류**, 429·5xx·연결 오류는 백오프+지터로 설정 횟수만큼 재시도, 받은 원본 본문을 함께 돌려주는지, 넘겨받은 세션을 닫지 않는지
  (FR-016, FR-018, FR-020, research R7-1)
- [X] T005 [P] `backend/tests/unit/test_evaluate_krw.py` — `evaluate_krw(잔고, 예수금, 매매기준율, KRW 원금)` → 잔고 KRW·투자 수익·수익율
  (006 FR-068 식, 통화 자릿수 KRW 0). `backend/tests/unit/test_stock_fx_currency.py` — `fx_currency_for("KRW")` → `None`, `"USD"` → `"USD"`,
  모르는 통화 → `None`. `backend/tests/integration/test_load_rates_confirmed.py` — `load_rates`가 **잠정 행을 빼고** 읽어, 잠정 환율만 있는 날은
  `resolve_rate`가 앞 확정일의 값과 그 날짜를 돌려주는지(analyze C1). **006의 시뮬레이션·환율 테스트는 그대로 통과해야 한다** (FR-035,
  research R7-8)
- [X] T006 [P] `backend/tests/unit/test_compute_gaps_reason.py` — 커버리지 안 빈 날의 사유를 `source_missing`으로 줄 수 있고, 기본은 `no_quote`
  그대로(외환·주식 불변). `backend/tests/unit/test_search_priority.py` — 같은 일치 종류 안에서 `priority`가 작은 항목이 먼저, `priority`가 같으면
  006의 순서(이름 길이 → 가나다·알파벳 → 시장 → 코드), 주식 항목(기본 0)의 순서 불변 (FR-023, FR-004, research R7-6·R7-9)
- [X] T007 [P] `backend/tests/integration/test_crypto_schema.py` — 마이그레이션 뒤 테이블 11개와 열(data-model): 가격 `DECIMAL(36,14)`, 거래량
  `DECIMAL(38,8)` NULL 허용, `crypto_coin`의 `(source, source_id)` 유일, `crypto_daily`의 `(coin_id, day)` 기본 키, `crypto_setting` 기본값 없음(행 없음
  = 기본), 마이그레이션 하향·재상향 (FR-010, FR-031, data-model)

### Implementation for Phase 2

- [X] T008 `backend/src/config/settings.py` — `InvestingSettings`(T002의 값, 사용자 에이전트가 비면 기본 `aiohttp` 값 — 그러면 403으로 막힌다는 것을
  quickstart 17이 보인다), `load_settings`에 연결 (FR-016, FR-017)
- [X] T009 `backend/src/db/models.py`·`backend/src/db/migrations/versions/…_가상자산_스키마.py` — Crypto* 11개(data-model 1~9절). 형식 이름
  `CPRICE`·`CVOLUME` (FR-010, FR-012, FR-031, FR-032)
- [X] T010 `backend/src/ingestion/investing/parse.py`·`errors.py`·`__init__.py` — `CoinRow`, `DailyBar`, `parse_coin_page`, `korean_names`,
  `parse_daily(body, last_day)`, 오류 `InvestingBlocked`·`InvestingFormatError`·`InvestingNetworkError` (FR-006, FR-012a, FR-020~FR-022)
- [X] T011 `backend/src/ingestion/investing/client.py` — `InvestingClient(settings, *, session=None, monotonic=…, sleep=…)`: `fetch_coin_pages(edition)`,
  `fetch_daily(source_id, start, end, *, last_day)` → (행, 원본). 세마포어 1 + 최소 간격 제한기(인스턴스 하나를 두 줄이 공유), 백오프+지터, 403 분류
  (FR-016, FR-018, FR-020, research R7-1·R7-11)
- [X] T012 주식과 공유하는 규칙 — `backend/src/simulation/fx_convert.py`(`evaluate_krw`), `backend/src/api/services/stock_simulation.py`(`_evaluate`가
  `evaluate_krw`를 부른다), `backend/src/api/services/stock_fx.py`(`fx_currency_for(currency)`와 호출처 `stock_collect.py`·`stock_simulation.py`,
  **`load_rates`는 `series(…, confirmed_only=True)`** — analyze C1), `backend/src/api/services/series_query.py`(`compute_gaps(…,
  inside_reason="no_quote")`), `backend/src/search/match.py`(`SearchEntry.priority` 기본 0). **주식의 출력은 날짜가 지난 잠정 환율이 있는 날 말고는
  바뀌지 않는다** — 006 테스트 전체로 확인 (FR-004, FR-023, FR-035, plan Complexity Tracking)

**Checkpoint**: 스키마·어댑터·공유 규칙 준비. 백엔드 전체 테스트(006 포함)가 통과한다

---

## Phase 3: User Story 2 - 코인을 이름·심볼로 찾아 고른다 (Priority: P1)

**Goal**: 출처의 코인 목록(영문·한국어 판)을 일주일에 한 번 받아 두고, 한글·초성·영문·심볼로 찾아 고른다

**Independent Test**: 목록을 받은 상태에서 "btc", "Bitcoin", "비트코인", "ㅇㄷㄹㅇ", "max"를 쳐 기대한 코인이 맨 위에 나오고 같은 심볼이 구별되는지

**순서 메모**: US1과 같은 P1이지만 먼저 한다 — US1의 화면이 코인을 고르려면 검색이 있어야 한다. 둘을 합친 것이 MVP다

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] `backend/tests/unit/test_crypto_list_due.py` — 갱신 판정 순수 함수: 받은 적 없음 → 갱신, 마지막 성공 뒤 7일 미만 → 안 함,
  7일 이상(한국 시간 날짜) → 갱신, 오늘 이미 시도했으면(실패 포함) → 안 함 — 다음 날 다시, 한국 시간 자정 경계 (FR-005)
- [X] T014 [P] [US2] `backend/tests/integration/test_crypto_list_refresh.py` — 가짜 출처(T001 픽스처)로 `refresh_coins`: 영문·한국어 판을 다 받은 뒤
  한 트랜잭션 교체, 한글 이름은 **식별자로만** 짝지음, 이번 목록에 없는 코인은 `missing`(지우지 않음)·다시 보이면 `listed`, 이전보다 50% 넘게
  줄면 거절(`shrunk`)하고 아무것도 바꾸지 않음, 영문 판 실패 → 아무것도 안 바뀜, **한국어 판만 실패 → 영문으로 교체하고 한글 이름은 이전 값**,
  같은 본문은 원본 한 번만, 갱신 기록(`as_of`·`row_count`·`attempts`·`last_error_kind`), 점유 중이면 두 번째 갱신은 시작하지 않음, 수집 전용
  로그에 시작·완료·실패 사건 — 사용자 에이전트·헤더 값 없음 (FR-004, FR-005, FR-005a, FR-006, FR-019, SC-011)
- [X] T015 [P] [US2] `backend/tests/integration/test_crypto_search_api.py` — `GET /api/crypto/search`: "btc"·"Bitcoin"·"비트코인"·"ㅂㅌㅋㅇ" → 맨 위
  비트코인, "max" → MAX 5개가 순위순으로 구별(`coinId`가 다름), `nameKo`는 한글 이름이 있을 때만, `listStatus: missing` 표시, `list.state`
  (`never`·`refreshing`·`failed`+`reason`·`ready`)와 `list.koreanNames`, `q` 없음 → 400. **실행 주체**: 갱신 주기가 된 첫 검색이 **기다리지 않고**
  응답하며, `lifespan`이 띄운 목록 갱신 줄이 그 요청을 받아 갱신을 끝낸다(앱 수명을 거치는 테스트, 가짜 출처). **진행 스트림**
  `GET /api/crypto/list/progress`: 갱신 중 `snapshot`(판·받은 쪽 수·`pagesExpected`(처음이면 `null`)·받은 코인 수)이 쪽마다 늘고 판이 바뀌면
  0부터, `completed`·`failed`(사유), 갱신 중이 아니면 마지막 상태 한 번, 머리글 `no-transform`(FR-005b, analyze C2). **상위 50개 측정**:
  `coins_all_compact.json`으로 만든 색인에서 상위 50개 각각을 영문 이름과 심볼로 검색해 맨 위 비율 ≥ 95%, 한글 이름이 있는 코인은 한글·초성으로도
  ≥ 95% — 비율을 실패 메시지에 싣는다(analyze M1) (FR-003~FR-006, FR-005b, SC-002, SC-002a)
- [X] T016 [P] [US2] `frontend/tests/CoinSearch.test.tsx` — 결과 한 줄(한글 이름·영문 이름·심볼·`USD`·`#순위`, 한글이 없으면 영문이 맨 앞, "목록에서
  빠짐" 글자), 엔터 = 맨 위, 방향키 선택, **한글 조합 중 엔터·방향키 무시**(006 버그 `search-enter-ime`과 같은 테스트), 목록 상태 줄(처음 받는 중,
  갱신 실패 사유와 이전 기준 시각), 결과 없음과 목록 없음 구별, **목록 상태가 `never`·`refreshing`이면 진행 스트림을 구독해 "영문 12쪽 받음"·
  "한국어 8/37쪽"처럼 보이고 `completed`에 검색을 다시 보냄, 화면을 떠나면 구독을 끊음**(analyze C2) (FR-003, FR-005, FR-005b, FR-006)

### Implementation for User Story 2

- [X] T017 [US2] `backend/src/repository/crypto_coin.py`·`crypto_list_lock.py` — 코인 upsert·`missing` 표시, 갱신 기록 읽기·쓰기, 점유(기본 키 충돌 — 지울 수 있는 것이 점유뿐이라 따로 둔다, 006과 같다), 원본 쪽·본문(해시),
  검색 색인용 전 코인 읽기 (FR-005, FR-005a, data-model 1~4절)
- [X] T018 [US2] `backend/src/api/services/crypto_list_refresh.py`·`backend/src/worker/crypto_list_queue.py`·`backend/src/worker/crypto_list_worker.py`·
  `backend/src/api/routes/crypto_list_progress.py`·`backend/src/api/main.py`(`lifespan` 등록·라우터) — 주기 판정, 요청(기다리지 않음), 두 판
  받기·축소 검사·교체, 쪽마다 점유 행에 진행 기록, 진행 스트림, 사건 기록 (FR-005, FR-005b, FR-006, FR-019)
- [X] T019 [US2] `backend/src/api/services/crypto_index.py`·`backend/src/api/routes/crypto_search.py`·`backend/src/api/main.py`(라우터) — 메모리 색인(갱신
  기록 버전), `SearchEntry(names=(한글, 영문), codes=(심볼,), priority=순위)`, 응답(rest-api 검색) (FR-003, FR-004, FR-006)
- [X] T020 [US2] `frontend/src/lib/types.ts`(검색 응답·목록 진행 사건)·`frontend/src/lib/cryptoListProgressStream.ts`·
  `frontend/src/components/crypto/CoinSearch.tsx` — C2, 목록 갱신 진행 구독 (FR-003~FR-006, FR-005b)

**Checkpoint**: 검색으로 코인을 고를 수 있다(목록 갱신 포함)

---

## Phase 4: User Story 1 - 코인 하나에 투자했다면 지금 얼마인지 본다 (Priority: P1) 🎯 MVP

**Goal**: 고른 코인을 달러 원금으로 실행해 수집 → 계산 → 보드·표를 본다. 수수료 설정 포함

**Independent Test**: 비트코인·달러 10,000·2020-01-15를 처음 실행해 수집 진행이 보이고, 끝나면 소수 수량·0.1% 수수료 행·KRW 기준 수익률이 나오는지

### Tests for User Story 1 ⚠️

- [X] T021 [P] [US1] `backend/tests/unit/test_crypto_hold.py` — 순수 함수: 시작 월 1일 일봉 시가로 매수(시작일이 15일이어도), 1일이 결측이면 그 달의
  첫 일봉으로 사고 행에 결측 표시, 월 행은 매달 첫 일봉·최신순, `latest` = 마지막 일봉, **손계산 참조값**(research R7-7: 7,196.39111328125·10,000·
  0.1% → 수량 1.38819719, 수수료 9.9900099215980029296875, 예수금 0.0000684803990673828125 — 계산 과정을 주석으로), 수수료 포함 총액 ≤ 원금·예수금 ≥
  0, 원금이 최소 단위 값보다 작으면 수량 0·전액 예수금, **1개 값이 원금보다 커도 소수로 산다**(원금 100달러·시가 84,513달러·0.1% → ⌊100 ÷ 84,597.513⌋₈
  = 0.00118206 — 계산 과정을 주석으로, analyze L3), 아주 작은 가격(1e-12)도 0으로 잘리지 않음, 같은 입력 같은 결과, 잔고 = 수량 × 그 행의 시가(예수금
  제외) (FR-025~FR-031, SC-004, SC-006)
- [X] T022 [P] [US1] `backend/tests/unit/test_buy_fraction.py` — `buy_fraction(예수금, 시가, 수수료율)`: 소수 8자리 버림, 총액 ≤ 예수금, 시가·예수금
  0 이하 → 0, 정수 수량 함수 `buy_quantity`는 그대로 (FR-026)
- [X] T023 [P] [US1] `backend/tests/integration/test_crypto_collection.py` — 가짜 출처로 `crypto_runner`: 시작 월 1일 ~ 계산 끝을 730일 청크로, 청크마다
  원본 저장(요청 구간 포함), upsert 멱등(두 번 받아도 같은 행), 오늘·미래 행은 저장 안 함, 커버리지 = 요청한 구간, 앞부분이 빈 코인(ETH 픽스처)은
  `first_available_date` = 첫 일봉, 일봉 0행 코인은 `first_available_date` 없음, 실패 종류(`blocked`·`format`·`network`·`empty`)를 작업
  `last_error`에, **가격을 읽지 못한 행이 든 청크는 저장 0행·커버리지 그대로·`format`·사유에 날짜와 필드**(analyze M2), 중단 뒤 재실행은 빠진
  구간만, 같은 코인 점유 중이면 새 작업 없음, 수집 전용 로그 사건 (FR-008, FR-010~FR-014, FR-012a, FR-019, FR-020, FR-022, SC-005)
- [X] T024 [P] [US1] `backend/tests/integration/test_crypto_simulation_api.py` — `GET /api/crypto/simulation`(달러 원금, USD 환율 픽스처 있음):
  받지 않은 구간 → 202(`jobId`·`progressUrl`, 결과 없음), USD 환율이 비면 202 `fx`, 다 있으면 200 — 행의 수량 8자리 문자열·`tradeFee`는 매수 행에만·
  `firstDayMissing`·열별 통화(시가·수수료·예수금·잔고 USD, `balanceKrw`, `profit`·`returnRate` KRW 기준)·`summary.principalKrw`·`boughtOn`·
  `condition.tradeFeeRate`, 일봉이 계산 끝 전에 끊기면 `isFinal: false`·`asOf` = 마지막 일봉, `before_listing`(수집 전: 기록된 첫 일봉, 수집 후: 시작
  월에 일봉 없음), `start_after_end`, `unknown_coin`+`reselect`, `no_price_data`(Doge Killer), `currency_pair_not_allowed`(EUR·JPY), 원금 0·문자 →
  400. **실행 주체**: 202를 받은 요청이 `lifespan`의 가상자산 수집 줄로 이어져 작업이 끝나고, 다시 요청하면 200 (FR-002, FR-007~FR-009, FR-013,
  FR-022, FR-024~FR-028, FR-035, FR-036, FR-037a, SC-003, SC-006, SC-007)
- [X] T025 [P] [US1] `backend/tests/integration/test_crypto_progress_sse.py` — `GET /api/crypto/progress`: `snapshot`(받은 날 / 받을 날), `completed`,
  `failed`(`kind`), 머리글 `no-transform`·`X-Accel-Buffering`, 프레임마다 새 스냅샷(006 R6-19) (FR-013, FR-020, SC-003)
- [X] T026 [P] [US1] `backend/tests/integration/test_crypto_settings_api.py` — `GET`: 기본 `0.001000`·`isDefault: true`, 문자열. `PUT`: 저장·`isDefault`
  바뀜, 범위 밖(−0.1, 1, 1.5)·숫자 아님·빠짐 → 422 `invalid_setting`, **주식 설정과 따로**(주식 수수료 그대로). 바꾼 수수료가 다음 시뮬레이션에
  쓰이고 `condition.tradeFeeRate`에 보인다 (FR-032, FR-033, SC-008)
- [X] T027 [P] [US1] `backend/tests/integration/test_crypto_worker.py` — **실행 주체**: 앱 기동이 가상자산 수집 줄과 목록 갱신 줄을 띄운다(태스크 6개),
  기동 시 오래된 가상자산 점유를 회수, 주식 수집이 진행 중이어도 가상자산 수집이 기다리지 않고(반대도) 함께 끝난다 (FR-014, FR-015, SC-012)
- [X] T028 [P] [US1] `frontend/tests/` — `CryptoPage.test.tsx`(`/crypto` 화면, 재투자 칸 없음, 일봉 기준 UTC 안내, 시작일 상한 = UTC 어제),
  `CryptoPerformanceTable.test.tsx`(열 구성·배당 열 없음, 머리글 통화 아래 줄, 수량 8자리, 매수 행에만 수수료, `◇`와 글자 설명, 잔고 `USD (KRW)`, 표
  `w-max`), `formatPrice.test.ts`(1 이상 소수 2자리, 1 미만 유효 숫자 4자리 이상, `0.00000579`, `0`·`0.00`이 되지 않음), `cryptoStore.test.ts`(202 →
  진행 구독 → 완료 뒤 다시 요청, 실패 사유 종류별 문구), `CryptoSettingsForm.test.tsx`(0.1 % 표시·저장·범위 밖 거절·기본값으로),
  `Sidebar` 순서·경로(`/crypto`) — **기존 `frontend/tests/Sidebar.test.tsx`의 기대를 바꾼다**: 메뉴 순서(외환 → 가상자산 → 주식, 18행), 준비중
  목록에서 가상자산 제거(34행), 가상자산 항목이 링크(48행). 테스트 커밋에서 바꾸고 사유를 적는다(analyze M3). `noUnbuiltAssetRoutes.test.ts`에서
  `crypto`를 뺀다(사이드바 경로 목록에 `/crypto`, 라우트 디렉토리 — API 호출 검사 부분은 T020이 `/api/crypto`를 불러 Phase 3에서
  앞당겼다) (FR-001, FR-009, FR-013, FR-020~FR-022, FR-032, FR-033, FR-037~FR-042, SC-009)

### Implementation for User Story 1

- [X] T029 [US1] `backend/src/simulation/money.py`(`buy_fraction`)·`backend/src/simulation/crypto_hold.py` (FR-025~FR-031)
- [X] T030 [US1] `backend/src/repository/crypto_daily.py`·`crypto_job.py`·`crypto_setting.py` — 일봉 upsert·조회, 커버리지, 첫 일봉 기록, 작업·점유,
  수수료율(기본 0.001) (FR-010, FR-011, FR-014, FR-032)
- [X] T031 [US1] `backend/src/worker/crypto_queue.py`·`crypto_runner.py`·`crypto_worker.py`·`backend/src/api/main.py`(`lifespan`, 기동 시 회수) —
  청크 수집, 원본 저장, 첫 일봉 기록, 실패 종류, 사건 기록 (FR-010~FR-015, FR-019, FR-020)
- [X] T032 [US1] `backend/src/api/services/crypto_collect.py`·`crypto_simulation.py`·`backend/src/api/routes/crypto_simulation.py`·`crypto_progress.py`·
  `crypto_settings.py`·`backend/src/api/main.py`(라우터) — 202 판정(일봉 + 환율), 시작 가능 날짜, 계산 끝 UTC 어제, KRW 평가(`evaluate_krw`), 응답
  (FR-002, FR-007~FR-009, FR-013, FR-022, FR-024, FR-033, FR-035, FR-036)
- [X] T033 [US1] `frontend/src/lib/types.ts`·`format.ts`(`formatPrice`·`formatQuantity`)·`cryptoProgressStream.ts`·`frontend/src/stores/cryptoStore.ts`·
  `frontend/src/components/crypto/CryptoSimulationForm.tsx`·`CryptoPerformanceTable.tsx`·`frontend/src/app/crypto/page.tsx`·
  `frontend/src/components/settings/CryptoSettingsForm.tsx`·`frontend/src/app/settings/page.tsx`·`frontend/src/components/shell/Sidebar.tsx` —
  보드는 `PerformanceBoard` 그대로, 수집 안내는 `CollectingNotice`(대상 이름을 받게) (FR-001, FR-009, FR-013, FR-032, FR-037~FR-042)
- [X] T034 [US1] 실제 브라우저(3030, 1440px)로 확인한다 — quickstart 1·2·3·6·7·8·10·12·13·14·16·17·18·20. 실제 출처로 받는다. 결과를 quickstart 실행
  기록에 적는다 (SC-001, SC-003, SC-010, SC-011, SC-012)

**Checkpoint**: MVP — 검색 → 실행 → 수집 진행 → 보드·표. 달러 원금, 수수료 설정

---

## Phase 5: User Story 3 - 원화 원금으로 본다 (Priority: P2)

**Goal**: 원화 원금이면 첫 매수일에 환전하고, 행마다 그 행의 환율로 KRW 평가한다(달러 원금의 KRW 평가는 US1에 있다)

**Independent Test**: 원화 1,000만 원으로 실행해 환전 환율과 날짜, 행마다 환율, 잔고 `USD (KRW)`, 투자 수익 KRW가 나오는지

### Tests for User Story 3 ⚠️

- [X] T035 [P] [US3] `backend/tests/integration/test_crypto_simulation_krw.py` — 원화 원금: 환전 = 첫 매수일 현금 살 때 환율 + 스프레드 90% 우대, 그날
  고시가 없으면 이전 고시일과 그 날짜(`exchange.rateDate`), 환전한 달러로 매수, 행마다 `fxRate`·`fxRateDate`, `profit` = (잔고 + 예수금) × 그 행의
  환율 − 원금, `principalKrw` 없음, **행 날짜의 환율이 잠정이면 앞 확정일의 환율과 그 날짜(`fxRateDate`)**(analyze C1). 환율 구간을 채울 수 없으면
  409 `fx_not_available_before`, 수집했는데 값이 없으면 409 `fx_unavailable`, 환율이 비면 202 `fx`(외환 화면과 같은 수집 표) (FR-034~FR-036, SC-007)
- [X] T036 [P] [US3] `frontend/tests/CryptoBoardKrw.test.tsx`·`cryptoStoreFx.test.ts` — 원화 원금이면 보드에 환전 줄, 달러 원금이면 `10,000$ (…₩)`(반복 2026-10-04에 `$10,000 (₩…)` — T049), 환율
  수집 대기(202 `fx`) 뒤 외환 수집 스트림 완료 시 다시 요청(006 stockStore의 환율 대기와 같다) (FR-034~FR-036, FR-042)

### Implementation for User Story 3

- [X] T037 [US3] (Phase 4의 T032·T033이 함께 연결해 코드 변경 없음 — T035·T036이 구현 변경 없이 통과) `backend/src/api/services/crypto_simulation.py`(환전 경로 — `build_exchange`·`cash_buy_spread`·`load_rates`를 그대로)·
  `frontend/src/stores/cryptoStore.ts`(환율 대기) — 006과 같은 규칙 (FR-034~FR-036)
- [X] T038 [US3] 실제 브라우저로 quickstart 9를 확인하고 기록한다 (SC-007)

**Checkpoint**: 원화·달러 원금 모두 KRW 기준

---

## Phase 6: User Story 4 - 성과의 흐름을 차트로 본다 (Priority: P2)

**Goal**: 일봉마다의 잔고(KRW)·수익률 차트, 결측은 끊어 그린다

**Independent Test**: 결과로 차트가 그려지고, 결측 구간에서 선이 끊기며, 끝점이 표 최신 행과 같은지

### Tests for User Story 4 ⚠️

- [X] T039 [P] [US4] `backend/tests/integration/test_crypto_series_api.py` — `GET /api/crypto/simulation/series`: 점은 일봉마다, 잔고 = `balanceKrw`,
  수익률 KRW 기준, **표 최신 행과 같은 날짜·값**, `basisCurrency: "KRW"`, 커버리지 안 빈 날(픽스처에서 하루를 뺀 일봉) → `gaps.reason: source_missing`
  (`no_quote` 없음), 다운샘플링 표시, 202·오류는 표와 같다 (FR-023, FR-043, FR-044, SC-005, SC-007)
- [X] T040 [P] [US4] `frontend/tests/chartSeriesSourceMissing.test.ts`·`PerformanceChartMissing.test.tsx` — `source_missing`에서 선이 끊긴다,
  `no_quote`는 여전히 잇는다(외환·주식 불변), 범례 "결측 N구간" (FR-023, FR-043)

### Implementation for User Story 4

- [X] T041 [US4] `backend/src/api/services/crypto_series.py`·`backend/src/api/routes/crypto_series.py`(`compute_gaps(…, inside_reason="source_missing")`)·
  `frontend/src/lib/chartSeries.ts`·`frontend/src/components/stock/PerformanceChart.tsx`(범례)·`frontend/src/app/crypto/page.tsx`(차트 연결)
  (FR-023, FR-043, FR-044)
- [X] T042 [US4] 결측이 있는 실데이터를 찾으면 브라우저로 quickstart 19를 확인하고, 못 찾으면 T039·T040으로 대신했다고 기록한다 (FR-023)

**Checkpoint**: 차트 포함

---

## Phase 7: User Story 5 - 실행 이력을 남기고 비교한다 (Priority: P3)

**Goal**: 가상자산 이력(주식과 따로)과 KRW 기준 비교

**Independent Test**: 두 코인을 실행한 뒤 이력에서 골라 비교 차트가 "모두 KRW 기준"으로 그려지는지

### Tests for User Story 5 ⚠️

- [X] T043 [P] [US5] `frontend/tests/cryptoHistory.test.ts`·`CryptoHistory.test.tsx` — 실행하면 이력이 남고(코인 id·심볼·이름·slug·시작일·원금·통화),
  **주식 이력과 다른 저장 키**(서로 보이지 않음), 결과 수치를 저장하지 않음, 다시 실행해 `unknown_coin`이면 "검색에서 다시 고르세요", 막힌 원금 통화
  조합이면 사유, 둘 이상 고르면 비교 — 기준 문구 "모두 KRW 기준", 시작일이 다르면 범례에 각 시작일 (FR-045, FR-046)

### Implementation for User Story 5

- [X] T044 [US5] `frontend/src/lib/cryptoHistory.ts`·`frontend/src/components/crypto/CryptoHistory.tsx`(또는 006 `SimulationHistory`를 항목 표시를 받게
  일반화)·`frontend/src/stores/cryptoStore.ts`(이력·비교)·`frontend/src/app/crypto/page.tsx` — 비교는 `ComparisonChart` 그대로 (FR-045, FR-046)
- [X] T045 [US5] 실제 브라우저로 quickstart 15를 확인하고 기록한다 (FR-045, FR-046)

**Checkpoint**: 모든 스토리 완료

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T046 [P] `README.md`·`CLAUDE.md` — "가상자산은 다음 자산군 기능(번호 미정)"을 007로 갱신, 현재 상태 표에 007, `lifespan` 태스크 6개(가상자산 수집·
  목록 갱신 추가), **investing.com 원칙 II 이탈(개인 이용 잠정)**과 사용자 에이전트 설정, 가상자산 일봉 = UTC 하루·잠정 미저장 (FR-047, FR-018)
- [X] T047 품질 게이트 — 백엔드 전체 테스트·커버리지 80% 이상·mypy strict·ruff, 프론트엔드 테스트·tsc·eslint. **006의 기존 테스트가 고치지 않고
  통과하는지** 따로 확인한다 (SC-013)
- [X] T048 quickstart 전체(1~20)를 실제 브라우저로 한 번 더 돌려 실행 기록을 채운다 — 앞의 스토리별 확인과 다른 날이면 목록 주기·UTC 경계도 본다
  (SC-001~SC-012)

---

## Phase 9: 보드 통화 기호 위치·차트 축 쉼표 (반복 2026-10-04)

**Goal**: 성과 보드의 투자 원금·투자 수익에서 통화 기호를 숫자 앞으로 옮기고(`₩10,000,000`, `$10,000 (₩…)`, `-₩5,446`), 성과 추이 차트의 두 축
눈금에 천 단위 쉼표를 넣는다(잔고 `360,000,000`, 수익률 `3,200.00`). 보드·차트는 주식 화면도 함께 쓴다 (FR-042a, FR-043a, SC-014, SC-015)

**순서**: 테스트(T049·T051)를 먼저 커밋하고 최초 실패를 확인한 뒤 구현(T050·T052), 마지막에 브라우저 확인(T053). 구현 뒤 테스트가 실패하면 멈추고
먼저 보고한다(D2). **006 테스트 두 파일(`PerformanceBoardCurrency`·`PerformanceBoardKrw`)의 기대값을 바꾼다** — 요구사항이 바뀐 것이고
사용자가 반복 정의(2026-10-04)에서 승인했다. 테스트 커밋에서 바꾸고 사유를 적는다

- [X] T049 [P] `frontend/tests/PerformanceBoardCurrency.test.tsx`·`PerformanceBoardKrw.test.tsx`·`CryptoBoardKrw.test.tsx` — `formatMoneyWithSymbol`
  기대값을 기호 앞으로 고쳐 쓴다: `"10000000" KRW` → `₩10,000,000`, `"1000.50" USD` → `$1,000.50`, `"1000" USD` → `$1,000`, `"100000" JPY` →
  `¥100,000`, `"-5446" KRW` → `-₩5,446`, 모르는 통화 `"1000" GBP` → `GBP 1,000`. 보드 렌더링: 원화 원금의 원금·수익, 달러 원금 `$10,000 (₩…)`,
  엔 원금, 손실. `formatMoney`는 그대로다(표·차트·이력이 쓴다) (FR-042a, SC-014). **구현 뒤 005 `PerformanceBoard.test.tsx`의 손실 부호
  정규식(`-5,446`)이 실패해 `-₩5,446`으로 고쳤다** — 반복 정의의 영향 분석이 기호 없는 단언을 놓쳤다(D2, 사용자 승인 2026-10-04)
- [X] T050 `frontend/src/lib/format.ts` `formatMoneyWithSymbol` — 부호 → 기호 → 숫자 순, 모르는 통화는 코드와 공백.
  `frontend/src/components/stock/PerformanceBoard.tsx` 머리 주석의 `10,000,000₩` 예시 갱신 (FR-042a, SC-014)
- [X] T051 [P] `frontend/tests/PerformanceChartAxis.test.tsx`(신규) — 순수 함수 `formatAxisNumber`: `(360000000, 0)` → `360,000,000`, `(3200, 2)` →
  `3,200.00`, `(-400, 2)` → `-400.00`, `(999, 2)` → `999.00`, `(1234.6, 0)` → `1,235`. 차트: 기존 `lightweight-charts` 모의로 잔고·수익률 시리즈
  옵션의 `priceFormat`이 `type: "custom"`이고 그 formatter가 위 형식을 내는지, 결측으로 끊긴 **모든 구간의** 두 시리즈에 형식이 있는지(첫 구간만이
  아니다) (FR-043a, SC-015)
- [X] T052 `frontend/src/lib/format.ts` `formatAxisNumber(value: number, fractionDigits: number)` — 축 눈금 전용(그리기용 숫자를 받는다, 금액 문자열에
  쓰지 않는다). `frontend/src/components/stock/PerformanceChart.tsx` — 구간마다 잔고 시리즈에 `priceFormat: { type: "custom", minMove: 1, formatter }`
  (KRW·JPY 0자리, 그 밖 2자리 — `basisCurrency`로 고른다), 수익률 시리즈에 `minMove: 0.01`, 2자리 (FR-043a, SC-015)
- [X] T053 브라우저(3030) 확인 — quickstart 21·22를 주식(SK하이닉스, 원화 1,000만, 2020-01-01)과 가상자산(비트코인, 달러 원금)으로 실행하고
  기록한다. 품질 게이트(`npm test`, `npx tsc --noEmit`, `npx eslint .`) (SC-014, SC-015)

**Checkpoint**: 두 화면의 보드가 `₩…`·`$… (₩…)`로, 차트 두 축이 쉼표로 보인다. 수익률 표시(보드·표·툴팁)는 그대로다(범위 밖, research R7-14).
이력 비교 차트 축은 Phase 10

---

## Phase 10: 이력 비교 차트 수익률 축 쉼표 (반복 2026-10-04 #2)

**Goal**: 이력 비교 차트의 수익률 축 눈금에 천 단위 쉼표를 넣는다(`1,881.47`, `3,200.00`, `-400.00`). 성과 추이 차트와 같은 축 형식 함수를 쓴다.
비교 차트는 주식 화면도 함께 쓴다 (FR-046a, SC-016)

**순서**: 테스트(T054)를 먼저 커밋하고 최초 실패를 확인한 뒤 구현(T055), 마지막에 브라우저 확인(T056). 구현 뒤 테스트가 실패하면 멈추고 먼저
보고한다(D2). 축 형식 함수를 옮기므로 Phase 9의 `PerformanceChartAxis.test.tsx`(T051)와 기존 `ComparisonChart.test.tsx`(005 T087)·
`CryptoHistory.test.tsx`(T043)는 고치지 않고 통과해야 한다

- [X] T054 [P] `frontend/tests/ComparisonChartAxis.test.tsx`(신규) — 공용 함수 `axisPriceFormat`(`@/lib/chartSeries`): `(2)` → `type: "custom"`,
  `minMove: 0.01`, formatter `(1881.47)` → `1,881.47`, `(3200)` → `3,200.00`, `(-400)` → `-400.00`; `(0)` → `minMove: 1`, formatter `(360000000)` →
  `360,000,000`. 차트: 기존 `lightweight-charts` 모의로 두 이력 항목(그중 하나는 `source_missing` 결측으로 두 구간)을 그리면 시리즈 3개 **모두**의
  `priceFormat`이 `custom`·`minMove 0.01`이고 formatter가 `1,881.47`을 내는지 (FR-046a, SC-016)
- [X] T055 `frontend/src/lib/chartSeries.ts` `axisPriceFormat(fractionDigits)` — `PerformanceChart.tsx`의 `axisFormat`을 옮긴다(`formatAxisNumber`를
  쓴다). `frontend/src/components/stock/PerformanceChart.tsx`는 그것을 쓰고, `frontend/src/components/stock/ComparisonChart.tsx`는 항목·구간마다
  시리즈에 `priceFormat: axisPriceFormat(2)`를 준다. 머리 주석에 FR-046a (FR-043a, FR-046a, SC-015, SC-016)
- [ ] T056 브라우저(3030) 확인 — quickstart 23을 주식(이력 둘)과 가상자산(비트코인·솔라나 — 솔라나는 결측 1구간) 비교로 실행하고 기록한다.
  품질 게이트(`npm test`, `npx tsc --noEmit`, `npx eslint .`) (SC-016)

**Checkpoint**: 두 화면의 이력 비교 차트 수익률 축이 쉼표로 보이고, 성과 추이 차트의 수익률 축과 같은 형식이다

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작. T001은 출처를 부르는 유일한 단계다
- **Foundational (Phase 2)**: Setup 뒤. 모든 스토리를 막는다. T012는 006 테스트 전체가 통과해야 끝난다
- **US2 (Phase 3)** → **US1 (Phase 4)**: US1의 화면이 검색을 쓴다. 백엔드는 US1을 따로 시작할 수 있지만 브라우저 확인(T034)은 US2 뒤
- **US3 (Phase 5)**, **US4 (Phase 6)**: US1 뒤. 서로 독립 — 같은 파일(`crypto_simulation.py`·`page.tsx`)을 만지면 순서대로
- **US5 (Phase 7)**: US1 뒤 (US4의 시계열을 비교에 쓴다 — US4 뒤가 자연스럽다)
- **Polish (Phase 8)**: 모든 스토리 뒤
- **Phase 9 (반복 2026-10-04)**: Phase 8 뒤. 테스트(T049·T051)가 구현(T050·T052)보다 먼저, 브라우저 확인(T053)은 마지막
- **Phase 10 (반복 2026-10-04 #2)**: Phase 9 뒤(T052가 만든 축 형식을 옮긴다). 테스트(T054)가 구현(T055)보다 먼저, 브라우저 확인(T056)은 마지막

### Within Each Phase

- 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 모델 → 저장소 → 서비스 → 라우트 → 화면

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T018, T019, T031, T032 |
| `backend/src/api/services/crypto_simulation.py` | T032, T037 |
| `backend/src/api/services/stock_simulation.py`·`stock_fx.py`·`stock_collect.py` | T012 |
| `frontend/src/lib/types.ts` | T020, T033 |
| `frontend/tests/Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts` | T028 |
| `frontend/src/stores/cryptoStore.ts` | T033, T037, T044 |
| `frontend/src/app/crypto/page.tsx` | T033, T041, T044 |
| `frontend/src/components/stock/PerformanceChart.tsx` | T041, T052, T055 |
| `frontend/src/lib/chartSeries.ts` | T041, T055 |
| `frontend/src/components/stock/ComparisonChart.tsx` | T055 |
| `frontend/src/lib/format.ts` | T033, T050, T052 |

### Parallel Opportunities

- Phase 2 테스트 T003~T007은 모두 다른 파일 — 함께 쓴다
- 각 스토리의 테스트 태스크([P])는 함께 쓴다
- US3과 US4는 US1 뒤에 나란히 진행할 수 있다(위 같은 파일 표 주의)

---

## Parallel Example: Phase 2

```text
Task: "T003 test_investing_parse.py — 목록·일봉 파싱 (실제 픽스처)"
Task: "T004 test_investing_client.py — 헤더·커서·간격·403·재시도"
Task: "T005 test_evaluate_krw.py + test_stock_fx_currency.py"
Task: "T006 test_compute_gaps_reason.py + test_search_priority.py"
Task: "T007 test_crypto_schema.py"
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Phase 1 → Phase 2 (006 테스트 회귀 확인)
2. Phase 3 (US2 검색) → Phase 4 (US1 실행)
3. **멈추고 검증**: T034 브라우저 확인 — 검색 → 실행 → 수집 진행 → 보드·표

### Incremental Delivery

1. MVP(US2 + US1) — 달러 원금, 수수료 설정
2. US3 — 원화 원금
3. US4 — 차트(결측)
4. US5 — 이력·비교
5. Polish — 기록 갱신, 게이트, quickstart 전체
6. 반복 2026-10-04 — 보드 기호 위치, 차트 축 쉼표 (Phase 9)
7. 반복 2026-10-04 #2 — 이력 비교 차트 수익률 축 쉼표 (Phase 10)

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(007): <페이즈>`. 그 페이즈의 테스트만 담고 **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는
     예정된 것이다. 기존 테스트의 기대를 바꿔야 하면(주식 경로 공유 등) 이 커밋에서 바꾸고 사유를 적는다 — 단, 006 테스트를 바꿔야 한다면 먼저
     보고한다(T012)
  2. **구현 커밋** — `feat(007): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다
  - 테스트가 없는 태스크만 있는 페이즈(Setup의 픽스처·설정, 브라우저 확인, 문서)는 한 번 커밋한다
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다** — 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2)
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
- 픽스처를 새로 받아야 하면(형식 변경 등) T001과 같은 방식으로 받고 받은 날짜를 `fixtures/crypto/README.md`에 적는다
