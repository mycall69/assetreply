/**
 * 부동산 화면의 단일 상태 원천 — 지역·단지·평형 고르기 (T026) — 009 FR-002~FR-004, FR-011, FR-014, FR-015, SC-007,
 * ui-wireframes E2·E9, 헌법 원칙 VII.
 *
 * 예금 화면(`depositStore`)을 본뜬다. 고르는 순서는 시·도 → 시·군·구 → 동 → 단지 → 평형이고, 고를 때마다 그다음 목록을 요청한다.
 *
 * - **상위를 바꾸면 하위를 비운다**(SC-007) — 시·도를 바꾸면 시·군·구·동·단지·평형·결과를, 동을 바꾸면 단지·평형·결과를 지운다.
 *   **늦게 온 이전 응답은 버린다** — 응답이 올 때 그 요청의 상위가 아직 골라져 있는지 본다. 버리지 않으면 상위를 바꾼 뒤 이전
 *   상위의 하위 목록이 새 상위 아래에 들어간다
 * - 목록이 아직 없으면 서버가 202를 준다 — 진행을 구독하고, **끝나면 같은 목록을 다시 요청**한다(부분 목록을 먼저 보이지 않는다,
 *   FR-011). 진행 구독은 행정구역·실거래·기본 정보·평형 넷이고, 상위를 바꾸면 그 아래의 구독을 끊는다 — 남기면 떠난 동의 완료가
 *   단지 목록을 다시 요청한다
 * - 실패는 **종류와 사유**를 들고 있다. 문구는 화면이 종류마다 다르게 한다(FR-014·FR-015, `realEstateFailureText`)
 * - 결과(`summary`·`rows`)의 모양은 Phase 4(T039)가 정한다. 지금은 상위를 바꾸면 비운다는 약속만 있다
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import {
  subscribeRealEstateProgress,
  type RealEstateProgressHandlers,
  type RealEstateProgressSnapshot,
} from "@/lib/realEstateProgressStream";
import type {
  RealEstateAreaKey,
  RealEstateAreasResponse,
  RealEstateComplexesResponse,
  RealEstateFailureKind,
  RealEstateRegion,
  RealEstateRegionCollecting,
  RealEstateRegionLevel,
  RealEstateRegionsResponse,
  RealEstateTradeCollecting,
  SimulationSummary,
} from "@/lib/types";

/** 단계별 목록. 받기 전에는 `null`이다 — 빈 목록(`[]`)과 가른다. */
export type RealEstateRegionLists = Record<RealEstateRegionLevel, RealEstateRegion[] | null>;

export interface RealEstateSelection {
  sido: string | null;
  sgg: string | null;
  umd: string | null;
  complexId: number | null;
  area: RealEstateAreaKey | null;
}

/** 진행 스트림의 실패. 종류를 모르면(`null`) 사유를 그대로 보인다. */
export interface RealEstateFailureNotice {
  kind: RealEstateFailureKind | null;
  reason: string;
}

interface RealEstateState {
  regions: RealEstateRegionLists;
  selection: RealEstateSelection;
  /** 행정구역을 처음 받는 중(202). */
  regionCollecting: RealEstateRegionCollecting | null;
  /** 그 작업의 진행 — 받은 쪽 / 쪽 수. 스냅샷이 오기 전에는 `null`이다(0/0은 멈춘 것처럼 보인다). */
  regionProgress: RealEstateProgressSnapshot | null;
  /** 행정구역 수집이 실패했다 — 풀다운 자리에 경고하고 풀다운을 막는다(FR-015). 다시 시도는 화면을 다시 열 때다. */
  regionFailure: RealEstateFailureNotice | null;
  complexes: RealEstateComplexesResponse | null;
  /** 실거래 진행 — 받은 달 / 받을 달. 오기 전에는 응답의 `trades.monthsDone`·`monthsTotal`을 쓴다. */
  tradeProgress: RealEstateProgressSnapshot | null;
  /** 기본 정보(세대수·입주년도) 진행 — 받은 단지 / 단지 수. */
  detailsProgress: RealEstateProgressSnapshot | null;
  areas: RealEstateAreasResponse | null;
  /** 실거래를 아직 받지 않아 평형 구분을 모른다(202). */
  areasCollecting: RealEstateTradeCollecting | null;
  /** 결과 — Phase 4(T039)가 모양을 정한다. */
  summary: SimulationSummary | null;
  rows: unknown[];
  error: string | null;

