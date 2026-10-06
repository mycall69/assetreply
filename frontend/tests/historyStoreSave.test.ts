/**
 * 스토어의 이력 저장·삭제 (012 T047) — FR-011, FR-014, data-model 5.2.
 *
 * - 결과(200)가 나온 실행만 `PUT /api/history/{asset}`로 남긴다. 조건은 012 전 항목 모양 그대로다(`id`·`savedAt` 없음 — 결과도 없음). 202면 남기지 않는다
 * - 저장이 실패해도 결과는 그대로 보이고, 실패를 알린다(FR-014 — 조용히 실패하지 않는다)
 * - 삭제는 `DELETE`이고 실패하면 알린다. 다시 실행은 서버 `id`로 항목을 찾는다
 * - 저장 응답의 목록으로 이력과 보관 기간이 바뀐다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { SimulationResponse, SimulationSeriesResponse } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { useStockStore } from "@/stores/stockStore";
import { RESULT as DEPOSIT_RESULT } from "./support/depositFixtures";
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const SERIES = { from: "2024-01-15", to: "2024-02-16", points: [], gaps: [], downsampled: false, algorithm: "lttb",
  sourcePointCount: 0, principalCurrency: "KRW", basisCurrency: "KRW" } as unknown as SimulationSeriesResponse;
const LUMP: SimulationResponse = {
  stock: STOCK,
  condition: { start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0",
    dividendTaxRate: "0" },
  summary: { principal: "500000", profit: "1", returnRate: "0.1", asOf: "2024-02-16", isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

const CONDITION = { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true };
const ID = "KRX|005930.KS|2024-01-15|500000|KRW|R";

function answer(result: unknown = LUMP) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
    (path.includes("/series") ? SERIES : result) as never);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useStockStore.setState({
    input: { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
    plan: { mode: "lump_sum", frequency: "monthly" }, recurring: null, summary: null, rows: [], series: null,
    history: [], selectedHistory: [], comparison: [], historySaveError: null, error: null, collecting: null,
  });
  useDepositStore.getState().dispose();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" }, product: "deposit",
    summary: null, rows: [], history: [], selectedHistory: [], comparison: [], historySaveError: null, error: null,
  });
});

const puts = () => historyStub.calls().filter((c) => c.method === "PUT");

describe("주식", () => {
  it("결과가 나오면 조건만 저장하고 응답 목록을 쓴다", async () => {
    answer();
    await useStockStore.getState().run();
    expect(puts()).toEqual([{ method: "PUT", path: "/api/history/stock", body: { condition: CONDITION } }]);
    expect(useStockStore.getState().history.map((e) => e.id)).toEqual([ID]);
    expect(useStockStore.getState().retentionDays).toBe(30);
    expect(useStockStore.getState().historySaveError).toBeNull();
  });

  it("적립식은 방식·주기를 함께 저장한다", async () => {
    answer({ ...LUMP, condition: { mode: "recurring" }, summary: { asOf: "2024-02-16", isFinal: true } });
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    await useStockStore.getState().run();
    expect(puts()[0].body).toEqual({ condition: { ...CONDITION, mode: "recurring", frequency: "weekly" } });
  });

  it("202면 저장하지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ status: "collecting", stockId: 1, jobId: 7 } as never);
    await useStockStore.getState().run();
    expect(puts()).toEqual([]);
  });

  it("저장이 실패해도 결과는 그대로이고 알린다", async () => {
    answer();
    historyStub.fail("PUT");
    await useStockStore.getState().run();
    expect(useStockStore.getState().summary).not.toBeNull();
    expect(useStockStore.getState().historySaveError).toBe(
      "이력을 저장하지 못했습니다. 결과는 그대로이고, 다시 실행하면 다시 저장합니다.");
  });

  it("삭제는 DELETE이고 실패하면 알린다", async () => {
    historyStub.seed("stock", [CONDITION]);
    await useStockStore.getState().restoreHistory();
    await useStockStore.getState().removeHistoryEntry(ID);
    expect(historyStub.calls().at(-1)).toMatchObject({ method: "DELETE", path: `/api/history/stock?id=${encodeURIComponent(ID)}` });
    expect(useStockStore.getState().history).toEqual([]);
    historyStub.seed("stock", [CONDITION]);
    await useStockStore.getState().restoreHistory();
    historyStub.fail("DELETE");
    await useStockStore.getState().removeHistoryEntry(ID);
    expect(useStockStore.getState().historySaveError).toBe("이력을 지우지 못했습니다.");
    expect(useStockStore.getState().history.map((e) => e.id)).toEqual([ID]);
  });

  it("다시 실행은 서버 id로 항목을 찾아 그 조건으로 실행한다", async () => {
    historyStub.seed("stock", [{ ...CONDITION, principal: "3000000", id: "KRX|005930.KS|2024-01-15|3000000|KRW|R" }]);
    await useStockStore.getState().restoreHistory();
    const get = answer();
    await useStockStore.getState().rerunHistory("KRX|005930.KS|2024-01-15|3000000|KRW|R");
    expect(useStockStore.getState().input.principal).toBe("3000000");
    expect(String(get.mock.calls[0][0])).toContain("principal=3000000");
  });
});

describe("예금", () => {
  it("결과가 나오면 예금 이력에 저장한다 — 주식 이력과 따로다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      (path.includes("/series") ? SERIES : path.startsWith("/api/deposit/simulation?") ? DEPOSIT_RESULT
        : { institutions: [], source: "", basis: "" }) as never);
    await useDepositStore.getState().run();
    expect(puts()).toEqual([{ method: "PUT", path: "/api/history/deposit",
      body: { condition: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" } } }]);
    expect(historyStub.entries("stock")).toEqual([]);
  });
});
