/**
 * 투자 비교 화면의 상태 (013 T035·T050·T057·T077) — FR-002~FR-019, data-model 5, research R13-7·R13-8.
 *
 * - **대상마다 비교 경로 하나를 부른다**(research R13-1) — 계산된 대상부터 보이고(명확화 2), 막힌 대상이 하나라도 있으면 비교 전체가
 *   막힌다(명확화 1, `lib/compareBlock`)
 * - 202면 그 자산군의 진행 스트림을 **대상마다** 구독하고, 끝나면 **그 대상만** 다시 요청한다. 연달아 202를 세 번 받으면 수집 실패다 —
 *   환율 스트림이 곧바로 끝나는 경우의 되풀이를 막는다(FR-013 실패 양상 *늦게 일어남*)
 * - 실행마다 차례 번호를 올린다 — 늦게 온 이전 실행의 응답·스트림 사건은 버린다(FR-012a). 결과를 낸 조건과 지금 조건이 다르면
 *   흐린다(`isStale` — 파생 값이라 되돌리면 풀린다)
 * - **이력을 쓰지 않는다**(FR-020) — 메뉴 스토어의 `run` 계열·`saveHistoryFlow`를 부르지 않는다. 메뉴 스토어에서는 질의 함수만 쓴다
 * - **저장한 비교**(US4, data-model 5.2): 저장은 결과가 있고 흐리지 않고 막히지 않았을 때만이다(`saveBlockReason` — 수집 중인 대상이 남아도
 *   된다, 조건만의 기록이다). 본문은 결과를 낸 정규 조건이다 — 지금 입력이 아니다(흐린 결과를 다른 조건으로 저장하는 길을 막는다). 불러오기는
 *   입력을 채우고 곧바로 실행한다(FR-017). 저장·삭제가 실패해도 결과는 그대로다(FR-019)
 */
import { create } from "zustand";
import { subscribeCollection } from "@/lib/collectionStream";
import { ApiError } from "@/lib/apiClient";
import { classify, overall, type TargetState } from "@/lib/compareBlock";
import {
  comparisonPath,
  deleteSavedComparison,
  fetchComparison,
  fetchSavedComparisons,
  isCollecting,
  postSavedComparison,
} from "@/lib/compareApi";
import {
  allowedCurrencies,
  maxTargets,
  methodsFor,
  sameCondition,
  targetKey,
  toCondition,
  type CompareCondition,
} from "@/lib/compareCondition";
import { subscribeCryptoProgress } from "@/lib/cryptoProgressStream";
import { subscribeDepositProgress } from "@/lib/depositProgressStream";
import { DEFAULT_PRINCIPAL } from "@/lib/principalFormat";
import { subscribeRealEstateProgress } from "@/lib/realEstateProgressStream";
import { DEFAULT_START } from "@/lib/startDate";
import { subscribeStockProgress } from "@/lib/stockProgressStream";
import type {
  CompareAsset,
  CompareCollecting,
  CompareMethod,
  CompareTarget,
  CurrencyCode,
  Frequency,
  PrincipalCurrency,
  SavedComparison,
} from "@/lib/types";
import { failureText as cryptoFailureText } from "./cryptoStore";
import { depositFailureText } from "./depositStore";
import { realEstateFailureText } from "./realEstateStore";

/** `unitChange`(반복 2026-10-09)는 단가 등락률 — 예금은 %p 차이로 견준다. */
// 014 반복 2026-10-10f(FR-033) — 상장일 열도 정렬한다(날짜 글자, 비운 칸은 끝).
export type SortKey = "name" | "listing" | "asOf" | "principal" | "unitChange" | "currentValue" | "cost" | "profit" | "returnRate";

export interface SortState {
  key: SortKey;
  direction: "asc" | "desc";
}

export interface RunState {
  /** 실행 차례 번호 — 늦은 응답·스트림 사건을 버리는 기준. */
  seq: number;
  /** 결과를 낸 정규 조건 — 흐림·저장의 기준. */
  condition: CompareCondition;
  /** 대상 키 → 대상 상태. */
  byTarget: Record<string, TargetState>;
}

/** 저장한 비교 슬라이스(data-model 5.2). */
export interface SavedState {
  /** 서버 차례 그대로 — 최근 저장 먼저. */
  entries: SavedComparison[];
  loading: boolean;
  loadError: string | null;
  saveError: string | null;
  removeError: string | null;
  /** 저장을 보내는 중. */
  saving: boolean;
}

export interface CompareState {
  asset: CompareAsset;
  method: CompareMethod;
  frequency: Frequency;
  start: string;
  amount: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  targets: CompareTarget[];
  /** 알림 — 한도·같은 대상·통화 되돌림·대상 부족. */
  notice: string | null;
  run: RunState | null;
  sort: SortState | null;
  saved: SavedState;

