# Quickstart: 013 검증 안내

**Date**: 2026-10-08 | **Plan**: [plan.md](./plan.md) | **REST**: [contracts/rest-api.md](./contracts/rest-api.md) | **화면**: [contracts/ui-wireframes.md](./contracts/ui-wireframes.md)

이 문서는 기능이 끝에서 끝까지 동작함을 보이는 실행 안내다. 구현 코드는 담지 않는다. 결과는 맨 아래 "실행 기록"에 남긴다.

## 0. 준비

- 개발 DB에 새 테이블: `cd backend && .venv/bin/python -m alembic upgrade head` (머리가 `a6d2f9c41b83`의 다음 리비전이 된다)
- 테스트 스위트는 개발 서버를 내린 채 돌린다(`./stop.sh` → 테스트 → `./start.sh`). 테스트는 `assetreplay_test`를 드롭·재생성한다
- 브라우저 확인은 헤드리스 Chrome(1440×900, 새 브라우저 문맥)으로 한다. **사용자의 이력·저장한 비교를 바꾸지 않는다** — 비교 실행은 이력을 쓰지 않는다(이것 자체가
  확인 항목이다). 저장 확인으로 만든 저장한 비교는 끝에 지운다(전후 목록이 같음을 본다)

## 1. 단위 참조값 (SC-001·SC-003·SC-005)

```bash
cd backend && .venv/bin/python -m pytest -q --no-cov tests/unit/test_comparison_costs.py tests/unit/test_comparison_costs_recurring.py \
  tests/unit/test_comparison_metrics.py tests/unit/test_comparison_metrics_recurring.py tests/unit/test_comparison_conditions.py \
  tests/unit/test_deposit_accrued_tax.py tests/unit/test_installment_open_tax.py tests/unit/test_fx_resolve_bisect.py
cd frontend && npx vitest run tests/compareBlock.test.ts tests/decimalOrder.test.ts tests/compareCondition.test.ts tests/compareNoClientFinance.test.ts
```

기대:
- 비용 항목 합 = 몫의 합, 몫의 합 = 전체 합. 해외 주식 일시금 `buy_fee + sale_fee = saleCost.feesKrw`, 적립식 `buy_fee = buyFeeTotal`, 적금 `interest_tax_matured = taxTotal`,
  부동산 취득 항목 합 = `acquisition.total`. 가상자산 적립식의 시행일 뒤 기준일은 세금·합이 `null`(0이 아니다)
- 주 값 규칙이 보드와 같다(주식 일시금·부동산 물러남, 적립식 `null`, 가상자산 일시금·예금 보유 중)
- 정기예금 `balance = 회차 원금 + 경과 이자 − accrued_tax`, 기존 `balance`·`profit` 불변
- `resolve_rate`의 이분 탐색이 무작위 날짜에서 옛 방식과 같은 (환율, 쓴 날짜)
- 막힘 갈래·제안 날짜(수집 중인 대상이 있으면 제안 없음), 소수 문자열 정렬은 글자 차례가 아니라 수 차례(`"-0.5" < "0" < "9.99" < "10"`), `null`은 끝

## 2. API — 메뉴와 같은 값 (SC-001·SC-002·SC-007)

```bash
cd backend && .venv/bin/python -m pytest -q --no-cov tests/integration/test_comparison_api.py tests/integration/test_comparison_identity.py \
  tests/integration/test_comparison_identity_recurring.py tests/integration/test_saved_comparison_api.py tests/integration/test_saved_comparison_schema.py
```

기대:
- 일곱 경로 각각 같은 질의로 메뉴 표 경로의 `summary`와 비교 경로의 `summary`가 같다. `series`는 같은 `maxPoints`로 메뉴 `/series`와 같다
- 202·거절 본문이 메뉴와 같다(같은 고정 데이터로 두 경로를 부른다)
- 비교 경로 실행 뒤 `simulation_history` 행 수가 그대로다
- 저장 → 목록 차례(최근 저장 먼저) → 삭제(없는 `id`도 200) → 조건 글이 받은 금액 글자를 그대로 담는다 → 결과 키는 버려진다
- 스키마: 열·형·NOT NULL·색인, 하향(`a6d2f9c41b83`) 뒤 재상향

개발 서버에서 손으로 한 번(값은 기록한다):

```bash
curl -s 'http://localhost:8080/api/comparison/stocks/simulation?market=NYSE&symbol=XLK&start=2010-02-11&principal=20000000&principalCurrency=KRW&reinvest=true&end=2026-10-06' | jq '.comparison'
curl -s 'http://localhost:8080/api/stocks/simulation?market=NYSE&symbol=XLK&start=2010-02-11&principal=20000000&principalCurrency=KRW&reinvest=true&end=2026-10-06' | jq '.summary'
```

