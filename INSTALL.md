# 설치

AssetReplay를 내 컴퓨터에 설치하고 처음 띄우기까지의 순서다. 기능 소개·구조·개발 방식은 [README](README.md)에 있다.

```
준비물 → 설치 → 데이터베이스 → 설정(.env) → 스키마 적용 → 실행 → 첫 수집
```

---

## 1. 준비물

| 항목 | 버전 |
|------|------|
| Python | 3.14+ (`backend/pyproject.toml`의 `requires-python`) |
| Node.js | 20.9+ (`next` 요구 버전) |
| MySQL | 8.0+ (InnoDB, utf8mb4) |

출처마다 인증 정보가 따로다. **ECOS 인증키만 필수**이고, 나머지는 없으면 그 화면만 쓰지 못한다.

| 인증 정보 | 쓰는 화면 | 없으면 | 발급 |
|-----------|-----------|--------|------|
| 한국은행 ECOS 인증키 | 외환·예금 | 백엔드가 뜨지 않는다 | [ecos.bok.or.kr](https://ecos.bok.or.kr) |
| 키움증권 REST API 앱 키·시크릿 | 주식 — 국내·미국 종목 검색 | 검색 화면이 "인증 정보가 설정되지 않았습니다"와 할 일을 알린다. 일본 종목 검색과 시뮬레이션은 된다 | [openapi.kiwoom.com](https://openapi.kiwoom.com/) — 키움증권 계좌·HTS ID 연결·REST API 사용 등록 |
| 공공데이터포털 인증키 | 부동산 | 부동산 수집이 인증 실패로 멈춘다 | [data.go.kr](https://www.data.go.kr/) — 네 자료를 **각각 활용신청**(아래 4절) |

가상자산·대시보드(지표·뉴스)·부동산 단지 링크는 키가 필요 없다. 출처가 기본 사용자 에이전트를 막으므로 브라우저형 문자열을 쓰는데,
`.env.example`에 이미 들어 있다.

---

## 2. 설치

```bash
# 백엔드
cd backend
python3.14 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# 프론트엔드
cd ../frontend
npm install
```

Python은 **반드시 `backend/.venv/` 안에서** 돌린다(헌법 "Python 가상환경 [필수]"). `source activate`에 기대지 말고
`.venv/bin/python`을 직접 부른다. 가상환경이 없으면 `be-start.sh`가 만드는 명령을 알리고 멈춘다.

---

## 3. 데이터베이스

MySQL에 **개발 DB와 테스트 DB 둘**을 만들고 앱 사용자에게 권한을 준다. 관리자 계정의 `mysql` 클라이언트 안에서 한 번 실행한다.
비밀번호는 셸 인자로 넘기지 말고 클라이언트 안에서 입력한다.

```sql
CREATE DATABASE assetreplay      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE assetreplay_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'assetreplay'@'localhost' IDENTIFIED BY '비밀번호';
GRANT ALL PRIVILEGES ON assetreplay.*      TO 'assetreplay'@'localhost';
GRANT ALL PRIVILEGES ON assetreplay_test.* TO 'assetreplay'@'localhost';
FLUSH PRIVILEGES;
```

- **테스트 DB는 개발 DB 이름 + `_test`다**(`backend/tests/conftest.py`). 통합 테스트가 스키마를 드롭·재생성하므로 개발 DB와 반드시
  나눈다. 테스트가 시작할 때 테스트 DB가 없으면 만들려고 하는데, 앱 사용자에게 `CREATE DATABASE` 권한이 없는 것이 정상이라 그때는 위
  명령을 안내하고 멈춘다
- DB 이름을 바꾸면 `.env`의 `DB_NAME`과 테스트 DB 이름(`<DB_NAME>_test`)도 함께 바꾼다

---

## 4. 설정 (`.env`)

`.env.example`을 **저장소 루트**에 `.env`로 복사하고 값을 채운다. `.env`는 gitignore된다 — 커밋하지 않는다.

```bash
cp .env.example .env
```

### 필수

```
ECOS_API_KEY=발급받은_인증키
DB_HOST=localhost
DB_NAME=assetreplay
DB_USER=assetreplay
DB_PASSWORD=비밀번호
```

`DB_PORT`는 기본 3306이다. 예금(008)은 환율과 **같은 ECOS 인증키**를 쓴다 — 더 넣을 것이 없다.
**ECOS 인증키는 발급일부터 2년 유효하다**(ECOS 이용약관 제4조 ③). 만료되면 환율·예금 수집이 함께 인증 실패(`auth`)로 멈추므로
만료 전에 ECOS에서 연장한다.

### 주식 종목 검색 — 키움증권 (006)

```
KIWOOM_MODE=real
KIWOOM_APP_KEY=발급받은_앱_키
KIWOOM_APP_SECRET=발급받은_시크릿
```

키움은 **검색용 종목 목록에만** 쓴다(시세·배당·분할은 Yahoo). 실전(`real`)과 모의(`mock`)는 앱 키가 따로 발급된다 — 키와 모드가
어긋나면 인증 실패다. 미국 종목 목록에 해외주식 거래 신청이 따로 필요한지는 키움 문서에 없다.

### 부동산 — 공공데이터포털 (009)

```
DATA_API_KEY=공공데이터포털_인증키
APT_TRADE_PROBE_START=2005-01
```

포털에서 다음 네 자료를 **각각 활용신청**한다(같은 계정이면 키는 하나다). 등록되지 않은 자료는 HTTP 403(사유 30)으로 막히고 화면이
"인증키 설정과 활용신청을 확인하세요"를 보인다.

1. 국토교통부 아파트 매매 실거래가 **상세 자료**
2. 행정안전부 법정동코드
3. 국토교통부 공동주택 단지 목록
4. 공동주택 기본 정보

`DATA_API_KEY`는 일반 인증키(디코딩 키)다. 첫 거래 달을 찾을 탐색 시작 달 `APT_TRADE_PROBE_START`는 **코드에 기본값이 없다** —
`.env.example`에서 옮긴다(없으면 실거래 수집이 사유와 함께 멈춘다).

### 사용자 에이전트 — 가상자산·뉴스·부동산 단지 링크

`INVESTING_USER_AGENT`(가상자산 007)·`NEWS_USER_AGENT`(대시보드 뉴스 014)·`NAVER_LAND_USER_AGENT`(단지 링크 010)는 `.env.example`의 값을
그대로 둔다. 줄이 없으면 코드의 기본값을 쓰지만, **값을 비워 두면 출처가 막는다**(차단 경로를 재현하는 수단이다).

### 그 밖

나머지 항목은 모두 기본값이 있으며 `.env.example`에 주석으로 설명한다. **`.env`를 고치면 백엔드를 다시 띄운다** — 기동할 때 읽고,
인증 실패 막힘도 재시작에서 풀린다.

---

## 5. 스키마 적용

```bash
cd backend && .venv/bin/python -m alembic upgrade head
```

스키마는 Alembic 리비전(`backend/src/db/migrations/versions/`)으로만 관리한다. 수동 DDL은 쓰지 않는다.

---

## 6. 실행

```bash
./start.sh     # 백엔드 8080 → 프론트엔드 3030 차례로
./stop.sh
```

- 개별 제어는 `be-start.sh` · `be-stop.sh` · `fe-start.sh` · `fe-stop.sh`다. 스크립트는 이미 돌고 있는 프로세스를 먼저 내리고 다시 띄운다
- `start.sh`는 백엔드가 `/health`에 응답한 뒤에만 프론트엔드를 띄운다. 백엔드가 실패하면 프론트엔드는 띄우지 않는다
- 포트는 `BE_PORT`·`FE_PORT` 환경변수로 바꾼다. 브라우저는 프론트엔드 포트만 쓴다 — `/api/*`는 Next.js가 백엔드로 넘긴다
  (`frontend/next.config.ts`)
- **백엔드는 단일 워커로 뜬다**(`be-start.sh`의 `--workers 1`). 수집 워커가 앱 프로세스 안에서 돌기 때문에 여럿 띄우면 수집이 겹친다

브라우저에서 <http://localhost:3030>을 연다(대시보드로 옮겨 간다).

| 화면 | 주소 |
|------|------|
| 대시보드 | <http://localhost:3030/dashboard> |
| 외환 | <http://localhost:3030/fx> |
| 가상자산 | <http://localhost:3030/crypto> |
| 주식 | <http://localhost:3030/stocks> |
| 예금 | <http://localhost:3030/deposit> |
| 부동산 | <http://localhost:3030/realestate> |
| 투자 비교 | <http://localhost:3030/compare> |
| 설정 | <http://localhost:3030/settings> |

로그는 `logs/backend.log`(웹서버 표준출력)·`logs/frontend.log`(Next.js)·`logs/collection.log`(수집·출처 호출의 구조화 로그)에 남는다.

---

## 7. 첫 수집

새 DB에는 데이터가 없다. 자산군마다 받기 시작하는 때가 다르다.

| 자산군 | 받기 시작하는 때 |
|--------|------------------|
| 대시보드 지표 | 백엔드가 뜨면 스스로 받는다. 카드는 곧바로 보이고, 지표 모달의 그래프는 그 지표의 과거 일봉을 받은 뒤 보인다(처음 기동에 지표 12개를 다 받는 데 약 8분) |
| 외환 | 상단 바 우측의 **`⟳ 수집 현황`** 에서 통화를 골라 시작한다 |
| 주식·가상자산·예금 | 화면에서 처음 실행하면 그 대상의 자료를 받기 시작하고 진행을 보인다. 끝나면 결과가 채워진다. 해외 종목을 원화로 보면 그 통화의 환율도 함께 받는다 |
| 부동산 | 시·군·구를 처음 고를 때 그 시·군·구의 실거래를 받기 시작한다(단지 이름은 곧바로 보인다) |
| 대시보드 기준금리 | 백엔드가 뜨면 스스로 받는다 — 다섯 중앙은행의 결정 이력(약 11번 호출, 1분 안). 받는 동안 칸이 은행마다 "받는 중…"이다 |
| 검색용 목록 | 키움 종목 목록은 그날 처음 검색할 때(한국 시간), 코인 목록은 처음 검색할 때(그 뒤 7일마다) 받는다 |

수집은 서버에서 돌기 때문에 **화면을 떠나거나 브라우저를 닫아도 계속 진행된다.**

> **호출 한도 주의**
> - **ECOS**는 일일 호출 한도가 있다. 실측 하한은 150회이고 통화 하나의 전체 백필이 약 146회다. **하루에 전체 백필은 한 통화만** 하는
>   것이 안전하다. 수집 화면 상단의 "오늘 호출" 수로 확인한다(참고 지표이며 한도 판정은 출처 응답으로 한다)
> - **공공데이터포털**: 처음 고르는 시·군·구는 첫 거래 달부터 전체 이력(약 260~280회)을 받는다 — 하루 30곳 남짓이다. 한도에 닿으면
>   받은 달까지 남기고 다음 날 이어 받는다

---

## 8. 설치 확인

```bash
./stop.sh                                               # 서버를 먼저 내린다
(cd backend && .venv/bin/python -m pytest -q --cov=src)  # 백엔드
(cd frontend && npm test)                                # 프론트엔드
./start.sh
```

전체 테스트는 **네트워크 없이 통과한다**(외부 API는 저장된 응답 픽스처로 검증한다). **개발 서버를 띄운 채 백엔드 테스트를 돌리지
않는다** — 테스트가 같은 MySQL의 스키마를 드롭·재생성하므로, 그 사이 서버가 조회하면 `Unknown column` 오류가 난다.
타입·린트 검사는 [README의 개발](README.md#개발)에 있다.

---

## 업데이트할 때

```bash
git pull
cd backend && .venv/bin/pip install -e '.[dev]' && .venv/bin/python -m alembic upgrade head
cd ../frontend && npm install
cd .. && ./start.sh
```

새 기능이 테이블·열을 더하면 기존 설치도 `alembic upgrade head`로 올려야 한다. 올리지 않으면 새 테이블을 읽는 칸이 오류를 보인다 —
예를 들어 012(시뮬레이션 이력 `simulation_history`·`history_setting`)를 빠뜨리면 이력 칸이 "이력을 불러오지 못했습니다"(시뮬레이션은
된다), 013(저장한 비교 `saved_comparison`)을 빠뜨리면 투자 비교의 저장한 비교 칸이 "저장한 비교를 받지 못했습니다"(비교 실행은 된다)다.
014는 대시보드 지표 테이블들과 주식 첫 거래일 열(`stock.first_trade_date`), 기준금리 테이블 셋(`policy_rate_decision`·`policy_rate_raw`·`policy_rate_bank`)을 더한다 —
올리지 않으면 대시보드의 기준금리 칸이 "기준금리를 불러오지 못했습니다"다. 014 반복 2026-10-13은 투자 비교 설정 테이블(`comparison_setting`)을
더한다 — 올리지 않으면 설정 화면의 "투자 비교" 절이 오류를 보이고, 투자 비교 화면은 "투자 비교 설정을 읽지 못해 기본 20개로 제한합니다"다(비교 실행은 된다).

---

## 문제 해결

| 증상 | 할 일 |
|------|-------|
| `be-start.sh`가 "가상환경을 찾을 수 없습니다" | 2절의 백엔드 설치를 한다 |
| `be-start.sh`가 "저장소 루트에 .env가 없습니다" | 4절대로 `.env`를 만든다 |
| `be-start.sh`가 "30초 안에 /health가 응답하지 않았습니다" | 함께 보이는 `logs/backend.log` 마지막 줄을 본다 — `ECOS_API_KEY`가 비었거나 DB에 접속하지 못한 경우가 많다 |
| 테스트가 "테스트 DB … 를 만들 수 없습니다" | 3절의 테스트 DB를 관리자 계정으로 만든다 |
| 테스트하는 동안 서버가 `Unknown column` 오류 | 개발 서버를 띄운 채 테스트를 돌렸다 — `./stop.sh` → 테스트 → `./start.sh` |
| 이력·저장한 비교 칸이 "불러오지 못했습니다" | 5절의 스키마 적용을 다시 한다 |
| 환율·예금 수집이 인증 실패(`auth`) | ECOS 인증키가 만료됐거나 틀렸다 — 고친 뒤 백엔드를 다시 띄운다 |
| 주식 검색이 "인증 정보가 설정되지 않았습니다" | 키움 앱 키·시크릿을 넣고 백엔드를 다시 띄운다. `KIWOOM_MODE`가 키와 맞는지도 본다 |
| 부동산이 "인증키 설정과 활용신청을 확인하세요" | `DATA_API_KEY`와 네 자료의 활용신청을 확인한다 |
| 대시보드 뉴스 칸이 "차단" | 기다려도 풀리지 않는다 — `NEWS_USER_AGENT`를 지금 브라우저의 사용자 에이전트로 고치고 백엔드를 다시 띄운다 |
| 기준금리 칸이 "출처가 막음"·"최근 갱신 실패" | 같은 네이버 출처라 `NEWS_USER_AGENT`를 고치고 백엔드를 다시 띄운다. 칸의 [다시 시도]는 수집을 곧바로 다시 돌린다 |
