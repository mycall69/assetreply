/**
 * 가상자산 스토어의 적립식 (011 T036) — FR-017, FR-019, FR-033, FR-034, research R11-11.
 *
 * - 투자 방식은 `plan` 칸이다(기본 일시금·매달). `input`(일시금 네 칸)은 그대로다
 * - 적립식 `run()`은 `/api/crypto/recurring-simulation`을 정확한 질의로 부르고, 결과는 `recurring`에 들어간다(일시금 칸은 빈다)
 * - 202면 일시금과 같이 진행을 기다린다. 이력에 남기지 않는다
 * - 방식·주기를 바꾸면 두 결과를 모두 비운다
 * - `loadMore`는 적립식 경로의 `before`
 * - 이력 — 적립식 항목은 방식·주기를 남기고, 다시 실행하면 `plan`을 맞춘다. 옛 항목은 일시금이다. 비교 범례에 방식을 붙인다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { loadCryptoHistory } from "@/lib/cryptoHistory";
import type {
  CryptoHistoryEntry,
  CryptoSimulationResponse,
  RecurringCryptoResponse,
  SimulationSeriesResponse,
} from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const QUERY = "coinId=17&start=2024-01-15&amount=10000&principalCurrency=KRW&frequency=daily";

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
  hasMore: true,
  oldestReturned: "2024-01-16",
};

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-15", to: "2024-01-16", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1,
  points: [{ date: "2024-01-16", balance: "20400", returnRate: "0.020000", principal: "20000", price: "42000" }],
  gaps: [],
};

const LUMP: CryptoSimulationResponse = {
  coin: { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" },
  condition: { start: "2024-01-15", principal: "10000", principalCurrency: "KRW", tradeFeeRate: "0.001000" },
  summary: { principal: "10000", profit: "1", returnRate: "0.1", asOf: "2024-01-16", isFinal: true, boughtOn: "2024-01-01" },
  rows: [], hasMore: false, oldestReturned: null,
} as unknown as CryptoSimulationResponse;

function mockGet() {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.startsWith("/api/crypto/recurring-simulation/series")) return SERIES as never;
    if (path.startsWith("/api/crypto/recurring-simulation")) return RESULT as never;
    if (path.startsWith("/api/crypto/simulation/series")) return SERIES as never;
    return LUMP as never;
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useCryptoStore.setState({
    input: { coin: BTC, start: "2024-01-15", principal: "10000", principalCurrency: "KRW" },
    plan: { mode: "lump_sum", frequency: "monthly" },
    recurring: null, summary: null, rows: [], series: null, history: [], selectedHistory: [], comparison: [],
    error: null, collecting: null,
  });
});

describe("가상자산 적립식 실행", () => {
  it("기본 방식은 일시금·매달이다", () => {
    expect(useCryptoStore.getInitialState().plan).toEqual({ mode: "lump_sum", frequency: "monthly" });
  });

  it("적립식이면 따로 된 경로를 정확한 질의로 부르고 결과는 recurring에 들어간다", async () => {
    const get = mockGet();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    await useCryptoStore.getState().run();
    expect(get).toHaveBeenNthCalledWith(1, `/api/crypto/recurring-simulation?${QUERY}`);
    expect(get).toHaveBeenNthCalledWith(2, `/api/crypto/recurring-simulation/series?${QUERY}`);
    const state = useCryptoStore.getState();
    expect(state.recurring?.summary).toEqual(RESULT.summary);
    expect(state.recurring?.rows).toEqual(RESULT.rows);
    expect(state.recurring?.series).toEqual(SERIES);
    expect(state.rows).toEqual([]);
    expect(state.summary).toBeNull();
    expect(state.input).toEqual({ coin: BTC, start: "2024-01-15", principal: "10000", principalCurrency: "KRW" });
  });

  it("202면 진행을 기다리고 이력에 남기지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ status: "collecting", coinId: 17, jobId: 7 } as never);
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    await useCryptoStore.getState().run();
    const state = useCryptoStore.getState();
    expect(state.collecting).toMatchObject({ status: "collecting", jobId: 7 });
    expect(state.recurring).toBeNull();
    expect(loadCryptoHistory()).toEqual([]);
  });

  it("방식이나 주기를 바꾸면 두 결과를 모두 비운다", async () => {
    mockGet();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    await useCryptoStore.getState().run();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    expect(useCryptoStore.getState().recurring).toBeNull();
    useCryptoStore.setState({ summary: LUMP.summary });
    useCryptoStore.getState().setPlan({ mode: "lump_sum", frequency: "weekly" });
    expect(useCryptoStore.getState().summary).toBeNull();
  });

  it("이어 받기는 적립식 경로의 before다", async () => {
    const get = mockGet();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    await useCryptoStore.getState().run();
    await useCryptoStore.getState().loadMore();
    expect(get).toHaveBeenLastCalledWith(`/api/crypto/recurring-simulation?${QUERY}&before=2024-01-16`);
    expect(useCryptoStore.getState().recurring?.rows).toHaveLength(2);
  });

  it("실행한 적립식 조건을 방식·주기와 함께 이력에 남긴다", async () => {
    mockGet();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    await useCryptoStore.getState().run();
    expect(loadCryptoHistory()[0]).toMatchObject({ mode: "recurring", frequency: "daily", principal: "10000" });
  });

  it("설정이 바뀐 뒤 다시 받기는 적립식 결과에도 한다", async () => {
    const get = mockGet();
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    await useCryptoStore.getState().run();
    get.mockClear();
    await useCryptoStore.getState().refreshIfRan();
    expect(get).toHaveBeenNthCalledWith(1, `/api/crypto/recurring-simulation?${QUERY}`);
  });
});

describe("가상자산 적립식 이력", () => {
  const COIN = { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin", currency: "USD" };
  const RECURRING: CryptoHistoryEntry = {
    id: "17|2024-01-15|10000|KRW|recurring:daily", coin: COIN, start: "2024-01-15", principal: "10000",
    principalCurrency: "KRW", mode: "recurring", frequency: "daily", savedAt: "2026-10-05T00:00:00Z",
  };
  const OLD: CryptoHistoryEntry = {
    id: "17|2024-01-15|10000|KRW", coin: COIN, start: "2024-01-15", principal: "10000", principalCurrency: "KRW",
    savedAt: "2026-10-01T00:00:00Z",
  };

  it("적립식 항목을 다시 실행하면 방식을 맞추고 적립식 경로로 실행한다", async () => {
    const get = mockGet();
    useCryptoStore.setState({ history: [RECURRING] });
    await useCryptoStore.getState().rerunHistory(RECURRING.id);
    expect(useCryptoStore.getState().plan).toEqual({ mode: "recurring", frequency: "daily" });
    expect(get).toHaveBeenNthCalledWith(1, `/api/crypto/recurring-simulation?${QUERY}`);
  });

  it("옛 항목은 일시금으로 다시 실행한다", async () => {
    const get = mockGet();
    useCryptoStore.setState({ history: [OLD], plan: { mode: "recurring", frequency: "weekly" } });
    await useCryptoStore.getState().rerunHistory(OLD.id);
    expect(useCryptoStore.getState().plan.mode).toBe("lump_sum");
    expect(get.mock.calls[0][0]).toMatch(/^\/api\/crypto\/simulation\?/);
  });

  it("비교는 적립식 시계열 경로를 쓰고 범례에 방식을 붙인다", async () => {
    const get = mockGet();
    useCryptoStore.setState({ history: [RECURRING, OLD], selectedHistory: [RECURRING.id, OLD.id] });
    await useCryptoStore.getState().compareSelected();
    const paths = get.mock.calls.map((c) => c[0]);
    expect(paths).toContain(`/api/crypto/recurring-simulation/series?${QUERY}`);
    expect(paths.some((p) => p.startsWith("/api/crypto/simulation/series?"))).toBe(true);
    expect(useCryptoStore.getState().comparison.map((c) => c.label))
      .toEqual(["비트코인 (BTC) · 적립식 매일", "비트코인 (BTC)"]);
  });
});
