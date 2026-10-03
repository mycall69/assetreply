# Bug Fix: 넓은 화면에서 성과 표의 열 사이가 지나치게 벌어진다

- **Slug**: table-column-width
- **Fixed**: 2026-10-03
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

성과 표를 칸 폭(`w-full`)에서 내용 폭(`w-max`)으로, 테두리 상자를 표에 맞게(`w-fit max-w-full`) 바꿨다. 열 폭이 값·열 이름 중 넓은
쪽 + 여백이 되어 넓은 화면에서 남는 폭이 열 사이로 나뉘지 않는다. 좁은 화면에서는 지금처럼 표만 가로로 스크롤된다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `frontend/src/components/stock/PerformanceTable.tsx` | modified | `<table>` `w-full` → `w-max`, 테두리 상자에 `w-fit max-w-full` |
| `frontend/tests/PerformanceTableWidth.test.tsx` | added | 폭 규칙 3건(T148, 먼저 커밋 `f47b7a8`) |
| `specs/006-stock-simulation-enhancements/spec.md` | modified | FR-069에 "열 폭은 내용에 맞춘다"와 실패 양상 |
| `specs/006-stock-simulation-enhancements/research.md` | modified | R6-26에 넓은 화면 결정과 측정 |
| `specs/006-stock-simulation-enhancements/plan.md` | modified | FR-069 추적 행에 T148·T149 |
| `specs/006-stock-simulation-enhancements/tasks.md` | modified | T148·T149 추가(테스트 커밋)·완료 표시, T144에 고친 사실, 같은 파일 표 |
| `specs/006-stock-simulation-enhancements/quickstart.md` | modified | 35에 넓은 화면 확인과 표를 찾는 방법 |

## Diff Highlights (optional)

```tsx
<div className="w-fit max-w-full rounded-lg border border-gray-200">
  …
  <div className="overflow-x-auto">
    <table className="w-max text-xs">
```

## Tests Added or Updated

- `frontend/tests/PerformanceTableWidth.test.tsx::열 폭 (FR-069) > 표가 칸 폭으로 늘어나지 않고 내용 폭이다`
- `…::좁은 화면에서는 표만 가로로 스크롤된다` — 회귀 방지(고치기 전에도 통과)
- `…::테두리 상자가 표에 맞고 칸보다 넓어지지 않는다`

jsdom은 배치를 재지 못해 폭 규칙만 본다. 실제 폭은 아래 브라우저 실측이다. 최초 실행(고치기 전): 2 실패 / 1 통과.

## Local Verification

- `npx vitest run` → 67 파일 542 통과. `npx tsc --noEmit`·`npx eslint .` 통과
- 브라우저(헤드리스 Chrome 154, 3030 경유) 실측 — 성과 표를 행(`tr[data-kind]`)에서 찾아 쟀다:

| 폭 | 종목 | 표 | 테두리 상자 | 칸 | 결과 |
|----|------|---:|---:|---:|------|
| 1920px | 삼성전자·2,000만 원 | 1,024px | 1,026px | 1,648px | 모든 열이 내용 + 여백(±1px). `구매 주식수` 108 → 67px, `날짜` 193 → 120px, `배당금 총액` 177 → 110px |
| 1920px | VOO·1,000만 원 | 1,103px | 1,105px | 1,648px | 같다 |
| 1440px | VOO | 1,103px | 1,105px | 1,168px | 열 15개 모두 보임, 스크롤 없음(FR-069 유지) |
| 1200px | VOO | 1,103px | 928px | 928px | 상자가 칸에 묶이고 표만 스크롤(926/1,103), 페이지 1,200px |

  1920px 스크린숏에서 테두리 상자가 표 오른쪽 끝에서 닫힌다(빈 테두리 없음).

## Deviations from Assessment

- 없음. 평가의 Open Question(열 이름도 줄여 값 폭까지 맞출지)은 답이 없어 평가의 제안대로 **열 이름은 한 줄, 열 폭 = 값·열 이름 중 넓은
  쪽**으로 했다(평가 보고 때 "답이 없으면 제안대로"라고 알렸다). 값이 열 이름보다 좁은 열(`구매 주식수` 값 7px·열 이름 56px)은 열 이름
  폭이 바닥이다

## Follow-ups

- 값 폭까지 줄이기를 원하면 열 이름을 두 줄(`구매` / `주식수`)로 끊는 변경이 필요하다 — R6-26이 읽기 어렵다고 뺀 방식이라 사용자 결정이
  먼저다
- 스크롤로 옛 행을 이어 받으면 더 긴 값(큰 잔고 등)으로 표가 넓어질 수 있다. 칸을 넘으면 표만 스크롤된다(평가의 위험)
