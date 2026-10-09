/**
 * 투자 시뮬레이션 모달의 상태 (013 반복 2026-10-09b T101) — spec FR-011b, data-model 5.3, research R13-19.
 *
 * 비교 표의 줄에서 그 대상을 **그 줄을 낸 실행의 조건**으로 그 자산군 메뉴의 경로에 부른다 — 메뉴 표 경로와 `/series`(`lib/compareApi.menuPath`·
 * `menuSeriesPath`). 응답이 메뉴 화면이 받는 그대로라, 모달은 메뉴와 같은 부품으로 같은 결과를 그린다.
 *
 * - **메뉴 스토어를 쓰지 않는다** — 메뉴 화면의 입력·결과가 바뀌지 않고, 이력을 쓰지 않는다(FR-020 — 이 스토어에는 `/api/history` 요청이 없다)
 * - 메뉴 경로가 202를 주면(비교 뒤 받을 데이터가 생김) 진행을 구독하지 않고 까닭과 다시 시도만 둔다(R13-19)
 * - 일자별 표의 쪽 넘김(`before` = `oldestReturned`)·단위(`period`)는 메뉴 스토어와 같은 질의 규칙이다(주식·가상자산). 차례 번호로 늦은 응답을
 *   버린다 — 다른 줄을 열거나 닫으면 올린다
 */
import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import { menuPath, menuSeriesPath } from "@/lib/compareApi";
import type { CompareCondition } from "@/lib/compareCondition";
import { periodQuery } from "@/lib/tablePeriod";
import type {
  CompareTarget,
  CryptoSimulationResponse,
  DepositSimulationResponse,
  InstallmentResponse,
  PeriodUnit,
  RealEstateSimulationResponse,
  RecurringCryptoResponse,
  RecurringStockResponse,
  SimulationResponse,
  SimulationSeriesResponse,
} from "@/lib/types";

/** 메뉴 표 경로 응답 — 자산군·방식마다 그 메뉴의 형 그대로다. */
export type MenuBody = SimulationResponse | RecurringStockResponse | CryptoSimulationResponse | RecurringCryptoResponse
  | DepositSimulationResponse | InstallmentResponse | RealEstateSimulationResponse;

/** 쪽을 넘기는 표(주식·가상자산) — 행·더 있음·가장 오래된 행의 날. */
interface Pageable {
  rows: unknown[];
  hasMore: boolean;
  oldestReturned: string | null;
}

export interface DetailTarget {
  /** 비교 표의 대상 키. */
  key: string;
  name: string;
  href: string | null;
  /** 그 줄을 낸 실행의 정규 조건(`run.condition`) — 흐린 동안에도 이것이다(명확화 2026-10-09). */
  condition: CompareCondition;
  target: CompareTarget;
}

export type DetailStatus = "idle" | "loading" | "ok" | "collecting" | "failed";

export interface DetailState {
  open: DetailTarget | null;
  seq: number;
  status: DetailStatus;
  /** `collecting`·`failed`의 까닭. */
  reason: string | null;
  menu: MenuBody | null;
  series: SimulationSeriesResponse | null;
  seriesError: string | null;
  period: PeriodUnit;
  loadingMore: boolean;
  loadMoreError: string | null;
  tableLoading: boolean;
  tableError: string | null;

  openDetail: (target: DetailTarget) => Promise<void>;
  retry: () => Promise<void>;
  close: () => void;
  setPeriod: (period: PeriodUnit) => Promise<void>;
  loadMore: () => Promise<void>;
}

export const COLLECTING_REASON = "이 대상의 데이터를 받는 중입니다 — 잠시 뒤 다시 시도하세요.";

const failure = (err: unknown, fallback: string): string => (err instanceof ApiError ? err.message : fallback);

/** 202 본문인가 — 메뉴 경로의 수집 본문은 자산군마다 칸이 다르고 `status`만 같다. */
const collectingBody = (body: object): boolean => "status" in body && (body as { status?: unknown }).status === "collecting";

/** 쪽을 넘기는 표인가 — 주식·가상자산(일시금·적립식). 예금·부동산은 행을 한 번에 받는다. */
export function pageable(condition: CompareCondition): boolean {
  return condition.asset === "stock" || condition.asset === "crypto";
}

