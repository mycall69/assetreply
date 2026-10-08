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
 */
import { create } from "zustand";
import { subscribeCollection } from "@/lib/collectionStream";
import { classify, type TargetState } from "@/lib/compareBlock";
import { comparisonPath, fetchComparison, isCollecting } from "@/lib/compareApi";
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
} from "@/lib/types";
import { failureText as cryptoFailureText } from "./cryptoStore";
import { depositFailureText } from "./depositStore";
import { realEstateFailureText } from "./realEstateStore";

export type SortKey = "name" | "asOf" | "principal" | "currentValue" | "cost" | "profit" | "returnRate";

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

let runSeq = 0;

export const useCompareStore = create<CompareState>()((set, get) => {
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
        : { key, direction: key === "name" || key === "asOf" ? "asc" : "desc" } });
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
  };
});

/** 정렬·표가 쓰는 대상 열(실행의 차례). */
export function runRows(run: RunState): { key: string; target: CompareTarget; state: TargetState }[] {
  return run.condition.targets.map((target) => {
    const key = targetKey(target);
    return { key, target, state: run.byTarget[key] ?? { status: "requesting" } };
  });
}
