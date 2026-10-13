# 구현 주의 — 영역별

> `CLAUDE.md`에서 옮긴 영역별 구현 주의다(2026-10-11 — CLAUDE.md를 늘 지킬 규칙과 색인으로 줄였다). 글은 옮긴 그대로다.
> **그 영역을 고치기 전에 해당 절을 읽는다.** 기능별 요구·설계·실측 기록의 원본은 `specs/NNN-*/`다.

## 1. 기능 이력(상세)

| 기능 | 자산군 | 내용 |
|------|--------|------|
| 001 | 외환 | 환율 축적·조회·시각화. ECOS 어댑터, 청크 수집, 커버리지·재개, 작업·점유 모델 |
| 002 | 외환 | 외환 분석 화면 통합과 전역 셸. 확정/잠정 구분, 오늘 환율 새로고침, 스프레드 설정 |
| 003 | 외환 | 수집 실행 계층과 실시간 관측. **001·002가 만들어 두고 실행되지 않던 수집을 실제로 돌린다** |
| 004 | 외환 | 일자별 표의 스크롤 탐색과 일·주·월 기준일 전환. 기준일이 옮겨진 사실을 표시 |
| 005 | 주식/ETF | 배당 재투자 시뮬레이션. 시세·배당·분할 수집, 성과 표·차트, 원금 통화 환산, 이력 비교 |
| 006 | 주식/ETF | 005 개선. 키움 검색용 목록으로 국내·미국 한글·초성 검색, 고른 종목 등록, 시작일 기본값·월·년 이동, 엔화 고시 단위·환율 수집, 원금 통화 제한. **001의 `ensure_background_job` 고아 점유 결함과 005의 종목 미등록·휴일 시작 거절·분할 이중 적용 결함을 함께 고쳤다** |
| 007 | 가상자산 | 매수 후 보유 시뮬레이션. investing.com 코인 목록(영문·한국어 판, 주 1회)으로 이름·심볼·한글·초성 검색, 일봉(UTC 하루) 수집, 소수 8자리 수량, 가상자산 거래 수수료율 설정, KRW 기준 평가·차트(출처 결측은 끊는다)·이력 비교. **`load_rates`가 확정 환율만 읽게 고쳤다**(주식도 함께) |
| 008 | 예금 | 1년 만기 정기예금 재예치 시뮬레이션. ECOS 예금은행·비은행 가중평균 수신금리(월별)로 투자처 다섯(라디오), 만기마다 세후 이자 재예치, 원 미만 0 쪽 버림, 예금 이자 소득세율 설정(기본 15.4%), 미발표 달은 마지막 발표 달 금리로 잠정(저장하지 않음), 결측 달은 가입이면 409·재예치면 멈춤, 성과 표·차트(잠정 구간 연한 색)·이력 비교 |
| 009 | 부동산 | 아파트 매매 후 보유 시뮬레이션. 공공데이터포털 네 자료(실거래가 상세·법정동코드·단지 목록·기본 정보), 시·도 → 시·군·구 → 법정동 → 단지 풀다운(입주년도·세대수, 단지 목록 ↔ 실거래 짝짓기), 평형 일곱 구분, 시세 = 1·3·6·12·24·36개월 창의 실거래 평균(넓힌 창 추정, 최근 12개월 잠정), 취득세·중개 보수·재산세·종부세(시행일별 세법 표 2006~, 보유세 기준 비율 설정 기본 60%, 부부 5:5), 성과 표·차트(추정 점 표식·시세 없음 끊김)·이력 비교. **실측(T027·T054)으로 행정구역 두 결함(리 행 빈 상위 코드, 세종 시·도 없음), 재건축 전후 짝짓기, JSON 게이트웨이 사유, 평형 202의 진행 줄을 고쳤다** |
| 010 | 주식·가상자산·예금·부동산(+외환 다듬기) | 네 화면의 개선. **반복 3**: 주식 잔고 = 보유 × **종가**(매수는 시가 — 005 FR-013 대체, `DayBar.close_price` 필수)·표의 종가 열, 부동산 단지 이름 → Npay 부동산 단지 화면(`apt_complex_naver`, 비공개 자동완성 — 원칙 II 이탈). 성과 추이 차트에 가격 선(주식 **분할만 반영한 수정 종가**(반복 1 — 처음은 원주가 시가·분할 표식), 가상자산 시가, 예금 그 달 발표 금리, 부동산 그 달 실거래가 평균) — 눈금 없는 겹침 축(`priceScaleId "price"`), 시계열 점의 `price`(문자열)와 없을 때 `priceMissing`(`unpublished`·`missing`·`no_trades`). 커서 가까이 상자(표와 같은 형식 함수, 결측 구간마다 값 없는 자리 하나), 최근 시뮬레이션을 표 오른쪽에(`TableWithHistory` — 줄바꿈 flex, 경계 상수 없음), 주식 이력 다시 실행(등록 요청 없이). **반복 1**: 고른 종목·코인·단지와 이력 행의 이름을 네이버 증권·네이버 검색 새 탭 링크로(`lib/externalLinks`), 외환 왼쪽 정렬·통화 전환 동안 높이 붙잡기. **실측(T025·T036·T051)으로 상자 자리(그림 칸 기준 `point` → 화면 좌표)·이력 칸 폭·외환 기간 전환 스크롤을 고쳤다** |
| 011 | 주식·가상자산·예금(+주식 설정) | 투자 방식 둘째 갈래. **적립식**(주식·가상자산 — 매일·매주·매달·매년, 시작일에 맞춘 예정일, 휴장·출처 결측은 다음 거래일로 미뤄 합침, 원화 원금이면 납입마다 환전, 주식은 1주가 될 때까지 **매수 대기금**에 모으고 배당은 재투자일까지 **배당 현금**(분석 B1), 가상자산은 소수 8자리), 보드 다섯 칸(총 납입 원금·매매 수수료 총액·세금 총액·투자 수익·수익률 — 단순 수익률), 차트에 **누적 납입 원금 점선**. **정기 적금**(예금 — 1년·12회, 만기마다 적금 만기 + 정기예금 만기를 합쳐 1년 정기예금에 넣고 새 적금, 시중은행·상호금융만), 보드 여섯 칸. **주식 매도 세금 설정**(국내 0.20%·해외 22%·공제 250만 원 — 010 반복 4의 시행일별 표를 대체). 가상자산 매도 비용은 과세 시행일(2027-01-01) 규칙 하나. **실측(T030·T039)으로 지수 표기 금액(`0E-12`)·1센트 미만 금액의 `0.00` 표시를 고쳤다** |
| 012 | 외환·주식·가상자산(+네 자산군 이력·원금 기본값) | 네 화면의 개선. **외환 기간 전환은 창을 옮기지 않는다**(004 FR-005b를 기간 전환에 한해 대체 — 높이 붙잡기 `hooks/useHeightHold`, 놓을 때 바닥을 남긴다. 먼 날짜(FR-005a)는 그대로 표의 처음으로). **주식·가상자산 일자별 표에 일·주·월**(일시금·적립식 — 기준일 규칙은 외환과 같다: 주 = 금요일 이하의 마지막 시세일, 월 = 말일 이하의 마지막 시세일, 옮기면 📅, 끝나지 않은 구간은 ⏳, 사건 행(매수·배당락·재투자·납입)은 단위와 무관하게 남고, 출처 결측은 일 단위의 결측 구간 행 — 012 전의 "그 달 첫 거래일" 월 행·◇ 칸을 대체). **최근 시뮬레이션 이력을 로컬 DB에**(`simulation_history`·`history_setting`, 보관 기간 설정 7·30·90·180·365일·무기한 — 기본 30일, 마지막 실행 기준, 옛 브라우저 이력은 화면을 처음 열 때 옮긴다). **주식·가상자산·예금 원금 칸 처음 값 10,000,000원**. **반복 US5**: 주식·가상자산 보드 넷(일시금·적립식)에 **현재 잔고**(기준일의 원화 총자산 — 잔고 + 예수금(적립식은 + 매수 대기금·배당 현금), 매도 비용 전). 일시금 요약에 `totalKrw`를 더했다(= `profit` + 원화 원금, 적립식 011과 같은 뜻) — 보드 부품은 `totalKrw`가 있을 때만 칸을 그려 예금 보드가 그대로다. **반복 US6**: 해외 주식 매도 칸(일시금)·세금 칸(적립식)에 양도차익의 구성 "매도금액 − 취득가 − 수수료"(`saleCost.saleKrw`·`acquisitionKrw`·`feesKrw` — `foreign_sale_cost`가 차익을 만든 원 미만 버림 값, 국내 `null`). 취득가는 배당 재투자 매수를 포함하고 매도금액에 예수금은 없다 — "현재 잔고 − 원금"과 차익이 다른 까닭이다(버그 평가 `foreign-sale-tax-gain`, 계산은 맞았다) |
| 013 | 주식·가상자산·예금·부동산(투자 비교) | 새 화면 `/compare`. 한 자산군의 대상 2~10개(예금은 투자처 다섯까지)를 **같은 조건으로 한 번에** 실행해 나란히 본다 — 메뉴와 같은 검색·고르기 부품, 일곱 방식(주식·가상자산 일시금·적립식, 정기예금·정기 적금, 부동산 매입 후 보유). **비교 경로 일곱**(`/api/comparison/<자산군>/<메뉴 경로>`)이 메뉴 경로와 같은 함수를 같은 차례로 불러 `summary`·`series`가 메뉴와 같고 `comparison` 블록(원금·현재 가치·비용(반영 몫·매도 가정 몫)·투자 수익·수익률·`mainBasis`·`lineEnd`·잠정)을 더한다. 비교 표(정렬은 소수 문자열 견주기), 수익률 추이(보유 중 선 + 기준일 매도 후 점), 최종 지표 막대. 막힌 대상이 하나라도 있으면 비교 전체를 막고 가장 이른 시작일을 제안(명확화 1), 수집 중 대상은 끝나면 채우고(명확화 2), 조건을 바꾸면 흐린다(명확화 6). **저장한 비교**(`saved_comparison`, 보관 기간 없음 — 지울 때까지), 불러오면 지금 데이터로 다시 실행. 비교는 **이력을 쓰지 않는다**. 계산 모듈의 더함(값은 그대로): 정기예금 `accrued_tax`·정기 적금 `open_tax`, 환율 찾기 이분 탐색. **반복 2026-10-09**: 비교 표의 투자 원금과 현재 가치 사이에 단가 열 셋(시작일 단가·기준일 단가·등락 — 차이·등락률) — 주식은 상장국 통화의 **수정주가**(분할만 반영한 종가, 메뉴 차트 주가 선과 같은 값), 가상자산 일봉 시가, 예금 발표 금리와 %p(등락률 없음), 부동산 그 달 시세. 서버가 `comparison.unitPrice`(`simulation/unit_price.py`)로 계산하고 메뉴 응답은 그대로. **반복 2026-10-09b**: 비교 표의 계산된 줄 끝 "투자 시뮬레이션" 단추 → 그 줄의 조건으로 그 메뉴의 결과(투자 결과 패널·성과 추이·일자별 표)를 모달로 — 메뉴 경로·메뉴 부품, 이력 없음. **반복 2026-10-09c**: 백분율(`lib/format.formatPercent`)의 정수부를 세 자리마다 쉼표(`+1,761.91%`) — 공유 함수라 네 메뉴 화면도 함께(형식만, 값 불변) |
| 014 | 대시보드(지표·뉴스) | 새 화면 `/dashboard`(최상위 `/`가 옮겨 간다 — 사이드바 "대시보드"). **지표 카드 15개**(KOSPI·KOSDAQ·다우·나스닥·S&P 500·SOX·니케이 225·항셍·상해 종합·달러·엔(100엔)·유로·WTI·금·VIX) — Yahoo `/v7/finance/spark` 한 번 + 빠진 심볼만 `/v8/finance/chart`(`api/services/market_quotes` — 30초 캐시·단일 비행, 화면은 보이는 동안 60초마다), 장 상태 다섯(시장 현지 시각 — `zoneinfo`, 갱신 없는 세션 = 휴장), 전일은 이력(없으면 출처로 물러남)·환율은 늘 출처(런던 0시 경계, 시장 환율 — 저장하지 않는다). **지표 화면** `/dashboard/{지표}?unit=`(일·주·월·년 — 주·월은 `period_table` 기준일 규칙, 결측 = 같은 시장 묶음이 가진 날 또는 14일 넘는 빈칸, 3만 점 넘으면 LTTB, 오늘 잠정 꼬리 = 카드 값) — 이력은 로컬 DB(`market_indicator_daily`·`_raw`·`_coverage`·`market_close_revision`), 수집은 lifespan **아홉째 태스크**(`worker/market_worker` — 2년 청크 최신부터, 첫 날 = 출처 `firstTradeDate`, 겹쳐 받은 날의 값이 바뀌면 덮지 않고 개정 한 줄), 받는 중이면 202 + 진행 SSE. **환율 그래프는 외환 메뉴(001)의 ECOS 고시 이력**이다(대시보드는 ECOS를 부르지 않는다 — 모자라면 `ensure_background_job`). **뉴스 세 칸**(네이버 증권 주요뉴스·Yahoo Finance Latest News·Yahoo!ファイナンス ヘッドライン — 위 10개, 같은 제목 한 번, 허용 도메인 밖·`javascript:` 줄은 버림, 새 탭 `noopener noreferrer`, **저장하지 않고 메모리 10분**, 칸마다 실패·60→600초 백오프, 0건 = "읽지 못함"). **실측(T081·T083)으로 Yahoo 화면의 긴 응답 머리(약 19.5KB — aiohttp 기본 한도 8,190바이트)·받은 시각의 마이크로초·1024px 창의 뉴스 칸(창 폭 경계 → 줄바꿈 flex)을 고쳤다**. **반복 2026-10-10b**: 지표 화면 → **주소 있는 모달**(`app/dashboard/@modal/(.)[indicator]` 가로채기 + `[indicator]/page.tsx` = 대시보드 + 같은 모달), 단위 넷 → **보는 기간 여덟**(`range=1d|5d|1m|1y|5y|10y|20y|all`, 처음 1년, 옛 `unit` 무시 — 월 이상은 그 기간의 일봉 전부, 1d·5d는 **장중 시세**(Yahoo 5분·30분, 저장 안 함 — `indicator_intraday`)), **변화 까닭**(`/commentary` — 네이버 뉴스 포커스·Yahoo 종목 뉴스의 마지막 세션 이후 기사 최대 3개, 출처 글자 그대로, 10분), **일자별 표**(`/table` — 012 쪽 넘기기·행 꼴, 시가·고가·저가·종가·대비·등락률, `market_indicator_daily`에 OHLC 열 셋 — 이미 저장한 날은 기동 때 원본에서 되살린다). **실측(T123·T124)으로 "모두"가 끝 2천 점만 보이던 막대 간격 하한·장중 UTC 축·환율 표의 오늘 미수집 결측 행·까닭 어림 시각·옛 커서 상자·표 단위 전환의 흔들림을 고치고, 그래프 경로가 기간 앞부터만 읽게 했다**. **반복 2026-10-10c**: 기간은 **처음 보이는 범위**(일봉 전부 + `windows` — 왼쪽으로 끌면 첫 날까지, 월~모두 전환은 요청 없음, 장중은 일 5세션·주 1개월 + `window`, 진한 실선), **블랙 배경**(상단 바 오른쪽 끝 단추 — 전 화면·차트 다섯 종, 브라우저 저장소, 그리기 전 스크립트). **실측(T137·T138)으로 기간 단추의 모달 다시 붙기(`router.replace` → `history.replaceState`)·블랙 회색 400 대비·모달 열기의 이중 요청을 고쳤다**. **반복 2026-10-10d**: 외환 일자별 표(일·주·월)·CSV 오른쪽 끝에 **등락폭·등락율**(바로 아래 행 대비 — `/api/fx/daily` 행의 `change`, 계산은 `/latest`와 같은 `simulation/fx_change`, 014 FR-026의 외환 예외). **반복 2026-10-10e**: 투자 비교의 주식·가상자산 대상 이름에 **티커**(`S&P 500 뱅가드 ETF(VOO)`·`삼성전자(005930)`·`비트코인(BTC)` — 칩·표·범례·막대·모달·저장 목록, 화면만), 코인 검색 결과 줄도 이름(심볼). **실측(T154)으로 블랙 배경의 비교 수익률 범례 대비(3.72)를 고쳤다**. **반복 2026-10-10f**: 주식·가상자산의 **상장일**(검색 결과 줄의 `상장 …`(키움)·`첫 거래 …`(Yahoo)·`첫 일봉 …`(코인), 투자 비교 표의 대상과 기준일 사이 "상장일" 열 — 새 열 `stock.first_trade_date`(표시 전용)). **실측(T164)으로 등록 경로의 다시 시도 지연(출처가 막히면 고르기 3.0초)을 고쳤다**. **반복 2026-10-10g**(사용자 보고): 주식·가상자산 메뉴의 **고른 종목·코인 줄 밑**에도 상장일 한 줄(같은 글자 — 모르면 `상장일 —`) — 새 읽기 경로 둘(`/api/stocks/listing-date`·`/api/crypto/listing-date`), 고른 대상이 바뀔 때·그 결과나 시작 가능 날짜 안내가 올 때 묻는다. **반복 2026-10-11**(사용자 요청): 일·주·월 단추가 있는 투자 성과표(외환 일자별 환율 표·주식·가상자산 일자별 투자 성과·투자 비교 모달의 주식·가상자산 표)의 **처음 단위가 월**이다 — 화면 스토어의 처음 값과 비교 모달의 첫 표 요청만, 서버 기본(`period` 없음 = 일)은 그대로. **반복 2026-10-11b**(사용자 요청): 투자 비교 수익률 추이의 **왼쪽 축에 현재 가치**(대상마다 가는 선 — 비교 블록의 새 키 `valueLine`: 시계열 점과 같은 날마다 원화 총자산(일시금 주식·가상자산은 예수금 포함이라 점 `balance`와 다르다) + 매도 후 금액, 메뉴 응답·`lineEnd`는 그대로), 수익률 선이 있는 세 그래프(비교 수익률 추이·성과 추이·이력 수익률 비교)의 **두 지점 확대**(두 번 누르기 → `setVisibleRange`, 오른쪽 위 [리셋] → `fitContent`, 화면만 — `hooks/useChartZoom`) |

