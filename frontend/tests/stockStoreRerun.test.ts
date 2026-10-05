/**
 * 주식 이력의 다시 실행 — 스토어 (010 T026) — FR-018~FR-020, SC-005, research R10-11.
 *
 * - 항목의 종목·시작일·원금·원금 통화·배당 재투자를 **그대로** 입력에 넣고 곧바로 실행한다 — 조건 하나라도 빠지면 다른 조건의 결과가 그
 *   항목의 결과처럼 보인다(FR-018 실패 양상)
 * - **등록 요청(`POST /api/stocks/selection`)을 보내지 않는다** — 등록 경로는 목록 id나 일본 외부 결과만 받고 이력 항목에는 목록 id가 없다.
 *   이력의 종목은 이미 실행한(= 등록된) 종목이다. 고른 종목에 딸린 상태(상장일 안내·시작 가능 날짜·선택 오류)는 지운다
 * - 막힌 조합(원금 EUR·미국 종목)은 `run()`의 지금 규칙으로 거절과 사유 — 통화를 바꿔 실행하지 않는다(FR-019)
 * - 202면 직접 실행과 같은 수집 진행(FR-020)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { principalRule } from "@/lib/principalCurrency";
import { subscribeStockProgress } from "@/lib/stockProgressStream";
import type { SimulationHistoryEntry, SimulationResponse, SimulationSeriesResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: vi.fn(() => () => undefined) }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const APPLE = { market: "NASDAQ" as const, symbol: "AAPL", name: "Apple Inc.", currency: "USD" };

const APPLE_KRW: SimulationHistoryEntry = {
  id: "a", stock: APPLE, start: "2020-01-02", principal: "10000000", principalCurrency: "KRW",
  reinvest: false, savedAt: "2026-10-05T00:00:00Z",
};

/** 006 이전의 막힌 조합 — 미국 종목에 유로 원금. */
const APPLE_EUR: SimulationHistoryEntry = { ...APPLE_KRW, id: "eur", principalCurrency: "EUR", principal: "5000" };

const RESULT: SimulationResponse = {
  stock: APPLE,
  condition: { start: "2020-01-02", principal: "10000000", principalCurrency: "KRW", reinvest: false,
    tradeFeeRate: "0", dividendTaxRate: "0" },
  summary: { principal: "10000000", profit: "1", returnRate: "0.1", asOf: "2026-10-04", isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

const SERIES: SimulationSeriesResponse = {
  from: "2020-01-02", to: "2026-10-04", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 0, points: [], gaps: [],
};

const QUERY = "/api/stocks/simulation?market=NASDAQ&symbol=AAPL&start=2020-01-02&principal=10000000"
  + "&principalCurrency=KRW&reinvest=false";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(subscribeStockProgress).mockClear();
  localStorage.clear();
  // 다른 종목을 고른 상태 — 그 종목에 딸린 상태가 남아 있다.
  useStockStore.setState({
    input: { stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
      start: "2024-01-02", principal: "1000000", principalCurrency: "KRW", reinvest: true },
    listedOn: "1975-06-11",
    startable: { startableFrom: "1975-06-11", basis: "listing", message: "상장일" },
    selectionError: "이전 오류", error: null, summary: null, collecting: null,
    history: [APPLE_KRW, APPLE_EUR], selectedHistory: [],
  });
});

describe("rerunHistory", () => {
  it("항목의 조건을 그대로 넣고 그 조건으로 실행한다 — 등록 요청 없이", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.startsWith("/api/stocks/simulation/series") ? SERIES : RESULT) as never);
    const post = vi.spyOn(apiClient, "post");
    await useStockStore.getState().rerunHistory("a");
    const state = useStockStore.getState();
    expect(state.input).toEqual({ stock: APPLE, start: "2020-01-02", principal: "10000000",
      principalCurrency: "KRW", reinvest: false });
    expect(get.mock.calls[0][0]).toBe(QUERY);
    expect(post).not.toHaveBeenCalled();
    expect(state.summary).toEqual(RESULT.summary);
  });

  it("고른 종목에 딸린 상태를 지운다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.startsWith("/api/stocks/simulation/series") ? SERIES : RESULT) as never);
    await useStockStore.getState().rerunHistory("a");
    const state = useStockStore.getState();
    expect([state.listedOn, state.startable, state.selectionError]).toEqual([null, null, null]);
  });

  it("막힌 조합은 조건을 넣고 지금 규칙의 사유로 거절한다 — 통화를 바꾸지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    await useStockStore.getState().rerunHistory("eur");
    const state = useStockStore.getState();
    expect(state.input.principalCurrency).toBe("EUR");
    expect(state.input.stock).toEqual(APPLE);
    expect(state.error).toBe(`${principalRule("USD")}. 통화를 다시 고르세요.`);
    expect(get).not.toHaveBeenCalled();
  });

  it("받지 않은 구간이면 직접 실행과 같이 수집 진행을 구독한다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(
      { status: "collecting", market: "NASDAQ", symbol: "AAPL", jobId: 7 } as never);
    await useStockStore.getState().rerunHistory("a");
    expect(useStockStore.getState().collecting).toMatchObject({ status: "collecting", jobId: 7 });
    expect(vi.mocked(subscribeStockProgress).mock.calls[0][0]).toBe(7);
  });

  it("없는 항목이면 아무것도 하지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    const post = vi.spyOn(apiClient, "post");
    const before = useStockStore.getState().input;
    await useStockStore.getState().rerunHistory("nope");
    expect(get).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    expect(useStockStore.getState().input).toBe(before);
  });
});
