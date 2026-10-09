# 대시보드 뉴스 출처 픽스처 (014 T063)

뉴스 세 칸(R14-13)의 **응답 본문만** 담는다. 주소·응답 머리·쿠키는 담지 않는다. 2026-10-09 22:2x KST 실측 원본을 줄였다 —
파서가 보는 구조(JSON 키, `data-testid`·`class` 선택자, `window.__PRELOADED_STATE__` 줄)는 그대로다.

| 파일 | 요청 | 담긴 상황 |
|------|------|-----------|
| `naver_mainnews.json` | `stock.naver.com/api/domestic/news/list?category=MAINNEWS&page=1&pageSize=20` | 주요뉴스 20개 가운데 위 15개. **같은 제목이 다른 기사 번호로 두 번**(MBN 0001972681·0001972673 — 2·4번째 차례) |
| `naver_no_articles.json` | 가공 | `articles` 키가 없는 본문 — 구조가 바뀐 신호(`parse_empty`) |
| `yahoo_us_latest.html` | `finance.yahoo.com/topic/latest-news/`(브라우저형 UA) | `div[data-testid=topic-stream]` 부분만 남겼다 — 스트림 카드 25개, 광고 칸(`ad-container`) 6개, 카드마다 종목 링크(`/quote/…` 상대 주소, `title` 있음). 추적 속성(`data-yga`·`data-ylk`)·이미지 주소·SVG 경로는 지웠다 |
| `yahoo_us_latest_noua.html` | 같은 주소(aiohttp 기본 UA) | 429 본문 `Edge: Too Many Requests`(23바이트) |
| `yahoo_us_link_variants.html` | 가공(위 사본) | 앞 카드 넷의 기사 주소를 바꿨다 — 상대 주소 `/news/…`, `javascript:void(0)`, 다른 도메인 `https://example.com/…`, `http://finance.yahoo.com/…` |
| `yahoo_us_no_stream.html` | 가공(위 사본) | `topic-stream`·`stream-card` 표지를 다른 이름으로 바꿨다 — 목록 칸이 없는 화면(`parse_empty`) |
| `yahoo_jp_headline.html` | `finance.yahoo.co.jp/news/headline` | 상태 줄만 남겼다 — `mainNewsCategory`(ヘッドライン 20개, 시각 `"22:20"` 꼴, 유료 0개)·`pageInfo`(`currentDateTime` 1791552564857 = 2026-10-09 22:29 JST)·`subNewsHeadline`(빈 곁 목록). **`pageInfo.jwtToken`·`loginUrl`은 지웠다** |
| `yahoo_jp_headline_p12.html` | 같은 주소 `?page=12` | 오늘 시각(`"5:12"` — 앞 0 없음)과 지난 날(`"10/8"`)이 섞인 쪽 |
| `yahoo_jp_no_state.html` | 가공(`yahoo_jp_headline.html` 사본) | 상태 키 이름을 바꿨다 — 상태 키가 없는 화면(`parse_empty`) |

- 유료 기사(`isPaidArticle: true`)·1월 기준의 `"12/30"`·다른 도메인 링크는 실측 본문에 없다 — 계약 테스트가 위 본문의 상태 JSON을 고쳐 만든다.
- 다시 받을 때는 같은 방식으로 줄이고 이 표의 날짜·상황을 고친다. 주소에 키가 없는 출처지만 주소는 담지 않는다(다른 픽스처와 같은 규칙).
