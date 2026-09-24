# Contract: REST·SSE — 003

**Feature**: 003-fx-collection-runtime | **Date**: 2026-09-24

001·002가 정의한 엔드포인트는 그대로 둔다. 이 문서는 **신규와 변경분만** 다룬다.

모든 응답은 JSON, 날짜는 `YYYY-MM-DD`, 시각은 ISO 8601이다. 001의 공통 오류표를 따른다.

---

## 1. `POST /api/fx/collect` — 동작 변경 (경로·형식 불변)

**요청·응답 형식은 001과 동일하다.** 바뀌는 것은 서버가 실제로 수집을 실행한다는 점이다.

기존에는 작업 행을 만들고 점유만 잡은 뒤 202를 돌려주고 아무것도 실행하지 않았다. 이제 202를
돌려준 뒤 **백그라운드 태스크가 수집을 시작한다**(FR-001).

```json
{ "jobs": [ { "currency": "USD", "jobId": 42, "joinedExisting": false } ] }
```

| 필드 | 의미 |
|------|------|
| `joinedExisting` | `true`면 이미 진행 중인 작업이 있어 새로 시작하지 않고 합류했다 (FR-003) |

**요청 본문은 통화를 반드시 포함한다** (2026-09-24 반복). 001은 본문을 생략하면 전 통화를
시작하지만, **003 화면은 그 경로를 쓰지 않는다.** 001의 동작 자체는 바꾸지 않으며, 화면이
노출하지 않을 뿐이다.

```json
{ "currency": "USD" }
```

**계약상 보장**

- 202를 받은 뒤 클라이언트가 연결을 끊어도 수집은 계속된다(FR-001).
- **다른 통화의 수집이 진행 중이면 409 `collection_in_progress`로 거절하고, 어느 통화가
  진행 중인지 본문에 담는다**(FR-029). 조용히 무시하면 사용자는 버튼이 고장난 것으로 여긴다.
- 대상 구간이 이미 전부 수집됐으면 외부 호출 없이 즉시 완료된다(FR-009). 이 경우에도 작업은
  생성되며 `succeeded`로 끝난다 — 사용자가 "눌렀는데 아무 일도 없었다"고 느끼지 않게 한다.

---

## 2. `GET /api/fx/collection/timeline` [신규]

**선택한 통화**의 시간축 시각화에 필요한 값을 내려준다(FR-012, FR-027, R3-6).

**질의 매개변수**

| 이름 | 필수 | 설명 |
|------|------|------|
| `currency` | **예** | 조회할 통화. 누락 시 400 `invalid_query` |

**응답**

```json
{
  "generatedAt": "2026-09-24T07:40:00+09:00",
  "callsToday": 37,
  "currency": "USD",
  "targetFrom": "1995-01-04",
  "targetTo": "2026-09-23",
  "coveredFrom": "1995-01-04",
  "coveredThrough": "2024-03-15",
  "activeJob": {
    "jobId": 42,
    "rangeStart": "2024-03-16",
    "chunksTotal": 3,
    "chunksDone": 1,
    "currentChunk": { "from": "2025-03-16", "to": "2026-03-15" },
    "state": "running"
  },
  "busyWith": null
}
```

| 필드 | 의미 |
|------|------|
| `callsToday` | 오늘 데이터 출처를 호출한 수 (FR-024). **참고 지표**이며 한도 판정 근거가 아니다 |
| `targetFrom` / `targetTo` | 시간축의 양 끝. `targetTo`는 항상 어제다 |
| `coveredFrom` / `coveredThrough` | 채워진 구간. 한 번도 수집하지 않았으면 둘 다 `null` |
| `rangeStart` | **이어받기 지점** (FR-011). 이번 작업이 어디서부터 시작했는가 |
| `currentChunk` | 지금 받고 있는 구간 (FR-013). 저장하지 않고 계산한다 |
| `state` | `running` · `stalled` · `awaiting_reclaim` (아래 표) |
| `busyWith` | **다른** 통화가 수집 중이면 그 통화 코드. 없으면 `null` (FR-029) |

`activeJob`은 **선택한 통화가 진행 중일 때만 포함한다.** 값이 없을 때 키를 넣지 않는 것은
002가 세운 규약을 잇는다 — 정상 상태에 빈 객체를 두면 화면이 존재 여부가 아니라 내용을
검사해야 한다.

`busyWith`는 다르다. **선택한 통화가 아닌 다른 통화가 수집 중**임을 알리는 값이라, 화면이
시작 버튼을 막고 이유를 보여주는 근거가 된다(FR-029). 없을 때는 `null`을 명시한다 — 이 값은
"확인했고 없다"와 "확인하지 않았다"가 구별되어야 한다.

### `state` 값

| 값 | 조건 | 화면 의미 |
|----|------|-----------|
| `running` | 하트비트 60초 이내 | 정상 진행 중 |
| `stalled` | 하트비트 60초 초과, 900초 이내 | 응답 없음 — 회수 대기 중 (FR-006, FR-006a) |
| `awaiting_reclaim` | 하트비트 900초 초과 | 회수 대상. 곧 부분 완료로 확정된다 |

