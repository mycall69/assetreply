# Data Model: 013

**Date**: 2026-10-08 | **Research**: [research.md](./research.md)

## 1. DB — 새 테이블 하나 (마이그레이션 하나)

Alembic 리비전 하나(`down_revision = "a6d2f9c41b83"`, 파일 이름 `<rev>_저장한_비교.py`). 기존 테이블은 바뀌지 않는다.

### 1.1 `saved_comparison`

| 열 | 타입 | 제약 | 뜻 |
|----|------|------|----|
| `id` | `BigInteger` | PK, 자동 증가 | API의 `id` |
| `name` | `String(100)` | NOT NULL | 사용자가 붙인 이름 — 앞뒤 공백을 뺀 1~100자. 같은 이름이 여럿일 수 있다 |
| `asset_class` | `Enum("stock","crypto","deposit","realestate", native_enum=False, length=16, name="comparison_asset_class")` | NOT NULL | 자산군 — `condition.asset`과 같다(목록 표시·검증용) |
| `condition` | `Text` | NOT NULL | 비교 조건 — 서버가 정해진 차례로 직렬화한 JSON 글(2절) |
| `saved_at` | `DateTime(timezone=False)` | NOT NULL | 저장 시각(UTC). 목록 차례 |

- 색인 `ix_saved_comparison_list (saved_at, id)` — 목록은 `saved_at` 내림차순, 같은 초는 `id` 내림차순
- 보관 기간이 없다 — 지울 때까지 남는다(명확화 3). `history_setting`·이력 정리와 무관하다
- 금액 열이 없다 — 조건 안의 금액은 받은 글자 그대로의 기록이다(원칙 VI 해석 — plan Complexity Tracking, 012 R12-9 선례)
- 기존 테이블과 외래 키가 없다 — 대상(종목·코인·단지)이 지워지거나 합쳐져도 저장한 비교는 남고, 불러올 때 그 대상이 막힘으로 드러난다(FR-017)

## 2. 비교 조건 — 저장 본문과 화면의 정규 조건

`api/services/comparison_conditions.py`(서버 검증·정규화)와 `lib/compareCondition.ts`(화면의 정규 조건·같음 판정)가 같은 모양을 쓴다.

```json
{
  "v": 1,
  "asset": "stock",
  "method": "lump_sum",
  "frequency": null,
  "start": "2020-01-02",
  "amount": "10000000",
  "principalCurrency": "KRW",
  "reinvest": true,
  "targets": [
    {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
    {"market": "NYSE", "symbol": "XLK", "name": "Technology Select Sector SPDR Fund", "currency": "USD"}
  ]
}
```

| 칸 | 규칙 |
|----|------|
| `v` | `1` — 모양이 바뀌면 올린다 |
| `asset` | `stock`·`crypto`·`deposit`·`realestate` |
| `method` | 주식·가상자산 `lump_sum`·`recurring`, 예금 `deposit`·`installment`, 부동산 `hold` — 짝이 틀리면 거절 |
| `frequency` | `recurring`이면 `daily`·`weekly`·`monthly`·`yearly`, 그 밖은 `null` |
| `start` | `YYYY-MM-DD` — 부동산은 매입일 |
| `amount` | 일시금 원금·적립식 한 번 납입액·정기예금 원금·적금 월 납입액. `[0-9]+(\.[0-9]+)?`, > 0. 예금 둘은 정수. 부동산은 `null` |
| `principalCurrency` | 주식·가상자산 `KRW` 또는 모든 대상의 통화가 같을 때 그 통화. 예금·부동산 `KRW` |
| `reinvest` | 주식만 `true`·`false`, 그 밖은 `null` |
| `targets` | 2~10개, 차례 있음. 예금 ≤5, 정기 적금은 적금 있는 투자처(`commercial_bank`·`mutual_finance`)만. 같은 대상 키가 두 번이면 거절 |

**대상 칸**(표시용 이름을 함께 둔다 — 목록이 대상을 다시 찾지 않고 이름을 보인다)

| 자산군 | 칸 | 대상 키 |
|--------|----|---------|
| 주식 | `market`, `symbol`, `name`, `currency` | `market\|symbol` |
| 가상자산 | `coinId`(정수), `symbol`, `name`, `nameKo`(없으면 `null`), `currency`(시세 통화) | `coinId` |
| 예금 | `institution` | `institution` |
| 부동산 | `complexId`(정수), `name`, `umdName`, `area`(`10`·`20`·`30k`·`30l`·`40`·`50`·`60`), `areaLabel` | `complexId\|area` |

