# Bug Assessment: 한글을 조합 중에 엔터를 치면 고른 뒤 비운 검색 칸에 조합 중이던 글자가 들어간다

- **Slug**: search-enter-ime
- **Created**: 2026-10-03
- **Source**: pasted text (스크린숏 동반)
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

> 2. 종목 검색에서 '삼성전자'를 치면 삼성전자가 가장 위에 나오므로 엔터를 치면 자동으로 삼성전자가 선택되어야 하는데, 지금 '자'가
> 선택되어 자로 시작하는 종목 목록이 보이게 돼.

같은 보고의 1번(표 열 폭)은 원인과 파일이 달라 `table-column-width`로 나눴다(사용자 결정 2026-10-03).

## Symptom

검색 칸에 한글로 "삼성전자"를 치고 곧바로 엔터를 치면, 검색 칸이 `자`가 되고 `자`로 시작하는 종목 목록(자더·자빌·자비스…)이
열린다. 기대 동작은 맨 위 결과인 삼성전자가 골라지고 칸이 비는 것이다(006 FR-056).

실제로는 **삼성전자가 골라지기는 한다** — 칸을 비우면 `삼성전자(005930) KRX · KRW`가 보이고 실행 버튼이 켜진다. 그러나 칸에
`자`가 남아 고른 종목 줄이 가려지고(`StockSearch.tsx:310` — 검색어가 있으면 숨긴다) `자` 검색 결과가 열린다. 사용자는 삼성전자가
골라지지 않았다고 읽고, 그 목록에서 다시 엔터나 클릭을 하면 **다른 종목이 골라진다.**

## Reproduction

1. 브라우저(3030)의 `/stocks`에서 검색 칸에 한글 입력기로 "삼성전자"를 친다. 마지막 글자 `자`는 아직 조합 중이다(밑줄)
2. 결과 목록 맨 위에 `삼성전자(005930)`가 보이는 상태에서 방향키 없이 엔터를 친다
3. 칸이 `자`가 되고 `자`로 시작하는 종목 목록이 열린다

헤드리스 Chrome 154에서 DevTools 프로토콜로 재현했다(2026-10-03, `scratchpad/cdp_ime.py`). `Input.insertText("삼성전")` →
`Input.imeSetComposition("자")`(조합 중) → macOS 한글 입력기의 순서대로 조합 중 엔터(keyCode 229) → 조합 확정(`자`) → 엔터(13).
칸에 단 이벤트 기록:

```
input data=삼성전 value=삼성전
compositionstart value=삼성전
input composing data=자 value=삼성전자        ← 엔터 전: 목록 맨 위 '삼성전자(005930)'
keydown:Enter/229 composing value=삼성전자    ← 처리기가 여기서 고르고 칸을 비운다
input data=자 value=자                         ← 입력기가 조합 중이던 '자'를 빈 칸에 확정
keydown:Enter/13 value=자                      ← 결과가 비워져 있어 아무 일도 없다
```

엔터 뒤: 칸 `자`, 목록 `자더(JDZG)`·`자빌(JBL)`·`자비스(254120)`. 칸을 비우면 `삼성전자(005930) KRX · KRW`가 골라져 있다.

실제 입력기(macOS·Windows)에서 손으로는 재현하지 않았다 — 보고된 증상과 위 기록이 정확히 같다.

## Suspected Code Paths

- `frontend/src/components/stock/StockSearch.tsx:229` `onKeyDown` — `e.key === "Enter"`만 보고 고른다. **조합 중인지
  (`e.nativeEvent.isComposing`, keyCode 229)를 보지 않는다.** 한글 입력기는 조합 중 엔터를 "조합 확정"으로 쓰며, 그 keydown도
  `key: "Enter"`로 온다
- `frontend/src/components/stock/StockSearch.tsx:224` `choose` — `changeTerm("")`으로 칸을 비운다. 조합이 아직 끝나지 않아, 그
  뒤 입력기가 확정한 `자`가 빈 칸에 들어간다(제어 컴포넌트의 `onChange` → `changeTerm("자")` → 검색)
- `frontend/src/components/stock/StockSearch.tsx:310` — 검색어가 있으면 고른 종목 줄을 숨긴다. 그래서 골라진 삼성전자가 보이지 않는다
- `frontend/tests/StockSearchEnter.test.tsx` — `userEvent.type`·`userEvent.keyboard("{Enter}")`로 조합 없는 입력만 본다. 006 T129의
  테스트가 이 경로를 통과시킨 이유다
- quickstart 29의 브라우저 확인(T135)도 `Input.insertText`로 글자를 한 번에 넣어 조합이 없었다 — 같은 이유로 통과했다

## Root Cause Hypothesis

