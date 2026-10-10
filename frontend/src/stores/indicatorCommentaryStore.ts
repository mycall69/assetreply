/**
 * 지표 모달의 변화 까닭 스토어 (014 반복 2026-10-10b T120) — FR-027, data-model 7, contracts A8.
 *
 * 지표마다 한 칸이다. 서버가 10분 동안 기억하므로(출처를 다시 부르지 않는다) 모달을 열 때마다 묻는다. 출처 실패는 서버가 200으로
 * 싣는다(`status: "failed"`) — `error`는 서버 요청 자체의 실패다. 늦게 온 옛 응답은 버린다(지표마다 `seq`).
 */
import { create } from "zustand";
import { fetchCommentary } from "@/lib/dashboardApi";
import type { IndicatorCommentaryResponse } from "@/lib/types";

export interface CommentaryEntry {
  status: "loading" | "ready" | "error";
  body: IndicatorCommentaryResponse | null;
}

interface IndicatorCommentaryState {
  entries: Record<string, CommentaryEntry>;
  load: (id: string) => Promise<void>;
}

// 차례 번호는 상태가 아니다 — 화면을 다시 그리지 않는다.
const seqs = new Map<string, number>();

export const useIndicatorCommentaryStore = create<IndicatorCommentaryState>((set, get) => ({
  entries: {},

  load: async (id) => {
    const seq = (seqs.get(id) ?? 0) + 1;
    seqs.set(id, seq);
    const previous = get().entries[id]?.body ?? null;
    set((s) => ({ entries: { ...s.entries, [id]: { status: "loading", body: previous } } }));
    try {
      const body = await fetchCommentary(id);
      if (seqs.get(id) !== seq) return;
      set((s) => ({ entries: { ...s.entries, [id]: { status: "ready", body } } }));
    } catch {
      if (seqs.get(id) !== seq) return;
      set((s) => ({ entries: { ...s.entries, [id]: { status: "error", body: null } } }));
    }
  },
}));