- 직렬화: `json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` — 알려진 칸만 남긴다(012 `history_conditions`와 같은 틀)
- **자동 이름**(화면): `"{자산군} {대상 수}개 · {start} · {방식}"` — 예: `주식 3개 · 2020-01-02 · 일시금`. 사용자가 고친다
- 같음 판정(FR-012a): 정규 조건 둘의 JSON 글이 같은가. 대상 차례가 다르면 다른 조건이다(차례를 바꾸는 기능은 없다 — 빼고 다시 더하면 차례가 바뀐다)

## 3. 비교 경로의 `comparison` 블록

비교 경로 200 응답(contracts/rest-api.md 1)의 한 칸. `api/services/comparison_metrics.py`(순수)가 만든다. 금액은 원화 문자열(지수 표기 없음 — `dec`).

| 키 | 형 | 뜻 |
|----|----|----|
| `asOf` | 날짜 | 그 대상의 기준일 — 메뉴 요약의 `asOf` |
| `isFinal` | bool | 메뉴 요약의 `isFinal` |
| `principal` | `{amount, currency, krw}` | 투자 원금 — 입력 통화 금액과 원화(원화 원금이면 같다). 부동산은 `invested`(매입가 + 취득 비용) |
| `currentValue` | 문자열 \| `null` | 현재 가치(원화) — R13-4 |
| `mainBasis` | `after_sale` \| `holding` \| `unavailable` | 주 값이 무엇인가 — 보드 규칙(R13-4) |
| `profit`, `returnRate` | 문자열 \| `null` | 주 값(표의 투자 수익·수익률) |
| `holding` | `{profit, returnRate}` | 보유 중(매도 전) 값 — 메뉴 요약의 `profit`·`returnRate` |
| `costs` | 객체 | 3.1 |
| `lineEnd` | `{date, holdingReturnRate, afterSaleReturnRate}` | 선 끝 — `date = asOf`, 매도 후는 메뉴가 매도를 가정하는 대상만(그 밖·비움은 `null`) |
| `provisional` | 문자열 목록 | 잠정 까닭 — `unpublished_rate`·`provisional_price`·`estimated_price`·`not_final`. 없으면 빈 목록 |
| `fx` | 객체 \| `null` | 외화 대상만 — `{currency, valuationRate, valuationRateDate, source, exchange}`. `exchange`는 메뉴 응답의 원금 환전(없으면 `null`) |

### 3.1 `costs`

예(해외 주식 일시금 — 금액은 보기):

```json
{
  "total": "113030970",
  "reflected": {"total": "2848444", "items": [
    {"kind": "buy_fee", "amount": "5427"},
    {"kind": "dividend_tax", "amount": "2843017"}
  ]},
  "sale": {"total": "110182526", "items": [
    {"kind": "sale_fee", "amount": "80884"},
    {"kind": "capital_gains_tax", "amount": "110101642"}
  ], "blank": null}
}
```

| 항목 `kind` | 몫 | 자산군 |
|-------------|----|--------|
| `buy_fee` | 반영 | 주식·가상자산 |
| `dividend_tax` | 반영 | 주식 |
| `interest_tax_matured` | 반영 | 예금 둘 — 끝난 회차·만기 계약 |
| `interest_tax_open` | 반영 | 예금 둘 — 진행 중 회차·계약의 경과 이자 |
| `acquisition_tax`·`education_tax`·`rural_tax`·`brokerage_buy` | 반영(`inPrincipal: true`) | 부동산 — 투자 원금에 포함 |
| `property_tax`·`comprehensive_tax` | 반영 | 부동산 |
| `sale_fee` | 매도 | 주식·가상자산 적립식 |
| `transaction_tax`·`capital_gains_tax` | 매도 | 주식 |
| `crypto_tax` | 매도 | 가상자산 적립식 |
| `brokerage_sale`·`transfer_income_tax`·`transfer_local_tax` | 매도 | 부동산 |

- 항목마다 `inPrincipal`(bool)이 늘 있다 — 부동산 취득 비용만 `true`
- 매도 몫이 없는 자산군·방식(가상자산 일시금·예금 둘)은 `sale: null`
- 메뉴가 비우는 항목은 `amount: null`이고 `sale.blank`에 까닭(`outside_rules` 등), `sale.total`·`total`도 `null`(R13-3)
- 원화 환산 버림 규칙은 주식 적립식과 같다(R13-3)
- 참조값: 항목 합 = 그 몫의 `total`, `reflected.total + sale.total = total`. 해외 주식 일시금은 `buy_fee + sale_fee = saleCost.feesKrw`, 적립식 둘은
  `buy_fee = buyFeeTotal`, 정기 적금은 `interest_tax_matured = taxTotal`, 부동산은 `acquisition_tax + … + brokerage_buy = acquisition.total`

## 4. 계산 모듈의 더함 (값은 그대로)

