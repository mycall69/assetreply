# 주식 시세 출처(Yahoo) 픽스처

본문만 저장한다 — 요청 주소·머리·쿠키는 남기지 않는다(헌법 원칙 II).

## 차트 meta (014 반복 2026-10-10f — T158)

`/v8/finance/chart/{심볼}?range=1d&interval=1d` 응답 본문. 2026-10-10 21:28 KST에 받았다. 상장일 표시(FR-033)가 쓰는 칸은
`chart.result[0].meta.firstTradeDate`(초)와 `exchangeTimezoneName`이다.

| 파일 | 심볼 | `firstTradeDate` | 거래소 시간대 날짜 | 비고 |
|------|------|------------------|--------------------|------|
| `chart_meta_VOO.json` | VOO | 1284039000 | 2010-09-09 (America/New_York) | 실제 첫 거래일과 같다 |
| `chart_meta_005930_KS.json` | 005930.KS | 946944000 | 2000-01-04 (Asia/Seoul) | 출처의 국내 시세 시작일 — 키움 상장일(1975-06-11)이 먼저다 |
| `chart_meta_7203_T.json` | 7203.T | 925948800 | 1999-05-06 (Asia/Tokyo) | 출처의 일본 시세 시작일 — 상장일이 아니다 |

다른 파일(`chart_*`·`splits_*`·`search_*`)은 005·006에서 받은 것이다. `chart_full.json`의 `firstTradeDate`(1975)는 옛 응답이다.

## 마지막 거래 시각 봉 (버그 stock-provisional-bar)

`/v8/finance/chart/{심볼}?interval=1d&events=div,splits` 청크 응답 본문 — 개발 DB `stock_raw_response`에 보관한 원본 그대로다. 출처가 그날을
아직 일봉으로 굳히지 않으면 봉의 시각이 `meta.regularMarketTime`(마지막 거래 시각)이다. 확정 일봉은 개장 시각(KRX 09:00 KST, 미국 09:30
EDT)이다.

| 파일 | 원본 id | 요청 | 받은 시각(KST) | 봉 |
|------|---------|------|----------------|----|
| `chart_live_zero_005930_KS.json` | 524 | 2026-10-06 | 2026-10-07 03:21:55 | 10-06 15:30:02 — 시가·고가·저가·거래량 0, 종가 272,000. 출처의 확정 봉은 시가 278,500(2026-10-13 실측) |
| `chart_live_intraday_NVDA.json` | 640 | 2026-10-08 | 2026-10-09 00:23:41 | 10-08 11:23:41 EDT(장중) — 종가 자리가 그때의 현재가 236.08. 확정 종가 230.48 |
| `chart_live_after_close_005930_KS.json` | 612 | 2026-10-08 | 2026-10-09 00:19:15 | 10-08 15:32:40 KST(마감 뒤) — 시가 269,500·종가 262,000. 확정 봉과 같다 |
