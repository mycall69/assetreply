# Research: 013 — 투자 비교

**Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Technical Context에 "NEEDS CLARIFICATION"으로 남은 항목은 없다. 아래는 코드베이스 조사(2026-10-08 — 백엔드 경로·프론트엔드 부품·저장과 테스트 기반)에서 나온
사실과 그에 따른 설계 결정이다. 줄 번호는 조사 시점의 것이다.

## 조사에서 확인한 사실

| 확인 | 결과 |
|------|------|
| 계산 경로의 짜임 | 일곱 경로(주식 일시금·적립식, 가상자산 일시금·적립식, 정기예금, 정기 적금, 부동산)가 모두 "수집 판정 → `prepare`(서비스) → 요약 JSON → 시계열 빌더"다. 수집 판정과 `prepare`는 서비스 함수다. 요약 JSON 함수는 주식 일시금·가상자산 둘·예금 둘이 **경로 모듈**에, 주식 적립식·부동산이 서비스에 있다 |
| 표와 시계열 | 메뉴는 표 경로와 `/series` 경로를 따로 불러 **계산을 두 번** 한다. `prepare` 한 번으로 요약과 시계열을 함께 만들 수 있다 |
| 거절 본문 | 거절은 모두 예외이고, 예외 → 본문 변환은 `create_app()` 안의 처리기 클로저에만 있다(`api/main.py:205-424`). 따로 꺼내 쓸 도우미가 없다 — **같은 예외를 그대로 올리는 경로**면 같은 본문이 나온다 |
| 202 본문 | 주식 `{status, market, symbol, jobId?, progressUrl?, fx?}`, 가상자산 `{status, coinId, jobId?, progressUrl?, fx?}`, 예금 `{status, institution, jobId, progressUrl, series?}`, 부동산 `{status, kind:"trade", lawdCd, jobId, monthsDone, monthsTotal, progressUrl}` |
| 진행 스트림 | 네 자산군 모두 SSE이고 처리기 모양이 같다(`onSnapshot`·`onCompleted`·`onFailed` — `lib/*ProgressStream.ts`). 환율은 `lib/collectionStream.subscribeCollection(currency)`. 스토어마다 구독 해제가 **모듈 수준 하나**라 대상 하나만 구독한다 |
| 세션 | 요청마다 `AsyncSession` 하나(`db/session.get_session`). 한 세션을 여러 태스크가 함께 쓸 수 없다 — 대상 열을 한 요청에서 동시에 계산하려면 세션을 따로 열어야 한다 |
| 이력 쓰기 | 계산 경로는 이력을 쓰지 않는다. `simulation_history`를 쓰는 곳은 `api/services/history.py`뿐이고, 화면의 `saveHistoryFlow`(`lib/historyFlow.ts:84-93`)가 일곱 호출 지점(스토어의 `run` 계열)에서 부른다 |
| 비용 합계 — 있는 것 | 주식 적립식 `buyFeeTotal`·`dividendTaxTotal`·`saleCost`, 가상자산 적립식 `buyFeeTotal`·`saleCost`, 부동산 `acquisition.total`·`holdingTaxTotal`·`saleCost.total` |
| 비용 합계 — 없는 것 | 주식 일시금: 매수 수수료(재투자 매수 포함)·배당 소득세는 행에만 있다(`Row.trade_fee`·`Row.dividend_tax` — 종목 통화, 버림 전). 가상자산 일시금: 매수 수수료는 매수 행에만, **매도 비용이 없다**(012 US5 보드는 네 칸). 정기예금: 끝난 회차의 세금은 `terms[].tax`에, 진행 중 회차의 경과 이자 세금은 `simulate_deposit` 안에서 빼고 내놓지 않는다(`deposit_rollover.py:265`). 정기 적금: `taxTotal`은 만기분만이고 진행 중 계약의 경과 세금은 평가액에 녹아 있다 |
| 보드의 주 값 | 주식 일시금 `PerformanceBoard.tsx:50` — 매도 후 값이 있으면 그것, 없으면 보유 중. 부동산 `RealEstateBoard.tsx:44` — `after?.profit ?? summary.profit`. 적립식 `RecurringBoard.tsx:73` — 매도 후 값, 비면 "—". 가상자산 일시금·예금 — 보유 중 |
| 시계열의 끝 | 주식 일시금·적립식 시계열은 **행 날짜**(월 첫 거래일·사건 날)에만 점이 있어 기준일이 점이 아닐 수 있다. 가상자산(일봉)·예금·부동산 시계열은 기준일 점이 있다 |
| 가상자산 세금 | 적립식 매도 세금은 과세 시행일(2027-01-01) 전 기준일이면 0(`not_yet_taxed`), 그 뒤면 비운다(`outside_rules` — `tax`·`total`·`profitAfterSale`·`returnRateAfterSale`이 `null`) |
| 환율 찾기 | `simulation/fx_convert.resolve_rate:79-102` — 그날 고시가 없으면 **모든 날짜를 훑는다**(O(N)). 가상자산은 1년 365일이고 원화 고시는 약 250일이라 약 30%가 빗나간다. 일봉 시계열(`daily=True`)·매일 적립에서 대상 하나에 수백만 번 비교가 된다 — 10개 비교의 가장 느린 길 |
| 주식 등록 | 검색이 고른 것은 `StockChoice`이고 종목 식별은 `POST /api/stocks/selection` 응답이 정한다. 본문을 만드는 `selectionBody`(`stockStore.ts:208-214`)는 내보내지 않는다 |
| 검색 부품 | `StockSearch`·`CoinSearch`는 스토어 결합 없이 따로 쓸 수 있다. `InstitutionPicker`는 라디오(값 하나)다. 부동산 `RegionPicker`·`ComplexPicker`·`AreaBucketPicker`는 표시 부품이지만, 목록 받기·202·진행 구독은 `realEstateStore` 안에 있고, 고르기 동작이 메뉴의 결과와 진행 중 실행을 지운다(`clearResult` — `:233-237`) |
| 차트 | `ComparisonChart`(네 메뉴가 함께 씀)는 색 5개, 커서 상자 없음, 시리즈 수를 단언하는 테스트가 있다. 막대 차트 부품·`createSeriesMarkers`는 없다. "점만 그리는 `LineSeries`"(`PerformanceChart.tsx:239-257` 추정 표식)가 기존 모의 객체와 맞는 점 표식 방식이다 |
| 소수 정렬 | 소수 문자열을 비교하는 도우미가 없다. 화면의 정렬은 날짜 `localeCompare`뿐이다 |
| `noClientSideFinance` | ESLint 규칙이 아니라 vitest 정적 검사다(`tests/noClientSideFinance.test.ts`) — `MONEY_FILES` 세 파일에서 `Number`·`parseFloat`·`parseInt`를 막는다. 차트는 그리기용으로 `Number()`를 쓴다(`chartSeries.ts:120`) |
| 가드 테스트 | `tests/noUnbuiltAssetRoutes.test.ts`가 `src/app/compare`와 `/api/(compare\|dashboard)\b`를 막고 사이드바 링크 목록을 고정한다. `tests/Sidebar.test.tsx`가 "투자 비교"를 준비중으로 단언한다 |
| 이력 대역 | `tests/setup.ts`가 `fetch`를 감싸 `/api/history*`에만 메모리 대역으로 답한다(`tests/support/historyStub.ts`). 그 밖의 경로는 원래 `fetch`로 넘어간다 |
| 마이그레이션 | 머리는 `a6d2f9c41b83`(`시뮬레이션_이력`). JSON 열 대신 `Text`(012 R12-9 — MySQL JSON은 키 차례·수 표기를 바꾼다). 열거형은 비원생(`native_enum=False, length=16`), 시각은 UTC `DateTime(timezone=False)` |

