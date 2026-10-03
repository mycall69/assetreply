# Bug Verification: 주식 화면의 모든 API 요청이 프론트엔드에서 404 — 프록시가 `/api/fx`만 넘겼다

- **Slug**: stock-search-not-found
- **Tested**: 2026-10-03
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

원래 증상은 더 이상 재현되지 않는다. 실제 브라우저(헤드리스 Chrome)로 `/stocks`에서 "삼성"을 입력하자 두 검색
요청이 200으로 백엔드에 닿았고, 국내·미국 영역에 삼성 종목 20건이, 일본 영역에 "일본 종목을 찾지 못했습니다"가
나왔다 — "Not Found"는 없다. 프론트엔드 전체 테스트·타입·린트가 통과했고 회귀는 발견되지 않았다.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix, 브라우저) | 헤드리스 Chrome 154를 DevTools 프로토콜로 조작(`scratchpad/cdp_search.py`): `http://localhost:3030/stocks` 열기 → 검색 칸(`aria-label="종목 검색"`)에 "삼성" 입력 → 4초 뒤 두 영역의 글자·`role=alert`·네트워크 응답·스크린샷 수집 | pass | `/api/stocks/search`·`/search/external` 모두 200. 국내·미국 20건 + "결과가 더 있습니다" + 목록 기준 시각. 일본 "일본 종목을 찾지 못했습니다". 오류 알림 0건 |
| Reproduction (post-fix, HTTP) | 평가의 재현 표와 같은 요청을 3030 경유로 `curl` | pass | 검색·외부 검색·설정 200 `application/json`(수정 전 404 HTML), `/api/fx/latest` 200 |
| 화면 경로 회귀 | `curl` 3030 `/stocks`·`/fx` | pass | 둘 다 200 `text/html` — `/api/:path*` 규칙이 화면 경로를 가리지 않는다 |
| New / updated tests | `npx vitest run tests/nextConfigProxy.test.ts` | pass | 10 통과. 수정 전 커밋 `07f4c82`에서 8 실패 / 2 통과를 확인했다 |
| Regression suite (프론트엔드) | `npm test` | pass | 56 파일, 447 통과 |
| Regression suite (백엔드) | — | skipped | 이 수정은 백엔드를 바꾸지 않았다(`git diff 3196b32..HEAD -- backend` 비어 있음). 개발 서버가 떠 있어 CLAUDE.md("개발 서버를 띄운 채 통합 테스트를 돌리지 말 것")에 따라 돌리지 않았다 |
| Lint / type-check | `npx tsc --noEmit`, `npx eslint .` | pass | 둘 다 종료 코드 0, 출력 없음 |

## Output Excerpts

브라우저 조작(헤드리스 Chrome)의 네트워크 응답과 화면 글자:

```
API responses:
  200 /api/fx/jobs?status=running&limit=5
  200 /api/fx/jobs?status=running&limit=5
  200 /api/stocks/search?q=%EC%82%BC%EC%84%B1
  200 /api/stocks/search/external?q=%EC%82%BC%EC%84%B1
국내·미국 영역: "국내·미국\n삼성공조\nKRX · KRW006660\n삼성물산\nKRX · KRW028260\n … 삼성스팩10호\nKRX · KRW0044K0\n\n결과가 더 있습니다. 검색어를 더 입력하세요.\n\n목록 기준 KOSPI 10-03 00:05 · KOSDAQ 10-03 00:05 · NYSE 10-03 00:05 · NASDAQ 10-03 00:0…"
일본 영역: "일본\n\n일본 종목을 찾지 못했습니다."
alerts: []
```

스크린샷(`scratchpad/search_after_fix.png`)은 보고된 스크린샷과 같은 화면에서 "Not Found" 대신 삼성공조·삼성물산·
삼성생명·삼성전기·삼성전자… 목록을 보인다.

```
nextConfigProxy:  Test Files 1 passed (1) / Tests 10 passed (10)
npm test:         Test Files 56 passed (56) / Tests 447 passed (447)
tsc exit=0, eslint exit=0
```

## Residual Risks

- **입력 방식**: 브라우저 조작은 `Input.insertText`로 "삼성"을 한 번에 넣었다. 실제 한글 입력의 조합(IME composition)
  이벤트는 거치지 않았다. 이 결함은 프록시 문제라 입력 방식과 무관하지만, 받침 대기 규칙(research R6-5) 같은 조합
  중 동작은 이 검증이 덮지 않는다(프론트엔드 테스트가 덮는다).
- **검색 뒤의 흐름은 이 검증 범위 밖이다**: 종목 고르기(`/api/stocks/selection`) → 실행(`/simulation`) → 수집 진행
  (`/progress` SSE) → 결과 표·차트까지 브라우저로 끝까지 지나가지는 않았다. 같은 규칙으로 넘어가며 3030 경유
  `/settings`·`/progress`가 백엔드에 닿는 것은 fix 단계에서 확인했다. 006 quickstart의 화면 시나리오
  (7·13·6-2·W2a·W4·W1a)를 브라우저로 실행하는 일이 남아 있다(tasks T090).
- **백엔드 스위트를 돌리지 않았다** — 백엔드 변경이 없어 영향은 없다고 판단했다.
- 헤드리스 Chrome 154에서 확인했다. 사용자의 브라우저 종류에 따른 차이는 이 결함(서버 쪽 프록시)과 무관하다.

## Recommendation

버그를 닫는다 — 실제 브라우저에서 원래 재현 단계를 다시 밟아 증상이 사라진 것을 확인했고, 회귀 테스트가 같은
누락(프록시되지 않는 `/api` 접두사)을 앞으로 잡는다. 다만 이 결함은 주식 화면 전체가 브라우저에서 한 번도 동작한
적이 없었다는 뜻이므로, 검색 이후의 흐름(고르기 → 실행 → 수집 → 결과)을 브라우저로 한 번 끝까지 지나가는
화면 시나리오 검증(006 T090의 남은 항목)을 이어서 하기를 권한다.
