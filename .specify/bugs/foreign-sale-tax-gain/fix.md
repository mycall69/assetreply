# Bug Fix: 해외 주식 보드의 양도소득세가 "현재 잔고 − 원금 − 공제"와 다르다

- **Slug**: foreign-sale-tax-gain
- **Fixed**: 2026-10-07
- **Assessment**: ./assessment.md
- **Status**: applied (Remediation A — 012 반복 US6으로 처리)

## Summary

계산은 맞았다(assessment — 서버 값을 행 단위로 다시 계산해 1원도 다르지 않음). 오해의 원인인 표시의 빈틈을 고쳤다 — 해외 주식 보드의 매도 칸(일시금)·세금 칸(주식 적립식)이
양도차익의 구성 "매도금액 − 취득가 − 수수료"와 취득가 설명(배당 재투자 매수 포함 · 예수금은 팔지 않음)을 "차익 − 공제" 바로 앞에 보인다. 버그 수정 명령이 아니라
012 반복(`/speckit-iterate-define` → `apply` → `implement`)으로 다뤘다 — 응답 키·보드 문구가 바뀌는 요구사항 변경이라 spec FR-019·SC-011·contracts·tasks T077~T084를 함께 고쳤다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `backend/src/simulation/stock_sale_cost.py` | modified | `SaleCost.sale_krw`·`acquisition_krw`·`fees_krw` — 차익을 만든 원 미만 버림 값. 계산 불변 |
| `backend/src/api/routes/stock_simulation.py`·`backend/src/api/services/stock_recurring.py` | modified | `saleCost` JSON에 `saleKrw`·`acquisitionKrw`·`feesKrw`(국내 `null`) |
| `frontend/src/lib/types.ts`·`frontend/src/components/stock/PerformanceBoard.tsx`·`frontend/src/components/recurring/RecurringBoard.tsx` | modified | `gainBreakdown` — 구성 두 줄(세 값이 없으면 그리지 않음) |
| `backend/tests/unit/test_stock_sale_cost_breakdown.py` | added test | 원 미만 버림·식·국내 None·기존 값 그대로 |
| `backend/tests/integration/test_sale_gain_breakdown_api.py` | added test | 일시금(재투자)·적립식의 새 키와 식, 취득가 = 처음 + 재투자 매수, 매도금액은 보유 주식만 |
| `frontend/tests/SaleGainBreakdown.test.tsx` | added test | 두 줄의 문구·자리, 국내·US6 전 응답에는 없음, 서버 값 |
| `backend/tests/integration/test_stock_sale_cost_api.py`·`test_stock_recurring_api.py` | updated test | `saleCost ==` 단언 다섯에 새 키 셋을 더함(사용자 승인 2026-10-07 — T077) |

커밋: `3d182ff`(테스트·문서) → `8003b24`(구현) → T084 기록 커밋.

## Tests Added or Updated

- `test_stock_sale_cost_breakdown.py::Test해외::test_구성_값은_원_미만을_버린_값이고_차익과_0원_차이다` — 보고(XLK)의 값으로 식을 고정
- `test_sale_gain_breakdown_api.py::Test일시금::test_취득가는_처음_매수와_배당_재투자_매수의_합이다` — 차이의 주된 원인(재투자 매수의 취득가)을 고정
- `test_sale_gain_breakdown_api.py::Test일시금::test_매도금액은_보유_주식만이다` — 예수금이 매도금액에 섞이지 않음
- `SaleGainBreakdown.test.tsx` — 매도 칸·세금 칸의 구성 줄

## Local Verification

- 게이트(서버를 내린 채): 백엔드 2,838 passed(커버리지 96.35%), 프론트엔드 166 파일·1,421 passed, mypy·ruff·tsc·eslint 통과
- API: 보고 조건(XLK 2010-02-11 원화 2,000만 원 재투자, 2026-10-06 기준) → 매도금액 539,229,405 − 취득가 36,181,082 − 수수료 86,311 = 차익 502,962,012
- 브라우저: XLK 일시금·적립식의 구성 줄, 삼성전자 매도 칸 그대로(012 quickstart US6 기록)
- 불변 대조: 기존 응답 값이 모두 같고 더한 키만 늘었다

## Deviations from Assessment

- 수정 경로를 `/speckit-bug-fix`가 아니라 012 반복으로 바꿨다 — assessment의 Remediation이 이미 "요구사항이 바뀌는 일이라 012 반복으로 다루는 편이 맞다"고 적었고 사용자가 A를 골랐다
- 수수료를 매수·매도 하나로 낸다(`feesKrw`) — 매도 수수료는 매도 칸 첫 줄에 이미 있어 줄을 늘리지 않았다(research R12-18)

## Follow-ups

- 필요하면 `/speckit-bug-test slug=foreign-sale-tax-gain`으로 검증 보고를 남긴다
