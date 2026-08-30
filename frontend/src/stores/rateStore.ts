/** 조회 상태 Zustand 스토어 (T059). */

import { create } from "zustand";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type { RateResponse } from "@/lib/types";

interface RateState {
  currency: CurrencyCode;
  date: string;
  result: RateResponse | null;
  loading: boolean;
  error: string | null;
  setCurrency: (c: CurrencyCode) => void;
  setDate: (d: string) => void;
  fetchRate: () => Promise<void>;
}

/** 어제 — 축적 범위의 끝이다 (FR-002, 당일 고시는 확정 전 변경될 수 있다). */
export function yesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

export const useRateStore = create<RateState>((set, get) => ({
  currency: "USD",
  date: yesterday(),
  result: null,
  loading: false,
  error: null,

  setCurrency: (currency) => set({ currency }),
  setDate: (date) => set({ date }),

  fetchRate: async () => {
    const { currency, date } = get();
    set({ loading: true, error: null });
    try {
      const result = await apiClient.get<RateResponse>(
        `/api/fx/rates/${currency}?date=${date}`,
      );
      set({ result, loading: false });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "조회에 실패했습니다.";
      set({ error: message, loading: false, result: null });
    }
  },
}));
