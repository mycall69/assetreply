# AssetReplay

다중 자산군의 히스토리 데이터를 축적하고, 과거 시점의 투자 성과를 재현·비교한다.

"그때 샀더라면 지금 얼마일까"에 답하려면 **그때의 값을 그대로 갖고 있어야 한다.**
이 프로젝트는 그 데이터를 쌓는 일부터 시작한다.

---

## 현재 상태

**외환(FX)**과 **주식/ETF** 자산군이 동작한다.

| 기능 | 자산군 | 내용 |
|------|--------|------|
| 001 | 외환 | 환율 축적·조회·시각화. 한국은행 ECOS 어댑터, 구간 분할 수집, 커버리지 기반 재개 |
| 002 | 외환 | 분석 화면 통합과 전역 내비게이션. 확정/잠정 구분, 오늘 환율 새로고침, 스프레드 설정 |
| 003 | 외환 | 수집 실행 계층과 실시간 관측. 서버 주도 백그라운드 수집, 시간축 시각화, 기록 적재 |
| 004 | 외환 | 일자별 표의 스크롤 탐색과 기간 단위 전환. 일·주·월 기준일, 옮겨진 기준일 표시 |
| 005 | 주식/ETF | 배당 재투자 시뮬레이션. 일별 시세·배당·분할 수집, 성과 표·차트, 원금 통화 환산, 이력 비교 |

자산군 확장 순서는 고정되어 있다 — **외환 → 가상자산 → 주식/ETF → 예금 → 부동산.**
한 번에 하나씩, 수집부터 화면까지 동작하는 수직 슬라이스로 완결한다.

**005는 이 순서를 한 칸 건너뛰었다.** 사용자가 쓰던 Google Apps Script 시뮬레이터를
대체하는 것이 먼저 필요했기 때문이며, 사용자 승인을 받은 결정이다. 건너뛴
**가상자산은 006으로 남아 있다** (`specs/005-stock-investment-simulation/plan.md`의
Complexity Tracking에 근거와 함께 기록).

부동산이 마지막인 이유는 지역·단지·면적 축의 비정기 거래 데이터라, 나머지 넷의 균일한
일별 시계열과 형태가 근본적으로 다르기 때문이다.

---

## 시작하기

### 준비물