## 2. 헌법 원칙 II 이탈(상세)

헌법 원칙 II 이탈이 열 기록되어 있다 — 모두 개인 이용을 전제로 한 **잠정** 결정이고, 도구를 공개하거나 여러 사용자에게
제공할 계획이 생기면 전제가 깨진다.

- 005 — 주식 시세 출처가 Yahoo의 **비공식 엔드포인트**다
- 007 — 가상자산 목록·시세 출처가 investing.com의 **공개되지 않은 내부 API**다. 약관이 허가 없는 저장·사용을 금지한다
  (`specs/007-crypto-investment-simulation/plan.md`의 Complexity Tracking, 사용자 승인)
- 010 반복 3 — 부동산 단지 화면 링크의 단지 번호를 Npay 부동산 단지 자동완성(`fin.land.naver.com/front-api`, **공개되지 않은 내부 API**)으로
  찾는다(`specs/010-chart-price-overlay-history-layout/plan.md`의 Complexity Tracking, 사용자 승인 2026-10-06)
- 014 — 아래 넷 모두 `specs/014-market-dashboard/plan.md`의 Complexity Tracking, 사용자 승인 2026-10-09
  - 대시보드 지표(지수·원자재·VIX·시장 환율)의 시세·일봉도 005와 같은 Yahoo **비공식 엔드포인트**(`/v7/finance/spark`·`/v8/finance/chart`)다
  - 한국 뉴스는 네이버 증권 주요뉴스의 **공개되지 않은 내부 API**(`stock.naver.com/api/domestic/news/list`)다. robots.txt가 모두 막고 약관이 자동 수집을 금지한다
  - 미국 뉴스는 Yahoo Finance Latest News **화면 HTML**이다. 약관이 허가 없는 자동 수집을 금지한다
  - 일본 뉴스는 Yahoo!ファイナンス ヘッドライン 화면에 **내장된 상태 JSON**(`window.__PRELOADED_STATE__`)이다
