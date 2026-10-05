# Research: 성과 추이 차트의 가격 선·차트 위 값 표시와 최근 시뮬레이션 배치

**Feature**: `010-chart-price-overlay-history-layout` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

새 출처·새 수집·새 테이블이 없다. 조사는 세 가지다 — (1) 네 자산군의 시계열 조립 코드가 가격을 이미 손에 쥐고 있는지, (2) lightweight-charts 5.2.1이
눈금 없는 가격 선·커서 위 상자·터치를 기존 테스트 모의 객체를 깨지 않고 받는지, (3) 표와 이력을 나란히 둘 수 있는 실제 창 폭. (3)은 개발 DB와
브라우저(1440·1920px 창)에서 쟀다.

---

## R10-1. 가격은 이미 계산 결과 안에 있다 (FR-001, FR-002)

**실측(코드)** — 네 시계열 조립 함수(`api/services/*_series.py`)는 표와 같은 계산 결과를 받아 모양만 바꾼다(005 SC-032). 그 결과에 가격이 이미 있다.

| 자산군 | 시계열 점의 출처 | 가격 | 표의 같은 값 |
|--------|------------------|------|--------------|
| 주식 | `SimulationResult.rows`(달 첫 거래일·배당락·재투자 행) — 같은 날은 마지막 행 | `Row.open_price` = 그날 **원주가 시가**(`DayBar(quote_date, open_raw)`), 종목 통화 | `rows[].openPrice` "시작가" (`str()`) |
| 가상자산 | `CryptoResult.daily`(일봉마다) | `row.open_price`, 시세 통화(`coin.quote_currency`) | `rows[].openPrice` "시가" (`format(…, "f")`) |
| 예금 | `DepositOutcome.rows`(가입·매달 1일·만기·재예치) + 계산 끝 | **결과에 없다** — `prepare`가 읽은 월별 금리(`deposit_rate.get_rates`)와 마지막 발표 달(`get_coverage().latest_month`)을 계산에 넘기고 버린다 | 표에는 회차의 **적용 금리**(`rate`)만 있다 — 다른 값(Clarifications) |
| 부동산 | `HoldingResult.rows`(매달) + 계산 끝 | `HoldingRow.month_average`(같은 단지·평형, 해제 제외, 원 정수 — 없으면 `None`) | `rows[].monthAverage` "그 달 평균" |

**Decision**: 가격은 이 값들을 **그대로** 점에 싣는다. 새 조회·새 계산은 없다.

- 주식의 점은 지금처럼 표의 행 날짜(달 첫 거래일·배당락일·재투자일)뿐이다 — 주가 선도 1년에 12~16점이다. 일별 주가를 따로 보내는 안(`pricePoints`)은
  R10-2의 "한 점에 가격과 잔고"를 뒤집고, 표의 행이 아닌 날에는 상자가 잔고·수익률을 보일 수 없어 기각했다(분석 단계, 사용자 결정 — spec FR-001·
  Assumptions).

- 예금만 전달 경로를 하나 더한다 — `prepare`가 이미 읽은 월별 금리와 마지막 발표 달을 `Prepared`에 실어 시계열 조립까지 넘긴다(R10-5).
- 주식은 분할 기록을 결과에 싣는다 — `run_simulation`이 이미 `price_repo.splits`로 읽어 시뮬레이터에 넘기고 버린다(R10-4).

**Rationale**: 차트가 따로 가격을 구하면(시계열 경로에서 저장소를 다시 읽으면) 반올림·날짜 기준·통화가 갈라져 조용히 어긋난다(FR-002 실패 양상). 같은
계산 결과에서 꺼내면 표와 다를 수가 없다.

**Alternatives considered**: 시계열 경로에서 저장소를 다시 읽는다 — 같은 요청 안에서도 두 번째 읽기가 첫 번째와 다를 수 있고(수집이 그 사이 끝나면),
코드가 두 벌이 된다. 주식에 수정주가를 쓴다 — Clarifications가 원주가로 정했다(표의 "시작가"와 같아야 한다).

## R10-2. 계약 모양 — 점마다 `price`, 빈 사유는 따로 (FR-001, FR-003, FR-011)

**Decision**:

