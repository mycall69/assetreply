/**
 * 투자 성과표의 처음 단위 (014 반복 2026-10-11 T176) — spec FR-035, SC-020, US8, data-model 13, contracts D14, research R14-28.
 *
 * - 일·주·월 단추가 있는 표 넷(외환 일자별 환율 표, 주식·가상자산 일자별 투자 성과, 투자 비교 모달의 주식·가상자산 표)은 **처음이 "월"**이다 — 탭만이 아니라
 *   첫 표 요청부터 `period=monthly`다(탭과 행이 다르면 안 된다 — FR-035 실패 양상)
 * - 서버의 기본은 그대로다 — "일"을 고르면 지금처럼 `period`를 싣지 않는다. 시계열 요청에는 단위가 없다(012 FR-007)
 * - 고른 단위는 같은 화면에서 남는다(다시 실행해도). 비교 모달은 열 때마다 "월"부터, 예금·부동산 모달 요청에는 단위가 없다
 * - 대상 밖: 대시보드 지표 모달의 일자별 표는 처음 "일"이다
 */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import FxPage from "@/app/fx/page";
import StocksPage from "@/app/stocks/page";
import { SimulationModal } from "@/components/compare/SimulationModal";
import { apiClient } from "@/lib/apiClient";
import { comparisonPath } from "@/lib/compareApi";
import type {
  CoverageRow,
  DailyResponse,
  LatestResponse,
  PeriodRow,
  SeriesResponse,
  SimulationHistoryEntry,
  SimulationResponse,
  SimulationSeriesResponse,
} from "@/lib/types";
import { pageable, useCompareDetailStore, type DetailTarget } from "@/stores/compareDetailStore";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";
import { useIndicatorTableStore } from "@/stores/indicatorTableStore";
import { useStockStore } from "@/stores/stockStore";
import { BTC } from "./support/coinSearchFixtures";
import { CASES, CRYPTO_RECURRING, SERIES as MODAL_SERIES, STOCK_RECURRING } from "./support/compareDetailFixtures";
import { routeCompare } from "./support/compareFixtures";
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
const STOCK_INPUT = { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW" as const, reinvest: true };
const STOCK_QUERY = "market=KRX&symbol=005930.KS&start=2024-01-15&principal=500000&principalCurrency=KRW&reinvest=true";
const STOCK_RECURRING_QUERY =
  "market=KRX&symbol=005930.KS&start=2024-01-15&amount=500000&principalCurrency=KRW&frequency=monthly&reinvest=true";
const CRYPTO_INPUT = { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" as const };
const CRYPTO_QUERY = `coinId=${BTC.coinId}&start=2020-01-15&principal=10000&principalCurrency=USD`;

const lump = (): SimulationResponse => ({
  stock: STOCK,
  condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0",
    dividendTaxRate: "0" },
  summary: { principal: "500000", profit: "3426", returnRate: "0.006853", asOf: "2024-02-16", isFinal: true },
  rows: [{ date: "2024-02-16", kind: "period", openPrice: "70000", closePrice: "70500", boughtShares: 0, heldShares: 7,
    cash: "9926", principal: "500000", balance: "493500", profit: "3426", returnRate: "0.006853" }],
  hasMore: false, oldestReturned: "2024-02-16",
});
const SERIES = { from: "2024-01-15", to: "2024-02-16", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, points: [{ date: "2024-02-16", balance: "503426", returnRate: "0.006853" }],
  gaps: [] } as unknown as SimulationSeriesResponse;

/** 표 요청만 — 시계열(`/series`)은 뺀다. */
const tableCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => !p.includes("/series"));
const seriesCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => p.includes("/series"));

const selectedTab = (scope: HTMLElement = document.body) =>
  within(scope).getAllByRole("tab").find((t) => t.getAttribute("aria-selected") === "true")?.textContent;

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();
  // 처음 값 그대로 — 이 파일은 스토어의 처음 단위를 본다(다른 화면 테스트처럼 `daily`를 심지 않는다).
  useFxWorkspaceStore.setState(useFxWorkspaceStore.getInitialState(), true);
  useStockStore.setState(useStockStore.getInitialState(), true);
  useCryptoStore.setState(useCryptoStore.getInitialState(), true);
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
});

