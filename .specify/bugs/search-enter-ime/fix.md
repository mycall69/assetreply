# Bug Fix: 한글을 조합 중에 엔터를 치면 고른 뒤 비운 검색 칸에 조합 중이던 글자가 들어간다

- **Slug**: search-enter-ime
- **Fixed**: 2026-10-03
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

검색 칸의 키 처리기가 한글 입력기의 조합 중 키 입력(`isComposing` 또는 keyCode 229)을 무시하게 했다. 조합 중 엔터는 입력기가 글자를
확정하는 데 쓰고, 고르기는 확정 뒤에 오는 엔터에서 한다. 그래서 칸을 비운 뒤 입력기가 조합 중이던 글자를 넣는 일이 없다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `frontend/src/components/stock/StockSearch.tsx` | modified | `onKeyDown` 맨 앞에 조합 중 판정 한 줄. 엔터·방향키 모두 |
| `frontend/tests/StockSearchEnter.test.tsx` | added tests | 조합 중 엔터 4건(T146, 먼저 커밋 `cf4a0e6`) |
| `specs/006-stock-simulation-enhancements/spec.md` | modified | FR-056에 "조합 중 엔터·방향키는 확정이다"와 실패 양상 |
| `specs/006-stock-simulation-enhancements/plan.md` | modified | FR-056 추적 행에 T146·T147 |
| `specs/006-stock-simulation-enhancements/tasks.md` | modified | T146·T147 추가(테스트 커밋)·완료 표시, T134에 고친 사실, 같은 파일 표 |
| `specs/006-stock-simulation-enhancements/quickstart.md` | modified | 29에 한글 입력기 확인과 자동 조작 시 조합 상태를 거칠 것 |

## Diff Highlights (optional)

```tsx
const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
  // 한글 조합 중의 키 입력은 입력기의 것이다(버그 search-enter-ime). …
  if (e.nativeEvent.isComposing || e.keyCode === 229) return;
  if (options.length === 0) return;
  …
```

## Tests Added or Updated

- `frontend/tests/StockSearchEnter.test.tsx::한글 조합 중 엔터 > 조합 중 엔터에서는 고르지 않고 칸도 그대로다`
- `…::조합이 확정된 뒤의 엔터에서 맨 위 결과를 한 번 고르고 칸이 빈다` — 조합 중 엔터 → 확정 → 엔터. 확정은 Chrome 기록대로
  "칸이 비었으면 확정한 글자가 빈 칸에 들어간다"로 흉내 낸다. 고치기 전에는 칸이 `자`였다
- `…::Safari 순서 — 조합 확정 뒤 오는 keyCode 229 엔터도 고르지 않는다`
- `…::조합 중 방향키는 항목을 옮기지 않는다` — 고치기 전에는 조합 중 방향키 두 번이 삼성전자우를 골랐다

최초 실행(고치기 전): 4 실패 / 4 통과(기존 FR-056 테스트).

## Local Verification

- `npx vitest run` → 66 파일 539 통과(고친 뒤 새 4건 포함). `npx tsc --noEmit`·`npx eslint .` 통과
- 브라우저(헤드리스 Chrome 154, 3030 경유, 1440px): 평가 때와 같은 순서 — `Input.insertText("삼성전")` →
  `Input.imeSetComposition("자")` → 조합 중 엔터(229) → 확정(`자`) → 엔터(13).
  - 고치기 전(평가): 칸 `자`, 목록 `자더`·`자빌`·`자비스`
  - 고친 뒤: 칸 비어 있음, `삼성전자(005930) KRX · KRW`가 골라져 보인다. 기록 — `keydown:Enter/229 composing value=삼성전자` →
    `compositionend data=자 value=삼성전자` → `keydown:Enter/13 value=삼성전자`(여기서 고른다)
- 실제 한글 입력기(macOS·Windows)로 손으로 친 확인은 하지 않았다

## Deviations from Assessment

- 없음. 평가의 제안(조합 중 판정 하나, 상태·지연 없음)대로 고쳤다

## Follow-ups

- 실제 한글 입력기로 손으로 확인한다 — 자동 조작은 macOS 입력기의 이벤트 순서를 흉내 낸 것이다
- 평가의 남은 위험: 마지막 글자 직후(검색 응답 전) 엔터는 이전 검색어의 맨 위 결과를 고른다. FR-056("보이는 목록의 맨 위") 범위
  안이라 고치지 않았다
