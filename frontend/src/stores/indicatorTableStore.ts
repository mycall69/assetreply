/**
 * 지표 모달의 일자별 표 스토어 (014 반복 2026-10-10b T120) — FR-016, FR-029, data-model 7, contracts A7.
 *
 * - 처음은 일 단위다. 단위를 바꾸면 처음부터 다시 받는다 — 옛 단위의 행을 남기면 두 단위가 섞인 표가 된다
 * - 더 받기는 `before = oldestReturned`이고 뒤에 붙인다(주식 일자별 표와 같은 쪽 넘기기)
 * - 늦게 온 옛 응답은 버린다(`seq`)
 * - 202는 그래프와 같은 받는 중·실패다 — 받은 만큼만 보인 표를 완성된 이력처럼 보이지 않는다(FR-016). 다시 받는 시점은 모달이
 *   정한다(그래프가 다 받아지면 표도 다시 연다)
 */
import { create } from "zustand";
import { ApiError } from "@/lib/apiClient";
import { fetchTable } from "@/lib/dashboardApi";
import type { IndicatorCollecting, IndicatorTablePeriod, IndicatorTableResponse, IndicatorTableRow } from "@/lib/types";

interface IndicatorTableState {
  id: string | null;
  period: IndicatorTablePeriod;
  status: "idle" | "loading" | "ready" | "collecting" | "failed" | "not_found" | "error";
  rows: IndicatorTableRow[];
  table: IndicatorTableResponse | null;
  collecting: IndicatorCollecting | null;
  hasMore: boolean;
  oldestReturned: string | null;
  loadingMore: boolean;
  loadError: string | null;
  seq: number;
  open: (id: string) => Promise<void>;
  setPeriod: (period: IndicatorTablePeriod) => Promise<void>;
  loadMore: () => Promise<void>;
  close: () => void;
}

function isCollecting(body: IndicatorTableResponse | IndicatorCollecting): body is IndicatorCollecting {
  return "status" in body;
}

const BLANK = {
  status: "idle" as const,
  rows: [] as IndicatorTableRow[],
  table: null,
  collecting: null,
  hasMore: false,
  oldestReturned: null,
  loadingMore: false,
  loadError: null,
};

export const useIndicatorTableStore = create<IndicatorTableState>((set, get) => {
  const first = async (id: string, period: IndicatorTablePeriod) => {
    const seq = get().seq + 1;
    set({ ...BLANK, id, period, seq, status: "loading" });
    try {
      const body = await fetchTable(id, period);
      if (get().seq !== seq) return;
      if (isCollecting(body)) {
        set({ collecting: body, status: body.status === "failed" ? "failed" : "collecting" });
        return;
      }
      set({
        table: body, rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned,
        collecting: null, status: "ready",
      });
    } catch (err) {
      if (get().seq !== seq) return;
      if (err instanceof ApiError && err.httpStatus === 404) {
        set({ status: "not_found" });
        return;
      }
      set({ status: "error" });
    }
  };

  return {
    id: null,
    period: "daily",
    ...BLANK,
    seq: 0,

    open: (id) => first(id, "daily"),

    setPeriod: async (period) => {
      const id = get().id;
      if (id) await first(id, period);
    },

    loadMore: async () => {
      const { id, period, oldestReturned, hasMore, loadingMore, status } = get();
      if (!id || !hasMore || loadingMore || status !== "ready" || oldestReturned === null) return;
      const seq = get().seq;
      set({ loadingMore: true, loadError: null });
      try {
        const body = await fetchTable(id, period, oldestReturned);
        if (get().seq !== seq) return;
        if (isCollecting(body)) {
          set({ loadingMore: false, loadError: "이력을 받는 중입니다." });
          return;
        }
        set((s) => ({
          rows: [...s.rows, ...body.rows], hasMore: body.hasMore, oldestReturned: body.oldestReturned,
          loadingMore: false,
        }));
      } catch {
        if (get().seq !== seq) return;
        set({ loadingMore: false, loadError: "더 받지 못했습니다." });
      }
    },

    close: () => set((s) => ({ ...BLANK, id: null, period: "daily", seq: s.seq + 1 })),
  };
});
