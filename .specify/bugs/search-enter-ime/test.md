# Bug Verification: 한글을 조합 중에 엔터를 치면 고른 뒤 비운 검색 칸에 조합 중이던 글자가 들어간다

- **Slug**: search-enter-ime
- **Tested**: 2026-10-03
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

증상은 더 이상 재현되지 않는다. 평가 때와 같은 브라우저 순서(조합 중 엔터 → 확정 → 엔터)로 "삼성전자"를 넣자 칸이 비고 삼성전자가
골라졌다. 다른 검색어("현대차"), 조합 중 방향키, 조합 없는 영문·방향키 선택도 기대대로였다. 프론트엔드 전체 테스트·타입·린트가
통과했고 회귀는 없었다. 실제 한글 입력기로 손으로 친 확인은 하지 않았다(아래 Residual Risks).

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix, 평가 순서) | 헤드리스 Chrome 154, 3030 경유, 1440px: `Input.insertText("삼성전")` → `Input.imeSetComposition("자")` → 엔터(keyCode 229) → 확정(`자`) → 엔터(13) | pass | 칸 비어 있음, `삼성전자(005930) KRX · KRW`. 고치기 전(평가)에는 칸 `자`, 목록 `자더`·`자빌`·`자비스` |
| 다른 한글 검색어 | 같은 순서로 "현대" + 조합 중 "차" | pass | `현대차(005380) KRX · KRW`가 골라지고 칸이 빈다 |
| 조합 중 방향키 | "삼성전" + 조합 중 "자", 조합 중 ↓(229) 두 번 → 엔터(229) → 확정 → 엔터(13) | pass | 항목이 옮겨지지 않아 맨 위 `삼성전자(005930)`. 고치기 전에는 단위 테스트에서 삼성전자우가 골라졌다 |
| 회귀 — 조합 없는 엔터 | "VOO"를 한 번에 넣고 엔터(13) | pass | `S&P 500 뱅가드 ETF(VOO) NYSE · USD` |
| 회귀 — 조합 없는 방향키 | "삼성"을 한 번에 넣고 ↓(40) 두 번 → 엔터 | pass | 두 번째 줄 `삼성물산(028260)` (맨 위 `삼성공조`) |
| New / updated tests | `npx vitest run tests/StockSearchEnter.test.tsx` | pass | 8 통과 — 조합 중 엔터 4건(T146) + 기존 FR-056 4건 |
| Regression suite (프론트엔드) | `npx vitest run` | pass | 66 파일 539 통과 |
| Regression suite (백엔드) | — | skipped | 이 수정은 백엔드를 바꾸지 않았다(`StockSearch.tsx`·프론트엔드 테스트·문서만) |
| Lint / type-check | `npx tsc --noEmit`, `npx eslint .` | pass | 둘 다 오류 없음 |

## Output Excerpts

브라우저 조작 (고친 뒤):

```
[삼성전자]       엔터 전 맨 위: ['삼성전자(005930)', '삼성전자우(005935)'] 칸: 삼성전자
                엔터 뒤: {'value': '', 'selected': '삼성전자(005930) KRX · KRW', 'options': []}
[현대차]         엔터 뒤: {'value': '', 'selected': '현대차(005380) KRX · KRW', 'options': []}
[삼성전자 + 조합 중 ↓×2]  엔터 뒤: {'value': '', 'selected': '삼성전자(005930) KRX · KRW', 'options': []}
[VOO, 조합 없음]  엔터 뒤: {'value': '', 'selected': 'S&P 500 뱅가드 ETF(VOO) NYSE · USD', 'options': []}
[삼성, 조합 없음, ↓×2]  엔터 뒤: {'value': '', 'selected': '삼성물산(028260) KRX · KRW', 'options': []}
```

이벤트 기록(fix 단계, 같은 순서): `keydown:Enter/229 composing value=삼성전자` → `compositionend data=자 value=삼성전자` →
`keydown:Enter/13 value=삼성전자` — 확정 뒤 엔터에서 고른다.

테스트:

```
tests/StockSearchEnter.test.tsx  Tests 8 passed (8)
전체  Test Files 66 passed (66) / Tests 539 passed (539)
tsc-ok / eslint-ok
```

## Residual Risks

- **실제 한글 입력기로 손으로 친 확인은 하지 않았다.** 브라우저 자동 조작은 DevTools 프로토콜로 macOS 한글 입력기의 이벤트 순서(조합
  중 엔터 229 → 확정 → 엔터 13)를 흉내 낸 것이다. 보고된 증상이 이 순서로 정확히 재현됐고 고친 뒤 사라졌지만, Windows 입력기·Safari의
  실제 순서는 흉내 내지 않았다 — Safari 순서(확정 뒤 keyCode 229 엔터)는 단위 테스트만 본다
- 확정 뒤 엔터가 오지 않는 입력기가 있다면 엔터를 두 번 쳐야 고른다(평가의 위험 — 틀린 종목이 골라지지는 않는다)
- 마지막 글자 직후(검색 응답 전) 엔터는 이전 검색어의 맨 위 결과를 고른다 — FR-056("보이는 목록의 맨 위") 범위 안이라 고치지 않았다

## Recommendation

버그를 닫는다 — 평가의 재현 순서를 실제 브라우저에서 다시 밟아 증상이 사라진 것을 확인했고, 다른 한글 검색어·조합 중 방향키·조합
없는 엔터와 방향키 선택도 기대대로였다. 실제 한글 입력기로 한 번 손으로 쳐 보는 것이 남은 확인이다(quickstart 29).
