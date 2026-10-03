# Bug Assessment: 주식 화면의 모든 API 요청이 프론트엔드에서 404 — 프록시가 `/api/fx`만 넘긴다

- **Slug**: stock-search-not-found
- **Created**: 2026-10-03
- **Source**: pasted text (+ 스크린샷)
- **Verdict**: valid
- **Severity**: critical

## Report (verbatim or summarized)

> 종목에 '삼성'을 입력해도 Not Found라고 나와

스크린샷: `/stocks` 화면의 종목 칸에 "삼성"을 넣으면 검색 목록의 **국내·미국** 영역과 **일본** 영역이 둘 다
빨간 글씨로 "Not Found"를 보인다.

## Symptom

브라우저에서 종목을 검색하면 두 영역 모두 "Not Found"가 나온다. 기대 동작은 국내·미국 영역에 삼성전자·삼성물산
등 로컬 목록 결과가, 일본 영역에 외부 검색 결과(없으면 "결과 없음")가 나오는 것이다. 검색만이 아니라 **주식
화면의 모든 백엔드 요청**(`/api/stocks/*` — 검색, 종목 등록, 시뮬레이션 표·차트, 설정, 진행 스트림)이 같은 이유로
실패한다.

## Reproduction

1. `./start.sh`(백엔드 8080, 프론트엔드 3030)
2. 브라우저로 `http://localhost:3030/stocks`를 열고 종목 칸에 "삼성"을 입력한다
3. 두 영역이 "Not Found"를 보인다

같은 요청을 직접 보내 확인했다(2026-10-03):

| 요청 | 결과 |
|------|------|
| `GET http://127.0.0.1:8080/api/stocks/search?q=삼성` (백엔드 직접) | **200**, 삼성공조·삼성물산·삼성생명… |
| `GET http://127.0.0.1:8080/api/stocks/search/external?q=삼성` (백엔드 직접) | **200**, `results: []` |
| `GET http://127.0.0.1:3030/api/stocks/search?q=삼성` (프론트엔드 경유) | **404**, Next.js의 HTML 404 페이지 |
| `GET http://127.0.0.1:3030/api/stocks/search/external?q=삼성` (프론트엔드 경유) | **404** |
| `GET http://127.0.0.1:3030/api/stocks/settings` (프론트엔드 경유) | **404** |
| `GET http://127.0.0.1:3030/api/fx/latest?currency=USD` (프론트엔드 경유) | **200** |

백엔드는 정상이고, 프론트엔드를 거친 `/api/stocks/*`만 404다.

## Suspected Code Paths

- `frontend/next.config.ts:rewrites()` — 프록시 규칙이 **`/api/fx/:path*` 하나뿐이다.** 001(`573088b`)에서 만든 뒤
  바뀐 적이 없다. 005가 `/api/stocks/*` 라우트를 더했지만 여기에 규칙을 더하지 않았다. 그래서 브라우저의
  `/api/stocks/*` 요청은 백엔드로 가지 않고 Next.js가 직접 받아 404 페이지를 돌려준다.
- `frontend/src/lib/apiClient.ts:request()` — 응답 본문이 JSON이 아니면 `res.statusText`를 메시지로 쓴다. Next.js의
  HTML 404라 `"Not Found"`가 그대로 화면에 나온다(증상 문구의 출처).
- `frontend/src/components/stock/StockSearch.tsx:177`·`:196` — `/api/stocks/search`·`/api/stocks/search/external`를
  부르고 실패하면 각 영역에 오류 메시지를 보인다. 두 영역이 같은 문구를 보이는 이유다(코드 자체는 맞다).
- `frontend/src/lib/stockProgressStream.ts:33` — 진행 스트림 `EventSource`도 `/api/stocks/progress`라 같은 이유로
  연결되지 않는다.
- 백엔드 라우트 접두사는 `/api/fx`(10개)와 `/api/stocks`(6개)뿐이다. 프론트엔드의 `src/app` 아래에는 **API 라우트
  핸들러가 없다**(`src/app/{fx,settings,stocks}`는 화면이다).

## Root Cause Hypothesis

**신뢰도: 높음.** `next.config.ts`의 rewrite가 `/api/fx/:path*`만 백엔드로 넘기므로 `/api/stocks/*`는 프록시되지
않는다. 위 표의 직접 요청으로 확인했다. 005·006 내내 드러나지 않은 이유는 셋이다. ① 프론트엔드 테스트는 모두
`apiClient`를 흉내 내어 프록시를 거치지 않는다. ② 수동 검증(005 quickstart, 006 T090)은 백엔드(8080)를 직접
불렀다. ③ 006 T090은 화면 조작 시나리오를 "프론트엔드 테스트가 대신한다"고 기록했다(이 결함으로 그 가정이
틀렸음이 드러났다). 005의 화면 수동 검증(005 T109)은 끝나지 않은 채 남아 있었다(006 research R6-17).

