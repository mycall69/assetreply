/**
 * 예금 시뮬레이션 화면의 단일 상태 원천 (T021) — 008 FR-002~FR-007, FR-011, FR-016, ui-wireframes D2·D8, 헌법 원칙 VII.
 *
 * 가상자산 화면(`cryptoStore`)을 본뜬다. **결과를 저장하지 않는다** — 설정과 금리가 바뀌면 결과가 달라진다(005 R5-9).
 *
 * - **부분 결과를 보여주지 않는다**(FR-011). 202면 결과를 비우고 진행(받은 달 / 받을 달)을 구독하고, 끝나면 다시 요청한다
 * - 수집이 실패하면 **종류마다 다른 말**로 할 일까지 보인다(FR-016). 다만 금리를 **받아 둔 투자처**면 곧바로 한 번 다시 요청한다
 *   (FR-016a) — 서버가 받아 둔 금리로 계산해 결과와 확인 실패(`recheckFailed`)를 준다. 받은 적 없는 투자처는 다시 요청하지 않는다 —
 *   같은 실패가 되풀이되며 출처 호출만 쓴다. 다시 요청은 한 실행에 한 번이다
 * - 투자처를 바꾸면 결과를 지운다(D2) — 이전 투자처의 결과가 새 이름 아래 남으면 그 수치를 새 투자처의 것으로 읽는다
 * - 011 — 상품(`product`)이 정기 적금이면 따로 된 경로(`/api/deposit/installment-simulation`)를 부르고 결과는 `installment`에 둔다
 *   (정기예금 칸과 한 번에 한쪽만 — research R11-11). 202는 금리 계열(적금 → 정기예금)마다 온다 — 끝날 때마다 다시 요청한다.
 *   적금이 없는 투자처가 골라져 있는데 적금으로 바꾸면 시중은행으로 바꾸고 그 사실을 알린다(ui-wireframes §7)
 */

import { create } from "zustand";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import type { Startable } from "@/components/stock/StartDateInput";
import { ApiError, apiClient } from "@/lib/apiClient";
import { INITIAL_HISTORY, removeHistoryFlow, restoreHistoryFlow, saveHistoryFlow } from "@/lib/historyFlow";
import { subscribeDepositProgress, type DepositProgressSnapshot } from "@/lib/depositProgressStream";
import { DEFAULT_START } from "@/lib/startDate";
import type {
  BeforeFirstMonthBody,
  DepositCollecting,
  DepositCondition,
  DepositFailureKind,
  DepositHistoryEntry,
  DepositInstitution,
  DepositInstitutionKey,
  DepositInstitutionsResponse,
  DepositProduct,
  DepositRow,
  DepositSimulationResponse,
  DepositSummary,
  InstallmentCondition,
  InstallmentContract,
  InstallmentResponse,
  InstallmentRow,
  InstallmentSummary,
  LadderDeposit,
  SimulationSeriesResponse,
} from "@/lib/types";

export interface DepositInput {
  institution: DepositInstitutionKey;
  start: string;
  /** 원 단위 정수 문자열(쉼표 없음). 문자열로 들고 있다가 문자열로 보낸다(헌법 원칙 VI). */
  principal: string;
}

/** 011 — 적금 결과. 정기예금 칸과 **따로 둔다** — 한 번에 한쪽만 채운다(research R11-11). */
export interface InstallmentResult {
  rows: InstallmentRow[];
  summary: InstallmentSummary;
  condition: InstallmentCondition;
  contracts: InstallmentContract[];
  deposits: LadderDeposit[];
  /** 결과의 투자처 이름 — 입력이 바뀌어도 결과가 어느 투자처의 것인지 남긴다. */
  name: string;
  series: SimulationSeriesResponse | null;
  seriesError: string | null;
}

interface DepositState {
  input: DepositInput;
  /** 011 — 상품. 기본은 정기예금이다(011 전과 같은 화면). 적금이면 `input.principal`이 월 납입액이다. */
  product: DepositProduct;
  /** 011 — 적금 결과. 정기예금이면 `null`이다. */
  installment: InstallmentResult | null;
  /** 011 — 적금으로 바꾸며 투자처를 바꿨다는 알림(적금이 없는 투자처였다). */
  productNotice: string | null;
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
  /** 차트용 시계열(FR-036). 표와 **같은 조건**으로 따로 받는다. */
  series: SimulationSeriesResponse | null;
  /** 차트만 실패한 사유. **표를 지우지 않는다** — 차트가 비는 것과 결과가 없는 것은 다른 사건이다(005와 같다). */
  seriesError: string | null;
  collecting: DepositCollecting | null;
  /** 수집 진행. 스냅샷이 오기 전에는 `null`이다 — 0/0은 멈춘 것처럼 보인다. */
  progress: DepositProgressSnapshot | null;
  loading: boolean;
  error: string | null;