## R13-1 대상 하나의 결과 — 비교 경로를 대상마다 부른다

**Decision**: 메뉴 경로마다 짝이 되는 **비교 경로**를 백엔드에 둔다(`/api/comparison/...` — R13-2). 비교 경로는 대상 **하나**를 계산한다.

- 메뉴 경로와 **같은 질의·같은 검증·같은 수집 판정·같은 `prepare`**를 같은 차례로 부른다. 거절은 같은 예외를 그대로 올려 같은 처리기가 같은 본문을 낸다.
  202는 메뉴의 수집 본문을 그대로 낸다
- 200은 `prepare` **한 번**으로 메뉴의 요약 JSON(메뉴와 같은 함수)·메뉴의 시계열 JSON(같은 빌더)·비교 블록(`comparison` — R13-3·R13-4·R13-5)을 함께 낸다.
  표의 행(쪽)은 만들지 않는다
- 화면은 대상마다 따로 요청한다(최대 10개 — 브라우저가 호스트당 동시 연결을 나눈다). 요청마다 세션이 따로라 서로 막지 않는다
- 비교 경로는 이력을 쓰지 않는다(계산 경로 전부가 그렇다 — 조사). 수집 작업 행을 쓰고 커밋하는 것은 메뉴와 같다
- 가상자산 일시금은 `daily=True` 한 번으로 요약·시계열을 함께 낸다 — 요약이 메뉴(`daily=False`)와 같다는 것을 통합 테스트가 지킨다

**Rationale**:
- SC-001(메뉴와 같은 값)을 구조로 지킨다 — 비교 경로의 `summary`는 메뉴 함수의 출력 그 자체다. 통합 테스트가 같은 질의의 메뉴 응답 `summary`와 비교 경로 `summary`가 같음을 본다
- 명확화 2(계산된 대상부터)와 맞다 — 대상마다 200·202·거절이 따로 온다
- 거절 본문을 다시 만들지 않는다 — 처리기 클로저를 꺼내는 리팩터가 필요 없다
- 계산이 대상마다 한 번이다(메뉴는 표·시계열로 두 번)

**Alternatives considered**:
- 화면이 메뉴 경로를 대상마다 둘씩(표·시계열) 부른다 — 계산이 20번이고, 일시금 비용 합계·정기예금 경과 세금이 없어 결국 메뉴 응답을 바꿔야 한다. 표 경로는 행 쪽까지 만든다
- 대상 열을 한 번에 받는 묶음 경로 — 예외를 잡아 본문을 다시 만들어야 하고(처리기가 클로저), 한 세션으로는 병렬이 안 되며, 수집이 끝날 때마다 모든 대상을 다시
  계산해야 계산된 대상부터 보일 수 있다

## R13-2 경로 이름과 질의

**Decision**:

