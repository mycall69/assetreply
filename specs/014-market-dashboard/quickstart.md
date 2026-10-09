# Quickstart: 014 대시보드 검증 안내

## 0. 준비

- 개발 DB에 새 테이블을 만든다: `cd backend && .venv/bin/alembic upgrade head`
  - 새 리비전 하나이고, `down_revision = "b3e7d5a1c924"`다
- 새 설정은 모두 기본값이 있다(data-model §8). `.env`는 고치지 않는다 — 임시 백엔드는 환경 변수로 덮는다
- **개발 서버를 띄운 채 통합 테스트를 돌리지 않는다**(`./stop.sh` → 테스트 → `./start.sh`)

## 1. 순수 계산 — 참조값 (네트워크·DB 없음)

```bash
cd backend && .venv/bin/python -m pytest -q tests/unit/test_market_session.py tests/unit/test_market_quote.py \
  tests/unit/test_market_gaps.py tests/unit/test_indicator_periods.py tests/unit/test_market_indicators.py \
  tests/unit/test_settings_market.py tests/unit/test_market_runner_plan.py tests/unit/test_market_quotes_service.py tests/unit/test_news_cache.py
```

**`market_session`**
- 한글날 KS11(출처 세션 10-08) → `holiday`
- 서머타임 전환 주 미국: 3월 둘째 일요일 뒤 월요일 한국 22:30에 `open`, 그 전 주 22:30은 `pre_open`
- 도쿄 11:45 → `break`
- `cme` 금 17:30 뉴욕 → `closed`, 일 18:30 → `open`이고 거래일은 월요일
- 갱신 없는 세션: cme 성탄절에 시작 30분 뒤 `pre_open`, 2시간 뒤 `holiday`(R14-7)

**`market_quote`**
- 휴장 카드: 차이 = 10-08 − 10-07이고 0%가 아니다
- 상해: `chartPreviousClose = 0.0002050505`여도 `fulldayChange`로 맞는 전일 값이 나온다
- 이력이 닿지 않으면 `from = "source"`다
- 엔 ×100은 정확하다(`8.449 → 844.900000`)
- 전일 −37.63(WTI)이면 `changeRate: null` + `non_positive_base`다

**`market_gaps`**
- 다우만 빈 평일 → `missing`, 넷 다 빈 평일 → 휴장
- 상해 국경절 9일 → 휴장, 15일 공백 → `missing`
- SOX 1994 전은 다우와 견주지 않는다

**`indicator_periods`**
- 주·월은 012 `period_table`과 같은 대표일이다(같은 입력의 대조)
- 년 = 12-31 이하 마지막 거래일
- `shifted` 📅, 끝나지 않은 기간 `ongoing`, 잠정 꼬리

## 2. 출처 계약 — 저장한 응답 본문 픽스처

```bash
cd backend && .venv/bin/python -m pytest -q tests/contract/test_yahoo_market_client.py tests/contract/test_yahoo_market_quotes.py tests/contract/test_yahoo_gate.py \
  tests/contract/test_news_naver.py tests/contract/test_news_yahoo_us.py tests/contract/test_news_yahoo_jp.py
```

픽스처는 실측 본문을 줄여 `tests/contract/fixtures/market/`·`fixtures/news/`에 둔다(R14-1·R14-13). README 표에 받은 날·주소 종류·내용을 적는다.

**Yahoo 차트·spark**
- 현지 날짜가 `zoneinfo` 기준이다 — 겨울 CL=F 자정 행이 하루 앞당겨지지 않는다
- 종가 `null` 행은 버린다. 오늘 봉은 확정으로 내지 않는다. `firstTradeDate`를 읽는다
- spark 15개를 읽는다. 빠진 심볼만 차트로 다시 부른다
- 429면 관문 전체가 쉰다

**뉴스**
- 칸마다 10개, 중복 제목은 한 번만 센다(네이버 MBN 두 건)
- 허용 도메인 밖 링크·`javascript:`·상대 주소는 그 줄을 버리거나 절대 주소로 바꾼다
- 광고 칸(Yahoo US `ad-container`)을 거른다
- 시각: kr KST → UTC, jp `"22:20"`·`"10/8"`, us 글자 그대로
- 유료 표시를 읽는다
- 구조가 바뀐 본문(목록 없음)은 `parse_empty`다
- 429 본문(UA 없음)은 `rate_limited`다

