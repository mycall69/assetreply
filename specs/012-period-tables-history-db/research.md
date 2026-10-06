# Research: 012 — 기간 전환 스크롤, 일·주·월 표, 이력의 로컬 DB, 투자금 기본값

**Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Technical Context에 "NEEDS CLARIFICATION"으로 남은 항목은 없다. 아래는 코드베이스 조사(2026-10-06)에서 나온 사실과 그에 따른 설계 결정이다.
줄 번호는 조사 시점의 것이다.

## 조사에서 확인한 사실

| 확인 | 결과 |
|------|------|
| 외환 기간 전환의 스크롤 | `fxWorkspaceStore.setPeriod`가 `daily: null`과 `tableEpoch + 1`을 함께 낸다(`:338-359`). 새 표가 붙으면 `app/fx/page.tsx`의 효과(`:54-63`)가 `tableTop.scrollIntoView`를 부른다 — 이것이 "화면이 위로 쑥 올라감"이다. 먼 날짜(`selectDate`, `:365-403`)도 `tableEpoch`를 올리고, 표가 붙어 있으므로 `DailyTable`의 `resetKey` 효과(`:53-58`)도 함께 돈다 |
| 높이 붙잡기 | `holdWhile`(`page.tsx:41-52`)은 바꾸기 직전 작업 영역 높이를 `minHeight`로 잡고, 다시 받기가 끝나면 놓는다. 통화·기간 전환 모두에 이미 걸려 있다. 놓은 뒤 새 표가 짧으면 문서가 줄어 브라우저가 스크롤을 당긴다 |
| 외환 늦은 응답 | `setPeriod`·`loadMoreDaily`는 단위를 견준다. `loadAll`(`:241-279`)은 단위·통화를 견주지 않는다 — 통화 전환의 `loadAll`이 늦게 오면 기간 전환 뒤의 표에 이전 단위의 행이 들어올 수 있다 |
| 주식 하루하루 상태 | `reinvest.simulate_detailed`(`:158-278`)와 `recurring_stock.simulate_recurring_stock`(`:154-245`)은 모든 거래일을 훑지만, 사건 행·월 행과 마지막 상태(`latest`)만 낸다. **하루하루 상태가 없다** |
| 가상자산 하루하루 상태 | `crypto_hold.HoldOutcome.daily`(`:78`)와 `recurring_crypto`의 `daily`(`:167`)가 일봉마다 상태를 낸다. 일시금 `daily`의 매수일 행에는 수수료가 없다 — 수수료는 월 행(`rows`)에 있다 |
| 차트의 재료 | 주식 일시금·적립식 시계열은 **표의 행**(`result.rows`)으로 만든다(`stock_series._one_per_day`, `recurring_series.build_stock_series`) — 월 첫 거래일과 사건 날의 점이다. 가상자산 시계열은 `daily`다 |
| 첫 평가일 | 주식 일시금은 시작일 이후 첫 거래일에 산다. 가상자산 일시금은 **시작 월의 첫 일봉**에 산다(`crypto_simulation.py:158`, `crypto_hold.py:115`). 적립식은 첫 납입일부터 행이 있다 |
| 계산과 쪽 | 쪽마다 시뮬레이션을 처음부터 다시 계산한다. 캐시가 없다(`test_settings_applied::test_저장할_캐시가_없어_즉시_반영된다`가 지킨다). 쪽 함수는 넷이고, 일시금 둘은 같은 날의 행을 한 쪽에 붙잡지 않는다 — 같은 날 두 행이 쪽 경계에 걸리면 뒤 행이 빠진다 |
| 질의 이름 | 적립식 경로의 `frequency`는 납입 주기다. 외환의 단위 이름은 `period`(`daily`·`weekly`·`monthly`)다 |
| 결측 구간 | `series_query.compute_gaps`(`:61-89`)가 순수 함수다. 가상자산은 `inside_reason="source_missing"`으로 부른다. 일시금은 시작 월 1일부터, 적립식은 시작일부터 본다 |
| 외환 기간 함수 | `api/services/period_rows.py`의 `period_bounds`·`shifted_from`·`is_ongoing`은 순수하지만, 모듈이 `FxRate`·`repository.fx_rate`를 불러온다. `shifted_from`은 주말 고시가 없다고 전제한다. `is_ongoing`은 오늘과 견준다 |
| 이력 저장소 | 브라우저 키 넷(`assetreplay:stock-history:v1`·`assetreplay:crypto-history:v1`·`assetreplay.depositHistory.v1`·`assetreplay:realestate-history:v1`). 식별자 규칙은 lib 넷의 `conditionId` 계열이다. `savedAt`은 실행마다 새로 쓰이지만 어디서도 읽지 않는다. 011 전 항목은 읽을 때 고치지 않고 쓰는 곳에서 기본값을 준다 |
| 이력 호출 | 스토어의 `restoreHistory`(동기)를 화면 마운트 효과가 부른다. 저장은 200 결과 뒤에만 한다(202 아님). 이력 부품 넷은 순수 표시 부품이다 |
| 설정의 틀 | 단일 행 테이블(`id = 1`) + 코드의 기본값 상수 + `upsert`. PUT은 저장 뒤 GET 본문을 돌려준다. 검증 실패는 422 `invalid_setting`. 설정 화면은 절마다 `useState` + `apiClient.get/put` |
| 마이그레이션 | 머리는 `f4c2a8e19d35`(`주식_매도_세금_설정`). JSON 열을 쓰는 테이블이 없다 — 긴 글은 `Text`다. 보관 기간 정리의 선례 `db/retention.purge_succeeded_jobs`가 있다(앱에서 부르지 않음) |
| 원금 칸 | 세 스토어의 처음 값이 `principal: ""`다. 스토어는 모듈 수준이라 화면을 오가도 남고, 마운트 효과가 입력을 덮지 않는다. 다시 실행은 항목의 값을 넣는다. 원금이 비어 있는지 검사는 예금에만 있다 |

