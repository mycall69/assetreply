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
import {
  loadHistory,
  removeHistory,
  saveHistory,
} from "@/lib/simulationHistory";
import { subscribeCollection } from "@/lib/collectionStream";
import { createSequence } from "@/lib/searchSequence";
import {
  subscribeStockProgress,
  type StockProgressSnapshot,
} from "@/lib/stockProgressStream";
import type {
  ExchangeInfo,
  FxCollecting,
  FxNotAvailableBefore,
  PrincipalCurrency,
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

interface StockState {
  input: SimulationInput;
  /**
   * 고른 종목을 등록하는 중 (006 FR-030b). 이 동안 `input.stock`은 비어 있다 —
   * 이전 종목이 남으면 등록이 끝나기 전에 누른 실행이 이전 종목으로 나간다.
   */
  selecting: boolean;
  /** 등록 실패 사유. **실행 전에** 보인다 — 실행하고 나서야 알면 원인이 "종목이 없다"로 보인다. */
  selectionError: string | null;
  /** 등록 응답의 상장일. 시작 가능 날짜가 아니라 하한이다 (006 FR-005a). */
  listedOn: string | null;
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

  /** 이력 (FR-035). **조건만 담긴다** — 결과는 설정·환율이 바뀌면 달라진다. */
  history: SimulationHistoryEntry[];
  historySaveError: string | null;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;

  setInput: (next: Partial<SimulationInput>) => void;
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
  restoreHistory: () => void;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => void;
  compareSelected: () => Promise<void>;
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

function stopWatching(): void {
  unwatch?.();
  unwatch = null;
  unwatchFx?.();
  unwatchFx = null;
}

/**
 * 환율 수집을 구독하고 **끝나면 다시 요청한다** (006 FR-046, research R6-10).
 *
 * 003의 통화별 스트림은 진행 중이면 `snapshot`, 아니면 5초마다 `idle`을 보낸다.
 *
 * - `waiting`: 다른 통화가 끝나면(`idle`의 `busyWith`가 비면) 다시 요청한다
 * - `queued`·`collecting`: 진행을 본 뒤 `idle`이 오면 끝난 것이다. 진행을 한 번도 못 보고
 *   `idle`이 두 번 오면 구독이 붙기 전에 끝났다고 보고 다시 요청한다 — 진행을 못 봤다고
 *   영원히 기다리면 화면이 "받고 있습니다"에 머문다. 한 번의 `idle`로 다시 요청하지 않는
 *   이유는 워커가 큐에서 꺼내기 직전일 수 있어서다
 */
function watchFx(fx: FxCollecting, get: () => StockState): void {
  unwatchFx?.();
  let sawActive = false;
  let idleCount = 0;
  const rerun = () => {
    unwatchFx?.();
    unwatchFx = null;
    void get().run();
  };
  unwatchFx = subscribeCollection(fx.currency, {
    onSnapshot: () => {
      sawActive = true;
    },
    onIdle: (payload) => {
      if (fx.state === "waiting") {
        if (payload.busyWith === null) rerun();
        return;
      }
      idleCount += 1;
      if (sawActive || idleCount >= 2) rerun();
    },
    onEvent: () => undefined,
  });
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

export const useStockStore = create<StockState>((set, get) => ({
  input: {
    stock: null,
    start: "",
    principal: "",
    principalCurrency: "KRW",
    reinvest: true,
  },
  selecting: false,
  selectionError: null,
  listedOn: null,
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
  history: [],
  historySaveError: null,
  selectedHistory: [],
  comparison: [],
  comparing: false,
  comparisonError: null,

  setInput: (next) => set({ input: { ...get().input, ...next } }),

  selectStock: async (choice) => {
    const id = selectionSeq.next();
    set({
      input: { ...get().input, stock: null },
      selecting: true,
      selectionError: null,
      listedOn: null,
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
    if (get().summary === null) return;
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
    const { input } = get();
    const query = toQuery(input);
    if (input.stock === null || query === "") {
      set({ error: "종목을 먼저 고르세요." });
      return;
    }
    // 이전 실행의 구독을 끊는다. 남기면 이전 조건의 완료 신호가 새 조건을 다시 요청한다.
    stopWatching();
    set({
      rows: [], summary: null, condition: null, exchange: null,
      hasMore: false, oldestReturned: null, series: null, seriesError: null,
      collecting: null, fxBlocked: null, progress: null, loading: true, error: null,
      loadMoreError: null,
    });
    try {
      const body = await apiClient.get<SimulationResponse | SimulationCollecting>(
        `/api/stocks/simulation?${query}`,
      );
      if ("status" in body && body.status === "collecting") {
        // FR-049 — 부분 결과를 완성된 결과처럼 보여주지 않는다.
        //
        // **이력에도 남기지 않는다.** 아직 결과가 없는 조건이다.
        set({ collecting: body, progress: null, loading: false });
        // 006 — 주식 시세와 환율을 따로 기다린다. 어느 쪽이 끝나도 다시 요청하고, 서버가
        // 둘 다 끝났는지 판정한다(FR-045).
        if (body.jobId !== undefined) watchProgress(body.jobId, set, get);
        if (body.fx !== undefined) watchFx(body.fx, get);
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

      // FR-035 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다**(R5-9).
      const saved = saveHistory({
        stock: input.stock,
        start: input.start,
        principal: input.principal,
        principalCurrency: input.principalCurrency,
        reinvest: input.reinvest,
      });
      set({
        history: loadHistory(),
        historySaveError: saved.ok ? null : saved.reason,
      });

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
    const { hasMore, oldestReturned, loadingMore, input } = get();
    if (!hasMore || oldestReturned === null || loadingMore) return;
    set({ loadingMore: true, loadMoreError: null });
    try {
      const body = await apiClient.get<SimulationResponse>(
        `/api/stocks/simulation?${toQuery(input)}&before=${oldestReturned}`,
      );
      set({
        rows: [...get().rows, ...body.rows],
        hasMore: body.hasMore,
        oldestReturned: body.oldestReturned,
        loadingMore: false,
      });
    } catch (err) {
      // 이미 표시된 행은 그대로 둔다 (FR-004와 같은 계열). 조용히 멈추면 사용자는
      // 데이터가 거기서 끝난 것으로 오해한다.
      set({
        loadingMore: false,
        loadMoreError: message(err, "이어서 불러오지 못했습니다."),
      });
    }
  },

  /** 저장소에서 이력을 읽는다. 첫 화면 진입에 한 번 부른다 (FR-037). */
  restoreHistory: () => set({ history: loadHistory() }),

  toggleHistory: (id) => {
    const selected = get().selectedHistory;
    set({
      selectedHistory: selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    });
  },

  removeHistoryEntry: (id) => {
    const result = removeHistory(id);
    set({
      history: loadHistory(),
      selectedHistory: get().selectedHistory.filter((x) => x !== id),
      // 지운 항목이 비교에 올라가 있었으면 함께 내린다 — 남겨 두면 목록에 없는
      // 선이 차트에 남아 사용자가 어느 조건인지 확인할 길이 없다.
      comparison: get().comparison.filter((c) => c.id !== id),
      historySaveError: result.ok ? null : result.reason,
    });
  },

  /**
   * 고른 이력을 **지금 다시 계산해서** 겹친다 (FR-038).
   *
   * 저장된 결과를 쓰지 않는 이유는 R5-9와 같다 — 설정과 환율이 바뀌면 달라지는데,
   * 저장된 값을 겹치면 어느 시점의 조건에서 나온 선인지 알 수 없다.
   */
  compareSelected: async () => {
    const { history, selectedHistory } = get();
    const targets = history.filter((e) => selectedHistory.includes(e.id));
    if (targets.length < 2) return;

    set({ comparing: true, comparisonError: null, comparison: [] });

    const items: ComparisonItem[] = [];
    const failed: string[] = [];

    for (const entry of targets) {
      const query = toQuery({
        stock: entry.stock,
        start: entry.start,
        principal: entry.principal,
        principalCurrency: entry.principalCurrency,
        reinvest: entry.reinvest,
      });
      try {
        const body = await apiClient.get<SimulationSeriesResponse | SimulationCollecting>(
          `/api/stocks/simulation/series?${query}`,
        );
        if ("status" in body && body.status === "collecting") {
          // FR-049 — 부분 결과를 완성된 선처럼 겹치지 않는다.
          failed.push(entry.stock.name);
          continue;
        }
        items.push({
          id: entry.id,
          label: entry.stock.name,
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