- 점에 `price`(문자열 또는 `null`)를 더한다. `null`이면 `priceMissing`(사유)을 함께 싣는다 — `unpublished`(예금 미발표 달), `missing`(예금 결측 달),
  `no_trades`(부동산 거래 없는 달). 값이 있으면 `priceMissing` 키를 두지 않는다(006 FR-059의 "해당이 없으면 키를 두지 않는다").
- 응답 위에 `priceKind`(`stock_open`·`crypto_open`·`deposit_rate`·`apt_average`)와 `priceCurrency`(주식·가상자산·부동산은 통화, 예금은 `null`)를 싣는다.
  화면은 `priceKind`로 범례 이름·형식을 고른다 — 서버는 한국어 표시 문구를 만들지 않는다.
- 부동산 점에 `profit`(투자 수익, 원 정수 문자열)을 더한다 — 차트 위 표시(FR-009)가 보인다. 표의 `profit`, 끝점은 `summary.profit`과 같다.
- 주식 응답에 `splits`(효력일·분자·분모, 구간 안의 것)를 더한다(R10-4).
- **기존 `gaps`에 가격 결측을 넣지 않는다.** `gaps`는 잔고·수익률 선이 끊기는 자리다 — 가격만 없는 달(예금 미발표, 부동산 거래 없음)을 넣으면 잔고 선까지
  끊기고, 기존 테스트(`test_realestate_series_api`의 `gaps` 정확 비교 둘, `test_deposit_series`·`test_crypto_series`의 `gaps == []`)가 깨진다.

**Rationale**: 가격과 잔고를 한 점에 두면 날짜가 어긋날 수 없다(FR-007). 사유를 명시하면(헌법 원칙 V) 화면이 "0"이나 빈칸 대신 "—"와 사유를 보인다
(FR-011). 가격이 없는 날의 사유는 자산군마다 하나뿐인 경우가 많지만, 예금은 둘(미발표·결측)이라 화면이 추측하지 않게 서버가 말한다.

**Alternatives considered**: 가격 선을 별도 배열(`priceSeries`)로 보낸다 — 두 배열을 따로 줄이면 날짜가 갈라지고(FR-007 실패), 화면이 두 배열을 날짜로
맞춰야 한다. 가격 결측을 `gaps`에 사유로 더한다 — 위의 이유로 기각. 숫자(JSON number)로 보낸다 — 헌법 원칙 VI 위반.

## R10-3. 다운샘플은 점을 통째로 고른다 (FR-007)

**실측(코드)** — 네 조립 함수 모두 잔고(평가액) 축으로 LTTB를 돌려 **날짜를 고른 뒤 그 날짜의 점을 통째로** 가져온다(`by_date[p.date]`). 점에 필드를
더해도 같은 날짜의 값이 함께 따라온다.

**Decision**: 다운샘플은 바꾸지 않는다. 가격은 점의 필드로 따라간다. 각 조립 함수의 단위·통합 테스트에 "줄인 점의 가격 = 그 날짜 원래 점의 가격"을 더한다.

**Rationale**: 고르는 기준을 잔고로 두면 잔고 선의 모양이 지금과 같다(SC-006 — 이 기능 전과 같은 차트). 가격의 극값이 고른 점에서 빠질 수 있지만, 보이는
점의 값은 모두 그 날의 실제 값이다 — 범례가 "원본 N개 중 M개"를 이미 밝힌다.

**Alternatives considered**: 가격 축으로도 따로 골라 합친다 — 점 수가 늘고 잔고 선의 모양이 바뀐다. 가격으로만 고른다 — 잔고 선이 지금과 달라진다.

## R10-4. 주식 분할 표식 (FR-008)

**실측(코드)** — 주식 표에는 분할 표시가 없다(행 종류는 `month_first`·`dividend`·`reinvest`). 분할은 시뮬레이터가 효력일에 주식 수를 바꾸는 것으로만
드러난다. 효력일은 대개 점의 날짜(달 첫 거래일·배당락일)가 아니다 — 원주가 선은 효력일 **뒤 첫 점**에서 꺾인다. spec FR-008의 "표의 분할 표시와 같은
날"을 이 사실대로 고쳤다(같은 작업 단위).

**Decision**:

