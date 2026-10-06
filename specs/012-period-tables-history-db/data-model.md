# Data Model: 012

**Date**: 2026-10-06 | **Research**: [research.md](./research.md)

## 1. DB — 새 테이블 둘 (마이그레이션 하나)

Alembic 리비전 하나(`down_revision = "f4c2a8e19d35"`, 파일 이름 `<rev>_시뮬레이션_이력.py`). 기존 테이블은 바뀌지 않는다.

### 1.1 `simulation_history`

| 열 | 타입 | 제약 | 뜻 |
|----|------|------|----|
| `asset_class` | `Enum("stock","crypto","deposit","realestate", native_enum=False, length=16)` | PK | 자산군 |
| `condition_key` | `String(255)` | PK | 조건 식별자 — 서버가 조건에서 계산(2절). API의 `id` |
| `condition` | `Text` | NOT NULL | 조건 — 서버가 정해진 차례로 직렬화한 JSON 글(2절) |
| `last_run_at` | `DateTime(timezone=False)` | NOT NULL | 마지막 실행 시각(UTC). 목록 차례 |
| `retain_from` | `DateTime(timezone=False)` | NOT NULL | 보관 기준 시각(UTC) — 마지막 실행 시각, 옮긴 항목은 옮긴 시각(spec FR-012) |

- 기본 키: `(asset_class, condition_key)` — 같은 조건은 한 행이다. `db/dialect.upsert`가 기본 키로 충돌을 가르므로 따로 된 유일 키를 두지 않는다
  (구현 중 확인 — PostgreSQL의 `ON CONFLICT` 대상도 기본 키다)
- 색인: `ix_simulation_history_list (asset_class, last_run_at)` — 목록·차례
- 결과를 담지 않는다(spec FR-011 — 005 R5-9).

**상태 전이**:
- 실행(PUT) — 없으면 넣고, 있으면 `last_run_at = retain_from = 지금`이다. `condition`은 새로 쓴다(같은 식별자면 같은 조건이다).
- 옮기기(import) — 없으면 `last_run_at = savedAt`(없거나 읽을 수 없으면 지금), `retain_from = 지금`으로 넣는다. 있으면 둘 다 큰 쪽이다(spec FR-013).
- 삭제(DELETE) — 행을 지운다.
- 정리 — `retain_from < 지금 − 기간`인 행을 지운다(무기한이면 하지 않는다). 목록·저장·옮기기·설정 저장 때 먼저 한다(research R12-10).

### 1.2 `history_setting`

| 열 | 타입 | 제약 | 뜻 |
|----|------|------|----|
| `id` | `SmallInteger` | PK, 기본 1 | 단일 행 |
| `retention` | `Enum("days_7","days_30","days_90","days_180","days_365","unlimited", native_enum=False, length=16)` | NOT NULL | 보관 기간 |
| `updated_at` | `DateTime` | `server_default now()`, `onupdate` | 다른 설정 테이블과 같다 |

- 행이 없으면 기본 `days_30`이다(코드의 `Final` 상수 `DEFAULT_RETENTION`).
- API는 일 수로 말한다 — `7·30·90·180·365`, 무기한은 `null`(contracts/rest-api.md 5).

## 2. 조건 — 자산군마다의 칸과 식별자 규칙

서버(`api/services/history_conditions.py` — 순수 함수)가 검증하고 식별자를 계산한다. 식별자 규칙은 지금 화면 lib의 규칙과 **글자까지 같다**. 옮긴
항목의 식별자가 바뀌지 않는다는 것을 지금 화면 테스트의 식별자 예시로 대조 테스트한다.

| 자산군 | 칸 (필수 · 선택) | 식별자 |
|--------|-------------------|--------|
| `stock` | `stock{market,symbol,name,currency}` · `start` · `principal` · `principalCurrency` · `reinvest` / 선택 `mode:"recurring"` · `frequency` | `market\|symbol\|start\|principal\|principalCurrency\|R`(재투자 끔이면 `N`) + 적립식이면 `\|recurring:{frequency}` |
| `crypto` | `coin{coinId,symbol,name,nameKo?,slug,currency}` · `start` · `principal` · `principalCurrency` / 선택 `mode` · `frequency` | `coinId\|start\|principal\|principalCurrency` + 적립식이면 `\|recurring:{frequency}` |
| `deposit` | `institution` · `start` · `principal` / 선택 `product:"installment"` | `institution\|start\|principal` + 적금이면 `\|installment` |
| `realestate` | `complexId` · `complexName` · `umd` · `area` · `areaLabel` · `buyDate` · `buyPrice`(문자열 또는 `null`) | `complexId\|area\|buyDate\|{buyPrice 또는 "market"}` |