- 014 반복 2026-10-10b — 아래 둘 모두 같은 Complexity Tracking, T095 실측 뒤 사용자 승인 2026-10-10
  - 지표 모달의 변화 까닭은 네이버 증권 뉴스 포커스의 **공개되지 않은 내부 API**(`/api/domestic/news/focus`)와 Yahoo Finance 종목 뉴스 **화면 HTML**(`/quote/{심볼}/news/`)이다
  - 지표 모달의 장중 시세(일·주)도 005와 같은 Yahoo **비공식 엔드포인트**(`/v8/finance/chart`의 `interval=5m·30m`)다
- 014 반복 2026-10-11d — 같은 Complexity Tracking, T202 실측 뒤 사용자 승인 2026-10-11
  - 대시보드 기준금리는 네이버 증권 기준금리의 **공개되지 않은 내부 API**(`/api/securityService/marketindex/standardInterest`·`…/{국가}/calendars`)다.
    robots.txt가 모두 막고 약관이 자동 수집을 금지한다. 변화 까닭은 승인된 뉴스 포커스의 다른 분류(`sid=404`)라 새 경로가 아니다

## 3. 수집·출처

**자산군마다 수집 워커가 따로다.** `lifespan`이 아홉 태스크를 띄운다 — FX 수집, 점유 회수, 주식 수집, **검색용 목록
갱신(006)**, **코인 목록 갱신·가상자산 수집(007)**, **예금 금리 수집(008)**, **부동산 수집(009 — 안에서 실거래 줄과 목록 줄
둘)**, **대시보드 지표 이력 수집(014)**. 출처가 다르므로 호출 한도도 따로이며, 한 큐에 섞으면 환율 수집이 주식
수집을 막으면서 그 이유가 화면 어디에도 드러나지 않는다. 목록 갱신 워커는 안에서 국내·미국 두 줄로 나뉜다 — 미국 목록의
분당 제한이 국내를 막지 않게 한다. 가상자산의 두 줄(목록·시세)은 **같은 출처 클라이언트(`InvestingClient`)를 함께
쓴다** — 요청 사이 최소 간격(`INVESTING_MIN_INTERVAL_SECONDS`)을 두 줄이 함께 지킨다.

**예금 금리는 환율과 같은 ECOS·같은 인증키다**(008). 수집 줄은 따로지만(환율 백필이 예금을 막지 않는다) ECOS 요청은
**관문(`ingestion/ecos/gate.py`의 `EcosGate`) 하나를 함께 지난다** — 동시 요청 수(`ECOS_MAX_CONCURRENT_REQUESTS`)를 함께
지키고, 한도 초과(`INFO-300`)면 관문 전체가 물러선다. 관문은 이벤트 루프마다 하나다. 시중은행은 **2012-01부터**다(정확히
1년인 항목). 금리는 익월 발표라 최근 달은 **잠정**이다 — 받지 않은 달이 있어도 오늘(한국 시간) 이미 확인했으면 202가 아니라
200(잠정)이고, 오늘 확인이 실패했으면 받아 둔 금리로 200 + `recheckFailed`다(`checked_on`은 성공했을 때만 갱신 — 다음 날
다시 확인). 겹쳐 받은 최근 2개월(`DEPOSIT_RECHECK_OVERLAP_MONTHS`)의 값이 바뀌어도 덮어쓰지 않고 `deposit_rate_revised` 사건만
남긴다. **ECOS 인증키는 발급일부터 2년 유효하다**(약관 제4조 ③) — 만료되면 환율·예금 수집이 함께 `auth`로 실패하므로
연장한다. 화면·README에 출처(ECOS)를 밝힌다(약관 제7조 ②).

**부동산 출처(공공데이터포털)는 네 자료를 각각 활용신청해야 한다**(009 — 실거래가 **상세** 자료·법정동코드·단지 목록·기본
정보, 같은 `DATA_API_KEY`). 미등록이면 403(사유 30) → `auth`다. **게이트웨이 오류 본문은 자료 형식을 따른다** — 실거래는 XML,
법정동코드·단지 목록·기본 정보는 JSON(`"returnReasonCode": "30"`)이다(T054 실측 — XML만 읽으면 틀린 키가 연결 오류로 보인다). 키가 **URL 질의**(`serviceKey`)에 들어가므로 URL을 어디에도
남기지 않는다 — 원본은 본문만, 오류 문구는 키(날 것·인코딩·디코딩)를 지운 뒤 `mask_secrets`. 하루 호출 수는 자료별로 **보내기 전에
DB에 센다**(`apt_api_usage`, 한국 시간 날짜 — 다시 띄워도 이어 센다). 처음 고르는 시·군·구는 전체 이력(약 260~280회)을 받는다.
`APT_TRADE_PROBE_START`는 **코드 기본값이 없다**(없으면 실거래 수집이 멈춘다). 잠정은 **12개월**이다 — 최근 3개월은 하루 한 번,
4~12개월 전 달은 한 달에 한 번 다시 받는다(늦은 해제). **현존 시·군·구 코드만** 쓴다 — 출처가 과거 거래도 새 코드로만 준다. 세법이
바뀌면 `simulation/apt_tax_rules.py`에 규칙을 더하고 현행 규칙의 끝을 닫는다(표 밖 날짜는 거절 — 가까운 해로 메우지 않는다).
실거래 수집 중에는 목록 쪽(단지 목록·기본 정보)이 실거래와 짝짓지 않는다 — 그 실행의 마지막 맞추기가 건축년도를 알고 짝짓는다.

**가상자산 출처(investing.com)는 로그인이 필요 없지만 브라우저형 사용자 에이전트가 있어야 한다**(`INVESTING_USER_AGENT`,
줄이 없으면 코드의 기본값). 비워 두면 aiohttp 기본값이 나가 403(`blocked`)이 된다 — 차단 경로를 재현하는 수단이다. 일봉은
**UTC 하루**이고 계산 끝은 **UTC 어제**다 — 마감 전 일봉은 저장하지 않는다(원본에는 남는다). 코인 목록은 마지막 성공 뒤
7일이 지나 처음 검색할 때(한국 시간 날짜) 받고, 처음엔 약 2분 걸린다 — 검색 칸이 진행 스트림(`/api/crypto/list/progress`)으로
받은 쪽 수를 보인다. 커버리지 안의 빈 날은 휴장이 아니라 **출처 결측**(`source_missing` — 차트가 끊는다)이다.

**검색용 목록(006)은 키움 인증 정보가 있어야 받는다**(`.env`의 `KIWOOM_MODE`·
`KIWOOM_APP_KEY`·`KIWOOM_APP_SECRET`). 비어 있으면 받지 않고 검색 응답의 `lists`가
`auth_missing`을 알린다. **인증 정보를 고치면 백엔드를 다시 띄운다** — 기동 시 읽고, 인증
실패 막힘도 프로세스 메모리라 재시작에서 풀린다. 목록은 그날(한국 시간) 처음 검색할 때 받는다.
키·시크릿·토큰 값을 출력하거나 셸 인자로 넘기지 말 것.

**외환 수집 요청은 `collection_gate.ensure_background_job`만 거친다**(006). 이 함수는 작업도
점유도 만들지 않고 003의 시작 큐에 요청만 넘긴 뒤 수집 표(`collecting`·`queued`·`waiting`)를
돌려준다. 작업과 점유는 워커의 `run_once`만 만든다 — 001처럼 미리 만들면 아무도 실행하지 않는
고아 점유가 그 통화의 수집을 막는다.

