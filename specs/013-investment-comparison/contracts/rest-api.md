# REST API 계약 (013)

**Date**: 2026-10-08 | **Data Model**: [../data-model.md](../data-model.md) | **Research**: [../research.md](../research.md)

새 경로는 두 묶음이다 — 대상 하나를 계산하는 **비교 경로 일곱**(1절)과 **저장한 비교**(2~4절). 기존 경로의 질의·응답은 바뀌지 않는다(FR-020).

## 1. 비교 경로 일곱 — 대상 하나

| 경로 | 짝이 되는 메뉴 경로 | 질의 |
|------|--------------------|------|
| `GET /api/comparison/stocks/simulation` | `/api/stocks/simulation` | `market`, `symbol`, `start`, `principal`, `principalCurrency`, `reinvest`, `end`?, `maxPoints`? |
| `GET /api/comparison/stocks/recurring-simulation` | `/api/stocks/recurring-simulation` | `market`, `symbol`, `start`, `amount`, `frequency`, `principalCurrency`, `reinvest`, `end`?, `maxPoints`? |
| `GET /api/comparison/crypto/simulation` | `/api/crypto/simulation` | `coinId`, `start`, `principal`, `principalCurrency`, `end`?, `maxPoints`? |
| `GET /api/comparison/crypto/recurring-simulation` | `/api/crypto/recurring-simulation` | `coinId`, `start`, `amount`, `frequency`, `principalCurrency`, `end`?, `maxPoints`? |
| `GET /api/comparison/deposit/simulation` | `/api/deposit/simulation` | `institution`, `start`, `principal`, `principalCurrency`?, `end`?, `maxPoints`? |
| `GET /api/comparison/deposit/installment-simulation` | `/api/deposit/installment-simulation` | `institution`, `start`, `amount`, `end`?, `maxPoints`? |
| `GET /api/comparison/realestate/simulation` | `/api/realestate/simulation` | `complexId`, `area`, `buyDate`, `principalCurrency`?, `maxPoints`? |

### 1.1 질의

- 이름·형·검증·처음 값은 짝이 되는 메뉴 경로와 **같다**(검증 함수를 함께 쓴다). 표 전용 질의(`before`·`limit`·`period`)는 없다
- `maxPoints`: 2 이상, 처음 값 **1000**(메뉴 시계열은 2000). 같은 LTTB 다운샘플링
- 부동산은 `buyPrice`를 받지 않는다 — 매입가는 그 달 시세다(FR-008). 메뉴처럼 `buyPrice`를 보내면 400 `invalid_query`
- 계산 끝은 메뉴 규칙 그대로다(주식 어제, 가상자산 UTC 어제 `calculation_end`, 예금 KST 오늘, 부동산 KST 오늘)

### 1.2 200

```json
{
  "basisCurrency": "KRW",
  "target": {"market": "NYSE", "symbol": "XLK", "name": "Technology Select Sector SPDR Fund", "currency": "USD"},
  "condition": { "...": "메뉴 응답의 condition 그대로" },
  "exchange": { "...": "메뉴 응답의 exchange 그대로 — 없으면 null" },
  "summary": { "...": "메뉴 응답의 summary 그대로 — 같은 함수가 만든다" },
  "series": { "...": "메뉴 /series 응답 그대로 — 같은 빌더, maxPoints만 다르다" },
  "comparison": { "...": "data-model 3" }
}
```

| 키 | 자산군별 내용 |
|----|---------------|
| `target` | 주식 메뉴 응답의 `stock`, 가상자산 `coin`, 예금 `institution`(`{key, name}`), 부동산 `{complex, area}` |
| `condition` | 메뉴 응답의 `condition` 그대로 |
| `exchange` | 주식·가상자산 일시금의 원금 환전(메뉴 응답과 같다). 그 밖은 `null` |
| `summary` | 메뉴 표 경로 응답의 `summary`와 **같은 값**(SC-001 — 통합 테스트가 같은 질의의 두 응답을 견준다) |
| `series` | 메뉴 `/series` 응답과 같은 모양. `maxPoints`가 같으면 같은 값 |
| `comparison` | 정규화 블록 — data-model 3 |

정기 적금은 메뉴 응답의 `contracts`·`deposits`, 정기예금은 `terms`, 모든 자산군의 `rows`를 담지 않는다(표가 없다 — FR-011).

### 1.3 202 — 수집 중

