# Bug Fix: 시세 출처가 아직 확정하지 않은 마지막 봉(시가 0·장중 값)을 일봉으로 저장하고 다시 받지 않는다

- **Slug**: stock-provisional-bar
- **Fixed**: 2026-10-13
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

주식 어댑터가 출처의 잠정 봉을 확정 일봉에서 가른다. 잠정은 세 가지다.
- 그 거래일의 정규 세션이 아직 끝나지 않았을 때 받은 봉
- 마지막 거래 시각 봉인데 시가·종가가 0 이하인 봉
- 봉이 없어도, 요청 끝까지에 세션이 아직 끝나지 않은 날(장 전에는 출처가 그날 봉을 주지 않는다 — 실측에서 찾았다)

잠정 봉은 행을 만들지 않고, 수집은 그 첫 날부터를 받은 구간에 넣지 않아 다음 수집이 다시 받는다. 곧바로 다시 받아 202가 되풀이되는 일은
조회 쪽에서 막는다. 마지막 작업이 그 구간을 요청했고 성공했으면 설정한 시간(기본 30분) 동안 받아 둔 날까지로 답한다. 개발 DB에
잘못 저장된 두 행(삼성전자 2026-10-06, NVDA 2026-10-08)은 지우고 커버리지를 줄였다. 그 뒤 평소 수집 경로로 다시 받았다.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `backend/src/simulation/market_session.py` | modified | `session_finished(key, day, now)` — 순수 함수. 지난 거래일이면 끝났고, 오늘이면 시간표상 마감 뒤만 끝났다 |
| `backend/src/ingestion/yahoo/parse.py` | modified | `parse_chart(body, *, now=None, requested_to=None)` — 잠정 봉·빈 봉(확정 자리의 0 이하 가격)은 행이 없다. 요청 끝까지의 세션이 안 끝난 첫 날도 잠정. `ChartData.provisional_from`(마지막 칸, 기본 `None`). 시장 → 시간표 키 `_SESSION_KEYS` |
| `backend/src/ingestion/yahoo/client.py` | modified | `fetch_chart`가 지금 시각(분할 기록 요청과 같은 시각)과 요청 끝을 해석에 넘긴다 |
| `backend/src/worker/stock_runner.py` | modified | 잠정 날이 있으면 커버리지를 그 전날까지만 넓히고 그 뒤 청크를 받지 않는다 |
| `backend/src/repository/stock_job.py` | modified | `attempted_since(session, stock_id, start, end, since)` — 마지막 작업이 그 구간을 요청했고 `since` 뒤에 성공했는가 |
| `backend/src/api/services/stock_collect.py` | modified | `plan_collection` — 위가 참이면 수집하지 않는다(`None`) |
| `backend/src/config/settings.py`·`.env.example` | modified | `stock_provisional_retry_minutes`(`STOCK_PROVISIONAL_RETRY_MINUTES`, 기본 30, 최소 1) |
| `docs/implementation-notes.md` §3·`CLAUDE.md` 색인 | modified | 잠정 봉 규칙과 남은 한계(미국 마감 뒤 봉의 시가) |
| `backend/tests/contract/test_stock_provisional_bar.py` | added test | 원본 응답 픽스처 셋 |
| `backend/tests/unit/test_session_finished.py` | added test | 시간표 판정 |
| `backend/tests/integration/test_stock_provisional_collection.py` | added test | 커버리지·되풀이 막기 |

## Diff Highlights

```python
# ingestion/yahoo/parse.py — parse_chart
day = _local_date(epoch, offset)
empty = open_raw <= 0 or close_raw <= 0
unfinished = (now is not None and session_key is not None
              and not session_finished(session_key, day, now))
if unfinished or (empty and epoch == live_stamp):   # 잠정 — 행 없음, 그 첫 날을 알린다
    provisional = day if provisional is None else min(provisional, day)
    continue
if empty:                                           # 확정 자리의 0 — 출처의 빈 값(잠정 아님)
    continue
...
first_open = _first_unfinished(session_key, now)    # 오늘 세션이 끝났으면 다음 날
pending = first_open if first_open <= requested_to else None   # 봉이 없어도 그날부터 잠정

# worker/stock_runner.py — collect_range
through = chunk_end if provisional is None else min(chunk_end, provisional - _ONE_DAY)
if through >= chunk_start:
    await record_coverage(session, stock_id, chunk_start, through)
...
if provisional is not None:
    return stored                                   # 뒤 청크를 기록하면 잠정 날이 덮인다

# api/services/stock_collect.py — plan_collection
if await attempted_since(session, stock_id, missing_from, missing_through,
                         dt.datetime.now() - retry):
    return None                                     # 받아 둔 날까지로 답한다
```

