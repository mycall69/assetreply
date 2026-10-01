/**
 * 주식 시뮬레이션 화면의 단일 상태 원천 (T044) — 헌법 원칙 VII.
 *
 * **결과를 저장하지 않는다.** 설정과 환율이 바뀌면 결과가 달라지므로, 들고 있으면
 * 갱신 시점을 관리해야 하고 그 관리가 틀리면 조용히 낡은 값을 보여준다
 * (research R5-9). 상태는 "지금 화면에 그릴 것"만 담는다.
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import {
  loadHistory,
  removeHistory,
  saveHistory,
} from "@/lib/simulationHistory";
import type {
  ExchangeInfo,
  PrincipalCurrency,
  SimulationCollecting,
  SimulationCondition,
  SimulationHistoryEntry,
  SimulationResponse,
  SimulationRow,
  SimulationSeriesResponse,
  SimulationSummary,
  StockSearchResult,
} from "@/lib/types";

export interface SimulationInput {
  stock: StockSearchResult | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
}

interface StockState {
  input: SimulationInput;
  rows: SimulationRow[];
  summary: SimulationSummary | null;
  condition: SimulationCondition | null;
  exchange: ExchangeInfo | null;
  hasMore: boolean;
  oldestReturned: string | null;
  /** 차트용 전 구간 시계열 (FR-033). 표와 **같은 조건**으로 따로 받는다. */
  series: SimulationSeriesResponse | null;
  /**
   * 차트만 실패했을 때의 사유.
   *
   * **표를 지우지 않는다.** 차트가 비는 것과 결과가 없는 것은 다른 사건인데,
   * 한 덩어리로 다루면 멀쩡한 표까지 사라져 사용자는 조건이 틀렸다고 읽는다.
   */
  seriesError: string | null;
  collecting: SimulationCollecting | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;

  /** 이력 (FR-035). **조건만 담긴다** — 결과는 설정·환율이 바뀌면 달라진다. */
  history: SimulationHistoryEntry[];
  historySaveError: string | null;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;

  setInput: (next: Partial<SimulationInput>) => void;
  run: () => Promise<void>;
  loadMore: () => Promise<void>;
  /**
   * 설정이 바뀐 뒤 결과를 다시 받는다 (FR-017).
   *
   * 아직 실행한 적이 없으면 아무것도 하지 않는다 — 설정 화면에 들렀다는 이유로
   * 시뮬레이션이 시작되면 사용자가 요청하지 않은 출처 호출이 나간다.
   */
  refreshIfRan: () => Promise<void>;
  restoreHistory: () => void;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => void;
  compareSelected: () => Promise<void>;
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

/** 조건을 질의 문자열로. 원금은 **문자열 그대로** 보낸다 (헌법 원칙 VI). */
export function toQuery(input: {
  stock: StockSearchResult | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
}): string {
  const stock = input.stock;
  if (stock === null) return "";
  const params = new URLSearchParams({
    market: stock.market,
    symbol: stock.symbol,
    start: input.start,
    principal: input.principal,
    principalCurrency: input.principalCurrency,
    reinvest: String(input.reinvest),
  });
  return params.toString();
}

