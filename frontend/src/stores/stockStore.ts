/**
 * 주식 시뮬레이션 화면의 단일 상태 원천 (T044) — 헌법 원칙 VII.
 *
 * **결과를 저장하지 않는다.** 설정과 환율이 바뀌면 결과가 달라지므로, 들고 있으면
 * 갱신 시점을 관리해야 하고 그 관리가 틀리면 조용히 낡은 값을 보여준다
 * (research R5-9). 상태는 "지금 화면에 그릴 것"만 담는다.
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import { subscribeCollection } from "@/lib/collectionStream";
import {
  INITIAL_HISTORY,
  removeHistoryFlow,
  restoreHistoryFlow,
  saveHistoryFlow,
} from "@/lib/historyFlow";
import { isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import { createSequence } from "@/lib/searchSequence";
import { DEFAULT_PRINCIPAL } from "@/lib/principalFormat";
import { DEFAULT_START } from "@/lib/startDate";
import { periodQuery } from "@/lib/tablePeriod";
import {
  subscribeStockProgress,
  type StockProgressSnapshot,
} from "@/lib/stockProgressStream";
import type {
  BeforeListingBody,
  ExchangeInfo,
  CurrencyCode,
  FxCollecting,
  FxNotAvailableBefore,
  InvestmentPlan,
  JobRow,
  PeriodUnit,
  PrincipalCurrency,
  RecurringStockCondition,
  RecurringStockResponse,
  RecurringStockRow,
  RecurringStockSummary,
  SelectionResponse,
  SimulationCollecting,
  SimulationCondition,
  SimulationHistoryEntry,
  SimulationResponse,
  SimulationRow,
  SimulationSeriesResponse,
  SimulationSummary,
  StockChoice,
  StockSearchResult,
} from "@/lib/types";

export interface SimulationInput {
  stock: StockSearchResult | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
}

/**
 * 011 — 적립식 결과. 일시금 칸과 **따로 둔다** — 한 번에 한쪽만 채운다(research R11-11). 일시금 칸의 모양(행·요약)은 기존 테스트가
 * 고정한다.
 */
export interface RecurringResult {
  rows: RecurringStockRow[];
  summary: RecurringStockSummary;
  condition: RecurringStockCondition;
  hasMore: boolean;
  oldestReturned: string | null;
  series: SimulationSeriesResponse | null;
  seriesError: string | null;
}

/** 이력 범례의 주기 이름(011). */
const FREQUENCY_NAME = { daily: "매일", weekly: "매주", monthly: "매달", yearly: "매년" } as const;

interface StockState {
  input: SimulationInput;
  /**
   * 011 — 투자 방식(일시금·적립식)과 주기. `input`(일시금 다섯 칸)과 따로 둔다 — `stockStoreRerun.test.ts`가 `input`의 모양을
   * 정확히 고정한다. 적립식이면 `input.principal`이 한 번 납입액이다.
   */
  plan: InvestmentPlan;
  /** 011 — 적립식 결과. 일시금이면 `null`이다. */
  recurring: RecurringResult | null;
  /**
   * 고른 종목을 등록하는 중 (006 FR-030b). 이 동안 `input.stock`은 비어 있다 —
   * 이전 종목이 남으면 등록이 끝나기 전에 누른 실행이 이전 종목으로 나간다.
   */
  selecting: boolean;
  /** 등록 실패 사유. **실행 전에** 보인다 — 실행하고 나서야 알면 원인이 "종목이 없다"로 보인다. */
  selectionError: string | null;
  /** 등록 응답의 상장일. 시작 가능 날짜가 아니라 하한이다 (006 FR-005a). */
  listedOn: string | null;
  /**
   * 실행 뒤 서버가 알려 준 시작 가능 날짜 (006 FR-005, W1a). 일반 오류와 따로 둔다 — 그 날짜로
   * 옮기는 수단을 그려야 한다. **시작일은 바꾸지 않는다.**
   */
  startable: Pick<BeforeListingBody, "startableFrom" | "basis" | "message"> | null;
  rows: SimulationRow[];
  summary: SimulationSummary | null;
  condition: SimulationCondition | null;
  exchange: ExchangeInfo | null;
  hasMore: boolean;
  oldestReturned: string | null;
  /** 차트용 전 구간 시계열 (FR-033). 표와 **같은 조건**으로 따로 받는다. */
  series: SimulationSeriesResponse | null;
  /**
   * 차트만 실패했을 때의 사유.
   *
   * **표를 지우지 않는다.** 차트가 비는 것과 결과가 없는 것은 다른 사건인데,
   * 한 덩어리로 다루면 멀쩡한 표까지 사라져 사용자는 조건이 틀렸다고 읽는다.
   */
  seriesError: string | null;
  collecting: SimulationCollecting | null;
  /**
   * 필요한 환율이 수집으로 채울 수 없는 구간이다 (006 FR-043a, W4a). 일반 오류와 따로 둔다 —
   * 사유에 따라 "그 달로 옮기기"를 그려야 한다.
   */
  fxBlocked: FxNotAvailableBefore | null;
  /** 수집 진행 (FR-047). 스냅샷이 오기 전에는 `null`이다 — 0/0은 멈춘 것처럼 보인다. */
  progress: StockProgressSnapshot | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;

