# Data Model: 성과 추이 차트의 가격 선·차트 위 값 표시와 최근 시뮬레이션 배치

**Feature**: `010-chart-price-overlay-history-layout` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**DB 변경 없음** — 새 테이블·열·마이그레이션이 없다. 가격은 이미 저장된 시세·금리·실거래에서 계산 결과로 나온 값이다(research R10-1). 바뀌는 것은
메모리 안의 결과 형식(백엔드), 시계열 응답(contracts/rest-api.md), 화면의 파생 값(프론트엔드)이다. 이력 저장 형식은 바꾸지 않는다(FR-021).

---

## 1. 백엔드 — 계산 결과에 실을 것

| 형식 | 더하는 필드 | 출처 | 기본값 |
|------|-------------|------|--------|
| `stock_simulation.SimulationResult` | `splits: tuple[SplitOn, ...]` | `run_simulation`이 이미 읽는 `price_repo.splits(stock_id, start, end)` | `()` — 결과를 직접 만드는 테스트(`test_stock_series_build`)를 위해 |
| `stock_simulation.SimulationResult`(반복 1) | `closes: Mapping[date, Decimal]` — 날짜별 **원주가 종가**(`close_raw`) | `run_simulation`이 이미 읽는 `price_repo.prices`의 `close_raw` | 빈 매핑 — 위와 같은 이유 |
| `deposit_simulation.Prepared` | `rates: Mapping[date, Decimal]`(달 1일 → 연 %), `latest_month: date`(마지막 발표 달) | `prepare`가 이미 읽는 `deposit_rate.get_rates`·`get_coverage` | 없음 — `Prepared`를 만드는 곳은 `prepare`·`simulate_or_collect` 둘뿐이고 둘 다 넘긴다 |

`SplitOn`은 시뮬레이터의 기존 형식(`date`·`numerator`·`denominator`)이다 — 새 형식을 만들지 않는다. 반복 1부터 `splits`는 수정 종가 계산에만 쓰고 응답에
싣지 않는다.

## 2. 백엔드 — 시계열 점

네 조립 함수의 `SeriesPoint`에 필드를 더한다. **한 점의 모든 값은 같은 날의 것이다**(FR-007) — 점은 지금처럼 날짜로 통째로 고른다(R10-3).

| 자산군 | `price` | `price_missing` | 그 밖 |
|--------|---------|-----------------|-------|
| 주식 | `Decimal` — 그 날의 **분할만 반영한 수정 종가**(반복 1): `closes[date] ÷ ∏(numerator/denominator)` — 곱은 `date < 효력일 ≤ end`인 분할 전부(효력일 당일 이후의 종가는 이미 분할 뒤 값). 종목 통화. 늘 있다. 점은 표의 행 날짜뿐(일별 아님 — spec FR-001). 처음(반복 전)은 `Row.open_price`(원주가 시가) | 없음 | — |
| 가상자산 | `Decimal` — `daily[i].row.open_price`(시세 통화). 늘 있다(점은 일봉이 있는 날만) | 없음 | — |
| 예금 | `Decimal \| None` — 점 날짜의 달 `m`: `m > latest_month` → `None`, `m ∉ rates` → `None`, 아니면 `rates[m]` | `"unpublished"`(`m > latest_month`) · `"missing"`(`m ∉ rates`) · `None` | — |
| 부동산 | `int \| None` — 그 점이 나온 행의 `month_average`. 첫 점(매입일)은 매입 달 행, 끝점(계산 끝)은 그 달 행(`rows[0]`) | `"no_trades"`(`month_average is None`) · `None` | `profit: int` — 행의 `profit`, 끝점은 `summary.profit` |

시계열 형식에 더하는 것:

| 형식 | 필드 |
|------|------|
| `StockSeries` | ~~`splits`~~ — 반복 1에서 응답에서 뺐다(분할 표식 없음). 수정 종가는 조립 안에서 결과의 `splits`로 계산한다 |
| `DepositSeries` | 없음(점의 필드만) — `build_series(outcome, *, start, rates, latest_month)`. 새 인자는 **필수**(R10-5) |

**불변식**:

