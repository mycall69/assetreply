# 가상자산 출처(investing.com) 실제 응답 픽스처 — 007 T001

받은 때: **2026-10-03 11:00~11:03Z**(UTC). aiohttp, 브라우저형 사용자 에이전트(Chrome 154 문자열), 요청 사이 1.5초. 스크립트는 저장소에 넣지
않았다(일회성 — tasks T001). **실제 응답 그대로**다. `coins_all_compact.json`만 파생 픽스처다.

| 파일 | 요청 | 내용 |
|------|------|------|
| `coins_en_p1.json` | `GET https://endpoints.investing.com/pd-instruments/v1/crypto/coins?sort=rank&order=asc&limit=100&domain_id=1` | 영문 판 첫 쪽 100개, `next_page_cursor` 있음 |
| `coins_en_last.json` | 위 + `&cursor=…`(37번째 쪽) | 영문 판 마지막 쪽 54개, `next_page_cursor: null` |
| `coins_ko_p1.json` | 위 + `domain_id=18` | 한국어 판 첫 쪽 — 같은 `instrument_id`, 이름 일부만 한글 |
| `coins_all_compact.json` | 영문·한국어 각 37쪽(74요청)에서 **뽑은 파생 픽스처** | 3,654개 × `instrument_id`·`name`·`symbol`·`rank`·`slug`·`name_ko`(한국어 판 이름이 영문과 다르고 한글을 포함할 때만 — 12개). 검색 순위 측정용(SC-002, analyze M1) |
| `btc_2020_2021.json` | `GET https://api.investing.com/api/financialdata/historical/1057391?start-date=2020-01-01&end-date=2021-12-31&time-frame=Daily&add-missing-rows=false`, 헤더 `domain-id: www` | BTC 731행(빠진 날 없음) |
| `btc_recent.json` | 같은 일봉 API, 2026-09-13 ~ 2026-10-03 | BTC 21행 — **마감 전인 2026-10-03(UTC 오늘) 일봉 포함** |
| `btc_2011_06.json` | 2011-06-01 ~ 2011-07-31 | BTC 61행 — **거래량 빈 값 6일**(`volume: ""`, `volumeRaw: 0`, 2011-06-20 ~ 06-25) |
| `eth_first.json` | ETH(1061443) 2015-06-01 ~ 2017-05-31 | 448행 — 요청 시작보다 늦은 **첫 일봉 2016-03-10**, 거래량 빈 값 7일 |
| `shib_recent.json` | SHIB(1177506) 2026-09-13 ~ 2026-10-03 | 21행 — 아주 작은 가격(`0.0000057…`), 큰 거래량(`2,623.71B`) |
| `leash_empty.json` | Doge Killer(LEASH, 1230723) 2026-09-13 ~ 2026-10-03 | **일봉 없음 — `"data": null`**(빈 배열이 아니다) |
| `blocked_403.txt` | `btc` 일봉 API를 **기본 사용자 에이전트·`domain-id` 없이** | 403, 본문 `403`(차단) |

원본 요청 기록(시각·상태·URL)은 위 표로 줄였다. 형식이 바뀌어 다시 받으면 이 표의 날짜와 내용을 고친다.
