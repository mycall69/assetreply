/**
 * 가상자산 시뮬레이션 화면의 단일 상태 원천 (T033) — 007 FR-013, FR-020, FR-008, 헌법 원칙 VII.
 *
 * 주식 화면(`stockStore`)을 본뜬다. **결과를 저장하지 않는다** — 설정과 환율이 바뀌면 결과가 달라진다(005 R5-9). 상태는 "지금
 * 화면에 그릴 것"만 담는다.
 *
 * - **부분 결과를 보여주지 않는다**(FR-013). 202면 결과를 비우고 진행을 구독하고, 끝나면 다시 요청한다
 * - 수집이 실패하면 **종류마다 다른 말**로 사유를 보인다(FR-020)
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeCollection } from "@/lib/collectionStream";
import { subscribeCryptoProgress, type CryptoProgressSnapshot } from "@/lib/cryptoProgressStream";
import { isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import { DEFAULT_START } from "@/lib/startDate";
import type {
  BeforeListingBody,
  CoinSearchResult,
  CryptoCollecting,
  CryptoCondition,
  CryptoFailureKind,
  CryptoRow,
  CryptoSimulationResponse,
  CryptoSummary,
  ExchangeInfo,
  FxCollecting,
  FxNotAvailableBefore,
  JobRow,
  PrincipalCurrency,
} from "@/lib/types";

export interface CryptoInput {
  coin: CoinSearchResult | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
}

interface CryptoState {
  input: CryptoInput;
  /** 실행 뒤 서버가 알려 준 시작 가능 날짜(FR-008). 시작일은 바꾸지 않는다 — 옮기기는 눌러야 일어난다. */
  startable: Pick<BeforeListingBody, "startableFrom" | "basis" | "message"> | null;
  rows: CryptoRow[];
  summary: CryptoSummary | null;
  condition: CryptoCondition | null;
  exchange: ExchangeInfo | null;
  hasMore: boolean;
  oldestReturned: string | null;
  collecting: CryptoCollecting | null;
  /** 수집 진행. 스냅샷이 오기 전에는 `null`이다 — 0/0은 멈춘 것처럼 보인다. */
  progress: CryptoProgressSnapshot | null;
  fxBlocked: FxNotAvailableBefore | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;

  setInput: (next: Partial<CryptoInput>) => void;
  /** 검색에서 고른 코인. 시작일·원금은 그대로 둔다 — 같은 조건으로 두 코인을 비교하려던 사용자 몰래 바꾸지 않는다. */
  selectCoin: (coin: CoinSearchResult) => void;
  run: () => Promise<void>;
  loadMore: () => Promise<void>;
  /** 설정이 바뀐 뒤 결과를 다시 받는다(FR-033). 실행한 적이 없으면 아무것도 하지 않는다. */
  refreshIfRan: () => Promise<void>;
  /** 화면을 떠날 때 진행 구독을 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다. */
  dispose: () => void;
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

type Setter = (partial: Partial<CryptoState>) => void;
type Getter = () => CryptoState;

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

export const useCryptoStore = create<CryptoState>((set, get) => ({
  input: { coin: null, start: DEFAULT_START, principal: "", principalCurrency: "KRW" },
  startable: null,
  rows: [],
  summary: null,
  condition: null,
  exchange: null,
  hasMore: false,
  oldestReturned: null,
  collecting: null,
  progress: null,
  fxBlocked: null,
  loading: false,
  loadingMore: false,
  error: null,
  loadMoreError: null,

  setInput: (next) => set({ input: { ...get().input, ...next } }),

  selectCoin: (coin) => set({ input: { ...get().input, coin }, startable: null, error: null }),

  refreshIfRan: async () => {
    if (get().summary === null) return;
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
    set({
      rows: [], summary: null, condition: null, exchange: null, hasMore: false,
      oldestReturned: null, collecting: null, progress: null, fxBlocked: null, startable: null,
      loading: true, error: null, loadMoreError: null,
    });
    try {
      const body = await apiClient.get<CryptoSimulationResponse | CryptoCollecting>(
        `/api/crypto/simulation?${toQuery(input)}`);
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
        oldestReturned: result.oldestReturned, loading: false,
      });
    } catch (err) {
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
  },

  dispose: () => stopWatching(),

  /** 표를 이어 받는다. **기존 배열 끝에 덧붙인다** — 전체를 교체하면 보던 위치가 처음으로 튄다. */
  loadMore: async () => {
    const { hasMore, oldestReturned, loadingMore, input } = get();
    if (!hasMore || oldestReturned === null || loadingMore) return;
    set({ loadingMore: true, loadMoreError: null });
    try {
      const body = await apiClient.get<CryptoSimulationResponse>(
        `/api/crypto/simulation?${toQuery(input)}&before=${oldestReturned}`);
      set({
        rows: [...get().rows, ...body.rows], hasMore: body.hasMore,
        oldestReturned: body.oldestReturned, loadingMore: false,
      });
    } catch (err) {
      set({ loadingMore: false, loadMoreError: message(err, "이어서 불러오지 못했습니다.") });
    }
  },
}));
