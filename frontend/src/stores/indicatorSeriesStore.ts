/**
 * 지표 화면 그래프 스토어 (014 T059) — FR-010, FR-011, FR-016, data-model 7.
 *
 * - 202(받는 중)면 진행을 구독하고 `completed`에 그래프를 다시 받는다 — 다 받아졌는데 그래프로 바뀌지 않으면 사용자가 새로고침해야
 *   한다(FR-016 실패 양상). 환율도 같은 진행 경로다(반복 2026-10-10 — 서버가 외환 커버리지로 같은 사건을 낸다). 스트림이 끊겨도 늦지 않게
 *   받는 동안 15초마다 다시 묻는 것을 함께 둔다
 * - 단위를 바꾸면 주소 바꾸기 콜백을 부르고 다시 받는다 — 늦게 온 옛 단위 응답은 버린다(`seq`)
 * - 없는 지표(404)는 `not_found`다
 */
import { create } from "zustand";
import { ApiError } from "@/lib/apiClient";
import { fetchSeries, requestCollect } from "@/lib/dashboardApi";
import { subscribeIndicatorProgress } from "@/lib/dashboardProgressStream";
import type { IndicatorCollecting, IndicatorSeriesResponse, IndicatorUnit } from "@/lib/types";

const RECHECK_MS = 15_000;

interface IndicatorSeriesState {
  id: string | null;
  unit: IndicatorUnit;
  status: "idle" | "loading" | "ready" | "collecting" | "failed" | "not_found" | "error";
  series: IndicatorSeriesResponse | null;
  collecting: IndicatorCollecting | null;
  error: string | null;
  seq: number;
  open: (id: string, unit: IndicatorUnit) => Promise<void>;
  setUnit: (unit: IndicatorUnit, replaceUrl: (unit: IndicatorUnit) => void) => Promise<void>;
  retryCollect: () => Promise<void>;
  close: () => void;
}

let unsubscribe: (() => void) | null = null;
let recheck: ReturnType<typeof setTimeout> | null = null;

function stopWatching() {
  if (unsubscribe) unsubscribe();
  unsubscribe = null;
  if (recheck !== null) clearTimeout(recheck);
  recheck = null;
}

function isCollecting(body: IndicatorSeriesResponse | IndicatorCollecting): body is IndicatorCollecting {
  return "status" in body;
}

export const useIndicatorSeriesStore = create<IndicatorSeriesState>((set, get) => {
  const watch = (body: IndicatorCollecting, seq: number) => {
    stopWatching();
    const again = () => {
      if (get().seq !== seq) return;
      const { id, unit } = get();
      if (id) void get().open(id, unit);
    };
    unsubscribe = subscribeIndicatorProgress(body.progressUrl, {
      onSnapshot: (progress) => {
        const current = get().collecting;
        if (get().seq === seq && current) set({ collecting: { ...current, progress } });
      },
      onCompleted: again,
      onFailed: again,
    });
    recheck = setTimeout(again, RECHECK_MS);
  };

  return {
    id: null,
    unit: "daily",
    status: "idle",
    series: null,
    collecting: null,
    error: null,
    seq: 0,

    open: async (id, unit) => {
      const seq = get().seq + 1;
      set({ id, unit, seq, status: get().series && get().id === id ? get().status : "loading", error: null });
      try {
        const body = await fetchSeries(id, unit);
        if (get().seq !== seq) return;
        if (isCollecting(body)) {
          set({ collecting: body, status: body.status === "failed" ? "failed" : "collecting" });
          if (body.status === "collecting") watch(body, seq);
          else stopWatching();
          return;
        }
        stopWatching();
        set({ series: body, collecting: null, status: "ready" });
      } catch (err) {
        if (get().seq !== seq) return;
        stopWatching();
        if (err instanceof ApiError && err.httpStatus === 404) {
          set({ status: "not_found", series: null, collecting: null });
          return;
        }
        set({ status: "error", error: "이력을 불러오지 못했습니다." });
      }
    },

    setUnit: async (unit, replaceUrl) => {
      replaceUrl(unit);
      const id = get().id;
      if (id) await get().open(id, unit);
    },

    retryCollect: async () => {
      const { id, unit } = get();
      if (!id) return;
      try {
        await requestCollect(id);
      } catch {
        // 다시 시도가 실패해도 화면은 지금 상태를 다시 받는다 — 까닭은 그 응답이 보인다
      }
      await get().open(id, unit);
    },

    close: () => {
      stopWatching();
      set((s) => ({ id: null, status: "idle", series: null, collecting: null, error: null, seq: s.seq + 1 }));
    },
  };
});