- `SimulationResult`에 `splits: tuple[SplitOn, ...] = ()`를 더한다(기본값 — `test_stock_series_build`가 결과를 직접 만든다). `run_simulation`이 이미
  읽은 `split_rows`를 담는다.
- 시계열 응답 `splits: [{date, numerator, denominator}]`(구간 안, 효력일 오름차순).
- **표식 자리는 화면이 정한다** — 그린 점(다운샘플 뒤) 중 효력일 이상인 첫 점. 순수 함수 `splitMarks(points, splits)`(`lib/chartSeries.ts`). 효력일 뒤에
  점이 없으면 표식이 없다(꺾임도 없다).
- 표식은 가격 선 위에 점만 그리는 시리즈(009의 추정 표식과 같은 방법)이고, 범례 "● 분할", 그 점의 차트 위 표시에 "분할 1→4 (2020-08-31 효력)".

**Rationale**: 다운샘플은 서버가 하므로, 서버가 표식 날짜를 정하면 그 점이 줄이기에서 빠졌을 때 표식이 허공을 가리킨다. 그린 점을 아는 화면이 정한다.

**Alternatives considered**: `createSeriesMarkers`(v5 플러그인) — 기존 테스트 모의 객체(파일마다 인라인, `addSeries`·`setData`·`subscribeCrosshairMove`·
`timeScale`·`remove`만)에 없다. 분할이 없는 응답에서는 부르지 않으면 되지만, 같은 일을 이미 검증된 점 시리즈로 할 수 있다. 세로선 — 라이브러리에 기본 기능이
없다(플러그인 직접 구현).

## R10-5. 예금의 그 달 금리 (FR-001, FR-002, FR-003)

**실측(코드)** — `simulation/deposit_rollover._rate_resolver`: 날짜의 달이 `latest_month` 뒤면 마지막 발표 달 금리로 대신한다(잠정 — `provisional`).
아니면 `rates[month]`이고 없으면 `RateMissing`. 가입·재예치만 금리를 읽으므로 **만기 사이 달의 결측은 계산을 멈추지 않는다** — 그 달 점의 금리 칸이 빈다.
spec에 이 경우(예금 결측 달 — "결측")를 더했다(FR-003·FR-011·SC-002, Edge Cases).

**Decision**:

- `prepare`가 읽은 `rates`(달 → 연 %)와 `latest_month`를 `Prepared`에 싣는다(`published_rates`). `build_series(outcome, *, start, rates, latest_month)` —
  새 인자는 **필수**다(기본값이 있으면 경로가 넘기기를 잊어도 모든 점이 "미발표"로 조용히 나온다).
- 점의 가격 = 점 날짜의 달 `m`에 대해 `m > latest_month`면 `null` + `unpublished`, `m`이 `rates`에 없으면 `null` + `missing`, 아니면 `rates[m]`.
  서식은 표의 `rate`와 같은 `rate_text`.
- 이 값은 "시뮬레이션이 그 달 가입·재예치에 읽는 금리"와 같다(FR-002) — 같은 `rates`·같은 달 규칙이다. 단위 테스트가 가입·재예치 행의 적용 금리와 그 점의
  가격이 같음을 확인한다(잠정 행 제외).

**Rationale**: 잠정 달에 대신 쓴 금리를 그 달 금리로 그리면 발표되지 않은 값이 발표된 것처럼 보인다(원칙 V, spec Edge Cases).

**Alternatives considered**: 표의 적용 금리(회차마다 고정)를 그린다 — Clarifications가 기각(그 달 발표 금리가 아니다). 시계열 경로에서 금리를 다시 읽는다 —
R10-1의 이유로 기각.

## R10-6. 부동산의 그 달 실거래가 평균과 투자 수익 (FR-001, FR-009, FR-011)

**Decision**:

- 점의 가격 = 그 점이 나온 행의 `month_average`. 첫 점(매입일)은 매입 달 행, 끝점(계산 끝)은 그 달 행(`rows[0]` — 행은 내림차순). `None`이면 `null` +
  `no_trades`.
- `profit` = 행의 `profit`, 끝점은 `summary.profit`.
- 시세 없음 달은 지금처럼 점이 없고 `gaps`(`no_price`)다 — 실거래가 평균도 없다(36개월 창 안에 거래가 없으니 그 달에도 없다).
- 추정 표식(`estimated`)은 평가액에만 붙는다 — 실거래가 평균은 늘 실측이다(FR-006).

