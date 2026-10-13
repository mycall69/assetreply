# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 원칙 VIII에 따라 이 저장소의 모든 문서·주석·커밋 메시지는 한국어로 작성한다.
> 기술 용어, 라이브러리명, API 식별자, 코드 심볼은 원어를 유지한다.

이 파일에는 **늘 지킬 규칙과 색인**만 둔다. 영역별 구현 주의(출처·계산·차트·이력·비교·대시보드)는
[`docs/implementation-notes.md`](docs/implementation-notes.md)에 있다 — **그 영역을 고치기 전에 해당 절을 읽는다**(아래 색인).
기능별 요구·설계·실측 기록의 원본은 `specs/NNN-*/`다.

## 현재 상태

외환(FX)·가상자산·주식/ETF·예금·부동산 — **다섯 자산군이 모두 구현되어 있다.** 기능별 상세는 implementation-notes §1.

| 기능 | 자산군 | 요지 |
|------|--------|------|
| 001~004 | 외환 | 환율 축적·조회·시각화(ECOS, 청크 수집, 작업·점유), 분석 화면·전역 셸, 수집 실행 계층, 일자별 표의 일·주·월 |
| 005·006 | 주식/ETF | 배당 재투자 시뮬레이션, 키움 목록 검색(한글·초성)·종목 등록·원금 통화 — 고아 점유·분할 이중 적용 결함 수정 |
| 007 | 가상자산 | investing.com 코인 검색·일봉(UTC 하루)·소수 8자리 매수 후 보유 |
| 008 | 예금 | ECOS 수신금리로 1년 정기예금 재예치(세후 이자, 미발표 달 잠정) |
| 009 | 부동산 | 공공데이터포털 실거래로 아파트 매매 후 보유(시세 창·세법 표·보유세) |
| 010 | 네 자산군 | 차트 가격 선·커서 상자·이력 배치, 주식 잔고 = 종가, Npay 단지 링크, 매도 비용 보드 |
| 011 | 주식·가상자산·예금 | 적립식·정기 적금, 주식 매도 세금 설정 |
| 012 | 외환·주식·가상자산 | 외환 기간 전환 스크롤, 주식·가상자산 표의 일·주·월, 이력 로컬 DB, 현재 잔고 |
| 013 | 투자 비교 | `/compare` — 같은 조건의 대상 2개 이상(014가 끝을 설정으로 — 기본 20·최대 100), 저장한 비교, 단가 열, 투자 시뮬레이션 모달 |
| 014 | 대시보드 | `/dashboard` 지표 15개·주소 있는 모달·뉴스 세 칸·블랙 배경. 반복으로 외환 등락, 티커, 상장일, 처음 단위 월, 수익률 추이의 현재 가치 축·두 지점 확대, 확대 구간의 일 단위 자료, 기준금리, 투자 비교의 대상 수 설정, 주식·가상자산 표의 등락 |

005가 원칙 IX의 고정 순서를 한 칸 건너뛰었고(사용자 승인 — `specs/005-…/plan.md` Complexity Tracking) 007~009가 채웠다.
010~014는 새 자산군이 아니라 화면·투자 방식·비교·조회 화면의 개선이다.

헌법 원칙 II 이탈이 열 기록되어 있다 — 모두 개인 이용 전제의 **잠정** 결정이고, 도구를 공개하거나 여러 사용자에게 제공할 계획이
생기면 전제가 깨진다(목록·승인 위치는 implementation-notes §2):
- Yahoo **비공식 엔드포인트** — 주식 시세(005), 대시보드 지표 시세·일봉·장중(014)
- **공개되지 않은 내부 API** — investing.com(007), Npay 부동산 단지 자동완성(010), 네이버 증권 주요뉴스·뉴스 포커스·기준금리(014)
- **화면 HTML·내장 JSON** — Yahoo Finance 뉴스·종목 뉴스, Yahoo!ファイナンス ヘッドライン(014)

## 헌법이 최우선

`.specify/memory/constitution.md`가 최상위 규칙이다(v5.2.0, 원칙 9개). 모든 설계·구현·리뷰가 여기에 종속되고, `/speckit-plan`의
`Constitution Check`가 이 파일을 판정 기준으로 읽는다. 작업 전 반드시 통독할 것. 위반이 잦은 규칙:

