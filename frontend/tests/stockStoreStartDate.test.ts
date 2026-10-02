/**
 * 시작일 상태 (T058) — 006 FR-001, FR-005a, FR-006.
 *
 * **종목을 바꿔도 시작일은 유지된다.** 기본값으로 되돌리면 같은 시작일로 두 종목을 비교하려던 조건이
 * 사용자 몰래 바뀐다. 결과는 둘 다 정상으로 보인다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import { useStockStore } from "@/stores/stockStore";
import { SAMSUNG } from "./support/stockSearchFixtures";

vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: () => () => undefined,
}));
vi.mock("@/lib/collectionStream", () => ({
  subscribeCollection: () => () => undefined,
}));

beforeEach(() => {
  vi.restoreAllMocks();
  useStockStore.getState().dispose();
});

describe("시작일", () => {
  it("처음 값은 2020-01-01이다", async () => {
    vi.resetModules();
    const { useStockStore: fresh } = await import("@/stores/stockStore");
    expect(fresh.getState().input.start).toBe("2020-01-01");
  });

  it("종목을 바꿔도 그대로다", async () => {
    useStockStore.getState().setInput({ start: "2018-03-15" });
    vi.spyOn(apiClient, "post").mockResolvedValue({
      market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW",
      listedOn: "1975-06-11" });
    await useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    expect(useStockStore.getState().input.start).toBe("2018-03-15");
  });

  it("시세 시작일로 거절되면 그 날짜와 근거를 들고 있는다", async () => {
    useStockStore.setState({ input: { ...useStockStore.getState().input,
      stock: { market: "KRX", symbol: "123450.KS", name: "늦은시세", currency: "KRW" },
      start: "2021-05-10" } });
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(400, "before_listing",
      "2021-07-01부터 시세가 있습니다. 그 이전은 계산할 수 없습니다.",
      { status: "before_listing", startableFrom: "2021-07-01", basis: "price_start",
        message: "2021-07-01부터 시세가 있습니다. 그 이전은 계산할 수 없습니다." }));
    await useStockStore.getState().run();
    expect(useStockStore.getState().startable).toEqual({
      startableFrom: "2021-07-01", basis: "price_start",
      message: "2021-07-01부터 시세가 있습니다. 그 이전은 계산할 수 없습니다." });
    // W1a로 말한다 — 일반 오류로 한 번 더 말하지 않는다. 시작일도 몰래 옮기지 않는다.
    expect(useStockStore.getState().error).toBeNull();
    expect(useStockStore.getState().input.start).toBe("2021-05-10");
  });

  it("종목을 바꾸면 이전 종목의 시작 가능 날짜를 지운다", async () => {
    useStockStore.setState({ startable: { startableFrom: "2021-07-01", basis: "price_start",
      message: "" } });
    vi.spyOn(apiClient, "post").mockResolvedValue({
      market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW", listedOn: null });
    await useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    expect(useStockStore.getState().startable).toBeNull();
  });
});
