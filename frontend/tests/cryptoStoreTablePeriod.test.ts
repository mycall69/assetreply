/**
 * 가상자산 스토어의 표 단위 (012 T024) — FR-003, FR-006, FR-007, data-model 5.1. 주식(T023)과 같은 규칙이다.
 *
 * - 처음 단위는 일이고 요청에 `period`가 없다. 단위를 바꾸면 표의 행만 다시 받는다(요약·시계열은 같은 객체)
 * - 늦은 응답은 차례 번호로 버린다. 다시 실행해도 단위가 남는다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { CryptoSimulationResponse, RecurringCryptoResponse } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";
import { RESULT } from "./support/cryptoFixtures";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const QUERY = `coinId=${BTC.coinId}&start=2020-01-15&principal=10000&principalCurrency=USD`;
const SERIES = { from: "2020-01-15", to: "2021-12-31", points: [], gaps: [], downsampled: false, algorithm: "lttb",
  sourcePointCount: 0, principalCurrency: "USD", basisCurrency: "KRW" };

const withDates = (dates: string[]): CryptoSimulationResponse => ({
  ...RESULT, rows: dates.map((date) => ({ ...RESULT.rows[0], date })), hasMore: false, oldestReturned: dates.at(-1) ?? null,
});

beforeEach(() => {
  vi.restoreAllMocks();
  useCryptoStore.getState().dispose();
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
    plan: { mode: "lump_sum", frequency: "monthly" },
    rows: [], summary: null, series: null, recurring: null, collecting: null, error: null, startable: null,
    tablePeriod: "daily", tableLoading: false, tableError: null,
  });
});

const store = () => useCryptoStore.getState();

function route(table: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.includes("/series")) return SERIES as never;
    return table(path) as never;
  });
}

describe("가상자산 표 단위", () => {
  it("처음은 일이고 요청에 period가 없다", async () => {
    expect(useCryptoStore.getInitialState().tablePeriod).toBe("daily");
    const get = route(() => withDates(["2021-12-31"]));
    await store().run();
    expect(get).toHaveBeenNthCalledWith(1, `/api/crypto/simulation?${QUERY}`);
  });

  it("단위를 바꾸면 표의 행만 다시 받는다", async () => {
    route(() => withDates(["2021-12-31"]));
    await store().run();
    const { summary, series } = store();
    const get = route(() => withDates(["2021-12-31", "2021-12-24"]));
    const pending = store().setTablePeriod("weekly");
    expect(store().rows).toEqual([]);
    await pending;
    expect(get).toHaveBeenCalledWith(`/api/crypto/simulation?${QUERY}&period=weekly`);
    expect(store().rows.map((r) => r.date)).toEqual(["2021-12-31", "2021-12-24"]);
    expect(store().summary).toBe(summary);
    expect(store().series).toBe(series);
  });

  it("적립식이면 적립식 경로의 표만 다시 받는다", async () => {
    const recurring = { coin: { coinId: BTC.coinId, symbol: "BTC", name: "Bitcoin", nameKo: null, currency: "USD" },
      condition: {}, summary: { asOf: "2021-12-31", isFinal: true }, rows: [], hasMore: false,
      oldestReturned: null } as unknown as RecurringCryptoResponse;
    route(() => recurring);
    store().setPlan({ mode: "recurring", frequency: "daily" });
    await store().run();
    const get = route(() => recurring);
    await store().setTablePeriod("monthly");
    expect(get).toHaveBeenCalledWith(expect.stringMatching(/^\/api\/crypto\/recurring-simulation\?.*&period=monthly$/));
  });

  it("늦게 온 이전 단위 응답은 버린다", async () => {
    route(() => withDates(["2021-12-31"]));
    await store().run();
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.includes("period=weekly")) { await gate; return withDates(["2021-12-24"]) as never; }
      return withDates(["2021-11-30"]) as never;
    });
    const weekly = store().setTablePeriod("weekly");
    await store().setTablePeriod("monthly");
    release();
    await weekly;
    expect(store().rows.map((r) => r.date)).toEqual(["2021-11-30"]);
  });

  it("다시 실행해도 단위가 남는다", async () => {
    route(() => withDates(["2021-12-31"]));
    await store().run();
    await store().setTablePeriod("weekly");
    vi.restoreAllMocks();  // 앞 실행의 호출 기록을 지운다
    const get = route(() => withDates(["2021-12-31"]));
    await store().run();
    expect(store().tablePeriod).toBe("weekly");
    expect(get).toHaveBeenNthCalledWith(1, `/api/crypto/simulation?${QUERY}&period=weekly`);
  });
});
