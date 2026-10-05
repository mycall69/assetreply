# Implementation Plan: 부동산 투자 시뮬레이션

**Branch**: `009-real-estate-investment-simulation` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-real-estate-investment-simulation/spec.md`

## Summary

사이드바의 "부동산"을 실제 메뉴로 만든다. 시·도 → 시·군·구 → 법정동 → 단지를 풀다운으로, 평형을 일곱 구분으로 고르고 매입일(과 선택으로
실제 매입가)을 넣으면, 그때 산 아파트를 지금까지 들고 있을 때의 평가액에서 매입가·취득 비용(취득세·중개 수수료)·해마다 낸 보유세(재산세·
종부세)를 뺀 성과를 보드·월별 표·차트·이력 비교로 보인다. 시세는 국토교통부 아파트 매매 실거래가로 정한다 — 같은 단지·같은 평형 구분의
그 달 평균, 없으면 3·6·12·24·36개월로 넓힌 평균(추정)이다. 헌법 원칙 IX의 다섯 자산군 중 마지막이다.

**설계 중 실측한 결과**(research R9-1~R9-5, 2026-10-05 공공데이터포털):

| 실측 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| 실거래 요청 | 시·군·구 5자리 × 계약 년월, XML, 한 쪽 1,000행. 송파구 한 달 최대 1,173건(2쪽) | 수집 단위 = 시·군·구 × 계약 월. 받은 행 수 ≠ `totalCount`면 형식 오류(R9-1) |
| 입력 오류 | 틀린 시·군·구 코드·틀린 년월·미래 달이 모두 정상 + 0건 | 요청 코드는 행정구역 표의 코드만(R9-1) |
| 시작 | 송파구 2005-12 계약분부터(2005-11 이전 0건) | 첫 달은 2005-01부터 탐색해 발견(헌법 — 상수 아님, R9-5) |
| 단지 식별자 | 기본 자료에 없다 — **상세 자료**에 `aptSeq`·법정동 코드·본번·부번 | 상세 자료를 쓴다. **지금 키는 미등록**(403 사유 30) — 사용자 활용신청(R9-1) |
| 행정구역·단지 정보 | 법정동코드·단지 목록 V4·기본 정보 V5 — 셋 다 **미등록** | 사용자 활용신청. 단지 목록 + 실거래 단지 짝짓기(R9-3) |
| 같은 거래 | 송파구 29,119건 중 모든 필드가 같은 행 232쌍(같은 날 같은 층·면적·금액의 다른 호) | 거래 키에 응답 안 순번(`occurrence`)을 더한다(R9-4) |
| 헬리오시티 참조값 | 경계표(FR-004)로 2020-01~2023-09 **225/225칸** 일치 — 단, **해제 거래를 넣고 평균을 반올림**한 값 | 화면은 해제 제외·반올림(사용자 결정), 참조값 테스트는 해제 포함 계산(SC-003, R9-2) |
| 거래 유형 | 2021-11 이전은 빈 값 | 직거래 구분은 보관만(시세에 넣는다 — 사용자 결정) |
| 한도 | 개발계정 하루 10,000회(실거래·법정동), 5,000회(단지 정보), 이용허락범위 제한 없음 | 하루 호출 수를 DB에 세어 설정 한도(9,000·4,500·9,000) 전에 멈춘다(R9-5) |
| 늦은 해제 (분석 단계) | 송파구 해제 840건 중 계약 달 + 3개월 이후 신고 25%, 11개월 이내 98.8%, 가장 늦게 +35개월 | **잠정 12개월** — 최근 3개월은 하루 한 번, 4~12개월은 한 달 한 번 다시 받는다(사용자 결정, R9-5) |
| 행정구역 개편 (분석 단계) | 출처는 과거 거래도 새 코드로만 준다(춘천 42110 → 0건 / 51110 → 308건, 2020-01) | 현존 코드만 쓰고, 사라진 코드의 거래는 집계에서 뺀다(R9-3) |

**구현 전에 사용자가 할 일**: 공공데이터포털에서 네 자료를 활용신청한다(quickstart 준비 — 같은 계정·같은 키). T001이 그 뒤 실제 응답을
픽스처로 받는다.

세법은 2006-01-01부터의 **시행일별 표**를 데이터 모듈 하나(`simulation/apt_tax_rules.py`)에 두고 항목마다 근거 법령·시행일을 적는다 —
취득세·중개 보수는 매입일, 재산세·종부세는 그해 6월 1일에 시행 중인 표를 쓴다. 보유세 기준 금액은 그해 6월 시세 × 60%(공시가격 대용)이고
그 위에 공정시장가액비율을 곱한다(사용자 결정). 공유 부품 변경은 차트 둘(결측 사유 `no_price`, 점의 선택 키 `estimated`)뿐이고 보드는 부동산
전용이다(R9-10).

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp. XML은 표준 라이브러리(`xml.etree.ElementTree`) — 새 의존 없음 |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — **신규 테이블 10개**(data-model), Alembic 마이그레이션 하나(head `c4d8e2f91b07` 다음). 기존 테이블 변경 없음 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library. 출처는 **실제 응답 픽스처**로 계약 테스트 |
| 타입·린트 | mypy strict, ruff(`--no-cache`) / tsc, eslint |
| 출처 | **공공데이터포털**(국토교통부 실거래 상세·단지 목록·기본 정보, 행정안전부 법정동코드) — 공식 공개 API, 한 인증키(`DATA_API_KEY`)가 URL 질의에 들어간다. 동시 수·자료별 하루 한도·재시도(`DATA_API_RETRY_MAX_ATTEMPTS` 4, `DATA_API_RETRY_BASE_DELAY_MS` 1000)는 설정 |
| 원금 통화 | KRW만. 환율 없음 |
| 수집 실행 | 앱 수명 태스크 1개 추가(8번째) — 안에서 실거래 줄과 목록 줄(행정구역·단지 기본 정보)로 나뉜다. 두 줄과 요청 경로의 단지 목록 호출이 출처 관문(`DataGoKrGate`)을 함께 지난다 |
| 계산 | 순수 함수 — `simulation/apt_area.py`(평형 경계), `apt_price.py`(시세 창), `apt_tax_rules.py`(세법 표 — 데이터), `apt_tax.py`(세액), `apt_holding.py`(매달 행·요약) |
| 성능 목표 | 받은 구간이면 결과 3초 안(SC-001). 수집 진행 2초 안(SC-002) |
| 규모 | 시·군·구 하나의 전체 이력 약 250개월 × 1~2쪽 ≈ 280회(하루 한도로 30곳 남짓 — 화면 E2·README에 안내). 다시 받기는 시·군·구당 하루 3~4회 + 한 달 9~10회. 원본은 송파구 95개월 약 15MB(실측) — 같은 요청의 본문이 같으면 다시 저장하지 않는다(data-model 4절). 단지의 거래는 많아야 수천 건 — 요청마다 읽어 계산한다. 결과 행은 많아야 250줄 남짓이라 한 번에 보낸다 |
| 제약 | 백엔드 단일 워커 — 기동 시 남은 점유를 회수한다(007·008과 같다). 테스트는 네트워크 없이(헌법 원칙 III). 계약일·달은 시각이 없는 **한국 시간 달력**이다(008과 같다 — 받은·갱신 시각은 UTC) |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 출처 호출은 aiohttp. 실거래·기본 정보 수집은 워커 태스크(202 + SSE). 요청 경로에서 부르는 것은 단지 목록 1회뿐이고 그것도 비동기로 관문을 지난다. 동기 I/O 없음 |
| II. 데이터 소스 격리 | ✅ | 어댑터를 `ingestion/datagokr/` 안에 둔다 — XML 필드명·`resultCode`·게이트웨이 사유는 그 밖으로 나가지 않는다(Protocol). **이용허락범위 제한 없음을 실측으로 확인했다**(R9-1, R9-3 — 이탈 아님). 출처 표시는 화면 E1과 README(FR-036). 동시 수(`DATA_API_MAX_CONCURRENT`)·자료별 하루 한도(`DATA_API_DAILY_LIMIT_*`)·재시도(`DATA_API_RETRY_MAX_ATTEMPTS`·`DATA_API_RETRY_BASE_DELAY_MS`)는 설정으로 선언, 실패는 지수 백오프 + 지터, 인증 실패는 다시 시도하지 않고 한도 사유 22는 즉시 멈춘다. 인증키는 `.env`에만 — URL에 들어가므로 URL을 로그·원본·사유에 남기지 않고 `mask_secrets`를 거친다(FR-013) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행·먼저 커밋·최초 실패 확인, 구현 뒤 실패하면 멈추고 보고(006 D2). 계약 테스트는 실제 응답 픽스처(R9-9). 참조값은 헬리오시티 225칸(SC-003), 시세 창(SC-004), 세금 경계 해(SC-005). 실행 주체(`lifespan`의 수집 줄, 202가 요청한 수집)는 그 주체를 거쳐야만 통과하는 테스트와 짝짓는다(006 D1) |
| IV. 모듈화 | ✅ | 계산은 `simulation/apt_*.py` 순수 함수(DB·HTTP 없음). 세법 표는 로직 없는 데이터 모듈. 단지 짝짓기도 순수 함수(`api/services/realestate_complex_match.py`). 도메인은 `AptTrade`·`Region`·`ComplexListing`(Protocol 쪽 형식)만 본다 |
| V. 정합성·재현성 | ✅(기록 2) | 원본 분리 보관(본문만, URL 없음 — 같은 본문은 다시 저장하지 않되 다른 판은 모두 남긴다), upsert, `source`·`ingested_at`, 커버리지(시·군·구 × 계약 월, 첫 달 발견). **잠정 = 최근 12개월**(출처가 해제를 계속 바꾸는 기간 — 실측), 최근 3개월은 하루 한 번·4~12개월은 한 달 한 번 다시 받고 결과에 잠정을 드러낸다. 확정 달은 다시 받지 않는다(그 뒤의 해제 약 1.2%는 spec Assumptions의 한계). 보유세가 추정·잠정 시세에서 나왔으면 그 기준을 세금과 함께 싣는다. 입주년도의 출처(`move_in_source`)를 남긴다. 해제·사라진 거래는 지우지 않고 표시해 집계에서 뺀다(원본이 근거). **시세 창은 명시적 추정 규칙**이다 — 결과에 창·건수·추정 표시를 별도 필드로 싣고 저장하지 않는다(원칙 V의 "보정은 규칙을 문서화하고 별도 컬럼으로 표시"). 시세 없음은 0이 아니라 비움·끊음. 고유 키는 **(자산 식별자, 날짜)를 거래 사건에 맞춘 것**이다 — Complexity Tracking |
| VI. 금융 정확성 | ✅ | `Decimal`, 금액 `DECIMAL(15,0)`·면적 `DECIMAL(7,2)`·비율 `DECIMAL(9,6)`. 만원 → 원 정수 변환, 평균 반올림, 세액 10원 미만 버림 위치를 정해 두고 참조값(SC-003~SC-005). 가정(60%·부부 5:5·1세대 1주택·연도별 세법)은 설정·데이터 모듈·보드 기준 줄로 드러낸다 |
| VII. UI·진행 | ✅ | Zustand, SSE 진행(006~008과 같은 `no-transform`), Lightweight Charts(축 쉼표), 추정·잠정·시세 없음 구별 |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | 부동산이 마지막 자산군. 수집~화면 수직 슬라이스. 오피스텔·대출·임대·매도 비용·재건축 연결은 범위 밖(YAGNI) |
| DB 운영 규약 | ✅ | ORM, 마이그레이션 하나, upsert는 기존 방언 추상화(`db/dialect.py`), 커넥션 풀은 기존 엔진 |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음. 픽스처 경로는 `pathlib` |
| 명세 작성 규약 | ✅ | 아래 추적성 표. 설계 중 바뀐 요구(해제 제외의 참조값 검증 방식, 반올림, FR-014 확인 실패, FR-021 6월 시세 없음)와 **분석 뒤 바뀐 요구**(FR-002 현존 코드, FR-003 이름 곧바로·지번·id 안정, FR-005 세법 표 하한, FR-010 잠정 12개월, FR-014 받아 둔 시·군·구, FR-021 기준 시세 표시, FR-034 자릿수, SC-006, Assumptions 개편·늦은 해제)를 spec에 같은 작업 단위로 반영했다. 모든 FR·SC가 태스크에 연결되어 있다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 출처 응답의 누출 | ✅ | 도메인·API는 시·군·구 코드·단지 id·평형 키·`AptTrade`만 본다. `aptSeq`·`kaptCode`는 저장 계층의 짝짓기 열이고 응답에는 단지 id만 나간다 |
| 인증키 누출 | ✅ | 원본 테이블에 URL 열이 없고 `request_ref`는 불투명한 참조다. 실패 사유·사건은 `mask_secrets`. 픽스처는 응답 본문만(자동 검사, quickstart) |
| 활용신청 의존 | ⚠(기록) | 네 자료가 지금 키에 미등록이다. 신청 전에는 T001(픽스처)부터 막힌다 — 구현 순서의 첫 단계로 둔다. 상세 자료가 끝내 안 되면 기본 자료 + (법정동·지번·이름) 묶기로 물러나고 그 한계를 화면에 적는다(R9-1 Alternatives) |
| 잠정·추정 | ✅ | 잠정 달·추정 시세는 계산 안에서만 정해지고 저장하지 않는다. 결과를 보관하지 않아 다시 확인·확정과 함께 바뀐다. 보드·표·차트·비교 모든 경로에 표시가 있다(SC-006) |
| 행정구역 개편 | ✅ | 풀다운·요청은 현존 코드만. 사라진 코드는 `retired_at`으로 남기고 그 코드의 거래는 `missing_since` — 같은 거래를 두 코드로 두 번 세지 않는다(R9-3 실측) |
| 단지 id 안정성 | ✅ | 단지 행을 지우지 않고 합칠 때 `merged_into`를 남긴다 — 이력의 옛 id도 같은 단지로 열린다(data-model 2절) |
| 세법 표 범위 | ✅ | 시작 가능 날짜는 첫 거래 달과 표의 첫 날(2006-01-01) 중 늦은 날(`before_first_trade` + 근거). 보유 중의 날짜를 표가 덮지 않으면 409 `tax_rule_not_covered` — 가까운 해로 대신하지 않는다(FR-023). 표의 구간이 겹치거나 비지 않음을 단위 테스트가 검사한다 |
| 공유 부품 변경 | ✅(기록) | 차트의 결측 사유 `no_price`(끊는다), 시계열 점의 선택 키 `estimated`(표식) — 둘 다 선택이고 기본이 지금 동작이다. 005~008 차트 테스트는 바꾸지 않고 통과해야 한다 |
| 바뀌는 기존 테스트 | ⚠(승인 필요) | lifespan 태스크 수(7 → 8, `test_crypto_worker.py`·`test_deposit_worker.py`), 사이드바·미구현 가드(`Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts` — `realestate`를 준비된 메뉴로), 날짜 하드코딩 가드(`test_no_hardcoded_dates.py` — 세법 표의 법령 시행일은 축적 시작일이 아니므로 `apt_tax_rules.py`만 예외, 2026-10-05 승인). 008과 같은 종류의 변경이다 — 구현 단계에서 사용자 승인을 받는다(006 D2) |

## Project Structure

### Documentation (this feature)

```text
specs/009-real-estate-investment-simulation/
├── spec.md              # /speckit-specify, /speckit-clarify (+ plan 실측 뒤 결정 2건)
├── plan.md              # 이 파일
├── research.md          # R9-1 ~ R9-11 (공공데이터포털 실측, 헬리오시티 225칸 대조)
├── data-model.md        # 신규 테이블 10개 + 세법 표 모듈
├── quickstart.md        # 활용신청 4건, 검증 시나리오 26개
├── contracts/
│   ├── rest-api.md      # /api/realestate/* + 출처(공공데이터포털 4자료) 계약
│   └── ui-wireframes.md # E1~E9
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks — 54개, Phase 1~8(US1은 Phase 3·4 두 페이즈)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── config/settings.py                # 변경 — DATA_API_KEY, DATA_API_MAX_CONCURRENT(3), DATA_API_DAILY_LIMIT_TRADE(9000)·_KAPT(4500)·_REGION(9000),
│   │                                     #        DATA_API_RETRY_MAX_ATTEMPTS(4)·DATA_API_RETRY_BASE_DELAY_MS(1000), APT_TRADE_PROBE_START(2005-01),
│   │                                     #        APT_TRADE_PROVISIONAL_MONTHS(12), APT_TRADE_DAILY_RECHECK_MONTHS(3), APT_LIST_REFRESH_DAYS(30) (R9-3, R9-5)
│   ├── ingestion/datagokr/
│   │   ├── errors.py                     # 신규 — 실패 종류(인증·한도·형식·연결)
│   │   ├── gate.py                       # 신규 — DataGoKrGate: 동시 수 + 자료별 하루 호출 수(보내기 전에 센다) + 사유 22 즉시 멈춤 (R9-5)
│   │   ├── client.py                     # 신규 — 인증키 한 번 인코딩, URL을 남기지 않음, 게이트웨이 오류(XML) → 실패 종류, 백오프+지터 (R9-1)
│   │   ├── trade_parse.py                # 신규 — 상세 실거래 XML → AptTrade: 만원→원, 면적 Decimal, 해제, occurrence, totalCount 검사 (FR-019, R9-4)
│   │   ├── region_parse.py               # 신규 — 법정동코드 → Region: 리 제외, 일반시 아래 구 (R9-3)
│   │   └── kapt_parse.py                 # 신규 — 단지 목록·기본 정보 → ComplexListing·ComplexBasis (R9-3)
│   ├── ingestion/protocols.py            # 변경 — AptTrade·Region·ComplexListing·ComplexBasis, 출처 Protocol
│   ├── db/models.py                      # 변경 — Apt* 9개 (data-model)
│   ├── db/migrations/versions/…_부동산_스키마.py  # 신규
│   ├── repository/
│   │   ├── apt_region.py                 # 신규 — 행정구역 upsert·조회(seen_at·retired_at — 현존 코드만 조회), 목록 상태
│   │   ├── apt_complex.py                # 신규 — 단지 upsert(apt_seq·kapt_code 짝, 합칠 때 merged_into), 세대수·입주년도(move_in_source)
│   │   ├── apt_trade.py                  # 신규 — 거래 upsert(바뀌는 필드만), 사라진 행 표시, 커버리지·확인한 날, 원본, 단지·구분 집계 읽기
│   │   ├── apt_job.py                    # 신규 — 작업·점유·고아 회수(008 deposit_job과 같은 수단)
│   │   ├── apt_usage.py                  # 신규 — 하루 호출 수(한국 시간 날짜)
│   │   └── apt_setting.py                # 신규 — 보유세 기준 비율(기본 0.600000)
│   ├── simulation/
│   │   ├── apt_area.py                   # 신규 — 평형 일곱 구분 경계표와 판정(Decimal) (FR-004)
│   │   ├── apt_price.py                  # 신규 — 그 달 평균(반올림)·시세 창·추정·잠정 (FR-016~FR-018, R9-6)
│   │   ├── apt_tax_rules.py              # 신규 — 시행일별 세법 표(데이터, 근거 조문) 2006-01-01~ (FR-023, R9-7)
│   │   ├── apt_tax.py                    # 신규 — 취득세·중개 보수·재산세(분납)·종부세(부부 5:5), 10원 미만 버림, RuleNotCovered (FR-020~FR-024)
│   │   └── apt_holding.py                # 신규 — 매달 행·보유세 납부 달·요약·taxGaps (FR-025~FR-027, R9-8)
│   ├── api/services/
│   │   ├── realestate_complex_match.py   # 신규 — 단지 목록 ↔ 실거래 단지 짝짓기(법정동 코드 + 지번, 아니면 정규화 이름) (FR-003, R9-3)
│   │   ├── realestate_lists.py           # 신규 — 행정구역·단지 목록 응답, 202·백그라운드 갱신 판정 (FR-002, FR-003, FR-015)
│   │   ├── realestate_collect.py         # 신규 — 실거래 202 판정(받지 않은 달 + 잠정 달 오늘 확인 여부, 확인 실패 시 200) (FR-009~FR-011, FR-014)
│   │   ├── realestate_simulation.py      # 신규 — 입력 검증, 시작 가능 날짜, 매입가, 계산 끝(오늘 KST), 응답 (FR-005~FR-007, FR-029, FR-030)
│   │   └── realestate_series.py          # 신규 — 매달 점, gaps(no_price), estimated·provisional (FR-031)
│   ├── api/routes/
│   │   ├── realestate_regions.py         # 신규 — GET /api/realestate/regions
│   │   ├── realestate_complexes.py       # 신규 — GET /api/realestate/complexes, /complexes/{id}/areas
│   │   ├── realestate_simulation.py      # 신규 — GET /api/realestate/simulation
│   │   ├── realestate_series.py          # 신규 — GET /api/realestate/simulation/series
│   │   ├── realestate_progress.py        # 신규 — GET /api/realestate/progress (SSE)
│   │   └── realestate_settings.py        # 신규 — GET·PUT /api/realestate/settings (FR-034)
│   ├── api/main.py                       # 변경 — 라우터, lifespan 태스크 1개(부동산 수집), 기동 시 고아 점유 회수
│   ├── observability/events.py           # 변경 — apt_collection_* 사건(시·군·구·구간·종류), apt_trade_revised(다시 받기에서 바뀐 거래 — 더함·해제·사라짐 수, 잠정→확정 추적)
│   └── worker/
│       ├── apt_queue.py                  # 신규 — 시작 큐 둘(실거래 · 목록)
│       ├── apt_trade_runner.py           # 신규 — 첫 달 탐색, 쪽 넘김, 원본·거래·커버리지, 잠정 다시 받기·사라진 행, 한도 멈춤 (R9-4, R9-5)
│       ├── apt_list_runner.py            # 신규 — 행정구역(30일), 단지 기본 정보 채우기 (R9-3)
│       └── apt_worker.py                 # 신규 — 앱 수명 태스크 하나, 안에서 두 줄
└── tests/
    ├── contract/fixtures/apt/            # 신규 — 실제 응답(상세 실거래 송파구 2020-01~2023-09·해제 달·2쪽 달, 단지 목록·기본 정보 가락동,
    │                                     #        법정동코드 일부, 사유 30, 빈 결과) + README(받은 날·범위)
    ├── contract/                         # test_datagokr_trade_parse.py, test_datagokr_lists_parse.py, test_datagokr_client.py,
    │                                     # test_datagokr_gate.py, test_apt_fixtures_no_key.py
    ├── unit/                             # apt_area(경계), apt_price(SC-004), apt_helio_reference(SC-003), apt_tax(SC-005), apt_tax_rules(구간 연속),
    │                                     # apt_holding, realestate_complex_match, datagokr_boundaries
    └── integration/                      # 수집·커버리지·잠정·한도·사라진 행, 202 게이트·확인 실패 200, 행정구역·단지·평형 API, 시뮬레이션·시계열,
                                          # SSE, 설정, lifespan(8개), 다른 자산군 수집과 동시