export const useStockStore = create<StockState>((set, get) => ({
  input: {
    stock: null,
    start: "",
    principal: "",
    principalCurrency: "KRW",
    reinvest: true,
  },
  rows: [],
  summary: null,
  condition: null,
  exchange: null,
  hasMore: false,
  oldestReturned: null,
  series: null,
  seriesError: null,
  collecting: null,
  loading: false,
  loadingMore: false,
  error: null,
  loadMoreError: null,
  history: [],
  historySaveError: null,
  selectedHistory: [],
  comparison: [],
  comparing: false,
  comparisonError: null,

  setInput: (next) => set({ input: { ...get().input, ...next } }),

  refreshIfRan: async () => {
    if (get().summary === null) return;
    await get().run();
  },

  /**
   * 시뮬레이션을 실행한다.
   *
   * **실행 즉시 이전 결과를 비운다.** 새 조건의 응답이 도착할 때까지 이전 결과가
   * 남으면 사용자가 지금 보는 수치가 어느 조건의 것인지 알 수 없다
   * (002 FR-036c·003 FR-028·004 FR-010과 같은 계열).
   */
  run: async () => {
    const { input } = get();
    const query = toQuery(input);
    if (input.stock === null || query === "") {
      set({ error: "종목을 먼저 고르세요." });
      return;
    }
    set({
      rows: [], summary: null, condition: null, exchange: null,
      hasMore: false, oldestReturned: null, series: null, seriesError: null,
      collecting: null, loading: true, error: null, loadMoreError: null,
    });
    try {
      const body = await apiClient.get<SimulationResponse | SimulationCollecting>(
        `/api/stocks/simulation?${query}`,
      );
      if ("status" in body && body.status === "collecting") {
        // FR-049 — 부분 결과를 완성된 결과처럼 보여주지 않는다.
        set({ collecting: body, loading: false });
        return;
      }
      const result = body as SimulationResponse;
      set({
        rows: result.rows,
        summary: result.summary,
        condition: result.condition,
        exchange: result.exchange ?? null,
        hasMore: result.hasMore,
        oldestReturned: result.oldestReturned,
      });

      // FR-035 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다**(R5-9).
      const saved = saveHistory({
        stock: input.stock,
        start: input.start,
        principal: input.principal,
        principalCurrency: input.principalCurrency,
        reinvest: input.reinvest,
      });
      set({
        history: loadHistory(),
        historySaveError: saved.ok ? null : saved.reason,
      });

      // **표가 수집 중이 아님을 확인한 뒤에 받는다.** 나란히 보내면 같은 구간에
      // 수집 요청이 두 번 나가고, 둘 다 작업을 만들려 해 하나는 점유에 걸린다.
      try {
        const series = await apiClient.get<SimulationSeriesResponse>(
          `/api/stocks/simulation/series?${query}`,
        );
        set({ series, loading: false });
      } catch (err) {
        set({
          seriesError: message(err, "차트를 불러오지 못했습니다."),
          loading: false,
        });
      }
    } catch (err) {
      set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
    }
  },

  /**
   * 표를 이어 받는다 (FR-029). **기존 배열 끝에 덧붙인다** — 전체를 교체하면
   * 보던 위치가 처음으로 튄다 (004 research R4-6).
   */
  loadMore: async () => {
    const { hasMore, oldestReturned, loadingMore, input } = get();
    if (!hasMore || oldestReturned === null || loadingMore) return;
    set({ loadingMore: true, loadMoreError: null });
    try {
      const body = await apiClient.get<SimulationResponse>(
        `/api/stocks/simulation?${toQuery(input)}&before=${oldestReturned}`,
      );
      set({
        rows: [...get().rows, ...body.rows],
        hasMore: body.hasMore,
        oldestReturned: body.oldestReturned,
        loadingMore: false,
      });
    } catch (err) {
      // 이미 표시된 행은 그대로 둔다 (FR-004와 같은 계열). 조용히 멈추면 사용자는
      // 데이터가 거기서 끝난 것으로 오해한다.
      set({
        loadingMore: false,
        loadMoreError: message(err, "이어서 불러오지 못했습니다."),
      });
    }
  },

  /** 저장소에서 이력을 읽는다. 첫 화면 진입에 한 번 부른다 (FR-037). */
  restoreHistory: () => set({ history: loadHistory() }),

  toggleHistory: (id) => {
    const selected = get().selectedHistory;
    set({
      selectedHistory: selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    });
  },

  removeHistoryEntry: (id) => {
    const result = removeHistory(id);
    set({
      history: loadHistory(),
      selectedHistory: get().selectedHistory.filter((x) => x !== id),
      // 지운 항목이 비교에 올라가 있었으면 함께 내린다 — 남겨 두면 목록에 없는
      // 선이 차트에 남아 사용자가 어느 조건인지 확인할 길이 없다.
      comparison: get().comparison.filter((c) => c.id !== id),
      historySaveError: result.ok ? null : result.reason,
    });
  },

  /**
   * 고른 이력을 **지금 다시 계산해서** 겹친다 (FR-038).
   *
   * 저장된 결과를 쓰지 않는 이유는 R5-9와 같다 — 설정과 환율이 바뀌면 달라지는데,
   * 저장된 값을 겹치면 어느 시점의 조건에서 나온 선인지 알 수 없다.
   */
  compareSelected: async () => {
    const { history, selectedHistory } = get();
    const targets = history.filter((e) => selectedHistory.includes(e.id));
    if (targets.length < 2) return;

    set({ comparing: true, comparisonError: null, comparison: [] });

    const items: ComparisonItem[] = [];
    const failed: string[] = [];

    for (const entry of targets) {
      const query = toQuery({
        stock: entry.stock,
        start: entry.start,
        principal: entry.principal,
        principalCurrency: entry.principalCurrency,
        reinvest: entry.reinvest,
      });
      try {
        const body = await apiClient.get<SimulationSeriesResponse | SimulationCollecting>(
          `/api/stocks/simulation/series?${query}`,
        );
        if ("status" in body && body.status === "collecting") {
          // FR-049 — 부분 결과를 완성된 선처럼 겹치지 않는다.
          failed.push(entry.stock.name);
          continue;
        }
        items.push({
          id: entry.id,
          label: entry.stock.name,
          start: entry.start,
          series: body as SimulationSeriesResponse,
        });
      } catch {
        failed.push(entry.stock.name);
      }
    }

    set({
      comparison: items,
      comparing: false,
      // 조용히 빠지면 사용자는 그 종목이 비교에서 졌다고 읽는다.
      comparisonError: failed.length === 0
        ? null
        : `${failed.join(" · ")}의 시계열을 불러오지 못했습니다.`,
    });
  },
}));
