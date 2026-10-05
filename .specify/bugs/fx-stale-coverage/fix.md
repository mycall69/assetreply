---
slug: fx-stale-coverage
status: fixed
fixed: 2026-10-05
---

# 수정: 화면을 연 뒤 수집한 통화의 환율 트렌드가 비어 있다

- **Slug**: fx-stale-coverage
- **Fixed**: 2026-10-05
- **Assessment**: ./assessment.md
- **Status**: applied

## 요약

외환 스토어의 `loadAll`이 커버리지를 처음 한 번만 받아 두던 캐시를 없애, 부를 때마다(진입·통화 전환·오늘 환율 새로고침) 새로 받게 했다.
화면을 연 뒤 수집된 통화도 그 통화의 축적 범위로 차트를 요청하고, 매일 늘어난 `coveredThrough`도 다시 읽기 없이 들어온다.

## 바뀐 것

| 파일 | 변경 | 비고 |
|------|------|------|
| `frontend/src/stores/fxWorkspaceStore.ts` | 수정 | `loadAll` — `coverage.length > 0`이면 캐시를 쓰던 분기 제거, 늘 `/api/fx/coverage`를 받는다. R2-6 주석을 고친 이유와 함께 바꿨다 |
| `frontend/tests/BugFxStaleCoverage.test.ts` | 테스트 추가 | 회귀 넷(R1 둘·R2·R3) — 먼저 커밋(b8c14bb), 최초 실행 4 failed |

## 핵심 변경

```ts
// 전
const covPromise = coverage.length > 0
  ? Promise.resolve({ coverage })
  : apiClient.get<{ coverage: CoverageRow[] }>("/api/fx/coverage");
const cov = await covPromise;

// 후
const cov = await apiClient.get<{ coverage: CoverageRow[] }>("/api/fx/coverage");
```

## 더한 테스트

- `BugFxStaleCoverage.test.ts` "R1 — 그 통화로 바꾸면 축적 범위로 차트를 요청한다" — 캐시에 EUR이 없고 서버는 EUR을 알려 줄 때 `to`가 EUR의
  `coveredThrough`이고 `from ≠ to`, `coverageFor("EUR")`가 서버 값
- "R1 — 프리셋을 바꿔도 축적 범위 안이다" — 이어서 '전체' 프리셋이 `1994-04-11 ~ 2026-10-02`
- "R2 — 그 통화의 범위 안 날짜를 고르면 '수집된 데이터 없음'이 아니다" — `selectDate` 뒤 `notice`가 `null`
- "R3 — 오늘 환율 새로고침(loadAll)이 늘어난 coveredThrough까지 차트를 요청한다"

## 로컬 확인

- `npx vitest run tests/BugFxStaleCoverage.test.ts` → 수정 전 4 failed(R1 `to 2025-10-04` = `from` — 실측 증상과 같다), 수정 뒤 4 passed
- `npm test` → 127 파일·1,133 passed(이전 1,129 + 새 4). **기존 테스트 변경 없음**(헌법 D2 해당 없음)
- `npx tsc --noEmit`·`npx eslint` → 통과
- 브라우저(개발 서버, CDP): 화면 진입 때 받은 커버리지 응답 둘(StrictMode로 두 번)에서 EUR을 빼 "화면을 연 때 EUR이 없던" 상태를 만든 뒤 EUR로
  바꿨다 → 전환이 커버리지를 새로 받아 `series?currency=EUR&from=2025-10-04&to=2026-10-04`를 요청, 차트 242점. 수정 전 사용자 브라우저의 요청은
  `from=2025-10-04&to=2025-10-04`였다(`logs/backend.log`)

## 평가와 달라진 점

없음.

## 후속

- `setCurrency`의 범위 판정(`checkRange(kept, cov)`)은 여전히 **바꾸기 전** 캐시로 한다. 캐시에 그 통화가 없으면 유지하던 선택 날짜를 버리고
  그 통화의 최근 고시일로 옮긴다 — 화면을 연 뒤 수집된 통화로 처음 바꿀 때 한 번뿐이고 최근 고시일은 유효한 날짜라 이번 범위에서 고치지 않았다.
  고치려면 새 커버리지를 받은 뒤 판정해야 해 `setCurrency`·`loadAll`의 순서가 바뀐다.
- 통화 전환마다 작은 GET이 하나 는다(세 행). 로컬에서 체감 지연 없음.
