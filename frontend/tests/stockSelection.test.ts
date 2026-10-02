/**
 * 고른 종목의 등록 (T029) — 006 FR-030, FR-030a, FR-030b, research R6-17.
 *
 * **고르는 순간 등록한다.** 005는 고른 종목을 저장하는 경로가 없어 고른 종목마다 실행에서 "알 수
 * 없는 종목"으로 끝났다. 등록이 실패하면 그 자리에서 드러나야 한다 — 실행하고 나서야 알면 원인이
 * "종목이 없다"로 보여 사용자는 검색 결과를 믿지 못하게 된다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import { loadHistory } from "@/lib/simulationHistory";
import type { LocalStockResult, SelectionResponse, SimulationResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";
import { SAMSUNG, TOYOTA } from "./support/stockSearchFixtures";

const REGISTERED: SelectionResponse = {
  market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW",
  listedOn: "1975-06-11",
};

const RESULT: SimulationResponse = {
  stock: { market: "AMEX", symbol: "SPY", name: "SPDR S&P 500", currency: "USD" },
  condition: {
    start: "2021-08-02", principal: "1000", principalCurrency: "USD", reinvest: true,
    tradeFeeRate: "0", dividendTaxRate: "0",
  },
  summary: { principal: "1000", profit: "0", returnRate: "0", asOf: "2021-08-31",
    isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useStockStore.setState({
    input: { stock: null, start: "2021-08-02", principal: "1000000",
      principalCurrency: "KRW", reinvest: true },
    selecting: false, selectionError: null, error: null, summary: null,
  });
});

describe("등록", () => {
  it("목록 결과를 고르는 순간 등록을 부른다", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue(REGISTERED);
    await useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    expect(post).toHaveBeenCalledWith("/api/stocks/selection",
      { source: "listing", listingId: 1021 });
    expect(useStockStore.getState().input.stock).toEqual({
      market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" });
    expect(useStockStore.getState().selectionError).toBeNull();
  });

  it("일본 결과는 받은 식별을 그대로 보낸다", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      ...TOYOTA, listedOn: null, kind: undefined });
    await useStockStore.getState().selectStock({ source: "external", result: TOYOTA });
    expect(post).toHaveBeenCalledWith("/api/stocks/selection", {
      source: "external", market: "TSE", symbol: "7203.T",
      name: "Toyota Motor Corporation", currency: "JPY" });
    expect(useStockStore.getState().input.stock?.symbol).toBe("7203.T");
  });

  it("등록하는 동안에는 종목이 비어 실행할 수 없다", async () => {
    // 이전 종목이 남아 있으면 등록이 끝나기 전에 누른 실행이 이전 종목으로 나간다.
    useStockStore.setState({ input: { ...useStockStore.getState().input,
      stock: { market: "KRX", symbol: "000660.KS", name: "SK하이닉스", currency: "KRW" } } });
    let release: (value: SelectionResponse) => void = () => {};
    vi.spyOn(apiClient, "post").mockReturnValue(
      new Promise((resolve) => { release = resolve as typeof release; }));
    const done = useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    expect(useStockStore.getState().selecting).toBe(true);
    expect(useStockStore.getState().input.stock).toBeNull();
    release(REGISTERED);
    await done;
    expect(useStockStore.getState().selecting).toBe(false);
  });

  it("실패하면 실행 전에 사유를 보인다", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(
      new ApiError(404, "unknown_listing", "목록에서 찾을 수 없는 종목입니다."));
    const get = vi.spyOn(apiClient, "get");
    await useStockStore.getState().selectStock({ source: "listing", listingId: 9,
      preview: SAMSUNG });
    expect(useStockStore.getState().selectionError).toBe("목록에서 찾을 수 없는 종목입니다.");
    expect(useStockStore.getState().input.stock).toBeNull();

    await useStockStore.getState().run();
    expect(get).not.toHaveBeenCalled();
  });

  it("늦게 온 이전 등록 응답이 나중 선택을 덮지 않는다", async () => {
    let releaseFirst: (value: SelectionResponse) => void = () => {};
    const post = vi.spyOn(apiClient, "post");
    post.mockReturnValueOnce(new Promise((r) => { releaseFirst = r as typeof releaseFirst; }));
    post.mockResolvedValueOnce({ ...REGISTERED, symbol: "005935.KS", name: "삼성전자우" });

    const first = useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    await useStockStore.getState().selectStock({ source: "listing", listingId: 1022,
      preview: { ...SAMSUNG, listingId: 1022 } as LocalStockResult });
    releaseFirst(REGISTERED);
    await first;
    expect(useStockStore.getState().input.stock?.symbol).toBe("005935.KS");
  });
});

describe("등록 뒤", () => {
  it("시뮬레이션과 이력이 등록 응답의 식별을 쓴다", async () => {
    // FR-030a — 목록은 SPY를 NYSE로 두지만 005가 AMEX로 저장해 두었다. 등록 응답이 그 식별이다.
    vi.spyOn(apiClient, "post").mockResolvedValue({
      market: "AMEX", symbol: "SPY", name: "SPDR S&P 500", currency: "USD", listedOn: null,
    } satisfies SelectionResponse);
    const preview: LocalStockResult = {
      ...SAMSUNG, listingId: 5001, country: "US", market: "NYSE", symbol: "SPY", code: "SPY",
      name: "S&P 500 SPDR ETF", currency: "USD", kind: "etf", listedOn: null,
    };
    await useStockStore.getState().selectStock({ source: "listing", listingId: 5001, preview });
    useStockStore.getState().setInput({ principalCurrency: "USD", principal: "1000" });

    const get = vi.spyOn(apiClient, "get").mockImplementation(((path: string) =>
      Promise.resolve(path.includes("/series") ? {
        from: "2021-08-02", to: "2021-08-31", principalCurrency: "USD", downsampled: false,
        algorithm: "none", sourcePointCount: 0, points: [], gaps: [],
      } : RESULT)) as typeof apiClient.get);
    await useStockStore.getState().run();

    expect(get.mock.calls[0][0]).toContain("market=AMEX");
    expect(get.mock.calls[0][0]).toContain("symbol=SPY");
    expect(loadHistory()[0].stock).toEqual({
      market: "AMEX", symbol: "SPY", name: "SPDR S&P 500", currency: "USD" });
  });

  it("등록 응답의 상장일을 들고 있는다", async () => {
    // W1a — 시작일이 상장일보다 이르면 실행 전에 알린다(US3에서 쓴다).
    vi.spyOn(apiClient, "post").mockResolvedValue(REGISTERED);
    await useStockStore.getState().selectStock({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
    expect(useStockStore.getState().listedOn).toBe("1975-06-11");
  });
});
