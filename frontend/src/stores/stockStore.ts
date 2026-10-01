/**
 * 주식 시뮬레이션 화면의 단일 상태 원천 (T044) — 헌법 원칙 VII.
 *
 * **결과를 저장하지 않는다.** 설정과 환율이 바뀌면 결과가 달라지므로, 들고 있으면
 * 갱신 시점을 관리해야 하고 그 관리가 틀리면 조용히 낡은 값을 보여준다
 * (research R5-9). 상태는 "지금 화면에 그릴 것"만 담는다.
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import type {
  ExchangeInfo,
  PrincipalCurrency,
  SimulationCollecting,
  SimulationCondition,
  SimulationResponse,
  SimulationRow,
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
  collecting: SimulationCollecting | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;

  setInput: (next: Partial<SimulationInput>) => void;
  run: () => Promise<void>;
  loadMore: () => Promise<void>;
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

/** 조건을 질의 문자열로. 원금은 **문자열 그대로** 보낸다 (헌법 원칙 VI). */
export function toQuery(input: SimulationInput): string {
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
  collecting: null,
  loading: false,
  loadingMore: false,
  error: null,
  loadMoreError: null,

  setInput: (next) => set({ input: { ...get().input, ...next } }),

  /**
   * 시뮬레이션을 실행한다.
   *
   * **실행 즉시 이전 결과를 비운다.** 새 조건의 응답이 도착할 때까지 이전 결과가
   * 남으면 사용자가 지금 보는 수치가 어느 조건의 것인지 알 수 없다
   * (002 FR-036c·003 FR-028·004 FR-010과 같은 계열).
   */
  run: async () => {
    const query = toQuery(get().input);
    if (query === "") {
      set({ error: "종목을 먼저 고르세요." });
      return;
    }
    set({
      rows: [], summary: null, condition: null, exchange: null,
      hasMore: false, oldestReturned: null, collecting: null,
      loading: true, error: null, loadMoreError: null,
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
        loading: false,
      });
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
}));