**신뢰도: 높음.** 엔터 처리기가 입력기의 조합 확정 엔터와 사용자의 선택 엔터를 구별하지 않는다. 한글은 마지막 글자가 거의 항상
조합 중인 채로 엔터를 치게 되므로, 한글 검색어를 치고 엔터를 치는 대부분의 경우에 일어난다. 처리기가 조합 중 엔터에서 고르고 칸을
비우면, 입력기가 그 뒤에 조합 중이던 글자를 빈 칸에 확정해 넣는다. 위 이벤트 기록이 그 순서를 그대로 보인다. 006 FR-056(T134)이
엔터 선택을 추가할 때 생겼다 — 그 전에는 엔터에 반응하지 않았다.

## Proposed Remediation

**Preferred**: `onKeyDown`에서 **조합 중인 키 입력은 무시한다** — `e.nativeEvent.isComposing`이 참이거나 `keyCode`가 229면 아무
것도 하지 않고 돌아간다(방향키도 같다). 입력기가 조합을 확정한 뒤 오는 엔터(keyCode 13, 조합 아님)에서 고른다. 그때 칸의 값은
확정된 `삼성전자`이고, 목록은 조합 중에 이미 받은 `삼성전자` 검색 결과다(위 기록의 엔터 전 상태).

- keyCode 229도 보는 이유: Safari는 조합 확정(`compositionend`)을 keydown보다 먼저 보내, 그 keydown의 `isComposing`이 거짓이고
  keyCode만 229다. `isComposing`만 보면 Safari에서 같은 결함이 남는다
- 구현은 이 판정 하나를 `onKeyDown` 맨 앞에 두는 것으로 끝난다. 입력기·브라우저마다 다른 이벤트 순서를 흉내 내는 상태(조합 중
  플래그, 지연 선택)를 두지 않는다

**Alternatives**:
- **조합 중 엔터를 기억했다가 `compositionend` 뒤에 고른다** — 확정 뒤 엔터가 한 번 더 오는 입력기에서는 두 번 고르게 되어 막는
  상태가 또 필요하다. 이벤트 순서가 입력기마다 달라 틀리기 쉽다
- **`choose`가 칸을 비우는 시점을 늦춘다**(`setTimeout`) — 확정된 글자가 늦게 들어오는 경우를 시간으로 맞추는 것이라 근거가 없다

**Files likely to change**:
- `frontend/src/components/stock/StockSearch.tsx` — `onKeyDown` 맨 앞의 조합 중 판정
- `frontend/tests/StockSearchEnter.test.tsx` — 조합 중 엔터 테스트 추가
- `specs/006-stock-simulation-enhancements/spec.md`(FR-056 실패 양상에 조합 중 엔터), `tasks.md`(새 태스크), `quickstart.md`(29의
  확인 방법 — 조합을 거치는 입력으로)

**Tests to add or update**:
- 조합 중 엔터(`keyDown` `key: "Enter"`, `isComposing: true`)에서는 고르지 않고 칸 값이 그대로다
- 조합 확정 뒤 엔터(keyCode 13)에서 맨 위 결과를 **한 번** 고르고 칸이 빈다 — 조합 중 엔터 + 확정 엔터의 연속에서 `onSelect`가
  정확히 한 번 불린다
- Safari 순서: `isComposing` 거짓·keyCode 229인 엔터도 무시한다
- 조합 중 방향키도 무시한다(조합 중 방향키는 입력기가 쓴다)
- 기존 FR-056 테스트(조합 없는 엔터·방향키 선택·결과 없음)는 그대로 통과해야 한다
- 헌법 원칙 III: 테스트를 먼저 커밋하고 최초 실패를 확인한다
- 브라우저 재확인: `cdp_ime.py`의 순서(조합 중 엔터 → 확정 → 엔터)로 칸이 비고 `삼성전자(005930)`가 보이는지

## Risks & Considerations

- **조합 확정 뒤 엔터가 오지 않는 입력기**가 있다면 그 환경에서는 엔터를 두 번 쳐야 고른다. 틀린 종목이 골라지는 것보다 낫고, 확정
  뒤 엔터가 오는 것이 Chrome·Safari·Firefox의 한글 입력기에서 흔한 순서다(위 기록). 손으로 확인한 입력기는 없다
- **목록이 덜 갱신된 상태의 엔터**: 마지막 글자를 친 직후(입력 대기 150ms + 응답 전) 엔터를 치면 맨 위 결과는 그 전 검색어
  (`삼성전`)의 결과다. 이 수정의 범위 밖이다 — FR-056은 "보이는 목록의 맨 위"이고, 지금 재현에서는 엔터 전에 `삼성전자` 결과가 이미
  보였다
- 일본 종목 영역(외부 검색)도 같은 처리기를 쓰므로 함께 고쳐진다
- 데이터 위험 없음. 화면만 바뀐다

## Open Questions

- 없음 — 조합 중 엔터를 무시하는 것은 FR-056의 의도(보이는 맨 위 결과를 고른다)를 바꾸지 않는다
