---
slug: fx-stale-coverage
status: verified
tested: 2026-10-05
---

# 검증: 화면을 연 뒤 수집한 통화의 환율 트렌드가 비어 있다

- **Slug**: fx-stale-coverage
- **Tested**: 2026-10-05
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## 요약

평가의 두 증상(화면을 연 뒤 수집된 통화의 빈 차트, 늘어난 `coveredThrough`가 차트에 들어오지 않음)이 수정 뒤 브라우저에서 재현되지 않는다.
회귀 테스트 4개와 프론트엔드 전체(1,133개)가 통과하고, 기존 테스트는 바뀌지 않았다.

## 수행한 검사

| 검사 | 명령 / 동작 | 결과 | 비고 |
|------|-------------|------|------|
| 재현 1 — 화면을 연 뒤 수집된 통화(수정 뒤) | 개발 서버 + 헤드리스 Chrome(CDP). 화면 진입 때의 커버리지 응답(StrictMode로 2번)에서 EUR을 빼 "화면을 연 때 EUR이 없던" 상태를 만든 뒤 EUR로 바꿈 → '전체' 프리셋 → 범위 안 날짜(2026-09-30) 고르기 | pass | 전환이 커버리지를 새로 받아 `EUR&from=2025-10-04&to=2026-10-04`, '전체'는 `from=1994-04-11&to=2026-10-04`, 차트 `표시 8,633개 중 2,000개`, "아직 수집된 데이터가 없습니다" 없음 |
| 재현 2 — 늘어난 coveredThrough(수정 뒤) | 진입 때 커버리지의 USD `coveredThrough`를 2026-10-01로 꾸민 뒤 JPY → USD로 갔다 옴(`loadAll` — 오늘 환율 새로고침과 같은 함수, ECOS를 부르지 않는 길) | pass | 진입 때 `to=2026-10-01`(꾸민 캐시) → 돌아온 뒤 `to=2026-10-04`(서버 값) |
| 회귀 테스트 | `npx vitest run tests/BugFxStaleCoverage.test.ts` | pass | 4 passed. 수정 전 커밋(b8c14bb)에서는 4 failed — R1이 `to 2025-10-04` = `from`(사용자 브라우저의 실측 요청과 같은 모양) |
| 프론트엔드 전체 | `npm test` | pass | 127 파일·1,133 passed |
| 타입·린트 | `npx tsc --noEmit` · `npx eslint .` | pass | 둘 다 종료 코드 0 |
| 기존 테스트 변경 | `git diff --stat b8c14bb~1 HEAD -- frontend/tests backend` | pass | 새 파일 `BugFxStaleCoverage.test.ts`뿐 — 헌법 D2 해당 없음 |
| 백엔드 | — | skipped | 이 수정은 백엔드를 바꾸지 않았다(diff 없음). 백엔드 전체 실행은 서버를 내려야 하고(같은 MySQL 스키마를 드롭·재생성) 약 7분 걸린다 |

## 출력 발췌

```
new_currency | coverage altered at entry 2 fresh after 1
  entry series ['fx/series?currency=USD&from=2025-10-04&to=2026-10-04', (같음)]
  after series ['fx/series?currency=EUR&from=2025-10-04&to=2026-10-04', 'fx/series?currency=EUR&from=1994-04-11&to=2026-10-04']
  chart 표시 8,633개 중 2,000개 | no-data notice False
grown_through | coverage altered at entry 2 fresh after 2
  entry series ['fx/series?currency=USD&from=2025-10-04&to=2026-10-01', (같음)]
  after series ['fx/series?currency=JPY&from=2025-10-04&to=2026-10-02', 'fx/series?currency=USD&from=2025-10-04&to=2026-10-04']
```

수정 전(사용자 브라우저, `logs/backend.log`): `GET /api/fx/series?currency=EUR&from=2025-10-04&to=2025-10-04`.

## 남은 위험

- **재현은 같은 상태를 꾸며서 했다** — 평가의 문자 그대로의 절차(화면을 연 채 EUR을 수집)는 EUR이 이미 수집되어 있어 다시 하려면 EUR 데이터를 지워야
  한다(되돌리기 어려운 작업이라 하지 않았다). 대신 진입 때 커버리지 응답에서 EUR을 빼 화면이 기억하는 상태를 같게 만들었다. 수정 전 같은 상태의 결과는
  사용자 브라우저의 실측 요청(위)과 회귀 테스트의 최초 실패로 확인했다.
- `setCurrency`의 범위 판정은 여전히 바꾸기 전 캐시로 한다 — 화면을 연 뒤 수집된 통화로 처음 바꿀 때 선택 날짜가 그 통화의 최근 고시일로 옮겨진다
  (fix.md 후속). 이번 결함(빈 차트)과 별개이고 옮겨진 날짜는 유효하다.
- 사용자가 이미 열어 둔 탭은 수정 전 코드다 — 새로 고쳐야 반영된다(개발 서버는 고친 코드를 내준다).

## 권고

결함을 닫는다 — 두 증상 모두 수정 뒤 브라우저에서 재현되지 않고, 회귀 테스트가 수정 전 실패·수정 뒤 통과로 결함을 고정한다.