  setAsset: (asset: CompareAsset) => void;
  setMethod: (method: CompareMethod) => void;
  setFrequency: (frequency: Frequency) => void;
  setStart: (start: string) => void;
  setAmount: (amount: string) => void;
  setPrincipalCurrency: (currency: PrincipalCurrency) => void;
  setReinvest: (reinvest: boolean) => void;
  /** 대상을 더한다. 같은 대상이거나 한도를 넘으면 더하지 않고 알린다. */
  addTarget: (target: CompareTarget) => boolean;
  removeTarget: (key: string) => void;
  toggleSort: (key: SortKey) => void;
  runComparison: () => Promise<void>;
  /** 실패한 대상만 다시 요청한다. */
  retryTarget: (key: string) => Promise<void>;
  /** 막힘 칸의 제안 — 시작일만 옮긴다. 실행하지 않는다(spec 가정). */
  moveStart: (date: string) => void;
  /** 진행 구독을 모두 푼다 — 화면을 떠날 때·자산군을 바꿀 때·새로 실행할 때. */
  dispose: () => void;
  /** 저장한 비교 목록을 받는다. */
  loadSaved: () => Promise<void>;
  /** 결과를 낸 조건을 이름과 함께 저장한다. 저장할 수 없거나 실패하면 `false`. */
  saveComparison: (name: string) => Promise<boolean>;
  /** 저장한 비교의 조건을 채우고 곧바로 실행한다. */
  openSaved: (id: number) => Promise<void>;
  removeSaved: (id: number) => Promise<void>;
}

/** 연달아 받은 202가 이만큼이면 수집 실패로 둔다(research R13-7). */
const MAX_COLLECTING_REPEATS = 3;

/** 대상 키 → 진행 구독 해제. */
const subscriptions = new Map<string, () => void>();

function unsubscribe(key: string): void {
  subscriptions.get(key)?.();
  subscriptions.delete(key);
}

function unsubscribeAll(): void {
  for (const stop of subscriptions.values()) stop();
  subscriptions.clear();
}

/** 지금 입력의 정규 조건. */
export function currentCondition(state: CompareState): CompareCondition {
  return toCondition({
    asset: state.asset, method: state.method, frequency: state.frequency, start: state.start, amount: state.amount,
    principalCurrency: state.principalCurrency, reinvest: state.reinvest, targets: state.targets,
  });
}

/** 결과를 낸 조건과 지금 조건이 다른가 — 다르면 결과를 흐린다(FR-012a). 실행하지 않았으면 흐리지 않는다. */
export function isStale(state: CompareState): boolean {
  return state.run !== null && !sameCondition(state.run.condition, currentCondition(state));
}

/**
 * 저장할 수 없는 까닭 — 결과가 없음·흐림·막힘. `null`이면 저장할 수 있다(수집 중인 대상이 남아도 된다 — 조건만의 기록이다). 흐린 결과를 저장하면
 * 저장한 조건(결과를 낸 조건)과 화면의 입력이 달라 무엇을 저장했는지 알 수 없다(FR-012a).
 */
export function saveBlockReason(state: CompareState): string | null {
  if (state.run === null) return "비교를 실행한 뒤 저장할 수 있습니다";
  if (isStale(state)) return "다시 실행한 뒤 저장할 수 있습니다";
  const states = runRows(state.run).map((r) => r.state);
  if (overall(states) === "blocked") return "막힌 대상이 있어 저장할 수 없습니다";
  if (!states.some((s) => s.status === "ok")) return "결과가 나온 뒤 저장할 수 있습니다";
  return null;
}

const failure = (err: unknown): string => (err instanceof ApiError ? err.message : "서버에 연결하지 못했습니다");

const SAVED_INITIAL: SavedState = {
  entries: [], loading: false, loadError: null, saveError: null, removeError: null, saving: false,
};

let runSeq = 0;