  /**
   * 012 — 일자별 표의 단위(처음 일). 다시 실행해도 남고, 새로 고치면 처음 값이다(외환의 단위와 같다). 일이면 요청에 `period`를 싣지 않는다 — 기본
   * 단위의 요청 문자열이 지금과 같다.
   */
  tablePeriod: PeriodUnit;
  /**
   * 표 요청의 차례 번호. 실행·단위 전환마다 올린다 — 응답이 왔을 때 번호가 다르면 버린다(이어 받기 포함). 단위 비교만으로는 일 → 주 → 일 전환의
   * 첫 "일" 응답을 거르지 못한다(012 FR-006).
   */
  tableSeq: number;
  /** 단위를 바꿔 표를 다시 받는 중 — 표 자리에 "불러오는 중"을 보인다. 보드·차트는 그대로다(FR-007). */
  tableLoading: boolean;
  /** 단위를 바꿨는데 표를 받지 못했다. 고른 단위는 남는다. */
  tableError: string | null;

  /** 이력 (FR-035). **조건만 담긴다** — 결과는 설정·환율이 바뀌면 달라진다. 012부터 로컬 DB에 있다(`lib/historyFlow`). */
  history: SimulationHistoryEntry[];
  historyLoading: boolean;
  historyLoadError: string | null;
  historySaveError: string | null;
  historyNotice: string | null;
  retentionDays: number | null | undefined;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;