## R12-1 외환 기간 전환은 창을 옮기지 않는다

**Decision**: `setPeriod`가 `tableEpoch`를 올리지 않는다. `tableEpoch`는 "표의 처음으로"(004 FR-005a 먼 날짜)만의 신호가 된다. 화면의 효과(`page.tsx:54-63`)와
`DailyTable`의 `resetKey`는 그대로 둔다 — 둘 다 `tableEpoch`가 바뀔 때만 돈다.

- 기간 전환의 높이 붙잡기는 이미 있다. **놓을 때 바닥을 남긴다** — 새 표가 붙은 뒤 문서 높이가 지금 스크롤 위치를 받치지 못하면(새 표가 짧으면)
  `minHeight`를 "지금 스크롤 + 창 높이 − 작업 영역 위치"로 둔다. 다음 붙잡기까지 그대로다. 받칠 수 있으면 지금처럼 비운다.
- 이 장치를 훅 하나(`hooks/useHeightHold.ts`)로 뽑아 외환·주식·가상자산 화면이 함께 쓴다(R12-8).
- `loadAll`이 늦게 와도 지금 단위·통화가 아니면 버린다(FR-002 — 기존 결함을 함께 막는다).

**Rationale**: 스크롤 이동의 원인은 기간 전환이 "표의 처음으로" 신호를 함께 낸 것 하나다. 신호를 먼 날짜에만 남기면 FR-005a는 그대로다. 표가 붙지 않은
동안 먼 날짜를 고르는 경우도 화면 효과가 그대로 맡는다. 바닥을 남기는 이유는 FR-001의 실패 양상 *다른 곳에서 일어남*이다 — 놓는 순간 짧아진 문서를
브라우저가 당긴다. 월 단위의 짧은 이력에서 실제로 일어난다.

**Alternatives considered**:
- 화면 효과를 지우고 `DailyTable`의 `resetKey`만 남긴다 — 표가 떨어진 동안의 먼 날짜 선택이 표의 처음으로 가지 않는다.
- `tableEpoch`는 올리되 표가 떨어졌다 붙는다는 사실(새로 붙은 표는 직전 키를 모른다)에 기댄다 — 동작이 마운트 순서에 묶인다. 010에서 StrictMode가 이런 장치를
  무력화한 적이 있다.
- 놓을 때 늘 바닥을 남긴다 — 표가 충분히 길 때도 `minHeight`가 남아 010의 "새 통화가 오면 놓는다" 검사가 깨진다. 필요할 때만 남긴다.

## R12-2 기간 표는 서버가 만든다 — 새 순수 모듈

**Decision**: 표의 행 구성(기간 행·사건 행·결측 구간 행과 표시)을 서버의 새 순수 모듈 `backend/src/simulation/period_table.py`가 만든다. 행의 종류와 상관없이
날짜만 다루는 일반 함수다. 서비스가 그 결과를 자기 행 모양으로 바꾼다.

- 입력: 계산 기간 안의 시세일(오름차순), 사건이 있는 날, 단위, 계산 끝, (가상자산 일 단위만) 결측 구간
- 출력: 최신순 항목 목록 — `event`(사건 행 차례), `period`(대표일, `shifted_from`, `is_ongoing`), `missing`(처음·끝)
- 달력 함수(`period_bounds`·`anchor_of`·`is_ongoing`)를 같은 모듈에 둔다. 외환의 `period_rows.py`는 **고치지 않는다**.

