# Bug Assessment: 해외 주식 보드의 양도소득세가 "현재 잔고 − 원금 − 공제"와 다르다

- **Slug**: foreign-sale-tax-gain
- **Created**: 2026-10-07
- **Source**: pasted text + 스크린샷(주식 화면 보드)
- **Verdict**: invalid — 세금 계산은 맞다(기대 동작). 다만 보드가 양도차익이 어떻게 나왔는지 보이지 않아 오해를 부른다(표시의 빈틈 — 아래 Remediation)
- **Severity**: low (계산 오류 없음 · 표시 개선 여지)

## Report (verbatim)

> XLK를 2010년 2월11일에 한화 20,000,000원 투자하면 26년10월6일 기준으로 스샷과 같은 투자 성과가 나온다고 출력되고 있어.
> 그런데, 세금 계산이 조금 이상해 현재 잔고(잔고 + 예수금) - 2,500,000원에 대한 세금을 계산 해야 하는데 숫자가 조금 잘못 된 것 같아. 확인해줘.

스크린샷의 보드(2026-10-06 기준 · KRW 기준, 환전 2010-02-11 현금 살 때 1,158.10 — 스프레드 90% 우대):

| 칸 | 값 |
|----|----|
| 투자 원금 | ₩20,000,000 |
| 현재 잔고 | ₩539,297,203 (잔고 + 예수금) |
| 매도 수수료/세금 | -₩110,182,526 — 수수료 ₩80,884, 양도소득세 22% ₩110,101,642, 차익 ₩502,962,012 − 공제 ₩2,500,000 |
| 투자 수익 | ₩409,114,677 (보유 중 ₩519,297,203) |
| 수익률 | +2045.57% (보유 중 +2596.48%) |

## Symptom

사용자는 양도소득세를 "(현재 잔고 − 원금 − 기본공제) × 22%", 곧 (₩539,297,203 − ₩20,000,000 − ₩2,500,000) × 22% ≈ ₩113,685,384로 기대했다. 보드는
양도차익을 ₩502,962,012로 잡아 세금 ₩110,101,642를 냈다. 차이는 양도차익에서 ₩16,335,191이다.

**기대 동작이다.** 양도차익은 "현재 잔고 − 원금"이 아니라 "판 주식의 매도금액 − 그 주식들의 취득가 − 수수료"다. 배당을 재투자해 산 주식에도 각자의
취득가가 있고, 예수금은 팔지 않는다.

## Reproduction

1. 개발 서버에서 `GET /api/stocks/simulation?market=NYSE&symbol=XLK&start=2010-02-11&principal=20000000&principalCurrency=KRW&reinvest=true&end=2026-10-06`
   (화면: 주식 → S&P 500 기술주 SPDR ETF(XLK), 일시금, 시작일 2010-02-11, 원금 20,000,000 KRW, 배당 재투자)
2. `summary.saleCost.gain` = `502962012`, `tax` = `110101642`, `summary.totalKrw` = `539297203`
3. 모든 행(`period=monthly`로 이어 받아 매수 1행·재투자 67행)으로 같은 식을 다시 계산하면 아래 분해와 같다 — 서버 값과 1원도 다르지 않다(2026-10-07 실측)

### 실측 분해 (2026-10-07, 개발 DB)

| 항목 | 원화 | 근거 |
|------|------|------|
| 매도금액 — 보유 주식 × 기준일 종가 × 기준일 매매기준율(1,358.50) | ₩539,229,405 | 기준일 행 `balanceKrw` |
| − 취득가: 처음 매수(2010-02-11, 매매기준율 1,157.90) | ₩19,985,122 | 매수 행 `boughtShares × openPrice × fxRate` |
| − 취득가: 배당 재투자 매수 67회(각 매수일의 매매기준율) | ₩16,195,960 | 재투자 행 |
| − 매수 수수료(원화) | ₩5,427 | 행의 `tradeFee × fxRate` |
| − 매도 수수료 | ₩80,884 | `saleCost.fee` |
| **= 양도차익** | **₩502,962,012** | 서버 `saleCost.gain`과 같다 |
| 세금 = ⌊(₩502,962,012 − ₩2,500,000) × 22%⌋ | ₩110,101,642 | 서버 `saleCost.tax`와 같다 |

"현재 잔고 − 원금"(₩519,297,203)과의 차이 ₩16,335,191의 내역:
- 배당 재투자 매수의 취득가 **₩16,195,960** — 차이의 대부분
- 매수·매도 수수료 ₩86,311
- 예수금 ₩67,797 — 현재 잔고에는 들어가지만 팔지 않는 돈이다(1주가 안 되어 남은 돈)
- 처음 매수의 취득가가 원금보다 ₩14,878 작다 — 원금은 현금 살 때 환율(1,158.10)로 환전했고, 취득가는 매수일 매매기준율(1,157.90)로 잰다. 이 몫은 차이를 줄인다
- 합: ₩16,195,960 + ₩86,311 + ₩67,797 − ₩14,878 = ₩16,335,190(원 미만 버림 1원)

## Suspected Code Paths

- `backend/src/api/services/stock_sale.py:24` `sale_cost_for` — 매도금액 = `latest.row.balance`(보유 평가액 — 예수금 제외) × 기준일 매매기준율, 취득가 = 행 가운데
  `bought_shares > 0`인 모든 행(처음 매수 + 재투자)의 `bought_shares × open_price × fx_rate`, 매수 수수료 = `trade_fee × fx_rate`