frontend/
├── src/
│   ├── app/realestate/page.tsx           # 신규 — 부동산 화면 (E1)
│   ├── stores/realEstateStore.ts         # 신규 — 지역·단지·평형·매입 입력, 실행·수집 대기·확인 실패 뒤 한 번 다시 요청, 이력 (depositStore를 본뜬다)
│   ├── components/realestate/
│   │   ├── RegionPicker.tsx              # 신규 — 풀다운 셋, 상위 바꾸면 하위 비움, 첫 목록 진행 (E1, E2)
│   │   ├── ComplexPicker.tsx             # 신규 — 단지 풀다운(입주년도·세대수), 기본 정보·실거래 진행, 목록 실패 사유 (E1, E2)
│   │   ├── AreaBucketPicker.tsx          # 신규 — 라디오 일곱(거래 수·비활성), 경계표 (E1)
│   │   ├── RealEstateSimulationForm.tsx  # 신규 — 매입일·매입가(선택, 쉼표)·실행, 409 안내 (E1, E3)
│   │   ├── RealEstateBoard.tsx           # 신규 — 여섯 칸 보드·기준 줄 (E4)
│   │   ├── RealEstateNotice.tsx          # 신규 — 보드 아래 잠정·지금 시세 없음·보유세 계산 불가·확인 실패 줄 (E4)
│   │   ├── RealEstatePerformanceTable.tsx # 신규 — 열 11개, 두 줄 적용 시세·취득 비용, 납부 달만 세금, 내용 폭 (E5)
│   │   └── RealEstateHistory.tsx         # 신규 — 이력·다시 실행(지역까지 맞춤)·비교 (E7)
│   ├── components/stock/PerformanceChart.tsx  # 변경 — estimated 점 표식·범례 (E6)
│   ├── components/stock/CollectingNotice.tsx  # 변경 — 부동산 202·진행 타입(주어·단위는 008의 선택 속성)
│   ├── components/stock/ComparisonChart.tsx   # 그대로
│   ├── components/settings/RealEstateSettingsForm.tsx  # 신규 — 보유세 기준 비율 (E8)
│   ├── app/settings/page.tsx             # 변경 — 부동산 칸 연결
│   ├── components/shell/Sidebar.tsx      # 변경 — 부동산에 /realestate (E1)
│   ├── components/shell/TopBar.tsx       # 변경 — 제목 표에 /realestate "부동산" (FR-001)
│   ├── lib/chartSeries.ts                # 변경 — splitSeriesAtGaps가 no_price를 끊는다
│   ├── lib/types.ts                      # 변경 — 부동산 응답 형식, 결측 사유 no_price, 점의 선택 키 estimated
│   ├── lib/realEstateHistory.ts          # 신규 — 이력(키 assetreplay:realestate-history:v1)
│   └── lib/realEstateProgressStream.ts   # 신규 — /api/realestate/progress 구독
└── tests/                                # 각 변경에 대응. noUnbuiltAssetRoutes.test.ts에서 realestate를 뺀다(승인 필요)
```

**Structure Decision**: 기존 웹 애플리케이션 구조를 그대로 쓴다. 부동산은 다른 자산군과 **같은 층을 나란히** 둔다. 이름은 둘로 나눈다 — 출처·
저장·계산·워커는 다루는 데이터(아파트 매매)를 따라 `apt_`, 화면에 닿는 API 라우트·서비스는 메뉴(경로 `/api/realestate`)를 따라 `realestate_`.
공공데이터포털 어댑터는 새 디렉터리 `ingestion/datagokr/`에 둔다 — 네 자료가 같은 게이트웨이·같은 키·같은 오류 형식을 쓰므로 관문과 클라이언트를
하나로, 자료마다 다른 해석(파서)을 따로 둔다(008의 `ingestion/ecos/`와 같은 모양). 자산군에 무관한 것(차트·비교·매입일 입력·수집 안내·금액
쉼표)만 공유하고, 보드는 칸 구성이 달라 전용으로 둔다.

## 요구사항 추적성

설계 산출물·태스크와의 대응이다. 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (메뉴·제목) | E1, `Sidebar.tsx`, `TopBar.tsx`, `app/realestate/page.tsx`, `noUnbuiltAssetRoutes.test.ts`, tasks T020·T026·T027 |
| FR-002 (행정구역 풀다운·현존 코드만) | R9-3(개편 실측), rest-api `regions`, data-model 1·8절(`retired_at`), `region_parse.py`, `apt_list_runner.py`, `RegionPicker`, E2, tasks T005·T011·T015·T016·T017·T020·T022·T024·T025·T026·T027·T033·T034·T038·T054 |
| FR-003 (단지 목록 — 두 자료 합침·지번·id 안정) | R9-3, rest-api `complexes`(`jibun`·`trades.state`), data-model 2절(`merged_into`), `kapt_parse.py`, `realestate_complex_match.py`, `ComplexPicker`, E2, tasks T005·T011·T014·T016·T017·T020·T022·T023·T025·T026·T027 |
| FR-004 (평형 일곱 구분·경계표) | R9-2, rest-api `areas`, `apt_area.py`, `AreaBucketPicker`, E1, tasks T013·T017·T020·T021·T025·T026·T027·T029 |
| FR-005, FR-006 (매입일·시작 가능 날짜·매입가) | R9-8, rest-api `before_first_trade`·`no_price_at_purchase`·`no_trades_in_area`, `realestate_simulation.py`, `RealEstateSimulationForm`, E3, tasks T017·T032·T033·T034·T037·T038·T039·T040 |
| FR-007 (원화만) | rest-api `currency_not_allowed`, E1, tasks T020·T026·T033·T038·T040 |
| FR-008 (출처·해제 제외·직거래 포함) | R9-1, R9-2, data-model 3절(`cancelled`·`dealing_type`), `apt_price.py`, quickstart 1·8, tasks T001·T004·T011·T015·T024·T028·T029 |
| FR-009 (보관·빠진 구간·원본 분리·고유 키) | R9-4, data-model 3~5절, `apt_trade.py`, `apt_trade_runner.py`, tasks T001·T004·T007·T010·T015·T022·T024 |
| FR-010 (잠정 12개월·최근 3개월 하루 한 번·4~12개월 한 달 한 번·확정 달) | R9-5, data-model 5절·상태 전이, `realestate_collect.py`, `apt_trade_revised` 사건, quickstart 24, tasks T002·T009·T015·T022·T024·T033·T038·T054 |
| FR-011, FR-012 (백그라운드·진행·중복·회수·한도) | R9-5, rest-api 202·SSE, data-model 6·7절, `DataGoKrGate`, `apt_queue`·`apt_worker`·`realestate_progress.py`, quickstart 7·22·25, tasks T002·T006·T007·T009·T012·T015·T016·T017·T018·T019·T020·T022·T024·T025·T026·T027·T033·T038·T054 |
| FR-013 (인증키) | rest-api 출처 절, data-model 4절(URL 없음), `client.py`, `mask_secrets`, quickstart 23, tasks T001·T002·T006·T008·T009·T012·T015·T024·T054 |
| FR-014 (실패 종류·할 일·확인 실패 200) | R9-5, rest-api SSE `failed.kind`·`recheckFailed`, E4·E9, `realestateStore`, quickstart 21, tasks T004·T006·T011·T012·T015·T016·T017·T018·T020·T024·T026·T033·T034·T038·T039·T054 |
| FR-015 (목록 실패 사유) | rest-api `listError`, E2, tasks T005·T016·T017·T020·T025·T026·T054 |
| FR-016~FR-018 (시세 창·추정·잠정) | R9-6, `apt_price.py`, rest-api `rows[].window`·`estimated`·`provisional`, E5·E6, quickstart 12·16, tasks T028·T029·T033·T034·T035·T039·T040 |
| FR-019 (계약일·만원→원·읽기 실패) | R9-1, `trade_parse.py`, 계약 테스트, tasks T001·T004·T011·T015·T040 |
| FR-020~FR-024 (취득 비용·재산세·종부세·세법 표·끝수) | R9-7, data-model 세법 표, `apt_tax_rules.py`·`apt_tax.py`, rest-api `acquisition`·`propertyTax`·`comprehensiveTax`·`taxGaps`·`tax_rule_not_covered`, E3·E4·E5, quickstart 9·11, tasks T003·T030·T031·T032·T033·T034·T036·T037·T038·T040 |
| FR-025~FR-027 (평가·수익·계산 끝·재현성) | R9-8, `apt_holding.py`, rest-api `summary`·`lastPricedMonth`, E4, quickstart 10, tasks T032·T033·T034·T037·T038·T039·T040 |
| FR-028 (표) | E5, `RealEstatePerformanceTable`, rest-api `rows`, quickstart 19, tasks T033·T034·T038·T039·T040 |
| FR-029, FR-030 (보드·가정) | E4, `RealEstateBoard`·`RealEstateNotice`, rest-api `condition`·`summary`, tasks T033·T034·T038·T039·T040 |
| FR-031 (차트) | E6, `realestate_series.py`, `PerformanceChart`(`estimated`), `chartSeries.ts`(`no_price`), quickstart 18, tasks T045·T046·T047·T048·T051 |
| FR-032, FR-033 (이력·비교) | E7, `realEstateHistory.ts`, `RealEstateHistory`, `ComparisonChart`, quickstart 20, tasks T014·T016·T017·T049·T050·T051 |
| FR-034 (설정) | data-model 9절, rest-api 설정, E8, `RealEstateSettingsForm`, quickstart 17, tasks T007·T010·T041·T042·T043·T044·T051 |
| FR-035 (기록 갱신) | README·CLAUDE.md, tasks T052 |
| FR-036 (출처 표시) | E1 출처 줄, README 데이터 출처, R9-1·R9-3, tasks T020·T026·T027·T052 |
| SC-001, SC-002 | R9-11, quickstart 7·10, tasks T027·T040·T054 |
| SC-003 | R9-2, 헬리오시티 참조값 단위 테스트(해제 포함 계산), quickstart 8, tasks T001·T029 |
| SC-004 | R9-6, `apt_price` 단위 테스트, quickstart 12, tasks T028·T040 |
| SC-005 | R9-7, `apt_tax` 참조값 단위 테스트, quickstart 9, tasks T003·T031·T040 |
| SC-006 | 해제 제외·추정/잠정 표시 테스트(API·표·차트·비교), quickstart 16, tasks T015·T029·T032·T033·T034·T040·T045·T046·T049·T054 |
| SC-007 | E2, `RegionPicker` 테스트, quickstart 3·4, tasks T017·T020·T027 |
| SC-008 | 같은 입력 두 번(통합 테스트), quickstart 10, tasks T032·T033 |
| SC-009 | 시계열 통합 테스트, quickstart 18, tasks T045·T051 |
| SC-010 | 표 폭 테스트, quickstart 19, tasks T034·T040 |
| SC-011 | 원본·사건·실패 사유 검사, 픽스처 키 검사, quickstart 23, tasks T006·T008·T015·T054 |
| SC-012 | `DataGoKrGate` 계약 테스트, 한도 통합 테스트, quickstart 22, tasks T006·T012·T015·T054 |
| SC-013 | 자동 검사(전체 테스트), tasks T053 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-------------|------------------------------|
| **원칙 V의 "(자산 식별자, 날짜) 복합 유니크 키"를 거래 사건에 맞춘다** — 키 = (시·군·구, 계약일, 단지 일련번호, 동, 층, 전용면적, 금액, 응답 안 순번)(R9-4) | 실거래는 일별 시계열이 아니라 비정기 **사건**이다. (단지, 계약일)로는 같은 날 여러 거래가 하나로 합쳐져 거래 건수와 평균이 틀린다. 실측에서 모든 필드가 같은 거래도 232쌍 있었다 — 순번 없이는 둘 중 하나를 잃는다(FR-009 실패 양상) | (단지, 계약일) 키는 거래를 잃는다. 출처의 거래 고유 ID는 없다. 행 전체 해시는 해제 표시가 붙을 때 다른 행이 되어 같은 거래가 둘로 늘어난다 — 바뀌는 필드는 키에서 빼고 upsert로 고친다. 멱등성·재개 가능성(원칙 V의 목적)은 그대로 지킨다 |
| **시세 창을 넓혀 결측 달의 시세를 정한다**(1 → 36개월, R9-6) | 아파트는 같은 단지·같은 평형이라도 거래가 없는 달이 흔하다 — 그 달의 시세가 없으면 평가·보유세가 대부분의 달에서 멈춘다. 사용자가 명세 입력에서 정한 규칙이다 | 원칙 V가 금지하는 것은 **임의** 보간·전일 값 복사다. 이 규칙은 명세에 정의되고(FR-016), 결과에 창·건수·추정을 별도 필드로 드러내며(FR-017), 저장하지 않는다 — 원칙 V의 "보정은 규칙을 문서화하고 별도 컬럼으로 표시"를 따른다. 36개월 밖은 시세 없음으로 멈춘다. 시세 없음 달마다 계산을 멈추는 안은 대부분의 단지에서 결과가 나오지 않는다 |
| **세법 표가 크다** — 2006년부터 취득세·중개 보수·재산세·종부세의 시행일별 규칙(R9-7) | 사용자 결정(연도별 세법). 한 해의 세율로 20년을 계산하면 2021~2022 종부세처럼 크게 다른 해가 조용히 틀린다(FR-023 실패 양상) | 현행 세법 하나 — 사용자가 기각했다. DB 테이블 — 근거 조문을 코드 리뷰로 검토하기 어렵고 바꿀 때 마이그레이션이 든다. JSON — mypy를 받지 못한다. 표를 데이터 모듈 하나에 두고, 구간이 비거나 겹치지 않음과 경계 해의 참조값을 테스트로 묶는다 |
| **공유 차트에 선택 키·사유를 더한다** — 결측 사유 `no_price`, 시계열 점의 `estimated`(R9-10) | 시세 없음은 끊고 추정 점은 실측과 구별해야 한다(FR-031, 헌법 원칙 V) | 부동산 전용 차트는 축 쉼표·끊기·두 축·잠정 색 규칙이 두 벌이 된다(007 R7-14가 막은 실패). 둘 다 선택이고 다른 자산군의 응답에는 없어 지금과 같다 — 005~008 차트 테스트가 회귀 검사다 |
