/**
 * 스프레드 설정 상태 (T054) — 헌법 원칙 VII(Zustand 상태 관리 MUST).
 *
 * 페이지에서 `useState` + `useEffect`로 서버 데이터를 다루면 React 19의
 * `set-state-in-effect` 규칙에 걸리고, 원칙 VII의 상태 관리 방식과도 어긋난다.
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { RestoreResponse, SpreadsResponse } from "@/lib/types";

type Values = Record<"cashBuy" | "cashSell" | "remitSend" | "remitReceive", string>;

interface SpreadState {
  data: SpreadsResponse | null;
  message: string | null;
  error: string | null;
  load: () => Promise<void>;
  save: (changes: Record<string, Values>) => Promise<void>;
  restore: (scope: string) => Promise<void>;
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

export const useSpreadStore = create<SpreadState>((set, get) => ({
  data: null,
  message: null,
  error: null,

  load: async () => {
    try {
      set({ data: await apiClient.get<SpreadsResponse>("/api/fx/spreads"), error: null });
    } catch (err) {
      set({ error: message(err, "스프레드를 불러오지 못했습니다.") });
    }
  },

  save: async (changes) => {
    set({ error: null, message: null });
    try {
      for (const [currency, values] of Object.entries(changes)) {
        await apiClient.put(`/api/fx/spreads/${currency}`, values);
      }
      await get().load();
      set({ message: "저장했습니다." });
    } catch (err) {
      set({ error: message(err, "저장하지 못했습니다.") });
    }
  },

  restore: async (scope) => {
    set({ error: null, message: null });
    try {
      const body = await apiClient.post<RestoreResponse>(
        "/api/fx/spreads/restore", scope === "all" ? {} : { currency: scope });
      set((s) => ({
        data: s.data ? { ...s.data, spreads: body.spreads } : s.data,
        // FR-031a: 부분 실패해도 성공분은 그대로다. 실패한 통화를 함께 알린다.
        message:
          body.failed.length === 0
            ? `${body.restored.join(", ")} 복원했습니다.`
            : `${body.restored.join(", ")} 복원. 실패: ${body.failed
                .map((f) => `${f.currency}(${f.reason})`)
                .join(", ")}`,
      }));
    } catch (err) {
      set({ error: message(err, "복원하지 못했습니다.") });
    }
  },
}));