- `price is None` ⇔ `price_missing is not None`.
- 가상자산의 `price`는 `None`이 아니다. 주식은 그 날 원주가 종가가 없을 때만 `None` + `missing`이다(반복 1 — 지어내지 않는다). 실제 경로에서는 점이 거래일이라 늘 있고(통합 테스트), 결과를 직접 만드는 005 단위 테스트에서만 생긴다.
- 주식의 `price`는 분할 앞뒤에서 원주가 종가의 변동만큼만 바뀐다 — 분할 비율만큼 꺾이지 않는다(반복 1). 분할이 없으면 원주가 종가 그대로다.
- 수정 종가는 계산할 때마다 구하고 저장하지 않는다(원칙 V — 명시 규칙, 원본은 원주가·분할 기록).
- 예금의 `price`(값이 있을 때)는 같은 달에 시작한 가입·재예치 행의 적용 금리(`Row.rate`, 잠정이 아닌 행)와 같다(FR-002).
- 부동산의 `price`(값이 있을 때)는 같은 달 행의 `month_average`와 같다. 시세 없음 달은 점이 없다(지금과 같다 — `gaps`의 `no_price`).
- `gaps`는 바뀌지 않는다 — 가격만 없는 날을 넣지 않는다(R10-2).

## 3. 프론트엔드 — 응답 형식 (`lib/types.ts`)

```text
PriceKind     = "stock_adjusted_close" | "crypto_open" | "deposit_rate" | "apt_average"   # 반복 1: stock_open → stock_adjusted_close
PriceMissing  = "unpublished" | "missing" | "no_trades"
(반복 1에서 제거: SplitMark)

SimulationPoint (+)
  price?: DecimalString | null        # 가격이 있는 응답(010)에만 키가 있다
  priceMissing?: PriceMissing         # price가 null일 때만
  profit?: DecimalString              # 부동산만 — 투자 수익(원)

SimulationSeriesResponse (+)
  priceKind?: PriceKind
  priceCurrency?: string | null       # 예금은 null
  (반복 1에서 제거: splits?)
```

모두 **선택 키**다 — 기존 테스트 응답(가격 없음)이 타입 검사를 그대로 통과하고, 차트는 가격 키가 없으면 지금과 같이 그린다(R10-7).

## 4. 프론트엔드 — 파생 값 (순수 함수, `lib/chartSeries.ts`·`lib/chartHover.ts`)

| 이름 | 입력 → 출력 | 규칙 |
|------|-------------|------|
| `priceSegments(points, gaps)` | 점 → 가격 선 구간들 | `splitSeriesAtGaps`(잔고와 같은 자리) → `price === null`인 점에서 다시 끊음. 점 하나뿐인 구간도 남긴다(점으로 그린다) |
| ~~`splitMarks(points, splits)`~~ | — | 반복 1에서 없앴다(분할 표식 없음 — spec FR-008) |
| `gapSlots(points, gaps)` | 값 없는 자리(구간마다 하나) | 첫 점 ~ 끝 점 안의 `source_missing`·`no_price` **구간마다 `from` 하나**(그 구간의 `from`·`to`·사유를 함께). 점 범위 밖 구간·그 밖의 사유(`no_quote`·`not_collected`)는 자리를 두지 않는다. 날마다 두지 않는다 — 줄인 차트에서 구간이 과장된다(research R10-8) |
| `hoverView(series, time)` | 커서 자리 → 상자 내용 | 아래 표. 점이 없고 자리면 사유 |
| `placeHover(point, box, area)` | 좌표 → 상자 왼쪽·위 | 오른쪽 아래 12px, 넘치면 왼쪽·위로. 늘 `0 ≤ left ≤ area.width − box.width`, `0 ≤ top ≤ area.height − box.height` |

**상자 내용(`HoverView`)** — 줄의 순서와 형식(R10-9 — 표와 같은 형식 함수):

| 자산군 | 줄 |
|--------|----|
| 주식 | 날짜 · 주가(수정 종가) `$182.40` · 잔고 `₩12,345,678` · 수익률 — 반복 1: 줄 이름에 "수정 종가", 분할 문구(`notes`) 없음 |
| 가상자산 | 날짜 · 시세 `$0.0000053` · 잔고 `₩…` · 수익률 |
| 예금 | 날짜 · 잔고 `₩…` · 수익률 · 금리 `연 3.45%` / "— 미발표" / "— 결측" |
| 부동산 | 달(첫 점·끝 점은 날짜) · 평가액 `₩…` · 투자 수익 `₩…` · 수익률 · 실거래가 평균 `₩…` / "— 거래 없음" |
| (자리) | 구간 `from ~ to`(부동산은 달) · 모든 값 "—" · 사유 "출처 결측"(가상자산) / "시세 없음"(부동산) |