**주식 조회는 미수집 구간이 있으면 202를 준다.** 표와 차트가 같은 판정
(`api/services/stock_collect.collecting_body`)을 쓰므로, 한쪽만 결과가 나오는 일은 없다.
006부터 원금 통화와 종목 통화가 다르면 **환율 커버리지도 함께 보고**, 주식 수집은 시작 월
1일부터 받는다(시작 월의 실제 일봉으로 시작 가능 날짜를 판정한다). 받은
만큼만 계산한 수익률은 값이 멀쩡해 보이지만 틀렸다는 것이 이 게이트의 이유다.
그래서 **200 응답의 차트 결측 구간은 모두 휴장일**이고, 미수집은 거기 섞일 수 없다.

**주식 시세 출처(Yahoo)는 원주가를 주지 않는다**(006 FR-034). 시가·종가·배당이 받는 시점까지의
분할을 소급 반영한 값이라, 어댑터(`ingestion/yahoo/client.py`)가 청크마다 그 뒤의 분할 기록을 함께
받아 원주가로 되살린다. 시뮬레이션은 원주가에 분할 날 주식 수 조정을 더한다 — 어댑터를 거치지 않은
반영가를 저장하면 분할이 두 번 들어가 수익률이 몇 배로 부푼다(005가 그랬다).

**Npay 부동산 단지 번호**(010 반복 3): 단지 하나에 **한 번** 찾아 `apt_complex_naver`에 저장하고 다시 부르지 않는다(못 찾음은
`NAVER_LAND_RECHECK_DAYS` 뒤 다시). **실패는 저장하지 않는다** — 링크는 네이버 검색으로 물러난다. 출처는 브라우저형 사용자 에이전트·`Referer`·
**`Accept-Language`**가 없으면 403·429다(429가 늘 요청 제한은 아니다 — T067 실측). 같은 이름의 다른 지역 단지가 있어 **법정동 코드로 먼저 거른다**.
클라이언트는 lifespan에 하나(요청 경로만 쓴다 — 수집 태스크 없음). 새 테이블이라 개발 DB에 `alembic upgrade head`가 필요하다.

## 4. 계산·보드

**주식 잔고는 종가로 평가한다**(010 반복 3): `DayBar(date, open_price, close_price)` — 종가는 필수(시가로 메우지 않는다). 매수·수수료·배당율은 시가다.
참조 구현 대조(`test_reference_parity`)는 종가 = 시가 입력으로 매수·배당·예수금만 맞춘다 — 실제 잔고·수익률은 참조 구현(시가 평가)과 다르다.

**부동산 보드의 매도비용**(010 반복 5): 보드만 — 기준일에 평가액으로 판다고 가정한 매도 중개 보수(매수와 같은 서울 조례 요율) + 양도소득세(1세대 1주택,
부부 5:5 — 인별 기본공제·누진세율·지방소득세 10%, 12억 초과 비율 과세, 장특공 표2·표1, 단기 60%·70%)를 `summary.saleCost`로 더하고 `profitAfterSale`·
`returnRateAfterSale`을 낸다. 규칙은 `simulation/apt_tax_rules.py`의 `TRANSFER_RULES`(2023-01-01부터 — 그 앞은 세금을 비운다), 계산은 `simulation/apt_sale_cost.py`.
거주 기간 = 보유 × **거주 기간 비율**(설정, 기본 100%) — 보유세 기준 비율과 **따로 된 경로**(`/api/realestate/settings/residence`, `apt_setting.residence_ratio`
NULL = 100%)다. 비과세의 거주 2년 요건은 늘 적용한다(조정대상지역 취득 가정 — 보수적).

**주식 보드의 매도 수수료·세금**(010 반복 4 → 011): 보드만 — 기준일 상태를 모두 판다고 가정한 수수료(매매 수수료율)와 세금(국내 매도 세율,
해외 (원화 양도차익 − 기본공제) × 양도소득세율)을 `summary.saleCost`로 **더하고** `profitAfterSale`·`returnRateAfterSale`을 낸다 — `summary.profit`·표·차트·
이력 비교는 보유 중 값 그대로다. **011부터 세율·공제는 설정값이다**(`GET/PUT /api/stocks/settings/sale-tax`, `stock_setting`의 열 셋, NULL = 기본값) —
010의 시행일별 표는 없어졌고 모든 기준일에 같은 값이다. 기본값은 `Decimal("0.0020")`·`Decimal("0.22")`·`Decimal("2500000")`로 010 표 값과 **문자열까지
같다**(기본 설정의 보드 응답이 바뀌지 않는다). 저장소(`get_sale_tax`)는 기본값과 같은 저장값을 기본값 상수로 돌려준다 — 되돌린 뒤 DB 자릿수(`"0.002000"`)로
돌아오면 `taxRate`가 처음과 달라진다(SC-007). ETF 특례·대주주 양도세는 반영하지 않는다.

**적립식은 일시금과 따로 된 경로다**(011): `/api/stocks/recurring-simulation`·`/api/crypto/recurring-simulation`(+ `/series`). 검증·수집 판정·계산 끝은
일시금과 **같은 함수를 같은 순서로** 부른다(가상자산 계산 끝은 `routes/crypto_simulation.calculation_end` — 테스트는 그 모듈의 `utc_yesterday`를 바꿔
2027년 기준일을 만든다). 예정일은 `simulation/contribution_schedule`(시작일에 맞춘 날, 말일·2-29 규칙 `months_later`), 원화 평가는 행마다 **그 행까지의
원화 분모**로 나눈다 — 원금 하나로 나누면 수익률이 납입 횟수만큼 부푼다. 금액 문자열은 지수 표기 없이(`stock_recurring.dec` — `Decimal("0E-12")`를
`str()`로 내면 화면이 "0E12"다). 가상자산 매도 비용은 `simulation/crypto_sale_cost.py`의 과세 시행일(2027-01-01) 하나 — 그 뒤 기준일은 세금을 **비운다**
(0으로 메우지 않는다). 이 파일은 날짜 하드코딩 검사의 허용 목록(`_LEGAL_DATE_MODULES`)에 있다(법령 시행일 — 출처의 시작일을 넣지 않는다).

**정기 적금의 금리는 금리 계열 키다**(011): 적금 금리는 008의 수집 경로(`deposit_rate`·커버리지·잠금·큐·실행기)에 `commercial_bank_isav`·`mutual_finance_isav`로
담는다 — 스키마 변경 없음, 키 ↔ 출처 항목은 `ingestion/ecos/installment_items.py`에만 있다(정기적금(1-2년) `BEABAA2122`, 상호금융 정기적금 `BEBB0200` —
이름 패턴은 정확히 일치). 계열 키는 **응답에 나오지 않는다** — 202의 `institution`은 투자처 키이고 `series`(`installment`·`deposit`)가 더해진다. 적금은
**시중은행·상호금융만**이다(나머지 셋은 400 `installment_not_available` — 정기예금 금리로 대신하지 않는다). 시작 가능 날짜는 max(적금 첫 달, 정기예금 첫 달 − 1년)
(시중은행 2011-01-01). 계산은 `simulation/installment_ladder.py`(008 `deposit_rollover`의 이자·세금 함수와 금리 해석기 `rate_resolver`를 함께 쓴다).

## 5. 화면·차트

**성과 차트(`components/stock/PerformanceChart.tsx` — 네 자산군 공유)를 고칠 때**(010): 기존 차트 테스트의 모의 객체는 파일마다
인라인이고 `createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`만 있다 — 거기 없는 API
(`createSeriesMarkers`·`subscribeClick`·`priceScale()`)나 라이브러리 열거형을 **실행 중에** 쓰면 005~010의 차트 테스트가 함께 깨진다.
가격이 없는 칸은 `gaps`(잔고 선이 끊기는 자리)가 아니라 점의 `priceMissing`이다 — `gaps`에 넣으면 잔고 선까지 끊긴다. 상자 자리는
`subscribeCrosshairMove`의 `point`가 아니라 `sourceEvent`의 화면 좌표로 잰다 — `point`는 왼쪽 가격 축을 뺀 그림 칸 기준이다.
주식 주가 선은 **차트 표시용** 수정 종가(`simulation/split_adjust.split_restated_close` — 원주가 종가 ÷ 그 날 뒤 분할 비율)이고 재투자 계산에는
들어가지 않는다. 이 함수에 `adjusted_close`·`close_adjusted`·`adjclose` 같은 이름을 쓰면 005 가드(`tests/unit/test_no_adjusted_price.py` —
시뮬레이션 계층에서 출처 수정가의 이름을 찾는다)에 걸린다(010 반복 1).

**수익률 그래프의 두 지점 확대**(014 반복 2026-10-11b): 세 그래프(`CompareReturnChart`·`PerformanceChart`·`ComparisonChart`)가 `hooks/useChartZoom`·`components/ChartZoomControls`를
함께 쓴다. 누름은 차트 칸의 DOM 잡기 단계 이벤트(`onMouseDownCapture`·`onClickCapture` — 4px 넘게 움직였으면 끌기라 무시)이고, 날짜는 커서 추적의 `time`(`track`)이다 — 커서를
쫓지 않는 이력 비교만 누를 때 `coordinateToTime(화면 x − 칸 왼쪽)`으로 묻는다. **새 차트 API(`setVisibleRange`·`coordinateToTime`)는 누를 때만 부른다** — 그릴 때 부르면 위 모의가 깨진다
(이력 화면 `CryptoHistoryList`의 모의에는 `subscribeCrosshairMove`도 없다). 차트 효과의 정리에서 `detach`를 불러 다시 그린 차트는 처음 범위다. 고르는 동안의 Esc는 `window` 잡기 단계에서
받아 전파를 멈춘다 — 투자 비교 모달(`document`의 Esc)이 먼저 닫히면 고르기를 무르려다 결과 화면을 잃는다. 새 수익률 그래프를 만들면 같은 훅을 쓴다.

