# Bug Fix: 정수가 아닌 분할 비율(0.985:1)이 오면 그 종목의 시세 수집이 매번 실패한다

- **Slug**: fractional-split-ratio
- **Fixed**: 2026-10-03
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

분할 비율을 "양의 정수만"이 아니라 **정확한 기약 정수 쌍**으로 받게 바꿨다(`0.985:1` → `197:200`). 원주가 되살리기와
보유 주식 수 적용(005 FR-010·FR-010a)은 바꾸지 않아도 그대로 동작하며, 삼성물산을 2020-01-01부터 실제 출처로 실행해
결과까지 가는 것을 확인했다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `backend/src/ingestion/yahoo/parse.py` | modified | `_split_ratio_part`(양의 정수만) → `_ratio_part`(양의 유한한 `Fraction`)·`_split_ratio`(분자 ÷ 분모를 기약 정수 쌍으로, `INT` 초과 거절). `_split_events`가 쓴다 |
| `backend/tests/contract/test_stock_source_parse.py` | modified test | 기존 "정수가 아닌 비율은 거절"을 "쓸 수 없는 비율은 거절"로 좁힘, `Test분수_비율` 추가 |
| `backend/tests/contract/fixtures/stock/chart_split_fractional.json` | added | 삼성물산 실제 응답(2026-10-03 받음, 2020-01-01~2021-12-30) |
| `backend/tests/unit/test_money.py` | added test | 100주 × 197/200 → 98주 |
| `specs/006-stock-simulation-enhancements/spec.md`·`research.md`·`plan.md`·`tasks.md`·`quickstart.md` | modified | FR-034 비율 규칙, R6-18, 구조·Complexity, T120·T121, 실행 기록 결함 7 |

## Diff Highlights (optional)

```python
def _split_ratio(numerator: object, denominator: object) -> tuple[int, int]:
    ratio = _ratio_part(numerator) / _ratio_part(denominator)   # Fraction — 정확하다
    if ratio.numerator > _RATIO_MAX or ratio.denominator > _RATIO_MAX:
        raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")
    return ratio.numerator, ratio.denominator
```

## Tests Added or Updated

- `test_stock_source_parse.py::Test분수_비율::test_실제_응답의_분수_비율을_기약_정수_쌍으로_읽는다` — 실제 응답의 분할이 `(2020-05-13, 197, 200)`
- `test_stock_source_parse.py::Test분수_비율::test_되살린_원주가가_실제_호가와_같다` — 2020-05-08 `104499.996680`·2020-05-12 `101999.997422`(계산값과 정확히 같고 실제 호가와 0.01원 이내), 이벤트 날부터는 그대로
- `test_stock_source_parse.py::Test분수_비율::test_비율을_반올림하지_않고_기약_정수_쌍으로` — `5:1`, `2.5:1→5:2`, `1.5:1→3:2`, `1:10`, `0.985:1→197:200`, `4:2→2:1`
- `test_stock_source_parse.py::Test실수로_온_분할_비율::test_쓸_수_없는_비율은_거절한다` — 0·음수·NaN·문자열·`INT`를 넘는 기약 분수(`1.0526315789:1`)
- `test_money.py::Test분할_반영::test_분수_비율도_정수로_떨어지지_않는_몫은_버린다` — 100주 × 197/200 → 98주

## Local Verification

- Commands run:
  - 테스트 커밋(`d28e24e`) 시점 → 6 실패 / 54 통과(분수 비율 거절 5건, 4:2 미약분 1건)
  - 구현 뒤 `pytest tests/contract/test_stock_source_parse.py tests/contract/test_yahoo_client.py tests/unit/test_money.py`
    → 1 실패 / 65 통과 — 되살린 값이 `104499.996680`으로 기대 `104500.000000`과 달랐다(아래 평가와 달라진 점). **멈추고
    보고한 뒤 사용자 승인으로 테스트 기대를 고쳤다**(plan Complexity Tracking D2) → 66 통과
  - `pytest -q --cov=src` → 1333 통과, 커버리지 95%
  - `mypy src` → 오류 없음, `ruff check src tests` → 통과
- Manual checks (실제 출처, 개발 서버 8080):
  - 삼성물산 2020-01-01·원화 1,000만 원 실행 → 202 → 작업 129 `SUCCEEDED` 4/4(11:31:41~49) → 200
  - `stock_split`: `(2020-05-13, 197, 200)`. `stock_price` 시가: 2020-05-08 `104499.996680`, 2020-05-12 `101999.997422`,
    2020-05-13 `98000.000000`
  - 표: 2020-01-02 시가 108,999.999961원에 91주, 2020-06-01에 89주(이벤트 날 91 × 197/200 = 89.6 → 89), 수익률 239.87%

## Deviations from Assessment

- **"정확히 호가 단위가 된다"는 평가의 근거가 과장이었다.** 출처의 값은 단정밀도라(2020-05-08 `106091.3671875`, 실제
  104500 ÷ 0.985 = 106091.370558…) 197/200을 곱하면 `104499.99668`이 된다 — 실제 호가와 0.004원 이내로 같지만 정확히
  같지는 않다. 구현은 평가대로이고(반올림하지 않는다, research R6-18), 테스트 기대를 "계산값과 정확히 같고 실제 값과
  0.01원 이내"로 바꿨다(애플 테스트와 같은 방식). 사용자 승인 2026-10-03

## Follow-ups

- 2020-05-13 삼성물산 0.985:1 이벤트의 실제 성격(주주의 주식 수 변동 여부)은 여전히 확인하지 않았다. 005 FR-010a대로
  출처를 그대로 적용해 보유 주식이 이벤트 날 약 1.5% 줄어든다. 자사주 소각처럼 주주에게 영향이 없는 사건이었다면 그
  날짜를 걸치는 결과가 그만큼 낮게 나온다 — `stock_split`의 기록(197/200)이 되짚을 수단이다
- 정수가 아닌 비율이 오는 다른 국내 종목(무상증자 등)이 얼마나 되는지는 보지 않았다
- `/speckit-bug-test slug=fractional-split-ratio`로 검증 보고를 남긴다
