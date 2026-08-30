/** 수집 상태 Zustand 스토어 (T104). */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeProgress } from "@/lib/progressStream";
import type { CoverageRow, JobRow, ProgressState } from "@/lib/types";

interface StartResponse {
  jobs: { currency: string; jobId: number; joinedExisting: boolean }[];
}

interface CollectionState {
  coverage: CoverageRow[];
  jobs: JobRow[];
  progress: ProgressState | null;
  loading: boolean;
  error: string | null;
  unsubscribe: (() => void) | null;
  refresh: () => Promise<void>;
  startCollection: (currency?: string) => Promise<void>;
  watch: (jobId: number) => void;
  stopWatching: () => void;
}

export const useCollectionStore = create<CollectionState>((set, get) => ({
  coverage: [],
  jobs: [],
  progress: null,
  loading: false,
  error: null,
  unsubscribe: null,

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const [cov, jobs] = await Promise.all([
        apiClient.get<{ coverage: CoverageRow[] }>("/api/fx/coverage"),
        apiClient.get<{ jobs: JobRow[] }>("/api/fx/jobs?limit=20"),
      ]);
      set({ coverage: cov.coverage, jobs: jobs.jobs, loading: false });
    } catch (err) {
      set({
        error: err instanceof ApiError ? err.message : "현황을 불러오지 못했습니다.",
        loading: false,
      });
    }
  },

  startCollection: async (currency) => {
    try {
      const body = await apiClient.post<StartResponse>(
        "/api/fx/collect",
        currency ? { currency } : undefined,
      );
      const first = body.jobs[0];
      if (first) get().watch(first.jobId);
      await get().refresh();
    } catch (err) {
      set({ error: err instanceof ApiError ? err.message : "수집을 시작하지 못했습니다." });
    }
  },

  watch: (jobId) => {
    get().stopWatching();
    const unsubscribe = subscribeProgress(jobId, {
      onProgress: (progress) => set({ progress }),
      onCompleted: (progress) => {
        set({ progress });
        void get().refresh();
      },
      onError: (message) => set({ error: message }),
    });
    set({ unsubscribe });
  },

  stopWatching: () => {
    const { unsubscribe } = get();
    if (unsubscribe) unsubscribe();
    set({ unsubscribe: null });
  },
}));
