/**
 * 주식·가상자산 화면의 표 단위 탭 (012 T025) — FR-003, FR-006, FR-010, SC-005, contracts/ui-wireframes.md F2·F5.
 *
 * - 표 머리에 외환과 같은 단위 탭(`role="tablist"`, "기간 단위 선택")이 있고 처음은 "일"이다. 탭 제목은 그 표의 말이다(F2)
 * - 탭을 바꾸면 창이 움직이지 않는다(`scrollIntoView`를 부르지 않는다). 바꾸는 동안 작업 영역의 높이를 붙잡는다(US1과 같은 훅)
 * - 보드 글자가 그대로다 — 단위는 표의 행 구성만 바꾼다(FR-007)
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import StocksPage from "@/app/stocks/page";
import { apiClient } from "@/lib/apiClient";
import type { SimulationResponse, SimulationSeriesResponse } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useStockStore } from "@/stores/stockStore";
import { BTC } from "./support/coinSearchFixtures";
import { RESULT as CRYPTO_RESULT } from "./support/cryptoFixtures";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const lump = (dates: string[]): SimulationResponse => ({
  stock: STOCK,
  condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0",
    dividendTaxRate: "0" },
  summary: { principal: "500000", profit: "3426", returnRate: "0.006853", asOf: "2024-02-16", isFinal: true },
  rows: dates.map((date) => ({ date, kind: "period", openPrice: "70000", closePrice: "70500", boughtShares: 0, heldShares: 7,
    cash: "9926", principal: "500000", balance: "493500", profit: "3426", returnRate: "0.006853" })),
  hasMore: false, oldestReturned: dates.at(-1) ?? null,
});
const SERIES = { from: "2024-01-15", to: "2024-02-16", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, points: [{ date: "2024-02-16", balance: "503426", returnRate: "0.006853" }],
  gaps: [] } as unknown as SimulationSeriesResponse;

const board = () => (screen.getByText("KRW 기준").closest("p")?.parentElement as HTMLElement).textContent;
const workspace = (title: string) => screen.getByRole("heading", { name: title }).closest("header")?.parentElement as HTMLElement;
const tabs = () => screen.getByRole("tablist", { name: "기간 단위 선택" });

function gated(answer: (path: string) => unknown) {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.includes("period=")) await gate;
    return answer(path) as never;
  });
  return () => release();
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();
  useStockStore.setState({
    input: { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
    plan: { mode: "lump_sum", frequency: "monthly" }, recurring: null, history: [], selectedHistory: [], summary: null,
    rows: [], series: null, error: null, collecting: null, selecting: false, listedOn: null, startable: null,
    tablePeriod: "daily", tableLoading: false, tableError: null,
  });
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
    plan: { mode: "lump_sum", frequency: "monthly" }, recurring: null, history: [], summary: null, rows: [],
    series: null, error: null, collecting: null, startable: null, tablePeriod: "daily", tableLoading: false, tableError: null,
  });
});

describe("주식 화면", () => {
  it("표 머리에 단위 탭이 있고 처음은 일이며 탭 제목은 주식의 말이다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : lump(["2024-02-16"])) as never);
    render(<StocksPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("table");
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute("title", "시세가 있는 날마다");
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute("title", "그 주의 금요일 (없으면 그 앞의 마지막 거래일)");
    expect(screen.getByRole("tab", { name: "월" })).toHaveAttribute("title", "그 달의 말일 (없으면 그 달의 마지막 거래일)");
    expect(tabs().closest("section")?.querySelector("h3")?.textContent).toBe("일자별 투자 성과");
  });

  it("탭을 바꾸면 창이 움직이지 않고, 바꾸는 동안 높이를 붙잡고, 보드는 그대로다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : lump(["2024-02-16"])) as never);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const height = this.querySelector?.("h2")?.textContent === "주식 투자 시뮬레이션" ? 1900 : 0;
      return { width: 1000, height, top: 0, left: 0, right: 1000, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    render(<StocksPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("table");
    const before = board();
    const release = gated((path) => (path.includes("/series") ? SERIES : lump(["2024-02-16", "2024-02-09"])));
    fireEvent.click(screen.getByRole("tab", { name: "주" }));
    expect(workspace("주식 투자 시뮬레이션").style.minHeight).toBe("1900px");
    expect(screen.queryByRole("table")).toBeNull();  // 이전 단위의 행이 남지 않는다
    expect(screen.getByText("⟳ 불러오는 중…")).toBeInTheDocument();
    await act(async () => { release(); });
    await screen.findByRole("table");
    await waitFor(() => expect(workspace("주식 투자 시뮬레이션").style.minHeight).toBe(""));
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute("aria-selected", "true");
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    expect(board()).toBe(before);
  });
});

describe("가상자산 화면", () => {
  it("단위 탭의 제목은 일봉의 말이고, 바꿔도 창이 움직이지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : CRYPTO_RESULT) as never);
    render(<CryptoPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("table");
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute("title", "일봉마다");
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute("title",
      "그 주의 금요일 일봉 (없으면 그 앞의 마지막 일봉, 월~금에 없으면 그 주의 마지막 일봉)");
    const release = gated(() => CRYPTO_RESULT);
    fireEvent.click(screen.getByRole("tab", { name: "월" }));
    expect(screen.queryByRole("table")).toBeNull();
    await act(async () => { release(); });
    await screen.findByRole("table");
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
  });
});
