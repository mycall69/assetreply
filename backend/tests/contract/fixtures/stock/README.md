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