  /** 이력(FR-037). **조건만** 담긴다. 주식·가상자산 이력과 따로다. 012부터 로컬 DB에 있다(`lib/historyFlow`). */
  history: DepositHistoryEntry[];
  historyLoading: boolean;
  historyLoadError: string | null;
  historySaveError: string | null;
  historyNotice: string | null;
  retentionDays: number | null | undefined;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;

  setInput: (next: Partial<DepositInput>) => void;
  /** 011 — 상품을 바꾼다. 결과를 비운다 — 다른 상품의 결과가 이 상품의 조건과 함께 보이지 않게(조건은 남는다). */
  setProduct: (next: DepositProduct) => void;
  /** 투자처를 고른다. 결과를 지운다(D2) — 실행은 버튼으로 한다. */
  selectInstitution: (key: DepositInstitutionKey) => void;
  loadInstitutions: () => Promise<void>;
  run: () => Promise<void>;
  /** 설정이 바뀐 뒤 결과를 다시 받는다(FR-031). 실행한 적이 없으면 아무것도 하지 않는다. */
  refreshIfRan: () => Promise<void>;
  /** 화면을 떠날 때 진행 구독을 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다. */
  dispose: () => void;
  /** 012 — 옛 브라우저 이력을 옮긴 뒤 목록을 받는다. 다시 시도도 이것이다(FR-014a). */
  restoreHistory: () => Promise<void>;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => Promise<void>;
  /** 이력의 조건을 입력에 넣고 곧바로 실행한다. */
  rerunHistory: (id: string) => Promise<void>;
  /** 고른 이력을 **지금 다시 계산해서** 겹친다(FR-038) — 저장된 결과가 없다. */
  compareSelected: () => Promise<void>;
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
/** 지금 실행이 화면이 스스로 한 것인지(수집 완료·실패 뒤). 사용자가 실행하면 자동 다시 요청의 기회를 되돌린다. */
let automaticRun = false;
/** 이 실행에서 실패 뒤 다시 요청했는지(FR-016a) — 한 실행에 한 번. */
let retriedAfterFailure = false;

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

/** 011 — 적금 질의. 금액은 `amount`(월 납입액, 문자열 그대로)다. */
export function toInstallmentQuery(input: DepositInput): string {
  return new URLSearchParams({
    institution: input.institution, start: input.start, amount: input.principal,
  }).toString();
}

const EMPTY_RESULT = {
  rows: [], summary: null, condition: null, resultName: null, series: null, seriesError: null,
  collecting: null, progress: null, startable: null, installment: null,
} satisfies Partial<DepositState>;

/** 받침이 있으면 `은`·`으로`, 없으면 `는`·`로`. 투자처 이름 다섯에만 쓴다. */
function hasFinalConsonant(word: string): boolean {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code <= 11171 && code % 28 !== 0;
}

function switchedNotice(from: DepositInstitutionKey, to: DepositInstitutionKey): string {
  const a = INSTITUTION_NAMES[from];
  const b = INSTITUTION_NAMES[to];
  return `${a}${hasFinalConsonant(a) ? "은" : "는"} 적금이 없어 ${b}${hasFinalConsonant(b) ? "으로" : "로"} 바꿨습니다.`;
}

export const useDepositStore = create<DepositState>((set, get) => {
  /**
   * 금리를 받아 둔 투자처인가 — 투자처 목록의 `firstMonth`로 안다. 목록을 받지 못했으면 모른다(받지 않은 것으로 본다).
   * 011 — 적금 계열이면 그 투자처의 적금 칸(`installment.firstMonth`)으로 본다.
   */
  function hasRates(key: DepositInstitutionKey, series?: "installment" | "deposit"): boolean {
    return (get().institutions ?? []).some((i) => {
      if (i.key !== key) return false;
      if (series !== "installment") return i.firstMonth !== null;
      return i.installment !== undefined && i.installment.available && i.installment.firstMonth !== null;
    });
  }

  /** 적금을 고를 수 있는 투자처인가. 목록을 받기 전에는 모른다 — 막지 않고 서버가 사유와 함께 막는다. */
  function installmentAvailable(key: DepositInstitutionKey): boolean {
    const found = (get().institutions ?? []).find((i) => i.key === key);
    return found?.installment === undefined || found.installment.available;
  }

  function rerunAutomatically(): void {
    automaticRun = true;
    void get().run();
  }

  /** 진행을 구독한다. **완료에 다시 요청한다** — 부분 결과를 먼저 보여주지 않는 대신 끝난 시점을 알려야 한다. */
  function watchProgress(jobId: number, institution: DepositInstitutionKey,
    series?: "installment" | "deposit"): void {
    stopWatching();
    unwatch = subscribeDepositProgress(jobId, {
      onSnapshot: (progress) => set({ progress }),
      onCompleted: () => {
        stopWatching();
        rerunAutomatically();
      },
      onFailed: (kind, reason) => {
        stopWatching();
        // FR-016a — 받아 둔 금리로 답할 수 있으면 그 "다음 실행"을 화면이 대신 한다. 한 실행에 한 번.
        if (hasRates(institution, series) && !retriedAfterFailure) {
          retriedAfterFailure = true;
          rerunAutomatically();
          return;
        }
        set({ collecting: null, progress: null, error: depositFailureText(kind, reason) });
      },
    });
  }

  /** 011 — 적금을 실행한다. 수집 대기·오류의 처리는 정기예금과 같다(같은 202 본문 + `series`, 같은 진행 구독). */
  async function runInstallment(input: DepositInput): Promise<void> {
    const query = toInstallmentQuery(input);
    try {
      const body = await apiClient.get<InstallmentResponse | DepositCollecting>(
        `/api/deposit/installment-simulation?${query}`);
      if ("status" in body && body.status === "collecting") {
        // 부분 결과를 보이지 않고 이력에도 남기지 않는다(정기예금과 같다 — FR-011).
        set({ collecting: body, progress: null, loading: false });
        watchProgress(body.jobId, body.institution, body.series);
        return;
      }
      const result = body as InstallmentResponse;
      set({
        installment: {
          rows: result.rows, summary: result.summary, condition: result.condition, contracts: result.contracts,
          deposits: result.deposits, name: result.institution.name, series: null, seriesError: null,
        },
      });
      await saveHistoryFlow("deposit", {
        institution: input.institution, start: input.start, principal: input.principal, product: "installment" },
      get, set);
      try {
        const series = await apiClient.get<SimulationSeriesResponse>(
          `/api/deposit/installment-simulation/series?${query}`);
        const current = get().installment;
        set({ installment: current === null ? null : { ...current, series }, loading: false });
      } catch (err) {
        const current = get().installment;
        set({
          installment: current === null ? null
            : { ...current, seriesError: message(err, "차트를 불러오지 못했습니다.") },
          loading: false,
        });
      }
      void get().loadInstitutions();
    } catch (err) {
      fail(err);
    }
  }

  /** 실행이 실패한 사유를 상태로 옮긴다 — 정기예금과 적금이 같은 규칙이다(같은 오류 본문). */
  function fail(err: unknown): void {
    if (err instanceof ApiError && err.code === "before_first_month" && err.body) {
      const { startableFrom, message: text } = err.body as unknown as BeforeFirstMonthBody;
      set({ startable: { startableFrom, basis: "rate_start", message: text }, loading: false });
      return;
    }
    set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
  }

  return {
    input: { institution: "commercial_bank", start: DEFAULT_START, principal: "" },
    product: "deposit",
    productNotice: null,
    institutions: null,
    source: null,
    ...EMPTY_RESULT,
    loading: false,
    error: null,
    ...INITIAL_HISTORY,
    comparison: [],
    comparing: false,
    comparisonError: null,

    setInput: (next) => set({ input: { ...get().input, ...next } }),

    setProduct: (next) => {
      stopWatching();
      const input = get().input;
      const blocked = next === "installment" && !installmentAvailable(input.institution);
      // 적금이 없는 투자처면 첫 번째 고를 수 있는 투자처로 바꾸고 알린다 — 조용히 바꾸면 사용자는 고른 투자처의 결과로 읽는다.
      const fallback: DepositInstitutionKey = "commercial_bank";
      set({
        product: next,
        input: blocked ? { ...input, institution: fallback } : input,
        productNotice: blocked ? switchedNotice(input.institution, fallback) : null,
        ...EMPTY_RESULT, error: null, loading: false,
      });
    },

    selectInstitution: (key) => {
      if (key === get().input.institution) return;
      stopWatching();
      set({ input: { ...get().input, institution: key }, ...EMPTY_RESULT, error: null, productNotice: null });
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
      if (get().summary === null && get().installment === null) return;
      await get().run();
    },

    /** 실행 즉시 이전 결과를 비운다 — 남으면 지금 보는 수치가 어느 조건의 것인지 알 수 없다. */
    run: async () => {
      if (!automaticRun) retriedAfterFailure = false;
      automaticRun = false;
      const { input, product } = get();
      if (input.principal === "") {
        set({ error: product === "installment" ? "월 납입액을 입력하세요." : "투자 원금을 입력하세요." });
        return;
      }
      stopWatching();
      set({ ...EMPTY_RESULT, loading: true, error: null });
      if (product === "installment") {
        await runInstallment(input);
        return;
      }
      try {
        const body = await apiClient.get<DepositSimulationResponse | DepositCollecting>(
          `/api/deposit/simulation?${toQuery(input)}`);
        if ("status" in body && body.status === "collecting") {
          set({ collecting: body, progress: null, loading: false });
          watchProgress(body.jobId, body.institution);
          return;
        }
        const result = body as DepositSimulationResponse;
        set({
          rows: result.rows, summary: result.summary, condition: result.condition,
          resultName: result.institution.name,
        });
        // FR-037 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다.** 수집 중(202)이면 남기지 않는다 — 아직 결과가 없다.
        await saveHistoryFlow("deposit", {
          institution: input.institution, start: input.start, principal: input.principal }, get, set);
        // **표가 수집 중이 아님을 확인한 뒤에 받는다** — 나란히 보내면 같은 구간에 수집 요청이 두 번 나간다(005와 같다).
        try {
          const series = await apiClient.get<SimulationSeriesResponse>(
            `/api/deposit/simulation/series?${toQuery(input)}`);
          set({ series, loading: false });
        } catch (err) {
          set({ seriesError: message(err, "차트를 불러오지 못했습니다."), loading: false });
        }
        // 받은 범위가 늘었을 수 있다 — 시작 가능 달을 새로 보인다.
        void get().loadInstitutions();
      } catch (err) {
        fail(err);
      }
    },

    dispose: () => stopWatching(),

    restoreHistory: () => restoreHistoryFlow("deposit", get, set),

    toggleHistory: (id) => {
      const selected = get().selectedHistory;
      set({ selectedHistory: selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id] });
    },

    removeHistoryEntry: async (id) => {
      if (!(await removeHistoryFlow("deposit", id, get, set))) return;
      // 지운 항목의 선을 남기면 목록에 없는 조건이 차트에 남는다.
      set({ comparison: get().comparison.filter((c) => c.id !== id) });
    },

    rerunHistory: async (id) => {
      const entry = get().history.find((e) => e.id === id);
      if (entry === undefined) return;
      stopWatching();
      set({ input: { institution: entry.institution, start: entry.start, principal: entry.principal },
        // 011 — 빠진 칸은 정기예금이다(011 전 항목). `undefined`를 상품으로 옮기지 않는다.
        product: entry.product === "installment" ? "installment" : "deposit", productNotice: null,
        ...EMPTY_RESULT, error: null });
      await get().run();
    },

    compareSelected: async () => {
      const { history, selectedHistory } = get();
      const targets = history.filter((e) => selectedHistory.includes(e.id));
      if (targets.length < 2) return;
      set({ comparing: true, comparisonError: null, comparison: [] });
      const items: ComparisonItem[] = [];
      const failed: string[] = [];
      for (const entry of targets) {
        const name = (INSTITUTION_NAMES as Record<string, string>)[entry.institution] ?? entry.institution;
        // 011 — 적금 항목은 적금 시계열 경로이고, 범례 이름에 상품을 붙인다(FR-034).
        const installment = entry.product === "installment";
        const path = installment ? `/api/deposit/installment-simulation/series?${toInstallmentQuery(entry)}`
          : `/api/deposit/simulation/series?${toQuery(entry)}`;
        const product = installment ? `${name} · 정기 적금` : name;
        try {
          const body = await apiClient.get<SimulationSeriesResponse | DepositCollecting>(path);
          if ("status" in body && body.status === "collecting") {
            // 부분 결과를 완성된 선처럼 겹치지 않는다.
            failed.push(`${product}(아직 받지 못한 구간이 있습니다 — 실행해서 받으세요)`);
            continue;
          }
          const series = body as SimulationSeriesResponse;
          // FR-038 — 잠정 금리로 계산한 선이 섞여 있으면 범례가 말한다.
          const label = series.provisionalFrom != null ? `${product} (잠정)` : product;
          items.push({ id: entry.id, label, start: entry.start, series });
        } catch (err) {
          // 조용히 빼지 않는다 — 빼고 비교하면 그 투자처가 진 것으로 읽힌다.
          failed.push(err instanceof ApiError && err.code === "unknown_institution"
            ? `${name}(알 수 없는 투자처)` : `${name}(${message(err, "알 수 없는 오류")})`);
        }
      }
      set({
        comparison: items,
        comparing: false,
        comparisonError: failed.length === 0 ? null : `${failed.join(" · ")}의 시계열을 불러오지 못했습니다.`,
      });
    },
  };
});