  /** 화면을 열 때 시·도를 요청한다. 실패 뒤에 다시 부르면 새 작업을 따라간다. */
  loadSidos: () => Promise<void>;
  selectSido: (code: string) => Promise<void>;
  selectSgg: (code: string) => Promise<void>;
  selectUmd: (code: string) => Promise<void>;
  selectComplex: (complexId: number) => Promise<void>;
  /** 평형을 고른다. 결과를 지운다 — 실행은 버튼으로 한다. */
  selectArea: (key: RealEstateAreaKey) => void;
  /** 화면에 돌아왔을 때 받는 중이던 작업을 다시 구독한다 — 떠날 때 끊었다. 수집은 서버에서 이어졌다. */
  resumeWatching: () => void;
  /** 화면을 떠날 때 진행 구독을 모두 끊는다. */
  dispose: () => void;
}

/** 수집 실패 종류 → 문구와 할 일 (ui-wireframes E9). */
const FAILURE_TEXT: Record<RealEstateFailureKind, string> = {
  auth: "공공데이터포털 인증에 실패했습니다. — 인증키 설정과 활용신청을 확인하세요.",
  rate_limited: "실거래 출처의 하루 호출 한도에 닿았습니다. 받은 데까지 남겼습니다 — 내일 다시 실행하면 이어서 받습니다.",
  format: "출처의 응답 형식이 바뀌었습니다. — 어댑터를 고쳐야 합니다.",
  network: "출처에 연결하지 못했습니다. 다시 실행하면 이어서 받습니다.",
};

export function realEstateFailureText(kind: RealEstateFailureKind | null, reason: string): string {
  return kind === null ? reason : FAILURE_TEXT[kind];
}

/**
 * 진행 주소(`/api/realestate/progress?jobId=11`)의 작업 번호. 단지 기본 정보는 응답에 작업 번호 없이 주소만 온다
 * (contracts/rest-api `complexes`의 `details`).
 */
export function progressJobId(progressUrl: string | null): number | null {
  if (progressUrl === null) return null;
  const match = /[?&]jobId=(\d+)/.exec(progressUrl);
  return match === null ? null : Number(match[1]);
}

const REGIONS = "/api/realestate/regions";

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

const isCollecting = <T extends { status: "collecting" }>(body: object): body is T =>
  "status" in body && body.status === "collecting";

type Watch = "region" | "trade" | "details" | "areas";
/** 살아 있는 진행 구독 — 종류마다 하나. 작업 번호를 들고 있어 같은 작업을 두 번 구독하지 않는다. */
const watchers: Record<Watch, { jobId: number; stop: () => void } | null> = {
  region: null, trade: null, details: null, areas: null,
};

function stopWatching(key: Watch): void {
  watchers[key]?.stop();
  watchers[key] = null;
}

function watch(key: Watch, jobId: number, handlers: RealEstateProgressHandlers): void {
  // 같은 작업을 이미 구독하고 있으면 그대로 둔다 — 다시 받은 응답이 같은 작업을 가리키는 일이 흔하다.
  if (watchers[key]?.jobId === jobId) return;
  stopWatching(key);
  watchers[key] = { jobId, stop: subscribeRealEstateProgress(jobId, handlers) };
}

const NO_RESULT = { summary: null, rows: [] } satisfies Partial<RealEstateState>;

