---
slug: fx-stale-coverage
status: assessed
created: 2026-10-05
reporter: 사용자 ("현재 EUR은 환율 트랜드가 보이지가 않아.")
---

# 평가: 화면을 연 뒤 수집한 통화의 환율 트렌드가 비어 있다

- **Slug**: fx-stale-coverage (자동 생성 — 사용자가 지정하지 않음)
- **Created**: 2026-10-05
- **Source**: 사용자 보고(대화) + 백엔드 접근 로그
- **Verdict**: valid
- **Severity**: medium

## 보고 내용

> 현재 EUR은 환율 트랜드가 보이지가 않아.

직전에 개발 DB에 EUR 전 구간을 수집했다(`POST /api/fx/collect` → jobId 13, 33/33 구간, 8,633일, 1994-04-11~2026-10-02).
요약 카드·일자별 표는 EUR 값으로 나오는데 트렌드 차트만 비어 있다.

## 증상

외환 화면을 **열어 둔 채로** 그 통화가 수집되면, 그 통화로 바꿨을 때 트렌드 차트가 빈 채로 남는다(오류·안내 없음). 기대: 수집된 범위의
차트가 프리셋대로 그려진다. 새로 고침(전체 다시 읽기)하면 나온다.

## 재현

1. 어떤 통화(EUR)의 데이터가 없는 상태에서 외환 화면을 연다 — 커버리지 응답에 EUR 행이 없다.
2. 화면을 닫지 않은 채(다른 메뉴로 갔다 와도 같다 — 스토어가 모듈 전역이다) EUR을 수집한다.
3. 통화 탭에서 EUR을 고른다 → 요약·표는 나오고 차트는 비어 있다. 프리셋(6개월·1년·10년…)을 바꿔도 비어 있다.

**실측 증거**(`logs/backend.log`, 사용자 브라우저):

```
GET /api/fx/series?currency=EUR&from=2025-10-04&to=2025-10-04   ← 1년 프리셋, 하루짜리(토요일) 구간
GET /api/fx/series?currency=EUR&from=2026-04-04&to=2026-04-04   ← 6개월
GET /api/fx/series?currency=EUR&from=2026-09-04&to=2026-09-04   ← 1개월
GET /api/fx/series?currency=EUR&from=2016-10-04&to=2016-10-04   ← 10년
```

같은 시각 새로 연 헤드리스 브라우저는 커버리지를 새로 받아 `from=2025-10-04&to=2026-10-04`(정상)를 요청했고 차트가 그려졌다.

## 의심 코드

- `frontend/src/stores/fxWorkspaceStore.ts` `loadAll` — `coverage.length > 0`이면 커버리지를 다시 받지 않는다(주석: "커버리지는 세 통화를 한 번에
  반환하므로 통화를 바꿔도 다시 받지 않는다", 002 research R2-6). 그 뒤 `to = row?.coveredThrough ?? from` — 현재 통화의 행이 없으면 **시작일을 끝으로**
  써서 하루짜리 구간을 요청한다.
- 같은 파일 `setPreset` — `coverageFor()`(캐시)로 같은 계산(`to = row?.coveredThrough ?? from`)을 한다 — 프리셋을 바꿔도 하루짜리다.
- 같은 파일 `setCurrency`·`selectDate` → `checkRange(date, null)` — 캐시에 행이 없으면 "아직 수집된 데이터가 없습니다"로 판정한다(데이터가 있는데도).
- `frontend/src/app/fx/page.tsx` — `TodayRefresh`의 `onRefreshed` → `loadAll()`. 캐시 때문에 새로 받은 날이 생겨도 커버리지의 `coveredThrough`가
  그대로라 차트 끝이 늘지 않는다(같은 원인의 다른 증상 — 코드로 확인, 화면 재현은 하지 않음).

## 원인 가설 (확신: 높음)

002가 "커버리지는 한 세션 동안 바뀌지 않는다"고 보고 처음 한 번만 받았다. 003이 수집을 백그라운드로 돌리면서 이 전제가 깨졌다 — 화면을 연 뒤에도
새 통화가 생기고, 매일 수집이 `coveredThrough`를 늘린다. 낡은 캐시에 통화의 행이 없을 때 `to = from`으로 메워 **실패가 드러나지 않는다**(빈 차트,
안내 없음 — 헌법 원칙 V의 "결측을 명시적으로"와도 어긋난다).

## 수정안

**권장**: `loadAll`이 부를 때마다 커버리지를 새로 받는다(캐시 조건 제거). `loadAll`은 진입·통화 전환·오늘 환율 새로고침에서 불리므로, 그 뒤의
`setPreset`·`selectDate`가 쓰는 `coverageFor()`도 그 시점 값이 된다. 비용은 통화 전환마다 작은 GET 하나(세 행)다 — R2-6이 아낀 것이 이 하나다.

**대안**:
- 현재 통화의 행이 캐시에 없을 때만 다시 받는다 — EUR 증상은 고치지만 `coveredThrough`가 낡는 증상(차트 끝이 늘지 않음)은 남는다.
- 수집 완료 이벤트(SSE)를 받아 커버리지를 갱신한다 — 정확하지만 외환 화면이 수집 스트림을 구독해야 해 범위가 커진다.

**바뀔 파일**:
- `frontend/src/stores/fxWorkspaceStore.ts` — `loadAll`의 커버리지 캐시 제거, R2-6 주석 고침
- `frontend/tests/BugFxStaleCoverage.test.ts`(신규) — 회귀 테스트

**더할 테스트**:
- 캐시된 커버리지에 EUR이 없고 서버는 EUR을 알려 줄 때 `setCurrency("EUR")` → 차트 요청이 `from=1년 전 & to=EUR coveredThrough`(하루짜리가 아님),
  `coverageFor("EUR")`가 값이 있다
- 그 뒤 EUR 범위 안의 날짜를 고르면 "아직 수집된 데이터가 없습니다" 안내가 없다
- 오늘 환율 새로고침(`loadAll`)이 커버리지를 다시 받아 차트 `to`가 늘어난 `coveredThrough`가 된다

## 위험

- 기존 테스트 중 `loadAll`을 부르면서 커버리지 요청을 처리하지 않는 모의 객체가 있으면 깨진다 — 전체 실행으로 확인한다. 기존 테스트를 고쳐야 하면
  헌법 D2(기존 테스트 변경 승인)에 해당하므로 따로 알린다.
- 요청 순서: 커버리지 → (최신·일자별·차트 병렬)로 지금과 같다 — 통화 전환의 체감 지연은 GET 하나만큼 는다(로컬 수 ms).

## 열린 질문

- 없음. 사용자의 즉시 해결책은 외환 화면을 새로 고치는 것(브라우저 새로 고침)이다.