**검증 규칙** — 어기면 PUT은 422 `invalid_history`이고, 옮기기에서는 그 항목을 건너뛴다.
- 날짜(`start`·`buyDate`)는 ISO 날짜다.
- `principal`·`buyPrice`는 0보다 큰 십진 문자열이다. 서버가 계산하지 않고 받은 글자 그대로 둔다.
- `frequency`는 `daily·weekly·monthly·yearly`다. `mode`는 `recurring`이고, 그 밖의 방식은 칸을 두지 않는다(일시금).
- 문자열 칸의 길이는 각각 200 이하다. 식별자는 255 이하다.

**011 전 형식** — `mode`·`frequency`·`product` 칸이 없는 항목이다. 그대로 저장하고 그대로 돌려준다. 다시 실행·비교·표기는 지금처럼 쓰는 곳에서 기본값(일시금·
`monthly`·정기예금)을 준다(011 FR-033).

## 3. 기간 표 — 순수 모듈 `simulation/period_table.py`

### 3.1 달력

| 함수 | 입력 → 출력 | 규칙 |
|------|-------------|------|
| `period_bounds(day, unit)` | 날짜, `daily·weekly·monthly` → (처음, 끝) | 주 = 월~일, 월 = 1일~말일, 일 = 그날 |
| `anchor_of(day, unit)` | → 기준일 | 주 = 그 주 금요일, 월 = 그 달 말일, 일 = 그날 |
| `is_ongoing(period_to, end, unit)` | → bool | 일 단위는 거짓. 그 밖은 `period_to > end` |

### 3.2 표 만들기

```text
build_table(
  quote_days: Sequence[date],          # 계산 기간 안의 시세일(오름차순) — 첫 평가일 ~ 기준일
  event_days: Collection[date],        # 사건이 있는 날
  unit: PeriodUnit,
  end: date,                           # 계산 끝
  missing: Sequence[tuple[date, date]] = (),   # 가상자산 일 단위의 결측 구간(처음, 끝)
) -> list[TableEntry]                  # 최신순, 날짜마다 하나

TableEntry(kind, date, shifted_from: date | None, is_ongoing: bool, date_to: date | None)
  kind = "events"   # 그날의 사건 행 묶음 — 서비스가 사건 행들로 펼친다. 표시는 그날의 마지막 사건 행이 진다
       | "period"   # 하루하루 상태의 그날 값
       | "missing"  # 결측 구간(date ~ date_to)
```

사건 묶음을 날짜 하나로 두므로 쪽(3.3)이 같은 날의 사건 행을 가를 수 없다. 펼치기와 표시 붙이기는 `api/services/table_rows.table_page`가 한다 — 일시금은
같은 날의 행이 처리 차례로 놓여 마지막 행이, 적립식은 늦은 사건이 위라 첫 행이 그날의 마지막 사건 행이다.

**불변식** — 단위 테스트가 고정한다.
- 모든 사건 행이 단위와 관계없이 한 번씩 나온다(SC-003).
- 기간 하나에 대표 항목은 하나다. 대표일에 사건이 있으면 기간 행은 없고, 표시는 사건 묶음(펼치면 그날의 마지막 사건 행)이 진다(research R12-5).
- `shifted_from`은 대표일 ≠ 기준일일 때만 있다(spec FR-004·SC-002).
- 대표일은 주 단위에서 "금요일 이하의 마지막 시세일", 없으면 "그 주의 마지막 시세일"이다(research R12-3).
- `is_ongoing`은 주·월에서 구간 끝 > 계산 끝일 때만이다.
- `missing`은 `unit == daily`일 때만 들어간다. 입력 구간 수 = 출력 결측 행 수다.
- 첫 평가일 전 날짜의 `Period`·`Event`는 없다(`quote_days`가 그렇게 들어온다). `Missing`은 차트와 같은 구간이라 첫 평가일 앞에도 있을 수 있다.
- 값을 만들지 않는다 — 날짜만 고른다(원칙 V).

### 3.3 쪽

`page(entries, before, limit) -> (list[TableEntry], has_more)` — `date < before`인 항목을 최신순으로 `limit`개 자른다. **같은 날의 항목은 한 쪽에 붙잡는다.**
`Missing`의 커서 날짜는 `date_from`이다. 쪽이 비지 않으면 `oldestReturned` = 마지막 항목의 커서 날짜다.

## 4. 하루하루 상태 — 계산 모듈의 더함