- **금융 계산에 `float` 금지**(원칙 VI) — 코드는 `Decimal`, DB는 `DECIMAL`. `FLOAT`/`DOUBLE`은 곧바로 위반이다
- **동기 I/O 금지**(원칙 I) — 요청 경로에서 `requests`·동기 DB 드라이버·`time.sleep` 불가. 불가피하면 `run_in_executor`로 격리
- **테스트 우선**(원칙 III, NON-NEGOTIABLE) — 테스트를 먼저 커밋하고 최초 실행의 실패를 확인한 뒤 구현한다. 커버리지 80% 미만은 머지 차단
- **결측치 임의 보간 금지**(원칙 V) — 휴장일·결측치는 명시적으로 표현한다. 전일 값 자동 복사는 위반이다
- **요구사항 변경은 상위 산출물까지 같은 작업 단위에서**(명세 작성 규약) — FR/SC를 고치면 `plan.md` 추적성과 `tasks.md` 참조를
  그 자리에서 갱신한다. 참조하는 태스크가 없는 인수 기준은 위반이다
- **요구사항에는 실패 양상을 함께 쓴다**(명세 작성 규약) — 성공 조건만 적으면 구현이 빼먹어도 리뷰와 테스트를 함께 통과한다
- **한국어 문서화**(원칙 VIII)

## Spec-Kit SDD 워크플로

