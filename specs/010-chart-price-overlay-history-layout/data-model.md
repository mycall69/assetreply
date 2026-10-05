# Data Model: 성과 추이 차트의 가격 선·차트 위 값 표시와 최근 시뮬레이션 배치

**Feature**: `010-chart-price-overlay-history-layout` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**DB 변경 없음** — 새 테이블·열·마이그레이션이 없다. 가격은 이미 저장된 시세·금리·실거래에서 계산 결과로 나온 값이다(research R10-1). 바뀌는 것은
메모리 안의 결과 형식(백엔드), 시계열 응답(contracts/rest-api.md), 화면의 파생 값(프론트엔드)이다. 이력 저장 형식은 바꾸지 않는다(FR-021).

---

## 1. 백엔드 — 계산 결과에 실을 것

| 형식 | 더하는 필드 | 출처 | 기본값 |
|------|-------------|------|--------|
| `stock_simulation.SimulationResult` | `splits: tuple[SplitOn, ...]` | `run_simulation`이 이미 읽는 `price_repo.splits(stock_id, start, end)` | `()` — 결과를 직접 만드는 테스트(`test_stock_series_build`)를 위해 |
| `deposit_simulation.Prepared` | `rates: Mapping[date, Decimal]`(달 1일 → 연 %), `latest_month: date`(마지막 발표 달) | `prepare`가 이미 읽는 `deposit_rate.get_rates`·`get_coverage` | 없음 — `Prepared`를 만드는 곳은 `prepare`·`simulate_or_collect` 둘뿐이고 둘 다 넘긴다 |

`SplitOn`은 시뮬레이터의 기존 형식(`date`·`numerator`·`denominator`)이다 — 새 형식을 만들지 않는다.

## 2. 백엔드 — 시계열 점

네 조립 함수의 `SeriesPoint`에 필드를 더한다. **한 점의 모든 값은 같은 날의 것이다**(FR-007) — 점은 지금처럼 날짜로 통째로 고른다(R10-3).

| 자산군 | `price` | `price_missing` | 그 밖 |
|--------|---------|-----------------|-------|
| 주식 | `Decimal` — 그 날 마지막 행의 `Row.open_price`(원주가 시가, 종목 통화). 늘 있다. 점은 표의 행 날짜뿐(일별 아님 — spec FR-001) | 없음 | — |
| 가상자산 | `Decimal` — `daily[i].row.open_price`(시세 통화). 늘 있다(점은 일봉이 있는 날만) | 없음 | — |
| 예금 | `Decimal \| None` — 점 날짜의 달 `m`: `m > latest_month` → `None`, `m ∉ rates` → `None`, 아니면 `rates[m]` | `"unpublished"`(`m > latest_month`) · `"missing"`(`m ∉ rates`) · `None` | — |
| 부동산 | `int \| None` — 그 점이 나온 행의 `month_average`. 첫 점(매입일)은 매입 달 행, 끝점(계산 끝)은 그 달 행(`rows[0]`) | `"no_trades"`(`month_average is None`) · `None` | `profit: int` — 행의 `profit`, 끝점은 `summary.profit` |

시계열 형식에 더하는 것:

| 형식 | 필드 |
|------|------|
| `StockSeries` | `splits: tuple[SplitOn, ...]` — `start ≤ date ≤ end`, 효력일 오름차순 |
| `DepositSeries` | 없음(점의 필드만) — `build_series(outcome, *, start, rates, latest_month)`. 새 인자는 **필수**(R10-5) |

**불변식**:

- `price is None` ⇔ `price_missing is not None`.
- 주식·가상자산의 `price`는 `None`이 아니다 — `None`이면 조립이 틀린 것이다(단위 테스트).
- 예금의 `price`(값이 있을 때)는 같은 달에 시작한 가입·재예치 행의 적용 금리(`Row.rate`, 잠정이 아닌 행)와 같다(FR-002).
- 부동산의 `price`(값이 있을 때)는 같은 달 행의 `month_average`와 같다. 시세 없음 달은 점이 없다(지금과 같다 — `gaps`의 `no_price`).
- `gaps`는 바뀌지 않는다 — 가격만 없는 날을 넣지 않는다(R10-2).

