/**
 * 가상자산 화면의 적립식 — 화면 → 스토어 → 경로 (011 T036) — FR-017, FR-019, FR-020, FR-033.
 *
 * **실제로 눌러야만 통과한다**(006 D1): 화면이 투자 방식 칸을 그리지 않거나, 스토어가 방식을 받지 않거나, 실행이 적립식 경로를 부르지
 * 않으면 이 테스트가 실패한다. 결과가 오면 다섯 칸 보드("가상자산 과세 시행 전")와 적립식 표가 보이고, 이력 행은 방식·주기·금액을 보인다.
 * 배당 재투자 칸은 적립식에서도 없다(`CryptoPage.test.tsx` 그대로).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import { apiClient } from "@/lib/apiClient";
import type { RecurringCryptoResponse, SimulationSeriesResponse } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
// 실제 차트는 jsdom에서 그릴 수 없다(`matchMedia` 없음 — 처리되지 않은 오류로 실행이 실패한다). 범례는 DOM이라 모의로도 보인다.
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const RESULT: RecurringCryptoResponse = {
  coin: { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" },
  condition: { mode: "recurring", start: "2024-01-15", amount: "10000", principalCurrency: "KRW", frequency: "daily",
    tradeFeeRate: "0.001000" },
  summary: {
    contributed: "20000", contributedKrw: "20000", contributions: 2, pendingAfterEnd: 0, heldQuantity: "0.00036332",
    pending: "0.00029518", totalKrw: "20400", buyFeeTotal: "20", saleCost: { fee: "20", tax: "0", total: "20",
      taxKind: "not_yet_taxed" },
    feeTotal: "40", taxTotal: "0", profit: "400", returnRate: "0.020000", profitAfterSale: "380",
    returnRateAfterSale: "0.019000", asOf: "2024-01-16", isFinal: true,
  },
  rows: [{ date: "2024-01-16", kind: "contribution", openPrice: "42000", contribution: "10000",
    boughtQuantity: "0.00017601", heldQuantity: "0.00036332", pending: "0.00029518", contributed: "20000",
    contributedKrw: "20000", balance: "15.25944", balanceKrw: "20399", profit: "400", returnRate: "0.020000",
    tradeFee: "0.00739242", fxRate: "1336.8", fxRateDate: "2024-01-16", exchangeRate: "1339.2", exchangeRateDate: "2024-01-16" }],
  hasMore: false, oldestReturned: "2024-01-16",
};

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-15", to: "2024-01-16", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1,
  points: [{ date: "2024-01-16", balance: "20400", returnRate: "0.020000", principal: "20000", price: "42000" }],
  gaps: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useCryptoStore.setState({
    input: { coin: BTC, start: "2024-01-15", principal: "10000", principalCurrency: "KRW" },
    plan: { mode: "lump_sum", frequency: "monthly" },
    recurring: null, history: [], selectedHistory: [], summary: null, rows: [], series: null, error: null,
    collecting: null, startable: null,
  });
});

describe("가상자산 화면 — 적립식", () => {
  it("적립식을 고르고 매일로 실행하면 적립식 경로로 요청하고 다섯 칸 보드와 적립식 표가 보인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : RESULT) as never);
    render(<CryptoPage />);
    expect(screen.getByText("투자 원금")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(screen.getByText("한 번 납입액")).toBeInTheDocument();
    // 배당 재투자 칸은 적립식에서도 없다
    expect(screen.queryByText("배당 재투자")).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "납입 주기" }), { target: { value: "daily" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      "/api/crypto/recurring-simulation?coinId=17&start=2024-01-15&amount=10000&principalCurrency=KRW&frequency=daily"));
    expect(await screen.findByRole("group", { name: "총 납입 원금" })).toHaveTextContent("₩20,000");
    expect(screen.getByRole("group", { name: "세금 총액" })).toHaveTextContent("가상자산 과세 시행 전");
    expect(screen.queryByText(/매수일 /)).not.toBeInTheDocument();
    expect(screen.getAllByRole("row").some((r) => r.getAttribute("data-kind") === "contribution")).toBe(true);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("누적 납입 원금");
    expect(screen.getAllByTestId("history-row")[0]).toHaveTextContent("적립식 · 매일 ₩10,000");
  });

  it("누르지 않으면 적립식 경로를 부르지 않는다", async () => {
    const lump = {
      coin: RESULT.coin, condition: { start: "2024-01-15", principal: "10000", principalCurrency: "KRW",
        tradeFeeRate: "0.001000" },
      summary: { principal: "10000", profit: "1", returnRate: "0.1", asOf: "2024-01-16", isFinal: true,
        boughtOn: "2024-01-01" },
      rows: [], hasMore: false, oldestReturned: null,
    };
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : lump) as never);
    render(<CryptoPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(get.mock.calls.every((c) => !String(c[0]).includes("recurring"))).toBe(true);
  });

  it("일시금으로 되돌리면 적립식 결과가 빈다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : RESULT) as never);
    render(<CryptoPage />);
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("group", { name: "총 납입 원금" });
    fireEvent.click(screen.getByRole("radio", { name: "일시금" }));
    expect(screen.queryByRole("group", { name: "총 납입 원금" })).not.toBeInTheDocument();
    expect(useCryptoStore.getState().recurring).toBeNull();
  });
});
