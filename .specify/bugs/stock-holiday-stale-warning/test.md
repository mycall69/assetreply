# Bug Verification: 계산 끝(어제)이 휴장일이면 주식 보드·표에 "시세가 없습니다" 경고가 잘못 뜬다

- **Slug**: stock-holiday-stale-warning
- **Tested**: 2026-10-06
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

평가의 재현 조건(2026-10-06, 계산 끝 10-05 = 개천절 대체공휴일, 삼성전자)에서 증상이 더는 나오지 않는다. API의 `isFinal`이 `true`이고, 브라우저의
보드·표에 "이후 시세가 없습니다" 경고가 없다. 시세 단절(`test_delisted.py`)은 여전히 경고 대상이다. 백엔드·프론트엔드 전체 스위트와 타입·린트에
회귀가 없다.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction — API (post-fix) | `GET /api/stocks/simulation?market=KRX&symbol=005930.KS&start=2026-09-01&…`(개발 서버, 수정 반영 뒤 재기동) | pass | `asOf 2026-10-02`, `isFinal true`(수정 전 `false`) |
| Reproduction — 차트와 보드의 판정 일치 | 같은 조건의 `/series` | pass | 마지막 결측 구간 10-03~10-05가 `no_quote`(휴장)다. 이제 보드도 최종이라 둘이 어긋나지 않는다 |
| Reproduction — 대조 | AAPL(NASDAQ) 같은 조건 | pass | `asOf 2026-10-05`, `isFinal true` — 그대로 |
| Reproduction — 브라우저(1440px) | `/stocks`에서 이력의 삼성전자 일시금·적립식(매주) 항목을 다시 실행(CDP) | pass | 두 결과 모두 "이후 시세가 없습니다" 문구 0건이다. 표 위 경고(`table-asof`)가 없고, 보드 기준 줄은 "2026-10-02 기준"이다 |
| New / updated tests | `pytest tests/unit/test_quote_finality.py tests/integration/test_stock_holiday_asof.py tests/integration/test_delisted.py` | pass | 21 passed — 시세 단절 기존 테스트 포함 |
| Regression suite — 백엔드 | `pytest -q --cov=src`(서버를 내린 채) | pass | 2,663 passed, 커버리지 96.25%, 종료 코드 0 |
| Regression suite — 프론트엔드 | `npm test` | pass | 155 파일 / 1,302 passed, 종료 코드 0(화면 코드는 바뀌지 않았다) |
| Lint / type-check | `mypy src` · `ruff check --no-cache src tests` · `npx tsc --noEmit` · `npx eslint .` | pass | mypy 222 파일 문제 없음, ruff 통과, tsc·eslint 종료 코드 0 |

## Output Excerpts

```
KRX lump 2026-10-02 True
series tail gap {'from': '2026-10-03', 'to': '2026-10-05', 'reason': 'no_quote'}
AAPL lump 2026-10-05 True

lump      {"warning": [], "tableAsof": null, "mode": ["일시금"], "board": ["2026-10-02 기준 · KRW 기준 · …"]}
recurring {"warning": [], "tableAsof": null, "mode": ["적립식"], "basis": "2026-10-02 기준 · KRW 기준 · …"}

tests/unit/test_quote_finality.py, tests/integration/test_stock_holiday_asof.py, tests/integration/test_delisted.py — 21 passed
Required test coverage of 80% reached. Total coverage: 96.25%
2663 passed in 510.70s (0:08:30)
Test Files  155 passed (155) / Tests  1302 passed (1302)
```

## Residual Risks

- **주말 경우는 실제 날짜로 재현하지 않았다.** 평가가 예측한 "일요일·월요일 아침에도 뜬다"는 통합 테스트(`test_계산_끝이_주말이면_최종이다` —
  `end` = 일요일)와 단위 테스트로만 확인했다. 실제 주말의 개발 서버에서는 보지 않았다.
- **비교 종목이 적은 시장**: 같은 시장의 다른 종목이 그 뒤 거래 증거를 주지 못하면 평일 허용치(기본 7)로 가른다. 개발 DB의 TSE(1종목)처럼 종목이 적은
  시장에서는 상장폐지를 그 기간만큼 늦게 알린다(fix.md Follow-ups).
- **허용치 기본값 7**은 평가의 제안값이다. 실제 최장 거래소 연휴는 확인하지 않았다(평가 Open Question).
- 평가의 다른 Open Questions(장 마감 뒤 오늘 포함, 표의 기준일 행)는 이 수정의 범위 밖이고 여전히 열려 있다. 사용자가 본 "10월 1일 기준"처럼
  보이는 표의 맨 위 행(그 달 첫 거래일)은 그대로다.

## Recommendation

**버그를 닫는다 — 끝에서 끝까지 확인했다.** 원래 재현 조건(API·브라우저)에서 증상이 사라졌다. 시세 단절 경고는 유지되고, 전체 스위트에 회귀가
없다. 남은 것은 평가의 Open Questions 세 가지(장 마감 뒤 오늘 포함, 표의 기준일 행, 허용치 기본값)에 대한 결정이다. 이 버그와 따로 다룬다.
