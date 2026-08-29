# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 원칙 VIII에 따라 이 저장소의 모든 문서·주석·커밋 메시지는 한국어로 작성한다.
> 기술 용어, 라이브러리명, API 식별자, 코드 심볼은 원어를 유지한다.

## 현재 상태

**애플리케이션 소스 코드가 아직 존재하지 않는다.** 저장소에는 Spec-Kit 스캐폴딩(`.specify/`)과
Claude Code 설정(`.claude/`), 그리고 제정된 헌법만 있다. `pyproject.toml`, `package.json`,
테스트 러너, 마이그레이션 도구는 모두 미생성 상태이며, `git init`도 아직 수행되지 않았다.

따라서 첫 작업은 코드 수정이 아니라 `/speckit-specify`로 첫 기능 명세를 만드는 것이다.

## 헌법이 최우선

`.specify/memory/constitution.md`가 이 프로젝트의 최상위 규칙이다(v1.0.1, 원칙 9개).
모든 설계·구현·리뷰는 여기에 종속되며, `/speckit-plan`의 `Constitution Check` 게이트가
이 파일을 런타임에 읽어 판정 기준으로 삼는다. 작업 전 반드시 통독할 것.

아래는 위반 빈도가 높아 특히 주의할 규칙들이다. 전체 규칙은 헌법 원문을 참조한다.

- **금융 계산에 `float` 금지** (원칙 VI) — 금액·수익률·환율은 코드에서 `Decimal`,
  DB 컬럼은 `DECIMAL`. `FLOAT`/`DOUBLE` 사용은 곧바로 위반이다.
- **동기 I/O 금지** (원칙 I) — 요청 처리 경로에서 `requests`, 동기 DB 드라이버,
  `time.sleep` 사용 불가. 불가피하면 `run_in_executor`로 격리.
- **테스트 우선** (원칙 III, NON-NEGOTIABLE) — 구현보다 테스트를 먼저 커밋하고
  최초 실행에서 실패함을 확인한 뒤 구현한다. 커버리지 80% 미만은 머지 차단.
- **결측치 임의 보간 금지** (원칙 V) — 휴장일·결측치는 명시적으로 표현한다.
  전일 값 자동 복사는 위반이다.
- **한국어 문서화** (원칙 VIII).

## Spec-Kit SDD 워크플로

이 저장소는 Spec-Kit 1.0.1(`integration: claude`, `feature_numbering: sequential`)로
초기화되어 있다. 기능 개발은 슬래시 커맨드로 진행한다.

```
/speckit-specify  → /speckit-clarify → /speckit-plan → /speckit-tasks → /speckit-implement
```

보조 커맨드: `/speckit-analyze`(산출물 간 일관성 검사), `/speckit-checklist`,
`/speckit-converge`(코드베이스와 명세의 격차를 tasks.md에 추가), `/speckit-taskstoissues`.

기능별 산출물은 `specs/NNN-<short-name>/`에 생성된다.