## 3. 프론트엔드 — 응답 형식 (`lib/types.ts`)

```text
PriceKind     = "stock_open" | "crypto_open" | "deposit_rate" | "apt_average"
PriceMissing  = "unpublished" | "missing" | "no_trades"
SplitMark     = { date: string; numerator: number; denominator: number }

SimulationPoint (+)
  price?: DecimalString | null        # 가격이 있는 응답(010)에만 키가 있다
  priceMissing?: PriceMissing         # price가 null일 때만
  profit?: DecimalString              # 부동산만 — 투자 수익(원)

SimulationSeriesResponse (+)
  priceKind?: PriceKind
  priceCurrency?: string | null       # 예금은 null
  splits?: SplitMark[]                # 주식만
```

모두 **선택 키**다 — 기존 테스트 응답(가격 없음)이 타입 검사를 그대로 통과하고, 차트는 가격 키가 없으면 지금과 같이 그린다(R10-7).

## 4. 프론트엔드 — 파생 값 (순수 함수, `lib/chartSeries.ts`·`lib/chartHover.ts`)

| 이름 | 입력 → 출력 | 규칙 |
|------|-------------|------|
| `priceSegments(points, gaps)` | 점 → 가격 선 구간들 | `splitSeriesAtGaps`(잔고와 같은 자리) → `price === null`인 점에서 다시 끊음. 점 하나뿐인 구간도 남긴다(점으로 그린다) |
| `splitMarks(points, splits)` | 분할마다 표식 점 | 그린 점 중 `date ≥ split.date`인 첫 점. 없으면 그 분할은 표식이 없다. 같은 점에 둘이면 하나의 표식에 둘 다 |
| `gapSlots(points, gaps)` | 값 없는 자리(구간마다 하나) | 첫 점 ~ 끝 점 안의 `source_missing`·`no_price` **구간마다 `from` 하나**(그 구간의 `from`·`to`·사유를 함께). 점 범위 밖 구간·그 밖의 사유(`no_quote`·`not_collected`)는 자리를 두지 않는다. 날마다 두지 않는다 — 줄인 차트에서 구간이 과장된다(research R10-8) |
| `hoverView(series, time)` | 커서 자리 → 상자 내용 | 아래 표. 점이 없고 자리면 사유 |
| `placeHover(point, box, area)` | 좌표 → 상자 왼쪽·위 | 오른쪽 아래 12px, 넘치면 왼쪽·위로. 늘 `0 ≤ left ≤ area.width − box.width`, `0 ≤ top ≤ area.height − box.height` |

**상자 내용(`HoverView`)** — 줄의 순서와 형식(R10-9 — 표와 같은 형식 함수):

| 자산군 | 줄 |
|--------|----|
| 주식 | 날짜 · 주가 `$182.40`(분할 표식 점이면 "분할 1→4 (2020-08-31 효력)") · 잔고 `₩12,345,678` · 수익률 |
| 가상자산 | 날짜 · 시세 `$0.0000053` · 잔고 `₩…` · 수익률 |
| 예금 | 날짜 · 잔고 `₩…` · 수익률 · 금리 `연 3.45%` / "— 미발표" / "— 결측" |
| 부동산 | 달(첫 점·끝 점은 날짜) · 평가액 `₩…` · 투자 수익 `₩…` · 수익률 · 실거래가 평균 `₩…` / "— 거래 없음" |
| (자리) | 구간 `from ~ to`(부동산은 달) · 모든 값 "—" · 사유 "출처 결측"(가상자산) / "시세 없음"(부동산) |

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