`HoverView.notes`는 반복 1에서 뺐다(분할 문구가 유일한 쓰임이었다).

## 5. 최근 시뮬레이션 항목 — 바꾸지 않는다

| 자산군 | 저장 키 | 다시 실행이 쓰는 필드 |
|--------|---------|------------------------|
| 주식 | 006의 키 그대로 | `stock`(시장·종목코드·이름·통화) · `start` · `principal` · `principalCurrency` · `reinvest` — 이미 다 있다. 등록 요청을 다시 보내지 않는다 — 이력의 종목은 이미 등록되어 있다(research R10-11) |
| 가상자산·예금·부동산 | 007~009의 키 그대로 | 지금의 다시 실행 그대로 |

이미 저장된 이력은 그대로 열리고 다시 실행된다(FR-021). 006 이전의 막힌 조합 항목도 형식이 같다 — 다시 실행은 지금 규칙으로 거절한다(FR-019).

## 6. 배치 (`components/TableWithHistory.tsx`)

| 칸 | 규칙 |
|----|------|
| 바깥 | `flex flex-wrap items-start gap-5` |
| 표 칸 | `flex: 0 1 auto` — 기본 크기 = 표 고유 폭, 늘지 않는다(늘면 표와 이력 사이에 빈 칸이 생겨 이력이 화면 끝에 붙는다 — T036 실측으로 고침). `min-w-0` — 줄은 기본 크기로 나뉘므로 나란히 둔 표는 줄지 않고, 표 하나도 담지 못하는 좁은 창에서는 표 안에서 가로 스크롤한다(없으면 화면이 넘친다 — 구현 중 고침). 결과가 없으면 없다 |
| 이력 칸 | `flex: 1 1 400px`(400px부터 남는 폭을 가져간다 — 표 바로 오른쪽, 아래로 내려가면 전체 폭), `sticky top-4 self-start`, `max-height: calc(100vh − 2rem)`, 세로 스크롤 |
| 이력 행(네 화면) | `flex-wrap` — 칸이 좁으면 버튼 묶음이 다음 줄로. 칸 안 가로 넘침 없음 |

경계 폭은 상수가 아니다 — 두 칸의 기본 크기 합이 본문 폭을 넘으면 이력이 다음 줄(전체 폭)로 내려간다(R10-10).

## 7. 외부 페이지 링크 (반복 1, `lib/externalLinks.ts`)

저장하지 않고 외부를 부르지 않는다 — 자산의 식별에서 규칙으로 URL을 만든다. 모든 링크는 `<a target="_blank" rel="noopener noreferrer">`이고, 이력 행 안의
링크는 누를 때 행의 고르기·다시 실행을 일으키지 않는다.

| 자산 | 입력 | URL 규칙 |
|------|------|----------|
| 국내 주식(`KRX`) | 종목코드 `005930.KS`·`091990.KQ` | `https://stock.naver.com/domestic/stock/{접미사를 뺀 6자리}/price` |
| 미국 주식(`NASDAQ`) | 티커 `NVDA` | `https://stock.naver.com/worldstock/stock/{티커}.O/price` |
| 미국 주식(`NYSE`) | 티커 `KO` | `https://stock.naver.com/worldstock/stock/{티커}/price`(접미사 없음 — T040) |
| 미국 주식(`AMEX`) | 티커 `IOSX` | `https://stock.naver.com/worldstock/stock/{티커}.K/price`(T040) |
| 일본(`TSE`) | `7203.T` | `https://stock.naver.com/worldstock/stock/{저장소 심볼 그대로}/price`(T040) |
| 그 밖의 시장 | — | 링크 없음(이름만) |
| 가상자산 | 심볼 `BTC` | `https://stock.naver.com/crypto/UPBIT/{심볼}/price` — 늘 UPBIT(업비트에 없는 코인은 네이버 증권 홈으로 간다 — R10-14 한계) |
| 부동산 단지 | 법정동 이름·단지명 | 네이버 통합검색 `https://search.naver.com/search.naver?query={법정동} {단지명}`(URL 인코딩) — 맨 위 단지 카드가 네이버 부동산 단지 화면으로 이어진다(R10-15). 법정동 이름을 모르면 `{단지명}` |

