/**
 * 막힌 조합의 이력 (T078) — 006 FR-050c.
 *
 * **지우지 않는다.** 조용히 지우면 사용자는 이력이 사라진 이유를 알 수 없다. **비교에서 조용히 빼지
 * 않는다** — 빼고 비교하면 그 종목이 비교에서 진 것으로 읽힌다(005 FR-038 계열).
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SimulationHistory } from "@/components/stock/SimulationHistory";
import { apiClient } from "@/lib/apiClient";
// 012 승인 2026-10-07 — 012부터 옛 브라우저 키는 화면을 열 때 로컬 DB로 옮겨진다. 막힌 조합 항목도 옮겨져 남아야 한다(FR-013).
import { LEGACY_KEYS } from "@/lib/legacyHistory";
import type { SimulationHistoryEntry } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: () => () => undefined,
}));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const SAMSUNG_KRW: SimulationHistoryEntry = {
  id: "ok", savedAt: "2026-09-01T00:00:00.000Z",
  stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  start: "2021-08-01", principal: "1000000", principalCurrency: "KRW", reinvest: true,
};
// 005 시절에 남은 교차 통화 항목 — 원금 EUR·미국 종목.
const APPLE_EUR: SimulationHistoryEntry = {
  id: "eur", savedAt: "2026-09-02T00:00:00.000Z",
  stock: { market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD" },
  start: "2021-08-01", principal: "1000", principalCurrency: "EUR", reinvest: true,
};

const SERIES = {
  from: "2021-08-01", to: "2021-08-31", principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false,
  algorithm: "none", sourcePointCount: 0, points: [], gaps: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  localStorage.setItem(LEGACY_KEYS.stock, JSON.stringify([APPLE_EUR, SAMSUNG_KRW])); // 012 승인 2026-10-07
  useStockStore.setState({ history: [], selectedHistory: [], comparison: [],
    comparisonError: null });
});

describe("막힌 조합 이력", () => {
  // 012 승인 2026-10-07 — 불러오기는 옮기기·목록 요청이라 기다린다. 남는 곳은 로컬 DB(이력 대역)다.
  it("지우지 않고 남긴다", async () => {
    await useStockStore.getState().restoreHistory();
    expect(useStockStore.getState().history.map((e) => e.id)).toEqual(["eur", "ok"]);
    expect(historyStub.entries("stock")).toHaveLength(2);
  });

  it("목록에서 사유와 함께 보인다", () => {
    render(<SimulationHistory entries={[APPLE_EUR, SAMSUNG_KRW]} selected={[]}
      comparing={false} saveError={null} onToggle={vi.fn()} onRemove={vi.fn()}
      onCompare={vi.fn()} onRerun={vi.fn()} />);
    const rows = screen.getAllByTestId("history-row");
    expect(within(rows[0]).getByText(/KRW 또는 USD 원금만/)).toBeInTheDocument();
    expect(within(rows[1]).queryByText(/원금만/)).toBeNull();
  });

  it("비교에 고르면 조용히 빼지 않고 사유를 보인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(SERIES);
    await useStockStore.getState().restoreHistory(); // 012 승인 2026-10-07
    useStockStore.setState({ selectedHistory: ["eur", "ok"] });
    await useStockStore.getState().compareSelected();

    const state = useStockStore.getState();
    expect(state.comparison.map((c) => c.id)).toEqual(["ok"]);
    expect(state.comparisonError).toMatch(/Apple Inc\./);
    expect(state.comparisonError).toMatch(/KRW 또는 USD/);
    // 막힌 조합은 서버에 묻지 않는다 — 서버도 같은 규칙으로 거절한다(FR-050a).
    expect(get.mock.calls.every(([path]) => !String(path).includes("EUR"))).toBe(true);
  });
});