**Rationale**: 적용 시세(추정 포함)를 실거래가 자리에 넣으면 거래가 없던 달에 거래가 있던 것처럼 읽힌다(FR-011 실패 양상, Clarifications).

## R10-7. 가격 선 그리기 — 눈금 없는 겹침 축 (FR-004, FR-005, FR-006)

**실측(라이브러리 5.2.1 `typings.d.ts`)** — `priceScaleId`가 `left`·`right`가 아니면 **겹침(overlay) 가격 축**이 된다. 겹침 축은 눈금을 그리지 않고
늘 자동 비율이다. 여백은 차트 옵션 `overlayPriceScales.scaleMargins`로 준다 — `createChart` 옵션이라 모의 객체가 그대로 받는다(`priceScale().applyOptions`는
모의 객체에 없다).

**Decision**:

- 가격 시리즈는 `priceScaleId: "price"`(겹침), `priceLineVisible: false`, `lastValueVisible: false`(축 눈금·값 표지 없음). 색은 잔고(회색 계열)·수익률
  (주황 점선)과 다른 파랑 실선, 잠정 구간은 연한 파랑(008 규칙 — `provisionalFrom`).
- 구간 나누기 = 기존 `splitSeriesAtGaps`(잔고와 같은 자리에서 끊음) → **가격이 `null`인 점에서 다시 끊음** → 잠정 경계. 순수 함수
  `priceSegments(points, gaps)`(`lib/chartSeries.ts`).
- 점 하나뿐인 구간은 점으로 그린다(`pointMarkersVisible`) — 선은 두 점이 있어야 보인다. 부동산은 달마다 거래가 드물어 모든 구간에 점 표식을 단다.
- **가격 시리즈는 점에 `price` 키가 있을 때만 만든다.** 기존 차트 테스트(시리즈 수·축 검사 — `PerformanceChart`·`…Gaps`·`…Provisional`·`…Axis`·
  `…Estimated`)의 응답에는 가격이 없어 시리즈 수가 지금과 같다. 운영의 네 응답은 늘 가격을 싣는다.
- 범례: "─ 주가 (USD)", "─ 시세 (USD)", "─ 금리 (연 %)", "─ 실거래가 평균 (KRW)"(`priceKind` → 이름, `priceCurrency` → 단위).

**Rationale**: Clarifications — 눈금 없이 선 모양만. 잔고·수익률 축에 얹으면 평선이 되거나 수익률로 읽힌다(FR-004 실패 양상).

**Alternatives considered**: 셋째 보이는 축 — Clarifications가 기각(축이 셋이면 어느 선이 어느 축인지 읽기 어렵다). 아래 칸(pane) 분리 — 사용자 요청이
"같이 그려줘"이고, 칸이 둘이면 차트 위 표시가 칸을 가로질러야 한다.

## R10-8. 값이 없는 날의 자리 (FR-011)

**실측** — 라이브러리의 시간 축은 **어느 시리즈에든 있는 시각만** 자리로 둔다. 가상자산 출처 결측 날·부동산 시세 없음 달은 점이 없어 시간 축에 자리가 없다
— 커서가 그 날에 놓일 수 없어 "출처 결측"·"시세 없음"을 보일 곳이 없다. 예금 미발표·결측 달과 부동산 거래 없는 달은 점(잔고)이 있어 자리가 있다.

**Decision**: 점 범위(첫 점 ~ 끝 점) 안의 `source_missing`·`no_price` **구간마다 값 없는 자리(whitespace — `{ time }`) 하나**를 구간 시작일(`from`)에
둔다. 값 없는 자리만 담은 시리즈 하나를 겹침 축에 더한다(그리는 것이 없다). 커서가 그 자리에 오면 차트 위 표시가 구간 `from ~ to`와 잔고·수익률·가격 모두
"—", 그 구간의 사유를 보인다. 이 시리즈도 가격이 있는 응답에서만 만든다(R10-7 — 기존 테스트 그대로). 순수 함수 `gapSlots(points, gaps)`.

