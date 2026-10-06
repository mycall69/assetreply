/**
 * 주식 스토어의 적립식 (011 T022) — FR-001, FR-016, FR-033, FR-034, research R11-10·R11-11.
 *
 * - 투자 방식은 `plan` 칸이다(기본 일시금·매달). `input`(일시금 다섯 칸)은 그대로다 — `stockStoreRerun.test.ts`가 그 모양을 고정한다
 * - 적립식 `run()`은 따로 된 경로(`/api/stocks/recurring-simulation`)를 정확한 질의로 부르고, 결과는 `recurring`에 들어간다(일시금 칸은 빈다)
 * - 202면 일시금과 같이 진행을 기다린다. 이력에 남기지 않는다
 * - 방식·주기를 바꾸면 두 결과를 모두 비운다 — 한쪽 결과가 다른 방식의 조건과 함께 보이지 않게
 * - `loadMore`는 적립식 경로의 `before`
 * - 이력
 *   - 적립식 항목은 방식·주기를 남긴다
 *   - 다시 실행하면 `plan`을 맞추고, 옛 항목(방식 없음)은 일시금이다
 *   - 비교는 적립식 시계열 경로를 쓰고 범례 이름에 방식을 붙인다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type {
  RecurringStockResponse,
  SimulationHistoryEntry,
  SimulationResponse,
  SimulationSeriesResponse,
} from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";
// 012 승인 2026-10-07 — 012부터 이력은 로컬 DB에 있다. 브라우저 lib 대신 이력 대역에서 읽는다(research R12-12).
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const QUERY = "market=KRX&symbol=005930.KS&start=2024-01-15&amount=500000&principalCurrency=KRW&frequency=monthly&reinvest=true";

const RESULT: RecurringStockResponse = {
  stock: STOCK,
  condition: { mode: "recurring", start: "2024-01-15", amount: "500000", principalCurrency: "KRW", frequency: "monthly",
    reinvest: true, tradeFeeRate: "0.000150", dividendTaxRate: "0.154000" },
  summary: {
    contributed: "1000000", contributedKrw: "1000000", contributions: 2, pendingAfterEnd: 0, heldShares: 14,
    pending: "26854.05", dividendCash: "0", totalKrw: "999854.05", buyFeeTotal: "145", dividendTaxTotal: "0",
    saleCost: { fee: "145", tax: "1946", total: "2091", taxKind: "transaction_tax", taxRate: "0.0020", gain: null,
      deduction: null },
    feeTotal: "290", taxTotal: "1946", profit: "-145.95", returnRate: "-0.000146", profitAfterSale: "-2236.95",
    returnRateAfterSale: "-0.002237", asOf: "2024-02-15", isFinal: true,
  },
  rows: [{ date: "2024-02-15", kind: "contribution", openPrice: "69000", closePrice: "69500", contribution: "500000",
    boughtShares: 7, heldShares: 14, pending: "26854.05", dividendCash: "0", contributed: "1000000",
    contributedKrw: "1000000", balance: "973000", profit: "-145.95", returnRate: "-0.000146", tradeFee: "72.45" }],
  hasMore: true,
  oldestReturned: "2024-02-15",
};

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-15", to: "2024-02-15", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1,
  points: [{ date: "2024-02-15", balance: "999854.05", returnRate: "-0.000146", principal: "1000000", price: "69500" }],
  gaps: [],
};

const LUMP: SimulationResponse = {
  stock: STOCK,
  condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0",
    dividendTaxRate: "0" },
  summary: { principal: "500000", profit: "1", returnRate: "0.1", asOf: "2024-02-15", isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

function mockGet() {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.startsWith("/api/stocks/recurring-simulation/series")) return SERIES as never;
    if (path.startsWith("/api/stocks/recurring-simulation")) return RESULT as never;
    if (path.startsWith("/api/stocks/simulation/series")) return SERIES as never;
    return LUMP as never;
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useStockStore.setState({
    input: { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
    plan: { mode: "lump_sum", frequency: "monthly" },
    recurring: null, summary: null, rows: [], series: null, history: [], selectedHistory: [], comparison: [],
    error: null, collecting: null,
  });
});

describe("적립식 실행", () => {
  it("기본 방식은 일시금·매달이다", () => {
    expect(useStockStore.getInitialState().plan).toEqual({ mode: "lump_sum", frequency: "monthly" });
  });

  it("적립식이면 따로 된 경로를 정확한 질의로 부르고 결과는 recurring에 들어간다", async () => {
    const get = mockGet();
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "monthly" });
    await useStockStore.getState().run();
    expect(get).toHaveBeenNthCalledWith(1, `/api/stocks/recurring-simulation?${QUERY}`);
    expect(get).toHaveBeenNthCalledWith(2, `/api/stocks/recurring-simulation/series?${QUERY}`);
    const state = useStockStore.getState();
    expect(state.recurring?.summary).toEqual(RESULT.summary);
    expect(state.recurring?.rows).toEqual(RESULT.rows);
    expect(state.recurring?.series).toEqual(SERIES);
    expect(state.rows).toEqual([]);
    expect(state.summary).toBeNull();
    expect(state.input).toEqual({ stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW",
      reinvest: true });
  });

  it("202면 진행을 기다리고 이력에 남기지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ status: "collecting", stockId: 1, jobId: 7 } as never);
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    await useStockStore.getState().run();
    const state = useStockStore.getState();
    expect(state.collecting).toMatchObject({ status: "collecting", jobId: 7 });
    expect(state.recurring).toBeNull();
    expect(historyStub.entries("stock")).toEqual([]); // 012 승인 2026-10-07
  });

  it("방식이나 주기를 바꾸면 두 결과를 모두 비운다", async () => {
    mockGet();
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "monthly" });
    await useStockStore.getState().run();
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    expect(useStockStore.getState().recurring).toBeNull();
    useStockStore.setState({ summary: LUMP.summary });
    useStockStore.getState().setPlan({ mode: "lump_sum", frequency: "weekly" });
    expect(useStockStore.getState().summary).toBeNull();
  });

  it("이어 받기는 적립식 경로의 before다", async () => {
    const get = mockGet();
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "monthly" });
    await useStockStore.getState().run();
    await useStockStore.getState().loadMore();
    expect(get).toHaveBeenLastCalledWith(`/api/stocks/recurring-simulation?${QUERY}&before=2024-02-15`);
    expect(useStockStore.getState().recurring?.rows).toHaveLength(2);
  });

  it("실행한 적립식 조건을 방식·주기와 함께 이력에 남긴다", async () => {
    mockGet();
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "monthly" });
    await useStockStore.getState().run();
    // 012 승인 2026-10-07
    expect(historyStub.entries("stock")[0]).toMatchObject({ mode: "recurring", frequency: "monthly", principal: "500000" });
  });
});

describe("적립식 이력", () => {
  const RECURRING: SimulationHistoryEntry = {
    id: "KRX|005930.KS|2024-01-15|500000|KRW|R|recurring:monthly", stock: STOCK, start: "2024-01-15",
    principal: "500000", principalCurrency: "KRW", reinvest: true, mode: "recurring", frequency: "monthly",
    savedAt: "2026-10-05T00:00:00Z",
  };
  const OLD: SimulationHistoryEntry = {
    id: "KRX|005930.KS|2024-01-15|500000|KRW|R", stock: STOCK, start: "2024-01-15", principal: "500000",
    principalCurrency: "KRW", reinvest: true, savedAt: "2026-10-01T00:00:00Z",
  };

  it("적립식 항목을 다시 실행하면 방식을 맞추고 적립식 경로로 실행한다", async () => {
    const get = mockGet();
    useStockStore.setState({ history: [RECURRING] });
    await useStockStore.getState().rerunHistory(RECURRING.id);
    expect(useStockStore.getState().plan).toEqual({ mode: "recurring", frequency: "monthly" });
    expect(get).toHaveBeenNthCalledWith(1, `/api/stocks/recurring-simulation?${QUERY}`);
  });

  it("옛 항목은 일시금으로 다시 실행한다", async () => {
    const get = mockGet();
    useStockStore.setState({ history: [OLD], plan: { mode: "recurring", frequency: "weekly" } });
    await useStockStore.getState().rerunHistory(OLD.id);
    expect(useStockStore.getState().plan.mode).toBe("lump_sum");
    expect(get.mock.calls[0][0]).toMatch(/^\/api\/stocks\/simulation\?/);
  });

  it("비교는 적립식 시계열 경로를 쓰고 범례에 방식을 붙인다", async () => {
    const get = mockGet();
    historyStub.seed("stock", [RECURRING, OLD]); // 012 승인 2026-10-07 — 브라우저 키 대신 대역에 심는다
    useStockStore.setState({ history: [RECURRING, OLD], selectedHistory: [RECURRING.id, OLD.id] });
    await useStockStore.getState().compareSelected();
    const paths = get.mock.calls.map((c) => c[0]);
    expect(paths).toContain(`/api/stocks/recurring-simulation/series?${QUERY}`);
    expect(paths.some((p) => p.startsWith("/api/stocks/simulation/series?"))).toBe(true);
    expect(useStockStore.getState().comparison.map((c) => c.label)).toEqual(["삼성전자 · 적립식 매달", "삼성전자"]);
  });
});
