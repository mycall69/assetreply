/**
 * 네 스토어의 이력 불러오기와 브라우저 이력 옮기기 (012 T046) — FR-013, FR-014a, SC-006, data-model 5.2, research R12-11.
 *
 * 차례: 그 자산군의 옛 키 → 옮기기(POST) → 2xx면 그 키 삭제 → 목록(GET).
 * - 다른 자산군의 키는 건드리지 않는다(FR-013 *다른 곳에서 일어남*)
 * - 옮기기·목록이 실패하면 키를 지우지 않고 `historyLoadError`다 — 빈 목록과 구별된다(FR-014a). 다시 시도가 같은 차례를 한다
 * - 읽을 수 없는 키는 옮기지도 지우지도 않는다. 옮기지 못한 항목 수는 알린다(`historyNotice`)
 * - `historyLoading`은 첫 목록이 오기 전까지 참이다 — 그동안 빈 상태 문구를 보이지 않는다
 * - 목록이 바뀌어 선택한 항목이 빠지면 선택에서 뺀다. 이미 받은 비교는 그대로다(spec Edge Cases — 비교에 쓰인 항목이 기간 지나 지워짐)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LEGACY_KEYS } from "@/lib/legacyHistory";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useDepositStore } from "@/stores/depositStore";
import { useRealEstateStore } from "@/stores/realEstateStore";
import { useStockStore } from "@/stores/stockStore";
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

type Asset = "stock" | "crypto" | "deposit" | "realestate";

interface HistoryStore {
  getState: () => {
    history: Array<{ id: string }>;
    historyLoading: boolean;
    historyLoadError: string | null;
    historyNotice: string | null;
    retentionDays?: number | null;
    selectedHistory: string[];
    comparison: unknown[];
    restoreHistory: () => Promise<void>;
  };
  setState: (partial: Record<string, unknown>) => void;
  getInitialState: () => { historyLoading: boolean };
}

const CASES: Array<{ asset: Asset; store: HistoryStore; entry: Record<string, unknown> }> = [
  { asset: "stock", store: useStockStore as unknown as HistoryStore, entry: {
    id: "KRX|005930.KS|2024-01-15|500000|KRW|R", stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
    start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true, savedAt: "2026-09-01T00:00:00.000Z" } },
  { asset: "crypto", store: useCryptoStore as unknown as HistoryStore, entry: {
    id: "17|2024-01-15|10000|KRW", coin: { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin",
      currency: "USD" }, start: "2024-01-15", principal: "10000", principalCurrency: "KRW", savedAt: "2026-09-01T00:00:00.000Z" } },
  { asset: "deposit", store: useDepositStore as unknown as HistoryStore, entry: {
    id: "commercial_bank|2015-01-15|1000000", institution: "commercial_bank", start: "2015-01-15", principal: "1000000",
    savedAt: "2026-09-01T00:00:00.000Z" } },
  { asset: "realestate", store: useRealEstateStore as unknown as HistoryStore, entry: {
    id: "4|30k|2021-03-15|market", complexId: 4, complexName: "헬리오시티", umd: "1171010700", area: "30k", areaLabel: "30평대",
    buyDate: "2021-03-15", buyPrice: null, savedAt: "2026-09-01T00:00:00.000Z" } },
];

beforeEach(() => {
  localStorage.clear();
  for (const { store } of CASES) {
    store.setState({ history: [], historyLoading: true, historyLoadError: null, historyNotice: null, selectedHistory: [],
      comparison: [], historySaveError: null });
  }
});

describe.each(CASES)("$asset", ({ asset, store, entry }) => {
  const key = LEGACY_KEYS[asset];

  it("처음에는 불러오는 중이다", () => {
    expect(store.getInitialState().historyLoading).toBe(true);
  });

  it("옛 키를 옮기고 지운 뒤 목록을 받는다 — 다른 자산군의 키는 그대로다", async () => {
    localStorage.setItem(key, JSON.stringify([entry]));
    const others = CASES.filter((c) => c.asset !== asset);
    for (const other of others) localStorage.setItem(LEGACY_KEYS[other.asset], JSON.stringify([other.entry]));
    await store.getState().restoreHistory();
    expect(localStorage.getItem(key)).toBeNull();
    expect(store.getState().history.map((e) => e.id)).toEqual([entry.id]);
    expect(store.getState().historyLoading).toBe(false);
    expect(store.getState().retentionDays).toBe(30);
    expect(historyStub.entries(asset).map((e) => e.id)).toEqual([entry.id]);
    for (const other of others) {
      expect(localStorage.getItem(LEGACY_KEYS[other.asset])).not.toBeNull();
      expect(historyStub.entries(other.asset)).toEqual([]);
    }
  });

  it("옛 키가 없으면 옮기지 않고 목록만 받는다", async () => {
    historyStub.seed(asset, [entry]);
    await store.getState().restoreHistory();
    expect(historyStub.calls().map((c) => c.method)).toEqual(["GET"]);
    expect(store.getState().history.map((e) => e.id)).toEqual([entry.id]);
  });

  it("옮기기가 실패하면 키가 남고 불러오기 실패다", async () => {
    localStorage.setItem(key, JSON.stringify([entry]));
    historyStub.fail("POST", /import$/);
    await store.getState().restoreHistory();
    expect(localStorage.getItem(key)).not.toBeNull();
    expect(store.getState().historyLoadError).toBe("이력을 불러오지 못했습니다.");
    expect(store.getState().historyLoading).toBe(false);
  });

  it("목록이 실패하면 불러오기 실패이고 다시 시도가 같은 차례를 한다", async () => {
    localStorage.setItem(key, JSON.stringify([entry]));
    historyStub.fail("GET");
    await store.getState().restoreHistory();
    expect(store.getState().historyLoadError).toBe("이력을 불러오지 못했습니다.");
    historyStub.heal();
    await store.getState().restoreHistory();
    expect(store.getState().historyLoadError).toBeNull();
    expect(store.getState().history.map((e) => e.id)).toEqual([entry.id]);
    expect(localStorage.getItem(key)).toBeNull();
  });

  it("읽을 수 없는 키는 옮기지도 지우지도 않는다", async () => {
    localStorage.setItem(key, "{깨짐");
    await store.getState().restoreHistory();
    expect(localStorage.getItem(key)).toBe("{깨짐");
    expect(historyStub.calls().some((c) => c.method === "POST")).toBe(false);
    expect(store.getState().historyLoadError).toBeNull();
  });

  it("옮기지 못한 항목 수를 알린다", async () => {
    const broken = { ...entry, start: undefined, buyDate: undefined };
    localStorage.setItem(key, JSON.stringify([entry, broken]));
    await store.getState().restoreHistory();
    expect(store.getState().historyNotice).toBe("읽을 수 없는 브라우저 이력 1개는 옮기지 못했습니다.");
  });

  it("목록에서 빠진 항목은 선택에서 빼고 이미 받은 비교는 그대로다", async () => {
    historyStub.seed(asset, [entry]);
    const comparison = [{ id: "gone" }];
    store.setState({ selectedHistory: ["gone", entry.id as string], comparison });
    await store.getState().restoreHistory();
    expect(store.getState().selectedHistory).toEqual([entry.id]);
    expect(store.getState().comparison).toBe(comparison);
  });
});
