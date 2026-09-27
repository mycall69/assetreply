# Data Model: 주식 투자 시뮬레이션

**Feature**: 005-stock-investment-simulation | **Date**: 2026-09-27

헌법 시계열 불변식을 따른다 — `(자산 식별자, 날짜)` 복합 유니크 키와 upsert, 모든
레코드에 `source`·`ingested_at`, 원본과 정규화의 분리 저장, **수정주가와 원주가의 구분**.

금액·비율 컬럼은 전부 `DECIMAL`이다. `FLOAT`/`DOUBLE`은 곧바로 원칙 VI 위반이다.

---

## 1. 신규 테이블

### `stock` — 종목

사용자가 검색해 고른 종목만 들어온다. 전체 목록을 미리 쌓지 않는다 (research R5-2).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `BIGINT` | PK | |
| `market` | `VARCHAR(8)` | NOT NULL | `KRX` · `NASDAQ` · `NYSE` · `TSE` 등 |
| `symbol` | `VARCHAR(32)` | NOT NULL | 출처가 쓰는 식별자 |
| `name` | `VARCHAR(128)` | NOT NULL | 표시용 이름 |
| `currency` | `CHAR(3)` | NOT NULL | 거래 통화. 환전 여부와 수익률 기준을 가른다 |
| `first_available_date` | `DATE` | NULL 허용 | 출처가 값을 주기 시작한 날. 수집 중 발견해 기록 |
| `delisted_through` | `DATE` | NULL 허용 | 시세가 끊긴 날. FR-014a의 근거 |
| `ingested_at` | `DATETIME` | NOT NULL | |

**유니크**: `(market, symbol)`

`currency`를 종목에 두는 이유는 시장과 통화가 1:1이 아닐 수 있기 때문이다. 종목마다
확정해 두면 환산 경로가 행 단위로 흔들리지 않는다.

### `stock_price` — 일별 시세

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `stock_id` | `BIGINT` | PK 일부, FK | |
| `quote_date` | `DATE` | PK 일부 | 거래소 현지 날짜 |
| `open_raw` | `DECIMAL(20,6)` | NOT NULL | **원주가 시가.** 시뮬레이션의 매수가 |
| `close_raw` | `DECIMAL(20,6)` | NOT NULL | **원주가 종가** |
| `close_adjusted` | `DECIMAL(20,6)` | NULL 허용 | **수정종가.** 보관만 하고 계산에 쓰지 않는다 |
| `source` | `VARCHAR(64)` | NOT NULL | |
| `ingested_at` | `DATETIME` | NOT NULL | |

**유니크**: `(stock_id, quote_date)` — 복합 PK가 곧 이것이다. upsert로 멱등성을 얻는다.

**원주가와 수정주가를 나란히 두되 계산은 원주가만 쓴다**(FR-011, FR-012). 섞으면 배당이
이중 계산되는데 값은 그럴듯하다.

수정종가는 **나중에 배당·분할이 생기면 과거 값이 바뀐다.** 재현성(FR-014)이 원주가에
기대는 근거다 (research R5-3).

### `stock_dividend` — 배당 이벤트

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `stock_id` | `BIGINT` | PK 일부, FK | |
| `ex_date` | `DATE` | PK 일부 | 배당락일. 이 기능은 이날을 지급 시점으로 다룬다 |
| `amount_per_share` | `DECIMAL(20,6)` | NOT NULL | **세전** 주당 배당금 |
| `source` | `VARCHAR(64)` | NOT NULL | |
| `ingested_at` | `DATETIME` | NOT NULL | |

**세전 금액을 저장한다.** 세율은 설정이라 바뀌며(FR-016), 세후를 저장하면 세율을 바꿨을 때
과거 행이 낡는다 — FR-017이 요구하는 재산출이 불가능해진다.

같은 날 여러 배당이 오면 합산해 한 행으로 둔다 (spec Assumptions).

### `stock_split` — 분할·병합 이벤트

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `stock_id` | `BIGINT` | PK 일부, FK | |
| `effective_date` | `DATE` | PK 일부 | 적용일 |
| `numerator` | `INT` | NOT NULL | 분할 후 |
| `denominator` | `INT` | NOT NULL | 분할 전 |
| `source` | `VARCHAR(64)` | NOT NULL | |
| `ingested_at` | `DATETIME` | NOT NULL | |

**비율을 분자·분모 정수로 보관한다.** 소수로 저장하면 3:1 분할이 `0.333333…`이 되어
보유 주식 수 계산에 오차가 들어간다.

병합(역분할)은 `numerator < denominator`다.

이 테이블이 **FR-010b가 요구하는 "적용한 이벤트의 기록"**이다. 제공처를 그대로 믿기로
했으므로(FR-010a), 틀렸을 때 되짚을 수단이 이것뿐이다.

### `stock_raw_response` — 원본 응답

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `BIGINT` | PK | |
| `stock_id` | `BIGINT` | FK, NULL 허용 | 검색 응답은 종목이 아직 없다 |
| `kind` | `VARCHAR(16)` | NOT NULL | `search` · `chart` |
| `requested_from` | `DATE` | NULL 허용 | |
| `requested_to` | `DATE` | NULL 허용 | |
| `body` | `MEDIUMTEXT` | NOT NULL | |
| `status_code` | `INT` | NOT NULL | |
| `received_at` | `DATETIME` | NOT NULL | |

001이 `fx_raw_response`에서 `TEXT`(65,535바이트)를 넘겨 `MEDIUMTEXT`로 넓혀야 했다.
주식 일봉은 한 번에 수천 행이 오므로 **처음부터 `MEDIUMTEXT`로 둔다.**