describe("외환 일자별 환율 표", () => {
  const DERIVED = { cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42" };
  const row = (date: string): PeriodRow => ({
    date, baseRate: "1354.200000", isProvisional: false, derived: DERIVED, periodFrom: `${date.slice(0, 8)}01`, periodTo: date,
    isOngoing: false,
  });
  const COVERAGE: CoverageRow[] = ["USD", "JPY", "EUR"].map((currency) => ({
    currency: currency as CoverageRow["currency"], coveredFrom: "2000-01-01", coveredThrough: "2026-08-28",
    firstAvailableDate: "2000-01-04", lastUpdatedAt: "2026-08-29T00:00:00Z",
  }));

  function answer(path: string): unknown {
    const currency = /currency=([A-Z]+)/.exec(path)?.[1] ?? "USD";
    if (path.startsWith("/api/fx/coverage")) return { coverage: COVERAGE };
    if (path.startsWith("/api/fx/latest")) {
      return { currency, quotePair: `${currency}/KRW`, date: "2026-08-28", baseRate: "1356.100000", quoteUnit: 1,
        isProvisional: false, fetchedAt: null, change: null } as unknown as LatestResponse;
    }
    if (path.startsWith("/api/fx/daily")) {
      const period = (/period=([a-z]+)/.exec(path)?.[1] ?? "daily") as DailyResponse["period"];
      return { currency, period, quoteUnit: 1, appliedSpread: DERIVED, spreadBasis: "current",
        rows: [row("2026-08-28"), row("2026-07-31")], hasMore: false, oldestReturned: "2026-07-31" } as DailyResponse;
    }
    if (path.startsWith("/api/fx/series")) {
      return { currency, quoteUnit: 1, from: "2025-08-28", to: "2026-08-28", downsampled: false, algorithm: "lttb",
        sourcePointCount: 1, points: [{ date: "2026-08-28", baseRate: "1356.100000" }], gaps: [] } as unknown as SeriesResponse;
    }
    throw new Error(`처리기가 없는 경로: ${path}`);
  }

  it("처음 단위는 월이다", () => {
    expect(useFxWorkspaceStore.getInitialState().period).toBe("monthly");
  });

  it("처음 연 화면은 '월' 탭이 선택돼 있고 첫 표 요청이 월이다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    render(<FxPage />);
    await screen.findByRole("table");
    expect(selectedTab(screen.getByRole("tablist", { name: "기간 단위 선택" }))).toBe("월");
    const daily = get.mock.calls.map(([p]) => String(p)).filter((p) => p.startsWith("/api/fx/daily"));
    expect(daily).toEqual(["/api/fx/daily?currency=USD&period=monthly"]);
  });
});

describe("주식 일자별 투자 성과", () => {
  const route = (table: () => unknown) => vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
    (path.includes("/series") ? SERIES : table()) as never);

  it("처음 단위는 월이다", () => {
    expect(useStockStore.getInitialState().tablePeriod).toBe("monthly");
  });

  it("일시금 처음 실행의 표 요청은 월이고, 시계열 요청에는 단위가 없다", async () => {
    useStockStore.setState({ input: STOCK_INPUT });
    const get = route(lump);
    await useStockStore.getState().run();
    expect(tableCalls(get)).toEqual([`/api/stocks/simulation?${STOCK_QUERY}&period=monthly`]);
    expect(seriesCalls(get)).toEqual([`/api/stocks/simulation/series?${STOCK_QUERY}`]);
  });

  it("적립식 처음 실행도 월이다", async () => {
    useStockStore.setState({ input: STOCK_INPUT, plan: { mode: "recurring", frequency: "monthly" } });
    const get = route(() => STOCK_RECURRING);
    await useStockStore.getState().run();
    expect(tableCalls(get)).toEqual([`/api/stocks/recurring-simulation?${STOCK_RECURRING_QUERY}&period=monthly`]);
  });

  it("이력 다시 실행도 월이다", async () => {
    const apple = { market: "NASDAQ" as const, symbol: "AAPL", name: "Apple Inc.", currency: "USD" };
    const entry: SimulationHistoryEntry = { id: "a", stock: apple, start: "2020-01-02", principal: "10000000",
      principalCurrency: "KRW", reinvest: false, savedAt: "2026-10-05T00:00:00Z" };
    useStockStore.setState({ history: [entry] });
    const get = route(lump);
    await useStockStore.getState().rerunHistory("a");
    expect(tableCalls(get)[0]).toBe("/api/stocks/simulation?market=NASDAQ&symbol=AAPL&start=2020-01-02&principal=10000000"
      + "&principalCurrency=KRW&reinvest=false&period=monthly");
  });

  it("'일'로 바꾼 뒤 다시 실행하면 '일'이 남는다 — 처음 값으로 되돌리지 않는다", async () => {
    useStockStore.setState({ input: STOCK_INPUT });
    const get = route(lump);
    await useStockStore.getState().run();
    await useStockStore.getState().setTablePeriod("daily");
    await useStockStore.getState().run();
    expect(useStockStore.getState().tablePeriod).toBe("daily");
    expect(tableCalls(get).at(-1)).toBe(`/api/stocks/simulation?${STOCK_QUERY}`);
  });

  it("화면의 표 머리는 '월' 탭이 선택된 채 그려진다", async () => {
    useStockStore.setState({ input: STOCK_INPUT });
    route(lump);
    render(<StocksPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("table");
    expect(selectedTab(screen.getByRole("tablist", { name: "기간 단위 선택" }))).toBe("월");
  });
});

