/**
 * 예금 시뮬레이션 화면의 단일 상태 원천 (T021) — 008 FR-002~FR-007, FR-011, FR-016, ui-wireframes D2·D8, 헌법 원칙 VII.
 *
 * 가상자산 화면(`cryptoStore`)을 본뜬다. **결과를 저장하지 않는다** — 설정과 금리가 바뀌면 결과가 달라진다(005 R5-9).
 *
 * - **부분 결과를 보여주지 않는다**(FR-011). 202면 결과를 비우고 진행(받은 달 / 받을 달)을 구독하고, 끝나면 다시 요청한다
 * - 수집이 실패하면 **종류마다 다른 말**로 할 일까지 보인다(FR-016)
 * - 투자처를 바꾸면 결과를 지운다(D2) — 이전 투자처의 결과가 새 이름 아래 남으면 그 수치를 새 투자처의 것으로 읽는다
 */

import { create } from "zustand";
import type { Startable } from "@/components/stock/StartDateInput";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeDepositProgress, type DepositProgressSnapshot } from "@/lib/depositProgressStream";
import { DEFAULT_START } from "@/lib/startDate";
import type {
  BeforeFirstMonthBody,
  DepositCollecting,
  DepositCondition,
  DepositFailureKind,
  DepositInstitution,
  DepositInstitutionKey,
  DepositInstitutionsResponse,
  DepositRow,
  DepositSimulationResponse,
  DepositSummary,
} from "@/lib/types";

export interface DepositInput {
  institution: DepositInstitutionKey;
  start: string;
  /** 원 단위 정수 문자열(쉼표 없음). 문자열로 들고 있다가 문자열로 보낸다(헌법 원칙 VI). */
  principal: string;
}

interface DepositState {
  input: DepositInput;
  /** 투자처 목록 — 설명과 받아 둔 범위. 받기 전에는 `null`이다(이름은 고정이라 화면이 먼저 그린다). */
  institutions: DepositInstitution[] | null;
  source: { name: string; basis: string } | null;
  /** 실행 뒤 서버가 알려 준 시작 가능 날짜(FR-006). 시작일은 바꾸지 않는다 — 옮기기는 눌러야 일어난다. */
  startable: Startable | null;
  rows: DepositRow[];
  summary: DepositSummary | null;
  condition: DepositCondition | null;
  /** 결과의 투자처 이름 — 입력이 바뀌어도 결과가 어느 투자처의 것인지 남긴다. */
  resultName: string | null;
  collecting: DepositCollecting | null;
  /** 수집 진행. 스냅샷이 오기 전에는 `null`이다 — 0/0은 멈춘 것처럼 보인다. */
  progress: DepositProgressSnapshot | null;
  loading: boolean;
  error: string | null;

  setInput: (next: Partial<DepositInput>) => void;
  /** 투자처를 고른다. 결과를 지운다(D2) — 실행은 버튼으로 한다. */
  selectInstitution: (key: DepositInstitutionKey) => void;
  loadInstitutions: () => Promise<void>;
  run: () => Promise<void>;
  /** 설정이 바뀐 뒤 결과를 다시 받는다(FR-031). 실행한 적이 없으면 아무것도 하지 않는다. */
  refreshIfRan: () => Promise<void>;
  /** 화면을 떠날 때 진행 구독을 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다. */
  dispose: () => void;
}

/** 수집 실패 종류 → 할 일까지 말하는 문구 (ui-wireframes D8). */
const FAILURE_TEXT: Record<DepositFailureKind, string> = {
  auth: "금리 출처 인증에 실패했습니다. 이미 받은 구간으로 계산할 수 있으면 계속 보입니다 — 인증키 설정을 확인하세요.",
  rate_limited: "금리 출처의 호출 한도를 넘었습니다. 잠시 뒤 다시 실행하세요.",
  format: "금리 출처의 응답 형식이 바뀌었습니다. 이미 받은 구간으로 계산할 수 있으면 계속 보입니다 — 어댑터를 고쳐야 합니다.",
  network: "금리 출처에 연결하지 못했습니다. 다시 실행하면 이어서 받습니다.",
};