**Rationale**:
- 화면은 계산하지 않는다(011 `noClientSideFinance`). 값은 그대로 서버 문자열이고, 대표일 판정도 서버가 한다.
- 표 넷(주식·가상자산 × 일시금·적립식)이 같은 규칙을 한 곳에서 쓴다.
- 외환 함수를 다시 쓰지 않는 이유가 셋이다.
  - 모듈이 `FxRate`와 저장소를 불러오므로 `simulation/`이 `api/`를 부르게 된다(계층 역전).
  - `shifted_from`이 주말 고시가 없다고 전제한다. 가상자산에는 틀리다(명확화 2).
  - `is_ongoing`의 기준이 오늘이다. 이 표의 기준은 계산 끝이다(FR-004a).
  - 외환은 004 테스트가 고정한 검증된 경로다. 두 규칙이 갈라질 때 외환이 흔들리지 않는다.

**Alternatives considered**:
- 일 단위 행을 모두 보내고 화면이 주·월을 고른다 — 20년 일 단위 5,000행(가상자산 7,300행)을 한 번에 보내야 하고, 대표일·표시 판정을 화면이 한다.
  쪽 이어 받기(FR-009)도 단위마다 달라진다.
- `period_rows.py`를 일반화한다 — 외환 경로가 바뀐다. 이 기능의 범위(US1은 화면만)를 넘는다.

## R12-3 대표일 규칙 — 자산군 하나의 규칙

**Decision**:
- **일**: 계산 기간 안의 시세일마다 한 기간이다. 표시는 없다.
- **주**(월~일): 그 주 ∩ 계산 기간에서 **금요일 이하의 마지막 시세일**이 대표일이다. 그런 날이 없으면 그 주 ∩ 계산 기간의 마지막 시세일(토·일)이다
  (명확화 2). 금요일이 아니면 `shifted_from` = 그 주 금요일.
- **월**: 그 달 ∩ 계산 기간의 마지막 시세일이 대표일이다. 말일이 아니면 `shifted_from` = 그 달 말일.
- 구간 ∩ 계산 기간에 시세일이 없으면 기간이 없다(FR-015와 같다).
- **진행 중**: 주·월에서 구간의 끝(일요일·말일)이 계산 끝 뒤면 `is_ongoing`이다(FR-004a). 일 단위는 늘 아니다.
- 주식의 시세일은 일봉 날짜(거래소 날짜), 가상자산은 UTC 일봉 날짜다.

**Rationale**: 주식에는 주말 일봉이 없으므로 이 규칙이 외환 규칙(그 구간의 마지막 고시일)과 같은 날을 고른다. 가상자산에서만 "금요일 이하"가 뜻을
갖는다. 하나의 규칙이라 자산군 분기가 없다. 진행 중의 기준을 계산 끝으로 두면 시세가 끊긴 종목의 마지막 구간(계산 끝 앞에 끝남)에 진행 중 표시가 붙지
않는다(spec Edge Cases).

**Alternatives considered**: 외환처럼 "그 구간의 마지막 시세일" — 가상자산 주 행이 매주 일요일이 되어 모든 행에 옮겨짐 표시가 붙는다(spec FR-004 실패 양상).

## R12-4 주식에 하루하루 상태를 더한다 — 기존 출력은 그대로

**Decision**: `reinvest.Outcome`과 `recurring_stock.RecurringOutcome`에 `daily`(하루하루 상태 — 첫 평가일부터 일봉마다 하나, 오름차순)를 **더한다**.

- 그날의 사건(분할·매수·배당·재투자·납입)을 모두 처리한 뒤의 상태다 — 지금의 월 행 스냅숏과 같은 시점이다.
- `rows`·`latest`는 바뀌지 않는다. 주식 차트와 보드의 재료가 그대로라 FR-007·FR-017이 구조로 지켜진다.
- 기본값이 빈 튜플인 칸이라 기존 생성자 호출(단위 테스트의 손 조립 포함)이 그대로 돈다.
- 불변식 테스트: 월 행이 있는 날의 `daily` 상태는 그 월 행과 값이 같다. `daily`의 마지막은 `latest`와 같다.

가상자산은 `daily`가 이미 있다. 일시금의 매수일 행만 `rows`(월 행 — 수수료가 있다)에서 가져온다(R12-5).

**Rationale**: 일 단위 표에는 거래일마다 상태가 필요하다. `rows`에 일 행을 넣으면 주식 차트가 그 행으로 그려지므로 차트가 바뀐다 — FR-007 위반이다.
`daily`를 따로 두면 계산 모듈의 검증된 출력과 그것을 고정한 단위 테스트(참조 구현 대조 포함)가 바뀌지 않는다.

**Alternatives considered**: 서비스가 일봉과 사건 행으로 하루하루 상태를 다시 만든다 — 계산을 두 곳에서 하게 된다(배당 현금·매수 대기금·분할의 순서).

## R12-5 사건 행과 기간 행의 합치기

**Decision**:
- **사건 행**은 단위와 관계없이 모두 나온다(FR-005).
  - 일시금(주식·가상자산): 첫 매수 `buy`
  - 주식: 배당락 `dividend`, 재투자 `reinvest`
  - 적립식: 납입 `contribution`(미뤄진 납입 표시 포함)
