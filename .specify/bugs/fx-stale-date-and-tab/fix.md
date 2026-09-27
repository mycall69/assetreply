---
slug: fx-stale-date-and-tab
status: fixed
assessed: 2026-09-27
fixed: 2026-09-27
---

# 수정 보고: 외환 화면의 낡은 날짜 표시와 통화 탭 식별 불가

[assessment.md](./assessment.md)의 제안을 적용했다. **세 건 중 둘을 코드로 고쳤고, 하나는
관리자 조치가 필요해 남아 있다.**

## 적용한 것

### R3 — 통화 탭 배경 (#3, MEDIUM)

`frontend/src/components/fx/CurrencyTabs.tsx`

컨테이너에 배경이 없어 활성 탭의 `bg-white`가 **흰 페이지 배경 위 흰색**이 됐다. 구별되는
것은 글자 굵기와 옅은 그림자뿐이었다.

```diff
- <div role="tablist" className="inline-flex rounded-lg border border-gray-300">
+ <div role="tablist" className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5">

-   className={`px-4 py-2 text-sm first:rounded-l-lg last:rounded-r-lg ${
-     active ? "bg-white font-semibold text-gray-900 shadow-sm" : "text-gray-500"
+   className={`rounded-md px-4 py-2 text-sm transition ${
+     active ? "bg-white font-semibold text-gray-900 shadow-sm"
+            : "text-gray-600 hover:text-gray-900"
```

분절 컨트롤의 표준 형태는 **컨테이너가 회색, 활성 항목이 흰색**이다. 기존 코드는 후자만
가져오고 전자를 빠뜨렸다. 비활성 글자색도 `gray-500` → `gray-600`으로 올려 대비를 확보했다.

이 변경은 002 외환 화면과 003 수집 화면 **양쪽에 적용된다** — 두 화면이 같은 컴포넌트를
쓴다.

### R2 — 범위 밖 날짜 선택 시 입력값 정합 (#2, LOW)

`frontend/src/stores/fxWorkspaceStore.ts`

```diff
  const notice = checkRange(date, cov);
  if (notice) {
-   set({ notice });
+   set({ selectedDate: date, notice });
    return;
  }
```

**FR-010은 "값을 반환하지 않는다"를 요구할 뿐 선택을 거절하라고 하지 않았다.** 이전
구현은 안내를 띄우면서 입력값을 되돌려, 안내와 화면이 서로 다른 날짜를 가리켰다. 사용자
눈에는 클릭이 먹지 않은 것으로 보인다.

값을 받지 않는 것은 그대로다 — `apiClient.get`이 호출되지 않음을 테스트가 고정한다.

### R1 — 테스트 DB 분리 (#1 재발 방지, HIGH)

`backend/tests/conftest.py` [신규]

통합 테스트의 `reset_schema()`가 개발 DB의 모든 테이블을 드롭·재생성해 **수집해 둔 실제
데이터를 통째로 날렸다.** 이번 보고의 근본 원인이다.

`DB_NAME`에 `_test` 접미사를 붙여 별도 데이터베이스로 보낸다. 환경변수를 모듈 임포트
시점에 바꾸는 이유는 `reset_schema()`가 내부에서 `load_settings()`를 다시 부르기 때문이다
— 픽스처로 설정 객체만 갈아끼우면 그 경로가 여전히 개발 DB를 본다.

## 남은 것 — 관리자 조치 필요

애플리케이션 DB 사용자(`assetreplay`)에게 **데이터베이스 생성 권한이 없다.** 정상이다 —
운영 계정이 그 권한을 갖지 않는 편이 낫다.

관리자 계정으로 한 번 실행해야 한다.

```sql
CREATE DATABASE `assetreplay_test` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON `assetreplay_test`.* TO 'assetreplay'@'localhost';
FLUSH PRIVILEGES;
```

이때까지 **백엔드 테스트는 돌지 않는다.** `conftest.py`가 위 SQL을 그대로 안내하며 중단한다.

## 고치지 않은 것 — #1의 현재 데이터

개발 DB에 남은 스텁 데이터(USD 12행, 전부 1200.00, 2020년)는 그대로다. 화면에서 수집을
시작하면 실제 값으로 채워진다.

**ECOS 일일 한도를 쓰므로 사용자가 판단할 일이다.** 통화 하나 백필이 약 146회이고 실측
하한이 150회다.

## 기존 테스트 하나를 갱신했다

`frontend/tests/selectedDate.test.ts`의 `조회 가능 범위 밖이면 알리고 상태를 바꾸지 않는다`가
**옛 전제를 인코딩**하고 있었다. R2가 그 동작을 의도적으로 바꾸므로 테스트도 함께 고쳤다.

```diff
- it("조회 가능 범위 밖이면 알리고 상태를 바꾸지 않는다", ...)
-   expect(selectedDate).toBe("2026-08-29");   // 이전 날짜 유지
+ it("조회 가능 범위 밖이면 알리되 선택은 반영한다", ...)
+   expect(selectedDate).toBe("1900-01-01");   // 요청한 날짜
+   expect(get).not.toHaveBeenCalled();        // 값은 여전히 받지 않는다
```

002가 의도적으로 구현하고 테스트한 동작을 바꾼 것이므로, 변경 사유를 테스트 주석에 남겼다.

## 남은 판단 — 사용자 확인 필요

R2 이후 **범위 밖 날짜를 고르면 입력값은 그 날짜인데 요약·표·차트는 이전 데이터를 그대로
보여준다.** 안내가 이유를 설명하지만, 화면 전체가 일관되지는 않는다.

대안은 범위 밖일 때 요약·표를 **값 없음 상태로 비우는** 것이다. 다만 그건 FR-010이 말하는
"값을 반환하지 않는다"의 화면 표현을 새로 정하는 일이라, 002 명세를 손대야 할 수 있다.
이번 수정 범위 밖으로 두고 사용자 판단을 기다린다.

## 검증

```
프론트엔드  178 passed (25 files) — 신규 회귀 9건 포함
tsc · eslint  통과
렌더링 확인   tablist에 bg-gray-100, 활성 탭에 bg-white 적용됨
백엔드        관리자 조치 전까지 실행 불가 (의도된 중단)
```

## 변경 파일

| 파일 | 변경 |
|------|------|
| `backend/tests/conftest.py` | [신규] 테스트 DB 분리 |
| `frontend/src/components/fx/CurrencyTabs.tsx` | 컨테이너 배경, 활성/비활성 대비 |
| `frontend/src/stores/fxWorkspaceStore.ts` | 범위 밖 선택 반영 |
| `frontend/tests/BugFxStaleDateAndTab.test.tsx` | [신규] 회귀 테스트 9건 |
| `frontend/tests/selectedDate.test.ts` | 옛 전제 테스트 갱신 |


---

## 추가 발견 (2026-09-27, 실제 수집 검증 중)

`#1`의 데이터를 실제로 채우려고 수집을 돌리다 **더 심각한 버그 둘**이 드러났다.
**수집은 한 번도 성공한 적이 없었다.**

### 버그 4 — `EcosClient`를 열지 않고 썼다

```
RuntimeError: EcosClient를 async with로 열어야 합니다.
```

`api/main.py`의 `lifespan`이 `EcosClient(settings)`를 그대로 워커에 넘겼다. `async with`로
들어가야 HTTP 세션이 생기는데 열지 않았다. **003 T024에서 만든 결함이다.**

첫 호출에서 예외가 나는데 `run_once`는 `SourceError`만 잡으므로, 그 예외가 `worker_loop`의
광범위 `except`까지 올라가 `"수집에 실패했습니다"`로만 남았다. 화면에는 작업이 생기고
끝나는 것처럼 보였다.

`worker/runner.py`의 `worker_loop`이 소스 수명을 직접 관리하도록 고쳤다. 회귀 테스트 2건을
넣었다 — 열지 않은 소스로는 수집이 되지 않음을, 종료 시 소스를 닫음을 고정한다.

### 버그 5 — 원본 응답 컬럼이 너무 작았다

```
DataError: (1406, "Data too long for column 'body' at row 1")
```

001이 `fx_raw_response.body`를 `TEXT`(65,535바이트)로 정의했는데 **한 해치 ECOS 응답이
그보다 크다.** 1964년이 197행에 57KB였고, 거래일이 많은 해(약 260행)는 75KB에 이른다.

청크를 줄이는 대안은 호출 수를 늘려 일일 한도를 더 쓰므로 컬럼을 키우는 쪽이 맞다.
`Text(length=16_777_215)`로 바꾸고 마이그레이션 `e7f2b1a94c63`을 추가했다.

### 왜 이제서야 드러났는가

**001·002·003 모두 스텁 소스로만 테스트했다.** 헌법 원칙 III이 요구하는 "네트워크 없이
통과"를 지키느라 실제 응답을 한 번도 보지 않았고, 그 결과 응답 크기와 클라이언트 수명이
검증 대상에서 빠졌다.

세 기능이 모두 통과 상태였는데 **파이프라인 전체가 실제로는 한 번도 돈 적이 없었다.**
스텁 테스트의 한계를 보여주는 사례다.

### 수집 결과

```
USD  17,514행, 1964-05-04 ~ 2026-09-23, 서로 다른 값 6,024개
     63회 호출로 전체 백필 완료, 오류 0건
```

JPY·EUR은 아직 비어 있다.