export function depositFailureText(kind: DepositFailureKind | null, reason: string): string {
  return kind === null ? reason : FAILURE_TEXT[kind];
}

/** 투자처 이름 — 다섯은 고정이다(FR-003). 목록을 받기 전에도 화면이 그린다. */
export const INSTITUTION_NAMES: Record<DepositInstitutionKey, string> = {
  commercial_bank: "시중은행",
  savings_bank: "저축은행",
  credit_union: "신협",
  mutual_finance: "상호금융",
  saemaul: "새마을금고",
};

export const INSTITUTION_KEYS = Object.keys(INSTITUTION_NAMES) as DepositInstitutionKey[];

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

let unwatch: (() => void) | null = null;

function stopWatching(): void {
  unwatch?.();
  unwatch = null;
}

/** 조건을 질의 문자열로. 원금은 **문자열 그대로** 보낸다(헌법 원칙 VI). 통화는 보내지 않는다 — 원화만이다(FR-004). */
export function toQuery(input: DepositInput): string {
  return new URLSearchParams({
    institution: input.institution, start: input.start, principal: input.principal,
  }).toString();
}

const EMPTY_RESULT = {
  rows: [], summary: null, condition: null, resultName: null, collecting: null, progress: null,
  startable: null,
} satisfies Partial<DepositState>;

export const useDepositStore = create<DepositState>((set, get) => {
  /** 진행을 구독한다. **완료에 다시 요청한다** — 부분 결과를 먼저 보여주지 않는 대신 끝난 시점을 알려야 한다. */
  function watchProgress(jobId: number): void {
    stopWatching();
    unwatch = subscribeDepositProgress(jobId, {
      onSnapshot: (progress) => set({ progress }),
      onCompleted: () => {
        stopWatching();
        void get().run();
      },
      onFailed: (kind, reason) => {
        stopWatching();
        set({ collecting: null, progress: null, error: depositFailureText(kind, reason) });
      },
    });
  }

  return {
    input: { institution: "commercial_bank", start: DEFAULT_START, principal: "" },
    institutions: null,
    source: null,
    ...EMPTY_RESULT,
    loading: false,
    error: null,

    setInput: (next) => set({ input: { ...get().input, ...next } }),

    selectInstitution: (key) => {
      if (key === get().input.institution) return;
      stopWatching();
      set({ input: { ...get().input, institution: key }, ...EMPTY_RESULT, error: null });
    },

    loadInstitutions: async () => {
      try {
        const body = await apiClient.get<DepositInstitutionsResponse>("/api/deposit/institutions");
        set({ institutions: body.institutions, source: { name: body.source, basis: body.basis } });
      } catch {
        // 설명과 범위만 빠진다 — 이름은 고정이라 고르고 실행할 수 있다.
      }
    },

    refreshIfRan: async () => {
      if (get().summary === null) return;
      await get().run();
    },

    /** 실행 즉시 이전 결과를 비운다 — 남으면 지금 보는 수치가 어느 조건의 것인지 알 수 없다. */
    run: async () => {
      const { input } = get();
      if (input.principal === "") {
        set({ error: "투자 원금을 입력하세요." });
        return;
      }
      stopWatching();
      set({ ...EMPTY_RESULT, loading: true, error: null });
      try {
        const body = await apiClient.get<DepositSimulationResponse | DepositCollecting>(
          `/api/deposit/simulation?${toQuery(input)}`);
        if ("status" in body && body.status === "collecting") {
          set({ collecting: body, progress: null, loading: false });
          watchProgress(body.jobId);
          return;
        }
        const result = body as DepositSimulationResponse;
        set({
          rows: result.rows, summary: result.summary, condition: result.condition,
          resultName: result.institution.name, loading: false,
        });
        // 받은 범위가 늘었을 수 있다 — 시작 가능 달을 새로 보인다.
        void get().loadInstitutions();
      } catch (err) {
        if (err instanceof ApiError && err.code === "before_first_month" && err.body) {
          const { startableFrom, message: text } = err.body as unknown as BeforeFirstMonthBody;
          set({ startable: { startableFrom, basis: "rate_start", message: text }, loading: false });
          return;
        }
        set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
      }
    },

    dispose: () => stopWatching(),
  };
});
