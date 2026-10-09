/**
 * 대시보드 뉴스 스토어 (014 T078) — FR-024, data-model 7.
 *
 * - `loadAll`은 세 칸을 **동시에** 부르고 온 것부터 그 칸을 바꾼다 — 가장 느린 출처가 다른 칸·카드를 막지 않는다
 * - `retry(source)`는 그 칸만 다시 부른다. 실패 기억이 남은 동안이면 서버가 출처를 부르지 않고 같은 실패를 준다
 * - 칸마다 늦게 온 옛 응답은 버린다(`seq`)
 */
import { create } from "zustand";
import { fetchNews } from "@/lib/dashboardApi";
import type { NewsFailure, NewsListResponse, NewsSourceKey } from "@/lib/types";

export const NEWS_SOURCES: readonly NewsSourceKey[] = ["kr", "us", "jp"];

export interface NewsColumnState {
  /** `failed`는 출처 실패(서버가 200으로 실음), `error`는 서버 요청 자체의 실패다. */
  status: "idle" | "loading" | "ready" | "failed" | "error";
  list: NewsListResponse | null;
  failure: NewsFailure | null;
  seq: number;
}

interface NewsState {
  columns: Record<NewsSourceKey, NewsColumnState>;
  loadAll: () => Promise<void>;
  retry: (source: NewsSourceKey) => Promise<void>;
}

export function initialColumns(): Record<NewsSourceKey, NewsColumnState> {
  const blank = (): NewsColumnState => ({ status: "idle", list: null, failure: null, seq: 0 });
  return { kr: blank(), us: blank(), jp: blank() };
}

export const useNewsStore = create<NewsState>((set, get) => {
  const patch = (source: NewsSourceKey, next: Partial<NewsColumnState>) =>
    set((s) => ({ columns: { ...s.columns, [source]: { ...s.columns[source], ...next } } }));

  const load = async (source: NewsSourceKey) => {
    const seq = get().columns[source].seq + 1;
    patch(source, { status: "loading", seq });
    try {
      const list = await fetchNews(source);
      if (get().columns[source].seq !== seq) return;
      if (list.status === "ok") patch(source, { status: "ready", list, failure: null });
      else patch(source, { status: "failed", list, failure: list.failure });
    } catch {
      if (get().columns[source].seq !== seq) return;
      patch(source, { status: "error", failure: null });
    }
  };

  return {
    columns: initialColumns(),
    loadAll: async () => {
      await Promise.all(NEWS_SOURCES.map((source) => load(source)));
    },
    retry: (source) => load(source),
  };
});