| 비교 경로 | 짝이 되는 메뉴 경로 |
|-----------|--------------------|
| `GET /api/comparison/stocks/simulation` | `/api/stocks/simulation` |
| `GET /api/comparison/stocks/recurring-simulation` | `/api/stocks/recurring-simulation` |
| `GET /api/comparison/crypto/simulation` | `/api/crypto/simulation` |
| `GET /api/comparison/crypto/recurring-simulation` | `/api/crypto/recurring-simulation` |
| `GET /api/comparison/deposit/simulation` | `/api/deposit/simulation` |
| `GET /api/comparison/deposit/installment-simulation` | `/api/deposit/installment-simulation` |
| `GET /api/comparison/realestate/simulation` | `/api/realestate/simulation` |

- 질의는 메뉴 경로와 같다. 표 전용 질의(`before`·`limit`·`period`)는 받지 않고, 시계열의 `maxPoints`를 받는다(처음 값 **1000** — 열 선 × 1000점, 헌법 VII 다운샘플링.
  메뉴 시계열의 처음 값 2000과 같은 LTTB다)
- 화면은 메뉴 스토어가 이미 내보내는 질의 함수를 그대로 쓴다 — `stockStore.toQuery`·`toRecurringQuery`, `cryptoStore.toQuery`·`toRecurringQuery`, `depositStore.toQuery`·
  `toInstallmentQuery`, 부동산 `simulationQuery`(지금 내보내지 않음 — 내보낸다). 같은 함수가 같은 공통 조건으로 대상마다 질의를 만든다(SC-002)
- 저장한 비교는 `/api/comparison/saved`(R13-10). 비교 경로는 모두 세 마디 이상(`/api/comparison/<자산군>/<경로>`)이라 `saved`와 겹치지 않는다. 그래도 저장 경로를
  먼저 등록한다(012 `settings`의 교훈)
- 새 라우터 모듈 하나(`api/routes/comparison.py` — 경로 일곱, 얇다), 저장 라우터 하나(`api/routes/saved_comparison.py`). `create_app()`에 다른 라우터처럼 더한다

**Rationale**: 메뉴 경로와 이름·질의가 짝이라 "같은 조건"의 대응이 한눈에 보인다. 질의 함수를 함께 써 비교 화면이 조건을 따로 조립하지 않는다.
`/api/comparison`은 `noUnbuiltAssetRoutes`의 `/api/(compare|dashboard)\b`에 걸리지 않지만, 그 테스트는 화면 경로(`src/app/compare`) 때문에 어차피 고친다(R13-16).

**Alternatives considered**: `/api/comparison/{asset}?method=` 하나 — 자산군마다 질의 이름·형이 달라(FastAPI 검증) 경로 안에서 다시 나눠야 한다.

## R13-3 비용 — 기간 전체 비용의 몫 (명확화 4)

**Decision**: 비용은 **이미 반영된 몫**(`reflected`)과 **매도 가정 몫**(`sale`)으로 나눈 항목 목록과 합이다. 모두 원화다. 새 순수 모듈
`simulation/comparison_costs.py`가 계산 결과(DB·HTTP 없음)에서 항목을 뽑는다.

| 자산군·방식 | 이미 반영된 몫 | 매도 가정 몫 |
|-------------|----------------|--------------|
| 주식 일시금 | 매수 수수료(처음 매수 + 배당 재투자 매수) · 배당 소득세 | `saleCost.fee` · `saleCost.tax`(국내 거래세 / 해외 양도소득세) |
| 주식 적립식 | `buyFeeTotal` · `dividendTaxTotal` | `saleCost.fee` · `saleCost.tax` |
| 가상자산 일시금 | 매수 수수료 | **없음** — 메뉴가 매도를 가정하지 않는다(012 US5) |
| 가상자산 적립식 | `buyFeeTotal` | `saleCost.fee` · `saleCost.tax`(시행일 뒤는 비움) |
| 정기예금 | 끝난 회차 이자 소득세 합 · 진행 중 회차 경과 이자의 소득세 | 없음 |
| 정기 적금 | 만기 이자 소득세(`taxTotal` — 메뉴 칸과 같다) · 진행 중 계약 경과 이자의 소득세 | 없음 |
| 부동산 | 취득세·지방교육세·농어촌특별세 · 매수 중개 보수 · 재산세 합 · 종부세 합 | 매도 중개 보수 · 양도소득세 · 지방소득세 |

- **원화 환산의 버림 규칙은 주식 적립식과 같다**(`services/stock_recurring.py:251-260`) — 국내 `floor_won(Σ 금액)`, 해외 `floor_won(Σ 금액 × 그 행 매매기준율)`.
  해외 일시금의 매수 수수료 원화는 `saleCost.feesKrw`의 매수 몫과 같은 값이 된다(참조값 테스트로 묶는다)
- 정기예금·정기 적금의 진행 중 경과 세금은 계산 모듈이 이미 계산해 평가액에서 빼는 값을 **내놓게 한다** — `deposit_rollover.Summary`에 `accrued_tax`, 적금 요약에
  `open_tax`를 더한다(기본값 0, 기존 값 불변). 비교 쪽에서 `accrued_interest`로 다시 계산하지 않는다(멈춤·만기일 경계를 두 군데서 판단하게 된다)
- 합(`total`)은 모든 항목이 있을 때만 낸다. 메뉴가 비우는 몫(가상자산 시행일 뒤 세금)이 있으면 그 항목은 `null`, 매도 몫의 합과 전체 합도 `null`이고 비운 까닭
  (`blank`)을 함께 낸다 — 0으로 메우지 않는다(FR-011)
- 부동산의 취득 비용은 투자 원금(`invested`)에도 들어 있다. 항목에 `inPrincipal: true`를 달아 화면이 "투자 원금에 포함"을 보인다

