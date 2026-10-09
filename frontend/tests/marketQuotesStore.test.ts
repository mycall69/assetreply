/**
 * 대시보드 시세 스토어 (014 T027) — FR-008, FR-009, FR-010, research R14-15.
 *
 * - 응답의 `refreshAfterSeconds`마다 다시 부른다. 화면이 보이지 않는 동안은 부르지 않고, 다시 보이면 곧바로 부른다
 *   (보이지 않는 탭이 계속 부르면 출처 한도를 낭비한다 — FR-008 실패 양상)
 * - 늦게 온 옛 응답은 버린다(`seq`)
 * - `startPolling`을 두 번 불러도 타이머는 하나다 — 대시보드에서 지표 화면으로 옮겨도 갱신이 두 번 걸리지 않는다(U1)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { DashboardQuotesResponse } from "@/lib/types";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { quotesOf } from "./support/dashboardFixtures";

let visibility: DocumentVisibilityState = "visible";

function setVisibility(next: DocumentVisibilityState) {
  visibility = next;
  document.dispatchEvent(new Event("visibilitychange"));
}

const quoteCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.filter(([p]) => p === "/api/dashboard/quotes").length;

beforeEach(() => {
  vi.useFakeTimers();
  visibility = "visible";
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("불러오기", () => {
  it("성공하면 ready와 응답", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().load();
    const s = useMarketQuotesStore.getState();
    expect(s.status).toBe("ready");
    expect(s.data?.indicators).toHaveLength(15);
  });

  it("실패하면 error와 문구, 받아 둔 응답은 남긴다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(quotesOf());
    await useMarketQuotesStore.getState().load();
    get.mockRejectedValueOnce(new Error("down"));
    await useMarketQuotesStore.getState().load();
    const s = useMarketQuotesStore.getState();
    expect(s.status).toBe("error");
    expect(s.error).toBe("지표 시세를 불러오지 못했습니다.");
    expect(s.data).not.toBeNull();
  });

  it("늦게 온 옛 응답은 버린다", async () => {
    let releaseOld: (v: DashboardQuotesResponse) => void = () => undefined;
    const old = new Promise<DashboardQuotesResponse>((r) => { releaseOld = r; });
    const fresh = quotesOf({ kospi: { stale: true } });
    vi.spyOn(apiClient, "get").mockReturnValueOnce(old).mockResolvedValueOnce(fresh);
    const first = useMarketQuotesStore.getState().load();
    await useMarketQuotesStore.getState().load();
    releaseOld(quotesOf());
    await first;
    expect(useMarketQuotesStore.getState().data?.indicators[0].stale).toBe(true);
  });
});

describe("주기 갱신", () => {
  it("refreshAfterSeconds마다 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().load();
    useMarketQuotesStore.getState().startPolling();
    await vi.advanceTimersByTimeAsync(59_000);
    expect(quoteCalls(get)).toBe(1);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(quoteCalls(get)).toBe(2);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(quoteCalls(get)).toBe(3);
  });

  it("보이지 않는 동안은 부르지 않고, 다시 보이면 곧바로 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().load();
    useMarketQuotesStore.getState().startPolling();
    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(180_000);
    expect(quoteCalls(get)).toBe(1);
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(quoteCalls(get)).toBe(2);
  });

  it("startPolling을 두 번 불러도 타이머는 하나", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().load();
    useMarketQuotesStore.getState().startPolling();
    useMarketQuotesStore.getState().startPolling();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(quoteCalls(get)).toBe(2);
  });

  it("stopPolling 뒤에는 부르지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().load();
    useMarketQuotesStore.getState().startPolling();
    useMarketQuotesStore.getState().stopPolling();
    await vi.advanceTimersByTimeAsync(300_000);
    setVisibility("visible");
    expect(quoteCalls(get)).toBe(1);
  });

  it("다시 시도는 같은 경로를 다시 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(quotesOf());
    await useMarketQuotesStore.getState().retry();
    expect(quoteCalls(get)).toBe(1);
  });
});