export const useCompareStore = create<CompareState>()((set, get) => {
  function setSaved(partial: Partial<SavedState>): void {
    set((s) => ({ saved: { ...s.saved, ...partial } }));
  }

  function setTarget(seq: number, key: string, next: TargetState): boolean {
    const run = get().run;
    if (run === null || run.seq !== seq) return false;
    set({ run: { ...run, byTarget: { ...run.byTarget, [key]: next } } });
    return true;
  }

  function progressOf(done: number, total: number) {
    return (seq: number, key: string) => {
      const state = get().run?.byTarget[key];
      if (state?.status !== "collecting") return;
      setTarget(seq, key, { ...state, progress: { done, total } });
    };
  }

  /** 202를 받은 대상의 진행을 구독한다. 끝나면 그 대상만 다시 요청한다. */
  function watch(seq: number, key: string, body: CompareCollecting, repeats: number): void {
    unsubscribe(key);
    const condition = get().run?.condition;
    if (condition === undefined) return;
    const live = () => get().run?.seq === seq;
    const completed = () => {
      unsubscribe(key);
      if (live()) void request(seq, key, repeats);
    };
    const failed = (reason: string) => {
      unsubscribe(key);
      if (live()) setTarget(seq, key, { status: "failed", reason });
    };
    const jobId = typeof body.jobId === "number" ? body.jobId : null;
    if (jobId === null && body.fx !== undefined) {
      // 환율만 비었다 — 통화 스트림이 한가해지면 다시 요청한다(서버가 다시 판정한다).
      let sawProgress = false;
      let idle = 0;
      subscriptions.set(key, subscribeCollection(body.fx.currency as CurrencyCode, {
        onSnapshot: () => {
          sawProgress = true;
        },
        onIdle: (payload) => {
          idle += 1;
          if (payload.busyWith === null && (sawProgress || idle >= 2)) completed();
        },
        onEvent: () => undefined,
      }));
      return;
    }
    if (jobId === null) return;
    switch (condition.asset) {
      case "stock":
        subscriptions.set(key, subscribeStockProgress(jobId, {
          onSnapshot: (s) => progressOf(s.daysDone, s.daysTotal)(seq, key),
          onCompleted: completed,
          onFailed: (reason) => failed(reason),
        }));
        return;
      case "crypto":
        subscriptions.set(key, subscribeCryptoProgress(jobId, {
          onSnapshot: (s) => progressOf(s.daysDone, s.daysTotal)(seq, key),
          onCompleted: completed,
          onFailed: (kind, reason) => failed(cryptoFailureText(kind, reason)),
        }));
        return;
      case "deposit":
        subscriptions.set(key, subscribeDepositProgress(jobId, {
          onSnapshot: (s) => progressOf(s.monthsDone, s.monthsTotal)(seq, key),
          onCompleted: completed,
          onFailed: (kind, reason) => failed(depositFailureText(kind, reason)),
        }));
        return;
      case "realestate":
        subscriptions.set(key, subscribeRealEstateProgress(jobId, {
          onSnapshot: (s) => progressOf(s.done, s.total)(seq, key),
          onCompleted: completed,
          onFailed: (kind, reason) => failed(realEstateFailureText(kind, reason)),
        }));
    }
  }

  /** 대상 하나를 요청한다. `repeats`는 그때까지 연달아 받은 202의 수다. */
  async function request(seq: number, key: string, repeats: number): Promise<void> {
    const run = get().run;
    if (run === null || run.seq !== seq) return;
    const target = run.condition.targets.find((t) => targetKey(t) === key);
    if (target === undefined) return;
    if (!setTarget(seq, key, { status: "requesting" })) return;
    try {
      const body = await fetchComparison(comparisonPath(run.condition, target));
      if (get().run?.seq !== seq) return;
      if (isCollecting(body)) {
        const next = repeats + 1;
        if (next >= MAX_COLLECTING_REPEATS) {
          setTarget(seq, key, { status: "failed", reason: "수집이 끝나지 않았습니다 — 다시 시도하세요." });
          return;
        }
        setTarget(seq, key, { status: "collecting", body, progress: null, repeats: next });
        watch(seq, key, body, next);
        return;
      }
      setTarget(seq, key, { status: "ok", data: body });
    } catch (err) {
      if (get().run?.seq !== seq) return;
      const result = classify(err);
      setTarget(seq, key, "blocked" in result
        ? { status: "blocked", reason: result.blocked }
        : { status: "failed", reason: result.failed });
    }
  }

  /** 원금 통화가 대상에 맞지 않으면 원화로 돌리고 알린다(006 FR-050b와 같은 이유 — 몰래 다른 통화로 계산하지 않는다). */
  function keepCurrency(targets: CompareTarget[]): Partial<CompareState> {
    const { asset, principalCurrency } = get();
    if (allowedCurrencies(asset, targets).includes(principalCurrency)) return {};
    return {
      principalCurrency: "KRW",
      notice: `대상의 통화가 같지 않아 ${principalCurrency} 원금을 고를 수 없습니다 — 원화로 바꿨습니다.`,
    };
  }

  return {
    asset: "stock",
    method: "lump_sum",
    frequency: "monthly",
    start: DEFAULT_START,
    amount: DEFAULT_PRINCIPAL,
    principalCurrency: "KRW",
    reinvest: true,
    targets: [],
    notice: null,
    run: null,
    sort: null,
    saved: SAVED_INITIAL,

    setAsset: (asset) => {
      if (asset === get().asset) return;
      unsubscribeAll();
      runSeq += 1;
      const methods = methodsFor(asset);
      set({
        asset, targets: [], run: null, notice: null, sort: null, principalCurrency: "KRW",
        method: methods.includes(get().method) ? get().method : methods[0],
      });
    },
    setMethod: (method) => set({ method }),
    setFrequency: (frequency) => set({ frequency }),
    setStart: (start) => set({ start }),
    setAmount: (amount) => set({ amount }),
    setPrincipalCurrency: (principalCurrency) => set({ principalCurrency, notice: null }),
    setReinvest: (reinvest) => set({ reinvest }),

    addTarget: (target) => {
      const { asset, targets } = get();
      const key = targetKey(target);
      if (targets.some((t) => targetKey(t) === key)) {
        set({ notice: "이미 더한 대상입니다." });
        return false;
      }
      const max = maxTargets(asset);
      if (targets.length >= max) {
        set({ notice: `최대 ${max}개까지 비교할 수 있습니다.` });
        return false;
      }
      const next = [...targets, target];
      set({ targets: next, notice: null, ...keepCurrency(next) });
      return true;
    },

    removeTarget: (key) => {
      const next = get().targets.filter((t) => targetKey(t) !== key);
      set({ targets: next, notice: null, ...keepCurrency(next) });
    },

    toggleSort: (key) => {
      const sort = get().sort;
      set({ sort: sort?.key === key
        ? { key, direction: sort.direction === "asc" ? "desc" : "asc" }
        : { key, direction: key === "name" || key === "asOf" || key === "listing" ? "asc" : "desc" } });
    },

    runComparison: async () => {
      const state = get();
      if (state.targets.length < 2) {
        set({ notice: "비교하려면 대상이 2개 이상이 필요합니다." });
        return;
      }
      unsubscribeAll();
      runSeq += 1;
      const seq = runSeq;
      const condition = currentCondition(state);
      const byTarget: Record<string, TargetState> = {};
      for (const t of condition.targets) byTarget[targetKey(t)] = { status: "requesting" };
      set({ run: { seq, condition, byTarget }, notice: null });
      await Promise.all(condition.targets.map((t) => request(seq, targetKey(t), 0)));
    },

    retryTarget: async (key) => {
      const run = get().run;
      if (run === null) return;
      unsubscribe(key);
      await request(run.seq, key, 0);
    },

    moveStart: (date) => set({ start: date }),

    dispose: () => {
      unsubscribeAll();
    },

    loadSaved: async () => {
      setSaved({ loading: true, loadError: null });
      try {
        const body = await fetchSavedComparisons();
        setSaved({ entries: body.entries, loading: false });
      } catch (err) {
        setSaved({ loading: false, loadError: `저장한 비교를 받지 못했습니다 — ${failure(err)}` });
      }
    },

    saveComparison: async (name) => {
      const state = get();
      const trimmed = name.trim();
      if (state.run === null || saveBlockReason(state) !== null || trimmed === "") return false;
      setSaved({ saving: true, saveError: null });
      try {
        const body = await postSavedComparison(trimmed, state.run.condition);
        setSaved({ entries: body.entries, saving: false });
        return true;
      } catch (err) {
        setSaved({ saving: false, saveError: `저장하지 못했습니다 — ${failure(err)}` });
        return false;
      }
    },

    openSaved: async (id) => {
      const entry = get().saved.entries.find((e) => e.id === id);
      if (entry === undefined) return;
      const c = entry.condition;
      unsubscribeAll();
      runSeq += 1;
      // 조건에 없는 칸(일시금의 주기, 부동산의 금액, 주식 밖의 재투자)은 지금 입력을 둔다 — 정규 조건이 그 칸을 쓰지 않아 같은 조건이다.
      set((s) => ({
        asset: c.asset, method: c.method, frequency: c.frequency ?? s.frequency, start: c.start, amount: c.amount ?? s.amount,
        principalCurrency: c.principalCurrency, reinvest: c.reinvest ?? s.reinvest, targets: c.targets,
        run: null, notice: null, sort: null,
      }));
      await get().runComparison();
    },

    removeSaved: async (id) => {
      setSaved({ removeError: null });
      try {
        const body = await deleteSavedComparison(id);
        setSaved({ entries: body.entries });
      } catch (err) {
        setSaved({ removeError: `지우지 못했습니다 — ${failure(err)}` });
      }
    },
  };
});

/** 정렬·표가 쓰는 대상 열(실행의 차례). */
export function runRows(run: RunState): { key: string; target: CompareTarget; state: TargetState }[] {
  return run.condition.targets.map((target) => {
    const key = targetKey(target);
    return { key, target, state: run.byTarget[key] ?? { status: "requesting" } };
  });
}
