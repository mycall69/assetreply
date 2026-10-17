# Bug Verification: 시세 출처가 아직 확정하지 않은 마지막 봉(시가 0·장중 값)을 일봉으로 저장하고 다시 받지 않는다

- **Slug**: stock-provisional-bar
- **Tested**: 2026-10-13 (실측) · 2026-10-17 (게이트 다시 실행·재확인)
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

보고된 증상은 더는 재현되지 않는다. 삼성전자 2026-10-06은 시가 278,500·종가 272,000으로 저장되어 있고, 표의 등락이 바르다. 같은 원인의 NVDA
2026-10-08도 확정 종가 230.48로 바로잡혔다. 미국 장중 실측에서는 오늘 봉이 저장되지 않았고 커버리지도 그날 앞에서 멈췄으며, 202가
되풀이되지 않았다. 전체 회귀에서 깨진 테스트는 없다.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| 재현(수정 뒤) — 저장값 | 원본 응답 다시 읽기 점검 → 두 행 삭제·커버리지 축소 → 개발 서버 평소 조회(202 → 200) | pass | 삼성전자 10-06 278,500/272,000, NVDA 10-08 234.92/230.48. 다시 점검: 잠정 행 0, 0 이하 가격 행 0 |
| 재현(수정 뒤) — 표 등락 | `GET /api/stocks/simulation`(일) · 헤드리스 Chrome 1440px(이력 다시 실행 → 일) | pass | 10-06 시작가 ▲5,000 +1.83%, 10-07 ▼9,000 −3.23%. 첫 쪽 30행이 API와 글자 차이 0(삼성전자·NVDA) |
| 재현(수정 뒤) — 미국 장중 | 2026-10-13 22:36 KST 어댑터 직접 호출 · 개발 서버 `end=2026-10-13` | pass | 어댑터: 행 없음, 잠정 10-13. 서버: 주식 새 작업 없음, 커버리지 10-12, 10-13 행 없음 |
| 새 테스트 | `pytest tests/contract/test_stock_provisional_bar.py tests/unit/test_session_finished.py tests/integration/test_stock_provisional_collection.py` | pass | 16 + 13 + 10 |
| 회귀 전체 | `pytest -q --cov=src`(서버 내림) | pass | 3,734 passed, 커버리지 96.66% |
| 타입·린트 | `mypy src` · `ruff check --no-cache src tests` | pass | 297 파일 |
| 프론트엔드 | — | skipped | 화면 코드를 바꾸지 않았다. 화면은 실측(위)으로 확인했다 |
| 재확인(2026-10-17) | 서버 다시 띄운 뒤 `GET /api/stocks/simulation?…005930.KS…&end=2026-10-08` | pass | 10-06 278,500/272,000 · 시작가 등락 +5,000(+1.83%) |

## Output Excerpts

```
samsung statuses [202, 200] asOf 2026-10-08 isFinal True
   2026-10-06 period open 278500.000000 close 272000.000000 openChange {"comparedTo": "2026-10-02", "absolute": "5000.000000", "percent": "1.83", "direction": "up", …}
nvda statuses [202, 200] asOf 2026-10-12 isFinal True
   2026-10-08 period open 234.919998 close 230.479996 …
(1) adapter prices [] provisional_from 2026-10-13          # 22:36 KST, 미국 장중
3734 passed in 677.45s (0:11:17)
```

## Residual Risks

- **미국 종목의 마감 뒤 봉 시가**: 마감 직후 받은 마지막 거래 시각 봉은 확정으로 둔다. 실측 7종목 가운데 4종목은 시가가 출처 확정값과 몇 센트
  다르다(fix.md Follow-ups)
- **출처의 `null` 봉**: 출처가 삼성전자·SK하이닉스 2026-10-12(월) 일봉을 모든 값 `null`로 준다. 같은 날 KOSPI 지수는 값이 있다. 이 봉은
  출처 결측으로 받은 구간에 들어가 다시 받지 않는다. 이 결함과 다른 문제다(fix.md Follow-ups)
- **`end`를 오늘로 준 해외 종목 조회**: 환율 수집이 어제까지라 환율 쪽 202가 이어진다. 이번 변경 전부터 있던 동작이고, 기본 계산 끝에서는
  생기지 않는다
- **장중 실측의 되풀이 막기**: 서버 경로의 200은 환율 쪽 202에 가려 직접 보지 못했다. 주식 쪽에 새 작업이 없었던 것으로 확인했고, 200 응답은
  통합 테스트(`Test되풀이_막기`)가 덮는다
- 실측 스크립트는 저장소 밖(세션 임시 폴더)에 두었고, 결과는 fix.md에 적었다

## Recommendation

결함을 닫는다. 보고된 증상과 같은 원인의 두 번째 사례를 실데이터로 확인했다. 남은 두 관찰(미국 마감 뒤 봉 시가, 출처의 `null` 봉)은 따로 판단할
문제로 넘긴다.