`comparison.profit`·`returnRate`가 메뉴 `summary.profitAfterSale`·`returnRateAfterSale`과 같고, `costs.sale.total`이 `saleCost.total`과 같다.

## 3. 화면 테스트 (FR 전반)

```bash
cd frontend && npx vitest run tests/ComparePage*.test.tsx tests/compareStore*.test.ts tests/CompareTable.test.tsx tests/CompareReturnChart.test.tsx \
  tests/CompareMetricBars.test.tsx tests/InstitutionChecklist.test.tsx tests/SavedComparisons.test.tsx tests/SaveComparisonForm.test.tsx \
  tests/HistoryStatesEmptyText.test.tsx tests/stockSelection.test.ts tests/realEstatePickerSlice.test.ts
```

- 종료 코드 0을 본다("N passed"만 보지 않는다 — 011 T036). 페이지 테스트는 `lightweight-charts`를 모의한다

## 4. 성능 (SC-004)

개발 서버에서, 시세를 받아 둔 대상으로:

1. 주식 10개(국내·미국 섞음) × 시작일 20년 전, 일시금 원화 원금 — "비교 실행"부터 표·그래프가 다 보일 때까지
2. 가상자산 10개 × 가능한 최장(원화 원금 — 환율 찾기 빗나감 길) 일시금 — 같은 측정

기대: 각각 5초 안. 브라우저 성능 기록 또는 CDP로 요청 시작~마지막 그리기 시각을 잰다. 넘으면 대상별 응답 시간을 기록하고 멈춘다(어느 대상이 느린가).

## 5. 브라우저 끝에서 끝까지 (US1~US4)

| # | 단계 | 기대 |
|---|------|------|
| 5-1 | 사이드바 "투자 비교" | `/compare`가 열리고 제목 "투자 비교"(F1) |
| 5-2 | 주식, 삼성전자·SK하이닉스·XLK, 2020-01-02, 10,000,000 KRW, 재투자 | 세 줄. 각 줄의 원금·현재 가치·투자 수익·수익률이 주식 메뉴의 같은 조건 보드와 같다. 비용 = 반영 + 매도 가정(US1 Independent Test) |
| 5-3 | 11번째 대상 | 더해지지 않고 알림(F2) |
| 5-4 | 시작일 2010-01-04 + 2015년 이후 상장 종목 | 막힘, 이름·까닭, 제안 날짜. 누르면 시작일만 바뀐다(US1-10) |
| 5-5 | 받지 않은 종목이 낀 비교 | 받아 둔 대상부터 보이고 나머지는 "수집 중"이었다가 채워진다(US1-11) |
| 5-6 | 결과 뒤 시작일 바꾸기 → 되돌리기 | 흐림·띠 → 풀림. 흐린 동안 저장 꺼짐(US1-12, US4-6) |
| 5-7 | 가상자산 비트코인·이더리움, 적립식 매달 100,000 KRW | 두 줄의 총 납입 원금이 같고 가상자산 메뉴의 같은 조건 결과와 같다(US2) |
| 5-8 | 예금 정기 적금 + 저축은행이 낀 저장 비교 불러오기 | 막힘 "정기 적금이 없는 투자처 — 빼세요"(US2-2) |
| 5-9 | 부동산 단지 둘(평형) | 매입가가 대상마다 다르다. 투자 원금 = 투입 금액(US1-9) |
| 5-10 | 그래프 | 선마다 이름, 기준일에 매도 후 점, 상자의 두 값, 최종 지표 = 표(US3) |
| 5-11 | 저장 → 새로 고침 → 불러오기 → 삭제 | 목록에 남고, 불러오면 같은 조건으로 다시 실행, 지우면 빠진다(US4) |
| 5-12 | 비교 실행 전후 `GET /api/history/{네 자산군}` | 같다 — 비교가 이력에 남지 않는다(FR-020·SC-007) |

## 6. 불변 (SC-009·FR-020)

012 quickstart 3-7과 같은 방식: 013 전 커밋(`71003d4`)과 013 뒤로 네 메뉴의 표·시계열 경로를 같은 질의로 부르고 응답을 견준다(주식 일시금·적립식, 가상자산
일시금·적립식, 정기예금, 정기 적금, 부동산). 기대: 같다(부동산은 계산 끝이 KST 오늘이라 같은 날 실행한다). 메뉴 화면 테스트는 R13-16 목록 밖에서 고친 것이 없다.

## 실행 기록

(구현 중 채운다)