**확대 구간의 일 단위 자료**(014 반복 2026-10-11c): 주식·가상자산 시계열 경로 여덟(메뉴 넷·비교 넷)의 선택 질의 `viewFrom`·`viewTo`(`series_query.view_window` — 둘 다 또는 없음,
하나만·거꾸로면 400 `invalid_query`, 계산 구간으로 자름)는 **계산을 바꾸지 않고** 그 구간의 시세일마다 점을 낸다 — 주식 일시금은 `stock_series.window_states`(일자별 표 "일" 행과 같은 규칙:
그 날 행이 있으면 그날의 마지막 행, 없으면 `daily`를 `convert`), 적립식은 `recurring_series._last_views` + `view_of`, 가상자산은 `daily` 그대로. `end`를 구간 끝으로 바꿔 부르면 계산이
바뀐다(기준일·매도 비용·적립식 분모). 비교 경로는 같은 점으로 `valueLine`을 낸다(`comparison_values.stock_lump_totals(..., states)`). 화면은 `hooks/useZoomDetail`(받은 자료는 받은 바탕 자료·
테마에만 쓴다 — 차례 번호로 늦은 응답을 버린다)과 `lib/chartDetail`(구간 끼우기 — 날짜 글자 비교)로 다시 그리고 `setVisibleRange(받은 구간)`을 다시 놓는다. 그래서 확대 상태는 바탕 자료·
테마가 바뀔 때만 비운다(`release`는 차트만, `clear`는 상태만, `detach`는 둘 다). 받는 그래프는 `lib/seriesDetail.needsDetail`(주식 늘, 가상자산·외환은 `downsampled`일 때만, 예금·부동산
없음)이고 주식·가상자산 스토어가 시계열 경로(`seriesPath`·`recurringSeriesPath`, 이력 항목 `path`)를 기억한다. 외환 추이(`FxChart`)·지표 일봉 그래프(`IndicatorChart` `DailyChart`)도 같은
확대 훅이다 — 지표 [리셋]은 `resetView`(그 기간의 `showWindow`)이고 기간을 바꾸면 풀린다, 장중은 대상 밖. 확대 단추·상태 줄은 오른쪽 가격 축 밖이다(`controlsRight` — 처음 누를 때
`priceScale("right").width()`를 잰다, 누를 때만 부른다).

**화면 테스트가 실제 차트를 그리면 실행이 실패한다**(011 T036): jsdom에 `matchMedia`가 없어 `lightweight-charts`가 처리되지 않은 오류를 내고, vitest는
단언이 모두 통과해도 **종료 코드 1**이다. 결과 화면을 그리는 페이지 테스트는 `lightweight-charts`를 모의하고, 시계열 요청에는 시계열 응답을 준다 — "N passed"만
보고 게이트를 판정하지 말고 종료 코드를 본다.

**외환 화면의 스크롤**(010 반복 1 → 012): 통화·기간 단위를 바꾸면 `daily`가 비워져 일자별 표가 떨어졌다 다시 붙는다. 그동안 문서가 무너지지 않게
바꾸기 직전 높이를 붙잡는다(`hooks/useHeightHold` — 주식·가상자산 표의 단위 전환도 같은 훅). **012부터 기간 전환은 창을 옮기지 않는다** — `setPeriod`는
`tableEpoch`를 올리지 않고, 새 표가 짧아 스크롤을 받치지 못하면 놓을 때 창 아래 끝까지의 바닥을 남긴다(그냥 놓으면 문서가 줄어 창이 끌려 올라간다).
먼 날짜를 골라 표를 새로 받을 때(004 FR-005a)만 화면이 기억한 표의 차례로 표의 처음으로 간다 — 새로 붙은 `DailyTable`은 직전 `resetKey`를 모른다.
"첫 렌더인가"로 가르는 장치는 개발 모드의 StrictMode 이중 효과에 무력하다(통화 전환마다 창이 표로 튀었다).

**외환 일자별 표의 등락**(014 반복 2026-10-10d): 서버가 `/api/fx/daily` 행마다 `change`(`comparedTo`·`absolute`·`percent`·`direction`, 비교할 행이 없으면 `null` — 키는 늘 있다)를
`Decimal`로 싣고 화면은 기호·색·부호만 입힌다(`DailyTable`·`csv`는 `noClientSideFinance` 대상). 비교 대상은 **바로 아래 행**이다 — 일 = 직전 고시일, 주·월 = 직전 대표값. 쪽의 마지막 행은
`daily_page`가 `hasMore` 판정에 **더 읽는 한 건**과 견준다 — 쪽 넘기기를 고칠 때 그 한 건을 버리면 경계 행이 "—"가 된다. 계산은 `simulation/fx_change.rate_change` 하나를 `/latest`와 함께
쓴다(같은 두 날이면 같은 글자). 비교 값이 0 이하면 표는 `percent: null`이고 `/latest`는 014 전처럼 `"0"`이다(응답 불변). CSV의 두 열은 **맨 끝**(004의 진행 중 뒤)이다 — 새 열을 더하면
그 뒤에 붙인다(앞에 끼우면 전에 받은 파일의 열 차례가 바뀐다). 화면 타입은 `DailyChange`(`percent`만 `null` 가능 — 요약의 `LatestChange`는 그대로)이고 `PeriodRow.change`는 선택 칸이다.

**주식·가상자산 일자별 표의 단위**(012): 표 경로 넷(일시금·적립식 × 주식·가상자산)이 `period=daily|weekly|monthly` 질의를 받는다(그 밖은 400 `invalid_query`).
화면은 `daily`이면 보내지 않는다(012 전 요청과 같다). 묶기는 순수 모듈 `simulation/period_table.py` 하나가 네 표에 함께 쓴다 — 외환의 `period_rows.py`는 고치지
않았다. 사건 행이 있는 날은 하루 묶음으로 쪽을 나눈다(한 날이 두 쪽에 갈리지 않는다). 원화 환산은 돌려주는 쪽의 행만 한다. **주식 차트는 표의 `daily`를 쓰지
않는다** — 시계열은 012 전처럼 `rows`(매달 첫 거래일·사건 날)에서 나온다. 보드·차트·이력 비교는 단위와 무관하다.
**처음 단위는 월이다**(014 반복 2026-10-11 — 외환·주식·가상자산 스토어와 비교 모달 `compareDetailStore`의 처음 값, 012의 처음 일을 대체). 서버의 기본은 그대로 일이라 화면의 첫 표 요청부터 `&period=monthly`가 붙는다 —
요청 글자를 정확히 견주는 화면 테스트는 처음 상태면 그 꼬리를 기대하고, 일 단위가 주제인 테스트는 스토어에 `tablePeriod: "daily"`(외환 `period`)를 심는다. 비교 모달은 열 때의 표 요청에도 단위를 싣는다(주식·가상자산만 —
예금·부동산 경로는 `period`를 모른다). 대시보드 지표 표(`indicatorTableStore`)는 처음 일 그대로다.

**블랙 배경(014 반복 2026-10-10c)은 색 변수 재정의다.** `app/globals.css`의 `.dark { --color-…: … }`(층 밖)가 Tailwind v4의 `@layer theme` 변수를 이겨 `<html class="dark">`일 때 팔레트가
바뀐다 — 컴포넌트 클래스는 그대로라 밝은 화면·014 전 화면 테스트가 바뀌지 않는다. **새 색 계열·단계를 쓰면 `.dark`에 짝을 더한다** — `tests/darkPaletteGuard.test.ts`가 src가 쓰는 색
유틸리티마다 재정의가 있는지, 글자·바탕 짝이 4.5:1 이상인지 본다(빠뜨리면 그 부품만 밝게 남아 글자가 묻힌다 — 전에 OS 다크 모드에서 그랬다). 테마는 `<html>`의 클래스이고 `app/layout.tsx`의
`<head>` 스크립트(`lib/themeScript`)가 그리기 전에 브라우저 저장소(`assetreplay.theme`)를 읽어 단다(`suppressHydrationWarning`). 상태는 `stores/themeStore`(저장소 실패에도 화면은 바뀜),
단추는 `components/shell/ThemeToggle`(서버는 늘 밝게 그리므로 `useSyncExternalStore`의 서버 값으로 붙고 곧바로 실제 테마로). **차트 다섯 종은 CSS 변수를 읽지 않는다** — `lib/chartTheme`의
`themedChartOptions`·`ink`(밝으면 받은 값 그대로)를 쓰고 테마를 효과 의존성에 넣어 **다시 만든다**(`applyOptions`는 005~013 차트 모의에 없다). 새 차트를 만들면 같은 두 함수를 쓴다.

## 6. 이력·투자 비교·상장일