메뉴 경로의 202 본문과 **같다**(research 조사 표). 화면은 `jobId`(와 주식·가상자산의 `fx`)로 진행 스트림을 구독한다(R13-7).

### 1.4 거절

메뉴 경로와 **같은 예외 → 같은 처리기 → 같은 본문**이다. 화면의 갈래 나누기는 research R13-6 표.

| HTTP | `status` | 더한 키 |
|------|----------|---------|
| 400 | `before_listing` | `startableFrom`, `basis` |
| 409 | `before_first_month` | `startableFrom`, `message` |
| 409 | `before_first_trade` | `startableFrom`, `basis` |
| 409 | `fx_not_available_before` | `reason`, `currency`, `availableFrom` |
| 400 | `installment_not_available` | `allowed` |
| 404 | `unknown_stock`·`unknown_coin` | `action` |
| 400 | `unknown_complex` | — |
| 409 | `region_retired` | `lawdCd` |
| 409 | `no_price_at_purchase` | `month` |
| 409 | `no_trades_in_area`·`tax_rule_not_covered`(`tax`, `date`)·`rate_missing`(`month`) | |
| 404 | `no_price_data`·`price_symbol_unknown`·`no_rate_data` | — |
| 400 | `start_after_end` | `lastDay` |
| 400 | `currency_pair_not_allowed`·`currency_not_allowed` | `allowed` |
| 400 | `invalid_query` | — |
| 409 | `fx_unavailable` | — |
| 502 / 503 | `source_unavailable` / `source_rate_limited` | — |

### 1.5 부수 효과

- 수집 작업 행·큐 요청 — 메뉴 경로와 같다(받지 않은 구간이 있을 때)
- 주식 종목 자동 등록(`require_stock`) — 메뉴 경로와 같다
- **이력을 쓰지 않는다**(FR-020 — 통합 테스트가 `simulation_history` 행 수가 그대로임을 본다)

## 2. `GET /api/comparison/saved` — 저장한 비교 목록

```json
{
  "entries": [
    {"id": 12, "name": "주식 3개 · 2020-01-02 · 일시금", "asset": "stock",
     "condition": { "...": "data-model 2 — 저장한 글을 읽은 객체" },
     "savedAt": "2026-10-08T03:21:07Z"}
  ]
}
```

- 차례: `savedAt` 내림차순, 같은 초는 `id` 내림차순
- 보관 기간이 없다 — 읽을 때 지우는 일이 없다
- 빈 목록이면 `{"entries": []}`

## 3. `POST /api/comparison/saved` — 저장

요청:

```json
{"name": "주식 3개 · 2020-01-02 · 일시금", "condition": { "...": "data-model 2" }}
```

- 201, 본문 `{"entry": {...새 항목}, "entries": [...목록 전체]}` — 화면이 목록을 다시 받지 않는다
- 같은 조건·같은 이름이어도 새 행이다(FR-016 — 저장할 때마다 새 항목)
- 검증 실패: 422 `{"status": "invalid_comparison", "message": "<어느 칸이 왜>"}` — 이름(빈 이름·100자 초과), `v`, `asset`·`method` 짝, `frequency`, `start`, `amount`,
  `principalCurrency`(대상 통화 규칙), `reinvest`, `targets`(수·중복·자산군 칸·적금 투자처)
- 저장은 조건만이다 — 본문에 결과 키(`summary`·`comparison` 등)가 있어도 정규화가 버린다(SC-006)

## 4. `DELETE /api/comparison/saved/{id}` — 삭제

- 200, 본문 `{"entries": [...남은 목록]}`
- 없는 `id`도 200(멱등 — 두 창에서 지워도 오류가 아니다)
- `id`가 정수가 아니면 FastAPI 기본 422

## 5. 오류 처리기

| 예외 | HTTP | `status` | 비고 |
|------|------|----------|------|
| `InvalidComparison`(신규, `api/errors.py`) | 422 | `invalid_comparison` | 메시지가 칸을 밝힌다 |

비교 경로 일곱은 새 예외가 없다 — 메뉴 경로의 예외를 그대로 올린다.

## 6. 등록 차례

`create_app()`에서 저장 라우터(`/api/comparison/saved`)를 비교 라우터(`/api/comparison/<자산군>/...`)보다 **먼저** 더한다. 지금은 마디 수가 달라 겹치지 않지만,
012 `settings`처럼 나중의 경로가 앞 경로를 잡지 않게 한다.
