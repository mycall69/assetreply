---

description: "Task list for 009-real-estate-investment-simulation"
---

# Tasks: 부동산 투자 시뮬레이션

**Input**: Design documents from `/specs/009-real-estate-investment-simulation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **필수.** 헌법 원칙 III(TDD)이 NON-NEGOTIABLE이므로 테스트 작성 → **실패 확인** → 구현 순서를 지킨다. **테스트를 구현보다
먼저 커밋한다** — 페이즈마다 테스트 커밋과 구현 커밋을 나눈다(아래 Notes). **구현 뒤 테스트가 실패하면 원인이 테스트 쪽으로 보여도 멈추고
실패 목록과 원인 판단을 먼저 보고한다**(이전에 통과하던 테스트가 실패로 바뀐 경우도 같다 — 006 D2).

**Organization**: 사용자 스토리별로 묶어 각 스토리를 독립적으로 구현·검증할 수 있게 한다. US1은 크기가 커서 두 페이즈로 나눈다 — 단지를 고르고
실거래를 받는 데까지(Phase 3), 시세·비용·보유 계산과 결과 화면(Phase 4). 둘 다 `[US1]`이고 MVP는 Phase 4까지다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (서로 다른 파일, 미완료 태스크에 의존하지 않음)
- **[Story]**: 소속 사용자 스토리 (US1~US4)
- 모든 태스크는 파일 경로와 **검증하는 FR·SC**를 적는다. 참조하는 태스크가 없는 인수 기준은 헌법 위반이다
- **ID는 안정적 참조다.** 반복으로 추가된 태스크는 번호를 이어 붙이고, 삭제된 태스크는 번호를 재사용하지 않고 취소선으로 남긴다

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Python 실행은 `backend/.venv/bin/python`을 직접 호출한다 (헌법 Python 가상환경 필수). 린트는 `ruff check --no-cache`(CLAUDE.md)

## 이 기능에서 특히 조심할 것

- **활용신청이 먼저다**: 실거래 상세·법정동코드·단지 목록·기본 정보 네 자료가 지금 키에 등록되어 있지 않다(research R9-1·R9-3). T001이 네
  자료를 불러 보고, 하나라도 403(게이트웨이 사유 30)이면 **멈추고 보고한다** — 상세 자료 없이 기본 자료로 물러날지는 사용자 결정이다
- **출처는 입력 오류를 알려 주지 않는다**: 틀린 시·군·구 코드·틀린 년월·미래 달이 모두 정상 + 0건이다(R9-1). 요청하는 시·군·구 코드는
  행정구역 표에 있는 것만, 년월은 코드가 만든다. 0건을 "거래 없음"으로 받아들이는 곳은 커버리지 하나다
- **인증키가 URL 질의(`serviceKey`)에 들어간다**: 요청 URL을 로그·원본·실패 사유·사건에 남기지 않는다. aiohttp 예외(`ClientResponseError`·
  `ClientConnectorError`)의 문구에는 요청 URL이 섞인다 — **키 값 그대로와 퍼센트 인코딩된 키를 직접 지운 뒤** `mask_secrets`를 거친다.
  `mask_secrets`는 16자 이상 영숫자 덩어리만 가리므로 `+`·`/`·`=`가 든 예전 형식 키는 조각이 남는다(지금 키는 64자 영숫자). 픽스처에는 응답
  본문만 둔다(FR-013, SC-011)
- **이중 인코딩**: 키는 디코딩 키를 **한 번만** 퍼센트 인코딩해 보낸다. 인코딩된 키를 다시 인코딩하면 `%2B`가 `%252B`가 되어 인증 실패(사유 30)로
  보인다(R9-1)
- **포털 오류는 HTTP 4xx + `OpenAPI_ServiceResponse`(XML)다**: 실거래 정상 응답의 `resultCode`(`000`)와 다른 곳에 있다. 사유 20·30·31·32 = 인증,
  22 = 한도, 12 = 서비스 없음(형식 — 엔드포인트가 바뀌었다). 한도 사유 22는 재시도하지 않고 그 수집을 멈춘다(R9-5)
- **하루 한도는 보내기 전에 센다**: `apt_api_usage`에 1을 더하고 설정 한도를 넘으면 보내지 않는다 — 출처가 막기 전에 멈추는 것이 목적이다
  (SC-012). 실패한 요청도 센다
- **같은 거래가 여럿이다**: 모든 필드가 같은 행이 송파구에서 232쌍 — 응답 안 순번(`occurrence`)을 키에 넣는다. 바뀌는 필드(`dealing_type`·
  `cancelled`·`cancelled_on`·`missing_since`)는 키에 넣지 않고 upsert로 고친다(R9-4)
- **해제·사라진 거래는 지우지 않는다**: 해제는 `cancelled`, 다시 받은 응답에 없는 행은 `missing_since` — 둘 다 집계에서 뺀다. 원본이 근거다
- **잘림**: 받은 행 수가 `totalCount`와 다르면 형식 오류이고 그 달을 받은 구간으로 기록하지 않는다. 금액·면적을 읽지 못한 행이 하나라도 있으면
  **응답 전체**가 형식 오류다(FR-019)
- **반올림 규칙이 셋이다 — 섞지 않는다**: 그 달 평균·창 평균은 원 미만 **반올림**(`ROUND_HALF_UP`, FR-016), 세액·수수료는 세목마다 **10원 미만
  버림**(FR-024), 수익률은 기존 `money.quantize_rate`(소수 6자리). 면적 경계는 `Decimal`로 비교한다(84.99·85.00·85.01)
- **화면은 해제를 뺀다 — 참조값만 해제를 넣는다**: 헬리오시티 스프레드시트는 해제를 넣은 값이다(R9-2). 스프레드시트와 맞추려고 화면 집계에 해제를
  넣으면 FR-008 위반이다. 참조값 테스트(T029)는 해제를 넣은 계산을 **따로 불러** 대조한다
- **창은 기준 달 뒤의 거래를 쓰지 않는다**(FR-016). 36개월 밖은 시세 없음 — 0이 아니라 비움·끊음(FR-026)
- **추정·잠정은 저장하지 않는다**: 계산할 때마다 보관한 거래에서 다시 구한다(FR-017). 결과도 저장하지 않는다
- **과세기준일**: 매입일 ≤ 그해 6월 1일이면 그해 보유세가 있다(6월 1일 매입 = 소유). 6월 시세가 없는 해는 0원이 아니라 "계산 불가"(FR-021)
- **세법 표가 덮지 않는 날짜는 계산하지 않는다**: 가까운 해의 규칙으로 대신하지 않는다 — `RuleNotCovered` → 409(FR-023)
- **날짜는 한국 시간 달력**이다 — 오늘·확인한 날·하루 호출 수의 날짜·계산 끝·잠정 기간. UTC로 정하면 오전 9시 전에 하루가 어긋난다
- **같은 날 202가 되풀이되면 안 된다 — 단, 받아 둔 시·군·구에서만**: 받아 둔 시·군·구(첫 달부터 잠정 기간 앞 달까지 모두 받음 — data-model
  5절)의 잠정 확인이 실패했으면 200 + `recheckFailed`이고, 화면은 `trades.state = collected`일 때만 한 번 다시 요청한다. 받지 않은 확정 달이 하나라도
  있으면 실패가 있었어도 202다 — 200을 주면 부분 결과다(FR-011, FR-014, 008 FR-016a)
- **잠정은 12개월이고 다시 받는 빈도가 둘이다**(spec Clarifications, research R9-5 실측): 최근 3개월은 `checked_on`이 오늘이 아니면, 4~12개월
  전 달은 `checked_on`이 이번 달이 아니면 다시 받는다. 잠정 3개월만 다시 받으면 해제의 25%가 확정 달에 남는다
- **현존 시·군·구 코드만 쓴다**(research R9-3 실측): 출처는 과거 거래도 개편 뒤의 새 코드로만 주고 사라진 코드에는 0건을 정상으로 준다.
  사라진 코드는 `retired_at`, 그 코드로 받은 거래는 `missing_since` — 같은 거래를 두 코드로 두 번 세지 않는다
- **단지 행은 지우지 않고 id는 바뀌지 않는다**: 짝짓기로 합칠 때 다른 행에 `merged_into`를 남기고, 단지 id를 받는 모든 경로가 그것을 따라간다 —
  이력이 옛 id를 가지고 있다(FR-032)
- **같은 본문의 원본은 다시 저장하지 않는다**: 같은 요청의 마지막 원본과 `body_sha256`이 같으면 새 행이 없다 — 확인한 사실은 커버리지의
  `checked_on`이 남긴다(data-model 4절)
- **공유 차트를 건드린다**(plan Complexity Tracking): 결측 사유 `no_price`, 점의 선택 키 `estimated`. **005~008의 차트 테스트는 고치지 않고 통과해야
  한다**
- **바꿔도 되는 기존 테스트는 plan의 목록뿐이다**: `test_crypto_worker.py`·`test_deposit_worker.py`(lifespan 태스크 7 → 8),
  `test_progress_sse.py`(SSE 목록에 `realestate_progress.py`), `Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`(부동산이 준비된 메뉴),
  `TopBarTitle.test.ts`(제목 한 줄 더함), `test_no_hardcoded_dates.py`(세법 표 `apt_tax_rules.py`의 법령 시행일을 예외로 —
  2026-10-05 D2 승인). 테스트 커밋에서 바꾸고 사유를 적는다. **이 밖의 기존 테스트를 바꿔야 하면 멈추고 보고한다**
- **실행 주체에는 그 주체를 거쳐야만 통과하는 테스트를 짝짓는다**(006 D1): `lifespan`의 부동산 수집 태스크, 동 선택·시뮬레이션 요청이 수집을
  시작하는 경로, 기동 시 고아 점유 회수
- **테스트는 네트워크 없이**(헌법 원칙 III, 소켓 차단 `conftest.py`). 출처를 부르는 것은 T001의 픽스처 저장 스크립트뿐이다

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 활용신청 확인, 실제 응답 픽스처, 설정 자리, 세법 표의 값

- [X] T001 공공데이터포털의 **실제 응답**을 받아 `backend/tests/contract/fixtures/apt/`에 저장한다. `.env`의 `DATA_API_KEY`를 파일에서 읽고(셸
  인자로 넘기지 않는다), 요청 사이 0.5초. **먼저 네 자료를 1회씩 불러 등록을 확인하고 하나라도 403(사유 30)이면 멈추고 보고한다**(quickstart
  준비). 받는 것: ① 상세 실거래(`RTMSDataSvcAptTradeDev`) 송파구 `11710`의 **2020-01~2023-09 전체 쪽**(헬리오시티 참조값 — 45개월)을
  `trade_11710_YYYYMM_pN.xml.gz`(gzip — 한 달 수백 KB라 그대로 넣지 않는다), 그 범위에 2쪽 이상인 달이 없으면 송파구에서 한 달 거래가 가장 많은 달
  하나를 더, 첫 달 탐색용 `2005-11`(0건)·`2005-12`(3건), 미래 달(빈 결과), 개편 확인용 춘천 `51110`·`42110`의 2020-01(새 코드 거래 있음 / 옛 코드
  0건 — research R9-3) ② 법정동코드 — 서울특별시 전체, 경기도 수원시(일반시 아래 구 — 41110 아래 41111…), 강원특별자치도와 옛 강원도(폐지
  코드가 오는지·어떻게 표시되는지 확인) ③ 단지 목록 — 가락동 `1171010700` ④ 기본 정보 — ③의 단지 전부 ⑤ 게이트웨이 오류 — 가짜 키(`TESTKEY…`)로 실거래 1회(사유 30).
  한도 초과(사유 22)는 실제로 받을 수 없으므로 ⑤의 코드·문구만 바꾼 **합성 픽스처**로 두고 README에 합성임을 적는다. 형식은 실거래 XML, 나머지는
  숫자처럼 보이는 문자열을 숫자로 바꾸지 않는 형식(XML 또는 JSON — 받은 응답으로 정하고 README에 적는다). **응답 본문만** 저장하고 요청 URL은
  저장하지 않는다 — 저장 뒤 파일들(압축을 푼 내용 포함)에 인증키 문자열이 없는지 검사한다. 받은 날짜·요청(키 자리는 `{key}`)·각 파일의 범위·
  `totalCount`를 `fixtures/apt/README.md`에 적는다. 상세 자료의 `aptSeq` 모양(시·군·구 코드가 들어가는지 — 개편 뒤 단지 식별자가 바뀌는지)도
  README에 적는다. 필드가 research R9-1·R9-3과 다르면 research를 고친다. 사용자 스프레드시트(45행 × 평형 5구분의
  건수·평균, 날짜 열 없음 — 2020-01부터 맞춤, R9-2)를 `helio_sheet_2020_2023.csv`로 옮겨 적는다. 스크립트는 저장소에 넣지 않는다(일회성)
  (FR-008, FR-009, FR-013, FR-019, SC-003, research R9-1~R9-3·R9-9)
- [X] T002 [P] `.env.example`에 설정 자리를 더한다 — `DATA_API_KEY`(빈 값 — 공공데이터포털 인증키, 활용신청 네 자료를 같은 키로), 
  `DATA_API_MAX_CONCURRENT`(3), `DATA_API_DAILY_LIMIT_TRADE`(9000)·`DATA_API_DAILY_LIMIT_KAPT`(4500)·`DATA_API_DAILY_LIMIT_REGION`(9000),
  `DATA_API_RETRY_MAX_ATTEMPTS`(4)·`DATA_API_RETRY_BASE_DELAY_MS`(1000), `APT_TRADE_PROBE_START`(`2005-01`), `APT_TRADE_PROVISIONAL_MONTHS`(12),
  `APT_TRADE_DAILY_RECHECK_MONTHS`(3), `APT_LIST_REFRESH_DAYS`(30 — 행정구역·동의 단지 목록). 값의 의미를 주석으로(포털 한도 10,000·5,000에서 여유를
  둔 값, 잠정 12개월은 늦은 해제의 98.8% — research R9-5) (FR-010, FR-012, FR-013, 헌법 원칙 II, research R9-5)
- [X] T003 [P] 세법 연혁을 조사해 `specs/009-real-estate-investment-simulation/research.md`에 **R9-7a 세법 표 값** 절을 쓴다 — 취득세(주택 유상, 지방교육세,
  농어촌특별세)·중개 보수 상한(매매)·재산세(주택 — 공정시장가액비율, 세율 구간, 1세대 1주택 특례, 지방교육세, 도시지역분, 7월 일괄 기준액)·
  종부세(주택 — 1인 공제, 공정시장가액비율, 세율 구간, 재산세 중복분 산식, 농어촌특별세)의 **시행일별 값**을 2006-01-01부터 오늘까지 빈틈없이.
  행마다 근거(법령명·조문·부칙·시행일)와 출처(국가법령정보센터 연혁 등)를 적는다. 2006~2008 종부세는 위헌 결정 뒤의 인별 기준으로 적는다(R9-7).
  부부 공동명의는 각자 기본 공제를 받는 인별 과세로 본다(1세대 1주택 단독 특례 공제를 쓰지 않는다) — 근거를 적는다. **참조 사례(SC-005)**를 함께
  정한다 — 취득세(2013-08-28 전·후, 2020-01 전·후의 6~9억 누진, 85㎡ 초과 농특세), 중개 보수(2015-04·2021-10-19 전·후 구간, 한도액), 재산세(7월
  일괄·분납, 2021 특례 전·후, 2022·2023 공정시장가액비율), 종부세(2019·2021·2022·2023, 공제 이하 0원)마다 입력·산식 전개·10원 단위 기대값,
  공식 예시(국세청·행정안전부 안내 자료)와 대조할 수 있으면 그 출처. 공식 예시가 없는 사례는 그 사실을 적는다. 값이 법령 연혁으로 확인되지
  않는 구간이 남으면 멈추고 보고한다(가까운 해로 메우지 않는다 — FR-023) (FR-020~FR-024, SC-005, research R9-7)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 스키마, 공공데이터포털 어댑터(관문·클라이언트·파서 셋). 모든 스토리가 기댄다

**⚠️ CRITICAL**: 이 페이즈가 끝나기 전에는 어떤 스토리도 시작하지 않는다

### Tests for Phase 2 ⚠️

- [ ] T004 [P] `backend/tests/contract/test_datagokr_trade_parse.py` — T001 픽스처로 상세 실거래 XML → `AptTrade`: 금액 `"120,000"` → 원
  `1200000000`(쉼표 제거, 만원 × 10,000, 정수), 전용면적 `Decimal("84.99")`(문자열 그대로), 계약일 = `dealYear`·`dealMonth`·`dealDay`(한국 시간
  달력), 단지 일련번호·법정동 코드(`sggCd + umdCd` 10자리)·지번(본번-부번)·동(없으면 빈 문자열)·층(지하 음수), `cdealType = O` → 해제·해제
  신고일(`YY.MM.DD` → 날짜), 거래 유형(2021-11 이전 빈 값 → `None`), 건축년도(`buildYear` → 정수, 빈 값이면 `None` — 입주년도의 대체값), **같은 응답 안에서 모든 키 필드가 같은 행의 `occurrence` 0·1·…**(같은 달을
  두 번 읽어도 같은 순번), 행 수 = README의 `totalCount`, 쪽 둘을 합쳐도 순번이 이어짐, `totalCount 0` → 빈 결과(오류 아님), **받은 행 수 ≠
  `totalCount` → 형식 오류(잘림)**, 금액·면적을 읽지 못하는 행이 하나라도 있으면 **응답 전체가 형식 오류**, `resultCode ≠ 000` → 형식 오류,
  XML이 아님 → 연결 오류, 게이트웨이 응답(사유 30 → 인증, 22 → 한도, 12 → 형식) (FR-008, FR-009, FR-014, FR-019, research R9-1·R9-4)
- [X] T005 [P] `backend/tests/contract/test_datagokr_lists_parse.py` — 법정동코드 → `Region`: 시·도·시·군·구·법정동 단계(`level` `sido`·`sgg`·`umd`),
  **리(`ri_cd ≠ 00`) 제외**, 실거래 요청 단위 `lawd_cd`(5자리), 수원시처럼 일반시 아래 구가 있으면 **구를 시·군·구로**(이름 "수원시 장안구")
  보이고 상위 시(41110)는 시·군·구 목록에서 뺌, 출처는 폐지 코드를 주지 않음(옛 "강원도" → `INFO-3` 결과 없음 — 오류가 아니라 빈 결과,
  T001 실측), 단지 목록 → `ComplexListing`(`kaptCode`·이름·`bjdCode`), 기본 정보 → `ComplexBasis`(세대수 = `kaptdaCnt`(실수 → 정수), **0이면
  `hoCnt`, 그것도 0이면 `None`** — 더샵송파루미스타 0.0·183, 사용승인일 `YYYYMMDD` → 연도, 지번 주소에서 본번·부번 — `142-`는 부번 0, 못
  읽으면 `None`), 없는 단지 코드(`kaptCode: null`) → 결과 없음. 빈 목록은 빈 결과 (FR-002, FR-003, FR-015, research R9-3)
- [X] T006 [P] `backend/tests/contract/test_datagokr_client.py`·`test_datagokr_gate.py`·`backend/tests/integration/test_apt_usage.py`(DB 계수기 — 한도까지 세고 멈춤, 자료·날짜별, 다시 만들어도 이어 셈, 동시 요청도 한도만큼만) — 가짜 세션으로: 요청 URL의 모양(자료별 경로, `LAWD_CD`·
  `DEAL_YMD`·`pageNo`·`numOfRows=1000`), **키는 한 번만 인코딩**(가짜 키 `TEST+KEY/1234567890abcd==`가 `%2B`·`%2F`·`%3D`로 한 번 — `%25`가
  없다), 돌려주는 원본에 URL이 없음, **연결 오류·HTTP 오류의 문구에 키가 없다** — 64자 영숫자 가짜 키와 `+`·`/`·`=`가 든 가짜 키 둘 다, 날 것과
  인코딩된 것 둘 다(문구에 URL이 섞인 aiohttp 예외를 흉내), 연결 오류·HTTP 5xx는 지수 백오프 + 지터로 `DATA_API_RETRY_MAX_ATTEMPTS`만큼
  재시도(지연 `DATA_API_RETRY_BASE_DELAY_MS` × 2ⁿ + 지터 — 주입한 잠), 인증·한도(사유 22)는 재시도하지 않음, 넘겨받은 세션을 닫지 않음. 관문(`DataGoKrGate`): 동시 요청이 `DATA_API_MAX_CONCURRENT`를 넘지 않음(실거래 줄·목록 줄·요청
  경로가 함께), **자료별 하루 호출 수를 보내기 전에 세고 한도에 닿으면 보내지 않고 한도 오류**(주입한 계수기·한국 시간 날짜 — 자정이 지나면 다시
  0부터), 사유 22를 받으면 그날 그 자료의 요청을 더 보내지 않음 (FR-012, FR-013, FR-014, SC-011, SC-012, 헌법 원칙 II, research R9-5)
- [X] T007 [P] `backend/tests/integration/test_apt_schema.py` — 마이그레이션 뒤 테이블 10개와 열(data-model — 작업은 `kind`·`target`·`total`·`done`): `apt_region`(`code CHAR(10)` PK, `level
  VARCHAR(8)`, `parent_code CHAR(10) NULL`, `lawd_cd CHAR(5) NULL`, `name VARCHAR(40)`, `full_name VARCHAR(80)`, `source VARCHAR(16)`, `ingested_at`,
  `seen_at`, `retired_at NULL`), `apt_complex`(`apt_seq VARCHAR(20) NULL UNIQUE`, `kapt_code VARCHAR(20) NULL UNIQUE`, `name VARCHAR(80)`, `jibun
  VARCHAR(20) NULL`, `move_in_year SMALLINT NULL`, `move_in_source VARCHAR(8) NULL`, `households INT NULL`, `details_checked_at NULL`, `merged_into
  BIGINT NULL`), `apt_trade`(`excl_area DECIMAL(9,4)`, `amount DECIMAL(15,0)`,
  `occurrence SMALLINT`, `dealing_type VARCHAR(8) NULL`, `cancelled BOOLEAN`, `cancelled_on DATE NULL`, `missing_since NULL`, `missing_reason VARCHAR(16) NULL`(`absent`·`region_retired`), `source VARCHAR(16)`,
  `ingested_at`, **유니크 (`lawd_cd`, `deal_date`, `apt_seq`, `apt_dong`, `floor`, `excl_area`, `amount`, `occurrence`)**, 인덱스 (`apt_seq`,
  `deal_date`)), `apt_raw_response`(`endpoint VARCHAR(24)`, `request_ref VARCHAR(40)`, `result_code VARCHAR(16) NULL`, `body LONGTEXT`,
  `body_sha256 CHAR(64)`, 인덱스 (`endpoint`, `request_ref`, `received_at`), **URL 열 없음**), `apt_trade_coverage`((`lawd_cd`, `deal_ym`) PK, `state VARCHAR(12)`, `trade_rows INT`, `checked_on DATE`), `apt_collection_job`·
  `apt_collection_lock`((`kind`, `target`) PK), `apt_api_usage`((`api`, `kst_date`) PK, `calls INT`), `apt_list_state`(`scope VARCHAR(20)` PK,
  `first_trade_ym CHAR(6) NULL`), `apt_setting`(`holding_tax_base_ratio DECIMAL(9,6)`, 행 없음 = 기본). `FLOAT`·`DOUBLE` 열이 없음, 마이그레이션
  하향·재상향 (FR-009, FR-012, FR-034, data-model 1~9절)
- [X] T008 [P] `backend/tests/unit/test_datagokr_boundaries.py`·`backend/tests/contract/test_apt_fixtures_no_key.py` — 공공데이터포털 응답 고유
  이름(`aptSeq`·`excluUseAr`·`dealAmount`·`cdealType`·`dealingGbn`·`kaptCode`·`kaptdaCnt`·`region_cd`·`locatadd_nm`·`resultCode`·
  `returnReasonCode`·`serviceKey`·`OpenAPI_ServiceResponse`)이 `src/ingestion/datagokr/` 밖(마이그레이션 제외)에 없다. `simulation/apt_*.py`가
  상위 계층을 임포트하지 않는다(기존 `test_layer_boundaries.py`가 이미 검사 — 바꾸지 않는다). 픽스처 전체(압축 안 포함)에 `.env`의 `DATA_API_KEY`
  값이 없다(키가 없는 환경에서는 건너뛴다) (FR-013, SC-011, 헌법 원칙 II·IV)

### Implementation for Phase 2

- [X] T009 `backend/src/config/settings.py`(테스트 `backend/tests/unit/test_settings_datagokr.py`) — `data_api_key`(비밀 — repr에 나오지 않게), `data_api_max_concurrent`(기본 3, 최소 1),
  `data_api_daily_limit_trade`(9000)·`_kapt`(4500)·`_region`(9000)(최소 1), `data_api_retry_max_attempts`(4, 최소 1)·`data_api_retry_base_delay_ms`
  (1000, 최소 0), `apt_trade_probe_start`(**코드 기본값 없음** — 없으면 None, `YYYY-MM` 검사. 헌법 — 시작일을 코드에 두지 않는다, 001 `ECOS_PROBE_FLOOR`와 같은 취지. 없으면 실거래 수집이 사유와 함께 멈춘다), `apt_trade_provisional_months`(12, 최소 1), `apt_trade_daily_recheck_months`(3,
  최소 1, 잠정 개월 이하), `apt_list_refresh_days`(30, 최소 1), `load_settings`에 연결 (FR-010, FR-012, FR-013, 헌법 원칙 II)
- [X] T010 `backend/src/db/models.py`·`backend/src/db/migrations/versions/…_부동산_스키마.py` — Apt* 9개(data-model 1~9절). 형식 이름 `AREA`
  (`DECIMAL(9,4)` — 2026-10-05 T001 실측으로 `DECIMAL(7,2)`에서 바꿈, research R9-2)·`WON`(`DECIMAL(15,0)`), 비율은 기존 `SPREAD`. 이전 head `c4d8e2f91b07` (FR-009, FR-034)
- [ ] T011 (2026-10-05 진행 중 — 실거래 파서 `trade_parse.py`만 남음: 상세 자료 등록 대기) `backend/src/ingestion/protocols.py`(`AptTrade`·`Region`·`ComplexListing`·`ComplexBasis`·결과·원본 타입, 출처 Protocol)·
  `backend/src/ingestion/datagokr/errors.py`(인증·한도·형식·연결)·`trade_parse.py`·`region_parse.py`·`kapt_parse.py` (FR-002, FR-003, FR-008,
  FR-014, FR-019, research R9-1·R9-3·R9-4)
- [ ] T012 (2026-10-05 진행 중 — `fetch_trades`만 남음: 상세 자료 등록 대기) `backend/src/ingestion/datagokr/gate.py`(`DataGoKrGate` — 이벤트 루프마다 하나, 동시 수 + 자료별 하루 계수(주입한 `UsageCounter`
  Protocol) + 사유 22 막힘)·`backend/src/ingestion/datagokr/client.py`(`DataGoKrClient(settings, gate, *, session=None)` — `fetch_trades(lawd_cd,
  ym, page)`·`fetch_regions(page)`·`fetch_complex_list(bjd_code)`·`fetch_complex_basis(kapt_code)` → (결과, 원본 본문), 키 한 번 인코딩, 오류 문구에서
  키를 직접 지운 뒤 `mask_secrets`, 재시도 설정으로 백오프+지터)·`backend/src/repository/apt_usage.py`(하루 호출 수 — 한국 시간 날짜, `UsageCounter` 구현)
  (FR-012, FR-013, FR-014, SC-012, research R9-5)

**Checkpoint**: 스키마·어댑터·관문 준비. 백엔드 전체 테스트(001~008 포함)가 고치지 않고 통과한다

---

## Phase 3: User Story 1 (1/2) - 단지를 고르고 실거래를 받는다 (Priority: P1)

**Goal**: 부동산 메뉴에서 시·도 → 시·군·구 → 법정동 → 단지를 풀다운으로, 평형을 일곱 구분으로 고른다. 행정구역·단지 기본 정보·그 시·군·구의
실거래를 백그라운드로 받고 진행을 보인다

**Independent Test**: 서울특별시 / 송파구 / 가락동을 고르면 헬리오시티가 입주년도·세대수와 함께 나오고, 송파구 실거래를 다 받은 뒤 평형 일곱
구분에 거래 수가 붙는지(quickstart 2~6)

### Tests for User Story 1 (1/2) ⚠️

- [X] T013 [P] [US1] `backend/tests/unit/test_apt_area.py` — 순수 함수: 일곱 구분의 키·이름·경계(10평대 50㎡ 미만, 20평대 50~70㎡ 미만, 30평대(국평)
  70~85㎡ **이하**, 30평대(대형) 85㎡ 초과~105㎡ 미만, 40평대 105~135㎡ 미만, 50평대 135~165㎡ 미만, 60평대 이상 165㎡ 이상), 경계 값(49.99·50·
  69.99·70·84.99·85·85.01·104.99·105·134.99·135·164.99·165)이 `Decimal`로 정확히 갈림, 헬리오시티의 실제 면적(39.1~39.86·49.19~49.32 → 10평대,
  59.96 → 20평대, 84.94~84.99 → 30평대(국평), 99.6 → 30평대(대형), 110.44·110.66·130.06 → 40평대, 150.07·150.09 → 50평대), 경계표가 화면용 형태
  (`minArea`·`maxArea`·`maxInclusive`)로 나옴 (FR-004, research R9-2)
- [ ] T014 [P] [US1] `backend/tests/unit/test_realestate_complex_match.py` — 순수 함수: 단지 목록(가락동 픽스처)과 실거래 단지(송파구 픽스처의
  가락동 거래)를 **법정동 코드가 같고 본번·부번이 같거나, 정규화 이름(공백·괄호와 그 안·"아파트" 제거)이 같고 그 동의 두 자료에서 하나씩뿐**
  이면 짝지음 — **헬리오시티는 대표 지번이 다르다(단지 목록 479, 실거래 913 — T001 실측)** 이름으로 짝지어 실거래의 그 `aptSeq`와 한 행,
  짝짓지 못한 실거래 단지는 따로(세대수 없음), 같은 동의 같은 이름 다른 지번 → 둘(이름으로 짝짓지 않음), 같은 `aptSeq`의 이름이 바뀌어도 하나(최근
  이름), 짝짓기 결과에 같은 단지가 두 번 나오지 않음, **두 행이 이미 따로 있을 때 짝이 드러나면 먼저 만든 행에 합치고 다른 행은 `merged_into`**
  (지우지 않음 — 결과가 "합칠 행 쌍"으로 나온다). 가락동 픽스처의 짝짓기 성공·실패 수를 기대값으로 고정 (FR-003, FR-032, research R9-3)
- [ ] T015 [P] [US1] `backend/tests/integration/test_apt_trade_collection.py` — 가짜 출처(T001 픽스처)로 실거래 실행기: **첫 달 탐색**
  (`APT_TRADE_PROBE_START`부터, 처음 거래가 있는 달을 `apt_list_state.first_trade_ym`에 — 2005-12), 달마다 `totalCount`만큼 쪽을 넘김, 거래 upsert
  (`source = molit:aptdev`, `ingested_at`은 다시 받아도 그대로), 원본은 쪽마다 한 행(본문만, `request_ref` `11710/202001/p1`), 커버리지(잠정 기간
  밖 `confirmed`, 최근 12개월 `provisional`, `trade_rows`, `checked_on` = 한국 시간 오늘), **같은 달을 다시 받아도 행이 늘지 않음**, 다시 받은 응답에
  해제가 붙으면 같은 행이 `cancelled`로, 사라진 행은 지우지 않고 `missing_since`(`missing_reason = absent`), 새 거래는 더함, 다시 받기에서 바뀐 수를 `apt_trade_revised`
  사건(시·군·구·달·더함·해제·사라짐), **잠정 달만 하루 한 번 다시 받고 확정 달은 다시 받지 않음**, 잠정 기간을 벗어난 달은 다음 확인에서
  `confirmed`, **잠정은 12개월(설정)이고 다시 받는 빈도가 둘** — 최근 3개월은 하루 한 번, 4~12개월 전 달은 한 달에 한 번(같은 달 안의 두 번째
  확인에서 4~12개월 전 달 요청 0건, 12개월 넘은 달은 다시 받지 않음), 4~12개월 전 달에 늦게 붙은 해제가 `apt_trade_revised`에 기록됨, **같은 본문을
  다시 받으면 원본 행이 늘지 않고**(해시) 다른 본문이면 새 행, **사라진 시·군·구 코드의 거래는 `missing_since`**(그 코드로 다시 요청하지 않음),
  잘림·읽기 실패 응답의 달은 커버리지에 없음, 실패 종류(`auth`·`rate_limited`·`format`·`network`)가 작업 `last_error`에 남고 **실패하면
  `checked_on`을 갱신하지 않음**, **하루 한도에 닿으면 받은 달까지 커버리지에 남기고 `rate_limited`로 멈추며 다음 실행은 받은 달 뒤부터**, 같은
  시·군·구 점유 중이면 두 번째 작업 없음, 실패 사유·사건·원본에 인증키 문자열 0건, 수집 전용 로그에 시작·완료·실패(시·군·구·구간·종류)
  (FR-002, FR-008~FR-014, FR-019, SC-006, SC-011, SC-012, research R9-3~R9-5)
- [ ] T016 [P] [US1] `backend/tests/integration/test_apt_list_collection.py` — 가짜 출처로 목록 줄: 행정구역 전체를 쪽마다 받아 upsert(`seen_at`),
  **다음 갱신에서 사라졌거나 폐지로 표시된 코드는 지우지 않고 `retired_at`**(시·군·구면 그 `lawd_cd`의 거래에 `missing_since`·`missing_reason =
  region_retired`), **새 코드로 받은 거래의 `apt_seq`가 같은 단지 행은 `umd_code`·`lawd_cd`가 새 코드로 바뀜**(식별자가 바뀐 경우 — 다른 `apt_seq` —
  옛 행은 그대로), 30일
  (`APT_LIST_REFRESH_DAYS`) 지나면 다시 받음, `apt_list_state('regions')`. 단지 목록(요청 경로 1회 — 이름 곧바로, 30일 지나 그 동을 처음 고르면 다시
  받음), 기본 정보는 새 단지만 1회로 세대수·입주년도 채움(`details_checked_at`), 실거래를 받은 뒤 짝짓기로 단지 행 합침(같은 행에 `apt_seq`·
  `kapt_code` — 두 행이 이미 있으면 먼저 만든 행에 합치고 다른 행 `merged_into`), 입주년도는 사용승인 연도(`move_in_source = kapt`) → 없으면 실거래
  건축년도(`trade`), 한도·실패 종류는 실거래와 같음 (FR-002, FR-003, FR-012, FR-014, FR-015, FR-032, research R9-3)
- [ ] T017 [P] [US1] `backend/tests/integration/test_realestate_lists_api.py` — `GET /api/realestate/regions`: 처음 → 202(`kind: region`, `progressUrl`)와
  수집 요청, 그 작업 실패 → 진행 스트림 `failed`(종류·사유)·다음 요청은 다시 202, 받은 뒤 시·도 → 시·군·구 → 법정동(가나다순, 수원시 장안구,
  **`retired_at`이 있는 코드 없음**), 30일 갱신 실패 → 받아 둔 목록 그대로 200, 모르는·사라진 `parent` → 400 `unknown_region`. `GET /api/realestate/complexes?umd=`:
  단지 목록으로 곧바로 `items`(가구수 내림차순·모르면 뒤, `households` 모르면 `null`, `jibun`, 합쳐진 행 없음), `details.pending`, 그 시·군·구
  실거래를 받은 적 없으면 수집을 **시작하고**(큐를 거쳐 — 동 선택이 수집의 실행 주체다) `trades.state = collecting`, 진행 중에 다시 요청하면 같은
  `jobId`(새 작업 없음), 받은 뒤 실거래 단지가 더해짐(`sources: ["trade"]`), **`trades.state = collected`는 첫 달부터 잠정 기간 앞 달까지 모두 받았을
  때만**(중간까지만 받았으면 아님), 마지막 작업이 실패했고 그 뒤 다 받은 적 없음 → `trades.state = failed`와 `failure`(`kind`·키 없는 `reason`), 단지
  목록 실패 → 200 + 실거래 단지만 + `listError`(빈 목록 대신 사유), 모르는 `umd` → 400. `GET /complexes/{id}/areas`: 일곱 구분을 늘(거래 0 포함),
  거래 수·첫 달은 **해제·사라짐 제외**, `startableFrom` = 첫 거래 달 1일과 `taxRulesFrom`(2006-01-01) 중 늦은 날(2005-12 첫 거래 → 2006-01-01),
  **합쳐진 단지의 옛 id → 같은 결과**, 실거래를 아직 받지 않았으면 202 (FR-002~FR-005, FR-011, FR-012, FR-014, FR-015, FR-032, SC-007)
- [ ] T018 [P] [US1] `backend/tests/integration/test_realestate_progress_sse.py` — 진행 스트림: `snapshot`(`kind` `trade`·`region`·`complex_details`,
  받은 것 / 받을 것 — 실거래는 처음부터 받을 달 수가 0보다 큼), `completed`, `failed`(`kind`, 인증키 없는 `reason`), 머리글 `no-transform`, 프레임마다
  새 스냅샷. **기존 `test_progress_sse.py`를 바꾼다** — 머리글 검사에 부동산 진행을 더하고 SSE 파일 목록에 `realestate_progress.py`(plan의
  목록 — 사유를 테스트 커밋에 적는다) (FR-011, FR-014)
- [ ] T019 [P] [US1] `backend/tests/integration/test_apt_worker.py` — **실행 주체**: 앱 기동이 부동산 수집 태스크를 띄운다(태스크 8개), 동 선택
  요청(단지 목록 200 + `trades.state: collecting`)과 시뮬레이션 요청(202)이 큐를 거쳐 워커가 수집을 끝낸다(내부 함수를 직접 부르지 않는다), 태스크 안 두 줄이 서로 기다리지 않음(실거래
  수집 중에 행정구역 갱신이 끝남), **기동 시 남은 부동산 점유를 회수**하고 그 작업을 `network`("점유 회수")로 마감, 예금 수집과 동시에 진행해도
  서로 기다리지 않음. **기존 `test_crypto_worker.py`·`test_deposit_worker.py`의 태스크 수 7 → 8**(plan의 목록 — 사유를 테스트 커밋에 적는다)
  (FR-011, FR-012)
- [ ] T020 [P] [US1] `frontend/tests/` — `RealEstatePage.test.tsx`(`/realestate` 화면, 풀다운 셋·단지·평형 라디오, 통화 칸 없음, 화면 아래 출처
  줄), `RegionPicker.test.tsx`(시·도를 바꾸면 시·군·구·동·단지·평형·결과가 빔, 동을 바꾸면 단지·평형·결과가 빔 — SC-007, 처음 목록 진행 줄,
  `label`이 붙은 `select`, **행정구역 수집 실패 → 지역 자리에 종류별 문구·할 일 `role="alert"`와 풀다운 비활성**, 받아 둔 목록이 있으면 경고 없음),
  `ComplexPicker.test.tsx`("헬리오시티 · 2018년 입주 · 9,510세대", 세대수 모르면 입주년도만, **같은 이름 단지가 둘이면 둘 다 끝에 지번 — 이름이 겹치지
  않으면 지번 없음**, 기본 정보 진행·실거래 진행 줄과 "처음 고르는 시·군·구는 전체 이력을 받습니다" 안내, `listError` 사유 `role="alert"`,
  **`trades.state = failed` → E9 문구·할 일 `role="alert"`**), `AreaBucketPicker.test.tsx`(`fieldset`·`legend` "평형", 일곱 항목·거래 수, 0건은 `disabled`와 "거래
  없음", 경계표 펼치기, 고른 구분의 경계·첫 달 줄 `aria-describedby`, 실거래 받기 전 안내), `realEstateStore.test.ts`(지역 선택 → 목록 요청, 202
  → 진행 구독 → 끝나면 다시 요청). **기존 테스트를 바꾼다**(plan의 목록): `Sidebar.test.tsx`(준비중 3 → 2, 준비되지 않은 항목의 예를 "투자
  비교"로, 부동산이 `/realestate` 링크), `noUnbuiltAssetRoutes.test.ts`(`realestate`를 빼고 사이드바 경로에 `/realestate`),
  `TopBarTitle.test.ts`(`["/realestate", "부동산"]` 한 줄 더함) (FR-001~FR-004, FR-007, FR-011, FR-014, FR-015, FR-036, SC-007)

### Implementation for User Story 1 (1/2)

- [X] T021 [US1] `backend/src/simulation/apt_area.py` — 경계표(데이터)와 `area_bucket(excl_area: Decimal) -> AreaBucket` (FR-004)
- [ ] T022 [US1] `backend/src/repository/apt_region.py`(행정구역 upsert·조회 — 현존 코드만, `seen_at`·`retired_at`, 목록 상태)·`apt_complex.py`(단지
  upsert — `apt_seq`·`kapt_code` 짝, 합칠 때 `merged_into`, id 해석이 `merged_into`를 따라감, 새 코드로 단지 행 코드 갱신, 세대수·입주년도·
  `move_in_source`)·`apt_trade.py`(거래 upsert — 바뀌는 필드만, 사라진 행·사라진 코드 표시와 `missing_reason`, 커버리지·`checked_on`·받아 둔 시·군·구 판정, 원본 — 같은 본문이면 새 행 없음, 단지·구분별 거래
  읽기 — 해제·사라짐 제외 여부를 인자로)·`apt_job.py`(작업·점유·고아 회수 — 008 `deposit_job`과 같은 수단). upsert는 기존 `db/dialect.py`
  (FR-002, FR-003, FR-009, FR-010, FR-012, data-model 1~8절)
- [ ] T023 [US1] `backend/src/api/services/realestate_complex_match.py` — 짝짓기 순수 함수(법정동 코드 + 지번, 아니면 정규화 이름) (FR-003)
- [ ] T024 [US1] `backend/src/worker/apt_queue.py`(시작 큐 둘 — 실거래·목록)·`apt_trade_runner.py`(첫 달 탐색, 쪽 넘김, 원본·거래·커버리지,
  잠정 다시 받기 — 최근 3개월 하루 한 번·4~12개월 한 달 한 번, 사라진 행·바뀐 수 사건, 받은 거래의 `apt_seq`로 단지 행 코드 갱신, 한도 멈춤)·
  `apt_list_runner.py`(행정구역 30일 갱신 — 사라진 코드 `retired_at`과 그 코드 거래 `missing_since(region_retired)`, 단지 기본 정보 채우기, 실거래 뒤
  짝짓기)·
  `apt_worker.py`(태스크 하나, 안에서 두 줄)·`backend/src/observability/events.py`(`apt_collection_started`·`_completed`·`_failed`·
  `apt_trade_revised`)·`backend/src/api/main.py`(`lifespan` 태스크 등록, 기동 시 회수, 관문·클라이언트 하나) (FR-002, FR-008~FR-014, research R9-3~R9-5)
- [ ] T025 [US1] `backend/src/api/services/realestate_lists.py`(행정구역·단지·평형 응답 — 현존 코드만, `jibun`, `trades.state`(`collected`·`failed`),
  `startableFrom`, 옛 단지 id 해석, 202·백그라운드 갱신 판정, 단지 목록 요청 경로 호출)·
  `backend/src/api/routes/realestate_regions.py`·`realestate_complexes.py`·`realestate_progress.py`·`backend/src/api/main.py`(라우터) —
  contracts/rest-api (FR-002~FR-004, FR-011, FR-015)
- [ ] T026 [US1] `frontend/src/lib/types.ts`(부동산 목록·진행 형식)·`frontend/src/lib/realEstateProgressStream.ts`·`frontend/src/stores/realEstateStore.ts`
  (지역·단지·평형 선택, 하위 비움, 목록 202·진행)·`frontend/src/components/realestate/RegionPicker.tsx`·`ComplexPicker.tsx`·`AreaBucketPicker.tsx`·
  `frontend/src/app/realestate/page.tsx`·`frontend/src/components/shell/Sidebar.tsx`(`/realestate`)·`TopBar.tsx`(제목 "부동산")·
  `frontend/src/components/stock/CollectingNotice.tsx`(부동산 202·진행 타입 — 주어·단위는 008의 선택 속성) — E1·E2·E9(같은 이름 단지의 지번,
  행정구역·실거래 실패 경고, 처음 시·군·구 안내) (FR-001~FR-004, FR-007, FR-011, FR-014, FR-015, FR-036)
- [ ] T027 [US1] 브라우저(3030, 창 1440px) 확인 — quickstart 1~6을 실행하고 `quickstart.md` 실행 기록에 적는다: 1(네 자료 정상 — T001 결과를
  옮겨 적어도 된다), 2(메뉴·제목·출처 줄), 3(처음 행정구역 받기 → 네 번의 선택), 4(상위 바꾸면 하위 비움), 5(가락동 단지 목록 → 세대수 채움 →
  송파구 실거래 진행(2초 안에 보임) → 실거래 단지 더해짐, 같은 단지 두 번 없음), 6(평형 일곱·거래 수·비활성·경계표) (FR-001~FR-004, FR-011,
  FR-036, SC-002, SC-007)

**Checkpoint**: 단지와 평형을 고를 수 있고 그 시·군·구의 실거래가 받아져 있다

---

## Phase 4: User Story 1 (2/2) - 그때 샀다면 지금 얼마인지 비용까지 빼고 본다 (Priority: P1) 🎯 MVP

**Goal**: 매입일(과 선택으로 매입가)을 넣어 실행하면, 시세 창으로 정한 매달 평가액과 취득 비용·보유세를 뺀 투자 수익을 보드와 월별 표로 본다.
받지 않은 구간이면 수집 진행 뒤 결과

**Independent Test**: 헬리오시티·30평대(국평)·2021-03-15로 실행해 표의 그 달 거래·평균이 해제를 뺀 기대값과 같고, 매입 행의 취득 비용과
7·9·12월 세금이 손계산과 같으며, 투자 수익 = 평가액 − 매입가 − 누적 비용인지(quickstart 7~11)

### Tests for User Story 1 (2/2) ⚠️

- [X] T028 [P] [US1] `backend/tests/unit/test_apt_price.py` — 순수 함수: 그 달 평균 = 해제·사라짐이 아닌 거래 합 ÷ 건수, 원 미만 **반올림**
  (`…0.5` → 올림, `…0.49` → 버림), 창 [1, 3, 6, 12, 24, 36]개월 중 거래가 있는 가장 짧은 창(창 안 **모든 거래의 평균** — 달별 평균의 평균이
  아니다), 기준 달 포함·**기준 달 뒤 거래는 쓰지 않음**, 1개월 = 실측(`estimated: false`), 넓은 창 = 추정, 36개월 안에 없으면 시세 없음(`None`),
  창 안에 잠정 달(오늘 기준 최근 12개월 — 설정)이 있으면 `provisional`, 해제 거래만 있는 달은 거래 없음. 손계산 참조 사례: 1·3·6·12·24·36개월 창,
  시세 없음, 잠정 달 포함 — 각각 시세·창·건수 (FR-008, FR-016~FR-018, SC-004, research R9-6)
- [ ] T029 [P] [US1] `backend/tests/unit/test_apt_helio_reference.py` — T001의 송파구 2020-01~2023-09 응답(gzip)을 **실제 파서**로 읽어 헬리오시티
  (`aptSeq`)만 고르고 평형 경계(T013)로 나눠, **해제를 넣은 계산**의 월별 평형별 건수·그 달 평균(반올림)이 `helio_sheet_2020_2023.csv`와
  **225칸 모두 같다**(SC-003). 같은 원본에서 **해제를 뺀 계산**은 그 기간 해제 27건만큼 다르고, 그 기대값(달·구분·건수·평균)을 손계산으로
  고정한다 — 화면 경로(`apt_price`)가 해제를 뺀 값을 낸다(SC-006) (FR-004, FR-008, FR-016, SC-003, SC-006, research R9-2)
- [X] T030 [P] [US1] `backend/tests/unit/test_apt_tax_rules.py` — 세법 표(데이터): 세목마다 규칙의 시행일 구간이 **2006-01-01부터 비거나 겹치지
  않고** 마지막 규칙의 끝이 없음(현행), 규칙마다 근거(법령·조문·시행일)가 비어 있지 않음, T003의 R9-7a 표와 값이 같음(대표 시행일 몇 곳),
  2005-12-31 → `RuleNotCovered(세목, 날짜)`, 비율·금액이 `Decimal` (FR-023, research R9-7)
- [X] T031 [P] [US1] `backend/tests/unit/test_apt_tax.py` — 순수 함수, T003의 참조 사례 모두 **10원 단위까지**: 취득세(85㎡ 이하·초과, 가액 구간,
  2013-08-28 전·후, 2020-01 6~9억 누진 — 지방교육세·농특세 포함), 중개 보수(2015-04·2021-10-19 전·후 구간, 한도액, 부가세 없음), 재산세(과세표준 =
  기준 금액 × 그해 공정시장가액비율, 누진·특례 세율, 지방교육세·도시지역분, **기준액 이하 7월 일괄 / 초과 7·9월 반씩**, 공동 소유여도 주택 하나의
  세액), 종부세(부부 5:5 — 1인 기준 금액 = 기준 금액 ÷ 2, 1인 공제, 공정시장가액비율, 누진, 재산세 중복분, 농특세, 두 사람 합, **1인 기준 금액이 공제
  이하면 0원**), 세목마다 10원 미만 버림 (FR-020~FR-024, SC-005)
- [X] T032 [P] [US1] `backend/tests/unit/test_apt_holding.py` — 순수 함수: 행 = 매입 달 ~ 이번 달 한 달에 한 줄(최신순), 매입 행에만 취득 비용,
  평가액 = 그 달 적용 시세, 누적 비용 = 취득 비용 + 그 달까지 낸 보유세, 투자 수익 = 평가액 − 매입가 − 누적 비용, 수익률 = 투자 수익 ÷ (매입가 +
  취득 비용)(`quantize_rate`), **보유세 기준 금액 = 그해 6월 적용 시세 × 비율(기본 0.6)**, 매입일 ≤ 6월 1일이면 그해 7·9월 재산세·12월 종부세,
  6월 2일 이후 매입이면 그해 없음, 이번 달까지 납부 달이 오지 않은 세금 없음, **6월 시세가 없는 해 → 그해 세금 `None`과 `taxGaps`(0이 아님)**,
  **세금마다 기준 시세 `basis`(달·시세·창·건수·추정·잠정)** — 6월 시세가 추정이면 `basis.estimated`, 시작 가능 날짜 = 첫 거래 달 1일과 세법 표의
  첫 날 중 늦은 날(이르면 `before_first_trade`와 근거 `first_trade`·`tax_rules`),
  시세 없음 달은 평가액·수익·수익률 `None`, 계산 끝 시세가 없으면 `lastPricedMonth`, 매입가 직접 입력이면 매입가·취득 비용이 그 금액, 매입 달
  시세 없음 + 매입가 없음 → `no_price_at_purchase`, 같은 입력 두 번 같은 결과(SC-008), 계산 끝 = 주입한 오늘(한국 시간) (FR-005, FR-006, FR-021,
  FR-022, FR-023, FR-025~FR-027, SC-006, SC-008, research R9-7·R9-8)
- [ ] T033 [P] [US1] `backend/tests/integration/test_realestate_simulation_api.py` — `GET /api/realestate/simulation`: 송파구 실거래를 받은 적 없음 →
  202(`kind: trade`, `monthsDone`·`monthsTotal`, `progressUrl`)와 수집 요청, 진행 중에 다시 요청 → 같은 `jobId`(새 작업 없음), 받지 않은 달이 있음
  → 202, 최근 3개월 달을 오늘 확인 전 → 202, **4~12개월 전 달을 이번 달 확인 전 → 202(이번 달 확인했으면 오늘 다시 202가 아님)**, **받아 둔
  시·군·구에서 오늘 잠정 확인 작업이 실패 → 200 + `summary.recheckFailed`(같은 날 202 되풀이 없음)**, **확정 달 일부를 받지 못한 채 오늘 한도로
  실패 → 202(200이 아니다 — 부분 결과 없음)**, 200의 `condition`·`acquisition`·
  `summary`·`rows`(contracts — 금액 원 정수 문자열, 수익률 소수 6자리, `rows[].window`·`windowTrades`·`estimated`·`provisional`, 세금은 납부 달
  행에만·다른 달 `null`, `installment`, `rule`), 해제 거래가 그 달 건수·평균에 없음(SC-006), `before_first_trade`(`startableFrom`),
  `no_price_at_purchase`(`month`), `no_trades_in_area`, `tax_rule_not_covered`(`tax`·`date`), `principalCurrency=USD` → `currency_not_allowed`,
  매입일 > 오늘(한국 시간) → `start_after_end`, 매입가 0·음수·쉼표·숫자 아님 → `invalid_query`, 모르는 단지 → `unknown_complex`, 합쳐진 단지의
  옛 id → 같은 결과, **사라진 `lawd_cd`에 남은 단지 → 409 `region_retired`(`lawdCd`), 새 코드로 받은 뒤에는 같은 단지 id로 200**(이력의 옛 id가
  이어진다 — `areas`·`series`도 같은 409), `before_first_trade`의 `basis`(`first_trade` · 2005-12 첫 거래면 `tax_rules`와 `startableFrom: 2006-01-01`), 세금의 `basis`(6월
  시세가 추정이면 `estimated: true`), 보유세 기준 비율은 `apt_setting` 기본 0.600000, 같은 요청 두 번 같은 응답(SC-008) (FR-002, FR-005~FR-007,
  FR-010, FR-011, FR-014, FR-018, FR-023, FR-025~FR-030, SC-006, SC-008)
- [ ] T034 [P] [US1] `frontend/tests/` — `RealEstateSimulationForm.test.tsx`(매입일 달력·월·년 이동·상한 오늘·하한 `startableFrom`, 매입가 선택 칸
  3자리 쉼표·단위 "원"·0 이하 거절, 409 안내 — `before_first_trade` 옮기기 수단(근거 `first_trade`면 첫 거래 달, `tax_rules`면 "세법 표는
  2006-01-01부터"), `no_price_at_purchase` 매입가 칸 초점, `tax_rule_not_covered` 세목·날짜, `region_retired` — 개편 사실과 "지역에서 다시 골라
  실행"), `RealEstateBoard.test.tsx`(칸 여섯, 기호가 숫자 앞
  `₩2,023,166,667`·손실 `-₩…`, 매입가 칸 "직접 입력" 또는 창·건수, 평가액 칸 창·건수·추정·잠정 글자, 기준 줄의 단지·평형·매입일·가정 넷),
  `RealEstateNotice.test.tsx`(잠정 줄 — 최근 12개월과 두 이유, 지금 시세 없음 줄 — 마지막 시세 달, 보유세 계산 불가 줄 — 해들, 확인 실패 줄 —
  `auth`면 "인증키 설정을 확인하세요", `format`이면 "어댑터를 고쳐야 합니다", 순서, `role="status"`), `RealEstatePerformanceTable.test.tsx`(열 11개·
  머리글 통화 KRW, 적용 시세 두 줄 "3개월·41건 추정·잠정", 그 달 평균 없으면 "—", 시세 없음 달 "시세 없음"·"—", 매입 행에만 취득 비용(합계·취득세·
  중개), 재산세 "(1/2)"·"(2/2)"·"(일괄)", 종부세 12월만, 다른 달 **빈칸**(0 아님), 계산 불가 해 "계산 불가", **세금의 기준 시세가 추정이면 "6월 시세
  추정"·잠정이면 "6월 시세 잠정"과 `title`의 기준 시세·창·건수**, 최신순, 표 `w-max`), `realEstateStoreSimulation.test.ts`(202 → 진행 구독 → 완료 뒤
  다시 요청, 실패 종류별 문구 E9, **`trades.state = collected`인 시·군·구면 `failed`를 받았을 때 한 번 다시 요청해 결과와 확인 실패 줄 —
  `collecting`·`failed`·`none`(받은 적 없거나 중간까지만)이면 다시 요청하지 않음, 한 실행에 한 번**) (FR-005, FR-006, FR-014, FR-017, FR-018,
  FR-002, FR-021, FR-026, FR-028~FR-030, SC-006, SC-010)

### Implementation for User Story 1 (2/2)

- [X] T035 [US1] `backend/src/simulation/apt_price.py` — 그 달 평균(반올림), 시세 창, 추정·잠정, 참조값 비교용 해제 포함 집계(테스트 전용 경로가 아니라
  인자로 고르는 같은 함수) (FR-016~FR-018, research R9-6)
- [X] T036 [US1] `backend/src/simulation/apt_tax_rules.py`(T003의 R9-7a 표 — 규칙마다 `effective_from`·`effective_to`·근거)·`apt_tax.py`(취득세·
  중개 보수·재산세(분납)·종부세(부부 5:5), 10원 미만 버림, `RuleNotCovered`) (FR-020~FR-024, research R9-7)
- [X] T037 [US1] `backend/src/simulation/apt_holding.py` — 매달 행·납부 달·세금의 기준 시세 `basis`·`taxGaps`·시작 가능 날짜(첫 거래 달과 세법 표 시작
  중 늦은 날)·요약(`quantize_rate`) (FR-005, FR-006, FR-021, FR-022, FR-025~FR-027, research R9-7·R9-8)
- [ ] T038 [US1] `backend/src/repository/apt_setting.py`(읽기 — 행 없으면 0.600000)·`backend/src/api/services/realestate_collect.py`(202 판정 — 받지 않은
  달, 최근 3개월 오늘 확인 여부, 4~12개월 이번 달 확인 여부, 진행 중 작업의 `jobId`, **받아 둔 시·군·구에서만** 오늘 실패 작업 → 200 + `recheckFailed` —
  모두 **단지의 현재 `lawd_cd`**로 판정하고 그 코드가 사라졌으면 409 `region_retired`)·`realestate_simulation.py`(입력 검증, 시작 가능 날짜, 매입가, 계산 끝 오늘
  한국 시간, 응답)·`backend/src/api/routes/realestate_simulation.py`·`backend/src/api/main.py`(라우터) — contracts/rest-api (FR-002, FR-005~FR-007,
  FR-010, FR-011, FR-014, FR-023, FR-025~FR-030)
- [ ] T039 [US1] `frontend/src/lib/types.ts`(시뮬레이션 응답)·`frontend/src/stores/realEstateStore.ts`(실행·202 대기·확인 실패 뒤 한 번 다시 요청)·
  `frontend/src/components/realestate/RealEstateSimulationForm.tsx`·`RealEstateBoard.tsx`·`RealEstateNotice.tsx`·`RealEstatePerformanceTable.tsx`·
  `frontend/src/app/realestate/page.tsx` — E1·E3·E4·E5·E9. 금액 형식은 `PerformanceBoard`와 같은 함수 (FR-005, FR-006, FR-014, FR-017, FR-018,
  FR-026, FR-028~FR-030)
- [ ] T040 [US1] 브라우저 확인 — quickstart 7~16과 19를 실행하고 기록한다: 7(처음 실행 202 → 2초 안 진행 → 결과, 부분 결과 없음), 8(표 2020-01~
  2023-09가 T029의 해제 제외 기대값과 같다), 9(매입 행·7·9·12월 세금 — T031 산식으로 그날 값 손계산), 10(같은 날 다시 3초 안, 출처 호출 없음),
  11(2021-07-15 매입 → 2021년 보유세 없음), 12(50평대 — 추정 창·시세 없음), 13(2018-01-01 → 409·옮기기, 2005-12 첫 거래 → 세법 표 근거로 2006-01
  옮기기), 14(매입가 직접 입력), 15(시세 없는 달 + 매입가 없음 → 409), 16(잠정 12개월 표시·6월 시세 추정 세금 표시), 19(1440px — 열 11개, 가로
  스크롤 없음) (FR-005~FR-007, FR-016~FR-030, SC-001, SC-002, SC-004~SC-006,
  SC-010)

**Checkpoint**: 부동산 화면에서 단지·평형·매입일로 결과를 볼 수 있다(MVP)

---

## Phase 5: User Story 2 - 보유세 가정을 정한다 (Priority: P2)

**Goal**: 설정의 부동산 보유세 기준 비율(기본 60%)을 바꾸면 결과가 새 비율로 다시 나오고 보드에 적용 비율이 보인다

**Independent Test**: 70%로 바꾸면 재산세·종부세가 늘고, 60%로 되돌리면 처음 결과(quickstart 17)

### Tests for User Story 2 ⚠️

- [ ] T041 [P] [US2] `backend/tests/integration/test_realestate_settings_api.py` — `GET` 기본 `{"holdingTaxBaseRatio": "0.600000", "isDefault": true}`,
  `PUT "0.7"` 뒤 시뮬레이션이 그 비율로 계산(`condition.holdingTaxBaseRatio`, 보유세 증가), 0·음수·1 초과·숫자 아님·**소수 6자리 초과**
  (`"0.6000001"`) → `422 invalid_setting`, `"1"`은 저장(100%), 다른 자산군 설정 불변 (FR-034, US2)
- [ ] T042 [P] [US2] `frontend/tests/RealEstateSettingsForm.test.tsx`·`realEstateStoreSettings.test.ts` — 60 % 표시·저장, `0`·`101`·`abc`·
  `60.12345`(백분율 소수 4자리 초과) 거절과 사유, `60.1234` → `"0.601234"` 저장, 기본값으로, 설정 화면에 다른 자산군 칸과 따로, 설정을 바꾸고 부동산
  화면에 돌아오면 다시 요청(008과 같다) (FR-034, US2)

### Implementation for User Story 2

- [ ] T043 [US2] `backend/src/repository/apt_setting.py`(쓰기)·`backend/src/api/routes/realestate_settings.py`·`backend/src/api/main.py`(라우터) —
  `GET`·`PUT /api/realestate/settings` (FR-034)
- [ ] T044 [US2] `frontend/src/components/settings/RealEstateSettingsForm.tsx`·`frontend/src/app/settings/page.tsx`·`frontend/src/stores/realEstateStore.ts`
  (설정 변경 뒤 다시 요청) — E8 (FR-034)

**Checkpoint**: 비율을 바꾸면 부동산 결과가 새 비율로 다시 나온다

---

## Phase 6: User Story 3 - 시세와 수익의 흐름을 차트로 본다 (Priority: P2)

**Goal**: 평가액·수익률을 두 축으로 그리고, 시세 없음 달은 끊고, 추정 점과 잠정 구간을 구별한다

**Independent Test**: 점마다 표의 그 달 값과 같고 끝점 = 보드, 시세 없음 구간이 끊기고, 추정 점에 표식(quickstart 18)

### Tests for User Story 3 ⚠️

- [ ] T045 [P] [US3] `backend/tests/integration/test_realestate_series_api.py` — `GET /api/realestate/simulation/series`: 점 = **첫 점 매입일** + 그 뒤
  매달 1일 + 끝점(매입일보다 이른 점 없음), **점마다 표의 그 달 `value`·`returnRate`와 같고 끝점은 `summary`와 같다**(SC-009), 시세 없음 달은 점 없음 + `gaps`(`no_price`), 점마다
  `estimated`·`provisional`, `provisionalFrom`(잠정 12개월의 첫 달), `basisCurrency` KRW, 202·오류는 표와 같다 (FR-031, SC-006, SC-009)
- [ ] T046 [P] [US3] `frontend/tests/PerformanceChartEstimated.test.tsx`·`chartSeriesNoPrice.test.ts` — `estimated`가 참인 점에만 표식(속이 빈 원)과 범례
  "○ 추정 시세(1개월 밖의 창)", `no_price` 사유에서 선이 끊김(앞뒤를 잇지 않음)과 범례 "시세 없음", 잠정은 기존 `provisionalFrom` 그대로, 키가 없으면
  지금과 같은 시리즈(**005~008의 `PerformanceChart*.test.tsx`·`chartSeries` 테스트는 그대로 통과**) (FR-031, SC-006)

### Implementation for User Story 3

- [ ] T047 [US3] `backend/src/api/services/realestate_series.py`·`backend/src/api/routes/realestate_series.py`·`backend/src/api/main.py`(라우터) —
  시뮬레이션과 같은 계산의 점(첫 점 매입일, 그 뒤 매달 1일), `gaps`, `estimated`·`provisional`, `provisionalFrom` (FR-031)
- [ ] T048 [US3] `frontend/src/lib/chartSeries.ts`(`no_price`를 끊는다)·`frontend/src/components/stock/PerformanceChart.tsx`(`estimated` 표식·범례,
  `collecting` 타입에 부동산 수집)·
  `frontend/src/lib/types.ts`(결측 사유 `no_price`, 점의 선택 키 `estimated`)·`frontend/src/stores/realEstateStore.ts`(시계열)·
  `frontend/src/app/realestate/page.tsx`(차트 연결) — E6 (FR-031)

**Checkpoint**: 차트가 표·보드와 같은 값으로 그려지고 추정·잠정·시세 없음이 구별된다

---

## Phase 7: User Story 4 - 실행 이력을 남기고 비교한다 (Priority: P3)

**Goal**: 실행 조건이 이력으로 남고, 다시 실행하거나 여러 이력을 골라 수익률을 비교한다

**Independent Test**: 헬리오시티 30평대(국평)·20평대를 같은 매입일로 실행한 뒤 이력에서 골라 비교 차트(quickstart 20)

### Tests for User Story 4 ⚠️

- [ ] T049 [P] [US4] `frontend/tests/realEstateHistory.test.ts`·`RealEstateHistory.test.tsx`·`realEstateStoreCompare.test.ts` — 저장 키가 다른 자산군과
  다름(`assetreplay:realestate-history:v1`), 조건만(단지 id·이름, 평형 구분, 매입일, 직접 넣은 매입가 또는 null — 결과 수치 없음), 같은 조건은 맨
  앞으로, 다시 실행 = 지역 풀다운까지 그 단지의 지역으로 맞추고 조건을 넣어 곧바로 실행, 삭제, 매입가 칸 "그 달 시세" 또는 금액, 둘 이상 골라
  비교 → `ComparisonChart`, 범례에 단지·평형·매입일, 잠정 항목 "(잠정)", 빠지는 항목은 "…의 시계열을 불러오지 못했습니다"와 사유(받지 않은 구간 —
  "실행해서 받으세요", 모르는 단지) (FR-032, FR-033, SC-006)

### Implementation for User Story 4

- [ ] T050 [US4] `frontend/src/lib/realEstateHistory.ts`·`frontend/src/components/realestate/RealEstateHistory.tsx`·`frontend/src/stores/realEstateStore.ts`
  (이력·비교)·`frontend/src/app/realestate/page.tsx` — E7. 비교는 `ComparisonChart` 그대로 (FR-032, FR-033)
- [ ] T051 [US4] 브라우저 확인 — quickstart 17·18·20(비율 70% → 되돌리기, 차트와 표·보드, 이력 비교)을 실행하고 기록한다 (FR-031~FR-034,
  SC-009)

**Checkpoint**: 이력·비교까지 동작한다

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T052 [P] `README.md`·`CLAUDE.md` — 현재 상태 표에 009(부동산: 국토교통부 실거래 상세 자료, 행정구역·단지 풀다운, 평형 일곱 구분, 시세 창
  1~36개월·추정·잠정 12개월, 취득 비용·재산세·종부세 — 연도별 세법 표·보유세 기준 비율 60%·부부 5:5), **다섯 자산군이 모두 구현됨**, `lifespan`
  태스크 8개(부동산 태스크 안의 실거래·목록 두 줄), **공공데이터포털 네 자료의 활용신청이 필요하고 하루 한도를 자체 계산한다**(처음 고르는
  시·군·구는 전체 이력 약 280회 — 하루 30곳 남짓), **잠정 12개월**(최근 3개월 하루 한 번·4~12개월 한 달 한 번 — 늦은 해제, 그 뒤의 해제 약 1.2%는
  반영하지 않음), **현존 시·군·구 코드만**(출처가 과거 거래도 새 코드로만 준다), 인증키가 URL 질의에 들어가므로 URL을 남기지 않는다, 세법이 바뀌면 `simulation/apt_tax_rules.py`에 규칙을 더한다(현행 규칙의 끝을 닫고), 화면·문서의 출처 표시
  (FR-035, FR-036)
- [ ] T053 품질 게이트 — 백엔드 전체 테스트·커버리지 80% 이상·mypy strict·`ruff check --no-cache`, 프론트엔드 테스트·tsc·eslint. **001~008의 기존
  테스트가 plan의 목록 밖에서 바뀌지 않았는지** 따로 확인한다(`git diff`로 기존 테스트 파일 목록) (SC-013)
- [ ] T054 quickstart 21~26을 실행하고 기록한다(21·22·24는 테스트 전용 DB의 임시 백엔드 — 008과 같은 방법, `.env`를 고치지 않고 환경변수로):
  21(틀린 키 → 행정구역 실패 경고, 받지 않은 곳 `auth` 문구·다시 열어도 사유, 받아 둔 송파구 → 한 번의 실행으로 결과와 확인 실패 줄, 중간까지만
  받은 곳 → 결과 없음), 22(한도 20 → `rate_limited`로 멈춤·커버리지 남음·출처의 사유 22 기록 0건, 한도를 되돌려 이어 받기), 23(수집 로그·원본·작업
  기록·`logs/backend.log`에 인증키 흔적 0건), 24(다음 날 — 최근 3개월만, 다음 달 — 4~12개월 전 달도, 12개월 넘은 달 요청 0건, 같은 본문 원본 늘지
  않음), 25(예금 수집과 동시), 26(춘천 — 새 코드로 2020년 거래, 옛 코드 요청 0건). 그날 할 수 없는 시나리오는 사유를 적고 통합 테스트(T015·T016·
  T017·T019)로 갈음한다 (FR-002, FR-010~FR-015, SC-001, SC-006, SC-011, SC-012)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작. **T001은 사용자의 활용신청이 끝나야 한다** — 출처를 부르는 유일한 단계다. T003(세법 조사)은 T001과 나란히
- **Foundational (Phase 2)**: T001 뒤(픽스처). 모든 스토리를 막는다
- **US1 (1/2) (Phase 3)**: Foundational 뒤
- **US1 (2/2) (Phase 4)**: Phase 3 뒤(받은 거래·평형 경계를 쓴다), 세법 표는 T003 뒤. Phase 4까지가 MVP
- **US2 (Phase 5)**, **US3 (Phase 6)**: Phase 4 뒤. 서로 독립 — 같은 파일(`realEstateStore.ts`·`page.tsx`·`main.py`)을 만지면 순서대로
- **US4 (Phase 7)**: Phase 4 뒤(US3의 시계열을 비교에 쓴다 — US3 뒤가 자연스럽다)
- **Polish (Phase 8)**: 모든 스토리 뒤

### Within Each Phase

- 테스트(⚠️) → 테스트 커밋(최초 실패 요약) → 구현 → 구현 커밋(통과 결과)
- 모델 → 저장소 → 계산 → 실행기 → 서비스 → 라우트 → 화면

### 같은 파일을 만지는 태스크 (병렬 불가)

| 파일 | 태스크 |
|------|--------|
| `backend/src/api/main.py` | T024, T025, T038, T043, T047 |
| `backend/src/repository/apt_setting.py` | T038, T043 |
| `frontend/src/lib/types.ts` | T026, T039, T048 |
| `frontend/src/stores/realEstateStore.ts` | T026, T039, T044, T048, T050 |
| `frontend/src/app/realestate/page.tsx` | T026, T039, T048, T050 |
| `frontend/src/components/stock/PerformanceChart.tsx`·`lib/chartSeries.ts` | T048 |
| `specs/009-real-estate-investment-simulation/research.md` | T001(필드가 다를 때), T003 |
| `specs/009-real-estate-investment-simulation/quickstart.md`(실행 기록) | T027, T040, T051, T054 |
| 기존 테스트 `test_progress_sse.py`·`test_crypto_worker.py`·`test_deposit_worker.py` | T018, T019 |
| 기존 테스트 `Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`·`TopBarTitle.test.ts` | T020 |

### Parallel Opportunities

- T002·T003은 T001과 나란히(T003은 출처를 부르지 않는다)
- Phase 2 테스트 T004~T008은 모두 다른 파일 — 함께 쓴다
- 각 페이즈의 테스트 태스크([P])는 함께 쓴다
- US2와 US3은 Phase 4 뒤에 나란히 진행할 수 있다(위 같은 파일 표 주의)

---

## Parallel Example: Phase 4 (US1 2/2 테스트)

```text
Task: "T028 test_apt_price.py — 반올림·창·추정·잠정·시세 없음"
Task: "T029 test_apt_helio_reference.py — 225칸(해제 포함)·해제 제외 기대값"
Task: "T030 test_apt_tax_rules.py — 구간 연속·근거·RuleNotCovered"
Task: "T031 test_apt_tax.py — 참조 사례 10원 단위"
Task: "T032 test_apt_holding.py — 행·납부 달·taxGaps·수익률"
Task: "T033 test_realestate_simulation_api.py — 202·recheckFailed·409·400"
Task: "T034 frontend 폼·보드·안내·표·스토어"
```

---

## Implementation Strategy

### MVP First (US1)

1. 사용자의 활용신청 → Phase 1 → Phase 2 (001~008 테스트 회귀 확인)
2. Phase 3 (US1 1/2) — **멈추고 검증**: T027 — 단지·평형 고르기, 실거래 수집 진행
3. Phase 4 (US1 2/2) — **멈추고 검증**: T040 — 보드·표, 헬리오시티 기대값과 세금 손계산 일치

### Incremental Delivery

1. MVP(US1) — 행정구역·단지·평형, 실거래 수집, 시세 창, 취득 비용·보유세, 보드·표
2. US2 — 보유세 기준 비율 설정
3. US3 — 차트(추정 표식·시세 없음 끊김·잠정)
4. US4 — 이력·비교
5. Polish — 기록 갱신, 게이트, quickstart 나머지

---

## Notes

- **커밋은 페이즈마다 두 번 한다** (헌법 원칙 III)
  1. **테스트 커밋** — `test(009): <페이즈>`. 그 페이즈의 테스트만 담고 **최초 실행의 실패 요약**(실패 수와 대표 이유)을 적는다. 이 단계의 실패는
     예정된 것이다. plan 목록의 기존 테스트를 바꾸면 이 커밋에서 바꾸고 사유를 적는다 — 목록 밖의 기존 테스트를 바꿔야 한다면 먼저 보고한다
  2. **구현 커밋** — `feat(009): <페이즈>`. 같은 테스트가 통과한 결과(통과 수, 게이트 결과)를 적는다
  - 테스트가 없는 태스크만 있는 페이즈(Setup의 픽스처·설정·세법 조사, 브라우저 확인, 문서)는 한 번 커밋한다
- **구현 뒤 테스트가 실패하면 멈추고 먼저 보고한다** — 원인이 테스트 쪽으로 보여도, 이전에 통과하던 테스트여도 같다(006 D2)
- 각 체크포인트에서 멈추고 그 스토리를 독립적으로 검증한다
- 픽스처를 새로 받아야 하면(형식 변경 등) T001과 같은 방식으로 받고 받은 날짜를 `fixtures/apt/README.md`에 적는다. 인증키가 들어가지 않았는지
  저장할 때마다 검사한다
- 세법이 바뀌면(새 시행일) `apt_tax_rules.py`에 규칙을 더하고 현행 규칙의 끝을 닫는다. 근거와 참조 사례를 함께 더한다(T030·T031)
- **2026-10-05 순서 변경(사용자 요청)**: T001이 활용신청 대기라, 출처와 무관한 계산(T013·T021·T028·T030~T032·T035~T037)을
  먼저 구현했다(커밋 `test(009): 계산`·`feat(009): 계산`). 헬리오시티 참조값 T029는 픽스처가 있어야 해 T001 뒤에 한다. D2 승인 2건 —
  `test_apt_price.py`의 잠정 시작 상수(테스트 실수: 2000-01이면 모든 달이 잠정), `test_no_hardcoded_dates.py`의 세법 표 예외
- **2026-10-05 T001 실측이 바꾼 것**: 전용면적이 소수 4자리까지 온다(`84.9725` — research R9-1). `AREA`를 `DECIMAL(7,2)`에서
  `DECIMAL(9,4)`로 바꿨다 — 마이그레이션 `a9d3e5c71f20`이 아직 푸시 전이라 같은 리비전을 고쳤다(개발 DB는 내렸다 올린다). 이 기능의
  스키마 테스트 `test_apt_schema.py::test_거래`의 기대 자릿수를 함께 고쳤다(요구사항 변경 — data-model 갱신에 따른 것, 테스트 커밋에서).
  순번(`occurrence`)은 계약 월의 모든 쪽을 이어 매긴다(2020-06 실측 — 같은 키가 1쪽·2쪽에 나뉘어 온다, R9-4)
