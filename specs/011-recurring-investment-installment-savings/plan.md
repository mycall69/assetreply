# Implementation Plan: 주식·가상자산 적립식 투자, 예금 정기 적금, 주식 매도 세금 설정

**Branch**: `011-recurring-investment-installment-savings` | **Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-recurring-investment-installment-savings/spec.md`

## Summary

기존 세 화면의 투자 방식을 넓히고, 주식 매도 세금을 설정으로 드러낸다.

- **주식·가상자산 적립식**: 시작일에 맞춘 주기(매일·매주·매달·매년)로 일정액을 넣는다. 휴장·결측이면 다음 거래일로 미룬다.
  - 주식: 정수 주식만 사고, 1주에 못 미치면 매수 대기금에 모은다. 세후 배당은 배당 현금에 들어오고, 재투자 켬이면 재투자일(배당락일 뒤 둘째 거래일)에 매수 대기금으로 옮겨 산다 — 그 전의 정기 매수는 배당을 쓰지 않는다(분석 B1).
  - 가상자산: 소수 8자리 수량으로 산다.
  - 원화 원금으로 외화 자산을 사면 납입마다 그날 환전한다.
  - 보드는 기준일에 모두 판다고 가정해 총 납입 원금, 매매 수수료 총액, 세금 총액, 투자 수익·수익률(단순)을 보인다.
- **정기 적금**: 1년 만기 적금에 매달 붓는다. 만기 금액은 1년 정기예금에 넣고, 같은 날 새 적금을 붓는다. 1년 뒤에는 두 만기 금액을 합쳐 다시 정기예금에
  넣는다(풍차).
  - ECOS 적금 금리는 **시중은행·상호금융에만** 있다(실측 — research R11-1).
- **주식 매도 세금 설정**: 국내 매도 세율(0.20%), 해외 양도소득세율(22%), 해외 연간 기본공제(2,500,000원)를 설정으로 둔다.
  - 010 반복 4의 시행일별 법령 표를 대체한다(명확화).
  - 기본 설정이면 일시금 보드의 응답이 문자열까지 같다.

새 출처는 없다. 계산은 새 순수 모듈 다섯이고, 일시금·정기예금 계산(`reinvest.py`·`crypto_hold.py`·`deposit_rollover.py`)은 고치지 않는다. 경로는
일시금과 따로 둔다(R11-10). DB 변경은 `stock_setting`의 열 셋뿐이다. 적금 금리는 008의 저장·수집 경로에 새 금리 계열 키로 담는다(R11-2).

**설계 중 확인한 것**:

| 확인 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| ECOS 적금 항목 (2026-10-06 실측) | 가중평균 수신금리 표는 `121Y002`·`121Y004` 둘뿐이다. 적금은 예금은행 `정기적금`·`(1-2년)`·`(3-4년)`, 상호금융 `정기적금`·`(3년만기)`뿐이다. 1년 항목은 없다. 저축은행·신협·새마을금고에는 적금이 없다 | 시중은행 = 정기적금(1-2년) 2003-01~, 상호금융 = 정기적금(만기 구분 없음) 2012-01~. 셋은 적금에서 고를 수 없다. spec FR-029를 고쳤다(R11-1) |
| 일시금의 첫 매수일 | 주식은 시작일 이후 첫 거래일(`prices(start, end)`)이고, 가상자산은 **시작 월의 첫 일봉**(`start.replace(day=1)`)이다 | 적립식은 둘 다 시작일 기준이다(명확화). 가상자산은 일시금과 첫날이 다를 수 있음을 Assumptions에 밝혔다 |
| 예금 저장의 키 | 다섯 테이블·큐·잠금·진행이 모두 `institution`(`String(24)`) 하나로 가른다. 스키마 테스트가 기본 키를 고정한다 | 적금은 새 금리 계열 키 `{inst}_isav`다 — 스키마 변경 없음(R11-2) |
| 예금 항목 해석 테스트 | `Test투자처_항목`이 `INSTITUTIONS`와 통계표별 결과를 정확히 고정한다 | 적금 계열은 따로 된 표·해석 함수(기존 결과 불변) |
| 일시금 화면 테스트 | `stockStoreRerun.test.ts`가 조회 문자열과 `input` 다섯 칸을 정확히 비교한다 | 방식·주기는 `plan` 칸(입력 밖)이고, 적립식은 따로 된 경로다(R10-10 → R11-10·R11-11) |
| 주식 설정 PUT | 세 값을 **모두** 요구한다(빠진 값을 기본값으로 채우지 않는다) | 매도 세금은 따로 된 경로 `/api/stocks/settings/sale-tax`(부동산 거주 비율과 같은 방식) |
| 010 반복 4 응답의 문자열 | 통합 테스트가 `taxRate: "0.0020"`·`"0.22"`·`deduction: "2500000"`을 정확히 비교한다 | 기본값 상수를 같은 자릿수로 둔다 — 기본 설정의 응답이 바뀌지 않는다(R11-7) |
| 차트 테스트의 선 개수 | `toHaveLength(2)` 등 선 개수를 정확히 센다 | 누적 납입 원금 선은 점에 `principal`이 있을 때만 그린다(R11-12) |
| 가드 테스트 | 주석까지 "전일 값"·"이전 값"·"직전 값"·fill 계열을 찾는다(`test_no_interpolation`). 날짜 리터럴은 허용 목록 모듈만이다(`test_no_hardcoded_dates`). ECOS 응답 키는 어댑터 밖에서 금지다(`test_layer_boundaries`) | 새 모듈 주석에 금지 낱말을 쓰지 않는다. 가상자산 과세 시행일은 `crypto_sale_cost.py`(허용 목록 변경 — 승인 필요) |
| 가상자산 과세 (웹, 2026-10-06) | 2027-01-01 이후 양도분부터 22%·연 250만 원 공제다. 2026년 세제개편안에 추가 유예가 없다 | 기준일 2027-01-01 전이면 세금 0, 그 뒤면 비움(R11-7) |

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async, aiohttp — 새 의존 없음 |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) — `stockStore.plan·recurring`, `cryptoStore.plan·recurring`, `depositStore.product·installment` |
| 차트 | lightweight-charts 5.2.1 — `addSeries`·`setData`만(새 API 없음). 누적 납입 원금 점선 |
| DB | MySQL 8 — 마이그레이션 1개(`stock_setting` 열 셋, `down_revision = "e3b9c4d27f61"`). 예금 테이블은 그대로(새 계열 키 값만) |
| 출처 | 새 출처 없음. ECOS 새 항목 둘(`BEABAA2122`·`BEBB0200`) — 같은 인증키·관문(`EcosGate`)·호출 한도 |
| 테스트 | pytest·pytest-asyncio(단위·계약·통합), Vitest·RTL. ECOS 적금 응답은 저장된 본문 픽스처(`tests/contract/fixtures/deposit/` — URL 없음) |
| 타입·린트 | mypy strict, ruff(`--no-cache`) / tsc(테스트 포함), eslint |
| 계산 | 새 순수 모듈 다섯(`contribution_schedule`·`recurring_stock`·`recurring_crypto`·`installment_ladder`·`crypto_sale_cost`) + `stock_sale_cost` 인자화. 모두 `Decimal` |
| 성능 목표 | 매일 적립 20년(약 5,000회)의 표 첫 쪽·시계열이 각각 3초 안(SC-008). 계산은 일봉 한 번 훑기, 표는 커서 페이지, 시계열은 LTTB |
| 제약 | 백엔드 단일 워커. 테스트는 네트워크 없이 통과한다(원칙 III). 일시금·정기예금 결과 불변(FR-039). 화면은 계산하지 않는다(`noClientSideFinance`) |
| 규모 | 새 경로 7(적립식 2×2, 적금 2, 세금 설정 1) + 투자처 목록 키 더함. 새 화면 부품 약 8. 스토어 3, 이력 3 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 새 I/O는 008 수집 경로(비동기 aiohttp·관문)와 기존 비동기 저장소 읽기뿐이다. 계산은 순수 함수다 |
| II. 데이터 소스 격리 | ✅ | 새 출처 없음. 적금 항목 ↔ 계열 키 대응은 ECOS 어댑터 안에만 둔다(`INSTALLMENT_SERIES`). ECOS 응답 키는 어댑터 밖에 나가지 않는다(`test_layer_boundaries`). 호출 한도·재시도·관문은 008 설정 그대로다. 약관 — 008 R8-2(자유 이용, 출처 표시)가 같은 통계표에 그대로 적용되고, 화면 출처 줄은 지금과 같다. 005·007·010의 기록된 이탈은 범위가 넓어지지 않는다(같은 시세) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 순수 모듈 다섯의 참조값 단위 테스트(손계산 — quickstart 2), ECOS 적금 응답 계약 테스트(저장 본문), 경로 통합 테스트(202·409·400·200), 화면·스토어 테스트를 먼저 커밋하고 최초 실패를 확인한다. 구현 뒤 실패하면 멈추고 보고한다(006 D2). 실행 주체(방식 라디오 → 스토어 → 경로)는 실제로 눌러야 통과하는 테스트와 짝짓는다(006 D1). **기존 검사 변경 셋은 구현 때 승인을 받는다**(아래 설계 후 재평가) |
| IV. 모듈화 | ✅ | 계산은 `simulation/`의 순수 함수다(DB·HTTP 없음 — `test_layer_boundaries`). 서비스는 읽어 넘긴다. 일시금 모듈을 고치지 않고 부품(`buy_quantity`·`spend_for`·`buy_fraction`·`apply_split`·`quantize_rate`·`evaluate_krw`·`exchange_rate`·`to_foreign`·`to_principal`·`resolve_rate`, 008 이자 함수)을 함께 쓴다 |
| V. 정합성·재현성 | ✅ | 휴장·결측일의 납입은 다음 거래일로 미루고 원래 날짜를 싣는다 — 다른 날의 가격을 쓰지 않는다. 계산 끝 뒤로 미뤄진 납입은 넣지 않는다(R11-3). 적금 미발표 달은 잠정(저장하지 않음)이고 결측 달은 멈춘다(008). 확정 환율만 쓰고 고시일을 싣는다. 가상자산 과세 시행 뒤는 세금을 비운다(0으로 메우지 않음). 재현성: 결과는 입력·설정·데이터의 함수다(저장 안 함) |
| VI. 금융 정확성 | ✅ | `Decimal`만 쓴다(`test_no_float`). 세율·공제는 설정으로 드러낸다(원칙 VI "명시적 파라미터"). 계산식마다 손계산 참조값 테스트가 있다(SC-001). DB 열은 `SPREAD`·`WON`(DECIMAL)이다. API 경계는 문자열이다 |
| VII. UI·진행 | ✅ | Zustand. 진행은 기존 SSE(주식·가상자산·예금 진행 스트림)다. 차트는 Lightweight Charts이고 시계열은 LTTB(최대 2,000점)이며, 표는 커서 페이지(매일 20년 약 5,000행) |
| VIII. 한국어 | ✅ | 문서·주석·커밋 한국어 |
| IX. MVP·자산군 순서 | ✅ | 새 자산군이 아니다. 기존 세 자산군 화면의 확장이고, 스토리마다 계산·경로·화면까지 완결한다(US1~US4) |
| DB 운영 규약 | ✅ | Alembic 리비전 하나(열 셋 추가, NULL 허용 — 기존 행 그대로). ORM만 쓰고 방언 문법은 `db/dialect.upsert`뿐이다 |
| 크로스 플랫폼 | ✅ | 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 설계 중 바뀐 요구(FR-004 계산 끝 뒤 납입, FR-014·FR-032 같은 날 행, FR-028 경과 평가 식, FR-029 투자처·항목, Assumptions)를 spec에 같은 작업 단위로 반영했다. 모든 FR·SC는 아래 추적성 표의 설계에 연결되고, `/speckit-tasks`가 태스크 번호를 채운다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 일시금·정기예금 불변 | ✅ | 일시금 경로·계산 모듈을 고치지 않는다. 주식 보드의 세율만 설정에서 오며, 기본값이 문자열까지 같다(R11-7). 공유 차트·이력은 키가 있을 때만 달라진다 |
| 조용히 빠지는 전달 | ✅ | 납입 목록·재투자 지연·세율은 기본값 없는 필수 인자다(빠뜨리면 타입 오류). 이력의 빠진 칸은 다시 실행이 기본값으로 채운다 — `undefined`가 입력이 되지 않는다 |
| 다른 곳에서 일어남 | ✅ | 배당이 매수에 섞이지 않게 돈의 칸을 둘로 둔다 — 재투자 끔은 계속, 재투자 켬은 재투자일까지 배당 현금이다(R11-4, SC-004, 분석 B1). 매일·매주 적립의 다음 매수가 재투자일보다 먼저 배당을 쓰지 않는다. 정기예금의 첫 달을 적금의 시작 가능 날짜로 내지 않는다(R11-9). 계열 키가 화면·API로 새지 않는다(R11-2) |
| 늦게 일어남 | ✅ | 적금은 두 계열을 함께 수집에 건다 — 하나 끝난 뒤 다른 하나를 그제야 거는 대기가 없다(R11-9). 가상자산 과세 시행일이 오면 보드가 "세법 미반영"으로 바뀐다 — 조용히 0이 아니다 |
| 공유 부품 변경 | ✅(기록) | `PerformanceChart`(키 있을 때만 점선 하나), `chartHover`(필드 둘 — `principal`·`depositRate`), 이력 셋(선택 칸), `InstitutionPicker`(비활성 항목)다. 기존 테스트는 바꾸지 않고 통과해야 한다 |
| **바뀌는 기존 테스트** | ⚠ 승인 필요(구현 때) | research R11-7의 셋이다. 모두 명확화(설정이 표를 대체)에서 나온다. ① `tests/unit/test_stock_sale_cost.py` — 시행일 표·표 밖 검사를 세율 인자 검사로 바꾼다(버림·공제·손실 기대값은 그대로). ② `test_stock_sale_cost_api.py::test_세율_표_밖_기준일은_세금을_비운다` — 2021 기준일도 설정 세율로. ③ `test_no_hardcoded_dates.py` `_LEGAL_DATE_MODULES` — `stock_sale_cost.py` → `crypto_sale_cost.py`. 그 밖의 기존 테스트는 고치지 않는다 |

## Project Structure

### Documentation (this feature)

```text
specs/011-recurring-investment-installment-savings/
├── spec.md              # /speckit-specify, /speckit-clarify (명확화 5) + plan 설계 중 고친 요구
├── plan.md              # 이 파일
├── research.md          # R11-1 ~ R11-14 (ECOS 적금 실측 포함)
├── data-model.md        # stock_setting 열 셋, 금리 계열 키, 순수 계산의 입출력, 이력·스토어 칸
├── quickstart.md        # 품질 게이트, 참조값, API·브라우저 검증
├── contracts/
│   ├── rest-api.md      # 새 경로 7, 투자처 목록 키, 세금 설정
│   └── ui-wireframes.md # 폼·보드·표·차트·이력·예금 상품·설정
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/simulation/
│   ├── contribution_schedule.py   # (신규) 예정일·실제 납입일·미뤄짐, 납입마다 환전·원화 분모(R11-3·R11-5)
│   ├── recurring_stock.py         # (신규) 주식 적립식 — 매수 대기금·배당 현금·정수 매수·재투자(R11-4)
│   ├── recurring_crypto.py        # (신규) 가상자산 적립식 — 소수 8자리(R11-6)
│   ├── installment_ladder.py      # (신규) 적금 → 정기예금 사다리(R11-8)
│   ├── crypto_sale_cost.py        # (신규) 가상자산 매도 수수료·과세 시행일 규칙(R11-7 — 법령 날짜 모듈)
│   ├── stock_sale_cost.py         # (변경) 시행일 표 제거 — 세율·공제를 인자로
│   └── deposit_rollover.py        # (변경 — 이름만) 금리 해석기를 공개 이름으로(동작 불변)
├── src/ingestion/ecos/
│   ├── installment_items.py       # (신규) INSTALLMENT_SERIES·resolve_installment_items(알려진 코드 + 이름 패턴)
│   └── deposit_client.py          # (변경) items_for(key)가 적금 계열 키도 안다(통계표 항목 캐시 공유)
├── src/repository/stock_setting.py   # (변경) SaleTaxSettings·get_sale_tax·save_sale_tax(기존 함수 불변)
├── src/db/models.py · src/db/migrations/versions/*_주식_매도_세금_설정.py   # StockSetting 열 셋
├── src/api/services/
│   ├── stock_recurring.py         # (신규) 읽기 → 일정·환전 → 계산 → 원화 평가·매도 비용·페이지
│   ├── crypto_recurring.py        # (신규) 같음(가상자산)
│   ├── deposit_installment.py     # (신규) (투자처, 상품) → 계열 키, 두 계열 판정·시작 가능 날짜, 계산
│   ├── recurring_series.py        # (신규) 적립식·적금 시계열 조립(점 principal·depositRate)
│   ├── stock_sale.py              # (변경) 설정 세율로 — sale_cost_for(…, sale_tax)
│   └── stock_simulation.py        # (변경) Prepared에 매도 세금 설정
├── src/api/routes/
│   ├── stock_recurring.py · crypto_recurring.py · deposit_installment.py   # (신규) 경로와 /series
│   ├── stock_settings.py          # (변경) GET/PUT /settings/sale-tax 추가
│   ├── stock_simulation.py        # (변경) summary_json이 설정 세율을 넘긴다
│   └── deposit_institutions.py    # (변경) 투자처마다 installment 객체
├── src/api/errors.py · src/api/main.py   # InstallmentNotAvailable(400) 처리기, 새 라우터 등록
└── tests/
    ├── unit/          # 새 순수 모듈 다섯의 참조값·불변식, stock_sale_cost(승인 뒤 변경)
    ├── contract/      # ECOS 적금 항목 해석·시계열 파싱(fixtures/deposit/ 새 본문 둘)
    └── integration/   # 새 경로 7·투자처 목록·세금 설정·일시금 보드의 설정 반영
                       # deposit_support.py(공유 보조) — 적금 계열의 SERIES·스텁을 더하기만(기존 값 그대로)

frontend/
├── src/lib/
│   ├── types.ts                   # Frequency, Recurring*·Installment* 응답, SaleTaxSettings, SimulationPoint.principal·depositRate
│   ├── simulationHistory.ts · cryptoHistory.ts · depositHistory.ts   # 선택 칸·식별자(R11-11)
│   ├── recurringText.ts           # (신규) 주기 안내 문장(날짜 계산 없음 — 요일·날짜 이름만)
│   └── chartHover.ts              # principal·depositRate 줄
├── src/components/
│   ├── recurring/InvestmentModeFields.tsx   # (신규) 투자 방식 라디오 + 주기 선택 + 안내
│   ├── recurring/RecurringBoard.tsx         # (신규) 다섯 칸(주식·가상자산)
│   ├── recurring/RecurringStockTable.tsx · RecurringCryptoTable.tsx   # (신규)
│   ├── deposit/ProductPicker.tsx            # (신규) 정기예금 | 정기 적금
│   ├── deposit/InstitutionPicker.tsx        # (변경) 적금이면 고를 수 없는 투자처 비활성 + 사유
│   ├── deposit/DepositSimulationForm.tsx    # (변경) 선택 속성 principalLabel("월 납입액") — 기본은 지금 문구
│   ├── stock/SimulationForm.tsx             # (변경) 선택 속성 principalLabel("한 번 납입액") — 기본은 지금 문구
│   ├── deposit/InstallmentBoard.tsx · InstallmentTable.tsx   # (신규)
│   ├── settings/StockSaleTaxForm.tsx        # (신규)
│   ├── stock/PerformanceChart.tsx           # (변경) principal 키가 있으면 점선
│   └── stock/SimulationHistory.tsx · crypto/CryptoHistory.tsx · deposit/DepositHistory.tsx   # 방식 표기
├── src/stores/stockStore.ts · cryptoStore.ts · depositStore.ts   # plan/product, recurring/installment, 다시 실행·비교
├── src/app/{stocks,crypto,deposit,settings}/page.tsx
└── tests/             # 새 파일 — 폼·보드·표·차트 키·이력·스토어·설정

CLAUDE.md · README.md   # 현재 상태 표에 011, 적금 계열 키·세금 설정 주의
```

**Structure Decision**: 기존 웹 앱 구조(backend/frontend) 그대로다. 적립식·적금은 **따로 된 계산 모듈·경로·화면 부품**으로 두고, 공유 부품(차트·이력·투자처
라디오)은 키가 있을 때만 달라진다. 일시금·정기예금의 검증된 경로(참조 구현 대조, 010 응답 비교)를 흔들지 않기 위해서다(R11-4·R11-10).

## 요구사항 추적성

설계 산출물·태스크와의 대응이다(F*n* = contracts/ui-wireframes.md §*n*). 모든 FR·SC가 하나 이상의 태스크에 참조된다(tasks.md) — 참조하는 태스크가 없는 FR·SC가 남으면 헌법 명세 작성 규약 위반이다.

| 요구사항 | 설계 |
|----------|------|
| FR-001 (투자 방식 선택·일시금 불변) | R11-10·R11-11, data-model 4, F1, quickstart 3·4-1, tasks T018·T022·T023·T027·T028·T029 |
| FR-002 (주기·납입액 검증, 추가 조건 없음) | R11-10, rest-api 1·2(`frequency`·`amount`), data-model 3, F1, tasks T012·T015·T018·T025·T027·T034·T038 |
| FR-003 (시작일에 맞춘 예정일) | R11-3, data-model 2.1, F1 안내, quickstart 2, tasks T004·T010·T017·T027 |
| FR-004 (미루기·합치기·계산 끝 뒤) | R11-3, data-model 2.1(`assign`·`pending_after_end`), rest-api `deferred`·`pendingAfterEnd`, quickstart 2, tasks T004·T010·T015·T025 |
| FR-005 (총 납입 원금·원화 분모) | R11-5, data-model 2.1(`basis_krw`), rest-api `contributedKrw`, tasks T004·T010·T015·T025 |
| FR-006·FR-007 (정수 매수·매수 대기금) | R11-4, data-model 2.2 불변식, quickstart 2·4-2, tasks T014·T024 |
| FR-008 (재투자 켬·끔, 배당 현금) | R11-4, data-model 2.2, quickstart 2, tasks T014·T024 |
| FR-009 (분할) | R11-4(하루 순서 (0)), tasks T014·T024 |
| FR-010 (납입마다 환전) | R11-5, rest-api `exchangeRate`, quickstart 2·3-2, tasks T004·T010·T014·T015·T024·T025 |
| FR-011 (행 평가·수익률 분모) | R11-4, data-model 2.2, rest-api 행, tasks T014·T015·T024·T025 |
| FR-012 (적립식 보드·단순 수익률·도움말) | R11-7, rest-api 1 `summary`, F2, quickstart 3-1, tasks T015·T019·T023·T025·T027·T029 |
| FR-013 (매도 세금·해외 공제 원화) | R11-7, data-model 2.4, rest-api 5, tasks T009·T011·T015·T025 |
| FR-014 (주식 표) | R11-4(행 종류), F3, quickstart 4-1·4-3, tasks T014·T015·T020·T023·T024·T027·T029 |
| FR-015 (누적 납입 원금 선) | R11-12, rest-api `/series` `principal`, F5, tasks T006·T007·T012·T013·T016·T023·T026·T029 |
| FR-016·FR-021 (수집 판정 일시금과 같음) | R11-10, rest-api 1·2, tasks T015·T016·T022·T025·T026·T034·T038 |
| FR-017~FR-019 (가상자산 적립식) | R11-6, data-model 2.3, rest-api 2, F4, tasks T004·T006·T010·T013·T031·T034·T035·T036·T037·T038·T039 |
| FR-020 (가상자산 매도 비용·과세 시행일) | R11-7, data-model 2.5, rest-api 2 `saleCost`, F2, quickstart 3-4·4-4, tasks T019·T032·T033·T034·T036·T037·T038·T039 |
| FR-022·FR-023 (예금 상품·적금 입력) | R11-11, rest-api 3, F7, tasks T012·T043·T045·T048·T049 |
| FR-024·FR-025 (적금 일정·단리 이자) | R11-8, data-model 2.6, quickstart 2, tasks T041·T043·T047·T048 |
| FR-026·FR-027 (만기 → 정기예금 + 새 적금, 정기예금 계산) | R11-8, data-model 2.6, rest-api 3 `contracts`·`deposits`, quickstart 3-5, tasks T041·T043·T047·T048 |
| FR-028 (경과 평가) | R11-8(식), data-model 2.6, tasks T041·T043·T047·T048 |
| FR-029 (적금 금리 항목·고를 수 있는 투자처·시작 가능 날짜) | R11-1·R11-2·R11-9, rest-api 3·4, F7, quickstart 1·3-5·3-6, tasks T003·T040·T043·T044·T045·T046·T048·T049 |
| FR-030 (잠정·결측·수집) | R11-8·R11-9, rest-api 3(202·409), tasks T041·T042·T043·T046·T047·T048 |
| FR-031·FR-032 (적금 보드·표·차트) | R11-12, rest-api 3, F5·F8, tasks T006·T007·T013·T043·T044·T045·T048·T049 |
| FR-033·FR-034 (이력·비교) | R11-11, data-model 3, F6, quickstart 4-6, tasks T021·T022·T023·T028·T036·T039·T045·T049·T055 |
| FR-035·FR-036 (세금 설정·검증) | R11-7, data-model 1.1, rest-api 5, F9, quickstart 3-7·4-7, tasks T005·T011·T012·T051·T052·T053·T054 |
| FR-037·FR-038 (설정이 표를 대체·보유 중 값 불변) | R11-7, rest-api 5 끝, F2a, 설계 후 재평가(바뀌는 기존 테스트), tasks T005·T008·T009·T011·T051·T052·T054 |
| FR-039 (일시금·정기예금·부동산·외환 불변) | 설계 후 재평가, quickstart 3-3·4-6, tasks T001·T011·T060 |
| SC-001 (참조값 0건) | quickstart 2, tasks T014·T030·T031·T041·T050 |
| SC-002 (납입 합계) | R11-3, quickstart 2, tasks T004·T014·T015·T030·T031·T034 |
| SC-003 (살 수 있는데 안 삼 0) | data-model 2.2 불변식, tasks T014·T030 |
| SC-004 (배당 현금 매수 0) | data-model 2.2 불변식, tasks T014 |
| SC-005 (노는 돈 0원·새 적금) | R11-8, quickstart 2·3-5, tasks T041·T043·T050 |
| SC-006 (불변) | quickstart 3-3·4-6, tasks T001·T002·T021·T030·T050·T055·T059·T060 |
| SC-007 (설정 반영·검증·되돌리기) | quickstart 3-7·4-7, tasks T051·T052 |
| SC-008 (3초) | R11-14, quickstart 3-8, tasks T056 |
| SC-009 (1분 입력) | F1·F7, quickstart 4-8, tasks T018·T019·T027·T045·T057 |
| SC-010 (1440px) | R11-13, F3·F4, quickstart 4-3, tasks T020·T027·T030 |

## Complexity Tracking

헌법 이탈이 없다 — 기록할 이탈 없음.

기록할 만한 설계 선택은 셋이다. 모두 원칙을 지키는 쪽이다.

- **금리 계열 키(R11-2)**: 예금 테이블의 `institution` 열이 "투자처"에서 "금리 계열"로 뜻이 넓어진다. 대신 008의 수집 경로를 그대로 쓴다.
- **법령 날짜 모듈 교체(R11-7)**: 날짜 하드코딩 가드의 허용 목록을 바꾼다(승인 필요). 출처의 시작일이 아니라 법령 시행일이다.
- **일시금과 따로 된 경로(R11-10)**: 경로 수가 늘지만 일시금의 응답 모양과 기존 테스트가 그대로다.