**Rationale**: 명확화 4는 기간 전체 비용과 몫의 구분을 요구한다. 몫을 서버가 나눠 내면 화면은 합하지 않는다(원칙 VI). 경과 세금을 계산 모듈에서 꺼내면 평가액과
비용이 같은 수에서 나온다.

**Alternatives considered**:
- 화면이 행을 받아 합한다 — 원칙 VI 위반, 표 경로가 쪽을 나눠 모든 행을 받기도 어렵다
- 가상자산 일시금에도 매도 비용(`crypto_sale_cost`)을 붙인다 — 메뉴에 없는 값이 생겨 "메뉴와 같은 값"(FR-011)이 깨진다. 메뉴를 바꾸는 일은 이 기능의 범위가 아니다

## R13-4 주 값·보유 중 값·현재 가치·잠정·환율 — 정규화 블록

**Decision**: 비교 경로의 200에 `comparison` 블록을 둔다(data-model 3). 순수 함수 모듈 `api/services/comparison_metrics.py`가 메뉴의 요약 값(`Decimal`)과
R13-3의 비용에서 만든다.

- **주 값**(표의 투자 수익·수익률)은 보드 규칙 그대로다 — 주식 일시금·부동산은 매도 후 → 없으면 보유 중, 적립식 둘은 매도 후(비면 `null`), 가상자산 일시금·예금 둘은
  보유 중. 어느 값인지 `mainBasis`(`after_sale`·`holding`·`unavailable`)로 낸다 — 한 표에서 물러난 줄을 화면이 표시한다
- **현재 가치**: 주식·가상자산(일시금·적립식) `totalKrw`, 정기예금 `principal + profit`(요약에 잔고 키가 없다 — 서버가 더한다), 정기 적금 `balance`, 부동산 `value`(없을 수 있다)
- **투자 원금**: 일시금 `principal`(+`principalKrw`), 적립식 `contributed`(+`contributedKrw`), 정기예금 `principal`, 정기 적금 `contributed`, 부동산 `invested`
- **잠정**(원칙 V): `provisional`에 까닭 목록 — `unpublished_rate`(예금 `provisionalFrom`), `provisional_price`·`estimated_price`(부동산), `not_final`(`isFinal = false`)
- **환율**(원칙 V): 외화 대상이면 평가 환율(기준일 행의 `fxRate`·`fxRateDate`, 출처 ECOS 매매기준율)과 원금 환전(메뉴의 `exchange`)을 낸다

**Rationale**: 보드마다 주 값 규칙이 달라 화면이 자산군마다 고르면 규칙이 두 군데(보드·비교)가 된다. 서버가 한 번 정해 내고 테스트가 보드 규칙과 묶는다.

**Alternatives considered**: 화면이 `summary`에서 고른다 — 고르기는 계산이 아니지만, 자산군·방식 일곱 갈래의 규칙이 화면 두 곳(보드·비교 표)에 생긴다.

## R13-5 수익률 추이 선과 끝 점 (명확화 5)

**Decision**:
- 선은 메뉴 시계열의 `returnRate`(보유 중, 원화 기준) 그대로다. 결측 구간(`gaps`)에서 끊는 규칙은 `lib/chartSeries.splitSeriesAtGaps`를 함께 쓴다
- 서버가 `comparison.lineEnd = {date: asOf, holdingReturnRate, afterSaleReturnRate | null}`를 낸다. 화면은 시계열의 마지막 날이 `date`보다 앞이면 그 날에 보유 중 점을
  더해 선을 기준일까지 잇는다(주식은 행 날짜에만 점이 있다 — 조사). 매도 후 점은 `afterSaleReturnRate`가 있을 때만 같은 날에 찍는다
- 새 부품 `components/compare/CompareReturnChart.tsx` — 메뉴 공유 `ComparisonChart`는 고치지 않는다(네 화면·시리즈 수 단언 테스트). 점은 "점만 그리는 `LineSeries`"
  (`lineVisible: false`, `pointMarkersVisible: true`) — 기존 모의 객체(`createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`)
  안에서 동작한다. `createSeriesMarkers`·`priceScale()`을 실행 중에 부르지 않는다(CLAUDE.md 010)
- 커서 상자는 `subscribeCrosshairMove`의 `sourceEvent` 화면 좌표로 놓는다(010). 그날 값이 없는 대상은 "값 없음". 기준일에는 보유 중·매도 후 두 값
- 색 10개 + 선 모양(실선·점선 번갈아 — 열거형을 실행 중에 읽지 않고 수로) + 범례·상자의 이름 — 색만으로 가르지 않는다(FR-015)

**Rationale**: 명확화 5와 FR-015의 "선은 메뉴 차트와 같은 값". 끝 점을 날짜로 맞추면 커서 상자가 기준일에 두 값을 함께 보일 수 있다.

**Alternatives considered**: 서버가 시계열 끝에 기준일 점을 끼워 넣는다 — 메뉴 시계열과 달라져 "같은 값"의 대조가 흐려진다.

## R13-6 막힘 판정과 시작일 제안 (명확화 1)

**Decision**: 화면의 순수 모듈 `lib/compareBlock.ts`가 대상별 응답을 갈래로 나누고 비교 전체 상태를 정한다.

