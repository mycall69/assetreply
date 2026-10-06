/**
 * 주식 화면의 적립식 — 화면 → 스토어 → 경로 (011 T023) — FR-001, FR-012, FR-014, FR-015, FR-033.
 *
 * **실제로 눌러야만 통과한다**(006 D1): 화면이 투자 방식 칸을 그리지 않거나, 스토어가 방식을 받지 않거나, 실행이 적립식 경로를 부르지
 * 않으면 이 테스트가 실패한다. 결과가 오면 다섯 칸 보드와 적립식 표가 보이고 일시금 보드(네 칸)는 없다. 이력 행은 방식·주기·금액을 보인다.
 * 일시금으로 되돌리면 결과가 빈다. 금액 칸 이름이 방식을 따라 바뀐다.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StocksPage from "@/app/stocks/page";
import { apiClient } from "@/lib/apiClient";
import type { RecurringStockResponse, SimulationSeriesResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };

const RESULT: RecurringStockResponse = {
  stock: STOCK,
  condition: { mode: "recurring", start: "2024-01-15", amount: "500000", principalCurrency: "KRW", frequency: "weekly",
    reinvest: true, tradeFeeRate: "0.000150", dividendTaxRate: "0.154000" },
  summary: {
    contributed: "1000000", contributedKrw: "1000000", contributions: 2, pendingAfterEnd: 0, heldShares: 14,
    pending: "26854", dividendCash: "0", totalKrw: "999854", buyFeeTotal: "145", dividendTaxTotal: "0",
    saleCost: { fee: "145", tax: "1946", total: "2091", taxKind: "transaction_tax", taxRate: "0.0020", gain: null,
      deduction: null },
    feeTotal: "290", taxTotal: "1946", profit: "-146", returnRate: "-0.000146", profitAfterSale: "-2237",
    returnRateAfterSale: "-0.002237", asOf: "2024-01-22", isFinal: true,
  },
  rows: [{ date: "2024-01-22", kind: "contribution", openPrice: "69000", closePrice: "69500", contribution: "500000",
    boughtShares: 7, heldShares: 14, pending: "26854", dividendCash: "0", contributed: "1000000",
    contributedKrw: "1000000", balance: "973000", profit: "-146", returnRate: "-0.000146", tradeFee: "72" }],
  hasMore: false, oldestReturned: "2024-01-22",
};

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-15", to: "2024-01-22", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1,
  points: [{ date: "2024-01-22", balance: "999854", returnRate: "-0.000146", principal: "1000000", price: "69500" }],
  gaps: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useStockStore.setState({
    input: { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
    plan: { mode: "lump_sum", frequency: "monthly" },
    recurring: null, history: [], selectedHistory: [], summary: null, rows: [], series: null, error: null,
    collecting: null, selecting: false, listedOn: null, startable: null,
  });
});

describe("주식 화면 — 적립식", () => {
  it("적립식을 고르고 주기를 바꿔 실행하면 적립식 경로로 요청하고 다섯 칸 보드와 적립식 표가 보인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : RESULT) as never);
    render(<StocksPage />);
    expect(screen.getByText("투자 원금")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(screen.getByText("한 번 납입액")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "납입 주기" }), { target: { value: "weekly" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      "/api/stocks/recurring-simulation?market=KRX&symbol=005930.KS&start=2024-01-15&amount=500000"
      + "&principalCurrency=KRW&frequency=weekly&reinvest=true"));
    expect(await screen.findByRole("group", { name: "총 납입 원금" })).toHaveTextContent("₩1,000,000");
    expect(screen.getByRole("group", { name: "매매 수수료 총액" })).toBeInTheDocument();
    expect(screen.queryByText("매도 수수료/세금")).not.toBeInTheDocument();
    expect(screen.getAllByRole("row").some((r) => r.getAttribute("data-kind") === "contribution")).toBe(true);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("누적 납입 원금");
    expect(screen.getAllByTestId("history-row")[0]).toHaveTextContent("적립식 · 매주 ₩500,000");
  });

  it("누르지 않으면 적립식 경로를 부르지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({
      stock: STOCK, condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true,
        tradeFeeRate: "0", dividendTaxRate: "0" },
      summary: { principal: "500000", profit: "1", returnRate: "0.1", asOf: "2024-01-22", isFinal: true },
      rows: [], hasMore: false, oldestReturned: null,
    } as never);
    render(<StocksPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(get.mock.calls.every((c) => !String(c[0]).includes("recurring"))).toBe(true);
  });

  it("일시금으로 되돌리면 적립식 결과가 빈다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : RESULT) as never);
    render(<StocksPage />);
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("group", { name: "총 납입 원금" });
    fireEvent.click(screen.getByRole("radio", { name: "일시금" }));
    expect(screen.queryByRole("group", { name: "총 납입 원금" })).not.toBeInTheDocument();
    expect(useStockStore.getState().recurring).toBeNull();
  });
});
