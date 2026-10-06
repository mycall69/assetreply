/**
 * 주식 스토어의 표 단위 (012 T023) — FR-003, FR-006, FR-007, data-model 5.1, research R12-7·R12-8.
 *
 * - 처음 단위는 일이고, 일이면 요청에 `period`가 없다 — 기본 단위의 요청 문자열이 지금과 같다(기존 정확 비교 테스트 보호)
 * - 단위를 바꾸면 **표의 행만** 비우고 다시 받는다. 보드(요약)·시계열은 같은 객체로 남는다(FR-007 — 보드가 표를 따라가지 않는다)
 * - 늦은 응답은 표 차례 번호로 버린다. 일 → 주 → 일 전환의 첫 "일" 응답도 버린다(단위 비교만으로는 거르지 못한다). 이어 받기도 같다
 * - 다시 실행·이력의 다시 실행에도 고른 단위가 남는다. 실패하면 단위는 남고 표 자리에 오류가 있다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type {
  RecurringStockResponse,
  SimulationResponse,
  SimulationRow,
  SimulationSeriesResponse,
} from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const LUMP_QUERY = "market=KRX&symbol=005930.KS&start=2024-01-15&principal=500000&principalCurrency=KRW&reinvest=true";

const row = (date: string, over: Partial<SimulationRow> = {}): SimulationRow => ({
  date, kind: "period", openPrice: "70000", closePrice: "70500", boughtShares: 0, heldShares: 7, cash: "9926.5",
  principal: "500000", balance: "493500", profit: "3426.5", returnRate: "0.006853", ...over,
});

const lump = (dates: string[], hasMore = false): SimulationResponse => ({
  stock: STOCK,
  condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0",
    dividendTaxRate: "0" },
  summary: { principal: "500000", profit: "3426.5", returnRate: "0.006853", asOf: "2024-02-16", isFinal: true },
  rows: dates.map((d) => row(d)), hasMore, oldestReturned: dates.at(-1) ?? null,
});

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-15", to: "2024-02-16", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, points: [{ date: "2024-02-16", balance: "503426.5", returnRate: "0.006853" }],
  gaps: [],
} as unknown as SimulationSeriesResponse;

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useStockStore.setState({
    input: { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
    plan: { mode: "lump_sum", frequency: "monthly" },
    recurring: null, summary: null, rows: [], series: null, history: [], selectedHistory: [], comparison: [],
    error: null, collecting: null, tablePeriod: "daily", tableLoading: false, tableError: null,
  });
});

const store = () => useStockStore.getState();

function route(table: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.includes("/series")) return SERIES as never;
    return table(path) as never;
  });
}

describe("처음 단위와 요청", () => {
  it("처음 단위는 일이다", () => {
    expect(useStockStore.getInitialState().tablePeriod).toBe("daily");
  });

  it("일이면 요청에 period가 없다", async () => {
    const get = route(() => lump(["2024-02-16"]));
    await store().run();
    expect(get).toHaveBeenNthCalledWith(1, `/api/stocks/simulation?${LUMP_QUERY}`);
    expect(get).toHaveBeenNthCalledWith(2, `/api/stocks/simulation/series?${LUMP_QUERY}`);
  });
});

describe("단위 바꾸기", () => {
  it("표만 다시 받고 요약·시계열은 같은 객체로 남는다", async () => {
    const get = route((path) => (path.includes("period=weekly") ? lump(["2024-02-16", "2024-02-09"]) : lump(["2024-02-16"])));
    await store().run();
    const { summary, series } = store();
    get.mockClear();
    const pending = store().setTablePeriod("weekly");
    expect(store().rows).toEqual([]);  // 이전 단위의 행이 남지 않는다
    expect(store().tableLoading).toBe(true);
    await pending;
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith(`/api/stocks/simulation?${LUMP_QUERY}&period=weekly`);
    expect(store().tablePeriod).toBe("weekly");
    expect(store().rows.map((r) => r.date)).toEqual(["2024-02-16", "2024-02-09"]);
    expect(store().summary).toBe(summary);
    expect(store().series).toBe(series);
    expect(store().tableLoading).toBe(false);
  });

  it("적립식이면 적립식 경로의 표만 다시 받는다", async () => {
    const recurring: RecurringStockResponse = {
      stock: STOCK,
      condition: { mode: "recurring", start: "2024-01-15", amount: "500000", principalCurrency: "KRW", frequency: "monthly",
        reinvest: true, tradeFeeRate: "0", dividendTaxRate: "0" },
      summary: { asOf: "2024-02-16", isFinal: true } as RecurringStockResponse["summary"],
      rows: [], hasMore: false, oldestReturned: null,
    };
    const get = route(() => recurring);
    store().setPlan({ mode: "recurring", frequency: "monthly" });
    await store().run();
    const before = store().recurring;
    get.mockClear();
    await store().setTablePeriod("monthly");
    expect(get).toHaveBeenCalledWith(expect.stringMatching(/^\/api\/stocks\/recurring-simulation\?.*&period=monthly$/));
    expect(store().recurring?.summary).toBe(before?.summary);
    expect(store().recurring?.series).toBe(before?.series);
  });

  it("결과가 없으면 단위만 바꾸고 요청하지 않는다", async () => {
    const get = route(() => lump([]));
    await store().setTablePeriod("monthly");
    expect(store().tablePeriod).toBe("monthly");
    expect(get).not.toHaveBeenCalled();
  });

  it("실패하면 고른 단위는 남고 표 자리에 오류가 있다", async () => {
    route(() => lump(["2024-02-16"]));
    await store().run();
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("네트워크"));
    await store().setTablePeriod("weekly");
    expect(store().tablePeriod).toBe("weekly");
    expect(store().tableError).not.toBeNull();
    expect(store().tableLoading).toBe(false);
  });
});

describe("늦은 응답", () => {
  it("주 → 월 사이에 늦게 온 주 응답은 버린다", async () => {
    route(() => lump(["2024-02-16"]));
    await store().run();
    let releaseWeekly: () => void = () => undefined;
    const weeklyGate = new Promise<void>((resolve) => { releaseWeekly = resolve; });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.includes("period=weekly")) { await weeklyGate; return lump(["2024-02-09"]) as never; }
      return lump(["2024-01-31"]) as never;
    });
    const weekly = store().setTablePeriod("weekly");
    await store().setTablePeriod("monthly");
    releaseWeekly();
    await weekly;
    expect(store().tablePeriod).toBe("monthly");
    expect(store().rows.map((r) => r.date)).toEqual(["2024-01-31"]);
  });

  it("일 → 주 → 일 전환의 첫 일 응답도 버린다", async () => {
    route(() => lump(["2024-02-16"]));
    await store().run();
    let releaseFirst: () => void = () => undefined;
    const firstGate = new Promise<void>((resolve) => { releaseFirst = resolve; });
    let dailyCalls = 0;
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.includes("period=weekly")) return lump(["2024-02-09"]) as never;
      dailyCalls += 1;
      if (dailyCalls === 1) { await firstGate; return lump(["2000-01-01"]) as never; }  // 늦게 온 첫 응답
      return lump(["2024-02-16"]) as never;
    });
    await store().setTablePeriod("weekly");
    const first = store().setTablePeriod("daily");  // 늦게 올 요청
    await store().setTablePeriod("weekly");
    await store().setTablePeriod("daily");
    releaseFirst();
    await first;
    expect(store().rows.map((r) => r.date)).toEqual(["2024-02-16"]);
  });

  it("단위를 바꾸는 동안 늦게 온 이어 받기는 붙이지 않는다", async () => {
    route(() => lump(["2024-02-16"], true));
    await store().run();
    let releaseMore: () => void = () => undefined;
    const moreGate = new Promise<void>((resolve) => { releaseMore = resolve; });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.includes("before=")) { await moreGate; return lump(["2024-02-15"]) as never; }
      return lump(["2024-02-09"]) as never;
    });
    const more = store().loadMore();
    await store().setTablePeriod("weekly");
    releaseMore();
    await more;
    expect(store().rows.map((r) => r.date)).toEqual(["2024-02-09"]);
  });

  it("이어 받기는 지금 단위로 요청한다", async () => {
    route(() => lump(["2024-02-16"], true));
    await store().run();
    await store().setTablePeriod("weekly");
    const get = route(() => lump(["2024-02-02"]));
    useStockStore.setState({ hasMore: true, oldestReturned: "2024-02-09" });
    await store().loadMore();
    expect(get).toHaveBeenCalledWith(`/api/stocks/simulation?${LUMP_QUERY}&before=2024-02-09&period=weekly`);
  });
});

describe("다시 실행", () => {
  it("다시 실행해도 고른 단위가 남고 그 단위로 받는다", async () => {
    route(() => lump(["2024-02-16"]));
    await store().run();
    await store().setTablePeriod("monthly");
    vi.restoreAllMocks();  // 앞 실행의 호출 기록을 지운다 — 같은 함수를 다시 감시하면 기록이 이어진다
    const get = route(() => lump(["2024-01-31"]));
    await store().run();
    expect(store().tablePeriod).toBe("monthly");
    expect(get).toHaveBeenNthCalledWith(1, `/api/stocks/simulation?${LUMP_QUERY}&period=monthly`);
    expect(get).toHaveBeenNthCalledWith(2, `/api/stocks/simulation/series?${LUMP_QUERY}`);  // 시계열에는 단위가 없다
  });
});
