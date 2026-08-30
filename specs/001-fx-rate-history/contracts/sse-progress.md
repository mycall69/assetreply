# Contract: 수집 진행률 스트림 (SSE)

**Feature**: 001-fx-rate-history | **Date**: 2026-08-30

FR-008, FR-034, SC-009를 충족한다. WebSocket이 아닌 SSE를 쓰는 근거는 research R4.

## GET `/api/fx/progress`

> 이 엔드포인트는 User Story 4에서 구현된다. 그 이전 단계에서는 `202` 응답에
> `progressUrl`이 포함되지 않는다 (rest-api.md 202 절 참조).

**Query**: `jobId` (선택 — 생략 시 진행 중인 전체 작업)
**Content-Type**: `text/event-stream`

### `event: progress`

진행 중 주기적으로 전송한다. **연속 전송 간격은 10초를 넘지 않는다** (SC-009).
진행에 변화가 없어도 하트비트 성격으로 전송해 클라이언트가 정지로 오인하지 않게 한다.

```text
event: progress
data: {"jobId":42,"currency":"USD","status":"running","chunksTotal":32,
       "chunksDone":18,"currentRange":{"from":"2013-01-01","to":"2013-12-31"},
       "coveredThrough":"2012-12-31","lastError":null}
```

### `event: completed`

```text
event: completed
data: {"jobId":42,"currency":"USD","status":"succeeded","chunksDone":32,
       "coveredThrough":"2026-08-29","finishedAt":"2026-08-30T00:31:10.000Z"}
```

`status`는 `succeeded` | `partial` | `failed`. `partial`·`failed`일 때 `lastError`에 사유가 담긴다
(FR-013). 이미 커밋된 구간은 유효하므로 `coveredThrough`는 중단 지점을 가리킨다.

### `event: error`

스트림 자체의 오류(작업 없음, 조회 불가). 수집 실패는 `completed`로 전달되며 여기 오지 않는다.

## 클라이언트 동작

- 브라우저 `EventSource`의 기본 재연결에 의존한다. 재연결 시 서버는 해당 작업의 현재 상태를
  `progress` 이벤트로 즉시 1회 전송해 클라이언트가 공백 없이 따라잡게 한다.
- 진행 중인 작업이 없으면 `completed`를 즉시 보내고 스트림을 닫는다.
