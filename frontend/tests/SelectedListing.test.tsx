/**
 * 고른 종목·코인 줄의 상장일 (014 반복 2026-10-10g T169) — FR-034, contracts D13·A11, research R14-27.
 *
 * 사용자 보고(2026-10-10): 주식 메뉴에서 고른 "QQQ 2배 프로셰어즈 ETF(QLD) NYSE · USD" 줄에 상장일이 없었다 — 10f는 드롭다운 결과 줄에만
 * 넣었다. 고른 줄의 **종목명 밑 한 줄**에 같은 글자(`상장 …`·`첫 거래 …`·`첫 일봉 …`)를 보인다.
 *
 * - 값은 고른 대상의 상장일 경로다(등록 응답이 아니다 — 이력 다시 실행은 등록이 없다). 대상이 바뀔 때 묻고 늦은 답은 버린다
 * - 결과가 올 때 다시 묻는다(실행의 수집이 첫 일봉·첫 거래일을 알게 한다). 결과가 비는 것은 묻지 않는다
 * - 묻는 동안·실패면 줄이 없다. 모르면 `상장일 —`와 까닭
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import StocksPage from "@/app/stocks/page";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { StockSearch } from "@/components/stock/StockSearch";
import { ApiError, apiClient } from "@/lib/apiClient";
import { LEGACY_KEYS } from "@/lib/legacyHistory";
import { listingTitle } from "@/lib/listingDate";
import type { SimulationHistoryEntry, SimulationResponse, SimulationSeriesResponse, StockSearchResult } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useStockStore } from "@/stores/stockStore";
import { BTC, BTS } from "./support/coinSearchFixtures";
import { RESULT as CRYPTO_RESULT } from "./support/cryptoFixtures";
import { listingStub } from "./support/listingStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
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

const QLD: StockSearchResult = { market: "NYSE", symbol: "QLD", name: "QQQ 2배 프로셰어즈 ETF", currency: "USD" };
const SAMSUNG: StockSearchResult = { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const SPY: StockSearchResult = { market: "AMEX", symbol: "SPY", name: "S&P 500 SPDR ETF", currency: "USD" };

const stockLine = () => screen.queryByTestId("stock-selected-listing");
const coinLine = () => screen.queryByTestId("coin-selected-listing");
/** 답이 그려질 틈 — 실패·붙잡힘을 볼 때 "아직 안 왔다"와 "오고도 안 그렸다"를 가른다. */
const settle = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("주식 — 고른 줄의 상장일", () => {
  it("종목명 밑 한 줄에 기준을 밝힌 날짜다 — 첫 거래 …", async () => {
    listingStub.seedStock("NYSE", "QLD", { date: "2006-06-21", basis: "first_trade" });
    render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    const line = await screen.findByTestId("stock-selected-listing");
    expect(line.textContent).toBe("첫 거래 2006-06-21");
    expect(line.querySelector("[title]")?.getAttribute("title")).toBe(listingTitle("first_trade"));
    // 종목명 링크가 있는 줄 **밑**이다 — 같은 줄의 오른쪽이 아니다
    const name = screen.getByRole("link", { name: /QQQ 2배 프로셰어즈 ETF/ });
    expect(name.closest("p")?.contains(line)).toBe(false);
    expect(name.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(listingStub.calls()).toEqual(["/api/stocks/listing-date?market=NYSE&symbol=QLD"]);
  });

  it("국내는 키움 상장일 — 상장 …", async () => {
    listingStub.seedStock("KRX", "005930.KS", { date: "1975-06-11", basis: "listing" });
    render(<StockSearch value={SAMSUNG} onSelect={vi.fn()} />);
    expect((await screen.findByTestId("stock-selected-listing")).textContent).toBe("상장 1975-06-11");
  });

  it("모르면 상장일 —와 까닭이다(지어내지 않는다)", async () => {
    render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    const line = await screen.findByTestId("stock-selected-listing");
    expect(line.textContent).toBe("상장일 —");
    expect(line.querySelector("[title]")?.getAttribute("title")).toMatch(/다시 고르거나 실행하면 다시 받습니다/);
  });

  it("묻는 동안은 줄이 없다 — \"—\"로 깜박이지 않는다", async () => {
    listingStub.hold();
    listingStub.seedStock("NYSE", "QLD", { date: "2006-06-21", basis: "first_trade" });
    render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    await waitFor(() => expect(listingStub.held()).toBe(1));
    expect(stockLine()).toBeNull();
    await act(async () => { listingStub.release(); });
    expect((await screen.findByTestId("stock-selected-listing")).textContent).toBe("첫 거래 2006-06-21");
  });

  it("경로가 실패하면 줄이 없고 고른 줄은 그대로다", async () => {
    listingStub.fail();
    render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    await waitFor(() => expect(listingStub.calls()).toHaveLength(1));
    await settle();
    expect(stockLine()).toBeNull();
    expect(screen.getByRole("link", { name: /QQQ 2배 프로셰어즈 ETF/ })).toBeInTheDocument();
  });

  it("대상이 바뀌면 다시 묻고, 늦게 온 이전 대상의 답은 그리지 않는다", async () => {
    listingStub.seedStock("NYSE", "QLD", { date: "2006-06-21", basis: "first_trade" });
    listingStub.seedStock("AMEX", "SPY", { date: "1993-01-29", basis: "first_trade" });
    listingStub.hold();
    const view = render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    await waitFor(() => expect(listingStub.held()).toBe(1));
    view.rerender(<StockSearch value={SPY} onSelect={vi.fn()} />);
    await waitFor(() => expect(listingStub.held()).toBe(2));
    // SPY의 답이 먼저, QLD의 답이 나중에 온다
    await act(async () => { listingStub.release([1, 0]); });
    await settle();
    expect(stockLine()?.textContent).toBe("첫 거래 1993-01-29");
  });

  it("결과 신호가 오면 다시 묻고, 결과가 비는 것은 묻지 않는다", async () => {
    const view = render(<StockSearch value={QLD} onSelect={vi.fn()} />);
    expect((await screen.findByTestId("stock-selected-listing")).textContent).toBe("상장일 —");
    // 실행의 수집이 첫 거래일을 알게 했다
    listingStub.seedStock("NYSE", "QLD", { date: "2006-06-21", basis: "first_trade" });
    view.rerender(<StockSearch value={QLD} onSelect={vi.fn()} listingRefresh="result" />);
    await waitFor(() => expect(stockLine()?.textContent).toBe("첫 거래 2006-06-21"));
    view.rerender(<StockSearch value={QLD} onSelect={vi.fn()} />);
    await settle();
    expect(listingStub.calls()).toHaveLength(2);
    // 비는 동안에도 아는 날짜는 남는다
    expect(stockLine()?.textContent).toBe("첫 거래 2006-06-21");
    view.rerender(<StockSearch value={QLD} onSelect={vi.fn()} listingRefresh="result" />);
    await waitFor(() => expect(listingStub.calls()).toHaveLength(3));
  });

  it("고른 것이 없으면 묻지 않는다 — 투자 비교의 검색", async () => {
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await settle();
    expect(listingStub.calls()).toEqual([]);
    expect(stockLine()).toBeNull();
  });
});

describe("가상자산 — 고른 줄의 상장일", () => {
  it("종목명 밑 한 줄에 첫 일봉 …", async () => {
    listingStub.seedCoin(BTC.coinId, { date: "2010-07-18", basis: "first_bar" });
    render(<CoinSearch value={BTC} onSelect={vi.fn()} />);
    const line = await screen.findByTestId("coin-selected-listing");
    expect(line.textContent).toBe("첫 일봉 2010-07-18");
    expect(line.querySelector("[title]")?.getAttribute("title")).toBe(listingTitle("first_bar"));
    expect(screen.getByTestId("coin-selected").contains(line)).toBe(false);
    expect(listingStub.calls()).toEqual([`/api/crypto/listing-date?coinId=${BTC.coinId}`]);
  });

  it("모르면 상장일 —와 까닭이다", async () => {
    render(<CoinSearch value={BTS} onSelect={vi.fn()} />);
    const line = await screen.findByTestId("coin-selected-listing");
    expect(line.textContent).toBe("상장일 —");
    expect(line.querySelector("[title]")?.getAttribute("title")).toMatch(/실행해 일봉을 받으면 보입니다/);
  });

  it("결과 신호가 오면 다시 묻는다 — 처음 고른 코인의 첫 일봉", async () => {
    const view = render(<CoinSearch value={BTS} onSelect={vi.fn()} />);
    expect((await screen.findByTestId("coin-selected-listing")).textContent).toBe("상장일 —");
    listingStub.seedCoin(BTS.coinId, { date: "2014-07-21", basis: "first_bar" });
    view.rerender(<CoinSearch value={BTS} onSelect={vi.fn()} listingRefresh="result" />);
    await waitFor(() => expect(coinLine()?.textContent).toBe("첫 일봉 2014-07-21"));
  });
});

// ─────────────────────────────── 화면 ───────────────────────────────

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
const SERIES = {
  from: "2020-01-02", to: "2026-10-04", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 0, points: [], gaps: [],
} as unknown as SimulationSeriesResponse;

describe("화면 — 고른 줄의 상장일", () => {
  beforeEach(() => {
    localStorage.clear();
    useStockStore.setState({
      input: { stock: null, start: "2024-01-02", principal: "1000000", principalCurrency: "KRW", reinvest: true },
      plan: { mode: "lump_sum", frequency: "monthly" }, recurring: null,
      history: [], selectedHistory: [], summary: null, rows: [], series: null, error: null, collecting: null,
    });
    useCryptoStore.setState({
      input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
      plan: { mode: "lump_sum", frequency: "monthly" }, recurring: null, history: [], summary: null, rows: [],
      series: null, error: null, collecting: null, startable: null,
    });
  });

  it("주식 — 이력 다시 실행(등록 없음) 뒤에도 고른 줄 밑에 상장일이 있고, 결과가 오면 한 번 더 묻는다", async () => {
    localStorage.setItem(LEGACY_KEYS.stock, JSON.stringify([ENTRY]));
    listingStub.seedStock("NASDAQ", "AAPL", { date: "1980-12-12", basis: "first_trade" });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.startsWith("/api/stocks/simulation/series") ? SERIES : RESULT) as never);
    const post = vi.spyOn(apiClient, "post");
    render(<StocksPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Apple Inc. 다시 실행" }));
    expect((await screen.findByTestId("stock-selected-listing")).textContent).toBe("첫 거래 1980-12-12");
    await waitFor(() => expect(listingStub.calls()).toEqual([
      "/api/stocks/listing-date?market=NASDAQ&symbol=AAPL",
      "/api/stocks/listing-date?market=NASDAQ&symbol=AAPL",
    ]));
    expect(post).not.toHaveBeenCalled();
  });

  it("가상자산 — 실행 결과가 오면 다시 물어 처음 고른 코인의 첫 일봉을 보인다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : CRYPTO_RESULT) as never);
    render(<CryptoPage />);
    expect((await screen.findByTestId("coin-selected-listing")).textContent).toBe("상장일 —");
    listingStub.seedCoin(BTC.coinId, { date: "2010-07-18", basis: "first_bar" });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(coinLine()?.textContent).toBe("첫 일봉 2010-07-18"));
  });

  it("가상자산 — 결과 대신 시작 가능 날짜 안내가 와도 다시 묻는다(시작일이 첫 일봉보다 이르다)", async () => {
    const body = { status: "before_listing", message: "2010-07-18부터 일봉이 있습니다.", startableFrom: "2010-07-18",
      basis: "price_start" };
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(400, "before_listing", body.message, body));
    render(<CryptoPage />);
    expect((await screen.findByTestId("coin-selected-listing")).textContent).toBe("상장일 —");
    listingStub.seedCoin(BTC.coinId, { date: "2010-07-18", basis: "first_bar" });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(coinLine()?.textContent).toBe("첫 일봉 2010-07-18"));
  });
});