## Tests Added or Updated

- `tests/contract/test_stock_provisional_bar.py` (16)
  - 0 봉: 행 없음, 잠정 10-06. 지금 시각이 없어도 같다
  - NVDA 장중 봉: 행 없음, 잠정 10-08. 장 전도 잠정이다
  - 같은 봉을 16:00 EDT에 받았다고 보면 확정이다(규칙의 경계)
  - 삼성전자 마감 뒤 봉은 확정이다(269,500/262,000)
  - 지금 시각이 없으면 세션을 가리지 않는다
  - 확정 자리의 시가 0·종가 음수는 행만 없고 잠정이 아니다
  - 클라이언트가 지금 시각으로 가른다
  - (실측 뒤 추가 — `c343ba9`) 장 전 응답(원본 id 1042 — 10-13 봉 없음)
    - 10-13을 요청했으면 10-12 행은 그대로이고 10-13이 잠정이다
    - 끝난 날만 요청했으면 잠정이 없다
    - 마감 뒤에는 오늘이 끝난 날이고 다음 날부터가 잠정이다
    - 국내 종목의 어제는 끝난 날이다
    - 클라이언트가 요청 끝을 넘긴다
- `tests/unit/test_session_finished.py` (13)
  - KRX 08:59~15:29는 끝나지 않았고 15:30부터 끝났다
  - 지난 거래일은 끝났다
  - 미국 장중(한국 00:23)은 끝나지 않았고 마감 뒤는 끝났다
  - 서머타임이 끝난 뒤 마감은 한국 06:00이다
  - 도쿄 점심은 끝나지 않았다
  - 뒤의 날은 끝나지 않았다
  - 모르는 시장은 거절한다
- `tests/integration/test_stock_provisional_collection.py` (10)
  - 수집: 잠정 날은 커버리지에 없다. 다음 수집이 그날부터 다시 받는다. 잠정 날 뒤 청크는 부르지 않는다. 첫날이 잠정이면 커버리지가 없다
  - 되풀이 막기
    - 방금 그 구간을 받았으면 200(`asOf` 09-30), 새 작업 없음. 차트도 같다
    - 31분 지나면 202
    - 설정 5분이면 10분 뒤 202
    - 마지막 작업이 실패면 202
    - 다른 구간의 작업이면 202
- 기존 테스트의 기대값은 바꾸지 않았다(확정 봉은 그대로 행이 된다)

## Local Verification

- 테스트를 먼저 커밋했다
  - `80bf626`: 계약 10·통합 6 실패. 다시 받아야 하는 경우의 통합 4건은 지금도 202라 통과했다. 단위는 함수가 없어 수집 오류였다
  - `c343ba9`: 계약 6 실패
- 게이트(서버를 내리고)
  - 첫 수정 뒤 3,728 passed, 커버리지 96.66%
  - 요청일 규칙 뒤 3,734 passed, 커버리지 96.66%
  - 바꾼 모듈 커버리지: `stock_collect`·`stock_runner` 100%, `yahoo/parse` 97%, `market_session` 97%, `stock_job` 92%, `yahoo/client` 92%. 덮이지 않은 줄은 모두 기존 줄이다
  - `mypy src`(297 파일)·`ruff check --no-cache src tests` 통과
  - 프론트엔드는 바꾸지 않아 다시 돌리지 않았다
- 개발 DB 바로잡기(일회성 점검 스크립트 — 저장소 밖)
  - 원본 일봉 응답을 받은 차례대로 새 해석(`now = received_at`)으로 다시 읽었다
    - 잠정으로 저장된 행 2개: 삼성전자 10-06(원본 524), NVDA 10-08(원본 640)
    - 0 이하 가격 행 1개: 삼성전자 10-06, 같은 행이다
  - 두 행을 지우고 커버리지를 줄였다(삼성전자 10-12 → 10-05, NVDA 10-12 → 10-07)
  - 새 코드로 띄운 개발 서버에 평소처럼 조회했다. 둘 다 202 → 200이고 커버리지는 10-12로 돌아왔다
    - 삼성전자 10-06 저장값: 278,500 / 272,000(출처 확정값과 같다)
    - NVDA 10-08 저장값: 234.919998 / 230.479996
  - 다시 점검: 잠정으로 저장된 행 0, 0 이하 가격 행 0