- 기간의 대표일에 사건 행이 있으면 그 날의 기간 행을 만들지 않는다. 대표일 표시(`shiftedFrom`·`isOngoing`)는 **그날의 마지막 사건 행**이 진다 — 그날
  모든 사건을 처리한 뒤의 상태라 기간 행이 보였을 값과 같다.
- 같은 날 행의 순서는 지금 그대로다(일시금은 배당 → 재투자, 적립식은 늦은 사건이 위).
- API 행의 `kind`: `buy`·`dividend`·`reinvest`·`contribution`·`period`·`missing`. 표의 `month_first`는 없어진다(FR-008). 계산 모듈 안의 `month_first`는 주식 차트의
  재료로 남는다.
- 가상자산 `firstDayMissing`(◇)은 표 행에서 없어진다. 월 단위는 옮겨진 기준일 표시가, 일 단위는 결측 구간 행이 대신한다(FR-008). 계산 모듈의 칸은
  남는다(단위 테스트가 고정 — 바꾸지 않는다).

**Rationale**: 011의 "그 달 첫 거래일 행은 그날 납입이 없을 때만" 규칙을 모든 사건과 모든 단위로 넓힌 것이다. 표시를 마지막 사건 행이 지므로 "다른 곳에서
일어남"(배당락일이 금요일로 바뀌어 보임)이 생기지 않는다 — 사건 행의 날짜는 늘 사건 날이다.

## R12-6 결측 구간 행 — 차트와 같은 구간

**Decision**: 가상자산 일 단위에서 `compute_gaps`를 **시계열 경로와 같은 입력**(일시금은 시작 월 1일부터, 적립식은 시작일부터 계산 끝까지, 같은 커버리지)으로
불러 `source_missing` 구간만 `missing` 행으로 넣는다. 행은 `{"kind": "missing", "date": 처음, "dateTo": 끝}`이고 값 키가 없다.

**Rationale**: 같은 함수·같은 입력이라 "결측 구간 행 수 = 차트 출처 결측 끊김 수"(SC-002)가 구조로 성립한다. 첫 평가일 앞의 결측(시작 월 1일이 빠져 3일에 산
경우)도 표 맨 아래 행이 되어 지금의 ◇가 알리던 사실이 남는다. 주식의 `no_quote`(휴장)는 행이 되지 않는다(FR-004b).

## R12-7 쪽과 질의

**Decision**:
- 네 표 경로에 `period`(`daily`·`weekly`·`monthly`, 기본 `daily`)를 더한다. 밖의 값은 400 `invalid_query` — `daily`로 떨어뜨리지 않는다. 응답에 `period`를
  싣는다(화면의 늦은 응답 판정 — FR-006).
- 요청마다 표 전체를 만든 뒤 커서(`before`)로 자른다 — 지금처럼 계산을 다시 하고 캐시가 없다. 원화 환산(행마다의 환율)은 **잘라 낸 쪽의 행만** 한다.
- 쪽 함수는 하나(`period_table.page`)로 모은다. **같은 날의 행을 한 쪽에 붙잡는다**(지금 적립식 주식 쪽 함수의 방식). 결측 구간 행의 커서 날짜는 그
  구간의 처음이다.
- 스토어는 `daily`이면 `period`를 보내지 않는다 — 기본 단위의 요청 문자열이 지금과 같다.

**Rationale**: 일 단위 20년도 행 묶기는 일봉 한 번 훑기다(011 SC-008의 계산과 같은 차수). 변환만 쪽 크기로 줄인다. 같은 날 행 붙잡기는 일 단위에서 사건 행과
겹치는 날이 많아지므로 꼭 필요하다 — 지금의 일시금 쪽 함수는 같은 날 두 행이 경계에 걸리면 뒤 행을 건너뛴다(FR-005 *일어나지 않음*).

## R12-8 화면 — 단위 탭·표시·붙잡기·늦은 응답

**Decision**:
- 표 머리에 외환과 같은 단위 탭을 둔다. `components/fx/PeriodTabs.tsx`에 선택 속성 `titles`를 더한다 — 기본값은 지금 외환 문구라 외환 화면과 그 테스트가 그대로다.
- 행 표시는 새 부품 `components/period/PeriodMarks.tsx`(📅·⏳, `title`·`aria-label` 글자 설명)와 범례 `PeriodLegend.tsx`다. 모양·기호는 외환
  `PeriodRowBadges`와 같고, 문구는 "시세가 없어"(주식)·"일봉이 없어"(가상자산)다. 외환 부품은 고치지 않는다.
