/**
 * 주식 화면의 다시 실행 — 화면 → 스토어 → 실행 (010 T028) — FR-018, FR-020, research R10-11.
 *
 * **이 경로를 거쳐야만 통과한다**(006 D1): 화면이 이력 부품에 `onRerun`을 넘기지 않거나 스토어의 `rerunHistory`가 실행하지 않으면 시뮬레이션
 * 요청이 나가지 않는다 — 주식에 다시 실행이 처음부터 없던 결함의 모양이다. 등록 요청은 없다(이력의 종목은 이미 등록되어 있다).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StocksPage from "@/app/stocks/page";
import { apiClient } from "@/lib/apiClient";
// 012 승인 2026-10-07 — 012부터 옛 브라우저 키는 화면을 열 때 로컬 DB로 옮겨진다. 옮겨진 항목으로 다시 실행한다(FR-013).
import { LEGACY_KEYS } from "@/lib/legacyHistory";
import type { SimulationHistoryEntry, SimulationResponse, SimulationSeriesResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const APPLE = { market: "NASDAQ" as const, symbol: "AAPL", name: "Apple Inc.", currency: "USD" };

const ENTRY: SimulationHistoryEntry = {
  id: "a", stock: APPLE, start: "2020-01-02", principal: "10000000", principalCurrency: "KRW",
  reinvest: false, savedAt: "2026-10-05T00:00:00Z",
};

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

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  localStorage.setItem(LEGACY_KEYS.stock, JSON.stringify([ENTRY])); // 012 승인 2026-10-07
  useStockStore.setState({
    input: { stock: null, start: "2024-01-02", principal: "1000000", principalCurrency: "KRW", reinvest: true },
    history: [], selectedHistory: [], summary: null, rows: [], series: null, error: null, collecting: null,
  });
});

describe("주식 화면 — 다시 실행", () => {
  it("이력의 다시 실행을 누르면 그 항목 조건으로 시뮬레이션을 요청하고 등록 요청은 없다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.startsWith("/api/stocks/simulation/series") ? SERIES : RESULT) as never);
    const post = vi.spyOn(apiClient, "post");
    render(<StocksPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Apple Inc. 다시 실행" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      "/api/stocks/simulation?market=NASDAQ&symbol=AAPL&start=2020-01-02&principal=10000000"
      + "&principalCurrency=KRW&reinvest=false"));
    expect(post).not.toHaveBeenCalled();
  });
});