| 모듈 | 더하는 칸 | 뜻 |
|------|-----------|----|
| `reinvest.Outcome` | `daily: tuple[Row, ...] = ()` | 첫 매수일부터 일봉마다, 그날 사건을 모두 처리한 뒤의 상태(`kind = "day"`). 매수일 행에만 `bought_shares`·`trade_fee`가 있다 |
| `recurring_stock.RecurringOutcome` | `daily: tuple[RecurringRow, ...] = ()` | 첫 납입일부터 일봉마다, 같은 시점의 상태(`kind = "day"` — `RowKind`에 더한다) |
| `crypto_hold.HoldOutcome` | (있음) `daily` | 그대로 |
| `recurring_crypto.RecurringCryptoOutcome` | (있음) `daily` | 그대로 |

- `rows`·`latest`는 바뀌지 않는다(주식 차트·보드의 재료 — spec FR-007·FR-017).
- 불변식 테스트
  - 월 행(`month_first`)이 있는 날은 `daily`의 그날 상태와 값이 같다.
  - `daily[-1]`은 `latest`와 값이 같다.
  - `daily`의 날짜는 계산 기간 안의 시세일과 같다.

**서비스의 조립** — 표 넷이 같다.
1. 사건 행을 모은다.
   - 일시금은 `buy` — 매수일의 월 행이다. 수수료가 있으므로 `daily` 대신 쓴다.
   - 그 밖은 `dividend`·`reinvest`·`contribution`이다.
2. 계산 기간 안의 시세일과 사건이 있는 날을 `build_table`에 넘긴다. 가상자산 일 단위는 `compute_gaps(…, inside_reason="source_missing")` 구간도 넘긴다
   — 시계열 경로와 같은 입력이다.
3. `page`로 자른다.
4. 쪽의 항목만 행으로 바꾼다.
   - `Event`는 그 사건 행, `Period`는 `daily`의 그날 상태(`kind = "period"`), `Missing`은 값 없는 행이다.
   - 원화 환산·환율 칸은 이때 붙인다.

## 5. 화면 상태

### 5.1 표 단위 (`stockStore`·`cryptoStore`)

| 칸 | 처음 | 뜻 |
|----|------|----|
| `tablePeriod` | `"daily"` | 고른 단위. 다시 실행해도 남는다. 새로 고치면 처음 값이다 |
| `tableSeq` | `0` | 표 요청 차례 번호. 실행·단위 전환마다 올린다. 응답의 번호가 지금과 다르면 버린다(이어 받기 포함) |
| `setTablePeriod(p)` | — | 일시금·적립식 중 지금 결과의 표만 다시 받는다. 행·`hasMore`·`oldestReturned`만 비우고 바꾼다. 보드·요약·시계열은 그대로다 |

요청 문자열에는 `tablePeriod !== "daily"`일 때만 `&period=`를 더한다(research R12-7).

### 5.2 이력 (`stockStore`·`cryptoStore`·`depositStore`·`realEstateStore`)

| 칸 | 처음 | 뜻 |
|----|------|----|
| `history` | `[]` | 서버 목록(지금과 같은 항목 모양 + 서버 `id`) |
| `historyLoading` | `true` | 첫 목록이 오기 전. 빈 상태 문구를 숨긴다 |
| `historyLoadError` | `null` | 옮기기·목록 실패(spec FR-014a) |
| `historySaveError` | `null` | 저장·삭제 실패(지금 칸 — 문구만 바뀐다) |
| `historyNotice` | `null` | 옮기지 못한 항목 수 알림 |
| `retentionDays` | `null` | 목록 응답의 보관 기간(안내 문구 — `null`이면 무기한) |

**행동**
- `restoreHistory()`(비동기)는 옮기기 → 목록이다(research R12-11). 다시 시도도 같은 행동이다.
- 저장은 200 결과 뒤 `PUT`이다. 응답 목록으로 `history`를 바꾼다.
- `removeHistoryEntry`는 `DELETE`다.
- 다시 실행·비교는 지금 그대로다(서버 `id`로 찾는다).
- 목록을 받을 때마다 `selectedHistory`를 목록에 있는 `id`로 줄인다. `comparison`은 건드리지 않는다(spec Edge Cases — 비교에 쓰인 항목이 기간 지나 지워짐).

### 5.3 브라우저 옛 키 (`lib/legacyHistory.ts`)

| 자산군 | 키 |
|--------|----|
| stock | `assetreplay:stock-history:v1` |
| crypto | `assetreplay:crypto-history:v1` |
| deposit | `assetreplay.depositHistory.v1` |
| realestate | `assetreplay:realestate-history:v1` |

- `readLegacy(asset)` → `{status: "none"} | {status: "unreadable"} | {status: "entries", entries}`
- `clearLegacy(asset)`는 그 키만 지운다.

### 5.4 원금 기본값

`DEFAULT_PRINCIPAL = "10000000"`(`lib/principalFormat.ts`)은 `stockStore`·`cryptoStore`·`depositStore`의 처음 `input.principal`이다. 그 밖의 입력 흐름은
바뀌지 않는다(research R12-14).
