# 대시보드 지표 출처 픽스처 (014 T005)

Yahoo 비공식 차트·spark 엔드포인트의 **응답 본문만** 담는다. 주소·응답 머리는 담지 않는다. 2026-10-09 실측 원본을 구간만 잘라 줄였다 — JSON 구조는 그대로다.

| 파일 | 요청 | 담긴 상황 |
|------|------|-----------|
| `spark_15.json` | `/v7/finance/spark?symbols=15개&range=1d&interval=1d` | 15개 심볼의 `meta`(현재 값·`fulldayChange`·`chartPreviousClose`·`currentTradingPeriod`) — 2026-10-09 13:21 UTC(한글날, 미국 장 전) |
| `spark_missing_shanghai.json` | 같다 | 위에서 `000001.SS` 한 심볼을 지운 사본 — 빠진 심볼만 차트로 다시 부르는지 |
| `quote_KS11.json` | `/v8/finance/chart/^KS11?range=1d&interval=1d` | 한국 휴장(한글날) — `regular`가 지난 거래일(10-08) 세션 |
| `quote_N225.json` · `quote_GSPC.json` · `quote_CL_F.json` · `quote_KRW_X.json` | 같은 꼴 | 니케이 장 마감 뒤, 미국 장 전, 선물·외환(세션 00:00–23:59) |
| `quote_000001.SS.json` | 같은 꼴 | `chartPreviousClose = 0.0002050505`(깨진 전일), `fulldayChange`로 역산하면 맞다 |
| `chart_KS11_2024_2025.json` | `interval=1d&period1&period2`(2년 청크) | 일봉 청크 하나 |
| `chart_KS11_1996.json` | `period1=0` 원본을 1996-12~1997-12로 자름 | 종가 `null` 행(휴일 자리 표시 — 1996-12-25 등 21행), `firstTradeDate` 1996-12-11 |
| `chart_CL_F_2020.json` | `period1=0` 원본을 2020-01~2021-03으로 자름 | 선물 근월물, 일봉 시각이 뉴욕 0시, 2020-04-20 종가 −37.63 |
| `chart_CL_F_2020_winter_fetch.json` | 위 사본 | `meta.gmtoffset`을 겨울(−18000)로 바꿨다 — 고정 오프셋으로 날짜를 바꾸면 여름 행이 하루 앞당겨진다(R14-3) |
| `chart_GSPC_1927.json` | `period1=-2208988800` 원본을 1927-12~1929-12로 자름 | 1970년 이전 — 음수 epoch, `firstTradeDate` 1927-12-30 |
| `chart_GSPC_open_today.json` | `range=5d&interval=1d` | 개장 3분 뒤 — 오늘(현지 10-09) 부분 봉 |
| `rate_limited.txt` | 브라우저형 UA 없이 | 429 본문(23바이트) |

**반복 2026-10-10b(T095 — 2026-10-10 03시 KST 토요일 실측)** — 장중 질의(`range=1d&interval=5m`·`range=5d&interval=30m`), 응답 본문만:

| 파일 | 요청 | 담긴 상황 |
|------|------|-----------|
| `intraday_GSPC_1d_5m.json` | `^GSPC` 1일 5분 | 79점 — 10-09(뉴욕 금요일) 13:30~20:00 UTC, 빈 점 없음. `meta.regularMarketDayHigh/Low`는 있고 시가는 없다 |
| `intraday_GSPC_5d_30m.json` | `^GSPC` 5일 30분 | 66점 — 10-05~10-09 |
| `intraday_KRW_X_5d_30m.json` | `KRW=X` 5일 30분 | 240점 중 빈 종가 24 — 건너뛴다 |
| `intraday_JPYKRW_X_1d_5m.json` | `JPYKRW=X` 1일 5분 | 288점 중 빈 종가 114, 1엔당 값(×100은 어댑터) |