describe("가상자산 일자별 투자 성과", () => {
  const route = (table: () => unknown) => vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
    (path.includes("/series") ? SERIES : table()) as never);

  it("처음 단위는 월이다", () => {
    expect(useCryptoStore.getInitialState().tablePeriod).toBe("monthly");
  });

  it("일시금 처음 실행의 표 요청은 월이고, 시계열 요청에는 단위가 없다", async () => {
    useCryptoStore.setState({ input: CRYPTO_INPUT });
    const get = route(() => CRYPTO_RESULT);
    await useCryptoStore.getState().run();
    expect(tableCalls(get)).toEqual([`/api/crypto/simulation?${CRYPTO_QUERY}&period=monthly`]);
    expect(seriesCalls(get)).toEqual([`/api/crypto/simulation/series?${CRYPTO_QUERY}`]);
  });

  it("적립식 처음 실행도 월이다", async () => {
    useCryptoStore.setState({ input: CRYPTO_INPUT, plan: { mode: "recurring", frequency: "daily" } });
    const get = route(() => CRYPTO_RECURRING);
    await useCryptoStore.getState().run();
    expect(tableCalls(get)).toEqual([expect.stringMatching(/^\/api\/crypto\/recurring-simulation\?.*&period=monthly$/)]);
  });

  it("'일'로 바꾼 뒤 다시 실행하면 '일'이 남는다", async () => {
    useCryptoStore.setState({ input: CRYPTO_INPUT });
    const get = route(() => CRYPTO_RESULT);
    await useCryptoStore.getState().run();
    await useCryptoStore.getState().setTablePeriod("daily");
    await useCryptoStore.getState().run();
    expect(tableCalls(get).at(-1)).toBe(`/api/crypto/simulation?${CRYPTO_QUERY}`);
  });

  it("화면의 표 머리는 '월' 탭이 선택된 채 그려진다", async () => {
    useCryptoStore.setState({ input: CRYPTO_INPUT });
    route(() => CRYPTO_RESULT);
    render(<CryptoPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByRole("table");
    expect(selectedTab(screen.getByRole("tablist", { name: "기간 단위 선택" }))).toBe("월");
  });
});

describe("투자 비교의 투자 시뮬레이션 모달", () => {
  const store = () => useCompareDetailStore.getState();
  const target = (c: (typeof CASES)[number]): DetailTarget => ({
    key: c.label, name: c.name, href: null, condition: c.condition, target: c.target });
  const menuOf = (c: (typeof CASES)[number]) =>
    comparisonPath(c.condition, c.target).replace("/api/comparison/", "/api/");

  it("닫힌 상태의 단위는 월이다", () => {
    expect(useCompareDetailStore.getInitialState().period).toBe("monthly");
  });

  it.each(CASES.filter((c) => pageable(c.condition)).map((c) => [c.label, c]))(
    "%s — 열 때의 표 요청부터 월이고, 시계열 요청에는 단위가 없다", async (_label, c) => {
      const get = routeCompare((path) => (path.includes("/series") ? MODAL_SERIES : c.menu));
      await store().openDetail(target(c));
      const menu = menuOf(c);
      expect(tableCalls(get)).toEqual([`${menu}&period=monthly`]);
      expect(seriesCalls(get)).toEqual([`${menu.split("?")[0]}/series?${menu.split("?")[1]}`]);
      expect(store().period).toBe("monthly");
    });

  it.each(CASES.filter((c) => !pageable(c.condition)).map((c) => [c.label, c]))(
    "%s — 단추가 없는 표라 요청에 단위를 싣지 않는다", async (_label, c) => {
      const get = routeCompare((path) => (path.includes("/series") ? MODAL_SERIES : c.menu));
      await store().openDetail(target(c));
      expect(tableCalls(get)).toEqual([menuOf(c)]);
      expect(get.mock.calls.some(([p]) => String(p).includes("period="))).toBe(false);
    });

  it("'일'로 바꾸면 단위 없이 받고, 닫고 다시 열면 '월'부터다", async () => {
    const c = CASES[0];
    const get = routeCompare((path) => (path.includes("/series") ? MODAL_SERIES : c.menu));
    await store().openDetail(target(c));
    await store().setPeriod("daily");
    expect(tableCalls(get).at(-1)).toBe(menuOf(c));
    store().close();
    await store().openDetail(target(c));
    expect(store().period).toBe("monthly");
    expect(tableCalls(get).at(-1)).toBe(`${menuOf(c)}&period=monthly`);
  });

  it("모달의 주식 표는 '월' 탭이 선택된 채 그려진다", async () => {
    const c = CASES.find((x) => x.condition.asset === "stock" && x.condition.method === "recurring") ?? CASES[0];
    routeCompare((path) => (path.includes("/series") ? MODAL_SERIES : STOCK_RECURRING));
    render(<SimulationModal />);
    await act(async () => { await store().openDetail(target(c)); });
    const table = await screen.findByTestId("simulation-modal-table");
    expect(selectedTab(table)).toBe("월");
  });
});

describe("대상 밖", () => {
  it("대시보드 지표 모달의 일자별 표는 처음 '일' 그대로다", () => {
    expect(useIndicatorTableStore.getInitialState().period).toBe("daily");
  });
});
