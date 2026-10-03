# Bug Fix: 주식 화면의 모든 API 요청이 프론트엔드에서 404 — 프록시가 `/api/fx`만 넘겼다

- **Slug**: stock-search-not-found
- **Fixed**: 2026-10-03
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

`frontend/next.config.ts`의 rewrite를 `/api/fx/:path*` 하나에서 **`/api/:path*` 하나**로 바꿔, 브라우저의
`/api/stocks/*` 요청이 백엔드에 닿게 했다. 프론트엔드 소스가 쓰는 모든 `/api` 접두사가 프록시되는지 검사하는
테스트를 먼저 커밋해, 다음 자산군이 같은 누락을 되풀이하면 테스트가 실패하게 했다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `frontend/tests/nextConfigProxy.test.ts` | added test | `rewrites()`의 규칙으로 주식·외환 주요 경로 9개와 소스의 모든 `/api` 접두사를 검사. 커밋 `07f4c82`(구현 전, 8 실패 / 2 통과) |
| `frontend/next.config.ts` | modified | rewrite `source: "/api/:path*"` → `${backendUrl}/api/:path*`. 주석에 결함 경위와 afterFiles 순서 근거 |
| `specs/006-stock-simulation-enhancements/tasks.md` | modified | T109(테스트)·T110(수정) 추가, 같은 파일 표, T090의 "화면 시나리오는 프론트엔드 테스트가 대신함" 가정 정정 |
| `specs/006-stock-simulation-enhancements/plan.md` | modified | Complexity Tracking "005·003 결함 수정이 섞인다"에 이 결함, 구조에 `next.config.ts` |
| `specs/006-stock-simulation-enhancements/quickstart.md` | modified | 실행 기록 "발견해 고친 결함" 6, "남은 것"의 화면 시나리오 가정 정정 |

## Diff Highlights (optional)

```ts
// frontend/next.config.ts
async rewrites() {
  return [
    {
      source: "/api/:path*",                        // 전: "/api/fx/:path*"
      destination: `${backendUrl}/api/:path*`,      // 전: `${backendUrl}/api/fx/:path*`
    },
  ];
},
```

## Tests Added or Updated

- `frontend/tests/nextConfigProxy.test.ts::백엔드 API 프록시 > %s를 백엔드로 넘긴다` — `/api/stocks/search`·
  `/search/external`·`/selection`·`/simulation`·`/simulation/series`·`/progress`·`/settings`, `/api/fx/latest`·
  `/collection/stream`이 **같은 경로 그대로** 백엔드 주소로 넘어가는 규칙에 덮이는지
- `frontend/tests/nextConfigProxy.test.ts::백엔드 API 프록시 > 프론트엔드 소스가 부르는 모든 /api 접두사를 넘긴다` —
  `src/`의 `.ts`·`.tsx`에서 `/api/<접두사>`를 모아(지금 `/api/fx`·`/api/stocks`) 하나라도 덮이지 않으면 실패

## Local Verification

- Commands run:
  - `npx vitest run tests/nextConfigProxy.test.ts` (수정 전) → 8 실패 / 2 통과 — `/api/stocks/*` 7개 "expected
    undefined to be defined", 접두사 검사 "expected [ '/api/stocks' ] to deeply equal []"
  - `npx vitest run tests/nextConfigProxy.test.ts` (수정 후) → 10 통과
  - `npm test` → 56 파일, 447 통과
  - `npx tsc --noEmit` → 오류 없음
  - `npx eslint .` → 오류 없음
- Manual checks (실행 중인 개발 서버, 3030 경유, Next.js가 설정 변경을 자동 반영):
  - `GET /api/stocks/search?q=삼성` → **200** `application/json`, 결과 20건(삼성공조·삼성물산·삼성생명·삼성전기·
    삼성전자…), 목록 5개 단위 모두 `ready` (수정 전 404 HTML)
  - `GET /api/stocks/search/external?q=삼성` → 200 `application/json` (수정 전 404)
  - `GET /api/stocks/settings` → 200 `application/json` (수정 전 404)
  - `GET /api/stocks/progress?jobId=999999` → 200 `text/event-stream`, 백엔드의 `failed`("알 수 없는 작업") 이벤트 —
    진행 스트림이 백엔드에 닿는다
  - `GET /api/fx/latest?currency=USD` → 200 (회귀 없음)
  - `GET /stocks` → 200 `text/html` — 화면 경로가 프록시에 가려지지 않는다

## Deviations from Assessment

없음. 평가의 우선 해법(`/api/:path*` 하나 + 접두사 검사 테스트)을 그대로 적용했다.

## Follow-ups

- **브라우저로 화면 시나리오를 실제 실행한다** — 006 quickstart 7·13·6-2·W2a·W4·W1a. "프론트엔드 테스트가
  대신한다"는 가정은 이 결함으로 틀렸음이 드러났다. 검색 → 종목 고르기 → 실행 → 수집 진행 → 결과까지 한 번은
  손으로 지나가야 한다. 005의 화면 수동 검증(005 T109)도 같은 이유로 남아 있다
- 프론트엔드에 API 라우트 핸들러(`src/app/api/...`)를 만들 계획이 생기면, 그 경로가 백엔드로 가지 않는지
  (afterFiles 순서) 다시 확인한다
- `/speckit-bug-test slug=stock-search-not-found`로 검증 보고를 남긴다
