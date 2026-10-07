# Bug Verification: 해외 주식 보드의 양도소득세가 "현재 잔고 − 원금 − 공제"와 다르다

- **Slug**: foreign-sale-tax-gain
- **Tested**: 2026-10-07
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

보고 조건(XLK 2010-02-11, 원화 2,000만 원, 배당 재투자, 2026-10-06 기준)을 그대로 다시 실행했다. 보드의 값은 스크린샷과 같다 — 계산은 원래 맞았고 바뀌지 않았다.
매도 칸에는 이제 "매도금액 ₩539,229,405 − 취득가 ₩36,181,082 − 수수료 ₩86,311"과 "취득가는 모든 매수(배당 재투자 포함) · 예수금은 팔지 않음"이 "차익 − 공제" 바로 앞에
보여, 차익이 "현재 잔고 − 원금"보다 작은 까닭이 화면에 있다(오해의 원인이던 표시의 빈틈이 닫혔다). 회귀는 없다.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) — API | `GET /api/stocks/simulation?market=NYSE&symbol=XLK&start=2010-02-11&principal=20000000&principalCurrency=KRW&reinvest=true&end=2026-10-06` | pass | `saleKrw` 539,229,405 − `acquisitionKrw` 36,181,082 − `feesKrw` 86,311 = `gain` 502,962,012. `tax`·`total`·`totalKrw`는 보고와 같다 |
| Reproduction (post-fix) — 브라우저 | 헤드리스 Chrome(1440×900, 새 브라우저 문맥)으로 주식 화면에서 XLK·2010-02-11·20,000,000 KRW·재투자 실행, 보드 칸 읽기 | pass | 매도 칸 여섯 줄 중 셋째·넷째가 구성 줄. 다른 칸 값은 스크린샷과 같다. 이력 PUT 1건을 막아 사용자 이력은 바뀌지 않았다(확인 전후 같음) |
| New / updated tests — 백엔드 | `.venv/bin/python -m pytest -q --no-cov tests/unit/test_stock_sale_cost_breakdown.py tests/unit/test_stock_sale_cost.py tests/integration/test_sale_gain_breakdown_api.py tests/integration/test_stock_sale_cost_api.py tests/integration/test_stock_recurring_api.py` | pass | 37 passed |
| New / updated tests — 화면 | `npx vitest run tests/SaleGainBreakdown.test.tsx` | pass | 5 passed |
| Regression suite — 백엔드 | `.venv/bin/python -m pytest -q --cov=src`(개발 서버를 내린 채) | pass | 2,838 passed, 커버리지 96.35% |
| Regression suite — 화면 | `npx vitest run` | pass | 166 파일·1,421 passed, 종료 코드 0 |
| Lint / type-check | `mypy src`·`ruff check --no-cache src tests`·`npx tsc --noEmit`·`npx eslint .` | pass | 모두 종료 코드 0 |

## Output Excerpts

```text
api: saleKrw 539229405 · acquisitionKrw 36181082 · feesKrw 86311 · gain 502962012 · tax 110101642 · identity true
board 매도 수수료/세금 -₩110,182,526:
  수수료 ₩80,884
  양도소득세 22% ₩110,101,642
  매도금액 ₩539,229,405 − 취득가 ₩36,181,082 − 수수료 ₩86,311
  취득가는 모든 매수(배당 재투자 포함) · 예수금은 팔지 않음
  차익 ₩502,962,012 − 공제 ₩2,500,000
  세율·공제: 설정값(설정 > 주식 매도 세금)
board 현재 잔고 ₩539,297,203 · 투자 수익 ₩409,114,677(보유 중 ₩519,297,203) · 수익률 +2045.57%
history_put_blocked 1 · history_unchanged true

backend: 2838 passed in 534.93s — Total coverage: 96.35%
frontend: Test Files 166 passed (166) · Tests 1421 passed (1421)
```

## Residual Risks

- 값은 2026-10-07의 개발 DB 시세·환율 기준이다. 이후 시세가 더해지면 기준일과 금액이 바뀐다(식은 그대로다).
- 세법 해석의 한계는 그대로다(assessment Risks): 환전 스프레드는 필요경비로 보지 않는다, 그해 다른 해외 매도가 없다고 가정한다, 해외 거래소 수수료는 반영하지 않는다.
- 브라우저 확인은 1440px 창이다. 좁은 창에서는 매도 칸의 구성 줄이 더 여러 줄로 감긴다(내용은 같다).

## Recommendation

닫는다 — end-to-end로 확인했다. 계산은 원래 맞았고, 보고의 원인이던 표시의 빈틈(양도차익의 구성이 보이지 않음)이 012 반복 US6으로 해소되었으며 회귀가 없다.