const isPageable = (body: MenuBody): body is MenuBody & Pageable => "hasMore" in body;

const CLOSED = {
  open: null, status: "idle" as DetailStatus, reason: null, menu: null, series: null, seriesError: null,
  period: "daily" as PeriodUnit, loadingMore: false, loadMoreError: null, tableLoading: false, tableError: null,
};

export const useCompareDetailStore = create<DetailState>()((set, get) => {
  /** 지금 열린 모달의 응답인가 — 아니면 버린다. */
  const live = (seq: number) => get().seq === seq && get().open !== null;

  async function loadSeries(seq: number, open: DetailTarget): Promise<void> {
    try {
      const body = await apiClient.get<SimulationSeriesResponse | { status: "collecting" }>(
        menuSeriesPath(open.condition, open.target));
      if (!live(seq)) return;
      if (collectingBody(body)) {
        set({ series: null, seriesError: COLLECTING_REASON });
        return;
      }
      set({ series: body as SimulationSeriesResponse, seriesError: null });
    } catch (err) {
      if (!live(seq)) return;
      set({ series: null, seriesError: failure(err, "성과 추이를 불러오지 못했습니다.") });
    }
  }

  async function load(open: DetailTarget): Promise<void> {
    const seq = get().seq + 1;
    set({ ...CLOSED, open, seq, status: "loading" });
    const table = (async () => {
      try {
        const body = await apiClient.get<MenuBody | { status: "collecting" }>(menuPath(open.condition, open.target));
        if (!live(seq)) return;
        if (collectingBody(body)) {
          set({ status: "collecting", reason: COLLECTING_REASON });
          return;
        }
        set({ status: "ok", menu: body as MenuBody });
      } catch (err) {
        if (!live(seq)) return;
        set({ status: "failed", reason: failure(err, "시뮬레이션을 불러오지 못했습니다.") });
      }
    })();
    await Promise.all([table, loadSeries(seq, open)]);
  }

  return {
    ...CLOSED,
    seq: 0,

    openDetail: (target) => load(target),

    retry: async () => {
      const open = get().open;
      if (open !== null) await load(open);
    },

    close: () => set({ ...CLOSED, seq: get().seq + 1 }),

    setPeriod: async (period) => {
      const { open, menu } = get();
      if (open === null || menu === null || !isPageable(menu) || !pageable(open.condition)) return;
      const seq = get().seq + 1;
      set({ seq, period, tableLoading: true, tableError: null, loadingMore: false, loadMoreError: null,
        menu: { ...menu, rows: [], hasMore: false, oldestReturned: null } as MenuBody });
      try {
        const body = await apiClient.get<Pageable>(`${menuPath(open.condition, open.target)}${periodQuery(period)}`);
        if (!live(seq)) return;
        const current = get().menu;
        if (current === null) return;
        set({ tableLoading: false,
          menu: { ...current, rows: body.rows, hasMore: body.hasMore, oldestReturned: body.oldestReturned } as MenuBody });
      } catch (err) {
        if (!live(seq)) return;
        set({ tableLoading: false, tableError: failure(err, "표를 불러오지 못했습니다.") });
      }
    },

    loadMore: async () => {
      const { open, menu, loadingMore, period, seq } = get();
      if (open === null || menu === null || !isPageable(menu) || loadingMore || !menu.hasMore
        || menu.oldestReturned === null) return;
      set({ loadingMore: true, loadMoreError: null });
      try {
        const body = await apiClient.get<Pageable>(
          `${menuPath(open.condition, open.target)}&before=${menu.oldestReturned}${periodQuery(period)}`);
        if (!live(seq)) return;
        const current = get().menu;
        if (current === null || !isPageable(current)) return;
        set({ loadingMore: false, menu: { ...current, rows: [...current.rows, ...body.rows], hasMore: body.hasMore,
          oldestReturned: body.oldestReturned } as MenuBody });
      } catch (err) {
        if (!live(seq)) return;
        // 이미 받은 행은 그대로 둔다(메뉴와 같다).
        set({ loadingMore: false, loadMoreError: failure(err, "이어서 불러오지 못했습니다.") });
      }
    },
  };
});