| 갈래 | 응답 | 화면 |
|------|------|------|
| 시작일로 풀림 | 400 `before_listing`(`startableFrom`), 409 `before_first_month`(`startableFrom`), 409 `before_first_trade`(`startableFrom`), 409 `fx_not_available_before`(`availableFrom`) | 막힘. 날짜를 제안 후보로 |
| 시작일로 안 풀림 | 400 `installment_not_available`, 404 `unknown_coin`·`unknown_stock`, 400 `unknown_complex`, 409 `region_retired`·`no_trades_in_area`·`no_price_at_purchase`(매입일을 바꾸라고도)·`tax_rule_not_covered`·`rate_missing`, 404 `no_price_data`·`price_symbol_unknown`·`no_rate_data`, 400 `currency_pair_not_allowed`·`currency_not_allowed` | 막힘. "이 대상을 빼세요"(+ 까닭) |
| 시작일이 너무 늦음 | 400 `start_after_end`(`lastDay`) | 막힘. "시작일을 {lastDay} 이전으로 바꾸세요" — 제안 날짜 없음(가장 이른 날 제안과 방향이 반대) |
| 실패(다시 시도) | 502 `source_unavailable`·503 `source_rate_limited`·409 `fx_unavailable`·네트워크·그 밖의 5xx, 수집 스트림의 실패 | 그 대상만 "수집 실패 — 다시 시도". 막힘이 아니다 |

- **비교 전체**: 막힌 대상이 하나라도 있으면 `blocked` — 결과(표·그래프)를 보이지 않는다. 이미 보이던 결과도 거둔다(늦게 드러난 막힘 — FR-010)
- **제안 날짜** = 시작일로 풀리는 대상들의 날짜 가운데 가장 늦은 날(`YYYY-MM-DD` 문자열 비교 — 금액 계산이 아니다). **수집 중인 대상이 남아 있으면 제안하지 않는다** —
  "수집 중인 대상 N개 — 끝나면 제안 날짜를 정합니다". 막힌 동안에도 수집은 계속한다(R13-7)
- 제안을 누르면 시작일만 옮긴다(실행하지 않는다 — spec 가정). 시작일이 바뀌어 결과가 없으니 흐림 대상도 없다

**Rationale**: 주식은 시작 월의 실제 일봉을 받은 뒤에야 상장일 판정이 끝나는 경우가 있다(`_require_start_month_bar` — 수집 뒤). 수집 중인 대상을 빼고 낸 제안은
그 대상이 끝난 뒤 틀릴 수 있다(SC-003). 시작일 후보 가운데 가장 늦은 날은 다른 모든 후보 이후라, 시작일 사유로는 다시 막히지 않는다.

**Alternatives considered**: 막힘이 하나라도 오면 다른 요청을 끊는다 — 수집 중인 대상의 시작 가능 날짜를 알 수 없어 제안이 틀린다. 서버가 판정한다 — 대상별
요청(R13-1)이라 비교 전체를 아는 곳이 화면뿐이다.

## R13-7 수집 기다리기와 다시 요청 (명확화 2)

**Decision**: 비교 스토어가 대상마다 구독을 하나씩 든다(`Map<대상 키, 해제 함수>`).

- 202 본문의 `jobId`로 그 자산군의 진행 스트림(`subscribeStockProgress`·`subscribeCryptoProgress`·`subscribeDepositProgress`·`subscribeRealEstateProgress`)을 구독한다.
  주식·가상자산의 환율 수집(`fx`)은 `subscribeCollection(currency)`를 구독한다
- `onCompleted` → **그 대상만** 다시 요청한다. `onFailed` → 그 대상을 "수집 실패"(까닭)로 두고 다시 시도 단추를 보인다
- 같은 실행에서 한 대상이 연달아 202를 받는 횟수에 한도를 둔다(**3**). 넘으면 수집 실패("수집이 끝나지 않았습니다") — 환율 스트림이 곧바로 끝나는 경우의 되풀이를 막는다
  (FR-013 실패 양상 *늦게 일어남*)
- 실행마다 차례 번호(`runSeq`)를 올린다. 늦게 온 응답·스트림 사건은 차례가 다르면 버린다(FR-012a — 옛 조건의 결과가 새 표에 들어가지 않는다)
- 화면을 떠나거나 자산군을 바꾸거나 새로 실행하면 모든 구독을 푼다

**Rationale**: 메뉴 스토어의 구독은 모듈 수준 하나라 함께 쓸 수 없다. 스트림 함수는 대상과 무관해 그대로 쓴다(헌법 VII — SSE 진행).

**Alternatives considered**: 몇 초마다 다시 요청(폴링) — 진행이 보이지 않고 원칙 VII(SSE)와 어긋난다.

## R13-8 비교 화면 상태 — 새 스토어

**Decision**: `stores/compareStore.ts`(Zustand) 하나. 메뉴 스토어의 `run`·`rerunHistory`·`refreshIfRan`을 부르지 않는다 — 그 함수들이 이력을 저장한다(FR-020).

- 입력: 자산군, 방식(일시금·적립식·정기예금·정기 적금·매입 후 보유)과 주기, 시작일, 금액, 원금 통화, 배당 재투자, 대상 목록(차례 있음)
- 실행: `runSeq`, 결과를 낸 조건(`ranCondition` — 정규 조건 객체), 대상별 상태(`requesting`·`ok`·`collecting`·`blocked`·`failed`와 내용)
- 흐림(FR-012a): `isStale = !sameCondition(지금 조건, ranCondition)` — 파생 값이라 되돌리면 풀린다. 표의 정렬은 조건이 아니다
- 저장 가능: 결과가 있고, 흐리지 않고, 막히지 않았을 때(수집 중인 대상이 남아도 된다 — FR-016)
- 자산군을 바꾸면 대상·결과를 비우고 시작일·금액을 남긴다. 없는 방식은 그 자산군의 기본 방식으로(FR-002, spec 경계 사례)
- 정규 조건과 같음 판정은 순수 모듈 `lib/compareCondition.ts` — 저장 본문과 같은 모양(data-model 2)