**Rationale**: 결측을 명시적으로 표현한다(원칙 V) — 지금은 결측 구간이 시간 축에서 접혀 커서로 사유를 볼 수 없다. 상자가 사유를 보이는 데는 자리 하나면
충분하다. 날마다 자리를 두면 안 된다 — 시간 축은 자리마다 같은 폭을 주므로, 줄인(다운샘플) 차트에서 결측 하루가 줄인 점 하나(며칠 치)와 같은 폭이 되어
구간이 몇 배로 과장되고, 자리 수가 줄이기 밖에서 늘어난다(원칙 VII — 분석 단계에서 고침). 차트 모양이 바뀌는 유일한 곳이다(quickstart가 확인한다).

**Alternatives considered**: 차트 위 표시를 결측 구간 위에서 띄우지 않는다 — spec FR-011의 "출처 결측"·"시세 없음"을 보일 수 없다. 서버가 결측 날에도 점을
보낸다 — 잔고 선의 점이 바뀌어 기존 테스트(`test_시세_없음_달은_점이_없고_끊는다`)가 깨진다.

## R10-9. 커서 가까이 상자 (FR-009, FR-010, FR-012, FR-013, FR-014)

**실측(라이브러리)** — `subscribeCrosshairMove`의 인자에 `time`(커서가 붙은 시간 축 자리 — 가장 가까운 자리로 붙는다)과 `point`(차트 안 좌표)가 있다.
커서가 차트를 벗어나면 둘 다 `undefined`로 한 번 더 부른다. 터치는 라이브러리 기본 **추적 모드**(길게 누르면 십자선이 손가락을 따라가고 다음 탭에 풀린다)가
같은 콜백을 부른다.

**Decision**:

- 상자는 차트 칸(`relative`) 안에 `absolute`로 띄운다(`data-testid="performance-hover"`, `role="tooltip"`). 자리는 순수 함수
  `placeHover(point, box, area)` — 기본은 커서 오른쪽 아래 12px, 오른쪽이 넘치면 커서 왼쪽, 아래가 넘치면 위. 차트 칸 밖으로 나가지 않는다(FR-012).
- 값은 `time`으로 찾은 **그 점의 원본 문자열**(지금처럼 `lookup`) — 다운샘플된 점이면 그 점의 날짜와 값이다(FR-010). 자리(whitespace)면 R10-8의 사유.
- 형식은 **표와 같은 함수**: 주식 가격 `currencySymbol + formatRate`(표의 시작가), 가상자산 `currencySymbol + formatPrice`(표의 시가), 예금 금리
  `formatAnnualRate`, 부동산 실거래가 평균·평가액·투자 수익 `formatMoneyWithSymbol(…, "KRW")`, 잔고 `formatMoneyWithSymbol(…, basisCurrency)`, 수익률
  `formatYield`. 날짜는 일(`YYYY-MM-DD`), 부동산은 달(`YYYY-MM`) — 첫 점·끝 점만 날짜(매입일·계산 끝).
- `time`·`point`가 없으면 상자를 지운다. 지금의 차트 아래 한 줄(`performance-tooltip`)은 없앤다(FR-013 — 참조하는 테스트 없음, 확인함).
- 터치는 기본 추적 모드 그대로 — 새 API 호출·옵션이 없다(`subscribeClick`은 기존 모의 객체에 없어, 부르면 기존 테스트 전부가 깨진다). 라이브러리 열거형
  (`TrackingModeExitMode` 등)을 실행 중에 읽지 않는다 — 모의 모듈에 없는 내보내기를 읽으면 vitest가 오류를 낸다.

**jsdom에서 검증하는 것**: 콜백을 직접 불러 상자의 문구·사유·사라짐, `placeHover`의 뒤집기(넓이를 인자로), 시리즈 수·축 id·`setData` 값(가격·분할·자리),
범례. **브라우저에서 보는 것**(quickstart): 실제 상자 위치·잘림, 0.2초 안의 표시(SC-003), 터치 흉내, 결측 구간의 길이.

**Alternatives considered**: 차트 왼쪽 위 고정 자리 — spec Assumptions(커서를 따라간다). 라이브러리 기본 십자선 값 표지 — 축 눈금이 없는 겹침 축에는
값 표지가 없고, 세 값을 한 자리에 모을 수 없다.

## R10-10. 표와 이력의 배치 — 측정과 경계 (FR-015, FR-016, FR-017, SC-004)