| 항목 | 버전 |
|------|------|
| Python | 3.14+ |
| Node.js | 20.9+ (`next` 요구 버전) |
| MySQL | 8.0+ (InnoDB, utf8mb4) |
| 한국은행 ECOS 인증키 | [ecos.bok.or.kr](https://ecos.bok.or.kr)에서 발급 |

### 설치

```bash
# 백엔드
cd backend
python3.14 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# 프론트엔드
cd ../frontend
npm install
```

### 설정

`.env.example`을 **저장소 루트**에 `.env`로 복사하고 값을 채운다.

```bash
cp .env.example .env
```

최소한 다음 다섯 개가 필요하다.

```
ECOS_API_KEY=발급받은_인증키
DB_HOST=localhost
DB_NAME=assetreplay
DB_USER=사용자명
DB_PASSWORD=비밀번호
```

`.env`는 gitignore된다. 나머지 항목은 기본값이 있으며 `.env.example`에 주석으로 설명한다.

### 스키마 적용

```bash
cd backend && .venv/bin/python -m alembic upgrade head
```

스키마는 Alembic 리비전으로만 관리한다. 수동 DDL은 쓰지 않는다.

### 실행

```bash
./start.sh     # 백엔드 8080 + 프론트엔드 3030
./stop.sh
```

개별 제어는 `be-start.sh` · `be-stop.sh` · `fe-start.sh` · `fe-stop.sh`를 쓴다.
스크립트는 이미 돌고 있는 프로세스를 먼저 종료한 뒤 재시작한다.

브라우저에서 <http://localhost:3030/fx>를 연다.

### 첫 수집

데이터가 없으면 화면이 비어 있다. 상단 바 우측의 **`⟳ 수집 현황`** 을 눌러 수집 화면으로
가서 통화를 고르고 시작한다.

수집은 서버에서 돌기 때문에 **화면을 떠나거나 브라우저를 닫아도 계속 진행된다.**
돌아오면 그동안 진행된 만큼 시간축이 채워져 있다.

> **호출 한도 주의**
> ECOS는 일일 호출 한도가 있다. 실측 하한은 150회이고 통화 하나의 전체 백필이 약 146회다.
> **하루에 전체 백필은 한 통화만** 하는 것이 안전하다. 화면 상단의 "오늘 호출" 수로
> 확인할 수 있다(참고 지표이며 한도 판정은 출처 응답으로 한다).

---

## 구조

```
backend/src/
├── ingestion/      외부 데이터 소스 어댑터. 벤더 응답 타입이 이 계층 밖으로 새지 않는다
├── repository/     저장·조회. DB 방언 문법은 db/dialect.py 뒤에 격리
├── simulation/     순수 함수 계산. DB·HTTP에 의존하지 않는다
├── worker/         수집 실행 수명 — 언제 무엇을 돌릴지
├── observability/  관측 기록 — 무슨 일이 있었는지 어떻게 남길지
└── api/            REST·SSE 엔드포인트

frontend/src/
├── app/            Next.js App Router
├── components/     화면 구성 요소
├── stores/         Zustand 상태
└── lib/            API 클라이언트, 타입, 스트림 구독
```

`worker`와 `observability`를 나눈 이유는 관심사가 다르기 때문이다. 한 모듈에 넣으면 수집
수명 로직과 기록 포맷이 엉킨다.

### 로그

| 파일 | 내용 |
|------|------|
| `logs/backend.log` | 웹서버 표준출력 |
| `logs/collection.log` | 수집 전용 구조화 로그 (한 줄 JSON) |

섞지 않는다. 접근 로그와 뒤엉키면 운영자가 걸러내야 한다.

---

## 개발

```bash
# 백엔드
cd backend
.venv/bin/python -m pytest -q --cov=src   # 테스트 + 커버리지
.venv/bin/python -m mypy src              # 타입 (strict)
.venv/bin/python -m ruff check src tests  # 린트

# 프론트엔드
cd frontend
npm test && npx tsc --noEmit && npx eslint .
```

전체 테스트는 **네트워크 없이 통과한다.** 외부 API는 저장된 응답 픽스처로 검증하며,
테스트가 실제 API를 호출하면 규약 위반이다.

> **개발 서버를 띄운 채 통합 테스트를 돌리지 말 것.**
> 테스트가 같은 MySQL의 스키마를 드롭·재생성하므로, 그 사이 서버가 조회하면
> `Unknown column` 오류가 난다.

> **백엔드는 단일 워커로 띄운다.**
> 수집 워커가 애플리케이션 프로세스 안에서 돌기 때문에, 워커를 여럿 띄우면 프로세스마다
> 수집 태스크가 생긴다. DB 점유가 중복 실행은 막지만 확인 호출이 한도를 낭비한다.
> `be-start.sh`가 이미 `--workers 1`을 지정한다.

### 품질 게이트

머지 전 다음을 모두 통과해야 한다.

- 전체 테스트 통과, 커버리지 80% 이상
- mypy strict 및 TypeScript 타입 체크
- 린트·포맷
- 신규 데이터 소스 추가 시 해당 소스의 계약 테스트
- 요구사항 변경 시 `plan.md` 추적성과 `tasks.md` 참조 갱신

---

## 개발 방식

이 저장소는 **Spec-Driven Development**([Spec Kit](https://github.com/github/spec-kit))로
개발한다. 코드를 쓰기 전에 명세를 쓰고, 명세에서 설계와 태스크를 유도한다.

```
specify → clarify → plan → tasks → analyze → implement
```

기능별 산출물은 `specs/NNN-<이름>/`에 있다. 각 기능의 **왜**는 거기에 적혀 있다 — 무엇을
만들었는지가 아니라 왜 그렇게 만들었고 무엇을 하지 않기로 했는지가 남는다.

`.specify/memory/constitution.md`가 최상위 규칙이다. 설계·구현·리뷰가 모두 여기에
종속되며, 충돌하는 관행은 무효다. 주요 원칙은 다음과 같다.

| 원칙 | 요지 |
|------|------|
| 비동기 우선 | 요청 경로에 동기 I/O 금지 |
| 데이터 소스 격리 | 벤더 응답이 도메인 계층에 노출되지 않는다 |
| 테스트 주도 | 테스트 → 실패 확인 → 구현. 커버리지 80% |
| 데이터 정합성 | 결측을 임의 보간하지 않는다. 확정값의 재현성을 보장한다 |
| 금융 계산 정확성 | 금액·비율은 `Decimal`, DB는 `DECIMAL`. `float` 금지 |

문서·주석·커밋 메시지는 한국어로 쓴다. 기술 용어와 코드 심볼은 원어를 유지한다.

---

## 기술 스택

| 영역 | 스택 |
|------|------|
| 백엔드 | Python 3.14, FastAPI, aiohttp, SQLAlchemy 2.x (async), Alembic, aiomysql |
| 프론트엔드 | Next.js 16, React 19, Zustand, Lightweight Charts, Tailwind CSS |
| 데이터베이스 | MySQL 8.0+ |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library |
| 타입·린트 | mypy (strict), ruff / TypeScript (strict), ESLint |

MySQL을 쓰지만 **교체 가능성을 전제로 설계한다.** DB 종속 문법은 방언 추상화 뒤에 격리해,
5개 자산군의 30년치가 쌓인 뒤 교체 비용이 폭발하지 않게 한다.

---

## 데이터 출처

| 자산군 | 출처 |
|--------|------|
| 외환 | [한국은행 ECOS](https://ecos.bok.or.kr/) (통계코드 731Y001) |
| 주식/ETF | Yahoo Finance chart (일봉·배당·분할) — **비공식 엔드포인트** |

원본 응답과 정규화된 시계열을 분리 저장한다. 출처가 값을 정정했을 때 갱신 전 값을 추적할
근거가 되기 때문이다.

**주식 출처는 잠정이다.** Yahoo는 2017년에 공식 API를 닫았고 지금 쓰는 경로는 문서화되지
않은 내부 엔드포인트다. 참조 구현(사용자의 Apps Script)이 쓰던 것을 그대로 이어받았으며,
**개인 이용이라는 전제에 기댄 사용자 승인 결정**이다. 도구를 공개하거나 여러 사용자에게
제공할 계획이 생기면 그 전제가 깨지므로 출처를 다시 정해야 한다. 어댑터를 교체할 때 손댈
지점은 `backend/src/ingestion/yahoo/` 한 곳이며, 정적 검사가 그 경계를 지킨다
(`tests/unit/test_layer_boundaries.py`).
