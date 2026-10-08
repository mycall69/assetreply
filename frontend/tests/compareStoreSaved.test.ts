/**
 * 비교 스토어의 저장 슬라이스 (013 T067) — FR-012a, FR-016~FR-019, SC-006, SC-007, data-model 5.2.
 *
 * - 저장은 결과가 있고 흐리지 않고 막히지 않았을 때만이다(수집 중인 대상이 남아도 된다 — 조건만의 기록이다). 본문은 결과를 낸 정규 조건 + 이름이다
 * - 저장·삭제가 실패해도 결과·실행 상태는 그대로다(FR-019)
 * - 불러오기는 자산군·방식·입력·대상을 채우고 곧바로 실행한다 — 처음 실행과 같은 질의다(SC-006). 불러온 대상이 지금 막히면 막힘 칸이다(FR-017)
 * - 어디에서도 이력을 쓰지 않는다(FR-020)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CompareCondition } from "@/lib/compareCondition";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import { isStale, saveBlockReason, useCompareStore } from "@/stores/compareStore";
import {
  BTC_T,
  ETH_T,
  HYNIX_T,
  SAMSUNG_T,
  XLK_T,
  apiError,
  collectingStock,
  ok,
  routeCompare,
} from "./support/compareFixtures";
import { historyStub } from "./support/historyStub";
import { savedComparisonStub } from "./support/savedComparisonStub";

const streams = vi.hoisted(() => ({ stock: [] as StockProgressHandlers[] }));
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (_jobId: number, handlers: StockProgressHandlers) => {
    streams.stock.push(handlers);
    return () => undefined;
  },
}));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const store = () => useCompareStore.getState();

beforeEach(() => {
  vi.restoreAllMocks();
  streams.stock.length = 0;
  store().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02", amount: "10000000" });
});

async function runStocks(answer: (path: string) => unknown = (p) => ok(p.includes("XLK") ? XLK_T : SAMSUNG_T)) {
  const get = routeCompare(answer);
  for (const t of [SAMSUNG_T, HYNIX_T, XLK_T]) store().addTarget(t);
  await store().runComparison();
  return get;
}

const posts = () => savedComparisonStub.calls().filter((c) => c.method === "POST");

const CRYPTO: CompareCondition = {
  v: 1, asset: "crypto", method: "recurring", frequency: "weekly", start: "2021-03-01", amount: "100000",
  principalCurrency: "KRW", reinvest: null, targets: [BTC_T, ETH_T],
};

describe("저장", () => {
  it("실행 전에는 저장할 수 없다", async () => {
    expect(saveBlockReason(store())).not.toBeNull();
    expect(await store().saveComparison("가")).toBe(false);
    expect(posts()).toEqual([]);
  });

  it("결과가 있으면 결과를 낸 정규 조건과 이름을 보내고 목록이 응답 목록이다", async () => {
    await runStocks();
    expect(saveBlockReason(store())).toBeNull();
    expect(await store().saveComparison("반도체 셋")).toBe(true);
    expect(posts()).toHaveLength(1);
    expect(posts()[0].body).toEqual({ name: "반도체 셋", condition: store().run?.condition });
    expect(store().saved.entries.map((e) => e.name)).toEqual(["반도체 셋"]);
    expect(store().saved.saveError).toBeNull();
  });

  it("수집 중인 대상이 남아도 저장할 수 있다", async () => {
    await runStocks((p) => (p.includes("000660") ? collectingStock(41) : ok(SAMSUNG_T)));
    expect(store().run?.byTarget["KRX|000660.KS"].status).toBe("collecting");
    expect(saveBlockReason(store())).toBeNull();
    expect(await store().saveComparison("가")).toBe(true);
  });

  it("흐린 동안은 저장할 수 없다 — 다시 실행한 뒤", async () => {
    await runStocks();
    store().setStart("2021-01-04");
    expect(isStale(store())).toBe(true);
    expect(saveBlockReason(store())).toBe("다시 실행한 뒤 저장할 수 있습니다");
    expect(await store().saveComparison("가")).toBe(false);
    expect(posts()).toEqual([]);
  });

  it("막히면 저장할 수 없다", async () => {
    await runStocks((p) => (p.includes("XLK")
      ? apiError(400, "before_listing", { startableFrom: "2021-11-29", basis: "listing" }) : ok(SAMSUNG_T)));
    expect(saveBlockReason(store())).not.toBeNull();
    expect(await store().saveComparison("가")).toBe(false);
    expect(posts()).toEqual([]);
  });

  it("실패하면 saveError이고 결과·실행 상태는 그대로다", async () => {
    await runStocks();
    const before = store().run;
    savedComparisonStub.fail("POST");
    expect(await store().saveComparison("가")).toBe(false);
    expect(store().saved.saveError).toMatch(/저장하지 못했습니다/);
    expect(store().run).toBe(before);
    savedComparisonStub.heal();
    expect(await store().saveComparison("가")).toBe(true);
    expect(store().saved.saveError).toBeNull();
  });
});

describe("목록", () => {
  it("받기 실패는 loadError이고 다시 받으면 목록이다", async () => {
    savedComparisonStub.seed([{ name: "가", condition: CRYPTO as unknown as Record<string, unknown> }]);
    savedComparisonStub.fail("GET");
    await store().loadSaved();
    expect(store().saved.loadError).toMatch(/받지 못했습니다/);
    expect(store().saved.loading).toBe(false);
    savedComparisonStub.heal();
    await store().loadSaved();
    expect(store().saved.loadError).toBeNull();
    expect(store().saved.entries.map((e) => e.name)).toEqual(["가"]);
  });

  it("삭제하면 빠지고, 실패하면 removeError이고 목록은 그대로다", async () => {
    savedComparisonStub.seed([
      { name: "가", condition: CRYPTO as unknown as Record<string, unknown> },
      { name: "나", condition: CRYPTO as unknown as Record<string, unknown> }]);
    await store().loadSaved();
    const [first] = store().saved.entries;
    savedComparisonStub.fail("DELETE");
    await store().removeSaved(first.id);
    expect(store().saved.removeError).toMatch(/지우지 못했습니다/);
    expect(store().saved.entries).toHaveLength(2);
    savedComparisonStub.heal();
    await store().removeSaved(first.id);
    expect(store().saved.removeError).toBeNull();
    expect(store().saved.entries.map((e) => e.id)).not.toContain(first.id);
  });
});

describe("불러오기", () => {
  it("저장한 조건을 채우고 곧바로 실행한다 — 처음 실행과 같은 질의다", async () => {
    const first = await runStocks();
    const firstPaths = first.mock.calls.map(([p]) => p).sort();
    await store().saveComparison("셋");
    const saved = store().saved.entries[0];

    // 새로 연 화면 — 입력이 처음 값이다.
    store().dispose();
    useCompareStore.setState(useCompareStore.getInitialState(), true);
    vi.restoreAllMocks(); // 첫 실행의 모의를 풀어 다음 호출만 센다
    const again = routeCompare((p) => ok(p.includes("XLK") ? XLK_T : SAMSUNG_T));
    await store().loadSaved();
    await store().openSaved(saved.id);
    const state = store();
    expect(state.asset).toBe("stock");
    expect(state.method).toBe("lump_sum");
    expect(state.start).toBe("2020-01-02");
    expect(state.amount).toBe("10000000");
    expect(state.targets.map((t) => ("symbol" in t ? t.symbol : ""))).toEqual(["005930.KS", "000660.KS", "XLK"]);
    expect(again.mock.calls.map(([p]) => p).sort()).toEqual(firstPaths);
    expect(state.run?.condition).toEqual(saved.condition);
    expect(isStale(state)).toBe(false);
  });

  it("적립식 주기·원금 통화·재투자도 채운다", async () => {
    savedComparisonStub.seed([{ name: "코인", condition: CRYPTO as unknown as Record<string, unknown> }]);
    const get = routeCompare(() => ok(BTC_T));
    await store().loadSaved();
    await store().openSaved(store().saved.entries[0].id);
    const state = store();
    expect([state.asset, state.method, state.frequency, state.start, state.amount, state.principalCurrency])
      .toEqual(["crypto", "recurring", "weekly", "2021-03-01", "100000", "KRW"]);
    expect(get.mock.calls.every(([p]) => p.startsWith("/api/comparison/crypto/recurring-simulation?"))).toBe(true);
    expect(get.mock.calls.map(([p]) => new URLSearchParams(p.split("?")[1]).get("frequency"))).toEqual(["weekly", "weekly"]);
  });

  it("불러온 대상이 지금 막히면 막힘 칸이다", async () => {
    savedComparisonStub.seed([{ name: "코인", condition: CRYPTO as unknown as Record<string, unknown> }]);
    routeCompare((p) => (p.includes("coinId=18") ? apiError(404, "unknown_coin") : ok(BTC_T)));
    await store().loadSaved();
    await store().openSaved(store().saved.entries[0].id);
    const eth = store().run?.byTarget["18"];
    expect(eth?.status).toBe("blocked");
    expect(eth?.status === "blocked" && eth.reason.code).toBe("unknown_coin");
  });

  it("어디에서도 이력을 쓰지 않는다", async () => {
    await runStocks();
    await store().saveComparison("가");
    await store().openSaved(store().saved.entries[0].id);
    await store().removeSaved(store().saved.entries[0].id);
    expect(historyStub.calls().filter((c) => c.method === "PUT")).toEqual([]);
  });
});