**`YahooStockClient`**
- 기존 계약 테스트가 **고치지 않고** 통과한다(`gate=None` 기본)

## 3. 저장·워커·API — 통합 (`assetreplay_test`)

```bash
./stop.sh && (cd backend && .venv/bin/python -m pytest -q tests/integration/test_market_worker.py tests/integration/test_market_repository.py tests/integration/test_dashboard_quotes_api.py \
  tests/integration/test_dashboard_series_api.py tests/integration/test_dashboard_news_api.py tests/integration/test_market_schema.py) ; ./start.sh
```

**워커**
- 처음 바퀴: 열두 지표의 최근 청크를 먼저 받고 `first_day`를 기록한다. 그다음 백필을 지표마다 돌아가며 받는다
- 중단 뒤 다시 돌리면 받은 곳부터 받는다. 받은 구간만 커버리지다
- 겹친 날 값이 바뀌면 `market_close_revision` 한 줄이 생기고 저장 값은 그대로다
- 하루 한 번만 원본이 쌓인다
- 오래 꺼졌다 켜지면 이어 받기를 2년 청크로 나눈다(R14-2)

**A1(현재 시세)**
- 15개를 한 번의 spark로 받는다
- 30초 안 두 요청에 출처 호출은 한 번이다(단일 비행)
- 한 심볼이 빠지면 그 카드만 실패다
- spark 실패면 마지막 성공 값에 `stale: true`다

**A2(그래프)**
- 백필 중이면 202 + 진행이다
- 완성되면 단위 넷의 점·`gaps`·`tailPending`이 나온다
- 오늘 잠정 꼬리가 붙는다
- 30,000점을 넘을 때만 줄인다
- 환율은 `fx_rate`의 값이다(외환 `/series`와 같은 날 같은 값 — SC-004)
- 없는 id는 404다
- 완성 뒤 실패가 있으면 200 + `history.lastFailure`, `lastSuccessAt`이 커버리지 행의 값이다(FR-019)

**A5(뉴스)**
- 세 칸이 따로 실패한다
- 10분 안 재요청은 출처를 부르지 않는다
- 실패 기억과 `retryAfterSeconds`가 맞다

**스키마**
- 금액 열이 `DECIMAL`이다(`test_금액_컬럼에_부동소수점이_없다`)
- PK가 `(indicator_id, trade_date)`다

## 4. 화면 (Vitest — `lightweight-charts` 모의, 종료 코드를 본다)

```bash
cd frontend && npm test -- --run && npx tsc --noEmit && npx eslint .
```

**대시보드**
- 날짜가 KST이고 요일이 붙는다. 자정 타이머로 바뀐다(가짜 시계)
- 카드 15개가 묶음·차례대로 보인다. 오름은 ▲ 빨강, 내림은 ▼ 파랑이다
- 다섯 상태와 ⏳·지연·출처 전일·시장 환율·선물 주석이 보인다
- 한 카드 실패에 나머지는 그대로다
- 보이지 않는 동안 부르지 않고, 다시 보이면 곧바로 부른다

**지표 화면**
- 머리 값이 같은 스토어다
- 단위 단추가 주소를 바꾼다. 새로고침하면 같은 단위다
- 받는 중이면 그래프 없음 → `completed`에 그래프다
- 없는 지표면 안내다
- 커서 상자에 📅·⏳가 보인다

**뉴스**
- 세 칸이 온 차례로 그려진다
- 링크는 `target="_blank" rel="noopener noreferrer"`다
- `parse_empty`는 "읽지 못함"이다
- 유료 표시가 보인다

**바뀌는 기존 테스트(R14-16)**
- 구현 뒤 실제로 실패한 목록을 만들어 "지금 단언 → 새 단언"으로 승인을 받는다
- 고친 줄에는 `// 014 승인 YYYY-MM-DD`를 단다

## 5. 실측 시나리오 (헤드리스 Chrome CDP — 013 방식, 실제 출처)

