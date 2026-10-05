# Data Model: 부동산 투자 시뮬레이션

**Feature**: `009-real-estate-investment-simulation` | 근거: [research.md](./research.md), [spec.md](./spec.md)

신규 테이블 9개, Alembic 마이그레이션 하나(head `c4d8e2f91b07` 다음). 기존 테이블은 바꾸지 않는다. 접두사 `apt_`(대상이 아파트 매매다).

형식 이름: `AREA` = `DECIMAL(7, 2)`(전용㎡), `WON` = `DECIMAL(15, 0)`(원 단위 금액 — 최고가 수백억도 담는다), `SPREAD` = `DECIMAL(9, 6)`(기존 —
비율), `TS` = `DATETIME`(UTC). 시뮬레이션 결과는 저장하지 않는다(거래·세법·설정의 함수).

---

## 1. `apt_region` — 행정구역 (FR-002)

| 열 | 형식 | 설명 |
|----|------|------|
| `code` | CHAR(10) PK | 법정동코드 10자리(`region_cd`). 시·도·시·군·구도 10자리(뒤가 0)로 둔다 |
| `level` | VARCHAR(8) | `sido` · `sgg` · `umd` |
| `parent_code` | CHAR(10) NULL | 상위 코드 |
| `lawd_cd` | CHAR(5) NULL | 실거래 요청 단위(시·군·구 5자리). `sgg`·`umd`에만 |
| `name` | VARCHAR(40) | 화면 이름 — 일반시 아래 구는 "수원시 장안구"처럼 붙인다 |
| `full_name` | VARCHAR(80) | 출처의 `locatadd_nm` |
| `source` | VARCHAR(16) | `stanregin` |
| `ingested_at` | TS | |
| `seen_at` | TS | 마지막 갱신에서 본 시각 |
| `retired_at` | TS NULL | 갱신에서 사라졌거나 출처가 폐지로 표시한 시각. 행은 지우지 않는다(과거 거래의 근거) |

- 리(`ri_cd ≠ 00`)는 넣지 않는다. 일반시 아래 구가 있으면 상위 시(예: 41110)는 `sgg` 목록에서 뺀다(research R9-3).
- **풀다운과 실거래 요청에는 `retired_at IS NULL`인 코드만 쓴다.** 출처는 과거 거래도 새 코드로만 준다 — 사라진 코드를 요청하면 0건이
  정상으로 온다(research R9-3 실측). 시·군·구 코드가 사라지면 그 `lawd_cd`의 거래를 `missing_since`(`missing_reason = region_retired`)로 집계에서
  빼고 그 커버리지를 쓰지 않는다 —
  새 코드의 수집이 전체 이력을 다시 받는다(같은 거래를 두 코드로 두 번 세지 않는다).
- 갱신 상태는 `apt_list_state`(8절).

## 2. `apt_complex` — 단지 (FR-003)

| 열 | 형식 | 설명 |
|----|------|------|
| `id` | BIGINT PK | |
| `umd_code` | CHAR(10) | 법정동 |
| `lawd_cd` | CHAR(5) | 시·군·구 |
| `apt_seq` | VARCHAR(20) NULL UNIQUE | 실거래 상세 자료의 단지 일련번호 — 실거래로 알게 된 단지 |
| `kapt_code` | VARCHAR(20) NULL UNIQUE | 단지 목록 자료의 단지 코드 — 단지 목록으로 알게 된 단지 |
| `name` | VARCHAR(80) | 화면 이름(단지 목록의 이름이 있으면 그것, 없으면 실거래의 최근 이름) |
| `jibun` | VARCHAR(20) NULL | 본번-부번(짝짓기 근거) |
| `move_in_year` | SMALLINT NULL | 사용승인 연도, 없으면 실거래의 건축년도 |
| `move_in_source` | VARCHAR(8) NULL | `move_in_year`를 얻은 자료 — `kapt`(사용승인일) · `trade`(건축년도) |
| `households` | INT NULL | 세대수(기본 정보). 모르면 NULL — 지어내지 않는다 |
| `details_checked_at` | TS NULL | 기본 정보를 받은 시각 |
| `merged_into` | BIGINT NULL | 다른 행에 합쳐졌으면 그 행의 `id` |
| `updated_at` | TS | |

- 두 자료의 같은 단지는 한 행이다 — `apt_seq`와 `kapt_code`를 함께 가진다. 짝짓기 규칙은 research R9-3(법정동 코드 + 지번, 아니면 정규화한
  이름). 짝짓지 못하면 각자 한 행.
