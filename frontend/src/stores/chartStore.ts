/** 차트 상태 Zustand 스토어 (T085). */

import { create } from "zustand";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type { CoverageRow, SeriesCollecting, SeriesResponse } from "@/lib/types";

export type Preset = "1m" | "1y" | "5y" | "all";

interface ChartState {
  currency: CurrencyCode;
  preset: Preset;
  from: string;
  to: string;
  data: SeriesResponse | null;
  collecting: SeriesCollecting | null;
  loading: boolean;
  error: string | null;
  setCurrency: (c: CurrencyCode) => void;
  setPreset: (p: Preset) => void;
  setRange: (from: string, to: string) => void;
  fetchSeries: () => Promise<void>;
}

function yesterday(): Date {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d;
}

/**
 * 프리셋 → 날짜 구간.
 *
 * "전체"의 시작일은 비워 둔다. 축적 시작일이 통화마다 다르므로(FR-002 — USD 1964,
 * EUR 1994) 클라이언트가 상수로 알 수 없다. `fetchSeries`가 커버리지에서 받아 채운다.
 */
export function presetRange(preset: Preset): { from: string; to: string } {
  const end = yesterday();
  const start = new Date(end);
  if (preset === "1m") start.setMonth(start.getMonth() - 1);
  else if (preset === "1y") start.setFullYear(start.getFullYear() - 1);
  else if (preset === "5y") start.setFullYear(start.getFullYear() - 5);
  else return { from: "", to: end.toISOString().slice(0, 10) };
  return { from: start.toISOString().slice(0, 10), to: end.toISOString().slice(0, 10) };
}

const initial = presetRange("1y");

export const useChartStore = create<ChartState>((set, get) => ({
  currency: "USD",
  preset: "1y",
  from: initial.from,
  to: initial.to,
  data: null,
  collecting: null,
  loading: false,
  error: null,

  // 통화를 바꾸면 "전체" 구간도 달라지므로 시작일을 비워 다시 해석하게 한다 (FR-002).
  setCurrency: (currency) =>
    set((s) => (s.preset === "all" ? { currency, ...presetRange("all") } : { currency })),
  setPreset: (preset) => set({ preset, ...presetRange(preset) }),
  setRange: (from, to) => set({ from, to }),

  fetchSeries: async () => {
    const { currency, to } = get();
    let { from } = get();
    set({ loading: true, error: null, collecting: null });
    try {
      if (from === "") {
        const { coverage } = await apiClient.get<{ coverage: CoverageRow[] }>(
          "/api/fx/coverage",
        );
        const row = coverage.find((c) => c.currency === currency);
        if (!row) {
          set({ error: "아직 수집된 데이터가 없습니다.", loading: false });
          return;
        }
        // 발견된 최초 제공일이 우선이고, 아직 없으면 수집 완료 구간 시작을 쓴다 (FR-002a).
        from = row.firstAvailableDate ?? row.coveredFrom;
        set({ from });
      }
      const body = await apiClient.get<SeriesResponse | SeriesCollecting>(
        `/api/fx/series?currency=${currency}&from=${from}&to=${to}`,
      );
      if ("status" in body && body.status === "collecting") {
        set({ collecting: body, data: null, loading: false });
      } else {
        set({ data: body as SeriesResponse, loading: false });
      }
    } catch (err) {
      set({
        error: err instanceof ApiError ? err.message : "시계열을 불러오지 못했습니다.",
        loading: false,
      });
    }
  },
}));