- API 등락(일 단위)
  - 삼성전자 10-06
    - 시작가 ▲5,000(+1.83%, 10-02 대비), 종가 ▼4,000(−1.45%)
    - 수정 전에는 시작가가 "▼ 273,500.00 −100.00%"였다
  - 삼성전자 10-07
    - 시작가 ▼9,000(−3.23%, 10-06 대비)
    - 수정 전에는 "▲ 269,500.00 —"였다
  - NVDA 10-08 종가 ▼6.99(−2.94%), 10-09 종가 ▼1.20(−0.52%)
- 화면(헤드리스 Chrome 1440px, 이력 다시 실행 → 일 단위)
  - 삼성전자·NVDA 표 첫 쪽 30행이 API와 글자 차이 0이다
  - 삼성전자 10-06 행: "278,500.00 | ▲ 5,000.00 | +1.83% | 272,000.00 | ▼ 4,000.00 | -1.45%"
- 미국 장중 실측(2026-10-13 22:36 KST = 09:36 EDT, 새 코드)
  - 어댑터: NVDA 10-13 하루 요청 → 행 없음, 잠정 10-13
  - 개발 서버 `end=2026-10-13` 조회
    - 주식 쪽은 새 작업을 만들지 않았다(되풀이 막기 — 22:29 작업이 그 구간을 요청했다)
    - 커버리지는 10-12이고 10-13 행이 없다
  - 남은 202는 환율 쪽이다
    - 환율 수집은 어제까지라 `end`가 오늘이면 202가 이어진다. 이번 변경 전부터 그렇고, 기본 계산 끝(어제)에서는 생기지 않는다
    - 그 동안 3초마다 조회해 빈 환율 작업(구간 0개, 외부 호출 없음)이 여러 건 생겼다
- 마감 뒤 봉 대조(저장값 vs 지금 출처 확정값)
  - KRX 4종목은 모두 같다
  - 미국 7종목 가운데 4종목은 시가가 몇 센트 다르다. 종가는 모두 같다(Follow-up)

## Deviations from Assessment

- **요청일 규칙을 더했다**(평가에 없던 셋째 잠정)
  - 실측 중 2026-10-13 22:29:55 KST(미국 개장 1분 전)에 NVDA 10-13을 요청했다
  - 출처는 10-13 봉 없이 10-12 마감 봉만 줬다. 평가의 두 규칙은 받은 봉만 보므로 10-13이 받은 구간에 들어갔다
  - 그대로면 장이 끝난 뒤에도 그날을 다시 받지 않는다 — 같은 결함이다
  - `parse_chart`에 `requested_to`를 더하고 클라이언트가 요청 끝을 넘긴다. 테스트를 먼저 커밋했다(`c343ba9`, 6건 실패 확인)
- 저장된 행 바로잡기(평가 4)는 평가대로 일회성 점검 스크립트로 했다(저장소에 넣지 않음). 그 실측이 NVDA 10-13을 행 없이
  받은 구간에 넣은 것도 같은 스크립트 방식으로 되돌렸다(10-13 행이 없음을 확인한 뒤 `covered_through` 10-13 → 10-12)

## Follow-ups

- 미국 종목의 마감 뒤 마지막 거래 시각 봉은 지금처럼 확정으로 둔다. 시가가 출처 확정값과 몇 센트 다를 수 있다(2026-10-13 실측 7종목 중
  4종목). 출처가 굳힐 때까지 다시 받으면 증분 수집마다 한 번씩 더 돈다 — 호출 수와 "받고 있습니다" 빈도의 대가가 있어 이번에는 하지 않았다
- 이미 저장된 그런 봉(마감 뒤 봉으로 받은 미국 종목 시가)은 바로잡지 않았다
- **별개 관찰 — 출처의 2026-10-12 국내 일봉 결측**: 출처가 삼성전자·SK하이닉스의 10-12(월) 일봉을 모든 값이 `null`로 준다(2026-10-13
  22:27 KST). 같은 날 KOSPI 지수(`^KS11`)는 값이 있다(종가 6,384.24). 지금 해석은 `null` 봉을 출처 결측으로 보고 행 없이 받은
  구간에 넣는다(005부터 그대로). 그래서 삼성전자 10-12가 휴장처럼 비고, 출처가 나중에 채워도 다시 받지 않는다. 잠정 봉(이 결함)과는
  다른 문제다. `null` 봉은 휴일 자리 표시이기도 해서(014 R14-4) 다시 받기 규칙을 정하려면 따로 판단이 필요하다
- `end`를 오늘로 준 미국·일본 종목 조회는 환율 쪽 202가 이어진다(환율 수집은 어제까지). 화면의 기본 계산 끝에서는 생기지 않는다