| 모듈 | 더함 | 지키는 것 |
|------|------|-----------|
| `simulation/deposit_rollover.py` | `Summary.accrued_tax: Decimal = 0` — 진행 중 회차의 경과 이자 소득세(평가액에서 빼는 그 값). 만기·멈춤으로 끝나면 0 | 기존 `balance`·`profit`·`returnRate` 불변. `balance = 회차 원금 + 경과 이자 − accrued_tax`(참조값) |
| `simulation/installment_ladder.py` | 요약에 `open_tax: Decimal = 0` — 진행 중 적금 계약·정기예금의 경과 이자 소득세 | 기존 값 불변. 평가액 = 납입·원금 + 경과 이자 − `open_tax`(참조값) |
| `simulation/comparison_costs.py`(신규) | 주식 일시금 행에서 매수 수수료·배당 소득세 원화 합, 가상자산 일시금 매수 수수료 원화 | 버림 규칙 = 주식 적립식(R13-3) |
| `simulation/fx_convert.py` | `RateLookup`에 정렬된 날짜 튜플, `resolve_rate`의 빗나감 경로를 이분 탐색으로 | 돌려주는 환율·쓴 날짜가 옛 방식과 같다(R13-13) |

## 5. 화면 상태 — `stores/compareStore.ts`

| 칸 | 형 | 뜻 |
|----|----|----|
| `asset` | `"stock" \| "crypto" \| "deposit" \| "realestate"` | 처음 `stock` |
| `method` | 2절의 `method` | 처음 `lump_sum`(부동산 `hold`, 예금 `deposit`) |
| `frequency` | `Frequency` | 적립식 주기 — 처음 `monthly` |
| `start` | 문자열 | 처음 `DEFAULT_START` |
| `amount` | 문자열 | 처음 `DEFAULT_PRINCIPAL`(`"10000000"`) |
| `principalCurrency` | `"KRW" \| "USD" \| "JPY"` | 처음 `KRW`. 고를 수 있는 통화는 대상에서 정한다 — 원화 + 모든 대상의 통화가 같을 때 그 통화 |
| `reinvest` | bool | 처음 `true` |
| `targets` | 대상 칸 목록(2절) | 차례 있음, 최대 10 |
| `run` | `RunState \| null` | 아래 |
| `saved` | 저장 슬라이스 | 5.2 |

### 5.1 `RunState`

| 칸 | 뜻 |
|----|----|
| `seq` | 실행 차례 번호 — 늦은 응답·스트림 사건을 버리는 기준(R13-7) |
| `condition` | 결과를 낸 정규 조건 — 흐림(`isStale`)·저장의 기준 |
| `byTarget` | 대상 키 → 대상 상태 |

**대상 상태** — `requesting` → `ok` \| `collecting` \| `blocked` \| `failed`

| 상태 | 내용 | 다음 |
|------|------|------|
| `requesting` | — | 응답에 따라 |
| `ok` | 비교 경로 200 본문(`summary`·`series`·`comparison`) | 끝 |
| `collecting` | 202 본문, 진행(스냅숏), 연달은 202 횟수 | 스트림 완료 → `requesting`. 스트림 실패·한도 초과 → `failed` |
| `blocked` | 갈래(`start` \| `remove` \| `too_late`), 까닭 코드·문구, 날짜(`startableFrom`·`availableFrom`·`lastDay`·`month`) | 끝(조건을 바꿔 다시 실행) |
| `failed` | 까닭 문구 | "다시 시도" → `requesting` |

**비교 전체**(파생 — `lib/compareBlock.ts`)

| 상태 | 판정 | 화면 |
|------|------|------|
| `blocked` | 막힌 대상이 하나라도 있다 | 결과를 보이지 않는다. 막힌 대상 목록·제안(수집 중인 대상이 없을 때만) |
| `partial` | 막힘 없음, `ok`가 아닌 대상이 있다 | `ok` 대상만 표·그래프, 나머지는 줄에 "수집 중"·"수집 실패" |
| `complete` | 모두 `ok` | 표·그래프 |
| `stale` | 위 어느 것이든 + 지금 조건 ≠ `run.condition` | 결과를 흐리고 "조건이 바뀜 — 다시 실행"(FR-012a). 저장 막힘 |

### 5.2 저장한 비교 슬라이스

| 칸 | 뜻 |
|----|----|
| `entries` | `{id, name, asset, condition, savedAt}` 목록 — 서버 차례 그대로 |
| `loading` / `loadError` | 목록 받기 상태 — 실패하면 문구 + 다시 시도(012 `HistoryContent`) |
| `saveError` / `removeError` | 저장·삭제 실패 문구 — 결과는 그대로(FR-019) |
| `saving` | 이름 칸 열림·보내는 중 |
