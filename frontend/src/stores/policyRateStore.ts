/**
 * 기준금리 스토어 (014 반복 2026-10-11d T209) — FR-040~FR-042, contracts A14~A17.
 *
 * - 칸(`data`)은 **DB만 읽는 경로**다 — 출처를 부르지 않으므로 지표 카드와 같은 주기(응답의 `refreshAfterSeconds`, 기본 60초)로 다시 읽는다.
 *   아직 받는 중인 은행이 있으면 5초 뒤 다시 읽는다(처음 기동의 결정 이력 받기는 은행마다 몇 초다)
 * - **화면이 보이지 않는 동안은 읽지 않는다** — 다시 보이면 곧바로 읽는다(지표 시세 스토어와 같다). 타이머는 하나다
 * - [다시 시도]는 수집 워커를 깨우고(`POST …/collect`) 5초 뒤 다시 읽는다
 * - 금리 모달의 결정 이력(`details`)·변화 까닭(`commentary`)은 은행마다 한 칸이다. 늦게 온 옛 응답은 버린다(`seq`·은행마다 차례 번호)
 * - 값은 서버 글자 그대로다 — 계산하지 않는다(원칙 VI)
 */
import { create } from "zustand";
import { fetchRateCommentary, fetchRateDetail, fetchRates, requestRateCollect } from "@/lib/dashboardApi";
import type { PolicyRateDetail, PolicyRatesResponse, RateCommentaryResponse } from "@/lib/types";

const DEFAULT_REFRESH_SECONDS = 60;
/** 받는 중인 은행이 있을 때·다시 시도 뒤 다시 읽기까지(초). */
export const COLLECTING_REFRESH_SECONDS = 5;

export interface RateDetailEntry {
  status: "loading" | "ready" | "error";
  body: PolicyRateDetail | null;
}

export interface RateCommentaryEntry {
  status: "loading" | "ready" | "error";
  body: RateCommentaryResponse | null;
}

interface PolicyRateState {
  status: "idle" | "loading" | "ready" | "error";
  data: PolicyRatesResponse | null;
  error: string | null;
  seq: number;
  details: Record<string, RateDetailEntry>;
  commentary: Record<string, RateCommentaryEntry>;
  load: () => Promise<void>;
  retry: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
  openDetail: (bank: string) => Promise<void>;
  closeDetail: () => void;
  loadCommentary: (bank: string) => Promise<void>;
}

// 타이머·구독·차례 번호는 상태가 아니다 — 화면을 다시 그리지 않는다.
let timer: ReturnType<typeof setTimeout> | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let detailTimer: ReturnType<typeof setTimeout> | null = null;
let polling = false;
let listening = false;
let watched: string | null = null;
const detailSeqs = new Map<string, number>();
const commentarySeqs = new Map<string, number>();

function hidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

function collecting(data: { banks: { state: string }[] } | null | undefined): boolean {
  return data?.banks.some((b) => b.state === "collecting") ?? false;
}

export const usePolicyRateStore = create<PolicyRateState>((set, get) => {
  const clear = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };

  const schedule = () => {
    clear();
    if (!polling) return;
    const data = get().data;
    const seconds = collecting(data) ? COLLECTING_REFRESH_SECONDS : data?.refreshAfterSeconds ?? DEFAULT_REFRESH_SECONDS;
    timer = setTimeout(() => {
      timer = null;
      if (!polling || hidden()) return; // 보이지 않는 동안은 읽지 않는다 — 다시 보일 때 읽는다
      void get().load();
    }, seconds * 1000);
  };

  const onVisibility = () => {
    if (!polling || hidden()) return;
    void get().load();
  };

  return {
    status: "idle",
    data: null,
    error: null,
    seq: 0,
    details: {},
    commentary: {},

    load: async () => {
      const seq = get().seq + 1;
      set({ seq, status: get().data ? get().status : "loading" });
      try {
        const data = await fetchRates();
        if (get().seq !== seq) return;
        set({ data, status: "ready", error: null });
      } catch {
        if (get().seq !== seq) return;
        set({ status: "error", error: "기준금리를 불러오지 못했습니다." });
      }
      // 다음 읽기는 방금 받은 칸으로 정한다 — 받는 중이 있으면 5초, 아니면 서버가 정한 주기
      if (polling) schedule();
    },

    retry: async () => {
      try {
        await requestRateCollect();
      } catch {
        // 깨우기가 실패해도 다시 읽는다 — 다음 주기의 수집이 남아 있다
      }
      if (retryTimer !== null) clearTimeout(retryTimer);
      retryTimer = setTimeout(() => {
        retryTimer = null;
        void get().load();
        const bank = watched;
        if (bank !== null) void get().openDetail(bank);
      }, COLLECTING_REFRESH_SECONDS * 1000);
    },

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
      if (retryTimer !== null) clearTimeout(retryTimer);
      retryTimer = null;
      if (listening && typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
        listening = false;
      }
    },

    openDetail: async (bank) => {
      watched = bank;
      if (detailTimer !== null) clearTimeout(detailTimer);
      detailTimer = null;
      const seq = (detailSeqs.get(bank) ?? 0) + 1;
      detailSeqs.set(bank, seq);
      const previous = get().details[bank]?.body ?? null;
      set((s) => ({ details: { ...s.details, [bank]: { status: "loading", body: previous } } }));
      try {
        const body = await fetchRateDetail(bank);
        if (detailSeqs.get(bank) !== seq) return;
        set((s) => ({ details: { ...s.details, [bank]: { status: "ready", body } } }));
        // 받는 중이면 모달이 열린 동안 5초 뒤 다시 읽는다 — 다 받으면 그래프·표가 된다
        if (body.state === "collecting" && watched === bank) {
          detailTimer = setTimeout(() => {
            detailTimer = null;
            if (watched === bank) void get().openDetail(bank);
          }, COLLECTING_REFRESH_SECONDS * 1000);
        }
      } catch {
        if (detailSeqs.get(bank) !== seq) return;
        set((s) => ({ details: { ...s.details, [bank]: { status: "error", body: null } } }));
      }
    },

    closeDetail: () => {
      watched = null;
      if (detailTimer !== null) clearTimeout(detailTimer);
      detailTimer = null;
    },

    loadCommentary: async (bank) => {
      const seq = (commentarySeqs.get(bank) ?? 0) + 1;
      commentarySeqs.set(bank, seq);
      const previous = get().commentary[bank]?.body ?? null;
      set((s) => ({ commentary: { ...s.commentary, [bank]: { status: "loading", body: previous } } }));
      try {
        const body = await fetchRateCommentary(bank);
        if (commentarySeqs.get(bank) !== seq) return;
        set((s) => ({ commentary: { ...s.commentary, [bank]: { status: "ready", body } } }));
      } catch {
        if (commentarySeqs.get(bank) !== seq) return;
        set((s) => ({ commentary: { ...s.commentary, [bank]: { status: "error", body: null } } }));
      }
    },
  };
});