**최근 시뮬레이션 이력은 로컬 DB다**(012): `simulation_history`(기본 키 `(asset_class, condition_key)`, 조건은 서버가 직렬화한 JSON 글 — 원금은 받은 글자
그대로, 서버가 그것으로 계산하지 않는다)·`history_setting`(단일 행, 행이 없으면 30일). 식별자는 서버(`api/services/history_conditions.py`)가 012 전 화면 lib와
글자까지 같은 규칙으로 계산한다. 경로는 `/api/history/{stock|crypto|deposit|realestate}`(GET·PUT·DELETE `?id=`·POST `/import`)와 `/api/history/settings` —
**설정 경로를 자산군 경로보다 먼저 등록한다**(뒤에 두면 `settings`가 자산군으로 잡혀 404). 기한 지난 항목은 읽고 쓸 때마다 먼저 지운다(보관 기간을 줄이면
곧바로 모든 자산군). 보관 기준은 마지막 실행 — 옮긴 항목은 옮긴 시각이다. 화면은 처음 열 때 그 자산군의 옛 브라우저 키를 옮기고 **옮기기가 2xx일 때만 키를
지운다**(읽을 수 없는 키는 옮기지도 지우지도 않는다). 네 스토어는 `lib/historyFlow.ts`를 함께 쓴다. 새 테이블이라 개발 DB에 `alembic upgrade head`가 필요하다.

**화면 테스트의 이력 대역**(012): `tests/setup.ts`가 `fetch`를 감싸 `/api/history` 요청에만 메모리 안 대역으로 답한다(도우미 `tests/support/historyStub.ts` —
`seed`·`entries`·`fail`·`calls`). 이력 클라이언트는 공통 요청 함수(`request`)를 직접 써서 `apiClient.get` 모의가 이력 요청을 가로채지 않는다. 이력이 주제가 아닌
테스트는 빈 이력과 성공하는 저장을 본다. 테스트마다 비운다.

**투자 비교의 비교 경로는 메뉴 경로의 짝이다**(013): `/api/comparison/{stocks,crypto,deposit,realestate}/simulation`·`stocks/recurring-simulation`·
`crypto/recurring-simulation`·`deposit/installment-simulation`(`api/routes/comparison.py`). 질의·검증·수집 판정·계산을 메뉴 경로와 **같은 함수를 같은 차례로** 부른다 —
같은 예외를 올려 202·거절 본문이 메뉴와 같고, 200은 메뉴의 요약 JSON·시계열 JSON(메뉴에서 꺼낸 `condition_json`·`series_json` 등 — 메뉴 응답은 바뀌지 않았다)에
`comparison` 블록(`api/services/comparison_metrics.py`)을 더한다. 대조는 `tests/integration/test_comparison_identity*.py`가 지킨다 — 메뉴 경로를 고치면 짝도 함께
본다. `maxPoints` 처음 값 1000, 부동산은 `buyPrice`를 받지 않는다(400 `invalid_query` — 매입가는 대상마다 그 달 시세). **비교 경로는 이력을 쓰지 않는다**(FR-020).
비용 몫은 `simulation/comparison_costs.py`(반영 몫·매도 가정 몫 — 메뉴가 비우는 항목은 0으로 메우지 않고 `blank`), 그 입력으로 정기예금 요약에 `accrued_tax`(기준일에
만기 전인 예금의 경과 이자 세금), 정기 적금 요약에 `open_tax`를 더했다(둘 다 끝 칸·기본값 0 — 기존 값 불변). 환율 찾기(`simulation/fx_convert.RateLookup`)는 이분
탐색이다(대상 10개 × 20년의 성능 — SC-004).
반복 2026-10-09의 단가 등락(`comparison.unitPrice`)은 비교 블록에만 있다 — 비교 경로가 지금 계산이 가진 값(주식 `closes`·`splits`·적립식 행 `close_price`, 가상자산
일봉 `open`, 예금 `rates`·`latest_month`, 부동산 `buy_price`·`value`)에서 고르고 차이·등락률은 순수 모듈이 낸다. 주식 기준 이름은 `split_restated_close`다 —
`split_adjusted_close`로 지었다가 005 가드(`test_no_adjusted_price` — 시뮬레이션 계층에서 `adjusted_close` 글자를 찾는다)에 걸렸다. 예금 기준일 달이 미발표면
마지막 발표 달의 금리를 그 달과 함께 잠정으로 낸다(계산이 쓴 그 금리 — 메뉴 차트처럼 그 달 금리로 내지 않는다).
반복 2026-10-09b의 **투자 시뮬레이션 모달**(`components/compare/SimulationModal.tsx`·`detail/*`, 상태 `stores/compareDetailStore.ts`)은 새 경로가 없다 — 그 줄을 낸 실행의
조건(`run.condition`)으로 **메뉴의 표 경로·`/series`**를 부른다(`lib/compareApi.menuPath` — 비교 경로에서 `/comparison`을 뺀 것). 메뉴가 쓰는 부품을 그대로 조립하고 메뉴
스토어를 쓰지 않는다(메뉴 입력·결과·이력 불변). 예금·가상자산 보드의 안내 줄은 메뉴 화면과 모달이 같은 함수(`lib/boardNotes`)로 만든다 — 메뉴 화면에서 안내 줄을 고치면
그 함수를 고친다. 202는 진행을 구독하지 않고 까닭과 다시 시도뿐이다. 닫으면 그 줄의 단추(`data-simulate-key`)로 포커스를 돌린다(연 순간의 포커스가 아니다 — Safari 등은
단추를 눌러도 포커스를 주지 않는다). 비교 표는 열이 열한 개라 마지막 열을 오른쪽에 붙였다(sticky) — 좁은 창에서 표는 가로로 스크롤되고 단추는 늘 보인다.

**저장한 비교**(013): `saved_comparison`(자동 증가 `id`, 저장할 때마다 새 행, **보관 기간 없음** — 012 이력 정리와 무관). 조건은 서버가 정해진 차례로 직렬화한 JSON 글이고
알려진 칸만 남는다(`api/services/comparison_conditions.py` — 금액은 받은 글자 그대로, 틀린 칸은 422 `invalid_comparison`이 칸을 밝힌다, 정기 적금은 시중은행·상호금융만).
서비스(`api/services/saved_comparison.py`)는 저장소를 `SavedComparisonRepository` Protocol로 받는다 — 경로가 `src.repository.saved_comparison` 모듈을 넘긴다. 저장 시각은
초 단위로 자른다(DB `DATETIME`의 반올림으로 응답의 `entry`와 목록이 1초 어긋나지 않게). **저장 라우터를 비교 라우터보다 먼저 등록한다**(012 `settings`와 같은 까닭).
새 테이블이라 개발 DB에 `alembic upgrade head`가 필요하다.

**비교 화면의 상태**(013, `stores/compareStore.ts`): 대상마다 비교 경로 하나를 부르고, 202면 그 자산군의 진행 스트림을 **대상마다** 구독해 끝나면 그 대상만 다시 요청한다
(연달아 202 세 번이면 수집 실패 — 환율 스트림이 곧바로 끝나는 되풀이를 막는다). 실행마다 차례 번호(`runSeq`)를 올려 늦은 응답·스트림 사건을 버린다. 흐림(`isStale`)은
결과를 낸 정규 조건과 지금 입력의 견주기다(파생 값 — 되돌리면 풀린다). 저장은 결과를 낸 조건을 보낸다(`saveBlockReason` — 흐림·막힘·결과 없음이면 막는다). 질의는
메뉴 스토어가 내보내는 질의 함수로 만든다. 부동산 고르기는 메뉴 스토어와 **같은 생성기**(`realEstateStateCreator`)의 두 번째 인스턴스(`stores/compareRealEstatePicker.ts`)다 —
비교 화면이 메뉴의 고른 단지를 바꾸지 않는다. 비교 표·막대는 값을 계산하지 않는다(정렬은 `lib/decimalOrder` 문자열 견주기, 막대 길이만 그리기 전용 `Number`).

**투자 비교의 대상 수**(014 반복 2026-10-13 — 013 FR-004의 10개를 대체): 더하기 한도는 **설정의 최대 대상 수**다(`comparison_setting` 단일 행 — 없으면 20, 정수 2~100,
`GET`·`PUT /api/comparison/settings` — 저장한 비교 라우터처럼 비교 라우터보다 먼저 등록). **서버 검증의 끝은 설정이 아니라 100**이다(`comparison_conditions.MAX_TARGETS`, 예금 5 —
설정의 위 끝도 이 상수) — 설정을 낮춰도 그보다 많은 저장한 비교를 불러오고·실행하고·다시 저장한다(화면은 자르지 않고 알린다 — `limitNotices`, 더하기만 막는다). 비교 화면은
**열 때마다** 설정을 읽고(`loadLimit` — 공통 `request`라 `apiClient.get` 모의가 가로채지 않는다, 화면 테스트는 `tests/setup.ts`의 설정 대역이 기본 20을 답한다), 읽지 못하면 20과
알림이다. 저장한 비교의 조건 글이 65,535바이트(UTF-8 — TEXT 열)를 넘으면 서비스가 422 `invalid_comparison`(칸 `condition`)으로 막는다 — 보내면 MySQL 엄격 모드가 500이다(열은
그대로 — 013 스키마 테스트). **요청은 한 번에 셋, 진행 구독은 둘, 확대 구간 요청은 셋**이다(`lib/concurrency` — 같은 주소 HTTP/1.1 연결 6개를 구독이 다 차지하면 화면이 오류 없이
멈춘다). 요청 차례는 모듈 하나를 실행 사이에 함께 쓴다(옛 실행의 기다리는 요청은 차례가 와도 보내지 않는다 — 화면을 떠나면 새 차례), 새 실행은 **기다리는 구독을 먼저 뺀 뒤**
열린 구독을 닫는다(닫을 때 비는 자리로 옛 구독이 열리지 않게). 늦게 연 진행 구독도 서버가 DB의 작업 상태로 완료를 보낸다. 수익률 추이는 선 모양 짝 20(`lineStyleOf` —
11~20번째는 모양을 뒤집음, 첫 10개 그대로)이고, 대상 11개 이상의 커서 상자는 커서 세로 자리에 가까운 10개다 — `priceToCoordinate`는 **커서 움직임에서만** 부른다(그릴 때 부르면 기존
차트 모의가 깨진다). 새 테이블이라 개발 DB에 `alembic upgrade head`가 필요하다.