Spec-Kit 1.0.1(`integration: claude`, `feature_numbering: sequential`). 기능 개발은 슬래시 커맨드로 진행한다.

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks → /speckit-implement
```

- 보조: `/speckit-analyze`(산출물 일관성), `/speckit-checklist`, `/speckit-converge`(코드와 명세의 격차를 tasks.md에),
  `/speckit-taskstoissues`. 반복 변경은 `/speckit-iterate-define` → `/speckit-iterate-apply`
- 산출물은 `specs/NNN-<short-name>/` — `spec.md`(요구), `plan.md`(설계·Constitution Check), `research.md`·`data-model.md`·
  `contracts/`·`quickstart.md`(설계 부속), `tasks.md`(의존성 순서의 태스크)
- `spec.md`를 고치면 `plan.md`·`tasks.md`가 함께 낡는다 — 세 파일은 한 묶음으로 갱신한다(`/speckit-analyze`는 사후 검출일 뿐 미루기의 근거가 아니다)
- **작업 중인 기능은 git 브랜치가 아니라 `.specify/feature.json`이 정한다**(머신 로컬, `.specify/.gitignore`). 우선순위는
  `SPECIFY_FEATURE_DIRECTORY` → `SPECIFY_FEATURE` → `feature.json`. "Feature directory not found"면 이것부터 본다
- 스크립트는 `.specify/scripts/bash/`, 템플릿은 `.specify/templates/`(직접 고치지 말고 커맨드로 쓴다)

## 목표 아키텍처

### 계층 (원칙 IV — 위반 시 원칙 II·III이 함께 무력화됨)

```
수집(ingestion) → 저장(repository) → 도메인 계산(simulation) → API → UI
```

- **ingestion**: 출처별 어댑터. 벤더(kiwoom-rest-api, 공공데이터포털, 거래소 API, 한국은행 ECOS)의 응답 타입이 이 계층 밖으로
  새어나가면 안 된다. rate limit·인증·재시도 정책은 코드가 아닌 설정으로 선언한다
- **simulation**: DB·HTTP에 의존하지 않는 **순수 함수**. DB나 HTTP 없이 단독 테스트가 불가능한 계산 코드는 원칙 IV 위반이다
- 상위 계층은 하위 계층의 구체 구현이 아닌 `Protocol`에 의존한다

### 시계열 스키마 불변식 (원칙 V)

- `(자산 식별자, 날짜)` 복합 유니크 키 + upsert — 수집의 멱등성·재개 가능성
- 모든 레코드에 `source`, `ingested_at`. 원본(raw) 응답과 정규화 시계열을 **분리 저장**
- 주가는 수정주가와 원주가를 **구분 저장**(액면분할·병합·유상증자 명시 반영)
- 시각은 UTC 저장, 표시 때 거래소 현지 시간대(KST/EST/JST)로. 가상자산 일봉 기준 시각은 UTC 00:00

### 자산군 확장 순서 (원칙 IX — 고정)

```
FX → 가상자산 → 주식/ETF/지수 → 예금 → 부동산
```

한 번에 하나씩, **조회 API와 UI까지 동작하는 수직 슬라이스로 완결**한다. 수집 계층만 먼저 만들고 UI를 미루는 것은 위반이다.
부동산이 마지막인 까닭은 지역/단지/면적 축의 비정기 거래 데이터라 나머지 넷의 균일한 일별 시계열과 형태가 다르기 때문이다.

## 명령어·스택

설치·설정(DB 둘·`.env`·스키마)·첫 수집 순서는 [`INSTALL.md`](INSTALL.md)에 있다 — 설치 절차·필수 설정이 바뀌면 그 파일을 고친다.
실행 스크립트는 저장소 루트에 있다 — `start.sh`·`stop.sh`(둘 다), `be-start.sh`·`be-stop.sh`, `fe-start.sh`·`fe-stop.sh`.
백엔드 8080, 프론트엔드 3030.

```bash
cd backend && .venv/bin/python -m pytest -q --cov=src             # 테스트 + 커버리지
cd backend && .venv/bin/python -m mypy src                        # 타입 (strict)
cd backend && .venv/bin/python -m ruff check --no-cache src tests  # 린트
cd frontend && npm test && npx tsc --noEmit && npx eslint .
```

- **Python은 반드시 `.venv/` 안에서**(헌법 "Python 가상환경 [필수]") — `source activate`에 기대지 말고 `.venv/bin/python`
  (Windows `.venv\Scripts\python`)을 직접 부른다
- 백엔드: Python 3.11+, FastAPI, aiohttp / `pytest` + `pytest-asyncio` / `mypy` strict / uv 또는 poetry
- 프론트엔드: Next.js 16+, React 19+, Zustand, Lightweight Charts, Tailwind CSS / Vitest + React Testing Library /
  TypeScript 5.0+(`strict: true`, `any` 금지) / pnpm 또는 npm. `frontend/AGENTS.md` — 이 Next.js는 학습 데이터와 다르다
- DB: MySQL 8.0+(InnoDB, utf8mb4) + aiomysql. 스키마 변경은 마이그레이션(Alembic)으로만 — 수동 DDL 금지.
  **새 테이블·열을 더하면 개발 DB에 `alembic upgrade head`가 필요하다**
- **품질 게이트**(머지 전 전부): 전체 테스트 + 커버리지 80% 이상, mypy strict·TypeScript 타입 체크, 린트·포맷, 새 데이터 출처면 계약 테스트

## 늘 지킬 운영 규칙

- **백엔드는 반드시 단일 워커로 띄운다**(`--workers 1`, `be-start.sh`가 이미 지정). 003이 수집 워커를 앱 프로세스 안에 두므로 워커를
  여럿 띄우면 프로세스마다 수집 태스크가 생긴다 — DB 점유가 중복 실행은 막지만 확인 호출에 일일 한도를 낭비한다
- **자산군마다 수집 워커가 따로다** — `lifespan`의 열 태스크(FX 수집·점유 회수·주식·검색용 목록·코인 목록·가상자산·예금 금리·
  부동산·대시보드 지표·기준금리). 출처가 다르면 한도도 따로이고, 한 큐에 섞으면 한 수집이 다른 수집을 막는데 화면 어디에도 드러나지 않는다
- **개발 서버를 띄운 채 통합 테스트를 돌리지 말 것** — 테스트가 같은 MySQL의 스키마를 드롭·재생성하므로 그 사이 서버가 조회하면
  `Unknown column` 오류가 난다. `./stop.sh` → 테스트 → `./start.sh`
- **전체 테스트는 네트워크 없이 통과**해야 한다(원칙 III) — 외부 API는 저장한 응답 픽스처(본문만 — 주소·키·토큰 없이)로 계약 테스트한다
- **린트는 `--no-cache`로 돌린다** — 로컬 캐시가 임포트 순서(I001) 위반을 가린 적이 있다(007). 아직 없는 모듈은 ruff가 제3자로
  분류하므로, 테스트를 먼저 쓸 때 임포트는 **구현 뒤 기준**(전부 `src.*` 묶음)으로 정렬해 둔다
- **차트 테스트 모의**(010): 기존 차트 테스트의 `lightweight-charts` 모의는 파일마다 인라인이고 `createChart`·`addSeries`·`setData`·
  `subscribeCrosshairMove`·`timeScale().fitContent`·`remove`만 있다(어떤 모의는 `subscribeCrosshairMove`도 없다). 그 밖의 API
  (`createSeriesMarkers`·`subscribeClick`·`priceScale()`·`applyOptions`·`setVisibleRange`)나 라이브러리 열거형을 **그릴 때** 쓰면
  005~014의 차트 테스트가 함께 깨진다 — 새 API는 누름 같은 사용자 동작에서만 부른다
- **vitest는 종료 코드로 판정한다**(011) — jsdom에 `matchMedia`가 없어 실제 차트를 그리면 단언이 다 통과해도 종료 코드 1이다.
  결과 화면 테스트는 `lightweight-charts`를 모의하고 시계열 요청에는 시계열 응답을 준다
- **비밀**: 키·시크릿·토큰 값을 출력하거나 셸 인자로 넘기지 않는다. `.env`(저장소 루트)는 커밋하지 않는다. 키가 URL 질의에 들어가는
  출처(공공데이터포털)는 URL을 어디에도 남기지 않는다. 키움 인증 정보를 고치면 백엔드를 다시 띄운다(기동 때 읽는다)
- **로그는 두 곳이다** — `logs/backend.log`(웹서버 표준출력), `logs/collection.log`(수집·출처 호출의 구조화 로그). 섞지 않는다

## 영역별 구현 주의 — 색인 (`docs/implementation-notes.md`)

고치기 전에 그 절을 읽는다. 한 줄은 가장 자주 어기는 점이다.

- **§3 수집·출처**
  - ECOS(008) — 환율·예금 금리가 한 관문(`EcosGate`)을 지난다. 인증키는 발급일부터 2년, 만료되면 둘 다 `auth`
  - 공공데이터포털(009) — 네 자료 각각 활용신청, 오류 본문은 XML·JSON 둘, 하루 호출 수를 보내기 전에 DB에 센다
  - investing.com(007) — 브라우저형 사용자 에이전트 필수, 일봉은 UTC 하루·계산 끝은 UTC 어제, 빈 날은 출처 결측
  - 키움 검색용 목록(006) — 인증 정보가 없으면 `auth_missing`, 그날 처음 검색할 때 받는다
  - 외환 수집 요청은 `collection_gate.ensure_background_job`만 거친다 — 미리 작업·점유를 만들면 고아 점유
  - 주식 조회의 202(미수집·환율 커버리지), Yahoo는 원주가를 주지 않는다(어댑터가 되살린다 — 분할 이중 적용 주의)
  - Npay 단지 번호(010) — 한 번 찾아 저장, 실패는 저장하지 않음, 법정동 코드로 먼저 거른다
- **§4 계산·보드** — 주식 잔고 = 종가(010), 부동산·주식 보드의 매도 비용(보드만 — `summary.profit`은 보유 중),
  적립식은 따로 된 경로(011 — 가상자산 계산 끝 `calculation_end`, 테스트는 `utc_yesterday`를 바꿔 2027년 기준일), 정기 적금의 금리 계열 키
- **§5 화면·차트** — 성과 차트(가격 선은 `priceMissing`, 상자 자리는 `sourceEvent` 좌표), 두 지점 확대(`useChartZoom` — 외환·지표 포함, 확대 구간의 일 단위
  자료는 `viewFrom`·`viewTo`로 받고 계산은 그대로 — `useZoomDetail`),
  외환 스크롤(`useHeightHold`), 외환 등락(`change` — 서버 계산), 일자별 표의 단위(처음 월 — 서버 기본은 일),
  성과표 등락(`table_rows`가 쪽을 자르기 전에 직전 기간 대표일 — 분할 맞춤·날짜 칸 고정), 블랙 배경(`.dark` 재정의 짝·`chartTheme`)
- **§6 이력·투자 비교·상장일** — 이력 로컬 DB(설정 경로를 먼저 등록), 화면 테스트의 이력·저장·상장일·비교 설정 대역(`tests/setup.ts`),
  비교 경로 = 메뉴 경로의 짝(`test_comparison_identity*`), 저장한 비교, 비교 화면 상태(`runSeq`), 대상 수(설정은 더하기 한도·서버 끝 100·요청 3·구독 2 — `lib/concurrency`), 대상 이름(`targetName`),
  현재 가치 축(`valueLine` — `lineEnd`에 키를 더하지 않는다), 상장일(`first_trade_date`는 표시 전용)
- **§7 대시보드** — 조회 화면(Yahoo 관문 공유, ECOS를 부르지 않음, 결측 가드의 금지 글자), 주소 있는 지표 모달(기간 단추는
  `history.replaceState`), 뉴스(저장하지 않음·메모리 캐시·Yahoo 긴 응답 머리), 기준금리(칸은 DB만 읽음·결정일은 한국 날짜·
  같은 날 두 행·까닭은 결정 날 뉴스 포커스의 은행 낱말 + 금리 낱말)