- **단지 행은 지우지 않고 `id`는 바뀌지 않는다** — 이력이 단지 id를 저장한다(FR-032). 짝짓기는 있는 행에 다른 쪽 식별자를 붙이는 것으로 한다.
  두 행이 이미 따로 있을 때 짝이 드러나면 먼저 만든 행(`id`가 작은 쪽)에 합치고, 다른 행의 식별자(`apt_seq`·`kapt_code`)를 옮긴 뒤 `merged_into`에
  그 `id`를 적는다. 단지 id를 받는 모든 API는 `merged_into`를 따라간다 — 옛 id로 열어도 같은 단지다. 목록 응답에는 합쳐진 행이 나오지 않는다.
- 실거래의 단지명이 바뀌어도 `apt_seq`로 같은 행이다.
- **시·군·구 코드가 바뀌면 단지 행의 코드도 따라간다**(1절 `retired_at`). 새 코드로 받은 거래의 `apt_seq`가 같은 단지 행이 있으면 실거래 수집이
  그 행의 `umd_code`·`lawd_cd`를 새 코드로 바꾼다. 단지의 수집 여부 판정(202)과 수집 요청은 단지의 **현재** `lawd_cd`를 쓴다 — 그 `lawd_cd`가
  사라졌는데 아직 새 코드로 갱신되지 않았으면 시뮬레이션·평형·시계열은 409 `region_retired`다. 개편으로 출처의 단지 식별자(`apt_seq`)까지
  바뀌었으면 옛 행은 갱신되지 않고 계속 409이며 새 행은 새 단지로 보인다(research R9-3의 한계).

## 3. `apt_trade` — 거래 (FR-008, FR-009, FR-019)

| 열 | 형식 | 설명 |
|----|------|------|
| `id` | BIGINT PK | |
| `lawd_cd` | CHAR(5) | 요청 단위 |
| `deal_ym` | CHAR(6) | 계약 년월(요청한 `DEAL_YMD`) |
| `deal_date` | DATE | 계약일(한국 시간 달력) |
| `apt_seq` | VARCHAR(20) | 단지 일련번호 |
| `umd_code` | CHAR(10) | 법정동 코드(`sggCd + umdCd`) |
| `jibun` | VARCHAR(20) | 본번-부번 |
| `apt_name` | VARCHAR(80) | 그때의 단지명 |
| `apt_dong` | VARCHAR(20) | 동(없으면 빈 문자열) |
| `floor` | SMALLINT | 층(지하는 음수) |
| `excl_area` | AREA | 전용㎡ |
| `amount` | WON | 원 단위 정수(만원 × 10,000) |
| `occurrence` | SMALLINT | 같은 응답 안에서 위 필드가 모두 같은 행의 순번(0부터) |
| `dealing_type` | VARCHAR(8) NULL | `중개거래`·`직거래`, 2021-11 이전은 NULL |
| `cancelled` | BOOLEAN | 해제(`cdealType = O`) |
| `cancelled_on` | DATE NULL | 해제 신고일 |
| `missing_since` | TS NULL | 집계에서 빠진 시각 — 다시 받은 응답에서 사라졌거나 시·군·구 코드가 사라졌다 |
| `missing_reason` | VARCHAR(16) NULL | `missing_since`의 사유 — `absent`(다시 받은 응답에 없음) · `region_retired`(시·군·구 코드가 사라짐, 1절) |
| `source` | VARCHAR(16) | `molit:aptdev` |
| `ingested_at` | TS | 처음 받은 시각(upsert가 지키지 않는다) |
| `updated_at` | TS | |

- 유니크 (`lawd_cd`, `deal_date`, `apt_seq`, `apt_dong`, `floor`, `excl_area`, `amount`, `occurrence`) + upsert — 바뀔 수 있는 필드
  (`dealing_type`, `cancelled`, `cancelled_on`, `missing_since`)만 갱신한다(research R9-4).
- 인덱스 (`apt_seq`, `deal_date`) — 단지의 거래를 계약일 순으로 읽는다.
- 평형 구분은 저장하지 않는다 — `excl_area`와 FR-004의 경계표로 계산한다(경계가 바뀌어도 다시 받지 않는다).
- 집계는 `cancelled = false`이고 `missing_since IS NULL`인 행만 쓴다. 다시 받은 응답에서 사라진 행은 `missing_reason = absent`, 시·군·구 코드가
  사라지면(1절) 그 코드의 행은 `region_retired`다 — 나중에 왜 빠졌는지 가릴 수 있다.