export const useRealEstateStore = create<RealEstateState>((set, get) => {
  /** 단지를 바꾸면 평형·결과를 지운다. */
  function belowComplex(): Partial<RealEstateState> {
    stopWatching("areas");
    return { areas: null, areasCollecting: null, ...NO_RESULT, error: null };
  }

  /** 동을 바꾸면 단지·평형·결과를 지우고 그 동의 진행 구독을 끊는다. */
  function belowUmd(): Partial<RealEstateState> {
    stopWatching("trade");
    stopWatching("details");
    return { complexes: null, tradeProgress: null, detailsProgress: null, ...belowComplex() };
  }

  async function fetchRegions(parent: string, level: "sgg" | "umd"): Promise<void> {
    try {
      const body = await apiClient.get<RealEstateRegionsResponse>(
        `${REGIONS}?${new URLSearchParams({ parent }).toString()}`);
      // SC-007 — 그 사이 상위가 바뀌었으면 버린다.
      const { selection } = get();
      if ((level === "sgg" ? selection.sido : selection.sgg) !== parent) return;
      set({ regions: { ...get().regions, [level]: body.items } });
    } catch (err) {
      const { selection } = get();
      if ((level === "sgg" ? selection.sido : selection.sgg) !== parent) return;
      set({ error: message(err, "행정구역 목록을 불러오지 못했습니다.") });
    }
  }

  /** 단지 목록 응답이 가리키는 작업(실거래·기본 정보)을 구독한다. 끝나면 단지 목록을 다시 요청한다. */
  function watchComplexJobs(body: RealEstateComplexesResponse, umd: string): void {
    const { trades } = body;
    if (trades.state === "collecting" && trades.jobId !== null) {
      watch("trade", trades.jobId, {
        onSnapshot: (tradeProgress) => set({ tradeProgress }),
        onCompleted: () => {
          stopWatching("trade");
          set({ tradeProgress: null });
          // 실거래에만 있던 단지가 더해진다. 같은 작업을 기다리던 평형도 이제 받을 수 있다.
          void fetchComplexes(umd);
          const { complexId } = get().selection;
          if (complexId !== null && get().areasCollecting !== null) void fetchAreas(complexId);
        },
        onFailed: (kind, reason) => {
          stopWatching("trade");
          const current = get().complexes;
          set({ tradeProgress: null, areasCollecting: null });
          if (kind === null || current === null) {
            // 종류를 모르면 서버의 기록(`trades.failure`)으로 보인다.
            void fetchComplexes(umd);
            return;
          }
          set({ complexes: { ...current,
            trades: { ...current.trades, state: "failed", jobId: null, failure: { kind, reason } } } });
        },
      });
    } else {
      stopWatching("trade");
      set({ tradeProgress: null });
    }

    const detailsJob = progressJobId(body.details.pending ? body.details.progressUrl : null);
    if (detailsJob !== null) {
      watch("details", detailsJob, {
        onSnapshot: (detailsProgress) => set({ detailsProgress }),
        onCompleted: () => {
          stopWatching("details");
          set({ detailsProgress: null });
          void fetchComplexes(umd);
        },
        // 세대수·입주년도만 빠진다 — 이름으로 고를 수 있다. 다음에 그 동을 고르면 다시 채운다.
        onFailed: () => {
          stopWatching("details");
          set({ detailsProgress: null });
        },
      });
    } else {
      stopWatching("details");
      set({ detailsProgress: null });
    }
  }

  async function fetchComplexes(umd: string): Promise<void> {
    try {
      const body = await apiClient.get<RealEstateComplexesResponse>(
        `/api/realestate/complexes?${new URLSearchParams({ umd }).toString()}`);
      if (get().selection.umd !== umd) return;
      set({ complexes: body });
      watchComplexJobs(body, umd);
    } catch (err) {
      if (get().selection.umd !== umd) return;
      set({ error: message(err, "단지 목록을 불러오지 못했습니다.") });
    }
  }

  /** 평형 202의 작업을 구독한다. 실거래 구독이 같은 작업이면 그쪽 완료가 평형을 다시 요청한다. */
  function watchAreas(jobId: number, complexId: number): void {
    if (watchers.trade?.jobId === jobId) return;
    watch("areas", jobId, {
      onSnapshot: () => undefined,
      onCompleted: () => {
        stopWatching("areas");
        void fetchAreas(complexId);
      },
      onFailed: (kind, reason) => {
        stopWatching("areas");
        set({ areasCollecting: null, error: realEstateFailureText(kind, reason) });
      },
    });
  }

  async function fetchAreas(complexId: number): Promise<void> {
    try {
      const body = await apiClient.get<RealEstateAreasResponse | RealEstateTradeCollecting>(
        `/api/realestate/complexes/${complexId}/areas`);
      if (get().selection.complexId !== complexId) return;
      if (isCollecting<RealEstateTradeCollecting>(body)) {
        set({ areas: null, areasCollecting: body });
        watchAreas(body.jobId, complexId);
        return;
      }
      set({ areas: body, areasCollecting: null });
    } catch (err) {
      if (get().selection.complexId !== complexId) return;
      set({ error: message(err, "평형 구분을 불러오지 못했습니다.") });
    }
  }

  return {
    regions: { sido: null, sgg: null, umd: null },
    selection: { sido: null, sgg: null, umd: null, complexId: null, area: null },
    regionCollecting: null,
    regionProgress: null,
    regionFailure: null,
    complexes: null,
    tradeProgress: null,
    detailsProgress: null,
    areas: null,
    areasCollecting: null,
    ...NO_RESULT,
    error: null,

    loadSidos: async () => {
      stopWatching("region");
      set({ regionFailure: null });
      try {
        const body = await apiClient.get<RealEstateRegionsResponse | RealEstateRegionCollecting>(REGIONS);
        if (isCollecting<RealEstateRegionCollecting>(body)) {
          set({ regionCollecting: body, regionProgress: null });
          watch("region", body.jobId, {
            onSnapshot: (regionProgress) => set({ regionProgress }),
            onCompleted: () => {
              stopWatching("region");
              set({ regionCollecting: null, regionProgress: null });
              void get().loadSidos();
            },
            onFailed: (kind, reason) => {
              stopWatching("region");
              // FR-015 — 빈 풀다운만 두지 않는다. 다시 요청하지 않는다 — 같은 실패가 되풀이되며 출처 호출만 쓴다.
              set({ regionCollecting: null, regionProgress: null, regionFailure: { kind, reason } });
            },
          });
          return;
        }
        set({ regions: { ...get().regions, sido: body.items }, regionCollecting: null, regionProgress: null });
      } catch (err) {
        set({ regionCollecting: null, error: message(err, "행정구역 목록을 불러오지 못했습니다.") });
      }
    },

    selectSido: async (code) => {
      set({
        selection: { sido: code, sgg: null, umd: null, complexId: null, area: null },
        regions: { ...get().regions, sgg: null, umd: null },
        ...belowUmd(),
      });
      await fetchRegions(code, "sgg");
    },

    selectSgg: async (code) => {
      set({
        selection: { ...get().selection, sgg: code, umd: null, complexId: null, area: null },
        regions: { ...get().regions, umd: null },
        ...belowUmd(),
      });
      await fetchRegions(code, "umd");
    },

    selectUmd: async (code) => {
      set({ selection: { ...get().selection, umd: code, complexId: null, area: null }, ...belowUmd() });
      await fetchComplexes(code);
    },

    selectComplex: async (complexId) => {
      set({ selection: { ...get().selection, complexId, area: null }, ...belowComplex() });
      await fetchAreas(complexId);
    },

    selectArea: (key) => set({ selection: { ...get().selection, area: key }, ...NO_RESULT }),

    resumeWatching: () => {
      const { complexes, areasCollecting, selection } = get();
      if (complexes !== null && selection.umd !== null) watchComplexJobs(complexes, selection.umd);
      if (areasCollecting !== null && selection.complexId !== null) {
        watchAreas(areasCollecting.jobId, selection.complexId);
      }
    },

    dispose: () => {
      stopWatching("region");
      stopWatching("trade");
      stopWatching("details");
      stopWatching("areas");
    },
  };
});