## Proposed Remediation

**Preferred**: rewrite 규칙을 **`/api/:path*` → `${backendUrl}/api/:path*` 하나로** 바꾼다. 프론트엔드에는 API 라우트
핸들러가 없고, 배열로 돌려준 rewrite는 Next.js가 자기 화면·정적 파일을 먼저 확인한 뒤에(afterFiles) 적용하므로
화면 경로와 부딪히지 않는다. 자산군마다 접두사를 더해야 하는 구조를 없애, 다음 자산군(가상자산)이 같은 결함을
되풀이하지 않게 한다. 주석의 근거(CORS·SSE)는 그대로 유지한다.

그리고 **프록시를 검사하는 테스트**를 더한다. `next.config.ts`의 `rewrites()`를 불러, 프론트엔드 소스가 부르는
모든 `/api/<접두사>`(지금은 `/api/fx`·`/api/stocks`)가 어떤 규칙으로든 백엔드로 넘어가는지 확인한다. 소스에서
접두사를 모아 검사하므로, 새 접두사를 쓰고 규칙을 빠뜨리면 테스트가 실패한다.

**Alternatives**:
- `/api/stocks/:path*` 규칙만 하나 더한다 — 변경이 가장 작지만 자산군을 더할 때마다 같은 누락이 생길 수 있다. 위
  검사 테스트와 함께라면 누락은 잡힌다.
- 백엔드에 CORS를 열고 `NEXT_PUBLIC_API_BASE_URL`로 직접 부른다 — `next.config.ts` 주석이 기각한 방식이다(허용
  출처 관리, SSE의 CORS). 택하지 않는다.

**Files likely to change**:
- `frontend/next.config.ts`
- `frontend/tests/nextConfigProxy.test.ts` (신규)
- `specs/006-stock-simulation-enhancements/tasks.md`·`plan.md`·`quickstart.md` — 결함 기록(005 결함 수정이 섞이는
  항목, T090 실행 기록의 "화면 시나리오는 프론트엔드 테스트가 대신함" 가정 정정)

**Tests to add or update**:
- `next.config.ts`의 `rewrites()`가 `/api/stocks/search`·`/api/stocks/progress`·`/api/fx/latest`를 백엔드
  주소로 넘기는지
- 프론트엔드 소스(`src/`)가 쓰는 모든 `/api/<접두사>`가 rewrite 규칙에 덮이는지 — 새 접두사의 누락을 막는다
- 헌법 원칙 III에 따라 테스트를 먼저 커밋하고 최초 실행 실패(`/api/stocks`가 덮이지 않음)를 확인한 뒤 고친다

## Risks & Considerations

- **개발 서버 재시작**: Next.js 개발 서버는 `next.config.ts` 변경을 감지해 다시 시작하지만, 반영되지 않으면
  `fe-stop.sh`·`fe-start.sh`로 다시 띄워야 한다. 확인 절차에 넣는다.
- **범위가 넓어진다**: `/api/:path*`는 앞으로 생길 모든 `/api/*`를 백엔드로 보낸다. 프론트엔드에 API 라우트
  핸들러를 만들 계획이 생기면 그 경로가 백엔드로 가지 않는지(afterFiles 순서) 다시 확인해야 한다. 지금은 없다.
- **보안**: 프록시 대상은 서버 쪽 환경변수(`BACKEND_URL`·`BE_PORT`)로만 정해지고 브라우저에 노출되지 않는다.
  바뀌지 않는다.
- **검증 공백**: 이 결함은 프론트엔드 테스트가 `apiClient`를 흉내 내어 생긴 공백에서 나왔다. 고친 뒤 브라우저(또는
  3030 경유 요청)로 검색·실행·진행 스트림을 실제로 확인해야 한다. 006 T090의 화면 시나리오(7·13·6-2·W2a·W4·W1a)가
  "프론트엔드 테스트가 대신함"으로 남아 있는데, 그 가정을 거두고 실제로 실행해야 한다.
- **005 결함**: 005부터 있던 결함이다. 006 plan의 Complexity Tracking "005·003 결함 수정이 섞인다" 항목에 더한다.

## Open Questions

- 없음. 원인과 재현이 직접 요청으로 확인되었다.