## 4. `apt_raw_response` — 받은 원본 (헌법 원칙 V, FR-013)

| 열 | 형식 | 설명 |
|----|------|------|
| `id` | BIGINT PK | |
| `endpoint` | VARCHAR(24) | `trade` · `region` · `complex_list` · `complex_basis` |
| `request_ref` | VARCHAR(40) | 불투명한 참조(`11710/202409/p1`, `1171010700`, `A10027875`) — URL이 아니다 |
| `status_code` | SMALLINT | |
| `result_code` | VARCHAR(16) NULL | 출처의 결과 코드·게이트웨이 사유 |
| `body` | LONGTEXT | 응답 본문 그대로 — 요청 URL(키 포함)은 저장하지 않는다 |
| `body_sha256` | CHAR(64) | 본문의 SHA-256 |
| `received_at` | TS | |

인덱스 (`endpoint`, `request_ref`, `received_at`), (`received_at`). **같은 (`endpoint`, `request_ref`)의 마지막 원본과 `body_sha256`이 같으면 새 행을
만들지 않는다** — 다시 확인한 사실은 커버리지의 `checked_on`이 남긴다. 내용이 다른 판은 모두 남아 잠정→확정 변화를 추적할 수 있다(헌법 원칙
V). 송파구 95개월 원본이 약 15MB다(research R9-5) — 다시 받기의 대부분이 같은 본문이라 이 규칙이 누적을 막는다. 지우지 않는다(007·008과 같은
정책 — 1GB를 넘으면 정리 정책을 따로 정한다).

## 5. `apt_trade_coverage` — 받은 달 (FR-009, FR-010)

| 열 | 형식 | 설명 |
|----|------|------|
| `lawd_cd` | CHAR(5) PK | |
| `deal_ym` | CHAR(6) PK | |
| `state` | VARCHAR(12) | `confirmed`(잠정 기간 밖) · `provisional`(최근 12개월 — 설정) |
| `trade_rows` | INT | 그 달 받은 행 수(해제 포함) |
| `checked_on` | DATE | 마지막으로 받은 날(한국 시간) — **성공했을 때만** 바뀐다 |
| `updated_at` | TS | |

- 시·군·구의 첫 달은 `apt_list_state`의 `first_trade_ym`이다(처음 거래가 있는 달 — 발견해서 기록).
- 잠정 달의 다시 받기(research R9-5): **최근 3개월**(`APT_TRADE_DAILY_RECHECK_MONTHS`)은 `checked_on`이 오늘(한국 시간)이 아니면, **4~12개월
  전 달**은 `checked_on`이 이번 달이 아니면 다시 받는다. 날이 지나 잠정 기간(`APT_TRADE_PROVISIONAL_MONTHS`, 12)을 벗어나면 다음 확인에서 한 번
  더 받고 `confirmed`가 된다(그 뒤 다시 받지 않는다).
- **받아 둔 시·군·구** = 첫 달(`first_trade_ym`)부터 잠정 기간 앞 달까지 모든 달의 행이 있는 시·군·구. 잠정 달 다시 받기만 실패했을 때 받아 둔
  거래로 답하는(200 + `recheckFailed`) 조건이다(rest-api).

## 6. `apt_collection_job` · `apt_collection_lock` — 수집 작업 (FR-011, FR-012)

`apt_collection_job`: `id`, `lawd_cd`, `kind`(`trade` · `region` · `complex_details`), `months_total`, `months_done`(trade만), `items_total`,
`items_done`(complex_details), `status`(JobStatus), `started_at`, `finished_at`, `last_error`(종류를 앞에 둔다 — `auth`·`rate_limited`·
`format`·`network`, 사유는 키를 지운다).

`apt_collection_lock`: (`kind`, `target`) PK — 같은 시·군·구·같은 법정동의 중복 수집 방지. 기동 시 남은 점유를 회수한다(008과 같다).

## 7. `apt_api_usage` — 하루 호출 수 (FR-012, SC-012)

| 열 | 형식 | 설명 |
|----|------|------|
| `api` | VARCHAR(16) PK | `trade` · `region` · `kapt` |
| `kst_date` | DATE PK | 한국 시간 날짜 |
| `calls` | INT | 그날 보낸 요청 수(실패 포함) |