  setInput: (next: Partial<SimulationInput>) => void;
  /** 011 — 투자 방식·주기를 바꾼다. **두 결과를 모두 비운다** — 한쪽 결과가 다른 방식의 조건과 함께 보이지 않게(008 D2와 같은 이유). */
  setPlan: (next: InvestmentPlan) => void;
  /**
   * 검색에서 고른 것을 등록하고, **등록 응답의 식별**을 입력에 쓴다 (006 FR-030b).
   *
   * 미국 종목은 목록과 005의 거래소가 다를 수 있어(FR-030a) 검색 결과의 식별을 그대로
   * 쓰면 같은 종목이 둘이 된다. 이후 시뮬레이션·이력은 이 식별을 쓴다.
   */
  selectStock: (choice: StockChoice) => Promise<void>;
  run: () => Promise<void>;
  loadMore: () => Promise<void>;
  /**
   * 012 — 일자별 표의 단위를 바꾼다. **표의 행만** 비우고 지금 결과(일시금 또는 적립식)의 표 첫 쪽을 다시 받는다 — 요약·시계열은 같은 객체로 남는다
   * (FR-007 — 보드가 표를 따라가지 않는다). 아직 결과가 없으면 단위만 바꾼다.
   */
  setTablePeriod: (period: PeriodUnit) => Promise<void>;
  /**
   * 설정이 바뀐 뒤 결과를 다시 받는다 (FR-017).
   *
   * 아직 실행한 적이 없으면 아무것도 하지 않는다 — 설정 화면에 들렀다는 이유로
   * 시뮬레이션이 시작되면 사용자가 요청하지 않은 출처 호출이 나간다.
   */
  refreshIfRan: () => Promise<void>;
  /**
   * 화면을 떠날 때 부른다. 진행 구독을 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다
   * (006 research R6-10 "다시 요청하는 쪽은 화면이다").
   */
  dispose: () => void;
  /** 012 — 옛 브라우저 이력을 옮긴 뒤 목록을 받는다. 다시 시도도 이것이다(FR-014a). */
  restoreHistory: () => Promise<void>;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => Promise<void>;
  compareSelected: () => Promise<void>;
  /**
   * 이력 항목의 조건을 입력에 넣고 곧바로 실행한다(010 FR-018~FR-020) — 가상자산·예금·부동산과 같은 동작. 등록 요청은 보내지 않는다:
   * 등록 경로는 목록 id나 일본 외부 결과만 받고 이력 항목에는 목록 id가 없다(research R10-11). 이력의 종목은 이미 실행한(= 등록된)
   * 종목이다.
   */
  rerunHistory: (id: string) => Promise<void>;
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

/**
 * 등록 요청 번호. 늦게 온 이전 등록 응답이 나중에 고른 종목을 덮으면, 사용자가 고른
 * 것과 다른 종목으로 실행된다 (006 FR-029a와 같은 계열).
 */
const selectionSeq = createSequence();

function selectionBody(choice: StockChoice): Record<string, unknown> {
  if (choice.source === "listing") {
    return { source: "listing", listingId: choice.listingId };
  }
  const { market, symbol, name, currency } = choice.result;
  return { source: "external", market, symbol, name, currency };
}

/**
 * 진행 구독 해제 함수. 모듈 수준에 두는 이유는 상태가 아니기 때문이다 — 화면에
 * 그릴 것이 아니라 정리해야 할 자원이다.
 */
let unwatch: (() => void) | null = null;
/** 환율 수집 구독 해제 함수 (006). 주식 진행과 따로 산다 — 둘 다 끝나야 결과가 나온다. */
let unwatchFx: (() => void) | null = null;
/** 화면이 스스로 다시 요청할 때 켠다. `run`이 읽고 끈다 — 사용자의 실행과 구별한다. */
let automaticRun = false;
/** 끝난 작업을 판정하지 못한 채 다시 요청한 적이 있는지. 사용자가 실행하면 지운다 (FR-047a). */
let unjudgedRerun = false;

function stopWatching(): void {
  unwatch?.();
  unwatch = null;
  unwatchFx?.();
  unwatchFx = null;
}

/**
 * 그 통화의 최근 수집 작업(최신이 먼저). 조회하지 못하면 `null`이다 — "작업이 없다"(빈 배열)와
 * 구별한다.
 */
async function recentFxJobs(currency: CurrencyCode): Promise<JobRow[] | null> {
  try {
    const body = await apiClient.get<{ jobs: JobRow[] }>(
      `/api/fx/jobs?currency=${currency}&limit=5`,
    );
    return body.jobs;
  } catch {
    return null;
  }
}

/**
 * 환율 수집을 구독하고 **끝나면 결과를 확인한다** (006 FR-046, FR-047a, research R6-10).
 *
 * 003의 통화별 스트림은 진행 중이면 `snapshot`, 아니면 5초마다 `idle`을 보낸다.
 *
 * - `waiting`: 다른 통화가 끝나면(`idle`의 `busyWith`가 비면) 다시 요청한다
 * - `queued`·`collecting`: 진행을 본 뒤 `idle`이 오면 끝난 것이다. 진행을 한 번도 못 보고
 *   `idle`이 두 번 오면 구독이 붙기 전에 끝났다고 본다 — 진행을 못 봤다고 영원히 기다리면
 *   화면이 "받고 있습니다"에 머문다. 한 번의 `idle`로 판단하지 않는 이유는 워커가 큐에서
 *   꺼내기 직전일 수 있어서다
 *
 * **`idle`은 끝났다는 것만 알리고 성공인지 알리지 않는다.** 끝나면 작업을 조회해 실패·부분
 * 성공이면 사유를 보이고 멈춘다. 그대로 다시 요청하면 서버가 실패한 수집을 또 시작하고,
 * 고쳐지지 않은 원인으로 같은 실패가 끝없이 반복된다(T090에서 실제로 쌓였다).
 *
 * 이번 수집의 작업은 진행에서 본 작업, 아니면 구독할 때의 마지막 작업보다 새 작업이다. 그것을
 * 찾지 못하면 다시 요청해 서버가 판정하게 한다 — 다만 **사용자 실행 한 번에 한 번만** 그렇게
 * 한다. 출처가 곧바로 거절하면 작업이 구독보다 먼저 끝나 기준 자체가 되기 때문이다. 두 번째에는
 * 마지막 작업을 이번 수집으로 본다.
 */
function watchFx(
  fx: FxCollecting,
  set: (partial: Partial<StockState>) => void,
  get: () => StockState,
): void {
  unwatchFx?.();
  let closed = false;
  let activeJobId: number | null = null;
  let idleCount = 0;
  let judging = false;
  // 구독할 때의 마지막 작업 번호. 조회하지 못하면 `undefined` — 새 작업을 가를 수 없다.
  const baseline: Promise<number | null | undefined> = fx.state === "waiting"
    ? Promise.resolve(undefined)
    : recentFxJobs(fx.currency).then((jobs) =>
      jobs === null ? undefined : (jobs[0]?.jobId ?? null));

  const rerun = () => {
    stopWatching();
    automaticRun = true;
    void get().run();
  };

  const judge = async () => {
    if (judging) return;
    judging = true;
    const [jobs, base] = await Promise.all([recentFxJobs(fx.currency), baseline]);
    judging = false;
    if (closed) return;
    const latest = jobs?.[0] ?? null;
    let ours: JobRow | null = null;
    if (jobs !== null && activeJobId !== null) {
      ours = jobs.find((job) => job.jobId === activeJobId) ?? null;
    } else if (latest !== null && base !== undefined && latest.jobId > (base ?? 0)) {
      ours = latest;
    } else if (latest !== null && unjudgedRerun) {
      ours = latest;
    }
    if (ours === null || ours.status === "running") {
      // 이번 작업을 찾지 못했다. 서버가 다시 판정한다 — 아직 비었으면 다시 202를 준다.
      if (activeJobId === null) unjudgedRerun = true;
      rerun();
      return;
    }
    if (ours.status === "succeeded") {
      rerun();
      return;
    }
    stopWatching();
    set({
      collecting: null,
      progress: null,
      error: `${fx.currency} 환율을 받지 못했습니다. `
        + `${ours.lastError ?? "출처가 사유를 알려주지 않았습니다."} 다시 실행하면 다시 받습니다.`,
    });
  };

  const unsubscribe = subscribeCollection(fx.currency, {
    onSnapshot: (snapshot) => {
      if (snapshot.activeJob !== undefined) activeJobId = snapshot.activeJob.jobId;
    },
    onIdle: (payload) => {
      if (fx.state === "waiting") {
        if (payload.busyWith === null) rerun();
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
 * 수집 진행을 구독한다.
 *
 * **완료 신호에 결과를 다시 요청한다.** 부분 결과를 먼저 보여주지 않는 대신
 * (FR-049) 끝난 시점을 알려야 한다 — 알리지 않으면 사용자가 새로고침할 때까지
 * 화면은 "받고 있습니다"에 머문다.
 */
function watchProgress(
  jobId: number,
  set: (partial: Partial<StockState>) => void,
  get: () => StockState,
): void {
  // 주식 진행만 갈아끼운다 — 환율 구독은 따로 산다.
  unwatch?.();
  unwatch = subscribeStockProgress(jobId, {
    onSnapshot: (progress) => set({ progress }),
    onCompleted: () => {
      stopWatching();
      void get().run();
    },
    onFailed: (reason) => {
      stopWatching();
      // 조용히 멈추면 사용자는 영원히 "받고 있습니다"를 본다.
      set({ collecting: null, progress: null, error: reason });
    },
  });
}

/**
 * 011 — 적립식을 실행한다. 수집 대기·오류의 처리는 일시금과 같다(같은 202 본문·같은 진행 구독). 결과는 `recurring`에만 넣는다.
 */
async function runRecurring(
  input: SimulationInput,
  set: (partial: Partial<StockState>) => void,
  get: () => StockState,
): Promise<void> {
  const plan = get().plan;
  const query = toRecurringQuery(input, plan);
  try {
    const body = await apiClient.get<RecurringStockResponse | SimulationCollecting>(
      `/api/stocks/recurring-simulation?${query}${periodQuery(get().tablePeriod)}`,
    );
    if ("status" in body && body.status === "collecting") {
      // 부분 결과를 보이지 않고 이력에도 남기지 않는다(일시금과 같다 — FR-016).
      set({ collecting: body, progress: null, loading: false });
      if (body.jobId !== undefined) watchProgress(body.jobId, set, get);
      if (body.fx !== undefined) watchFx(body.fx, set, get);
      return;
    }
    const result = body as RecurringStockResponse;
    set({
      recurring: {
        rows: result.rows, summary: result.summary, condition: result.condition,
        hasMore: result.hasMore, oldestReturned: result.oldestReturned, series: null, seriesError: null,
      },
    });
    if (input.stock !== null) {
      await saveHistoryFlow("stock", {
        stock: input.stock, start: input.start, principal: input.principal,
        principalCurrency: input.principalCurrency, reinvest: input.reinvest,
        mode: "recurring", frequency: plan.frequency,
      }, get, set);
    }
    try {
      const series = await apiClient.get<SimulationSeriesResponse>(
        `/api/stocks/recurring-simulation/series?${query}`,
      );
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
    if (err instanceof ApiError && err.code === "before_listing" && err.body) {
      const { startableFrom, basis, message: text } = err.body as unknown as BeforeListingBody;
      set({ startable: { startableFrom, basis, message: text }, loading: false });
      return;
    }
    if (err instanceof ApiError && err.code === "fx_not_available_before" && err.body) {
      set({ fxBlocked: err.body as unknown as FxNotAvailableBefore, loading: false });
      return;
    }
    set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
  }
}

/** 조건을 질의 문자열로. 원금은 **문자열 그대로** 보낸다 (헌법 원칙 VI). */
export function toQuery(input: {
  stock: StockSearchResult | null;
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
}): string {
  const stock = input.stock;
  if (stock === null) return "";
  const params = new URLSearchParams({
    market: stock.market,
    symbol: stock.symbol,
    start: input.start,
    principal: input.principal,
    principalCurrency: input.principalCurrency,
    reinvest: String(input.reinvest),
  });
  return params.toString();
}

/** 011 — 적립식 질의. 금액은 `amount`(한 번 납입액, 문자열 그대로)다. */
export function toRecurringQuery(input: SimulationInput, plan: InvestmentPlan): string {
  const stock = input.stock;
  if (stock === null) return "";
  return new URLSearchParams({
    market: stock.market,
    symbol: stock.symbol,
    start: input.start,
    amount: input.principal,
    principalCurrency: input.principalCurrency,
    frequency: plan.frequency,
    reinvest: String(input.reinvest),
  }).toString();
}

/** 결과 칸을 모두 비운 상태 — 실행 시작과 방식 전환이 함께 쓴다. 매번 새 배열이다(상태 사이에 같은 배열을 나누지 않는다). */
function cleared(): Partial<StockState> {
  return {
    rows: [], summary: null, condition: null, exchange: null,
    hasMore: false, oldestReturned: null, series: null, seriesError: null,
    collecting: null, fxBlocked: null, startable: null, progress: null,
    error: null, loadMoreError: null, recurring: null,
  };
}

export const useStockStore = create<StockState>((set, get) => ({
  plan: { mode: "lump_sum", frequency: "monthly" },
  recurring: null,
  input: {
    stock: null,
    // FR-001 — 처음 들어오면 2020-01-01. 종목을 바꿔도 덮지 않는다(FR-006).
    start: DEFAULT_START,
    // 012 FR-016 — 처음 열 때만 1천만 원이다. 방식·통화를 바꿔도 덮지 않는다.
    principal: DEFAULT_PRINCIPAL,
    principalCurrency: "KRW",
    reinvest: true,
  },
  selecting: false,
  selectionError: null,
  listedOn: null,
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
  fxBlocked: null,
  progress: null,
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

  selectStock: async (choice) => {
    const id = selectionSeq.next();
    // 시작일은 건드리지 않는다(FR-006). 이전 종목의 시작 가능 날짜는 이 종목의 것이 아니다.
    set({
      input: { ...get().input, stock: null },
      selecting: true,
      selectionError: null,
      listedOn: null,
      startable: null,
    });
    try {
      const body = await apiClient.post<SelectionResponse>(
        "/api/stocks/selection", selectionBody(choice));
      if (!selectionSeq.isLatest(id)) return;
      const { market, symbol, name, currency, listedOn } = body;
      set({
        input: { ...get().input, stock: { market, symbol, name, currency } },
        selecting: false,
        listedOn,
      });
    } catch (err) {
      if (!selectionSeq.isLatest(id)) return;
      set({
        selecting: false,
        selectionError: message(err, "고른 종목을 등록하지 못했습니다. 다시 고르세요."),
      });
    }
  },

  refreshIfRan: async () => {
    if (get().summary === null && get().recurring === null) return;
    await get().run();
  },

  /**
   * 시뮬레이션을 실행한다.
   *
   * **실행 즉시 이전 결과를 비운다.** 새 조건의 응답이 도착할 때까지 이전 결과가
   * 남으면 사용자가 지금 보는 수치가 어느 조건의 것인지 알 수 없다
   * (002 FR-036c·003 FR-028·004 FR-010과 같은 계열).
   */
  run: async () => {
    // 사용자가 실행하면 판정 없이 다시 요청한 기록을 지운다 (FR-047a).
    if (!automaticRun) unjudgedRerun = false;
    automaticRun = false;
    const { input } = get();
    const query = toQuery(input);
    if (input.stock === null || query === "") {
      set({ error: "종목을 먼저 고르세요." });
      return;
    }
    if (!isAllowedPrincipal(input.principalCurrency, input.stock.currency)) {
      // 006 FR-050 — 거절당할 요청을 보내지 않는다. 서버도 같은 규칙으로 막는다.
      set({ error: `${principalRule(input.stock.currency)}. 통화를 다시 고르세요.` });
      return;
    }
    // 이전 실행의 구독을 끊는다. 남기면 이전 조건의 완료 신호가 새 조건을 다시 요청한다.
    stopWatching();
    // 012 — 이전 결과의 이어 받기·단위 전환 응답이 새 결과에 섞이지 않게 차례를 올린다.
    set({ ...cleared(), loading: true, tableSeq: get().tableSeq + 1, tableLoading: false, tableError: null });
    if (get().plan.mode === "recurring") {
      await runRecurring(input, set, get);
      return;
    }
    try {
      const body = await apiClient.get<SimulationResponse | SimulationCollecting>(
        `/api/stocks/simulation?${query}${periodQuery(get().tablePeriod)}`,
      );
      if ("status" in body && body.status === "collecting") {
        // FR-049 — 부분 결과를 완성된 결과처럼 보여주지 않는다.
        //
        // **이력에도 남기지 않는다.** 아직 결과가 없는 조건이다.
        set({ collecting: body, progress: null, loading: false });
        // 006 — 주식 시세와 환율을 따로 기다린다. 어느 쪽이 끝나도 다시 요청하고, 서버가
        // 둘 다 끝났는지 판정한다(FR-045).
        if (body.jobId !== undefined) watchProgress(body.jobId, set, get);
        if (body.fx !== undefined) watchFx(body.fx, set, get);
        return;
      }
      const result = body as SimulationResponse;
      set({
        rows: result.rows,
        summary: result.summary,
        condition: result.condition,
        exchange: result.exchange ?? null,
        hasMore: result.hasMore,
        oldestReturned: result.oldestReturned,
      });

      // FR-035 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다**(R5-9). 저장이 실패해도 결과는 그대로다(012 FR-014).
      await saveHistoryFlow("stock", {
        stock: input.stock,
        start: input.start,
        principal: input.principal,
        principalCurrency: input.principalCurrency,
        reinvest: input.reinvest,
      }, get, set);

      // **표가 수집 중이 아님을 확인한 뒤에 받는다.** 나란히 보내면 같은 구간에
      // 수집 요청이 두 번 나가고, 둘 다 작업을 만들려 해 하나는 점유에 걸린다.
      try {
        const series = await apiClient.get<SimulationSeriesResponse>(
          `/api/stocks/simulation/series?${query}`,
        );
        set({ series, loading: false });
      } catch (err) {
        set({
          seriesError: message(err, "차트를 불러오지 못했습니다."),
          loading: false,
        });
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "before_listing" && err.body) {
        // W1a — 같은 모양으로 그 날짜와 옮기기를 보인다. 시작일을 몰래 옮기지 않는다.
        const { startableFrom, basis, message: text } =
          err.body as unknown as BeforeListingBody;
        set({ startable: { startableFrom, basis, message: text }, loading: false });
        return;
      }
      if (err instanceof ApiError && err.code === "fx_not_available_before" && err.body) {
        // W4a — 같은 사유를 일반 오류로 한 번 더 말하지 않는다.
        set({ fxBlocked: err.body as unknown as FxNotAvailableBefore, loading: false });
        return;
      }
      set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
    }
  },

  dispose: () => stopWatching(),

  /**
   * 표를 이어 받는다 (FR-029). **기존 배열 끝에 덧붙인다** — 전체를 교체하면
   * 보던 위치가 처음으로 튄다 (004 research R4-6).
   */
  loadMore: async () => {
    const recurring = get().recurring;
    if (recurring !== null) {
      // 011 — 적립식 표를 이어 받는다(같은 날의 행은 서버가 가르지 않는다).
      if (!recurring.hasMore || recurring.oldestReturned === null || get().loadingMore) return;
      const seq = get().tableSeq;
      set({ loadingMore: true, loadMoreError: null });
      try {
        const body = await apiClient.get<RecurringStockResponse>(
          `/api/stocks/recurring-simulation?${toRecurringQuery(get().input, get().plan)}&before=${recurring.oldestReturned}`
            + periodQuery(get().tablePeriod),
        );
        // 012 — 그 사이 단위를 바꿨거나 다시 실행했으면 이전 표의 쪽이다. 붙이지 않는다.
        if (get().tableSeq !== seq) return;
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
      const body = await apiClient.get<SimulationResponse>(
        `/api/stocks/simulation?${toQuery(input)}&before=${oldestReturned}${periodQuery(get().tablePeriod)}`,
      );
      // 012 — 그 사이 단위를 바꿨거나 다시 실행했으면 이전 표의 쪽이다. 붙이지 않는다.
      if (get().tableSeq !== seq) return;
      set({
        rows: [...get().rows, ...body.rows],
        hasMore: body.hasMore,
        oldestReturned: body.oldestReturned,
        loadingMore: false,
      });
    } catch (err) {
      if (get().tableSeq !== seq) return;
      // 이미 표시된 행은 그대로 둔다 (FR-004와 같은 계열). 조용히 멈추면 사용자는
      // 데이터가 거기서 끝난 것으로 오해한다.
      set({
        loadingMore: false,
        loadMoreError: message(err, "이어서 불러오지 못했습니다."),
      });
    }
  },

  setTablePeriod: async (period) => {
    const seq = get().tableSeq + 1;
    set({ tablePeriod: period, tableSeq: seq, tableError: null, loadingMore: false, loadMoreError: null });
    const { recurring, summary, input, plan } = get();
    if (recurring === null && summary === null) return;
    // 이전 단위의 행이 남지 않는다(004 FR-010과 같다) — 요약·시계열은 건드리지 않는다.
    if (recurring !== null) {
      set({ recurring: { ...recurring, rows: [], hasMore: false, oldestReturned: null }, tableLoading: true });
    } else {
      set({ rows: [], hasMore: false, oldestReturned: null, tableLoading: true });
    }
    try {
      if (recurring !== null) {
        const body = await apiClient.get<RecurringStockResponse>(
          `/api/stocks/recurring-simulation?${toRecurringQuery(input, plan)}${periodQuery(period)}`);
        if (get().tableSeq !== seq) return;
        const current = get().recurring;
        if (current === null) return;
        set({
          recurring: { ...current, rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned },
          tableLoading: false,
        });
      } else {
        const body = await apiClient.get<SimulationResponse>(
          `/api/stocks/simulation?${toQuery(input)}${periodQuery(period)}`);
        if (get().tableSeq !== seq) return;
        set({ rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned, tableLoading: false });
      }
    } catch (err) {
      if (get().tableSeq !== seq) return;
      set({ tableLoading: false, tableError: message(err, "표를 불러오지 못했습니다.") });
    }
  },

  /** 이력을 받는다 — 첫 화면 진입에 한 번, 불러오기 실패 뒤 다시 시도에 부른다 (FR-037, 012 FR-013·FR-014a). */
  restoreHistory: () => restoreHistoryFlow("stock", get, set),

  toggleHistory: (id) => {
    const selected = get().selectedHistory;
    set({
      selectedHistory: selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    });
  },

  removeHistoryEntry: async (id) => {
    if (!(await removeHistoryFlow("stock", id, get, set))) return;
    // 지운 항목이 비교에 올라가 있었으면 함께 내린다 — 남겨 두면 목록에 없는
    // 선이 차트에 남아 사용자가 어느 조건인지 확인할 길이 없다.
    set({ comparison: get().comparison.filter((c) => c.id !== id) });
  },

  /**
   * 고른 이력을 **지금 다시 계산해서** 겹친다 (FR-038).
   *
   * 저장된 결과를 쓰지 않는 이유는 R5-9와 같다 — 설정과 환율이 바뀌면 달라지는데,
   * 저장된 값을 겹치면 어느 시점의 조건에서 나온 선인지 알 수 없다.
   */
  rerunHistory: async (id) => {
    const entry = get().history.find((e) => e.id === id);
    if (entry === undefined) return;
    // 진행 중인 등록이 끝나며 입력의 종목을 덮지 않게 한다 — 그러면 다른 종목의 결과가 이 항목의 결과처럼 보인다.
    selectionSeq.invalidate();
    // 조건 하나라도 빠지면(재투자·원금 통화) 다른 조건의 결과가 그 항목의 결과처럼 보인다(FR-018 실패 양상). 고른 종목에 딸린
    // 상태(상장일 안내·시작 가능 날짜·선택 오류)는 이 종목의 것이 아니다. 막힌 조합은 `run()`이 지금 규칙으로 거절한다(FR-019).
    set({
      input: {
        stock: entry.stock, start: entry.start, principal: entry.principal,
        principalCurrency: entry.principalCurrency, reinvest: entry.reinvest,
      },
      // 011 — 빠진 칸은 일시금·매달이다(011 전 항목). `undefined`를 방식으로 옮기지 않는다.
      plan: { mode: entry.mode === "recurring" ? "recurring" : "lump_sum", frequency: entry.frequency ?? "monthly" },
      selecting: false, listedOn: null, startable: null, selectionError: null,
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
      if (!isAllowedPrincipal(entry.principalCurrency, entry.stock.currency)) {
        // 006 FR-050c — 조용히 빼지 않는다. 빼고 비교하면 그 종목이 진 것으로 읽힌다.
        failed.push(`${entry.stock.name}(원금 ${entry.principalCurrency} — `
          + `${principalRule(entry.stock.currency)})`);
        continue;
      }
      const condition = {
        stock: entry.stock,
        start: entry.start,
        principal: entry.principal,
        principalCurrency: entry.principalCurrency,
        reinvest: entry.reinvest,
      };
      // 011 — 적립식 항목은 적립식 시계열 경로이고, 범례 이름에 방식·주기를 붙인다(FR-034).
      const recurring = entry.mode === "recurring";
      const frequency = entry.frequency ?? "monthly";
      const path = recurring
        ? `/api/stocks/recurring-simulation/series?${toRecurringQuery(condition, { mode: "recurring", frequency })}`
        : `/api/stocks/simulation/series?${toQuery(condition)}`;
      const label = recurring ? `${entry.stock.name} · 적립식 ${FREQUENCY_NAME[frequency]}` : entry.stock.name;
      try {
        const body = await apiClient.get<SimulationSeriesResponse | SimulationCollecting>(path);
        if ("status" in body && body.status === "collecting") {
          // FR-049 — 부분 결과를 완성된 선처럼 겹치지 않는다.
          failed.push(entry.stock.name);
          continue;
        }
        items.push({
          id: entry.id,
          label,
          start: entry.start,
          series: body as SimulationSeriesResponse,
        });
      } catch {
        failed.push(entry.stock.name);
      }
    }

    set({
      comparison: items,
      comparing: false,
      // 조용히 빠지면 사용자는 그 종목이 비교에서 졌다고 읽는다.
      comparisonError: failed.length === 0
        ? null
        : `${failed.join(" · ")}의 시계열을 불러오지 못했습니다.`,
    });
  },
}));