| 파일 | 생성 커맨드 | 역할 |
|------|-------------|------|
| `spec.md` | specify | 요구사항 명세 |
| `plan.md` | plan | 설계 및 Constitution Check |
| `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | plan | 설계 부속 산출물 |
| `tasks.md` | tasks | 의존성 순서가 매겨진 실행 태스크 |

**현재 작업 중인 기능의 위치는 git 브랜치가 아니라 `.specify/feature.json`으로 결정된다.**
(이 파일은 `.specify/.gitignore`에 의해 머신 로컬 상태로 취급된다.)
우선순위는 `SPECIFY_FEATURE_DIRECTORY` 환경변수 → `SPECIFY_FEATURE` → `feature.json` 순이며,
`create-new-feature.sh`가 자동으로 기록한다. 스크립트가 "Feature directory not found"로
실패하면 먼저 이 상태부터 확인할 것.

스크립트는 `.specify/scripts/bash/`에 있다 (`create-new-feature.sh`, `setup-plan.sh`,
`setup-tasks.sh`, `check-prerequisites.sh`, `resolve-template.sh`). 템플릿은
`.specify/templates/`에 있으며, 직접 수정하지 말고 커맨드를 통해 사용한다.

## 목표 아키텍처

### 계층 (원칙 IV — 위반 시 원칙 II·III이 함께 무력화됨)

```
수집(ingestion) → 저장(repository) → 도메인 계산(simulation) → API → UI
```

- **ingestion**: 외부 데이터 소스별 어댑터. 벤더(kiwoom-rest-api, 공공데이터포털,
  거래소 API, 한국은행 ECOS)의 응답 타입이 이 계층 밖으로 새어나가면 안 된다.
  rate limit·인증·재시도 정책은 코드가 아닌 설정으로 선언한다.
- **simulation**: DB·HTTP에 의존하지 않는 **순수 함수**. DB나 HTTP 없이 단독 테스트가
  불가능한 계산 코드는 원칙 IV 위반이다.
- 상위 계층은 하위 계층의 구체 구현이 아닌 `Protocol`에 의존한다.

### 시계열 스키마 불변식 (원칙 V)

모든 자산군의 테이블 설계에 공통으로 적용된다.

- `(자산 식별자, 날짜)` 복합 유니크 키 + upsert → 수집의 멱등성·재개 가능성 확보
- 모든 레코드에 `source`, `ingested_at` 기록
- 원본(raw) 응답과 정규화(normalized) 시계열을 **분리 저장**
- 주가는 수정주가와 원주가를 **구분 저장** (액면분할·병합·유상증자 명시 반영)
- 시각은 UTC 저장, 표시 시점에 거래소 현지 시간대(KST/EST/JST)로 변환
- 가상자산 일봉 기준 시각은 UTC 00:00

### 자산군 확장 순서 (원칙 IX — 고정)

```
FX → 가상자산 → 주식/ETF/지수 → 예금 → 부동산
```

한 번에 하나씩, **조회 API와 UI까지 동작하는 수직 슬라이스로 완결**한다.
여러 자산군의 수집 계층만 먼저 만들고 UI를 미루는 것은 위반이다.
부동산이 마지막인 이유는 지역/단지/면적 축의 비정기 거래 데이터라 나머지 4개의
균일한 일별 시계열과 형태가 근본적으로 다르기 때문이다.

## 명령어

**아직 빌드/테스트 도구가 스캐폴딩되지 않았다.** 아래는 헌법이 규정한 스택과 실행 규약이며,
도구를 도입할 때 이 형태를 따른다. 실제 커맨드가 확정되면 이 절을 갱신할 것.

- **Python 실행은 반드시 `.venv/` 내에서** (헌법 "Python 가상환경 [필수]").
  `source activate`에 의존하지 말고 인터프리터를 직접 호출한다:
  `.venv/bin/python`(Mac/Linux), `.venv\Scripts\python`(Windows).
- 백엔드: Python 3.11+, FastAPI, aiohttp / 테스트 `pytest` + `pytest-asyncio` /
  타입 `mypy` (strict 통과 필수) / 패키지 관리 uv 또는 poetry
- 프론트엔드: Next.js 16+, React 19+, Zustand, Lightweight Charts, Tailwind CSS /
  테스트 Vitest + React Testing Library / TypeScript 5.0+ (`strict: true`, `any` 금지) /
  패키지 관리 pnpm 또는 npm
- DB: MySQL 8.0+ (InnoDB, utf8mb4) + aiomysql. 스키마 변경은 마이그레이션 스크립트로만
  관리하며 수동 DDL은 금지.

**품질 게이트** — 머지 전 전부 통과해야 한다: 전체 테스트 통과 + 커버리지 80% 이상,
mypy strict 및 TypeScript 타입 체크, 린트·포맷, 신규 데이터 소스 추가 시 계약 테스트 포함.

전체 테스트 스위트는 **네트워크 없이 통과**해야 한다(원칙 III). 외부 API는 저장된 응답
픽스처로 계약 테스트를 수행하며, 테스트가 실제 API를 호출하면 위반이다.
