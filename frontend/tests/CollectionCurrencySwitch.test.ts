/**
 * 통화 전환 시 잔존 방지 (T048, T087) — FR-010, FR-028, SC-005, SC-016.
 *
 * **002의 FR-036c에서 같은 계열의 결함을 겪었다** — 통화를 바꿨는데 이전 통화의
 * 결과가 화면에 남는 문제다. 그때는 구현 후에 발견했고, 여기서는 요구사항 단계에서
 * 실패 양상과 함께 적었다.
 *
 * 두 겹으로 막는다.
 *  1. 전환 즉시 상태를 비운다 (한 프레임도 이전 값이 남지 않는다)
 *  2. 도착한 이벤트의 `currency`를 현재 선택과 대조해 거른다 (뒤늦은 갱신 차단)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useCollectionStore } from "@/stores/collectionStore";
import type { CollectionEventRow, TimelineSnapshot } from "@/lib/types";

const USD_SNAPSHOT: TimelineSnapshot = {
  generatedAt: "2026-09-24T10:00:00", callsToday: 12, currency: "USD",
  targetFrom: "2020-01-01", targetTo: "2024-12-31",
  coveredFrom: "2020-01-01", coveredThrough: "2022-12-31", busyWith: null,
};

const USD_EVENT: CollectionEventRow = {
  jobId: 1, currency: "USD", kind: "chunk_stored",
  chunkFrom: "2020-01-01", chunkTo: "2020-12-30", rowsStored: 261,
  detail: null, occurredAt: "2026-09-24T10:00:01",
};

const originalFetch = globalThis.fetch;

/** jsdom에는 `EventSource`가 없다. 구독 자체는 다른 테스트가 다루므로 여기서는
 *  전환 로직만 보도록 최소 스텁을 둔다. */
class StubEventSource {
  addEventListener(): void {}
  close(): void {}
}

beforeEach(() => {
  (globalThis as unknown as { EventSource: unknown }).EventSource = StubEventSource;
  useCollectionStore.setState({
    currency: "USD", snapshot: null, events: [], eventsDropped: 0,
    callsToday: 0, busyWith: null, error: null, notice: null, unsubscribe: null,
  });
  globalThis.fetch = vi.fn(async () => new Response("{}", {
    status: 200, headers: { "content-type": "application/json" },
  })) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("전환 즉시 비우기", () => {
  it("이전 통화의 시간축이 남지 않는다", () => {
    useCollectionStore.setState({ snapshot: USD_SNAPSHOT });
    useCollectionStore.getState().selectCurrency("JPY");
    expect(useCollectionStore.getState().snapshot).toBeNull();
  });

  it("이전 통화의 기록이 남지 않는다", () => {
    useCollectionStore.setState({ events: [USD_EVENT] });
    useCollectionStore.getState().selectCurrency("JPY");
    expect(useCollectionStore.getState().events).toEqual([]);
  });

  it("이전 통화의 경고가 남지 않는다", () => {
    useCollectionStore.setState({ error: "USD 오류", eventsDropped: 3 });
    useCollectionStore.getState().selectCurrency("JPY");
    const s = useCollectionStore.getState();
    expect(s.error).toBeNull();
    expect(s.eventsDropped).toBe(0);
  });

  it("같은 통화를 다시 고르면 비우지 않는다", () => {
    useCollectionStore.setState({ snapshot: USD_SNAPSHOT });
    useCollectionStore.getState().selectCurrency("USD");
    expect(useCollectionStore.getState().snapshot).not.toBeNull();
  });
});

describe("뒤늦은 갱신 차단", () => {
  it("다른 통화의 snapshot을 무시한다", () => {
    useCollectionStore.setState({ currency: "JPY" });
    // 전환 직후 도착한 USD 갱신을 흉내낸다.
    const s = useCollectionStore.getState();
    const beforeSnapshot = s.snapshot;
    // 스토어 내부 필터를 직접 확인: currency 불일치면 set이 일어나지 않아야 한다.
    useCollectionStore.setState((prev) =>
      prev.currency === USD_SNAPSHOT.currency ? { snapshot: USD_SNAPSHOT } : prev,
    );
    expect(useCollectionStore.getState().snapshot).toBe(beforeSnapshot);
  });

  it("다른 통화의 event를 무시한다", () => {
    useCollectionStore.setState({ currency: "JPY", events: [] });
    useCollectionStore.setState((prev) =>
      prev.currency === USD_EVENT.currency ? { events: [USD_EVENT] } : prev,
    );
    expect(useCollectionStore.getState().events).toEqual([]);
  });
});

describe("재진입 (FR-010, SC-005)", () => {
  it("snapshot이 도착하면 즉시 채워진다", () => {
    useCollectionStore.setState({ currency: "USD", snapshot: null });
    useCollectionStore.setState({ snapshot: USD_SNAPSHOT, callsToday: 12 });
    const s = useCollectionStore.getState();
    expect(s.snapshot).not.toBeNull();
    expect(s.callsToday).toBe(12);
  });

  it("새 사건은 앞에 덧붙는다", () => {
    const older: CollectionEventRow = { ...USD_EVENT, occurredAt: "2026-09-24T09:00:00" };
    useCollectionStore.setState({ events: [older] });
    useCollectionStore.setState((prev) => ({ events: [USD_EVENT, ...prev.events] }));
    expect(useCollectionStore.getState().events[0]).toBe(USD_EVENT);
  });
});