- 결측 구간 행은 값 칸을 비우고 "MM-DD~MM-DD 출처 결측 — 값 없음"을 한 칸에 보인다(가상자산 표 둘).
- 스토어(주식·가상자산)에 `tablePeriod`(처음 `daily`)와 `setTablePeriod`를 둔다.
  - 단위를 바꾸면 **표의 행만** 비우고(보드·차트·요약은 그대로 — FR-007) 첫 쪽을 다시 받는다.
  - 늦은 응답은 표 차례 번호(`tableSeq`)로 버린다. 이어 받기도 같은 번호를 확인한다.
  - 다시 실행해도 고른 단위가 남는다(spec Assumptions).
- 화면은 단위 전환을 `useHeightHold`(R12-1)로 감싼다.

**Rationale**: 주식·가상자산의 늦은 응답 처리가 지금은 없다(실행·이어 받기 모두). 단위 비교만으로는 일 → 주 → 일 전환의 첫 "일" 응답을 거르지 못하므로
차례 번호를 쓴다. 보드가 표 응답에서 값을 다시 읽으면 FR-007 실패 양상(보드가 표의 맨 위 행을 따라감)의 문이 열리므로, 단위 전환은 행만 바꾼다.

## R12-9 이력 저장 모델 — 테이블 둘, 식별자는 서버가

**Decision**:
- `simulation_history` — 자산군(`asset_class`), 조건 식별자(`condition_key`), 조건(`condition` — JSON 글), 마지막 실행 시각(`last_run_at`), 보관 기준 시각
  (`retain_from`). `(asset_class, condition_key)` 유일.
- `history_setting` — 단일 행(`id = 1`), 보관 기간(`retention`, 비원생 열거 `days_7`…`days_365`·`unlimited`). 행이 없으면 기본 30일이다.
- **식별자는 서버가 조건에서 계산한다.** 규칙은 지금 lib 넷의 규칙과 글자까지 같다(옮긴 항목의 식별자가 그대로다). 화면은 서버가 준 `id`만 쓴다.
- 조건은 서버가 자산군마다 검증하고(칸·형식) 정해진 차례로 직렬화해 글로 저장한다. 011 전 형식(방식·상품 칸 없음)은 그대로 저장하고, 쓰는 곳의 기본값
  규칙(011 FR-033)이 지금처럼 읽는다.

**Rationale**:
- 식별자를 서버가 계산하면 유일 키가 저장된 내용에서 나온다 — 두 브라우저가 다른 판의 화면으로 저장해도 같은 조건은 한 항목이다.
- JSON 열 대신 글: 쓰는 테이블이 없어 선례가 없다. MySQL의 JSON은 키 차례·숫자 표기를 바꿔 돌려준다 — 원금 문자열 `"10000000"`이 수로 바뀌는 길이
  생긴다. 글이면 저장한 글자 그대로다.
- 원칙 VI(금액 열은 DECIMAL): 조건의 원금은 사용자가 친 입력 문자열의 기록이다. DB·서버가 이 값으로 계산하지 않고, 다시 실행하면 그 문자열이 그대로
  시뮬레이션 질의가 된다(지금의 브라우저 저장과 같다). 계산에 쓰이는 금액 열이 아니다 — Complexity Tracking에 기록한다.
- 열거형 보관 기간: 다른 설정 테이블은 "NULL = 기본값"인데 보관 기간에는 "무기한"이라는 값이 더 있다. NULL에 두 뜻을 싣지 않는다.
- 같은 조건의 동시 저장: `(asset_class, condition_key)` 유일 키와 upsert가 한 행으로 모은다. 마지막 실행 시각은 나중에 끝난 쓰기다 — 개인 이용 전제(spec
  Assumptions)에서 "늦은 쪽"과 같다.
- 원칙 VI 해석은 사용자가 확인했다(2026-10-06). 서버는 원금을 검증할 때만 `Decimal`로 읽고 받은 글자 그대로 저장·응답한다 — 이력 모듈에 원금 산술이 없다는
  것을 T039가 고정한다.

**Alternatives considered**:
- 자산군마다 테이블 넷(원금 DECIMAL 열) — 같은 기능의 저장소·경로·검증이 네 벌이다. 화면 조건이 바뀔 때마다(011처럼) 스키마를 바꿔야 한다.
- 화면이 식별자를 보내고 서버는 그대로 쓴다 — 식별자와 내용이 어긋날 수 있다(다른 판의 화면).

## R12-10 보관 기간 정리 — 읽고 쓸 때마다

**Decision**: 기한이 지난 항목(보관 기준 시각 < 지금 − 기간)을 지우는 일을 다음 때마다 같은 거래 안에서 먼저 한다.
- 목록 조회
- 항목 저장
- 옮기기
- 설정 저장 — 모든 자산군

무기한이면 지우지 않는다. 시각은 UTC로 저장하고 경과 시간으로 잰다(30일 = 30 × 24시간). 지금 시각은 서비스 모듈의 `utc_now()`로 얻고, 테스트는 그것을
바꾼다(가상자산 `utc_yesterday`와 같은 방식).