요청을 보내기 **전에** 1을 더하고 설정 한도를 넘으면 보내지 않는다. 프로세스를 다시 띄워도 이어 센다.

## 8. `apt_list_state` — 목록 갱신 상태

| 열 | 형식 | 설명 |
|----|------|------|
| `scope` | VARCHAR(20) PK | `regions`(전국) · `umd:1171010700`(그 동의 단지 목록) · `sgg:11710`(그 시·군·구의 실거래) |
| `refreshed_at` | TS NULL | 마지막 성공 |
| `first_trade_ym` | CHAR(6) NULL | `sgg:` 범위에서 처음 거래가 있는 달 |
| `updated_at` | TS |

`regions`와 `umd:`는 `refreshed_at`에서 30일(`APT_LIST_REFRESH_DAYS`)이 지나면 다시 받는다 — 행정구역은 처음 쓸 때 백그라운드로, 동의 단지
목록은 그 동을 처음 고를 때. 기본 정보는 새 단지만 받는다(세대수는 바뀌지 않는다). |

## 9. `apt_setting` — 부동산 설정 (FR-034)

| 열 | 형식 | 설명 |
|----|------|------|
| `id` | SMALLINT PK = 1 | 전역 단일 행 |
| `holding_tax_base_ratio` | SPREAD | 보유세 기준 비율, 기본 **0.600000**. 0 < 값 ≤ 1, 소수 6자리까지 |
| `updated_at` | TS | |

행이 없으면 기본값이다. 다른 자산군 설정과 따로다.

---

## 세법 표 (데이터 모듈 — 테이블이 아니다)

`backend/src/simulation/apt_tax_rules.py` — 시행일 구간마다 세목별 규칙 하나(research R9-7). 각 규칙은 `effective_from`, `effective_to`
(없으면 현행), 근거(법령·조문·시행일)를 가진다.

| 규칙 | 담는 값 |
|------|---------|
| 취득세 | 가액 구간별 세율(누진 산식 포함), 지방교육세율, 농어촌특별세(85㎡ 초과) |
| 중개 보수 | 가액 구간별 상한 요율과 한도액 |
| 재산세 | 공정시장가액비율(1세대 1주택 가액별), 세율 구간, 특례 세율, 지방교육세율, 도시지역분율, 7월 일괄 기준액 |
| 종부세 | 1인 공제액, 공정시장가액비율, 세율 구간, 재산세 중복분 산식의 매개변수, 농어촌특별세율 |

표가 덮지 않는 날짜를 물으면 `RuleNotCovered(세목, 날짜)`를 낸다 — 가까운 해로 대신하지 않는다(FR-023).

## 이력 (FR-032)

브라우저 저장소 키 `assetreplay:realestate-history:v1`(기존 형식). 항목: 단지 id·이름, 평형 구분, 매입일, 직접 넣은 매입가(없으면 null).
결과 수치는 없다.

## 상태 전이

```
coverage(달):   (없음) ──받음──▶ provisional(최근 12개월) ──잠정 기간을 벗어남 + 다시 받음──▶ confirmed
                                   │                                                        (다시 받지 않는다)
                                   ├──최근 3개월: 오늘 checked_on 아님 → 다시 받음(하루 한 번)
                                   └──4~12개월: 이번 달 checked_on 아님 → 다시 받음(한 달 한 번)
region(코드):   현존 ──갱신에서 사라짐·폐지 표시──▶ retired_at(풀다운·요청에서 뺌, 그 lawd_cd의 거래는 missing_since(region_retired))
complex(코드):  옛 lawd_cd ──새 코드로 받은 거래의 같은 apt_seq──▶ 새 umd_code·lawd_cd (갱신 전에는 409 region_retired)
complex(행):    따로 있는 두 행의 짝이 드러남 ──▶ 먼저 만든 행에 합침, 다른 행은 merged_into(지우지 않음)
trade(행):      받음 ──해제 표시──▶ cancelled ─┐
                받음 ──다시 받은 응답에 없음──▶ missing_since(absent) ─┤
                받음 ──시·군·구 코드가 사라짐──▶ missing_since(region_retired) ─┴─▶ 집계에서 뺀다(행은 지우지 않는다)
job:            running ──▶ succeeded | failed(종류: auth·rate_limited·format·network)
                (기동 시 남은 running → failed(network, "점유 회수"))
```
