/**
 * 지표 화면 그래프 스토어 (014 T059) — FR-010, FR-011, FR-016, data-model 7.
 *
 * - 202(받는 중)면 진행을 구독하고 `completed`에 그래프를 다시 받는다 — 다 받아졌는데 그래프로 바뀌지 않으면 사용자가 새로고침해야
 *   한다(FR-016 실패 양상). 환율도 같은 진행 경로다(반복 2026-10-10 — 서버가 외환 커버리지로 같은 사건을 낸다). 스트림이 끊겨도 늦지 않게
 *   받는 동안 15초마다 다시 묻는 것을 함께 둔다
 * - 기간을 바꾸면 주소 바꾸기 콜백을 부르고 다시 받는다 — 늦게 온 옛 기간 응답은 버린다(`seq`)
 * - (반복 2026-10-10b) 단위 대신 보는 기간 `range`다. 일·주(장중)는 수집과 무관한 200이다(`intraday`) — 출처가 실패해도 그래프 자리의
 *   본문이고(`status: "failed"`), 받는 중(202)으로 읽지 않는다
 * - (반복 2026-10-10c) 일봉 본문은 기간과 무관하게 저장된 일봉 전부다 — 월~모두 사이의 전환은 다시 받지 않고 `range`(처음 보이는 범위)와
 *   주소만 바꾼다. 장중 ↔ 일봉·장중끼리는 받는다(본문이 다르다)
 * - 없는 지표(404)는 `not_found`다
 */
import { create } from "zustand";
import { ApiError } from "@/lib/apiClient";
import { fetchSeries, requestCollect } from "@/lib/dashboardApi";
import { subscribeIndicatorProgress } from "@/lib/dashboardProgressStream";
import type { IndicatorChartSeries, IndicatorCollecting, IndicatorRange } from "@/lib/types";
import { DEFAULT_INDICATOR_RANGE, isIntradayRange } from "@/lib/types";

const RECHECK_MS = 15_000;

interface IndicatorSeriesState {
  id: string | null;
  range: IndicatorRange;
  status: "idle" | "loading" | "ready" | "collecting" | "failed" | "not_found" | "error";
  series: IndicatorChartSeries | null;
  collecting: IndicatorCollecting | null;
  error: string | null;
  seq: number;
  open: (id: string, range: IndicatorRange) => Promise<void>;
  setRange: (range: IndicatorRange, replaceUrl: (range: IndicatorRange) => void) => Promise<void>;
  /** 지금 기간을 다시 받는다 — 장중 실패의 다시 시도. */
  reload: () => Promise<void>;
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

function isCollecting(body: IndicatorChartSeries | IndicatorCollecting): body is IndicatorCollecting {
  // 장중 본문에도 `status`가 있다(출처 실패 — 그래프 자리의 본문) — `intraday`가 없을 때만 202다
  return "status" in body && !("intraday" in body);
}

export const useIndicatorSeriesStore = create<IndicatorSeriesState>((set, get) => {
  const watch = (body: IndicatorCollecting, seq: number) => {
    stopWatching();
    const again = () => {
      if (get().seq !== seq) return;
      const { id, range } = get();
      if (id) void get().open(id, range);
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
    range: DEFAULT_INDICATOR_RANGE,
    status: "idle",
    series: null,
    collecting: null,
    error: null,
    seq: 0,

    open: async (id, range) => {
      const seq = get().seq + 1;
      set({ id, range, seq, status: get().series && get().id === id ? get().status : "loading", error: null });
      try {
        const body = await fetchSeries(id, range);
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

    setRange: async (range, replaceUrl) => {
      replaceUrl(range);
      const { id, series, status, range: current } = get();
      // 같은 일봉 본문으로 보이는 범위만 바꾼다 — "모두"(약 2만 5천 점)를 기간마다 다시 받지 않는다
      const daily = series !== null && !("intraday" in series);
      if (daily && status === "ready" && !isIntradayRange(current) && !isIntradayRange(range)) {
        set({ range });
        return;
      }
      if (id) await get().open(id, range);
    },

    reload: async () => {
      const { id, range } = get();
      if (id) await get().open(id, range);
    },

    retryCollect: async () => {
      const { id, range } = get();
      if (!id) return;
      try {
        await requestCollect(id);
      } catch {
        // 다시 시도가 실패해도 화면은 지금 상태를 다시 받는다 — 까닭은 그 응답이 보인다
      }
      await get().open(id, range);
    },

    close: () => {
      stopWatching();
      set((s) => ({ id: null, status: "idle", series: null, collecting: null, error: null, seq: s.seq + 1 }));
    },
  };
});