## R13-9 대상 고르기 부품

**Decision**:
- **주식**: `StockSearch` 그대로 + 등록. `stockStore`의 `selectionBody`와 등록 호출을 `lib/stockSelection.ts`의 `registerStock(choice)`로 꺼내 두 스토어가 함께 쓴다
  (메뉴 동작 그대로 — 기존 테스트가 지킨다)
- **가상자산**: `CoinSearch` 그대로(등록 단계 없음 — `coinId`가 식별)
- **예금**: 새 `components/compare/InstitutionChecklist.tsx` — 체크박스 다섯. 정기 적금이면 `GET /api/deposit/institutions`의 `installment.available`이 거짓인 곳을
  끈다(까닭 문구). 기존 `InstitutionPicker`(라디오)는 그대로
- **부동산**: `realEstateStore`의 상태 생성기를 내보내(`realEstateStateCreator`) 비교 화면이 **같은 생성기로 따로 된 인스턴스**
  (`stores/compareRealEstatePicker.ts`)를 만든다. 비교는 그 인스턴스의 고르기(시·도 → 시·군·구 → 법정동 → 단지 → 평형, 목록 202·진행)만 쓰고
  `run`(이력을 저장한다)은 부르지 않는다 — 메뉴의 결과·진행을 지우지 않는다. 모듈 수준이던 진행 구독(`watchers`)·실행 차례(`runSeq`)를 생성기
  안으로 옮겨 인스턴스마다다
  - **지키는 조건**: 부동산 메뉴의 기존 테스트가 고치지 않고 통과해야 한다. 고쳐야 하면 멈추고 보고한다(원칙 III)
  - **구현 중 바꾼 것(2026-10-08 T033)**: 계획은 고르기만 떼어 낸 슬라이스 팩토리(`realEstatePickerSlice.ts`)였다. 고르기 동작이 같은 스토어의
    `clearResult`·`error`·실행 구독과 얽혀 떼어 내면 메뉴 쪽 코드가 크게 바뀐다. 생성기 하나를 두 번 쓰면 고르기 코드가 그대로 한 벌이고 메뉴의
    필드·동작은 바뀌지 않는다(부동산 스토어 테스트 5개 파일이 고치지 않고 통과했다)
- 고른 대상은 "대상 칩"으로 쌓인다(이름·빼기 단추). 같은 대상(주식 `market|symbol`, 가상자산 `coinId`, 예금 투자처, 부동산 `complexId|area`)은 다시 더하지 않는다.
  11번째는 더하지 않고 알린다(FR-004)

**Rationale**: FR-003 "같은 방법" — 부품과 흐름을 함께 써야 메뉴와 비교의 검색이 갈라지지 않는다. 부동산 흐름은 202·진행이 얽혀 베끼면 두 벌이 서로 달라진다.

**Alternatives considered**: 부동산 고르기를 비교 스토어에 새로 쓴다 — 약 200줄의 비동기 상태가 두 벌이 된다. `realEstateStore`를 그대로 쓴다 — 메뉴의 결과·진행을
지운다. 고르기만 슬라이스로 떼어 낸다 — 위 "구현 중 바꾼 것".

## R13-10 저장한 비교 — 테이블 하나, 조건은 서버가 정규화

**Decision**:
- 새 테이블 `saved_comparison`(data-model 1) — `id`(자동 증가), `name`, `asset_class`, `condition`(서버가 정해진 차례로 직렬화한 JSON 글), `saved_at`(UTC). 보관 기간이
  없다 — `history_setting`·정리(`purge`)와 무관하다(명확화 3)
- 경로: `GET /api/comparison/saved`(최근 저장 차례 — `saved_at` 내림차순, 같은 초는 `id` 내림차순), `POST /api/comparison/saved`(새 항목 — 같은 조건이어도 새 행),
  `DELETE /api/comparison/saved/{id}`(없는 `id`도 200 — 멱등)
- 검증은 순수 모듈 `api/services/comparison_conditions.py`(012 `history_conditions`와 같은 틀) — 형식·대상 수(2~10, 예금 ≤5, 정기 적금은 적금 있는 투자처만)·같은 대상
  중복·자산군과 방식의 짝·통화 규칙(외화는 모든 대상이 그 통화일 때만)·이름(앞뒤 공백을 뺀 1~100자). 실패는 422 `invalid_comparison`(어느 칸인지)
- 원금(금액)은 **받은 글자 그대로** 저장한다 — 서버는 검증할 때만 `Decimal`로 읽는다(012 R12-9와 같은 원칙 VI 해석 — Complexity Tracking)
- 서비스는 `SavedComparisonRepository` Protocol에 기댄다(헌법 원칙 IV). 서비스 단위 테스트는 메모리 안 가짜 저장소로 DB 없이 돈다
- 화면: 저장 단추 → 이름 칸(처음 값 자동 이름) → 저장. 목록은 비교 화면 오른쪽 칸(`TableWithHistory` 배치). 불러오면 조건을 채우고 곧바로 실행(FR-017)

