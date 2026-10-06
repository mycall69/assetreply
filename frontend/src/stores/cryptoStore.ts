/**
 * 가상자산 시뮬레이션 화면의 단일 상태 원천 (T033) — 007 FR-013, FR-020, FR-008, 헌법 원칙 VII.
 *
 * 주식 화면(`stockStore`)을 본뜬다. **결과를 저장하지 않는다** — 설정과 환율이 바뀌면 결과가 달라진다(005 R5-9). 상태는 "지금
 * 화면에 그릴 것"만 담는다.
 *
 * - **부분 결과를 보여주지 않는다**(FR-013). 202면 결과를 비우고 진행을 구독하고, 끝나면 다시 요청한다
 * - 수집이 실패하면 **종류마다 다른 말**로 사유를 보인다(FR-020)
 * - 011 — 투자 방식(`plan`)이 적립식이면 따로 된 경로(`/api/crypto/recurring-simulation`)를 부르고 결과는 `recurring`에 둔다.
 *   일시금 칸과 한 번에 한쪽만 채운다(research R11-11)
 */

import { create } from "zustand";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeCollection } from "@/lib/collectionStream";
import { INITIAL_HISTORY, removeHistoryFlow, restoreHistoryFlow, saveHistoryFlow } from "@/lib/historyFlow";
import { subscribeCryptoProgress, type CryptoProgressSnapshot } from "@/lib/cryptoProgressStream";
import { isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import { DEFAULT_PRINCIPAL } from "@/lib/principalFormat";
import { DEFAULT_START } from "@/lib/startDate";
import { periodQuery } from "@/lib/tablePeriod";
import type {
  BeforeListingBody,
  CoinRef,
  CryptoCollecting,
  CryptoCondition,
  CryptoFailureKind,
  CryptoHistoryEntry,
  CryptoSimulationResponse,
  CryptoSummary,
  CryptoTableRow,
  ExchangeInfo,
  Frequency,
  FxCollecting,
  FxNotAvailableBefore,
  InvestmentPlan,
  JobRow,
  PeriodUnit,
  PrincipalCurrency,
  RecurringCondition,
  RecurringCryptoResponse,
  RecurringCryptoSummary,
  RecurringCryptoTableRow,
  SimulationSeriesResponse,
} from "@/lib/types";

export interface CryptoInput {
  coin: CoinRef | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
}

/** 011 — 적립식 결과. 일시금 칸과 **따로 둔다** — 한 번에 한쪽만 채운다(research R11-11). */
export interface CryptoRecurringResult {
  rows: RecurringCryptoTableRow[];
  summary: RecurringCryptoSummary;
  condition: RecurringCondition;
  hasMore: boolean;
  oldestReturned: string | null;
  series: SimulationSeriesResponse | null;
  seriesError: string | null;
}

/** 이력 범례의 주기 이름(011). */
const FREQUENCY_NAME: Record<Frequency, string> = { daily: "매일", weekly: "매주", monthly: "매달", yearly: "매년" };

interface CryptoState {
  input: CryptoInput;
  /**
   * 011 — 투자 방식(일시금·적립식)과 주기. `input`(일시금 네 칸)과 따로 둔다. 적립식이면 `input.principal`이 한 번 납입액이다.
   */
  plan: InvestmentPlan;
  /** 011 — 적립식 결과. 일시금이면 `null`이다. */
  recurring: CryptoRecurringResult | null;
  /** 실행 뒤 서버가 알려 준 시작 가능 날짜(FR-008). 시작일은 바꾸지 않는다 — 옮기기는 눌러야 일어난다. */
  startable: Pick<BeforeListingBody, "startableFrom" | "basis" | "message"> | null;
  rows: CryptoTableRow[];
  summary: CryptoSummary | null;
  condition: CryptoCondition | null;
  exchange: ExchangeInfo | null;
  hasMore: boolean;
  oldestReturned: string | null;
  /** 차트용 일봉 시계열(FR-043). 표와 **같은 조건**으로 따로 받는다. */
  series: SimulationSeriesResponse | null;
  /** 차트만 실패한 사유. **표를 지우지 않는다** — 차트가 비는 것과 결과가 없는 것은 다른 사건이다(005와 같다). */
  seriesError: string | null;
  collecting: CryptoCollecting | null;
  /** 수집 진행. 스냅샷이 오기 전에는 `null`이다 — 0/0은 멈춘 것처럼 보인다. */
  progress: CryptoProgressSnapshot | null;
  fxBlocked: FxNotAvailableBefore | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;

  /** 012 — 일자별 표의 단위(처음 일). 주식 스토어와 같은 규칙이다 — 다시 실행해도 남고, 일이면 요청에 `period`가 없다. */
  tablePeriod: PeriodUnit;
  /** 표 요청의 차례 번호. 실행·단위 전환마다 올린다 — 번호가 다른 응답은 버린다(이어 받기 포함, 012 FR-006). */
  tableSeq: number;
  tableLoading: boolean;
  tableError: string | null;

  /** 이력(FR-045). **조건만** 담긴다. 주식 이력과 따로다. 012부터 로컬 DB에 있다(`lib/historyFlow`). */
  history: CryptoHistoryEntry[];
  historyLoading: boolean;
  historyLoadError: string | null;
  historySaveError: string | null;
  historyNotice: string | null;
  retentionDays: number | null | undefined;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;

  setInput: (next: Partial<CryptoInput>) => void;
  /** 011 — 투자 방식·주기를 바꾼다. 두 결과를 모두 비운다 — 한쪽 결과가 다른 방식의 조건과 함께 보이지 않게(조건은 남는다). */
  setPlan: (next: InvestmentPlan) => void;
  /** 검색에서 고른 코인. 시작일·원금은 그대로 둔다 — 같은 조건으로 두 코인을 비교하려던 사용자 몰래 바꾸지 않는다. */
  selectCoin: (coin: CoinRef) => void;
  run: () => Promise<void>;
  loadMore: () => Promise<void>;
  /** 012 — 표의 단위를 바꾼다. 표의 행만 다시 받는다 — 요약·시계열은 같은 객체로 남는다(FR-007). 결과가 없으면 단위만 바꾼다. */
  setTablePeriod: (period: PeriodUnit) => Promise<void>;
  /** 설정이 바뀐 뒤 결과를 다시 받는다(FR-033). 실행한 적이 없으면 아무것도 하지 않는다. */
  refreshIfRan: () => Promise<void>;
  /** 화면을 떠날 때 진행 구독을 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다. */
  dispose: () => void;
  /** 012 — 옛 브라우저 이력을 옮긴 뒤 목록을 받는다. 다시 시도도 이것이다(FR-014a). */
  restoreHistory: () => Promise<void>;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => Promise<void>;
  /** 이력의 조건을 입력에 넣고 실행한다. 코인이 없어졌으면 "검색에서 다시 고르세요"를 말한다. */
  rerunHistory: (id: string) => Promise<void>;
  /** 고른 이력을 **지금 다시 계산해서** 겹친다(FR-046) — 저장된 결과가 없다. */
  compareSelected: () => Promise<void>;
}

/** 수집 실패 종류 → 할 일까지 말하는 문구 (ui-wireframes C7). */
const FAILURE_TEXT: Record<CryptoFailureKind, string> = {
  blocked: "시세 출처가 접근을 막았습니다. 이미 받은 구간만으로는 결과를 낼 수 없습니다 — 잠시 뒤 다시 실행하세요.",
  format: "시세 출처의 응답 형식이 바뀌었습니다. 이미 받은 구간만으로는 결과를 낼 수 없습니다 — 어댑터를 고쳐야 합니다.",
  network: "시세 출처에 연결하지 못했습니다. 다시 실행하면 이어서 받습니다.",
  empty: "출처에 이 코인의 시세가 없습니다.",
};

export function failureText(kind: CryptoFailureKind | null, reason: string): string {
  return kind === null ? reason : FAILURE_TEXT[kind];
}

/** 이력에 남기는 코인 — 검색 결과의 순위 같은 것은 남기지 않는다(012 전 lib와 같은 모양). */
function coinRef({ coinId, symbol, name, nameKo, slug, currency }: CoinRef): Omit<CoinRef, "rank"> {
  return { coinId, symbol, name, nameKo, slug, currency };
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

let unwatch: (() => void) | null = null;
let unwatchFx: (() => void) | null = null;
/** 판정 없이 다시 요청한 적이 있는지. 사용자가 실행하면 지운다 — 같은 실패를 끝없이 되풀이하지 않게 한다. */
let unjudgedRerun = false;
let automaticRun = false;

function stopWatching(): void {
  unwatch?.();
  unwatch = null;
  unwatchFx?.();
  unwatchFx = null;
}

/** 조건을 질의 문자열로. 원금은 **문자열 그대로** 보낸다(헌법 원칙 VI). */
export function toQuery(input: CryptoInput): string {
  if (input.coin === null) return "";
  return new URLSearchParams({
    coinId: String(input.coin.coinId),
    start: input.start,
    principal: input.principal,
    principalCurrency: input.principalCurrency,
  }).toString();
}

/** 011 — 적립식 질의. 금액은 `amount`(한 번 납입액, 문자열 그대로)다. */
export function toRecurringQuery(input: CryptoInput, plan: InvestmentPlan): string {
  if (input.coin === null) return "";
  return new URLSearchParams({
    coinId: String(input.coin.coinId),
    start: input.start,
    amount: input.principal,
    principalCurrency: input.principalCurrency,
    frequency: plan.frequency,
  }).toString();
}

type Setter = (partial: Partial<CryptoState>) => void;
type Getter = () => CryptoState;

/** 결과 칸을 모두 비운 상태 — 실행 시작과 방식 전환이 함께 쓴다. 매번 새 배열이다(상태 사이에 같은 배열을 나누지 않는다). */
function cleared(): Partial<CryptoState> {
  return {
    rows: [], summary: null, condition: null, exchange: null, hasMore: false,
    oldestReturned: null, series: null, seriesError: null, collecting: null, progress: null, fxBlocked: null, startable: null,
    error: null, loadMoreError: null, recurring: null,
  };
}

/** 실행이 실패한 사유를 상태로 옮긴다 — 일시금과 적립식이 같은 규칙이다(같은 오류 본문). */
function failRun(err: unknown, set: Setter): void {
  if (err instanceof ApiError && err.code === "before_listing" && err.body) {
    const { startableFrom, basis, message: text } = err.body as unknown as BeforeListingBody;
    set({ startable: { startableFrom, basis, message: text }, loading: false });
    return;
  }
  if (err instanceof ApiError && err.code === "fx_not_available_before" && err.body) {
    set({ fxBlocked: err.body as unknown as FxNotAvailableBefore, loading: false });
    return;
  }
  if (err instanceof ApiError && err.code === "unknown_coin") {
    // 이력의 코인이 지금 DB에 없다 — 할 일(다시 고르기)을 함께 말한다.
    const text = err.message.includes("다시 고르세요") ? err.message
      : `${err.message} 검색에서 다시 고르세요.`;
    set({ error: text, loading: false });
    return;
  }
  set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
}

function rerun(get: Getter): void {
  stopWatching();
  automaticRun = true;
  void get().run();
}

/** 시세 수집 진행을 구독한다. **완료에 다시 요청한다** — 부분 결과를 먼저 보여주지 않는 대신 끝난 시점을 알려야 한다. */
function watchProgress(jobId: number, set: Setter, get: Getter): void {
  unwatch?.();
  unwatch = subscribeCryptoProgress(jobId, {
    onSnapshot: (progress) => set({ progress }),
    onCompleted: () => rerun(get),
    onFailed: (kind, reason) => {
      stopWatching();
      set({ collecting: null, progress: null, error: failureText(kind, reason) });
    },
  });
}

/**
 * 환율 수집을 구독하고 **끝나면 결과를 확인한다** — 주식 화면(006 FR-046, FR-047a)과 같은 규칙을 줄였다. 끝난 작업이 실패면
 * 사유를 보이고 멈춘다. 그대로 다시 요청하면 서버가 실패한 수집을 또 시작해 같은 실패가 끝없이 반복된다.
 */
function watchFx(fx: FxCollecting, set: Setter, get: Getter): void {
  unwatchFx?.();
  let activeJobId: number | null = null;
  let idleCount = 0;
  let closed = false;

  const judge = async () => {
    let jobs: JobRow[] | null = null;
    try {
      jobs = (await apiClient.get<{ jobs: JobRow[] }>(
        `/api/fx/jobs?currency=${fx.currency}&limit=5`)).jobs;
    } catch {
      jobs = null;
    }
    if (closed) return;
    const ours = jobs?.find((j) => j.jobId === activeJobId) ?? (unjudgedRerun ? jobs?.[0] : null);
    if (ours === undefined || ours === null || ours.status === "running" || ours.status === "succeeded") {
      if (ours === undefined || ours === null) unjudgedRerun = true;
      rerun(get);
      return;
    }
    stopWatching();
    set({
      collecting: null, progress: null,
      error: `${fx.currency} 환율을 받지 못했습니다. ${ours.lastError ?? ""} 다시 실행하면 다시 받습니다.`,
    });
  };

  const unsubscribe = subscribeCollection(fx.currency, {
    onSnapshot: (snapshot) => {
      if (snapshot.activeJob !== undefined) activeJobId = snapshot.activeJob.jobId;
    },
    onIdle: (payload) => {
      if (fx.state === "waiting") {
        if (payload.busyWith === null) rerun(get);
        return;
      }
      idleCount += 1;
      if (activeJobId !== null || idleCount >= 2) void judge();
    },
    onEvent: () => undefined,
  });
  unwatchFx = () => {
    closed = true;
    unsubscribe();
  };
}

/**
 * 011 — 적립식을 실행한다. 수집 대기·오류의 처리는 일시금과 같다(같은 202 본문·같은 진행 구독). 결과는 `recurring`에만 넣는다.
 */
async function runRecurring(input: CryptoInput & { coin: CoinRef }, set: Setter, get: Getter): Promise<void> {
  const plan = get().plan;
  const query = toRecurringQuery(input, plan);
  try {
    const body = await apiClient.get<RecurringCryptoResponse | CryptoCollecting>(
      `/api/crypto/recurring-simulation?${query}${periodQuery(get().tablePeriod)}`);
    if ("status" in body && body.status === "collecting") {
      // 부분 결과를 보이지 않고 이력에도 남기지 않는다(일시금과 같다 — FR-013).
      set({ collecting: body, progress: null, loading: false });
      if (body.jobId !== undefined) watchProgress(body.jobId, set, get);
      if (body.fx !== undefined) watchFx(body.fx, set, get);
      return;
    }
    const result = body as RecurringCryptoResponse;
    set({
      recurring: {
        rows: result.rows, summary: result.summary, condition: result.condition,
        hasMore: result.hasMore, oldestReturned: result.oldestReturned, series: null, seriesError: null,
      },
    });
    await saveHistoryFlow("crypto", {
      coin: coinRef(input.coin), start: input.start, principal: input.principal,
      principalCurrency: input.principalCurrency, mode: "recurring", frequency: plan.frequency }, get, set);
    try {
      const series = await apiClient.get<SimulationSeriesResponse>(
        `/api/crypto/recurring-simulation/series?${query}`);
      const current = get().recurring;
      set({ recurring: current === null ? null : { ...current, series }, loading: false });
    } catch (err) {
      const current = get().recurring;
      set({
        recurring: current === null ? null
          : { ...current, seriesError: message(err, "차트를 불러오지 못했습니다.") },
        loading: false,
      });
    }
  } catch (err) {
    failRun(err, set);
  }
}

export const useCryptoStore = create<CryptoState>((set, get) => ({
  plan: { mode: "lump_sum", frequency: "monthly" },
  recurring: null,
  // 012 FR-016 — 처음 열 때만 1천만 원이다. 방식·통화·코인을 바꿔도 덮지 않는다.
  input: { coin: null, start: DEFAULT_START, principal: DEFAULT_PRINCIPAL, principalCurrency: "KRW" },
  startable: null,
  rows: [],
  summary: null,
  condition: null,
  exchange: null,
  hasMore: false,
  oldestReturned: null,
  series: null,
  seriesError: null,
  collecting: null,
  progress: null,
  fxBlocked: null,
  loading: false,
  loadingMore: false,
  error: null,
  loadMoreError: null,
  tablePeriod: "daily",
  tableSeq: 0,
  tableLoading: false,
  tableError: null,
  ...INITIAL_HISTORY,
  comparison: [],
  comparing: false,
  comparisonError: null,

  setInput: (next) => set({ input: { ...get().input, ...next } }),

  setPlan: (next) => {
    stopWatching();
    set({ plan: next, ...cleared(), loading: false });
  },

  selectCoin: (coin) => set({ input: { ...get().input, coin }, startable: null, error: null }),

  refreshIfRan: async () => {
    if (get().summary === null && get().recurring === null) return;
    await get().run();
  },

  /** 실행 즉시 이전 결과를 비운다 — 남으면 지금 보는 수치가 어느 조건의 것인지 알 수 없다. */
  run: async () => {
    if (!automaticRun) unjudgedRerun = false;
    automaticRun = false;
    const { input } = get();
    if (input.coin === null) {
      set({ error: "코인을 먼저 고르세요." });
      return;
    }
    if (!isAllowedPrincipal(input.principalCurrency, input.coin.currency)) {
      set({ error: `${principalRule(input.coin.currency)}. 통화를 다시 고르세요.` });
      return;
    }
    stopWatching();
    // 012 — 이전 결과의 이어 받기·단위 전환 응답이 새 결과에 섞이지 않게 차례를 올린다.
    set({ ...cleared(), loading: true, tableSeq: get().tableSeq + 1, tableLoading: false, tableError: null });
    if (get().plan.mode === "recurring") {
      await runRecurring({ ...input, coin: input.coin }, set, get);
      return;
    }
    try {
      const body = await apiClient.get<CryptoSimulationResponse | CryptoCollecting>(
        `/api/crypto/simulation?${toQuery(input)}${periodQuery(get().tablePeriod)}`);
      if ("status" in body && body.status === "collecting") {
        set({ collecting: body, progress: null, loading: false });
        if (body.jobId !== undefined) watchProgress(body.jobId, set, get);
        if (body.fx !== undefined) watchFx(body.fx, set, get);
        return;
      }
      const result = body as CryptoSimulationResponse;
      set({
        rows: result.rows, summary: result.summary, condition: result.condition,
        exchange: result.exchange ?? null, hasMore: result.hasMore,
        oldestReturned: result.oldestReturned,
      });
      // FR-045 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다.** 수집 중(202)이면 남기지 않는다 — 아직 결과가 없다.
      await saveHistoryFlow("crypto", {
        coin: coinRef(input.coin), start: input.start, principal: input.principal,
        principalCurrency: input.principalCurrency }, get, set);
      // **표가 수집 중이 아님을 확인한 뒤에 받는다** — 나란히 보내면 같은 구간에 수집 요청이 두 번 나간다(005와 같다).
      try {
        const series = await apiClient.get<SimulationSeriesResponse>(
          `/api/crypto/simulation/series?${toQuery(input)}`);
        set({ series, loading: false });
      } catch (err) {
        set({ seriesError: message(err, "차트를 불러오지 못했습니다."), loading: false });
      }
    } catch (err) {
      failRun(err, set);
    }
  },

  dispose: () => stopWatching(),

  restoreHistory: () => restoreHistoryFlow("crypto", get, set),

  toggleHistory: (id) => {
    const selected = get().selectedHistory;
    set({ selectedHistory: selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id] });
  },

  removeHistoryEntry: async (id) => {
    if (!(await removeHistoryFlow("crypto", id, get, set))) return;
    // 지운 항목의 선을 남기면 목록에 없는 조건이 차트에 남는다.
    set({ comparison: get().comparison.filter((c) => c.id !== id) });
  },

  rerunHistory: async (id) => {
    const entry = get().history.find((e) => e.id === id);
    if (entry === undefined) return;
    set({
      input: { coin: entry.coin, start: entry.start, principal: entry.principal,
        principalCurrency: entry.principalCurrency },
      // 011 — 빠진 칸은 일시금·매달이다(011 전 항목). `undefined`를 방식으로 옮기지 않는다.
      plan: { mode: entry.mode === "recurring" ? "recurring" : "lump_sum", frequency: entry.frequency ?? "monthly" },
    });
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
      const name = `${entry.coin.nameKo ?? entry.coin.name} (${entry.coin.symbol})`;
      // 011 — 적립식 항목은 적립식 시계열 경로이고, 범례 이름에 방식·주기를 붙인다(FR-034).
      const recurring = entry.mode === "recurring";
      const frequency = entry.frequency ?? "monthly";
      const label = recurring ? `${name} · 적립식 ${FREQUENCY_NAME[frequency]}` : name;
      if (!isAllowedPrincipal(entry.principalCurrency, entry.coin.currency)) {
        // 조용히 빼지 않는다 — 빼고 비교하면 그 코인이 진 것으로 읽힌다.
        failed.push(`${label}(원금 ${entry.principalCurrency} — ${principalRule(entry.coin.currency)})`);
        continue;
      }
      const condition = { coin: entry.coin, start: entry.start, principal: entry.principal,
        principalCurrency: entry.principalCurrency };
      const path = recurring
        ? `/api/crypto/recurring-simulation/series?${toRecurringQuery(condition, { mode: "recurring", frequency })}`
        : `/api/crypto/simulation/series?${toQuery(condition)}`;
      try {
        const body = await apiClient.get<SimulationSeriesResponse | CryptoCollecting>(path);
        if ("status" in body && body.status === "collecting") {
          // 부분 결과를 완성된 선처럼 겹치지 않는다.
          failed.push(`${label}(아직 받지 못한 구간이 있습니다 — 실행해서 받으세요)`);
          continue;
        }
        items.push({ id: entry.id, label, start: entry.start, series: body as SimulationSeriesResponse });
      } catch (err) {
        failed.push(err instanceof ApiError && err.code === "unknown_coin"
          ? `${label}(검색에서 다시 고르세요)` : label);
      }
    }
    set({
      comparison: items,
      comparing: false,
      comparisonError: failed.length === 0 ? null : `${failed.join(" · ")}의 시계열을 불러오지 못했습니다.`,
    });
  },

  /** 표를 이어 받는다. **기존 배열 끝에 덧붙인다** — 전체를 교체하면 보던 위치가 처음으로 튄다. */
  loadMore: async () => {
    const recurring = get().recurring;
    if (recurring !== null) {
      // 011 — 적립식 표를 이어 받는다.
      if (!recurring.hasMore || recurring.oldestReturned === null || get().loadingMore) return;
      const seq = get().tableSeq;
      set({ loadingMore: true, loadMoreError: null });
      try {
        const body = await apiClient.get<RecurringCryptoResponse>(
          `/api/crypto/recurring-simulation?${toRecurringQuery(get().input, get().plan)}&before=${recurring.oldestReturned}`
            + periodQuery(get().tablePeriod));
        if (get().tableSeq !== seq) return;  // 012 — 그 사이 단위를 바꿨거나 다시 실행했다
        const current = get().recurring;
        if (current === null) return;
        set({
          recurring: { ...current, rows: [...current.rows, ...body.rows], hasMore: body.hasMore,
            oldestReturned: body.oldestReturned },
          loadingMore: false,
        });
      } catch (err) {
        if (get().tableSeq !== seq) return;
        set({ loadingMore: false, loadMoreError: message(err, "이어서 불러오지 못했습니다.") });
      }
      return;
    }
    const { hasMore, oldestReturned, loadingMore, input, tableSeq: seq } = get();
    if (!hasMore || oldestReturned === null || loadingMore) return;
    set({ loadingMore: true, loadMoreError: null });
    try {
      const body = await apiClient.get<CryptoSimulationResponse>(
        `/api/crypto/simulation?${toQuery(input)}&before=${oldestReturned}${periodQuery(get().tablePeriod)}`);
      if (get().tableSeq !== seq) return;  // 012 — 그 사이 단위를 바꿨거나 다시 실행했다
      set({
        rows: [...get().rows, ...body.rows], hasMore: body.hasMore,
        oldestReturned: body.oldestReturned, loadingMore: false,
      });
    } catch (err) {
      if (get().tableSeq !== seq) return;
      set({ loadingMore: false, loadMoreError: message(err, "이어서 불러오지 못했습니다.") });
    }
  },

  setTablePeriod: async (period) => {
    const seq = get().tableSeq + 1;
    set({ tablePeriod: period, tableSeq: seq, tableError: null, loadingMore: false, loadMoreError: null });
    const { recurring, summary, input, plan } = get();
    if (recurring === null && summary === null) return;
    // 이전 단위의 행이 남지 않는다 — 요약·시계열은 건드리지 않는다.
    if (recurring !== null) {
      set({ recurring: { ...recurring, rows: [], hasMore: false, oldestReturned: null }, tableLoading: true });
    } else {
      set({ rows: [], hasMore: false, oldestReturned: null, tableLoading: true });
    }
    try {
      if (recurring !== null) {
        const body = await apiClient.get<RecurringCryptoResponse>(
          `/api/crypto/recurring-simulation?${toRecurringQuery(input, plan)}${periodQuery(period)}`);
        if (get().tableSeq !== seq) return;
        const current = get().recurring;
        if (current === null) return;
        set({
          recurring: { ...current, rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned },
          tableLoading: false,
        });
      } else {
        const body = await apiClient.get<CryptoSimulationResponse>(
          `/api/crypto/simulation?${toQuery(input)}${periodQuery(period)}`);
        if (get().tableSeq !== seq) return;
        set({ rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned, tableLoading: false });
      }
    } catch (err) {
      if (get().tableSeq !== seq) return;
      set({ tableLoading: false, tableError: message(err, "표를 불러오지 못했습니다.") });
    }
  },
}));