### `stock_coverage` — 수집 구간

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `stock_id` | `BIGINT` | PK, FK | |
| `covered_from` | `DATE` | NOT NULL | |
| `covered_through` | `DATE` | NOT NULL | |
| `updated_at` | `DATETIME` | NOT NULL | |

FR-044의 "빠진 구간만 받는다"와 FR-045의 재개가 이것에 기댄다. `fx_coverage`와 **합치지
않는다** — 그쪽은 통화 단위이고 여기는 종목 단위다 (research R5-7).

### `stock_collection_job` · `stock_collection_lock`

003이 `fx_collection_job`·`fx_collection_lock`에서 만든 모양을 그대로 잇되 종목 단위로
둔다. 점유는 **자산군을 가로질러 공유하지 않는다** — FX 수집 중에 주식 수집을 막을
이유가 없고 출처가 달라 호출 한도도 따로다.

### `stock_setting` — 수수료·세율

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `TINYINT` | PK, 항상 1 | 전역 단일 행 |
| `trade_fee_rate` | `DECIMAL(10,6)` | NOT NULL | 기본 `0.000150` (0.015%) |
| `dividend_tax_rate` | `DECIMAL(10,6)` | NOT NULL | 기본 `0.154000` (15.4%) |
| `updated_at` | `DATETIME` | NOT NULL | |

`fx_spread`는 통화별이지만 이쪽은 **전역 하나**다. 시장별로 수수료가 다른 것이 현실이지만
명세가 하나로 받는다(FR-015).

---

## 2. 저장하지 않는 것

**시뮬레이션 결과 행을 저장하지 않는다** (research R5-9).

결과는 시세·배당·분할·설정·환율의 함수이고 **설정과 환율이 바뀐다.** FR-017이 "설정이
바뀌면 다시 제시되어야 한다"를 요구하므로, 저장하면 갱신 시점을 관리해야 하고 그 관리가
틀리면 조용히 낡은 값을 보여준다.

**이력은 브라우저에 둔다** (FR-037, research R5-10). 서버 테이블이 아니다.

---

## 3. 시뮬레이션 행 (파생)

질의 결과에서 만든다.

| 필드 | 설명 |
|------|------|
| `date` | **실제 거래일** (FR-028) |
| `kind` | `month_first` · `dividend` — 행의 종류 (FR-025) |
| `openPrice` | 그날 시가 (원주가) |
| `dividendPerShare` | 주당 배당금. 월 행은 **없음**(0이 아니라 키 없음, FR-026) |
| `dividendYield` | 배당율. 같은 규칙 |
| `boughtShares` | 그 행에서 산 주식 수 |
| `heldShares` | 보유 주식 수 |
| `cash` | 예수금 |
| `principal` | 투자금 |
| `balance` | 보유 주식 수 × 시가. **예수금 미포함** (FR-013) |
| `profit` | 총자산 − 투자금 |
| `returnRate` | 수익률 |
| `fxRate` | 이 행의 평가 환산에 쓴 환율 (외화 종목일 때) |
| `fxRateDate` | 그 환율의 날짜. 기준일과 다를 수 있다 (FR-041c) |

**월 행의 배당 칸은 키를 생략한다.** 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수
없다 — 002·003·004가 세운 규약과 같다.

---

## 4. 정밀도 규칙

research R5-5를 표로 고정한다. **한 곳에 두고 참조한다** — 흩뿌리면 한 군데만 틀려도 그
통화만 조용히 어긋난다.

| 값 | 규칙 |
|----|------|
| 매수 수량 | `Decimal` 나눗셈 후 **버림**. 올림하면 예수금이 음수가 된다 |
| KRW·JPY 금액 | 소수 0자리. 원화·엔화에 소수점 금액은 존재하지 않는다 |
| USD·EUR 금액 | 소수 2자리 |
| 수익률·배당율 | 소수 6자리 |
| 가격·배당금 저장 | `DECIMAL(20,6)` — 출처가 주는 정밀도를 깎지 않는다 |

**반올림은 표시 직전 한 번만** 한다. 중간마다 하면 60년치에서 누적이 눈에 띈다.

---

## 5. 매수 수량 산식

FR-007a를 식으로 고정한다.

```
수량 = ⌊ 예수금 ÷ (시가 × (1 + 수수료율)) ⌋
지출 = 수량 × 시가 × (1 + 수수료율)
예수금 ← 예수금 − 지출
```

**수수료를 포함한 총액이 예수금을 넘지 않는다.** 수량을 시가로만 정하고 수수료를 나중에
빼면 남은 돈보다 수수료가 클 때 **예수금이 음수가 된다**.

---

## 6. 환율 적용

| 시점 | 환율 | 근거 |
|------|------|------|
| 초기 환전 (1회) | **현금 살 때**, 스프레드의 10%만 적용 | FR-019, FR-020 — 실제로 돈을 바꾼다 |
| 기준일 평가 환산 | **매매기준율** | FR-041b — 환전이 아니라 값어치를 재는 것 |

그날 환율이 없으면 **가장 가까운 이전 고시일**의 값을 쓰고 그 날짜를 함께 내려준다
(FR-041c, research R5-6). 밝히지 않으면 곧바로 원칙 V 위반이다.

---

## 7. 예상 규모

| 항목 | 규모 |
|------|------|
| 종목당 일봉 (30년) | 약 7,500행 |
| 종목당 배당 이벤트 (30년, 분기 배당) | 약 120행 |
| 종목당 분할 이벤트 | 보통 0~5행 |
| 표에 나오는 행 (30년) | 월 360 + 배당 120 = 약 480행 |

표 행이 일봉의 **1/15**이라 서버에서 고르는 것이 맞다 (research R5-8).