**실측(브라우저, 개발 DB)**:

| 화면 | 가장 넓은 표(조건) | 표 고유 폭 | 나란히 놓이는 창 폭(계산) |
|------|---------------------|-----------:|--------------------------:|
| 주식 | AAPL · 원화 원금(15열 — 환산 열 포함) | 1,071px | 약 1,800px |
| 가상자산 | BTC · 원화 원금(11열) | 842px | 약 1,570px |
| 예금 | 시중은행(008 표) | 659px | 1,440px에서 이미 들어감(약 1,390px) |
| 부동산 | 헬리오시티 30평대(009 표 11열) | 836px | 약 1,560px |

- 본문 폭 = 창 폭 − 306px(사이드바 224 + 좌우 여백) — 1440px 창 1,134px, 1920px 창 1,614px.
- 이력 행의 최소 내용 폭 348px(주식) ~ 384px(가상자산) — 주식은 다시 실행 버튼(약 70px)이 더해진다. 이력 칸 400px(안쪽 여백을 빼면 368px)에는 행이
  한 줄로 다 들어가지 않을 수 있다 → **이력 행을 줄바꿈(`flex-wrap`)으로 바꾼다** — 버튼 묶음이 다음 줄로 내려가고 칸 안 가로 넘침이 없다. 칸이 전체 폭일
  때(좁은 창)는 지금처럼 한 줄이다. 사이 간격 20px.
- 나란히 놓이는 창 폭 = 표 고유 폭 + 400 + 20 + 306. **모두 1920px 이하**(SC-004·spec Assumptions).

**Decision**:

- 표와 이력을 **줄바꿈 flex**(`flex flex-wrap items-start gap-5`)에 둔다. 표 칸은 `flex: 999 1 auto`(기본 크기 = 표 고유 폭), 이력 칸은 `flex: 1 1 400px`.
  둘의 기본 크기 합이 본문 폭보다 크면 이력이 다음 줄로 내려가 전체 폭이 된다 — **경계 폭을 상수로 두지 않는다.** 표의 열이 조건마다 달라도(국내 종목은
  환산 열이 없다) 그 표의 실제 폭으로 경계가 정해져, 나란히 두느라 표가 줄어드는 일이 구조적으로 없다(FR-015 실패 양상).
- 이력 칸은 `sticky top-4 self-start`, `max-height: calc(100vh − 2rem)`, 안에서 세로 스크롤(FR-016). 창(문서)이 스크롤 주체다 — `AppShell`의 조상에
  `overflow`가 없어 sticky가 동작한다(확인함).
- 결과가 없으면(실행 전) 표 칸이 없어 이력이 전체 폭이다(지금과 같다).
- 공유 부품 하나 `components/TableWithHistory.tsx`에 규칙을 둔다 — 네 화면이 같은 규칙을 쓴다(한 화면만 다르게 고쳐지는 일을 막는다).
- 비교 차트는 이 부품 아래 전체 폭(지금 자리 — FR-017).
- 경계 폭은 quickstart가 화면마다 다시 재서 plan의 표에 기록한다(FR-015 — "측정값으로 정하고 화면별로 기록").

**Rationale**: 고정 경계(미디어 쿼리)는 표의 열이 바뀌면(배당 열, 환산 열) 조용히 틀린다 — 경계가 너무 좁으면 열이 잘리고, 너무 넓으면 흔한 창에서 늘
아래로 내려간다(FR-015의 두 실패 양상). 내용 폭으로 줄바꿈하면 둘 다 일어날 수 없다.

**Alternatives considered**: 자산군별 미디어 쿼리 상수(1800·1570·1440·1560) — 위의 이유. 컨테이너 쿼리 — 상수가 그대로 필요하다. `ResizeObserver`로 재서
JS가 배치 — 코드가 늘고 첫 그림에서 깜박인다. 이력 칸을 행이 한 줄로 들어가는 폭(약 460px)으로 넓힌다 — 경계가 60px 넓어져 주식이 1,860px 창에서야 나란히 놓인다. 행이 줄바꿈하면 칸 폭이 행 모양을
제약하지 않는다.

## R10-11. 주식 다시 실행 (FR-018, FR-019, FR-020)