**Rationale**: FR-012 실패 양상 *늦게 일어남* — 기간을 줄인 뒤 다음 날까지 남으면 안 된다. 읽을 때 지우면 목록에 기한 지난 항목이 보일 수 없다. 배경 태스크를
더하지 않는다 — 이미 여덟이고, 한 사용자 도구라 읽을 때 지우는 것으로 충분하다. 조회가 쓰기를 하는 것은 이 정리 하나로 한정하고 경로 문서에 밝힌다.

## R12-11 브라우저 이력 옮기기 — 화면마다 그 자산군만

**Decision**: 각 화면의 `restoreHistory`(마운트 효과)가 다음 차례로 한다.
1. 그 자산군의 브라우저 키를 읽는다.
2. 항목이 있으면 `POST /api/history/{asset}/import`로 보낸다.
3. 2xx면 그 키를 지운다.
4. 목록을 받는다.

- 서버는 항목마다 검증·식별자 계산 후 합친다.
  - 마지막 실행 시각은 브라우저 `savedAt`과 DB 값 중 늦은 쪽이다. `savedAt`이 없거나 읽을 수 없으면 옮긴 시각이다.
  - 보관 기준 시각은 DB 값과 **옮긴 시각** 중 늦은 쪽이다(명확화 4).
- 검증에 실패한 항목은 건너뛰고 수를 돌려준다(`skipped`). 화면은 0보다 크면 알린다 — 조용히 버리지 않는다.
- 키가 깨져 읽을 수 없으면(JSON 아님) 옮기지 않고 키도 지우지 않는다.
- 옮기기·목록이 실패하면 키를 지우지 않는다. 화면은 불러오기 실패(FR-014a)를 보인다. 다시 시도가 같은 차례를 다시 한다.

**Rationale**: 자산군 키를 그 화면만 다루므로 자산군이 섞일 수 없다(FR-013 *다른 곳에서 일어남*). 키 삭제를 서버의 성공 뒤에만 하므로 잃지 않는다(FR-013
*일어나지 않음*). 순서(마지막 실행 시각)는 브라우저의 것을 지키고 보관 기간만 옮긴 시각부터 잰다 — 목록 차례가 옮기기 전과 같다.

**Alternatives considered**: 앱 셸이 처음 열 때 넷을 한 번에 옮긴다 — 한 자산군 실패가 다른 자산군의 키 삭제와 얽힌다. 화면마다가 단순하다.

## R12-12 이력 요청 — 따로 된 클라이언트 함수

**Decision**: `frontend/src/lib/historyApi.ts`가 이력 경로를 부른다. `apiClient`의 공통 요청 함수(`request` — 공개로 바꾼다)를 직접 쓰고, `apiClient`에 `delete`를
더한다. 브라우저 키 읽기·지우기는 `lib/legacyHistory.ts` 하나로 모은다. 지금의 lib 넷(`simulationHistory.ts` 등)의 저장·식별자 함수는 없어진다.

- 테스트 기반(`tests/setup.ts`)에 `/api/history` 경로만 받는 메모리 안 대역(fetch)을 둔다. 이력이 주제가 아닌 화면·스토어 테스트는 빈 이력과 성공하는
  저장을 본다. 이력 테스트는 대역을 바꾸거나 직접 모의한다.

**Rationale**: 이력은 시뮬레이션과 실패 영역이 다르다. 이력 요청이 실패해도 결과는 보여야 한다(FR-014). 시뮬레이션 응답을 모의하는 기존 테스트(경로마다 같은
결과를 주는 `apiClient.get` 모의)가 이력 요청까지 가로채면, 이력과 무관한 단언들이 엉뚱한 응답으로 흔들린다. 공통 요청 함수를 쓰므로 오류 형식
(`ApiError`)은 같다.

## R12-13 실패·빈 상태의 화면

**Decision**:
- **불러오는 중**(`historyLoading`): 첫 목록이 오기 전에는 빈 상태 문구("아직 실행한 시뮬레이션이 없습니다")를 보이지 않는다.
- **불러오기 실패**(`historyLoadError`): "이력을 불러오지 못했습니다" + **다시 시도** 단추(FR-014a). 빈 상태 문구를 보이지 않는다.
- **저장 실패**: "이력을 저장하지 못했습니다. 결과는 그대로이고, 다시 실행하면 다시 저장합니다."(FR-014 — 지금의 `role="alert"` 자리)
- **삭제 실패**: "이력을 지우지 못했습니다."
- **옮기지 못한 항목**: "읽을 수 없는 브라우저 이력 N개는 옮기지 못했습니다."
- **안내**(FR-015): "ⓘ 이 기기의 로컬 DB에 저장됩니다. 마지막 실행 뒤 {N}일이 지나면 지워집니다 — 기간은 설정에서 바꿉니다." 무기한이면 "기한 없이
  남습니다". 자산군 구별 문구는 지금 그대로다.