대상 자리: 주식 — 고른 종목 줄(`StockSearch`), 이력 행(`SimulationHistory`). 가상자산 — 고른 코인 표시(`CoinSearch`), 이력 행(`CryptoHistory`).
부동산 — 보드의 단지 이름(`RealEstateBoard`), 이력 행(`RealEstateHistory`). 검색 목록 항목(옵션)은 링크가 아니다(고르기 그대로).
부동산 이력 항목에는 법정동 **코드**(`umd`)와 단지명만 있다 — 지금 받아 둔 행정구역(`regions.umd`)에 그 코드가 있으면 이름을 쓰고, 없으면 단지명만(R10-15, 저장 형식 불변 — FR-021).

## 8. 반복 3 (2026-10-06)

### 8.1 주식 계산의 하루 시세와 행 (FR-028, research R10-18)

```text
DayBar  = (date, open_price: Decimal, close_price: Decimal)   # 원주가. 종가는 필수 — 없으면 그 일봉을 쓰지 않는다(원칙 V)
Row    += close_price: Decimal | None = None                   # 그 행 날짜의 원주가 종가 — 계산이 만든 행에는 늘 있다(기본값은 행을 직접 만드는 005 테스트 때문, 잔고는 DayBar의 종가로 계산)
Row.balance = held_shares × close_price                        # 005 FR-013(× open_price)을 대체
Row.profit  = balance + cash − principal                       # 식은 그대로, 잔고가 종가 평가
매수 수량·매수 금액·수수료·배당율(÷ open_price)                 # 그대로 시가
```

표 응답 행 `closePrice`(문자열) · 프론트엔드 `SimulationRow.closePrice: DecimalString`(필수) · 표 열 "종가"(시작가 바로 뒤, 종목 통화 — 시작가와 같은 형식
`formatRate`).

### 8.2 Npay 부동산 단지 번호 (FR-029, research R10-19)

```text
apt_complex_naver                       # 단지 하나에 한 행. 마이그레이션으로 만든다
  complex_id        BIGINT  PK, FK apt_complex.id
  status            VARCHAR(16)  'found' | 'not_found'          # 실패는 행을 만들지 않는다
  naver_complex_no  INT     NULL                                 # found일 때만
  naver_name        VARCHAR(120) NULL                            # 고른 후보의 이름(대조용)
  keyword           VARCHAR(160) NOT NULL                        # 마지막으로 보낸 검색어
  checked_at        DATETIME NOT NULL                            # UTC — 못 찾음 다시 찾기의 기준
  raw_response      MEDIUMTEXT NULL                              # 고른(또는 마지막) 응답 본문 그대로
  source            VARCHAR(32) NOT NULL  'naver_land_autocomplete'
  ingested_at       DATETIME NOT NULL
```

- 어댑터가 내보내는 후보: `NaverComplexCandidate(number: int, name: str, legal_division_code: str, type: str)` — 출처 키 이름(`complexNumber` 등)은 어댑터 밖으로
  나가지 않는다.
- 고르기 `pick_naver_complex(candidates, umd_code, name) -> NaverComplexCandidate | None` — 순수 함수. 정규화: 공백 제거, 괄호와 그 안 제거, 끝의 "아파트" 제거.
  ① 같은 법정동 코드 ② 정규화한 이름이 같은 후보가 하나 ③ 없으면 한쪽이 다른 쪽을 품는 후보가 하나 ④ 그 밖은 `None`.
- 화면: 단지 이름 링크(`components/realestate/ComplexLink.tsx`)는 처음에 FR-026의 검색 주소이고, 이 경로가 `found`를 주면 응답의 `url`(Npay 부동산 단지 화면)로 바뀐다
  (주소는 백엔드 한 곳에서 만든다 — 화면에 같은 규칙을 두지 않는다).
  접근 이름은 바뀐 뒤 `{단지명} Npay 부동산에서 보기`, 그 전·못 찾음·실패는 `{단지명} 네이버에서 단지 찾기`. 같은 쪽 안에서 단지마다 한 번만 묻는다.