세 값을 나누는 이유는 FR-006a가 요구하는 "회수를 기다리는 중"을 표현하기 위해서다. `stalled`와
`awaiting_reclaim`을 합치면 사용자가 기다려야 하는지 아닌지 알 수 없다.

---

## 3. `GET /api/fx/collection/stream` [신규] — 수집 스트림 (SSE)

**선택한 통화**의 진행을 내보낸다(R3-7, FR-027). 001의 작업별 스트림
`GET /api/fx/progress?jobId=`는 그대로 유지한다.

**질의 매개변수**: `currency` (필수). 누락 시 400 `invalid_query`

통화를 전환하면 클라이언트가 기존 연결을 닫고 새 통화로 다시 연다. **이전 연결의 뒤늦은
이벤트가 새 화면에 반영되어서는 안 된다**(FR-028) — 이벤트에 실린 `currency`를 현재 선택과
대조해 거른다.

**미디어 타입**: `text/event-stream`
**헤더**: `Cache-Control: no-cache`, `X-Accel-Buffering: no`

### 이벤트: `snapshot`

연결 직후 1회, 이후 상태가 바뀔 때마다 보낸다. 본문은 위 `timeline` 응답과 **같은 구조**다.

```
event: snapshot
data: {"generatedAt":"...","callsToday":37,"currencies":[...]}

```

같은 구조를 쓰는 이유는 화면이 최초 진입(REST)과 이후 갱신(SSE)에서 서로 다른 형태를 다루지
않게 하기 위해서다. 재진입 시 즉시 따라잡아야 한다는 FR-010이 이 구조로 충족된다.

### 이벤트: `event`

새 수집 사건이 생길 때마다 보낸다(FR-022).

```
event: event
data: {"jobId":42,"currency":"USD","kind":"chunk_stored","chunkFrom":"2024-03-16","chunkTo":"2025-03-15","rowsStored":261,"occurredAt":"..."}

```

### 이벤트: `idle`

선택한 통화의 수집이 없을 때 보낸다. 연결은 유지한다.

```
event: idle
data: {"currency":"USD","callsToday":37,"busyWith":"JPY"}

```

`busyWith`가 있으면 다른 통화가 돌고 있다는 뜻이다. 화면은 시작 버튼을 막는다(FR-029).

**하트비트**: 상태 변화가 없어도 5초마다 `snapshot`을 보낸다. SC-004(10초 이내 갱신)의 근거다.

**종료하지 않는다**: 001의 작업별 스트림은 작업이 끝나면 닫히지만, 이 스트림은 화면이 열려
있는 동안 유지된다. 사용자가 새 수집을 시작하면 같은 연결로 이어진다. **이것이 001의 스트림을
재사용할 수 없는 이유다**(research R3-7).

---

## 4. `GET /api/fx/collection/events` [신규]

종료된 작업의 사건을 사후 조회한다(FR-022).

**질의 매개변수**

| 이름 | 필수 | 설명 |
|------|------|------|
| `jobId` | 택일 | 특정 작업의 사건 |
| `currency` | 택일 | 통화의 최근 사건 |
| `limit` | 아니오 | 기본 100, 최대 500 |

`jobId`와 `currency` 중 하나는 있어야 한다. 둘 다 없으면 `400 invalid_query`.

**응답**

```json
{
  "events": [
    {
      "jobId": 42,
      "currency": "USD",
      "kind": "chunk_stored",
      "chunkFrom": "2024-03-16",
      "chunkTo": "2025-03-15",
      "rowsStored": 261,
      "occurredAt": "2026-09-24T07:31:02+09:00"
    }
  ],
  "retention": { "jobsKept": 20 },
  "eventsDropped": 0
}
```

| 필드 | 의미 |
|------|------|
| `retention.jobsKept` | 보관 범위. 화면이 "왜 오래된 게 없는지" 설명할 수 있게 한다 (FR-023) |
| `eventsDropped` | 해당 작업에서 기록에 실패한 사건 수. **0보다 크면 이 기록은 불완전하다** (FR-018b) |

`eventsDropped`는 `jobId`로 조회할 때만 의미가 있다. `currency`로 조회하면 범위 내 작업들의
합을 돌려준다.

---

## 5. 오류

001의 공통 오류표를 따른다. 이번 기능이 더하는 것은 없다.

| 상황 | 상태 | `status` |
|------|------|----------|
| 지원하지 않는 통화 | 404 | `unknown_currency` |
| `jobId`·`currency` 모두 누락 | 400 | `invalid_query` |
| 존재하지 않는 작업 | 404 | `unknown_job` |
| 다른 통화가 수집 중 | 409 | `collection_in_progress` |
| 출처 한도 소진 | 503 | `source_rate_limited` |

**한도 소진은 수집 시작 요청의 오류가 아니다.** 수집 도중 발생하므로 202로 시작된 작업이
`partial`로 끝나고 사유가 남는다(FR-025a). 위 503은 시작 시점에 이미 소진이 확인된 경우에만
쓴다.