**Rationale**: 012 이력 테이블과 성격이 다르다(이름, 같은 조건의 여러 항목, 보관 기간 없음) — 같은 테이블에 섞으면 정리 규칙이 저장한 비교를 지운다.

**Alternatives considered**: `simulation_history`에 자산군 `comparison`을 더한다 — 기본 키가 조건 식별자라 같은 조건을 이름만 달리해 둘 수 없고, 보관 기간 정리를 받는다.

## R13-11 비교 표의 정렬

**Decision**: 순수 모듈 `lib/decimalOrder.ts`의 `compareDecimal(a, b)` — 소수 문자열을 부호 → 정수부 길이 → 자릿수 차례로 견준다. `null`(값 없음·수집 중·비움)은
늘 끝이다. 정렬 키: 이름, 기준일, 투자 원금(원화), 현재 가치, 비용 합, 투자 수익, 수익률. 같으면 더한 차례(안정 정렬). 비교 표·비용 칸·정렬 모듈은 새 정적 검사
`tests/compareNoClientFinance.test.ts`가 `noClientSideFinance`와 같은 규칙(`Number`·`parseFloat`·`parseInt` 금지)으로 본다 — 기존 검사의 파일 목록을 고치지 않는다.

**Rationale**: 정렬은 계산이 아니라 견주기다. `Number`로 바꾸면 큰 원화 금액·긴 소수에서 정밀도를 잃을 수 있다(원칙 VI).

## R13-12 최종 지표 그림

**Decision**: 시계열이 아니라 DOM 막대로 그린다(`components/compare/CompareMetricBars.tsx` — 수익률 묶음·투자 수익 묶음, 0 기준선 양쪽). 막대 옆 글자는 서버 문자열을
표와 같은 형식 함수로 보인다. 막대 길이는 **그리기 전용**으로 `Number()`를 쓴다(차트의 `chartSeries.ts:120` 선례) — 값 표시에는 쓰지 않는다. 값이 `null`인 대상은
막대 없이 "—"와 까닭.

**Rationale**: 헌법 VII는 시계열 차트를 Lightweight Charts로 정한다. 막대 둘은 시계열이 아니고, 새 의존성 없이 접근성(글자 값)을 지킨다.

**Alternatives considered**: `HistogramSeries` — 시간축에 대상을 늘어놓는 억지 사용이고, 모의 객체에 없는 이름이라 테스트마다 모의를 고쳐야 한다.

## R13-13 성능 (SC-004)

**Decision**:
- 대상마다 `prepare` 한 번(R13-1), 시계열 1000점(R13-2)
- `resolve_rate`의 빗나감 경로를 이분 탐색으로 바꾼다 — `RateLookup`이 정렬된 날짜 튜플을 함께 든다. 돌려주는 값(환율·쓴 날짜)은 그대로다. 참조 테스트: 무작위 날짜에서
  옛 방식(전체 훑기)과 결과가 같다
- 측정(quickstart 4): 받아 둔 주식 10개 × 20년 일시금, 원화 원금 가상자산 10개 × 가능한 최장 일시금 — 실행부터 표·그래프가 보일 때까지 5초 안

**Rationale**: 조사의 가장 느린 길이 환율 찾기다. 값이 같으므로 메뉴 결과는 바뀌지 않고 빨라진다.

## R13-14 이력에 남지 않음 (FR-020·SC-007)

**Decision**: 비교 스토어는 `saveHistoryFlow`·메뉴 스토어의 `run` 계열을 부르지 않는다. 화면 테스트가 비교 실행 뒤 `historyStub.calls()`에 `PUT`이 없음을 본다.
백엔드 비교 경로는 이력 서비스를 부르지 않는다(통합 테스트가 실행 뒤 `simulation_history`가 비어 있음을 본다).

## R13-15 사이드바·화면 경로

**Decision**: 화면 `src/app/compare/page.tsx`, 사이드바 `{ label: "투자 비교", href: "/compare" }`, 상단 바 제목 `TITLES["/compare"] = "투자 비교"`. 화면 배치는
contracts/ui-wireframes.md.

## R13-16 바뀌는 기존 테스트 — 구현 때 승인을 받는다

012와 같은 절차다 — 테스트를 먼저 쓰고, 구현 뒤 전체 스위트의 **실제** 실패 목록을 보이고 승인을 받은 뒤 그 테스트만 고친다(주석 `013 승인 <날짜>`).

예상(계획 시점):

| 테스트 | 바뀌는 단언 | 까닭 |
|--------|-------------|------|
| `frontend/tests/Sidebar.test.tsx` | 준비 안 된 항목 `["투자 비교","대시보드"]` → `["대시보드"]`, "준비중" 2개 → 1개, 포커스 예 "투자 비교" → "대시보드", 링크 목록에 `/compare` | FR-001 |
| `frontend/tests/noUnbuiltAssetRoutes.test.ts` | `UNBUILT`에서 `compare`를 뺀다, 사이드바 링크 목록에 `/compare` | FR-001 |
| `frontend/tests/TopBarTitle.test.ts` | 경로 → 제목 표에 `/compare` | FR-001(표가 전체를 고정하면) |

예상하지 않은 실패가 나오면 위 목록에 없으므로 멈추고 보고한다. 백엔드는 바뀌는 기존 테스트를 예상하지 않는다 — 계산 모듈에 더하는 필드는 기본값이 있고,
`resolve_rate`의 결과는 같다.

## R13-17 원칙 II·IX — 새 출처 없음, 새 자산군 없음

