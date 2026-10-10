# Implementation Plan: 대시보드 — 오늘의 시장 지표 15개와 과거 추이, 세 나라의 경제 뉴스

**Branch**: `014-market-dashboard` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/014-market-dashboard/spec.md`

## Summary

사이드바 "대시보드"가 새 화면 `/dashboard`를 연다(최상위 `/`도 그리로 간다). 맨 위에 오늘 날짜(한국 시간)가 있고, 지표 15개 카드(현재 값·전일 대비·기준 시각·장 상태)가 다섯 묶음으로 보인다. 아래에는 한국·미국·일본의 주요 경제 뉴스가 10개씩 보인다. 카드를 누르면 지표 화면 `/dashboard/{id}?unit=`에서 일·주·월·년 단위의 과거 추이를 본다.

- **US1 (P1) 카드**
  - 현재 시세는 Yahoo `/v7/finance/spark` **한 번**으로 15개를 받고, 서버가 30초 캐시·단일 비행으로 묶는다(R14-6)
  - 장 상태(개장 전·장중·점심 휴장·마감·휴장)는 시장마다 정해 둔 거래 시간표와 출처의 세션 날짜로 순수 모듈이 판정한다(R14-7)
  - 전일 종가는 **저장된 이력**에서 읽는다. 이력이 닿지 않으면 출처 값으로 물러나고 그 사실을 밝힌다(R14-8)
  - 환율 카드는 시장 환율(명확화 2)이다
  - 화면은 보이는 동안 60초마다 다시 부른다(R14-15)
- **US2 (P2) 지표 화면과 이력**
  - 환율을 뺀 12개 지표의 일별 확정 종가를 새 테이블에 출처 최대 기간(S&P 500은 1927년부터)으로 저장한다 — 원본·커버리지·개정을 따로 둔다
  - `lifespan`의 아홉째 태스크 `market_worker_loop`가 백그라운드로 백필(새것부터 2년 청크)·하루 한 번 이어 받기를 한다(R14-2·R14-4·R14-11)
  - 그래프는 일·주·월·년 대표값(012 규칙 + 년)이고, 결측은 같은 시장 묶음·14일 규칙으로 끊는다(R14-5·R14-12) — **반복 2026-10-10b에 기간 8개(점 묶기 없음)로 대체**(아래)
  - 환율 그래프는 외환의 ECOS 이력이다
- **US3 (P3) 뉴스**
  - 세 어댑터를 둔다(R14-13): 네이버 증권 내부 API의 주요뉴스, Yahoo Finance Latest News HTML, Yahoo!ファイナンス 뉴스 ヘッドライン의 내장 JSON
  - 메모리 캐시 10분, 실패 백오프, 칸마다 따로 된 경로다. 저장하지 않는다
- **같은 출처를 함께 지킨다**: 주식과 대시보드의 Yahoo 요청은 관문(`YahooGate`) 하나를 지난다 — 동시 요청 수와 429 때 함께 물러섬(R14-10)
- **반복 2026-10-10b — 지표 모달**(spec Iterations, T095~T127)
  - 지표 화면을 대시보드 위의 **주소 있는 모달**로 바꾼다(`/dashboard/{id}?range=` — Next 16 가로채기·병렬 경로, R14-20)
  - 차트는 **보는 기간 8개**다(점 묶기 없음). 일·주는 장중 시세(Yahoo 차트의 장중 질의 — 저장 안 함, R14-19), 월 이상은 저장된 일봉 전부다
  - 모달 머리에 **변화 까닭** — 지표마다 정한 시황 기사 목록에서 마지막 세션 이후 기사 1~3개를 출처 글자 그대로(R14-17)
  - 차트 아래 **일자별 표**(시가·고가·저가·종가·대비·등락률 — 일·주·월, 012 `period_table` 규칙, R14-21). `market_indicator_daily`에 시가·고가·저가 열을 더하고
    저장해 둔 원본 응답에서 되살린다(R14-18 — 다시 받지 않는다)
- **반복 2026-10-10c — 앞 구간 스크롤·장중 실선·블랙 배경**(spec Iterations, T128~T141)
  - 기간은 **처음 보이는 범위**다. 일봉 기간은 저장된 일봉 전부를 한 번 받고(`windows` — 기간마다 시작일) 처음 범위만 점 차례로 놓는다 — 왼쪽으로 끌면 첫 날까지, 월~모두 전환은
    다시 받지 않는다(R14-22). 장중은 일 = 최근 5세션 5분·주 = 최근 1개월 30분을 받고 `window`(마지막 세션·최근 5세션)로 처음 범위를 놓는다. 장중 선은 진한 실선이다
  - **블랙 배경**(FR-030) — 상단 바 오른쪽 끝의 단추(스크롤해도 위에 붙음), 전 화면·차트 다섯 종, 브라우저에 기억, 깜빡임 없음. Tailwind v4 색 변수를 `.dark` 아래에서 다시
    정의해 컴포넌트 클래스를 바꾸지 않는다(밝은 화면·014 전 테스트 불변 — R14-23). 차트는 `lib/chartTheme` 팔레트로 테마가 바뀌면 다시 만든다
- **반복 2026-10-10d — 외환 일자별 표의 등락폭·등락율**(spec Iterations, T142~T150 — FR-026 예외)
  - 외환 메뉴의 일자별 표(일·주·월) 오른쪽 끝에 등락폭·등락율 두 열 — **바로 아래 행 대비**(일 = 직전 고시일, 주·월 = 직전 대표값). 서버가 `/api/fx/daily` 행마다 `change`를
    `Decimal`로 싣고 화면은 형식만 입힌다(원칙 VI). 쪽의 마지막 행은 `daily_page`가 `hasMore` 판정에 이미 더 읽는 한 건과 견준다(추가 질의 없음 — R14-24)
  - 계산은 `/api/fx/latest`의 `_change`를 순수 모듈 `simulation/fx_change.py`로 옮겨 함께 쓴다(같은 반올림 — `/latest` 응답 불변). CSV는 두 열을 맨 끝(004의 진행 중 뒤)에 붙인다

**설계 중 확인한 것**

| 확인 | 결과 | 설계에 준 영향 |
|------|------|----------------|
| `range=max`는 일봉을 주지 않는다 | 1mo·3mo로 낮춘다(실측) | `period1/period2` 2년 청크, 새것부터(R14-2) |
| 출처 `gmtoffset`은 응답 시점의 오프셋 하나다 | 겨울 백필에서 CL=F 4,227행·FX 3,505행이 하루 앞당겨진다(실측) | `zoneinfo` + `exchangeTimezoneName`(R14-3). 주식 파서는 고치지 않는다(시각이 09:00·09:30이라 날짜 불변) |
| 출처가 시장 상태·지연 필드를 주지 않는다 | 세션 날짜는 거래소 달력을 반영하고, 세션 시각은 틀린다(KS11 15:00, 선물·외환 00:00–23:59) | 시장별 시간표 + 세션 날짜로 판정(R14-7). 상태 둘(개장 전·점심 휴장)을 spec FR-004·FR-006에 더했다(같은 작업 단위) |
| 상해 `chartPreviousClose`가 깨져 있다 | `0.0002050505` | 전일 종가를 이력에서 읽고, 물러날 때는 `fulldayChange`를 먼저 쓴다(R14-8). spec FR-005에 반영 |
| 지연은 시각 차이로만 알 수 있다 | WTI·금 약 10분, VIX 약 15분 | 값의 시각과 받은 시각의 차이로 판정(R14-9). spec FR-007에 반영 |
| 출처가 휴장일 달력을 주지 않는다 | 값 없는 행은 휴일 자리 표시다 | 같은 시장 묶음·14일 규칙으로 결측을 가른다(R14-5). spec FR-014에 반영 |
| 2,000점으로 줄이면 일 단위가 뜻을 잃는다 | S&P 일 단위 약 2만 5천 점 | 단위 전체를 보내고 3만 점을 넘을 때만 줄인다(R14-12 — Complexity Tracking). spec FR-012에 반영 |
| 네이버 뉴스 화면은 브라우저에서만 그린다 | HTML에 목록이 없다 | 화면이 부르는 내부 API(`MAINNEWS`)를 쓴다 — 원칙 II 이탈(사용자 승인) |
| Yahoo US에는 주요 목록이 없다 | Latest News 스트림뿐, 시각은 상대 표기 | 명확화 3의 물러남(최신 목록), 시각은 글자 그대로(spec FR-020·FR-021에 반영) |
| Yahoo JP `/news` 홈은 분야별 5개씩이다 | 편집 헤드라인은 `/news/headline`(20개) | 그 목록의 위 10개, 칸 링크는 `/news`(spec FR-020에 반영). 유료 기사 표시(FR-021) |
| 사이드바 선택이 경로 앞부분 일치다 | `href: "/"`면 늘 선택 | 대시보드는 `/dashboard`, 최상위는 옮긴다(R14-14). spec FR-001에 반영 |
| 주식 Yahoo 클라이언트가 세마포어를 인스턴스마다 가진다 | 검색 경로는 요청마다 새 인스턴스 | `YahooGate`를 선택 인자로 넘긴다(기본 `None` = 지금 그대로)(R14-10) |
| `zoneinfo`의 Windows 지원 | `tzdata` 패키지가 필요하다(009가 이미 `zoneinfo`를 쓴다) | 의존성 `tzdata`를 더한다(크로스 플랫폼 — 맥·리눅스는 시스템 시간대가 먼저다) |

## Technical Context

| 항목 | 값 |
|------|----|
| 언어(백엔드) | Python 3.14 (`.venv/bin/python`) |
| 프레임워크 | FastAPI, aiohttp, SQLAlchemy 2.x async + aiomysql, Alembic |
| 새 의존성 | `tzdata`(백엔드 — Windows `zoneinfo`). HTML·JSON 파싱은 표준 라이브러리(`html.parser`·`json`) — 새 파서 패키지 없음 |
| 언어(프론트엔드) | TypeScript 5 (`strict`), Next.js 16(App Router — `params`·`searchParams`는 Promise), React 19 |
| 상태 관리 | Zustand — `marketQuotesStore`·`indicatorSeriesStore`·`newsStore`. 반복 2026-10-10b: `indicatorTableStore`·`indicatorCommentaryStore`, 모달 열림은 주소다. 반복 2026-10-10c: `themeStore`(브라우저 저장소 — data-model §9), 그래프 스토어가 일봉 본문 한 벌을 지표마다 든다 |
| 화면 경로(반복 2026-10-10b) | 모달 — `app/dashboard/@modal/(.)[indicator]`(대시보드 안 이동 = 가로채기), `app/dashboard/[indicator]`(새로고침·직접 입력 = 대시보드 + 모달) — R14-20 |
| 차트 | Lightweight Charts — 새 `IndicatorChart`(`LineSeries`, 결측 구간마다 선 나눔, 잠정 꼬리 연한 색, 처음 범위 `setVisibleLogicalRange`). 반복 2026-10-10b: 처음 범위 없음(`fitContent`) — 기간 8개가 범위다, 막대 간격 하한 0.01px(기본 0.5px면 "모두"가 끝 2천 점만 보인다 — T123), 장중은 잠정 선·시간 축은 시장 현지 시각. 반복 2026-10-10c: 처음 범위 `setVisibleLogicalRange`(창 시작 차례 ~ 마지막 — 기존 차트 모의에 있는 API), 기간 전환은 다시 받지 않고 범위만, 장중 진한 실선, 테마가 바뀌면 다시 만든다(`applyOptions`를 쓰지 않는다) |
| 스타일(반복 2026-10-10c) | Tailwind v4 — 색 변수(`--color-*`)를 `.dark` 아래에서 재정의(회색 뒤집기·강조 색 어두운 바탕용), `@custom-variant dark (&:where(.dark, .dark *))`, `<html class="dark">`를 `app/layout.tsx`의 인라인 스크립트가 그리기 전에 단다 — R14-23 |
| DB | MySQL 8 — 새 테이블 넷(`market_indicator_daily`·`_raw`·`_coverage`·`market_close_revision`), Alembic 리비전 하나(`down_revision = "b3e7d5a1c924"`). 반복 2026-10-10b: `market_indicator_daily`에 `open_price`·`high_price`·`low_price` 열(Alembic 리비전 하나 — R14-18) |
| 출처 | Yahoo 차트·spark(지표 — 005 이탈의 확장), ECOS(환율 이력 — 001의 데이터 그대로), 네이버 증권 내부 API·Yahoo Finance HTML·Yahoo!ファイナンス 내장 JSON(뉴스). 반복 2026-10-10b: 변화 까닭의 시황 기사(R14-17), 장중 시세(Yahoo 차트 `interval=5m·30m` — R14-19) — 둘 다 저장 안 함 |
| 테스트 | pytest + pytest-asyncio(통합은 `assetreplay_test`, 계약은 저장 본문 픽스처 — 네트워크 없음), Vitest + RTL(`lightweight-charts` 모의, 종료 코드 확인) |
| 타입·린트 | mypy strict, ruff `--no-cache`, `tsc --noEmit`, eslint |
| 계산 | 서버 `Decimal`(차이·등락률·엔 ×100). 화면은 형식만(문자열) |
| 성능 목표 | 카드 15개 2초(SC-001), 모달 그래프 1초·기간 전환 1초(SC-002 — S&P "모두" 약 2만 5천 점, 반복 2026-10-10c: 일봉 전부를 받고 1년이 보이는 그래프 1초, 월~모두 전환은 요청 없이 0.3초), 표 첫 쪽·단위 전환 1초(SC-012) |
| 제약 | 다섯 메뉴·비교의 응답·이력·수집 불변(FR-026). 백엔드 단일 워커. 대시보드는 ECOS를 부르지 않는다 |
| 규모 | 일별 행 약 12만 5천(12개 지표), 처음 백필 약 250청크(약 7분), 뉴스 칸마다 10분에 많아야 한 번, 현재 시세 30초에 많아야 한 번 |

## Constitution Check

*GATE: Phase 0 전에 통과해야 한다. Phase 1 설계 뒤 다시 확인한다.*

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 출처 요청은 aiohttp, DB는 비동기 세션이다. 뉴스 파싱(`html.parser` — 약 1MB 한 장)은 요청 경로의 CPU 작업이지만 10분 캐시 뒤 한 번이다. 측정해 50ms를 넘으면 `run_in_executor`로 옮긴다(태스크에 측정 단계) |
| II. 데이터 소스 격리 | ⚠ 이탈 넷(사용자 승인 2026-10-09 — Complexity Tracking) + 반복 2026-10-10b 새 경로 둘(시황 기사·장중 시세 — **T095에서 실측 뒤 재승인**). 반복 2026-10-10c는 장중 받는 범위만 넓힌다(같은 엔드포인트 `range=5d·5m`·`1mo·30m` — 승인 그대로, 새 출처 없음, T128 실측) | 어댑터 격리: 출처 응답 형태는 `ingestion/yahoo/market*.py`·`ingestion/news/*` 밖으로 나가지 않는다. 심볼 대응은 `market_symbols.py` 한 곳이다. 한도·재시도·UA·주소는 설정이다(data-model §8). Yahoo 관문으로 주식과 한도를 함께 지킨다(R14-10). 출처를 화면·README에 밝힌다 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트를 먼저 커밋 → 최초 실패 확인 → 구현. 구현 뒤 실패하면 멈추고 보고한다. 먼저 쓸 테스트는 quickstart 1~4다. 출처 다섯 갈래(차트·spark·뉴스 셋)는 저장 본문 픽스처 계약 테스트다 — 네트워크 없음. 바뀌는 기존 테스트는 R14-16 목록이고 구현 뒤 실제 실패 목록으로 승인을 받는다. 반복 2026-10-10d: 새 테스트 넷을 먼저. 014 전 외환 테스트는 단언 하나가 바뀔 것으로 본다 — `frontend/tests/csv.test.ts`의 "진행 중 여부가 열로 남는다"(줄 끝 `/예$/` → 진행 중 열의 차례). 나머지는 키 부분집합·CSV 머리 이어짐·선택 칸이라 그대로다. 실제 실패 목록으로 T144 승인 |
| IV. 모듈화 | ✅ | 순수 함수: `simulation/market_indicators.py`·`market_session.py`·`market_quote.py`·`market_gaps.py`·`indicator_periods.py`(DB·HTTP 없음). 서비스는 Protocol에 기댄다: `MarketQuoteSource`(spark), `MarketHistoryRepository`(이력 읽기), `NewsSource`(칸마다 어댑터). 경로가 구체 구현을 주입한다(013 `SavedComparisonRepository` 관례). 반복 2026-10-10d: 외환 등락 계산은 순수 모듈 `simulation/fx_change.py`(경로 둘이 함께 부른다) |
| V. 정합성·재현성 | ✅ | (지표, 현지 거래일) PK. 새 날만 넣고, 바뀐 확정 값은 덮어쓰지 않고 개정 표에 남긴다. `source`·`ingested_at`, 원본 분리, UTC 저장. 오늘 봉·장중 값은 잠정이고 저장하지 않는다. 휴장·결측을 메우지 않는다(R14-5). 받은 구간만 커버리지다. 발견한 첫 날을 기록한다(날짜 하드코딩 없음). 거래소 현지 날짜는 `zoneinfo`다. 해석 둘을 Complexity Tracking에 기록한다: 거래소 달력 대신 출처 거래일·묶음 판정, 잠정 값은 보이기만 하고 확정 추적은 청크 원본·개정 표. 수집 상태는 그래프 경로(`history.lastSuccessAt`·`lastFailure`)로 조회한다(FR-019). 반복 2026-10-10b: 시가·고가·저가는 종가와 같은 불변식(새 날만·덮지 않음)이고 이미 저장한 날은 원본에서 되살린다(R14-18). 장중 시세는 저장하지 않는다. 반복 2026-10-10c: 장중 세션은 점이 있는 날뿐이다(빈 세션을 꾸미지 않는다) |
| VI. 금융 정확성 | ✅ | `DECIMAL(20,6)` 열, 출처 숫자는 `Decimal(str(…))`(기존 파서 관례). 차이·등락률·엔 ×100은 서버 `Decimal`이다. 화면은 계산하지 않는다(013 `compareNoClientFinance`와 같은 검사를 새 파일에). 반복 2026-10-10d: 외환 표의 등락폭·등락율도 서버 `Decimal`이다 — `DailyTable.tsx`·`csv.ts`는 이미 `noClientSideFinance`의 대상이라 화면은 문자열에 형식만 입힌다 |
| VII. 반응형 UI | ✅(해석 기록) | Zustand 스토어 셋. 백필 진행은 SSE(2초 폴링)다. 차트는 Lightweight Charts다. 점은 3만 점 한도 + LTTB이고, 그 이하는 라이브러리의 보이는 범위 그리기에 맡긴다(Complexity Tracking). 반복 2026-10-10b: 기간 8개는 그 기간의 일봉 전부(한도 넘을 때만 LTTB), 장중은 잠정 선, 표는 쪽 넘기기(012와 같음). 반복 2026-10-10c: 일봉은 한 번 받고 기간은 처음 범위만(전환에 요청 없음), 테마는 Zustand 스토어 + CSS 변수, 차트 다섯 종은 테마로 다시 그린다 |
| VIII. 한국어 문서화 | ✅ | 문서·주석·커밋 한국어, 식별자 원어. 반복 2026-10-10c: 테마 단추 이름·상태 한국어("블랙 배경") |
| IX. MVP 점진 | ✅ | 새 자산군이 아니다. 지수는 자산군 4의 "지수 시계열"이고, 환율은 자산군 1의 데이터이며, 원자재·VIX는 조회 지표다(시뮬레이션 없음). US1이 API·화면까지의 수직 조각이다. 범위 밖: 봉 그래프·거래량·장중 분 그래프·지표 편집·뉴스 저장·번역. 반복 2026-10-10d는 자산군 1(외환) 화면의 개선이다 — 새 자산군이 아니다 |
| DB 운영 규약 | ✅ | Alembic 리비전 하나. ORM만 쓴다 — "새 날만 삽입"은 ORM 조회 + 삽입이라 방언 문법이 없다. 커버리지 갱신은 `db/dialect.upsert`(격리된 유일한 곳). 열거형 비원생, 시각 UTC, 금액 `DECIMAL` |
| 크로스 플랫폼 | ✅ | `zoneinfo` + `tzdata`(Windows). 경로 `pathlib`. 새 플랫폼 의존 없음 |
| 명세 작성 규약 | ✅ | 설계 중 바뀐 요구를 spec에 같은 작업 단위로 반영했다: FR-001(주소), FR-004·FR-006(다섯 상태·판정), FR-005(이력의 전일·물러남·런던 0시), FR-007(확정 전·지연 판정), FR-012(점 한도), FR-014(결측 판정), FR-020(출처마다의 목록), FR-021(상대 표기·날짜만·유료), US1 시나리오 6·13, Edge Cases. 반복 2026-10-10(체크리스트 `checklists/sources.md`)에 FR-005·FR-009·FR-016·FR-018~FR-024·SC-001·SC-007을 보강하고 SC-011을 더했다(T087~T094). 모든 FR·SC는 아래 추적성 표의 설계·태스크에 연결된다 |

### 설계 후 재평가

| 항목 | 판정 | 근거 |
|------|------|------|
| 메뉴·수집 불변(FR-026·SC-010) | ✅ | 주식 클라이언트의 더함은 기본값 `None`인 선택 인자 `gate`뿐이다(값·청크·차례 불변). 외환은 읽기와 지금 수집 경로뿐이다. 다른 경로 응답은 키도 바뀌지 않는다 — quickstart 6이 014 전후를 견준다 |
| 일어나지 않음 | ✅ | 휴장 카드 0%·백필 중단 구간의 커버리지·0건 뉴스의 "뉴스 없음"·주소에 단위 안 남김이 각각 참조값·통합·계약·화면 테스트에서 깨진다(quickstart 1~4) |
| 다른 곳에서 일어남 | ✅ | 한국 날짜로 미국 "어제"를 잡으면 `market_quote` 참조값이 깨진다. 고정 오프셋 날짜는 겨울 CL=F 픽스처가 깨뜨린다. 카드·그래프 전일 불일치는 통합 대조(SC-003)로, 시장 환율이 고시 이력에 섞이면 스키마·통합(SC-004)으로 잡힌다. 탭 여럿 → 출처 한 번은 단일 비행 테스트, 허용 도메인 밖 링크는 계약 테스트가 잡는다 |
| 늦게 일어남 | ✅ | 보이지 않는 탭은 부르지 않는다(가짜 visibility). 자정 날짜는 가짜 시계로 본다. 하루 이어 받기를 놓치면 출처 전일 + 표시다. 백필 완료는 SSE `completed`로 그래프가 된다. 실패 기억은 백오프 상한 10분이다 |
| 공유 부품 변경 | ✅ | `PerformanceChart`·`FxChart`는 고치지 않는다(새 `IndicatorChart`). `period_table`은 부르기만 한다. `lib/format.ts`는 고치지 않는다(필요하면 새 함수를 더함만) |
| 반복 2026-10-10b | ✅ 승인됨 | 원칙 II 새 경로 둘 — T095 실측 뒤 사용자 재승인 2026-10-10. 014가 만든 테스트(`IndicatorPage`·`IndicatorChart`·`indicatorSeriesStore`·`indicatorSeriesFixtures`·`dashboardNoClientFinance`·`test_indicator_periods`·`test_dashboard_series_api`)는 구현 뒤 실제 실패 목록으로 사용자 승인 2026-10-10(T111). 014 전 테스트는 바뀌지 않았다 |
| 바뀌는 기존 테스트 | ⚠ 승인 필요 | R14-16: `Sidebar.test.tsx`·`noUnbuiltAssetRoutes.test.ts`, (필요하면) `TopBarTitle.test.ts`. 구현 뒤 실제 실패 목록으로 승인을 받는다 |
| 반복 2026-10-10c | ⚠ 승인 필요 | 014가 만든 테스트(`test_dashboard_range_api`·`test_dashboard_series_api`·`test_yahoo_market_intraday`·`IndicatorChartRange`·`IndicatorChart`·`indicatorSeriesStore`)는 구현 뒤 실제 실패 목록으로 승인받는다(T132). 014 전 테스트는 바꾸지 않는다 — 다크 테마는 색 변수 재정의라 클래스가 그대로이고, 차트는 기존 모의에 있는 API만 쓴다. 밝은 테마 화면은 T128 기준선 스크린샷과 견준다(T139) |
| 공유 부품 변경(반복 2026-10-10c) | ✅(해석 기록) | 차트 다섯 종(`FxChart`·`PerformanceChart`·`ComparisonChart`·`CompareReturnChart`·`IndicatorChart`)이 테마 팔레트를 받는다 — 밝은 테마의 선택 값은 지금과 같다(색·글자). `applyOptions`·라이브러리 열거형을 실행 중에 쓰지 않는다 |
| 반복 2026-10-10d — 외환 화면 예외(FR-026) | ✅(예외 기록) | 외환 일자별 표와 CSV의 오른쪽 끝 두 열만 바뀐다. `/api/fx/daily`는 행에 `change`가 더해질 뿐 다른 칸·차례·쪽 넘기기·202가 같고, `/api/fx/latest`는 같은 함수를 부르지만 대상 고르기·응답이 같다(`014-baseline` 대조 — T148). CSV 열은 맨 끝이라 001·004 머리 단언(앞 열의 이어짐)이 그대로다. 014 전 테스트는 `frontend/tests/csv.test.ts`의 "진행 중 여부가 열로 남는다"(줄 끝 `/예$/` → 진행 중 열의 차례) 하나가 바뀔 것으로 본다(T144 승인) |

## Project Structure

### Documentation (this feature)

```text
specs/014-market-dashboard/
├── spec.md
├── plan.md                  # 이 파일
├── research.md              # R14-1 ~ R14-16
├── data-model.md            # 테이블 넷 · 지표 목록 · 거래 시간 · 카드 · 그래프 점 · 뉴스 · 화면 상태 · 설정
├── quickstart.md            # 검증 안내 · 실행 기록
├── contracts/
│   ├── rest-api.md          # A1 시세 · A2 그래프 · A3 다시 시도 · A4 진행 SSE · A5 뉴스 · A6 불변
│   └── ui-wireframes.md     # D1 ~ D6
├── checklists/
│   └── requirements.md
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                         (변경 — tzdata)
├── src/
│   ├── api/
│   │   ├── main.py                        (변경 — 관문·대시보드 클라이언트·뉴스 클라이언트, 아홉째 태스크, 주식 클라이언트에 관문, 라우터 셋을 뒤에)
│   │   ├── routes/
│   │   │   ├── dashboard_quotes.py        (신규 — A1)
│   │   │   ├── dashboard_series.py        (신규 — A2·A3·A4)
│   │   │   ├── dashboard_news.py          (신규 — A5)
│   │   │   └── stock_search.py            (변경 — 요청마다 클라이언트에 관문)
│   │   └── services/
│   │       ├── market_quotes.py           (신규 — spark 캐시·단일 비행·마지막 성공 값·이력 전일, `MarketQuoteSource` Protocol)
│   │       ├── indicator_series.py        (신규 — 이력·외환 이력 읽기, 단위·결측·잠정 꼬리·한도, `MarketHistoryRepository` Protocol)
│   │       └── news_cache.py              (신규 — 칸마다 캐시·실패 백오프·단일 비행, `NewsSource` Protocol)
│   ├── config/settings.py                 (변경 — data-model §8)
│   ├── db/
│   │   ├── models.py                      (변경 — 테이블 넷)
│   │   └── migrations/versions/<rev>_대시보드_지표.py  (신규)
│   ├── repository/market_daily.py         (신규 — 새 날만 삽입·개정·원본·커버리지·이력 읽기·전일)
│   ├── ingestion/
│   │   ├── yahoo/
│   │   │   ├── gate.py                    (신규 — YahooGate, R14-10)
│   │   │   ├── market.py                  (신규 — YahooMarketClient: 일봉 청크·spark·빠진 심볼 차트)
│   │   │   ├── market_parse.py            (신규, 순수 — zoneinfo 날짜·null 행·오늘 봉·firstTradeDate·spark meta)
│   │   │   ├── market_symbols.py          (신규 — 지표 id ↔ 심볼·배수, 유일한 대응)
│   │   │   └── client.py                  (변경 — 선택 인자 gate, 기본 None)
│   │   └── news/
│   │       ├── client.py · errors.py · types.py   (신규 — 공통 세션·UA·재시도, NewsItem·NewsList)
│   │       ├── naver.py · yahoo_us.py · yahoo_jp.py (신규 — 어댑터 + 순수 파서, R14-13)
│   ├── simulation/
│   │   ├── market_indicators.py           (신규, 순수 — 고정 15개, data-model §2)
│   │   ├── market_session.py              (신규, 순수 — 시간표·거래일·다섯 상태, R14-7)
│   │   ├── market_quote.py                (신규, 순수 — 카드 값·전일·차이·등락률·지연, R14-8·R14-9)
│   │   ├── market_gaps.py                 (신규, 순수 — 휴장·결측, R14-5)
│   │   └── indicator_periods.py           (신규, 순수 — 일·주·월·년 대표값, R14-12)
│   └── worker/
│       ├── market_worker.py               (신규 — 주기 루프 + 깨우기 이벤트)
│       └── market_runner.py               (신규 — 지표마다 할 일·청크 실행·커버리지)
└── tests/
    ├── unit/        test_market_indicators.py · test_market_session.py · test_market_quote.py · test_market_gaps.py · test_indicator_periods.py ·
    │                test_news_cache.py · test_market_quotes_service.py · test_settings_market.py · test_market_runner_plan.py
    ├── contract/    test_yahoo_market_client.py · test_yahoo_market_quotes.py · test_yahoo_gate.py · test_news_naver.py · test_news_yahoo_us.py · test_news_yahoo_jp.py
    │                fixtures/market/ · fixtures/news/ (README 표 포함)
    └── integration/ test_market_worker.py · test_market_repository.py · test_dashboard_quotes_api.py · test_dashboard_series_api.py · test_dashboard_news_api.py ·
                     test_market_schema.py

frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                       (변경 — redirect("/dashboard"), 안내 자리 삭제)
│   │   └── dashboard/
│   │       ├── page.tsx                   (신규 — D1)
│   │       └── [indicator]/page.tsx       (신규 — 서버 컴포넌트가 params·searchParams를 풀어 넘김, D3·D4)
│   ├── stores/  marketQuotesStore.ts · indicatorSeriesStore.ts · newsStore.ts   (신규 — data-model §7)
│   ├── lib/
│   │   ├── dashboardApi.ts                (신규 — A1·A2·A3·A5)
│   │   ├── dashboardProgressStream.ts     (신규 — A4 구독)
│   │   ├── kstClock.ts                    (신규 — 한국 날짜·요일·다음 자정까지, R14-15)
│   │   └── types.ts                       (변경 — 대시보드 응답 타입)
│   └── components/
│       ├── dashboard/                     (신규 — TodayHeader · IndicatorGroups · IndicatorCard · QuoteStateLine · NewsSection · NewsColumn ·
│       │                                   IndicatorView · IndicatorHeader · UnitPicker · IndicatorChart · SeriesCollecting)
│       └── shell/Sidebar.tsx · TopBar.tsx (변경 — /dashboard)
└── tests/
    └── DashboardPage.test.tsx · IndicatorCard.test.tsx · TodayHeader.test.tsx · marketQuotesStore.test.ts · IndicatorPage.test.tsx ·
        IndicatorChart.test.tsx · indicatorSeriesStore.test.ts · NewsSection.test.tsx · newsStore.test.ts · kstClock.test.ts ·
        dashboardNoClientFinance.test.ts · RootRedirect.test.tsx · DashboardPageNews.test.tsx   (신규)
        Sidebar.test.tsx · noUnbuiltAssetRoutes.test.ts · (TopBarTitle.test.ts)   (변경 — 승인 필요, R14-16)
```

**반복 2026-10-10b에 더하거나 바꾸는 파일**:

```text
backend/src/
├── db/migrations/versions/<rev>_대시보드_시가.py     (신규 — open_price·high_price·low_price)
├── db/models.py · repository/market_daily.py          (변경 — 열 셋, 새 날만, 원본에서 되살리기)
├── ingestion/yahoo/market.py · market_parse.py        (변경 — 일봉 OHLC, fetch_intraday)
├── ingestion/news/commentary.py (+ 출처별 파서)       (신규 — 시황 기사, R14-17. Yahoo 스트림 카드 파서 재사용 검토)
├── simulation/indicator_table.py                      (신규, 순수 — 표 행·주·월 OHLC 묶기, R14-21)
├── simulation/indicator_periods.py                    (변경 — 년 지움, D7)
├── api/services/indicator_series.py                   (변경 — range, 일봉 자르기·장중 갈래)
├── api/services/indicator_intraday.py · indicator_table.py · indicator_commentary.py  (신규)
├── api/routes/dashboard_series.py                     (변경 — range)
└── api/routes/dashboard_table.py · dashboard_commentary.py  (신규 — A7·A8)
frontend/src/
├── app/dashboard/layout.tsx · @modal/default.tsx · @modal/(.)[indicator]/page.tsx   (신규 — 모달 슬롯, R14-20)
├── app/dashboard/[indicator]/page.tsx                 (변경 — 대시보드 + 모달)
├── components/dashboard/IndicatorModal.tsx · RangePicker.tsx · IndicatorTable.tsx · IndicatorCommentary.tsx  (신규)
├── components/dashboard/IndicatorChart.tsx · IndicatorView.tsx · IndicatorHeader.tsx  (변경 — 기간·장중·모달 안)
├── components/dashboard/UnitPicker.tsx                (삭제 — RangePicker로)
├── stores/indicatorTableStore.ts · indicatorCommentaryStore.ts  (신규), stores/indicatorSeriesStore.ts (변경 — range)
└── lib/types.ts · dashboardApi.ts                     (변경 — range·표·까닭)
backend/tests/
├── contract/   test_yahoo_market_client.py(OHLC) · test_yahoo_market_intraday.py · test_news_commentary.py · fixtures/market/ · fixtures/news/commentary/
├── unit/       test_indicator_table.py · test_indicator_range.py · test_indicator_commentary_select.py · test_indicator_intraday_cache.py
└── integration/ test_market_schema.py · test_market_repository.py · test_market_ohlc_restore.py · test_dashboard_series_api.py(range) ·
                 test_dashboard_table_api.py · test_dashboard_commentary_api.py
frontend/tests/ IndicatorModal.test.tsx · RangePicker.test.tsx · IndicatorChart.test.tsx · IndicatorTable.test.tsx · indicatorTableStore.test.ts ·
                IndicatorCommentary.test.tsx   (014 테스트 변경은 T111 승인 — IndicatorPage·IndicatorChart·indicatorSeriesStore)
```

**반복 2026-10-10c에 더하거나 바꾸는 파일**:

```text
backend/src/
├── ingestion/yahoo/market.py                          (변경 — 장중 대응 일 5d·5m, 주 1mo·30m)
├── simulation/intraday_window.py                      (신규, 순수 — 마지막 세션·최근 5세션 창, R14-22)
├── api/services/indicator_intraday.py                 (변경 — window)
└── api/services/indicator_series.py                   (변경 — 일봉 기간 = 일봉 전부 + windows)
frontend/src/
├── app/layout.tsx · app/globals.css                   (변경 — 깜빡임 방지 스크립트, .dark 팔레트·@custom-variant)
├── components/shell/TopBar.tsx                        (변경 — 오른쪽 끝 테마 단추, 스크롤해도 위)
├── components/shell/ThemeToggle.tsx · stores/themeStore.ts · lib/chartTheme.ts   (신규)
├── components/FxChart.tsx · stock/PerformanceChart.tsx · stock/ComparisonChart.tsx · compare/CompareReturnChart.tsx  (변경 — 테마 팔레트)
├── components/dashboard/IndicatorChart.tsx            (변경 — 처음 범위·장중 실선·테마)
├── stores/indicatorSeriesStore.ts                     (변경 — 일봉 본문 한 벌, 월~모두는 범위만)
└── lib/types.ts · lib/dashboardApi.ts                 (변경 — windows·window)
backend/tests/   contract/test_yahoo_market_intraday.py(새 범위 · fixtures/market/intraday_*_5d_5m·_1mo_30m) · unit/test_intraday_window.py ·
                 integration/test_dashboard_range_api.py
frontend/tests/  IndicatorChartWindow.test.tsx · themeStore.test.ts · ThemeToggle.test.tsx · themeScript.test.ts · chartTheme.test.tsx ·
                 darkPaletteGuard.test.ts · indicatorSeriesStore.test.ts   (014 테스트 변경은 T132 승인)
```

**반복 2026-10-10d에 더하거나 바꾸는 파일**:

```text
backend/src/
├── simulation/fx_change.py                            (신규, 순수 — 등락폭·등락율·방향, `/latest`의 `_change`를 옮김, R14-24)
├── api/routes/latest.py                               (변경 — 그 함수를 부름, 응답 불변)
├── api/services/daily_query.py                        (변경 — 쪽 너머 한 건을 쪽 마지막 행의 비교 대상으로)
└── api/routes/daily.py                                (변경 — 행의 `change`, A9)
frontend/src/
├── lib/types.ts                                       (변경 — `DailyChange`, `PeriodRow.change?`)
├── components/fx/DailyTable.tsx                       (변경 — 오른쪽 끝 두 열, D10)
└── lib/csv.ts                                         (변경 — 맨 끝 두 열)
backend/tests/   unit/test_fx_change.py · integration/test_fx_daily_change.py
frontend/tests/  DailyTableChange.test.tsx · csvChange.test.ts   (014 전 `csv.test.ts` 단언 하나 — T144 승인)
```

**Structure Decision**:
- 기존 웹 앱 구조(backend/frontend)를 그대로 쓴다
- 대시보드는 새 자산군이 아니라 조회 화면이다. 그래서 백엔드는 다음을 더한다:
  - 지표 이력 저장 한 벌(표·저장소·워커)
  - 현재 시세·뉴스의 메모리 캐시 서비스
  - 순수 계산 모듈 다섯
- 화면은 새 경로 둘(대시보드·지표 화면)과 새 스토어 셋이다. 기존 차트·형식 함수는 고치지 않는다

## 요구사항 추적성

범례: R = research.md, DM = data-model.md §, A = contracts/rest-api.md §, D = contracts/ui-wireframes.md §, Q = quickstart.md §. 각 줄 끝의 `tasks`는 tasks.md "요구사항 ↔ 태스크" 표와 같다 — 모든 FR·SC가 태스크에 참조된다(명세 작성 규약).

| 요구사항 | 설계 |
|----------|------|
| FR-001 (사이드바·최상위 → /dashboard, 선택·제목) | R14-14·R14-16, D6, Q4·Q5-1, tasks T018·T028·T029·T040·T041 |
| FR-002 (오늘 날짜 KST·자정) | R14-15, D1, Q4, tasks T024·T025·T037·T039 |
| FR-003 (고정 15개·묶음·단위) | R14-1, DM2, A1, D1, tasks T006·T012·T013·T023·T028·T035·T036·T083 |
| FR-004 (카드 칸·색·서버 문자열) | R14-8, DM4, A1, D1·D2, Q1·Q4, tasks T020·T023·T026·T030·T032·T036·T039 |
| FR-005 (현지 날짜의 직전 거래일·휴장·이력 전일·물러남·환율 예외) | R14-7·R14-8, DM3·DM4, A1, D2, Q1·Q3, tasks T010·T016·T020·T023·T026·T032·T034·T039·T041·T087 |
| FR-006 (다섯 상태·시간표·서머타임) | R14-7, DM3, D2, Q1, tasks T007·T011·T019·T026·T031·T039·T041 |
| FR-007 (잠정·확정 전·지연) | R14-4·R14-7·R14-9, DM3·DM4, D2, Q1, tasks T019·T020·T026·T031·T032·T039 |
| FR-008 (주기 갱신·보이는 동안·단일 비행) | R14-6·R14-15, DM7, A1, Q3·Q4, tasks T007·T011·T022·T025·T027·T028·T034·T038·T039·T061 |
| FR-009 (카드마다 실패·마지막 성공 값) | R14-6, A1(`stale`·`failure`), D2, Q3·Q4, tasks T005·T021·T022·T023·T026·T027·T028·T033·T034·T035·T038·T039·T087·T089·T092 |
| FR-010 (지표 모달·주소·닫기·포커스·없는 지표 — 반복 2026-10-10b) | R14-14, DM7, A2, D3·D4, Q4·Q5-4, tasks T047·T048·T050·T057·T058·T059·T060·T061·T062·T096·T106·T110·T111·T122·T123 |
| FR-011 (보는 기간 8개·처음 1년 — 반복 2026-10-10b, 처음 보이는 범위·앞 구간 스크롤 — 반복 2026-10-10c) | R14-12·R14-22, DM5, A2, D3, Q1·Q4·Q5-16·Q5-17, tasks T044·T048·T049·T050·T053·T059·T060·T061·T104·T105·T107·T115·T120·T121·T123·T124·T128·T129·T130·T132·T133·T134·T137·T138 |
| FR-012 (종가 선·커서·잠정 꼬리·점 한도, 장중 진한 실선 — 반복 2026-10-10c) | R14-12·R14-22, DM5, A2, D3, Q3·Q7·Q5-17, tasks T044·T047·T049·T053·T056·T060·T082·T104·T105·T107·T115·T121·T124·T129·T130·T132·T133·T134·T137 |
| FR-013 (표의 주·월 대표일 규칙·📅·⏳) | R14-12, DM5, A2, D3, Q1, tasks T044·T049·T053·T060·T104·T108·T114·T117 |
| FR-014 (휴장·결측 판정) | R14-5, DM5, A2(`gaps`), D3, Q1·Q3, tasks T043·T047·T049·T052·T056·T060·T104·T105·T108·T114·T115 |
| FR-015 (선물 근월물 주석) | R14-1, DM2, A1·A2(`notes`), D2·D3, tasks T006·T012·T026·T039·T050·T060 |
| FR-016 (받는 중·진행·실패·다시 시도) | R14-11, DM1.3, A2(202)·A3·A4, D4, Q3·Q4·Q5-5, tasks T046·T047·T048·T050·T056·T057·T058·T059·T060·T062·T087·T088·T090·T091·T093·T105·T106·T108·T117·T120 |
| FR-017 (12개 일별 이력·최대 기간·불변식) | R14-1·R14-2·R14-3, DM1, Q2·Q3, tasks T005·T009·T010·T015·T016·T042·T045·T046·T051·T054·T062·T097·T098·T099·T100·T101·T112·T123 |
| FR-018 (환율 — 카드 시장 환율, 그래프 ECOS, 외환 경로) | R14-1·R14-8·R14-12, DM2, A1·A2, D2·D3, Q3·Q5-6·Q6, tasks T006·T012·T013·T021·T023·T026·T033·T039·T047·T050·T056·T060·T062·T087·T088·T090·T091·T093·T105·T115·T117·T123 |
| FR-019 (백그라운드 백필·이어 받기·확정·개정·따로 된 워커·관문·수집 상태 조회) | R14-2·R14-4·R14-10·R14-11, DM1, A2(`history`)·A4, D3, Q3, tasks T007·T008·T010·T011·T014·T015·T016·T017·T042·T045·T046·T047·T050·T051·T054·T055·T056·T057·T087·T098·T100 |
| FR-020 (세 출처·탑 10·목록) | R14-13, DM6, A5, D5, Q2·Q5-7, tasks T063·T064·T065·T066·T068·T070·T072·T073·T074·T075·T077·T079·T081·T083·T087 |
| FR-021 (줄의 칸·시각·유료) | R14-13, DM6, A5, D5, Q2, tasks T064·T065·T066·T070·T073·T074·T075·T079·T087 |
| FR-022 (새 탭·opener·허용 도메인) | R14-13, A5, D5, Q2·Q4, tasks T064·T065·T066·T070·T073·T074·T075·T079·T081·T087·T103·T109 |
| FR-023 (저장 안 함·10분 캐시·실패 백오프) | R14-13, DM6, A5, Q3, tasks T007·T011·T067·T068·T076·T087·T089·T092 |
| FR-024 (칸마다 실패·0건 = 실패·카드 안 막음) | R14-13, A5, D1·D5, Q2·Q3·Q5-8, tasks T064·T065·T066·T067·T068·T069·T070·T071·T072·T076·T077·T078·T079·T081·T087 |
| FR-025 (출처 밝힘·목록뿐) | R14-13, D1·D5, tasks T070·T079·T085·T121·T126 |
| FR-026 (메뉴·비교 불변, 밝은 테마 화면 불변 — 반복 2026-10-10c, 외환 일자별 표 두 열 예외 — 반복 2026-10-10d) | R14-10·R14-16·R14-23·R14-24, A6·A9, Q6·Q5-19·Q5-20, tasks T001·T002·T008·T014·T017·T084·T085·T086·T125·T128·T135·T139·T144·T148 |
| FR-027 (변화 까닭 — 시황 기사·찾지 못함·새 탭) | R14-17, DM6a, A8, D8, Q2·Q5-13, tasks T095·T103·T104·T105·T109·T113·T118·T119·T120·T121·T123 |
| FR-028 (장중 시세 — 일·주, 저장 안 함, 받는 범위 5세션·1개월 — 반복 2026-10-10c) | R14-19·R14-22, DM5, A2(`1d`·`5d`), D3, Q2·Q5-11·Q5-17, tasks T095·T102·T104·T105·T107·T112·T116·T121·T123·T128·T129·T132·T133·T137 |
| FR-030 (화면 테마 — 블랙 배경, 반복 2026-10-10c) | R14-23, DM7·DM9, D6·D9, Q4·Q5-18, tasks T128·T131·T135·T136·T137·T140 |
| FR-029 (일자별 표 — 시가·고가·저가·일·주·월) | R14-18·R14-21, DM5a, A7, D7, Q1·Q3·Q4·Q5-12, tasks T104·T105·T108·T114·T117·T119·T120·T121·T123·T124 |
| FR-031 (외환 일자별 표의 등락폭·등락율 — 바로 아래 행 대비·서버 계산·CSV 맨 끝, 반복 2026-10-10d) | R14-24, DM10, A9, D10, Q4·Q5-20·Q6, tasks T142·T143·T145·T146·T147·T149 |
| SC-001 (카드 2초·뉴스가 막지 않음) | R14-6·R14-13, Q7, tasks T071·T082·T087 |
| SC-002 (모달 그래프 1초·기간 1초, 월~모두 전환 0.3초·요청 없음 — 반복 2026-10-10c) | R14-12·R14-22, Q7, tasks T047·T056·T082·T107·T124·T130·T138 |
| SC-003 (전일 규칙·휴장 0%·카드 = 그래프) | R14-7·R14-8, Q1·Q3, tasks T010·T020·T023·T032·T041 |
| SC-004 (환율 그래프 = 외환·계열 표시·섞임 없음) | R14-12, Q3·Q5-6, tasks T047·T056·T062 |
| SC-005 (대표일·결측 이음 없음) | R14-5·R14-12, Q1, tasks T043·T044·T052·T053 |
| SC-006 (첫 날·빠진 날 없음·개정 기록) | R14-2·R14-4, DM1, Q3, tasks T009·T010·T015·T016·T046·T054·T062 |
| SC-007 (따로 실패·0건) | R14-6·R14-13, Q2·Q3·Q5-8, tasks T022·T034·T064·T065·T066·T068·T071·T081·T087·T094 |
| SC-008 (새 탭·도메인·캐시) | R14-13, Q2·Q3·Q5-7, tasks T064·T065·T066·T068·T070·T081·T089·T092 |
| SC-009 (잠정 표시·서머타임) | R14-7, Q1, tasks T019·T026·T031 |
| SC-010 (메뉴·비교 불변) | Q6, tasks T001·T002·T084·T086·T094·T125·T127·T139·T141·T148·T150 |
| SC-011 (처음 기동의 과거 구간 — 429 0·15분) | R14-2·R14-10, Q5-5, tasks T062·T087 |
| SC-012 (표 1초·주·월 행 = 일봉 계산) | R14-21, Q1·Q7, tasks T104·T108·T124 |
| SC-013 (까닭 문구 = 출처 글자·새 탭·찾지 못함에 문장 없음) | R14-17, Q2·Q5-13, tasks T103·T109·T123 |
| SC-014 (시가·고가·저가 = 원본) | R14-18, Q2·Q5-14, tasks T098·T101·T123 |
| SC-015 (블랙 테마 대비 4.5:1·깜빡임 0·밝은 화면 불변 — 반복 2026-10-10c) | R14-23, Q5-18·Q5-19, tasks T128·T131·T136·T137·T139 |
| SC-016 (외환 표 등락 = 두 행의 `Decimal` 계산·쪽 경계 "—" 0·`/latest` 불변 — 반복 2026-10-10d) | R14-24, DM10, A9, Q5-20·Q6, tasks T142·T147·T148 |

## Complexity Tracking

### 원칙 II 이탈 — 사용자 승인 2026-10-09(개인 이용 전제의 잠정 결정)

도구를 공개하거나 여러 사용자에게 제공하면 전제가 깨진다 — 그때 다시 판정한다(005·007·010 반복 3과 같다).

| 이탈 | 출처의 규칙(실측 2026-10-09) | 왜 필요한가 | 버린 대안 | 피해를 줄이는 장치 |
|------|------------------------------|-------------|-----------|---------------------|
| **005 이탈의 확장** — Yahoo 비공식 차트(`/v8/finance/chart`)를 지수·선물·VIX 12개 이력에, 같은 호스트의 `/v7/finance/spark`를 15개 현재 시세에 쓴다 | 공개 API가 아니다(005와 같다). Yahoo Terms가 자동 수집을 금지한다 | 해외 지수·선물·VIX·장중 값의 무료 공식 출처가 없다 | ECOS·KRX 공식 통계(국내 지수만, 장중 없음) | 관문으로 주식과 한도를 함께 지킨다(R14-10). spark는 30초에 많아야 한 번이고, 이력은 하루 한 번 이어 받는다 |
| **네이버 증권 내부 API**(`stock.naver.com/api/domestic/news/list?category=MAINNEWS`) | robots.txt `User-agent: *` `Disallow: /`(stock·m.stock·n.news 모두). 네이버 이용약관이 자동화 수단의 수집을 금지한다. 네이버파이낸셜 이용약관 제10조 ① 6이 "API 서버 접근·크롤링"을 금지한다 | 사용자가 출처로 정했다. 화면은 브라우저에서만 그려 HTML에 목록이 없다 | 언론사 경제 RSS(연합뉴스·한국경제 — 사용자에게 제시) | 10분에 많아야 한 번이다. 목록(제목·언론사·시각·링크)만 메모리에 두고 저장·재배포하지 않는다. 링크는 원문(`n.news.naver.com`)으로 보낸다. 출처를 밝힌다 |
| **Yahoo Finance Latest News HTML**(`finance.yahoo.com/topic/latest-news/`) | robots.txt는 `/topic/`을 허용한다. Yahoo Terms가 "any automated means … for any purpose without our express, prior permission"을 금지한다 | 사용자가 출처로 정했다. 공개 RSS가 없다(실측 404) | 미국 칸 빼기(사용자에게 제시) | 같음. robots 허용 경로만 부른다(`/xhr` 등 금지 경로 안 씀) |
| **Yahoo!ファイナンス ヘッドライン 내장 JSON**(`finance.yahoo.co.jp/news/headline`) | robots.txt는 허용한다. LINEヤフー 共通利用規約 8.3·14가 제공 목적을 넘는 이용을 금지한다 | 사용자가 출처로 정했다(명세 뒤 주소 변경 요청) | Yahoo!ニュース 경제 RSS(사용자에게 제시) | 같음 |

**반복 2026-10-10b의 새 경로 — 사용자 승인 2026-10-10**(T095 실측 뒤 "네이버 + Yahoo 종목"·장중 승인):

| 이탈 | 출처의 규칙 | 왜 필요한가 | 버린 대안 | 피해를 줄이는 장치 |
|------|-------------|-------------|-----------|---------------------|
| **변화 까닭의 시황 기사** — 네이버 증권 뉴스 포커스 내부 API(`/api/domestic/news/focus?sid=401·403·429&date=`)와 Yahoo Finance 종목 뉴스 화면(`/quote/{심볼}/news/`) — 지표마다 하나(R14-17) | 네이버: robots.txt `Disallow: /`, 약관이 자동 수집 금지(주요뉴스와 같다). Yahoo: robots가 `/quote/` 허용, 약관이 자동 수집 금지 | 사용자가 "출처의 시황 기사"를 골랐다. 네이버만이면 다섯 지표(니케이·항셍·상해·금·VIX)가 늘 "찾지 못함"(실측 0~2) | 네이버만 · Yahoo 종목 뉴스만 · 빼기(사용자에게 제시) | 저장 안 함, 지표마다 10분에 많아야 한 번(네이버는 날짜 둘), 제목·요약·링크뿐, 출처를 밝힘 |
| **장중 시세** — Yahoo 차트 `range=1d&interval=5m`·`range=5d&interval=30m`(005 이탈의 같은 엔드포인트, R14-19). 반복 2026-10-10c: 받는 범위를 `range=5d&interval=5m`·`range=1mo&interval=30m`로 넓힌다(왼쪽 스크롤 — 사용자 요청 2026-10-10, 새 출처 아님) | 005와 같다 | 사용자가 "보는 기간 8개, 장중 포함"을 골랐다 | 일봉만(사용자에게 제시) | 저장 안 함, 일 60초·주 5분 캐시, 주식과 같은 관문·같은 사용자 에이전트 |

### 해석이 필요한 선택

| 선택 | 이유 | 버린 대안 |
|------|------|-----------|
| 그래프 점을 단위 전체로 보내고 3만 점을 넘을 때만 LTTB(원칙 VII "다운샘플링 또는 가상화" 해석) | Lightweight Charts는 보이는 논리 범위만 그린다(가상화). 2,000점으로 줄이면 일 단위의 처음 범위(1년)가 20점 남짓이 되어 단위의 뜻이 사라진다(R14-12). quickstart 7이 1초를 잰다 | 2,000점 LTTB · 범위별 지연 로딩(범위 구독·이어 붙이기의 복잡도) |
| `YahooStockClient`에 선택 인자 `gate`(기본 `None`) | 같은 출처의 한도를 함께 지키려면(FR-019) 주식 쪽 요청도 관문을 지나야 한다. 기본값이 지금 동작이라 기존 계약 테스트·수집 값이 바뀌지 않는다 | 대시보드만 늦추기(합친 호출을 아무도 안 봄) · 주식 클라이언트 함께 쓰기(파서·날짜 규칙이 다름 — R14-3) |
| 시장 거래 시간표를 코드 상수로 둔다 | 출처가 세션 시각을 틀리게 주고 상태 필드가 없다. 시각뿐이라 날짜 하드코딩 검사에 걸리지 않는다. 제도가 바뀌면 표를 고친다 | 설정(env)으로 — 시장마다 세션 여러 개라 설정이 표가 된다 · 거래소 달력 패키지(pandas 의존) |
| 모달이지만 주소를 둔다(반복 2026-10-10b — 가로채기·병렬 경로, R14-20) | 사용자가 "주소 있는 모달"을 골랐다. 새로고침·즐겨찾기가 같은 모달을 연다 | 주소 없는 모달(새로고침에 사라짐) |
| 시가·고가·저가를 원본에서 되살린다(R14-18) | 원본 254개가 이미 있다(원칙 V의 원본 분리 저장). 다시 받으면 약 250회·8분 | 다시 받기 |
| 확정 값 개정을 표(`market_close_revision`)에 남긴다(008은 로그만) | SC-006("개정 기록 없이 바뀐 사례 0건")을 조회로 확인한다. 같은 개정은 한 번만 넣는다 | 로그만 — 운영자만 볼 수 있다 |
| 원칙 V의 "거래소별 캘린더로 휴장일 판정"을 **출처의 거래일 + 같은 시장 묶음 + 14일 공백 + 갱신 없는 세션**으로 한다(R14-5·R14-7) | 출처가 휴장 달력을 주지 않는다. 출처의 거래일은 거래소 달력을 반영한다(005의 "커버리지 안 빈 날 = 휴장" 선례). 묶음 판정은 그 선례에 결측을 가를 근거를 더한다 | 거래소 달력 패키지(`exchange_calendars` — pandas 의존, 달력 갱신 책임) · 시장마다 휴일 표를 손으로 관리(해마다 갱신, 빠뜨리면 조용히 틀림) |
| 카드·그래프의 오늘 잠정 값(spark)을 저장하지 않는다. 잠정에서 확정으로 바뀐 사실은 **확정 종가의 청크 원본**(`market_indicator_raw`)과 개정 표로 추적한다(원칙 V 해석 — 008 미발표 달 금리를 저장하지 않은 선례, 007 마감 전 일봉을 원본에만 남긴 선례) | 잠정 값은 30초마다 바뀌는 표시용이다. 저장하면 하루 수천 행이 되고, 확정 값은 다음 날 청크가 원본과 함께 따로 남긴다. 같은 날을 겹쳐 다시 받을 때 값이 바뀌면 개정 표가 남긴다 | spark 응답을 하루 한 번 원본에 남긴다 — 장중 한 순간의 값이라 확정 값과 견줄 기준이 되지 않는다 |
| 블랙 테마를 컴포넌트마다 `dark:` 클래스로 넣지 않고 **Tailwind v4 색 변수를 `.dark` 아래에서 재정의**한다(반복 2026-10-10c — R14-23) | 화면 부품 수백 곳의 클래스를 고치면 밝은 화면과 014 전 화면 테스트가 함께 흔들린다(FR-026). 변수 재정의는 클래스 글자를 그대로 두고 블랙에서만 색이 바뀐다. 가드 테스트(`darkPaletteGuard`)가 src가 쓰는 색 유틸리티마다 재정의가 있는지 본다 — 빠뜨리면 그 부품만 밝게 남는다(FR-030 실패 양상) | 전 컴포넌트 `dark:`(수백 곳) · CSS `filter: invert`(차트·상승 빨강·하락 파랑의 색 뜻까지 뒤집힌다) |
| 테마가 바뀌면 차트를 **다시 만든다**(`applyOptions`를 쓰지 않는다 — 반복 2026-10-10c) | 005~013 차트 테스트의 인라인 모의에 `applyOptions`가 없어 실행 중에 쓰면 그 테스트가 깨진다(CLAUDE.md 010 주의). 테마 전환은 드물고 다시 만들기는 차트 하나 수십 ms다 | `applyOptions`로 색만 바꾸기(모의 다섯 벌을 고쳐야 한다 — 014 전 테스트 변경) |
| 일봉 기간이 다시 일봉 전부를 받는다(반복 2026-10-10c — R14-22) | 왼쪽 스크롤로 앞 구간을 보이려면 점이 있어야 한다. 한 번 받아 월~모두를 오가면 전환에 요청이 없다. T124의 "기간만 읽기"는 그래프 경로에서 빠진다(결측 판정 함수의 `since`는 남는다) | 왼쪽 끝에 닿으면 더 받기(라이브러리 범위 사건 구독·이어 붙이기 — 2만 5천 점이면 한 번에 충분, 모의 확장 필요) |
| `IndicatorChart`가 그래프 점의 값에 `Number()`를 쓴다(그리기 전용 — 원칙 VI 해석) | Lightweight Charts는 숫자만 받는다. 글자 값(머리·커서 상자)은 서버 문자열 그대로다. 013 `CompareMetricBars`·`chartSeries.ts:120` 선례. T030이 이 파일 한 곳만 허용한다 | 서버가 숫자형을 따로 보낸다 — JSON 숫자는 화면에서 같은 변환을 거친다 |