**비교 화면의 대상 이름**(014 반복 2026-10-10e): 이름 자리(칩·표·막힘 안내·범례·커서 상자·막대·모달 머리·저장 목록·화면 읽기 이름)는 모두 `lib/compareCondition.targetName` 하나를
거친다 — 주식 `nameWithCode`(006 표시 코드)·코인 `coinNameWithSymbol`(`lib/displayCode` — 코인 검색 결과 줄의 맨 앞 이름도 이것). 새 이름 자리를 만들면 이 함수를 쓴다(따로 만들면 같은 대상이
두 이름이다). 이름은 저장하지 않는다 — 저장한 비교의 조건은 그대로이고 옛 저장도 티커가 붙는다. 막대 이름 칸(10rem)은 잘리므로 `title`에 전체 이름이 있다. 수익률 추이의 선·범례·커서 상자 색은
`colorOf(index, theme)` — 블랙이면 같은 색상의 400 계열이다(밝은 바탕용 600 계열은 어두운 바탕에서 글자 대비 3.72 — T154).

**비교 수익률 추이의 현재 가치 축**(014 반복 2026-10-11b): 비교 블록의 `valueLine`(`comparison_metrics.value_points` — 시계열 본문의 점마다 하나, 계산하지 않고 고른다)이 왼쪽 축을
그린다. 일시금 주식·가상자산은 점 `balance`가 보유분만의 원화 평가라 `api/services/comparison_values`가 그 계산의 행에서 원화 원금 + 투자 수익을 고른다(요약 `totalKrw`와 같은 식 —
기준일 점 = `currentValue` 글자). 나머지 다섯은 점 `balance` 그대로다. `lineEnd`에는 키를 더하지 않는다(그 객체를 통째로 견주는 013 단위 테스트). 화면 타입은 선택 키(`valueLine?`)라
키가 없는 014 전 픽스처는 왼쪽 축·가는 선이 없다. 매도 후 금액 점(`afterSaleValue`)이 있어야 두 축의 범위가 같은 비율이 되어 일시금의 두 선이 겹친다.

**주식·가상자산의 상장일**(014 반복 2026-10-10f): 기준을 함께 낸다(`simulation/listing_date` — `listing`·`first_trade`·`first_bar`). 주식은 키움 국내 상장일(`stock_listing.listed_on`) →
`stock.first_trade_date`(Yahoo `meta`의 첫 거래일 — **출처가 시세를 가진 첫 날**이라 국내는 2000-01-04, 일본은 1999-05-06부터다. 오래된 종목은 상장일보다 늦다 — T158) → 없음, 코인은 수집으로
알게 된 첫 일봉(`first_available_date`) → 없음. 모르면 비운다. `stock.first_trade_date`는 **표시 전용**이다 — 시작일 판정(`first_available_date`·목록 `listed_on`)에 쓰지 않는다(쓰면 메뉴의
시작일 거절이 바뀐다). 채우는 때는 셋이다 — 등록(`stock_selection.fill_first_trade_date` — lifespan이 연 공유 클라이언트(`set_shared_first_trade_source`)가 있을 때만, **한 번만 묻는다**(다시
시도하면 출처가 막혔을 때 고르기가 3초 늦었다 — T164), 시간 한도 `STOCK_FIRST_TRADE_TIMEOUT_MS`, 실패해도 등록 성공·응답 불변), `worker/stock_runner.collect_range`의 청크 응답(비었을 때만),
그리고 **상장일을 낼 때** — 투자 비교 블록과 메뉴의 고른 줄 경로(`GET /api/stocks/listing-date` — 반복 2026-10-10g)가 같은 함수 `stock_selection.stock_listing`을 부른다(키움 상장일이 없고 모를 때,
같은 규칙). 저장한 비교·이력 다시 실행은 등록을 거치지 않고 이미 받아 둔 종목은 새 청크도 없어서, 셋째가 없으면 미국 종목이 늘 "—"였다(사용자 보고 — TQQQ·QLD·SOXL). 의존성 `get_first_trade`는
서비스(`api/services/stock_selection`)에 있고 세 경로가 함께 쓴다.
lifespan 없이 도는 테스트는 클라이언트가 없어 출처를 부르지 않는다. **검색은 출처를 부르지 않는다** — 검색 응답 둘은 저장된 값만 `firstTradedOn`으로 싣는다(미국은 티커로 맞춘다). API 칸에 출처 칸
이름(`firstTradeDate`)을 쓰면 005 가드 `test_layer_boundaries`(`STOCK_SOURCE_TOKENS`)가 막는다. 화면 글자·설명은 `lib/listingDate` 하나(`components/ListingText`), 비교 표의 상장일 열은
`method`가 일시금·적립식일 때만이다(정렬은 날짜 글자, 비운 칸은 끝). 새 열이라 개발 DB에 `alembic upgrade head`가 필요하다.
(반복 2026-10-10g) 메뉴의 **고른 줄 밑 한 줄**(`ListingText.SelectedListingLine` — 훅 `hooks/useSelectedListing`)은 등록 응답이 아니라 **고른 대상으로** 묻는다(`lib/listingApi` — 이력 다시 실행은 등록이 없다).
검색 부품의 `listingRefresh`가 바뀌면 다시 묻는다 — 화면이 결과(`summary`·`recurring`)나 시작 가능 날짜 안내(`startable`)가 있으면 `"result"`를 넘긴다(실행의 수집이 첫 일봉을 알게 하고,
시작일이 첫 일봉보다 이르면 결과 대신 안내가 온다). 결과가 비는 것으로는 묻지 않는다. 요청은 공통 요청 함수를 직접 쓰고, 화면 테스트는 `tests/setup.ts`의 대역(`tests/support/listingStub.ts` —
`seedStock`·`seedCoin`·`fail`·`hold`·`release`·`calls`, 심지 않은 대상은 `listing: null`)이 답한다. 고른 줄이 있는 화면 테스트는 `상장일 —` 한 줄을 본다.

**화면 테스트의 저장 대역**(013): `tests/setup.ts`가 이력 대역 곁에 `/api/comparison/saved` 요청에도 메모리 안 대역으로 답한다(`tests/support/savedComparisonStub.ts` —
`seed`·`entries`·`fail`·`heal`·`calls`). 비교 화면은 열 때 저장 목록을 받는다 — 저장이 주제가 아닌 화면 테스트는 빈 목록과 성공하는 저장을 본다. 테스트마다 비운다.

## 7. 대시보드

**대시보드(014)는 조회 화면이다.** 지표 이력 수집은 lifespan의 **아홉째 태스크**(`worker/market_worker` — 다른 자산군과 따로 된 줄)다.
주식 수집과 같은 Yahoo 출처라 **관문(`ingestion/yahoo/gate.py`의 `YahooGate`)을 주식 클라이언트와 함께 지난다** — 동시 요청 수를 함께 지키고 429면
관문 전체가 물러선다. 시세 클라이언트 하나를 현재 시세 서비스와 수집 워커가 함께 쓰고 **lifespan이 연다·닫는다**(워커가 닫으면 카드가 함께 멈춘다).
심볼 ↔ 지표는 `ingestion/yahoo/market_symbols.py`에만 있다(엔은 ×100 — 고시 단위). 날짜는 **`zoneinfo`의 거래소 시간대**로 바꾼다(고정 오프셋이면
서머타임 여름 봉이 하루 당겨진다). 대시보드는 **ECOS를 부르지 않는다** — 환율 그래프는 외환 고시 이력을 읽고 모자라면 외환 수집 경로에 넘긴다.
**환율 그래프도 대시보드 진행 경로다**(`indicator_series.fx_state` — 반복 2026-10-10): 외환 진행 스트림은 사건 이름·모양이 달라 지표 화면이 읽지 못한다.
그 통화의 마지막 외환 수집 작업이 `failed`·`partial`이고 점유·큐가 없으면 202 `failed{kind: "fx_collection"}`이고 **외환 수집을 다시 요청하지 않는다**
(화면이 15초마다 다시 물어 인증 만료에 ECOS를 계속 불렀다) — [다시 시도](POST collect)만 요청한다. 외환 작업의 `finished_at`은 서버 지역 시각이라 UTC로 바꿔 낸다.
카드의 시장 환율은 **저장하지 않는다**(고시 `fx_rate`와 다른 계열). 출처 일봉의 빈 종가 행(휴일 자리 표시·늦은 확정)은 버리고 다음 현지 날짜의 겹쳐
받기에서 채운다(T062 — 니케이 10-09). 결측 가드(`test_no_interpolation`)가 src에서 `backfill`·"전일 값"·"이전 값" 같은 글자를 찾는다 — 과거 구간
수집은 "과거 구간"·"older"로, 전일은 "전일 종가"로 쓴다. 새 테이블 넷이라 개발 DB에 `alembic upgrade head`가 필요하다. 처음 기동의 과거 구간 수집은
12개 지표 254청크 약 8분이다(T062).

