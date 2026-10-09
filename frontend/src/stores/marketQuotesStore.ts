/**
 * 대시보드 시세 스토어 (014 T038) — FR-008, FR-009, FR-010, research R14-15, data-model 7.
 *
 * 대시보드와 지표 화면이 **같은 스토어·같은 경로**를 쓴다 — 지표 화면 머리 값이 카드와 같다(FR-010).
 *
 * - 응답의 `refreshAfterSeconds`(서버 설정 — 기본 60초)마다 다시 부른다
 * - **화면이 보이지 않는 동안은 부르지 않는다** — 보이지 않는 탭이 계속 부르면 출처 한도를 낭비해 정작 볼 때 막힌다(FR-008
 *   실패 양상). 다시 보이면 곧바로 부른다
 * - 타이머는 하나다 — `startPolling`을 여러 번 불러도 갱신이 두 번 걸리지 않는다
 * - 늦게 온 옛 응답은 버린다(`seq`)
 */
import { create } from "zustand";
import { fetchQuotes } from "@/lib/dashboardApi";
import type { DashboardQuotesResponse } from "@/lib/types";

const DEFAULT_REFRESH_SECONDS = 60;

interface MarketQuotesState {
  status: "idle" | "loading" | "ready" | "error";
  data: DashboardQuotesResponse | null;
  error: string | null;
  seq: number;
  load: () => Promise<void>;
  retry: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

// 타이머·구독은 상태가 아니다 — 화면을 다시 그리지 않는다.
let timer: ReturnType<typeof setTimeout> | null = null;
let polling = false;
let listening = false;

function hidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

export const useMarketQuotesStore = create<MarketQuotesState>((set, get) => {
  const clear = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };

  const schedule = () => {
    clear();
    if (!polling) return;
    const seconds = get().data?.refreshAfterSeconds ?? DEFAULT_REFRESH_SECONDS;
    timer = setTimeout(() => {
      timer = null;
      if (!polling || hidden()) return; // 보이지 않는 동안은 부르지 않는다 — 다시 보일 때 부른다
      void get().load().then(schedule);
    }, seconds * 1000);
  };

  const onVisibility = () => {
    if (!polling || hidden()) return;
    void get().load().then(schedule);
  };

  return {
    status: "idle",
    data: null,
    error: null,
    seq: 0,

    load: async () => {
      const seq = get().seq + 1;
      set({ seq, status: get().data ? get().status : "loading" });
      try {
        const data = await fetchQuotes();
        if (get().seq !== seq) return;
        set({ data, status: "ready", error: null });
      } catch {
        if (get().seq !== seq) return;
        set({ status: "error", error: "지표 시세를 불러오지 못했습니다." });
      }
    },

    retry: () => get().load(),

    startPolling: () => {
      if (polling) return;
      polling = true;
      if (!listening && typeof document !== "undefined") {
        document.addEventListener("visibilitychange", onVisibility);
        listening = true;
      }
      schedule();
    },

    stopPolling: () => {
      polling = false;
      clear();
      if (listening && typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
        listening = false;
      }
    },
  };
});