**실측(코드)** — 가상자산 `rerunHistory`(`cryptoStore.ts`)는 입력을 이력 항목으로 바꾸고 `run()`을 부른다. 주식 이력 항목(`SimulationHistoryEntry`)은
`stock`(검색 결과 형식)·`start`·`principal`·`principalCurrency`·`reinvest`를 담는다. 주식은 종목을 고를 때 등록 요청(`selectStock` →
`POST /api/stocks/selection`)이 상장일(`listedOn`)을 받아 시작일 안내에 쓴다.

**Decision**:

- `stockStore.rerunHistory(id)` — 항목을 찾아 입력을 `{ stock: entry.stock, start, principal, principalCurrency, reinvest }`로 바꾸고, 고른 종목에 딸린
  상태(`listedOn`·`startable`·`selectionError`)를 지운 뒤 `run()`(가상자산 `rerunHistory`와 같은 꼴). **등록 요청을 다시 보내지 않는다.**
- 막힌 조합(원금 EUR·미국 종목 등)은 `run()`의 기존 검사·서버 거절이 그대로 사유를 보인다 — 다시 실행이 통화를 바꾸지 않는다(FR-019).
- 수집·진행·실패는 `run()`의 기존 경로(202 → SSE → 결과)다(FR-020).
- `SimulationHistory`에 필수 속성 `onRerun`과 행마다 "다시 실행" 버튼(가상자산과 같은 문구·`aria-label`)을 더한다. 지금 행 끝의 `ml-auto`는 버튼 묶음으로
  옮긴다.

**Rationale**: 등록 경로(`POST /api/stocks/selection`)는 검색 목록 id(`listing`)나 일본 외부 검색 결과(`external` — `select_external`이 일본·JPY 밖을
거절한다)만 받는다. 이력 항목에는 목록 id가 없어 국내·미국 종목을 다시 등록할 수 없다(분석 단계에서 확인 — 처음 설계는 `selectStock(entry.stock)`이었다).
이력의 종목은 이미 실행한(= 등록된) 종목이라 시뮬레이션 경로(`require_stock`)가 그대로 찾고, 계산은 직접 실행과 같은 `run()`이다(SC-005). DB를 새로 만들어
종목이 없으면 서버의 "모르는 종목" 사유가 직접 실행과 같은 자리에 보인다(FR-020). 다시 실행한 화면에는 상장일 안내가 비지만, 상장 전 시작일은 `run()`의
409 `before_listing`이 지금처럼 시작 가능 날짜와 사유를 보인다.

**Alternatives considered**: 등록 경로에 `source: "registered"`(시장·종목코드로 등록된 종목을 찾아 상장일을 돌려준다)를 더한다 — 새 API·계약 테스트가
늘어 이 기능의 목적 밖이다. 이력에 목록 id를 저장한다 — FR-021(이력 형식 불변) 위반이고 이미 저장된 이력에는 없다. `onRerun`을 선택 속성으로 — 기존 테스트를 바꾸지 않아도 되지만, 화면이 넘기기를
잊으면 버튼이 조용히 사라진다(지금 생긴 결함의 모양 그대로). 필수로 두고 기존 테스트 두 파일의 렌더에 속성만 더한다(D2 목록 — plan).

## R10-12. 바뀌는 기존 테스트 (D2)

**조사** — 백엔드 시계열 테스트에 점·응답의 키 집합 검사는 없다. `gaps` 정확 비교는 R10-2대로 그대로 통과한다. `test_stock_series_build`는 `Row`·
`SimulationResult`를 직접 만든다 — 새 필드에 기본값을 둔다. 예금 `build_series`를 직접 부르는 테스트는 없다. 프론트엔드 차트 테스트의 응답에는 가격이 없다
(R10-7). `performance-tooltip`을 참조하는 테스트는 없다. 화면 테스트(`CryptoPage`·`DepositPage`·`RealEstatePage`)는 DOM 순서·배치를 검사하지 않는다.

**Decision**: 바뀌는 기존 테스트는 **둘**이다 — `SimulationHistoryList.test.tsx`·`SimulationHistoryBlocked.test.tsx`의 `<SimulationHistory>` 렌더 10곳에
`onRerun` 속성을 더한다(검사 내용은 그대로). 이 밖에 기존 테스트가 실패하면 멈추고 보고한다(006 D2).