- `backend/src/simulation/stock_sale_cost.py` `foreign_sale_cost` — 양도차익 = 매도금액 − 취득가 − 매수·매도 수수료(원 미만 버림), 세금 = max(0, 차익 − 공제) × 세율
- `frontend/src/components/stock/PerformanceBoard.tsx` `saleNotes` — 매도 칸에 "차익 − 공제"만 적는다. 차익을 이루는 매도금액·취득가는 보이지 않는다

## Root Cause Hypothesis

계산 결함은 없다(확신 높음 — 서버 값을 행 단위로 다시 계산해 일치를 확인했다). 해외 주식 양도소득세의 양도차익은 소득세법의 틀대로 **양도가액 − 취득가액 −
필요경비**다.
- 배당으로 다시 산 주식도 취득한 주식이다. 그 취득가를 빼지 않으면 이미 배당 소득세를 낸 배당을 양도차익으로 한 번 더 과세하게 된다
- 예수금은 팔지 않으므로 양도가액이 아니다
- 취득가는 취득일 매매기준율로 잰다

오해의 원인은 표시다. 012 US5가 보드에 "현재 잔고"를 더하면서 사용자가 "현재 잔고 − 원금 = 차익"으로 읽기 쉬워졌다. 그런데 매도 칸은 "차익 − 공제"만 보여, 차익이
그보다 작은 까닭(재투자 취득가·예수금·수수료)이 화면 어디에도 없다. 010 반복 4가 세운 원칙("보드가 표와 다른 까닭이 보여야 한다")과 같은 종류의 빈틈이다.

## Proposed Remediation

**Preferred**: 계산은 바꾸지 않는다. 매도 칸의 설명 줄에 **양도차익의 구성**을 더한다 — 예: "매도금액 ₩539,229,405 − 취득가 ₩36,181,082(배당 재투자 매수 포함) −
수수료 ₩86,311". 화면은 계산하지 않으므로(헌법 원칙 VI) 서버가 `saleCost`에 `saleKrw`(매도금액)·`acquisitionKrw`(취득가 합)·`feesKrw`(매수·매도 수수료)를 더한다
(해외 종목만, 국내는 비움). `gain = saleKrw − acquisitionKrw − feesKrw`가 그대로 성립한다. 주식 적립식 보드의 세금 칸(같은 `foreign_sale_cost`)에도 같은 줄을 둔다.

요구사항이 바뀌는 일(응답 키·보드 문구)이라 버그 수정보다 **012 반복**(`/speckit-iterate-define`)으로 다루는 편이 맞다 — spec FR·contracts·tasks를 함께 고친다.

**Alternatives**:
- 아무것도 바꾸지 않는다 — 계산이 맞으므로 이 보고는 닫는다. 같은 오해가 다시 생길 수 있다
- 도움말(ⓘ)만 둔다 — "차익 = 매도금액(보유 주식) − 취득가(배당 재투자 매수 포함) − 수수료. 예수금은 팔지 않는다"를 고정 문구로. 서버 변경이 없지만 숫자가 없어
  사용자가 직접 맞춰 볼 수 없다

**Files likely to change** (Preferred를 고를 때):
- `backend/src/simulation/stock_sale_cost.py`(`SaleCost`에 구성 값)
- `backend/src/api/services/stock_sale.py`·`backend/src/api/routes/stock_simulation.py`(`saleCost` JSON)
- `backend/src/api/services/stock_recurring.py`(적립식 매도 비용)
- `frontend/src/lib/types.ts`(`SaleCost`)·`frontend/src/components/stock/PerformanceBoard.tsx`(`saleNotes`)·`frontend/src/components/recurring/RecurringBoard.tsx`
- 테스트: `backend/tests/unit/test_stock_sale_cost.py`, `backend/tests/integration/test_stock_sale_cost_api.py`, `frontend/tests/PerformanceBoardSaleCost.test.tsx`

**Tests to add or update**:
- 재투자가 있는 해외 종목에서 `gain = saleKrw − acquisitionKrw − feesKrw`이고 `acquisitionKrw`가 처음 매수 + 재투자 매수의 원화 합이다
- 예수금이 매도금액에 들어가지 않는다(`saleKrw = 보유 평가액의 원화`, `totalKrw − saleKrw = 예수금의 원화`)
- 매도 칸이 매도금액·취득가·수수료를 보인다(서버 값을 그린다)
- 기존 값(`gain`·`tax`·`total`)은 바뀌지 않는다 — 불변 대조

## Risks & Considerations

- 응답 키를 더하면 012 불변 대조(quickstart 3-7)에서 더한 키를 빼고 견줘야 한다(US5의 `totalKrw`와 같다)
- 매도 칸의 설명 줄이 길어진다(지금도 넷) — 보드 높이가 늘어난다. 칸 폭이 좁은 창에서 줄바꿈을 본다
- 세법 해석의 한계는 그대로다(문서화된 범위): 환전 스프레드는 필요경비로 보지 않는다, 그해 다른 해외 매도가 없다고 가정한다, 해외 거래소 수수료는 반영하지 않는다
  (`stock_sale_cost.py` 머리말)

## Open Questions

- [NEEDS CLARIFICATION: 표시를 고칠까? — (A) 매도 칸에 양도차익 구성(매도금액·취득가·수수료)을 숫자로 보인다(012 반복으로), (B) 고정 도움말만 둔다, (C) 계산이 맞으므로 닫는다]