**지표 모달(014 반복 2026-10-10b)은 주소 있는 모달이다.** 카드 링크(대시보드 안 이동)는 `app/dashboard/@modal/(.)[indicator]`가 가로채고(닫기 = `router.back()`),
새로고침·직접 입력은 `app/dashboard/[indicator]/page.tsx`가 대시보드 + 같은 모달을 그린다(닫기 = `router.replace("/dashboard")`). 모달은 시세 갱신을
**멈추지 않는다** — 뒤의 대시보드가 진다(닫을 때 `stopPolling`을 부르면 대시보드 카드 갱신까지 멈춘다). 닫히면 포커스를 그 카드 링크(`data-indicator`)로
돌린다. 그래프 경로 `?range=`의 일봉 기간은 **기간 앞의 마지막 날부터만 읽는다**(T124 — 결측 판정이 지역적이라 같다, 동등성 테스트가 지킨다) — 1년에 S&P
2만 5천 점을 모두 읽으면 0.2초였다. 차트의 **막대 간격 하한은 0.01px**다 — 라이브러리 기본(0.5px)이면 `fitContent`가 끝 2천 점만 보여 "모두"가 2019년부터였다.
장중 축 눈금·커서 시각은 시장 현지 시각(`tickMarkFormatter`·`localization.timeFormatter` — `TickMarkType`은 값으로 견준다, 열거형을 실행 중에 쓰면 차트 모의가
깨진다). 장중 시세(`api/services/indicator_intraday`)·변화 까닭(`api/services/indicator_commentary`)은 **저장하지 않는다** — 장중 일 60초·주 300초, 까닭 600초,
실패는 각각 현재 시세(10초)·뉴스(60→600초)와 같다. 까닭은 문장을 만들지 않는다 — 출처 제목·요약 원문이고, Yahoo의 상대 표기("19h ago")는 서버가 고르기에
쓰려고 어림한 `publishedAt`보다 먼저 보인다. 일자별 표(`/table`)는 012 `table_rows`의 쪽 넘기기·행 꼴이고 202는 그래프와 같은 판정(`market_pending`·
`fx_pending`)이다 — 환율 표의 결측 행은 받은 고시 사이만이다(마지막 고시 뒤 꼬리는 아니다). `market_indicator_daily`의 시가·고가·저가는 새 열이라 개발 DB에
`alembic upgrade head`가 필요하고, 워커가 기동 때 한 번 원본에서 되살린다(`market_ohlc_restored` — 다시 띄우면 0행). 출처가 0을 주면 NULL이다(0으로 보이지 않는다).
(반복 2026-10-10c) 그래프의 일봉 기간은 **기간과 무관하게 일봉 전부**와 `windows`(기간 → 처음 보이는 시작일)를 싣는다 — 화면이 `setVisibleLogicalRange`로 처음 범위만 놓고
월~모두 전환은 다시 받지 않는다(T124의 "기간 앞부터만 읽기"는 그래프에서 빠졌다). 장중은 일 `range=5d&interval=5m`·주 `range=1mo&interval=30m`을 받고 `window`(마지막 세션·최근
5세션 — `simulation/intraday_window`, 거래일 규칙은 `trading_date`)로 처음 범위를 준다. **기간 단추는 `window.history.replaceState`로 주소만 바꾼다** — `router.replace`는 페이지 조각의
질의가 바뀌어 모달 내용을 통째로 다시 붙였다(그래프·표를 다시 받았다 — T137). 스토어는 받는 중인 같은 본문·표 첫 쪽을 나눈다(개발 모드 이중 효과로 1MB를 두 번 받아 모달 열기가 1초를
넘었다 — T138). **실행 중인 `next dev`에서 루트 배치 등을 고친 뒤 카드 누름이 하드 이동이면**(가로채기 요청 500 `Invalid interception route: …(.)(.)…`) 프론트엔드를 다시 띄운다(T137).

**대시보드 뉴스(014)는 저장하지 않는다.** `api/services/news_cache`가 칸마다 메모리에 성공 10분(`NEWS_CACHE_SECONDS`)·실패 60초부터 두 배씩 600초까지
(백오프) 둔다 — 기억이 남은 동안의 재요청은 출처를 부르지 않는다. 출처를 부를 때마다 `collection.log`에 `news_fetch` 한 줄이고(캐시 효과를 이 줄로 본다),
카드 출처 실패는 `market_quotes_failed`(응답 전체)·`market_quotes_partial`(일부 지표) 한 줄이다(성공은 남기지 않는다 — 30초마다). 사건 칸에 `message` 같은
`LogRecord` 예약 이름을 쓰면 로거가 예외를 낸다 — 문구는 `detail`이다(대역 `_event`로는 드러나지 않아 실제 로거를 부르는 테스트가 있다). 클라이언트(`ingestion/news/client.NewsClient`)는 lifespan에 하나이고 **수집
태스크가 없다**(요청 경로만). 브라우저형 사용자 에이전트(`NEWS_USER_AGENT`)가 없으면 Yahoo가 곧바로 429다. **Yahoo 화면의 응답 머리 한 줄이
약 19.5KB라** 세션을 머리 한도를 넓혀 연다(aiohttp 기본 8,190바이트면 본문 전에 400 오류 — T081). 파서는 표준 라이브러리뿐이다(`html.parser`·
`json.raw_decode` — 한 번 약 0.1~14ms, 실행기 불필요). 출처 화면이 바뀌어 0건이면 실패(`parse_empty`)다 — 픽스처(`tests/contract/fixtures/news/`)를
다시 받을 때 Yahoo JP 상태의 `pageInfo.jwtToken`을 지운다.

**기준금리(014 반복 2026-10-11d)는 결정 이력을 쌓는다.** 수집은 lifespan의 **열째 태스크**(`worker/policy_rate_worker` — 출처가 네이버라 지표 워커와 따로)이고 한 바퀴는
`worker/policy_rate_runner.run_round` — 목록 한 번 → 은행마다 결정 이력(처음은 짧은 쪽까지 전부, 그 뒤는 새 결정이나 그 한국 날짜에 아직 겹쳐 받지 않았을 때만 첫 쪽).
**칸·모달 경로는 DB만 읽는다**(`api/services/policy_rates` — 출처를 부르지 않는다, 화면은 1분·받는 중이면 5초). 결정일은 출처 시각(`localTradedAt`, 한국 시각)의
**한국 날짜**다 — 옛 행의 `23:59:59`는 자리 표시라 발표 시각을 비운다(꾸며 내지 않는다). **같은 날 두 행**(실측 여섯 날 — 모두 같은 값)은 같은 값이면 한 행(실제 시각 먼저),
다른 값이면 저장하지 않고 `policy_rate_conflict`다. 저장값과 다른 금리는 덮지 않고 `policy_rate_revised`(로그만 — 008 선례). 결정 이력 쪽 크기는 출처 상한 **60**이다(61이면 400).
목록이 실패한 뒤 다음 바퀴에서 할 일이 없는 은행도 **목록 성공으로 성공을 남긴다** — 남기지 않으면 "최근 갱신 실패"가 다음 날까지 남는다(T210 준비 중 찾음). 실패 칸은 성공이
지우지 않는다(화면이 시각을 견준다). 은행 표는 셋으로 나뉜다 — 이름·금리 종류·국기·차례 `simulation/policy_rate.BANKS`, 출처 국가 코드 `ingestion/naver_rate/banks.py`,
까닭 낱말 `ingestion/news/commentary.BANK_WORDS`. **변화 까닭**(`api/services/policy_rate_commentary`)은 최근 결정일과 다음 날의 뉴스 포커스(404 → 403 → 429)에서 **은행 낱말과
금리 낱말이 둘 다** 든 제목, 게시 시각이 **발표 시각 30분 전 이후**(출처의 발표 시각은 어림 — 한은 10:00인데 결정 기사 09:52, T202)인 것만 3개다 — 지표의 "마지막 세션 이후" 규칙을 쓰면
결정 뒤 며칠이면 늘 "찾지 못함"이다. 같은 (분류, 날짜)는 은행 사이에 한 번 받는다. 금리 모달은 지표 모달의 껍데기(`IndicatorModal` — id가 은행이면 `RateView`)이고 닫으면 칸의 그
행(`data-rate`)으로 포커스가 돌아온다. 그래프(`RateChart`)는 **계단선**(`lineType: 1` — 열거형을 가져오지 않는다)·결정 점이고 기간 넷(1년·5년·10년·모두)은 마지막 결정에서 거꾸로 센
처음 범위다. 새 테이블 셋이라 개발 DB에 `alembic upgrade head`가 필요하다. 처음 기동의 결정 이력은 목록 1 + 결정 이력 10회다(쪽 사이 1초).