- 이력 부품의 새 속성(`loading`·`loadError`·`onRetry`·`retentionDays`)은 선택 속성이다 — 지금 속성으로 그리는 테스트가 그대로 돈다.

## R12-14 투자 원금 기본값

**Decision**: `lib/principalFormat.ts`에 `DEFAULT_PRINCIPAL = "10000000"`(쉼표 없는 저장 형식)을 두고 세 스토어(`stockStore`·`cryptoStore`·`depositStore`)의 처음
`input.principal`로 쓴다. 다른 동작은 지금 그대로다.
- 방식·상품·통화를 바꿔도 `input`을 건드리지 않는다
- 다시 실행은 항목의 값을 넣는다
- 마운트 효과가 입력을 덮지 않는다

부동산은 바뀌지 않는다.

**Rationale**: 조사 결과 지금 동작이 FR-016의 "처음 열 때만"과 이미 같다 — 처음 값만 바꾸면 된다. 처음 값이 빈칸이라고 단언하는 테스트, 채워진 칸에 이어 쳐서
깨질 테스트가 없다(원금 칸에 치는 테스트는 모두 명시한 처음 값에서 시작한다).

## R12-15 바뀌는 기존 테스트 — 구현 때 승인을 받는다

요구사항 셋이 바뀌므로(spec Dependencies) 다음 기존 테스트가 바뀐다. 무엇을 어떻게 바꾸는지는 아래와 같다.
- **스토리의 테스트 커밋 전에** 그 스토리의 목록을 사용자에게 보여 승인을 받는다. 그 테스트 커밋에서 **바뀐 요구를 단언하는 부분만** 새 기대로
  고친다(011 T008과 같은 차례). 고친 테스트도 구현 전에는 실패한다 — 예정된 실패다.
- 목록에 있어도 바뀐 요구를 단언하지 않는 테스트는 고치지 않는다(읽어서 가린다).
- 구현 뒤 목록 밖의 테스트가 실패하면 결함으로 보고 멈춘다(헌법 원칙 III).

**US1 (004 FR-005b의 기간 전환)** — 두 건
- `frontend/tests/FxPageLayout.test.tsx` "StrictMode — 통화 전환은 창을 옮기지 않고, 기간 단위 전환은 새 표가 붙은 뒤 표의 처음으로 옮긴다" — 기간 전환 뒤에도
  `scrollIntoView`가 불리지 않는다로 뒤집는다. 통화 부분은 그대로다.
- `frontend/tests/PeriodSwitch.test.ts` "전환하면 스크롤을 처음으로 되돌릴 신호를 낸다" — `tableEpoch`가 그대로다로 뒤집는다.

**US2 (월 행 → 기간 행, 기본 단위 일)** — 경로 응답의 행을 단언하는 통합 테스트. 계산 모듈의 단위 테스트는 바뀌지 않는다(R12-4).
- 주식 일시금
  - `test_simulation_api.py` `Test행_구조` 넷(종류 집합이 `buy`·`period`·`dividend`·`reinvest`가 된다), `Test페이지` 셋(행 수·커서 — 일 단위)
  - `test_simulation_rows.py::Test키가_있는_행.test_매수가_있는_행에만_매매_수수료가_있다`(`buy` 행)
  - `test_simulation_currency.py` 넷
  - `test_delisted.py` 둘
  - `test_start_available.py` 둘
  - `test_reinvest_difference.py`
  - `test_settings_applied.py::test_수수료를_바꾸면_보유_주식이_달라진다`
  - `test_stock_settings_tax.py`(2021-08-02 행)
  - 차트와 표를 묶은 검사
    - `test_stock_series_api.py::Test표와의_일치` 넷 — "끝점이 표의 최신 행과 같은 날짜다"는 "모든 점의 날짜에 같은 값의 표 행이 있다"로 바꾼다. 일 단위 표는 차트보다
      촘촘하다
    - `test_stock_simulation_close_api.py::test_시계열의_잔고는_표의_잔고와_같다`
- 가상자산 일시금
  - `test_crypto_simulation_api.py` `Test결과` 다섯(매수 행 `buy`, ◇ 대신 결측 구간 행, 쪽)
  - `test_crypto_simulation_krw.py` 둘
  - `test_crypto_series_api.py::test_표의_행과_같은_날짜는_같은_값이다`
  - `test_crypto_series_price_api.py`의 표 대조 하나
- 적립식
  - `test_stock_recurring_api.py` 셋
  - `test_crypto_recurring_api.py` 넷
  - `test_stock_recurring_series_api.py::test_점은_표의_날짜이고_총자산과_누적_납입_원금이다`
  - `test_crypto_recurring_series_api.py::test_표의_행과_같은_날짜는_같은_값이다`