새 데이터 출처가 없다(계약 테스트 대상 없음). 수집은 각 자산군의 지금 경로·한도를 그대로 쓴다. 부동산의 새 시·군·구는 처음 고를 때 실거래 약 260~280회를 받는다 —
새 지역 단지 10개면 하루 한도에 닿을 수 있다. 그때 그 대상은 수집 중·수집 실패(까닭)로 남는다(FR-013). 비교 화면이 한도를 따로 관리하지 않는다.

## R13-18 단가 등락 (반복 2026-10-09 — spec FR-011a, 명확화 2026-10-09)

**Decision**:

| 자산군 | 단가(`basis`) | 시작일 단가 | 기준일 단가 | 통화·단위 |
|--------|---------------|-------------|-------------|-----------|
| 주식(일시금·적립식) | 수정주가 `split_restated_close` — 010 `simulation/split_adjust.split_restated_close`(그 날 원주가 종가 ÷ 그 날 뒤 구간 안 분할 비율) | 시작일 이후 첫 거래일(매수일)의 수정주가 | 기준일 원주가 종가(그 뒤 분할이 없다) | 상장국 통화(KRW·USD·JPY), 1주 |
| 가상자산(일시금·적립식) | UTC 일봉 시가 `daily_open` | 매수한 일봉(적립식은 첫 납입 일봉) | 기준일 일봉 | 시세 통화, 1개 |
| 예금(정기예금·정기 적금) | 발표 금리 `published_rate` — 정기예금은 정기예금 금리, 적금은 적금 금리 | 가입 달 | 기준일 달 — 미발표면 마지막 발표 달 + 잠정(008 규칙) | 연 %, 차이는 %p, 등락률 없음 |
| 부동산 | 그 달 시세 `market_price` | 매입가(매입 달 시세 — 요약 `buyPrice`) | 평가액의 시세(요약 `value`·`valueMonth`, 추정·잠정 표식). 없으면 `missing` | KRW, 1채 |

- 서버의 순수 함수(`simulation/unit_price.py`)가 `change = asOf − start`, `changeRate = quantize_rate(change ÷ start)`(예금은 `None`)를 낸다. 비율 표기는 기존 `returnRate`와 같다
  (비율 값, 화면 `formatPercent`). 분할 누적 비율 글자(`50:1`, 병합 `1:10`)도 같은 모듈이 낸다
- 값은 비교 블록 `comparison.unitPrice`에만 싣는다(data-model 3.2) — 메뉴 요약·시계열은 바뀌지 않는다
- 기준 이름은 `split_restated_close`다 — 010 함수와 같은 이름이고, 출처 수정가의 이름(`adjusted_close`·`close_adjusted`·`adjclose`)을 시뮬레이션 계층에 두지 않는다
  (005 가드 `tests/unit/test_no_adjusted_price.py` — 구현 중 `split_adjusted_close`로 처음 지었다가 가드에 걸려 바꿨다, 2026-10-09)
- 데이터 출처(지금 계산이 이미 가진 값 — 새 출처 없음):
  - 주식 일시금: `SimulationResult.closes`·`splits`·첫 행(매수일)·`as_of`
  - 주식 적립식: 적립식 결과 행의 `close_price`·`splits`
  - 가상자산: 매수(첫 납입) 일봉·기준일 일봉의 `open`
  - 예금: 금리 해석기(`rate_resolver`)의 가입 달·기준일 달 발표 금리
  - 부동산: 요약의 `buyPrice`·`value`·`valueMonth`·`estimated`·`provisional`
- 화면: 열 셋(시작일 단가·기준일 단가·등락 — 등락 칸에 차이와 등락률 두 줄), "등락" 정렬은 등락률(예금은 %p)

**Rationale**:
- 사용자 답(2026-10-09): 주식은 "전부 수정 주가로 계산하고, 화면에서도 수정주가로" 보인다. 단가 열의 네 값을 수정주가로 낸다 — 투자 원금·현재 가치·투자 수익 계산은
  그대로다(SC-001, 005 가드 `test_no_adjusted_price` — 출처 수정가를 쓰지 않는다)
- 분할을 반영해야 1주의 가격 변화가 된다. 메뉴 차트의 주가 선과 같은 함수라 두 화면이 같은 값을 보인다(SC-010)
- 가상자산 시가는 현재 가치(시가 평가)와 같은 기준이다. 금리의 변화율은 읽기 어렵다 — %p 차이만
- 단가는 상장국 통화다 — 원화로 바꾸면 환율이 섞여 가격의 변화가 아니다. 그래서 해외 종목의 단가 등락률과 원화 수익률이 다르고, 칸 도움말이 그 까닭을 말한다

**Alternatives considered**:
- 원주가 그대로 — 분할이 끼면 차이·등락률이 분할 비율만큼 틀어진다(삼성전자 2018 50:1)
- 원주가 + 분할이 낀 대상은 등락 비움 — 분할이 흔한 미국 종목에서 칸이 자주 빈다
- 가상자산 종가 — 현재 가치와 기준이 달라진다
- 예금 "—" — 사용자가 금리와 %p를 골랐다
- 열 넷(차이·등락률을 따로) — 표가 넓어져 1440px 창에서 가로 스크롤이 생긴다. 등락 칸 하나에 두 줄로 둔다
- 화면이 시계열에서 단가를 고른다 — 주식 시계열은 행 날짜에만 점이 있어 기준일 종가가 없을 수 있고, 차이·등락률을 화면이 계산하게 된다(원칙 VI)