| # | 확인 | 기대 |
|---|------|------|
| 5-1 | `/` 열기 | `/dashboard`로 옮겨지고, 사이드바 "대시보드"만 선택된다. 다른 메뉴로 가면 그 메뉴만 선택된다 |
| 5-2 | 한국 시간 평일 오전(한국 장중) | KOSPI·KOSDAQ "장중 ⏳". 미국 "마감" 또는 "개장 전"이고, 미국 현지 날짜 기준 전일이다 |
| 5-3 | 한국 휴장일(가능하면) 또는 주말 | 휴장 카드의 차이가 마지막 거래일과 그 전 거래일의 차이다 — 0% 아님 |
| 5-4 | 카드 → 지표 화면 → 일·주·월·년 → 새로고침 → 뒤로 | 단위 유지, 대시보드 복귀. 커서 값이 출처의 같은 날 종가와 같다 |
| 5-5 | 처음 기동(빈 DB의 임시 백엔드) | 카드는 곧바로 보인다(`출처 전일` 표시). 지표 화면은 진행 → 완성 뒤 그래프다. 처음 백필 시간을 잰다 |
| 5-6 | 환율 카드·지표 화면 | 카드 = 시장 환율 + 주석, 그래프 = 외환 메뉴와 같은 날 같은 값(외환 `/series` 대조) |
| 5-7 | 뉴스 세 칸 | 10개씩(일본 ヘッドライン), 링크가 새 탭으로 열린다. 다시 열기 10분 안에 출처 호출이 없다(서버 로그) |
| 5-8 | 뉴스 출처 하나를 막기(임시 백엔드에서 `NEWS_US_URL`을 없는 주소로) | 미국 칸만 실패 + 다시 시도. 카드·다른 칸은 그대로 |
| 5-9 | 1440px·1024px 창 | 카드 줄바꿈, 뉴스 칸 쌓임, 가로 넘침 없음 |

## 6. 불변 (FR-026·SC-010)

- **메뉴 응답**: 013의 기준 스크립트(`013-baseline/fetch.py` + 대조)로 014 전후 다섯 메뉴·비교 응답을 견준다. 날짜가 바뀌는 부동산 외에는 차이가 0이어야 한다
- **주식 수집**: 주식 수집 통합 테스트가 고치지 않고 통과한다. 관문을 넘긴 클라이언트로 같은 스텁 응답이면 저장 행이 같다
- **외환**: 외환 `/latest`·`/series`가 014 전과 같다. 대시보드는 ECOS를 부르지 않는다(대시보드 경로를 부르는 동안 ECOS 요청 수 0 — 스텁 계수)

## 7. 성능 (SC-001·SC-002)

- 히스토리를 받아 둔 상태에서 `/dashboard`의 카드 15개가 보이기까지 2초 이내 — CDP의 탐색 시작 → 카드 15개 렌더
- `sp500`의 일 단위(약 2만 5천 점)가 그려지기까지 1초 이내, 단위 전환 1초 이내 — 응답 크기와 `setData` 시간을 함께 적는다

## 8. 실행 기록

### T041 — US1 실측(2026-10-10 00:23 KST, 토요일 — 헤드리스 Chrome CDP, 실제 Yahoo 출처, 수집 워커 전)

- **5-1**: `/` → `/dashboard`로 옮겨진다. 사이드바는 "대시보드"만 선택된 상태, 상단 바 제목 "대시보드". `/fx`로 가면 "외환"만 선택된다
- **날짜**: "2026년 10월 10일 (토)" + "한국 시간"
- **카드**: 15개, 묶음 다섯(한국·미국·일본·중국·환율·원자재·변동성) 차례
  - 화면의 값이 같은 순간 `/api/dashboard/quotes`의 값과 모두 같다(불일치 0)
- **5-2·5-3**: 장 상태가 시장마다 현지 시각 기준이다
  - KOSPI·KOSDAQ "휴장 · 10-08 종가"(한국 토요일). 차이 ▼177.97 −2.61%로 0%가 아니다
  - 니케이 "휴장 · 10-09 종가"(도쿄 토요일 00:23)
  - 항셍 "마감 ⏳ 확정 전 · 16:08 (한국 17:08)"(홍콩 금요일 밤 — 현지 날짜가 아직 지나지 않음)
  - 다우·나스닥·S&P·SOX "장중 ⏳ 잠정 · 11:23 (한국 00:23)"(뉴욕 금요일)
  - WTI·금 "약 9·10분 지연", VIX "약 15분 지연"(R14-9 실측과 같다)
- **전일**:
  - 수집 워커가 아직 없어 지수·선물은 "전일 값: 출처(이력에 아직 없음)"이다(R14-8 물러남)
  - 환율은 "전일: 런던 0시 기준(출처)" + "시장 환율 — 매매기준율과 다를 수 있음"이다
- **배치**: 1440px에서 카드 줄바꿈 정상(스크린샷 작업용 임시 폴더 `014_t041_dashboard.png`)