- 화면
  - 표 테스트의 고정 행 `kind: "month_first"` → `"period"`(타입이 바뀌어 tsc가 요구한다 — 단언은 그대로)
    - `PerformanceTable*`
    - `RecurringStockTable`
    - `RecurringCryptoTable`
    - `CryptoPerformanceTable`
    - `PerformanceBoard*`
  - ◇ 검사 둘
    - `CryptoPerformanceTable.test.tsx` "1일 결측 행에 ◇와 글자 설명이 있다"
    - `RecurringCryptoTable.test.tsx` "그 달 첫 일봉 행은 … ◇ 1일 결측이다"
    - 결측 구간 행 검사로 바꾼다

- **구현 뒤 실제 실패로 더해진 것(T011 승인 2026-10-06 — 목록을 만들 때 놓쳤다, 모두 위와 같은 이유)**
  - `test_crypto_settings_api.py::test_바꾼_수수료가_다음_시뮬레이션에_쓰인다`(첫 쪽의 마지막 행 = 매수 행이라 여겼다)
  - `test_crypto_simulation_api.py::test_아주_작은_가격을_원값_그대로_싣는다`(맨 아래가 시작 월 1일부터의 결측 구간 행)
  - `test_crypto_simulation_api.py::Test실행_주체::test_수집_줄이_작업을_끝내고_다시_요청하면_200이다`(같은 이유)
  - `test_stock_sale_cost_api.py::test_2023년_전_기준일도_설정_세율로_계산한다`(맨 위 행이 그 달 첫 거래일 → 기준일)
  - `test_stock_series_adjusted_api.py::test_점의_가격은_그_날_수정_종가다` 둘(차트 점 날짜 = 표 날짜 → 점마다 같은 날짜의 표 행이 있다)
  - 화면: `PerformanceTable.test.tsx`·`RecurringStockTable.test.tsx`의 `data-kind "month_first"` 단언, `tests/support/cryptoFixtures.ts`(매수 `buy`, ◇ 칸 제거)
- 목록에 있었지만 바뀌지 않은 것(바뀐 요구를 단언하지 않아 그대로 통과): `test_simulation_api.py` `Test행_구조`의 셋·`Test페이지` 셋, `test_start_available.py`,
  `test_reinvest_difference.py`, `test_settings_applied.py`, `test_stock_settings_tax.py`, `test_delisted.py`의 하나, `test_crypto_series_api.py`·
  `test_crypto_series_price_api.py`·`test_crypto_recurring_series_api.py`의 표 대조, `test_stock_simulation_close_api.py`, `test_crypto_recurring_api.py`의 셋

**US3 (이력의 보관 위치)**
- lib 테스트(브라우저 저장소 기반) — 식별자·중복·차례 검사는 서버 테스트로 옮기고, 키 검사는 `legacyHistory` 옮기기 테스트로 바꾼다
  - `simulationHistory.test.ts`
  - `simulationHistoryRecurring.test.ts`
  - `cryptoHistory.test.ts`
  - `cryptoHistoryRecurring.test.ts`
  - `depositHistory.test.ts`
  - `depositHistoryInstallment.test.ts`
  - `realEstateHistory.test.ts`
- 안내 문구 검사 — 새 안내로 바꾼다
  - `SimulationHistoryList.test.tsx` 둘
  - `CryptoHistoryList.test.tsx` 하나
  - `DepositHistoryList.test.tsx` 하나
  - `RealEstateHistoryList.test.tsx` 하나
- 브라우저 키에 직접 심고 읽는 스토어·화면 테스트 — 대역(R12-12)에 심고 읽게 바꾼다
  - `stockStoreRecurring` "적립식 이력"
  - `cryptoStoreRecurring` 같은 절
  - `depositStoreCompare` "이력"·"비교"
  - `depositStoreInstallment` "적금 이력"
  - `realEstateStoreCompare` "이력"·"비교"
  - `stockSelection` 하나
  - `SimulationFormPrincipal` "…이력에 남는다"
  - `SimulationHistoryBlocked`
  - `CryptoHistoryList`의 "저장소 —" 절
  - `StocksPageRerun`(심어 둔 키가 옮겨져 보이면 그대로 통과할 수 있다)

**US4** — 없다(R12-14).

## R12-16 성능

**Decision**: quickstart 3-6에서 잰다 — 20년 일 단위 첫 쪽과 다음 쪽이 각각 3초 안(SC-004).
- 주식 일시금(거래일 약 5,000)
- 가상자산 일시금(약 7,300일)
- 매일 적립 주식

**Rationale**: 늘어나는 일은 하루하루 상태 만들기(한 번 훑기)와 표 묶기(한 번 훑기)다. 원화 환산은 쪽 크기만 한다(R12-7). 011이 같은 크기의 계산을 3초 안에
냈다(011 SC-008).
