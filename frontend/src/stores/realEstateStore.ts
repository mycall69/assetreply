/**
 * 부동산 화면의 단일 상태 원천 — 지역·단지·평형 고르기 (T026)와 실행 (T039) — 009 FR-002~FR-007, FR-011, FR-014, FR-015,
 * FR-023, SC-007, ui-wireframes E2·E3·E9, 헌법 원칙 VII.
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
 *
 * 실행(T039)은 예금(`depositStore`)과 같다. **결과를 저장하지 않는다** — 설정과 거래가 바뀌면 결과가 달라진다.
 * - **부분 결과를 보여주지 않는다**(FR-011). 202면 결과를 비우고 진행(받은 달 / 받을 달)을 구독하고, 끝나면 같은 조건으로 다시 요청한다
 * - 수집이 실패하면 종류마다 다른 말(E9)로 할 일까지 보인다. 다만 **받아 둔 시·군·구**(단지 목록의 `trades.state = "collected"`)면
 *   곧바로 한 번 다시 요청한다 — 서버가 받아 둔 거래로 계산해 200 + `recheckFailed`를 준다. 받은 적 없거나 중간까지만 받은 시·군·구는
 *   다시 요청하지 않는다 — 서버도 200을 주지 않으므로(부분 결과) 같은 실패가 되풀이되며 하루 한도만 쓴다. 한 실행에 한 번이다
 * - 409는 종류마다 따로 든다 — `before_first_trade`는 시작 가능 날짜와 근거(매입일은 **바꾸지 않는다**, FR-005), 나머지는 거절
 * - 평형·단지 이하를 바꾸면 결과·거절을 지우고, 늦게 온 이전 실행의 응답은 버린다
 *
 * 이력과 비교(T050)도 예금과 같다 — 결과가 나온 실행의 **조건만** 남기고(FR-032), 비교는 고른 이력을 **지금 다시 계산해서** 겹친다
 * (FR-033). 다시 실행은 지역 풀다운까지 그 단지의 지역으로 맞춘다 — 풀다운이 이전 지역에 남으면 화면이 말하는 지역과 결과의 단지가
 * 어긋난다. 비교에서 빠지는 항목은 조용히 빼지 않는다 — 빼면 그 단지가 진 것으로 읽힌다.
 */

import { create } from "zustand";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import { ApiError, apiClient } from "@/lib/apiClient";
import {
  subscribeRealEstateProgress,
  type RealEstateProgressHandlers,
  type RealEstateProgressSnapshot,
} from "@/lib/realEstateProgressStream";
import { INITIAL_HISTORY, removeHistoryFlow, restoreHistoryFlow, saveHistoryFlow } from "@/lib/historyFlow";
import { DEFAULT_START } from "@/lib/startDate";
import type {
  RealEstateAcquisition,
  RealEstateAreaKey,
  RealEstateAreasResponse,
  RealEstateComplexesResponse,
  RealEstateCondition,
  RealEstateFailureKind,
  RealEstateHistoryEntry,
  RealEstateRegion,
  RealEstateRegionCollecting,
  RealEstateRegionLevel,
  RealEstateRegionsResponse,
  RealEstateRow,
  RealEstateSimulationResponse,
  RealEstateSummary,
  RealEstateTradeCollecting,
  SimulationSeriesResponse,
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

export interface RealEstateInput {
  buyDate: string;
  /** 원 단위 정수 문자열(쉼표 없음). 비었으면 매입 달의 시세다(FR-006). 문자열로 들고 있다가 문자열로 보낸다(헌법 원칙 VI). */
  buyPrice: string;
}

/** 실행 뒤 서버가 알려 준 시작 가능 날짜와 근거(409 `before_first_trade`, FR-005). */
export interface RealEstateStartable {
  startableFrom: string;
  basis: "first_trade" | "tax_rules";
}

/** 실행의 거절(409, ui-wireframes E3) — 화면이 종류마다 다른 말과 할 일을 보인다. */
export type RealEstateRejection =
  | { kind: "no_price_at_purchase"; month: string }
  | { kind: "no_trades_in_area" }
  | { kind: "tax_rule_not_covered"; tax: string; date: string }
  | { kind: "region_retired"; lawdCd: string };

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
  input: RealEstateInput;
  summary: RealEstateSummary | null;
  rows: RealEstateRow[];
  condition: RealEstateCondition | null;
  acquisition: RealEstateAcquisition | null;
  /** 결과의 단지·평형 — 입력이 바뀌어도 결과가 어느 단지·평형의 것인지 남긴다. */
  resultTarget: Pick<RealEstateSimulationResponse, "complex" | "area"> | null;
  /** 차트용 시계열(FR-031). 표와 **같은 조건**으로 따로 받는다. */
  series: SimulationSeriesResponse | null;
  /** 차트만 실패한 사유. **표를 지우지 않는다** — 차트가 비는 것과 결과가 없는 것은 다른 사건이다(005~008과 같다). */
  seriesError: string | null;
  /** 실행이 그 시·군·구의 실거래를 기다린다(202). */
  collecting: RealEstateTradeCollecting | null;
  /** 그 수집의 진행. 스냅샷이 오기 전에는 `null`이다. */
  progress: RealEstateProgressSnapshot | null;
  startable: RealEstateStartable | null;
  rejection: RealEstateRejection | null;
  loading: boolean;
  error: string | null;

  /** 화면을 열 때 시·도를 요청한다. 실패 뒤에 다시 부르면 새 작업을 따라간다. */
  loadSidos: () => Promise<void>;
  selectSido: (code: string) => Promise<void>;
  selectSgg: (code: string) => Promise<void>;
  selectUmd: (code: string) => Promise<void>;
  selectComplex: (complexId: number) => Promise<void>;
  /** 평형을 고른다. 결과를 지운다 — 실행은 버튼으로 한다. */
  selectArea: (key: RealEstateAreaKey) => void;
  setInput: (next: Partial<RealEstateInput>) => void;
  /** 고른 단지·평형과 입력으로 실행한다. 실행 즉시 이전 결과를 비운다. */
  run: () => Promise<void>;
  /**
   * 설정이 바뀐 뒤 결과를 다시 받는다(FR-034). 결과가 있을 때만 — 실행한 적이 없거나 거절됐으면 요청하지 않고, 수집 중이면 진행이
   * 끝날 때 어차피 다시 요청한다.
   */
  refreshIfRan: () => Promise<void>;

  /** 이력(FR-032). **조건만** 담긴다. 다른 자산군 이력과 따로다. 012부터 로컬 DB에 있다(`lib/historyFlow`). */
  history: RealEstateHistoryEntry[];
  historyLoading: boolean;
  historyLoadError: string | null;
  historySaveError: string | null;
  historyNotice: string | null;
  retentionDays: number | null | undefined;
  selectedHistory: string[];
  comparison: ComparisonItem[];
  comparing: boolean;
  comparisonError: string | null;
  /** 012 — 옛 브라우저 이력을 옮긴 뒤 목록을 받는다. 다시 시도도 이것이다(FR-014a). */
  restoreHistory: () => Promise<void>;
  toggleHistory: (id: string) => void;
  removeHistoryEntry: (id: string) => Promise<void>;
  /** 이력의 조건으로 지역 풀다운부터 평형까지 맞추고 곧바로 실행한다. */
  rerunHistory: (id: string) => Promise<void>;
  /** 고른 이력을 **지금 다시 계산해서** 겹친다(FR-033) — 저장된 결과가 없다. */
  compareSelected: () => Promise<void>;
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

type Watch = "region" | "trade" | "details" | "areas" | "simulation";
/** 살아 있는 진행 구독 — 종류마다 하나. 작업 번호를 들고 있어 같은 작업을 두 번 구독하지 않는다. */
const watchers: Record<Watch, { jobId: number; stop: () => void } | null> = {
  region: null, trade: null, details: null, areas: null, simulation: null,
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

const NO_RESULT = {
  summary: null, rows: [], condition: null, acquisition: null, resultTarget: null, series: null, seriesError: null,
  collecting: null, progress: null, startable: null, rejection: null, loading: false,
} satisfies Partial<RealEstateState>;

/** 지금 실행의 번호. 결과를 지우거나 새로 실행하면 늘어난다 — 늦게 온 이전 실행의 응답을 버린다. */
let runSeq = 0;
/** 지금 실행이 화면이 스스로 한 것인지(수집 완료·실패 뒤). 사용자가 실행하면 자동 다시 요청의 기회를 되돌린다. */
let automaticRun = false;
/** 이 실행에서 실패 뒤 다시 요청했는지 — 한 실행에 한 번(008 FR-016a와 같다). */
let retriedAfterFailure = false;

/** 결과·거절을 지우고 실행의 진행 구독을 끊는다. */
function clearResult(): typeof NO_RESULT {
  stopWatching("simulation");
  runSeq += 1;
  return NO_RESULT;
}

/** 실행의 질의. 매입가는 **문자열 그대로**, 비었으면 보내지 않는다. 통화는 보내지 않는다 — 원화만이다(FR-007). */
function simulationQuery(complexId: number, area: RealEstateAreaKey, input: RealEstateInput): string {
  const query = new URLSearchParams({ complexId: String(complexId), area, buyDate: input.buyDate });
  if (input.buyPrice !== "") query.set("buyPrice", input.buyPrice);
  return query.toString();
}

/** 오류 본문의 글자 필드. */
const field = (body: Record<string, unknown>, key: string): string =>
  typeof body[key] === "string" ? body[key] : "";

/** 409 본문 → 거절. 모르는 종류면 `null`(사유를 그대로 보인다). */
function rejectionOf(code: string, body: Record<string, unknown>): RealEstateRejection | null {
  switch (code) {
    case "no_price_at_purchase":
      return { kind: code, month: field(body, "month") };
    case "no_trades_in_area":
      return { kind: code };
    case "tax_rule_not_covered":
      return { kind: code, tax: field(body, "tax"), date: field(body, "date") };
    case "region_retired":
      return { kind: code, lawdCd: field(body, "lawdCd") };
    default:
      return null;
  }
}

export const useRealEstateStore = create<RealEstateState>((set, get) => {
  /** 단지를 바꾸면 평형·결과를 지운다. */
  function belowComplex(): Partial<RealEstateState> {
    stopWatching("areas");
    return { areas: null, areasCollecting: null, ...clearResult(), error: null };
  }

  /**
   * 차트용 시계열 — **표가 수집 중이 아님을 확인한 뒤에 받는다.** 나란히 보내면 같은 구간에 수집 요청이 두 번 나간다(005와 같다).
   * 그래도 202면(그 사이 잠정 확인이 시작됐다) 차트만 비우고 사유를 말한다 — 표는 지우지 않는다.
   */
  async function loadSeries(query: string, seq: number): Promise<void> {
    try {
      const body = await apiClient.get<SimulationSeriesResponse | RealEstateTradeCollecting>(
        `/api/realestate/simulation/series?${query}`);
      if (seq !== runSeq) return;
      if (isCollecting<RealEstateTradeCollecting>(body)) {
        set({ seriesError: "차트에 쓸 거래를 다시 확인하는 중입니다. 다시 실행하면 차트가 보입니다.", loading: false });
        return;
      }
      set({ series: body, loading: false });
    } catch (err) {
      if (seq !== runSeq) return;
      set({ seriesError: message(err, "차트를 불러오지 못했습니다."), loading: false });
    }
  }

  function rerunAutomatically(): void {
    automaticRun = true;
    void get().run();
  }

  /** 실행의 진행을 구독한다. **완료에 다시 요청한다** — 부분 결과를 먼저 보여주지 않는 대신 끝난 시점을 알려야 한다. */
  function watchSimulation(jobId: number): void {
    watch("simulation", jobId, {
      onSnapshot: (progress) => set({ progress }),
      onCompleted: () => {
        stopWatching("simulation");
        rerunAutomatically();
      },
      onFailed: (kind, reason) => {
        stopWatching("simulation");
        // 받아 둔 시·군·구면 서버가 받아 둔 거래로 답한다(200 + recheckFailed). 한 실행에 한 번.
        if (get().complexes?.trades.state === "collected" && !retriedAfterFailure) {
          retriedAfterFailure = true;
          rerunAutomatically();
          return;
        }
        set({ collecting: null, progress: null, error: realEstateFailureText(kind, reason) });
      },
    });
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
  /**
   * 그 시·군·구의 실거래 작업을 구독한다 — 진행 줄(단지 풀다운 아래)이 이 하나로 보인다. 끝나면 단지 목록을 다시 받고(실거래에만 있던
   * 단지가 더해진다), 같은 작업을 기다리던 평형도 다시 받는다. 실패하면 **그 작업의** 종류와 사유를 단지 목록의 실거래 상태에 둔다.
   */
  function watchTrade(jobId: number, umd: string): void {
    watch("trade", jobId, {
      onSnapshot: (tradeProgress) => set({ tradeProgress }),
      onCompleted: () => {
        stopWatching("trade");
        set({ tradeProgress: null });
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
  }

  function watchComplexJobs(body: RealEstateComplexesResponse, umd: string): void {
    const { trades } = body;
    if (trades.state === "collecting" && trades.jobId !== null) {
      watchTrade(trades.jobId, umd);
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

  /** 평형 202의 작업을 구독한다. 실거래 구독이 같은 작업이면(대개 그렇다) 그쪽 완료가 평형을 다시 요청한다 — 두 번 구독하지 않는다. */
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
        // 평형 202는 그 시·군·구의 실거래를 받는 중이라는 뜻이다 — 마지막 작업이 실패했던 곳이면 서버가 새 작업을 시작했다.
        // 단지 목록의 실거래 상태를 그 작업의 수집 중으로 바꿔 진행 줄 하나로 보이고 지난 실패 경고를 지운다(T054 실측 —
        // 고치기 전에는 진행이 보이지 않고 지난 한도 초과 경고가 남아 막힌 것처럼 보였다).
        const { complexes, selection } = get();
        if (complexes !== null && selection.umd !== null && complexes.umd.code === selection.umd) {
          set({ complexes: { ...complexes, trades: {
            state: "collecting", jobId: body.jobId, monthsDone: body.monthsDone, monthsTotal: body.monthsTotal,
            progressUrl: body.progressUrl, failure: null,
          } } });
          watchTrade(body.jobId, selection.umd);
        }
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
    input: { buyDate: DEFAULT_START, buyPrice: "" },
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

    selectArea: (key) => set({ selection: { ...get().selection, area: key }, ...clearResult(), error: null }),

    setInput: (next) => set({ input: { ...get().input, ...next } }),

    ...INITIAL_HISTORY,
    comparison: [],
    comparing: false,
    comparisonError: null,

    restoreHistory: () => restoreHistoryFlow("realestate", get, set),

    toggleHistory: (id) => {
      const selected = get().selectedHistory;
      set({ selectedHistory: selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id] });
    },

    removeHistoryEntry: async (id) => {
      if (!(await removeHistoryFlow("realestate", id, get, set))) return;
      // 지운 항목의 선을 남기면 목록에 없는 조건이 차트에 남는다.
      set({ comparison: get().comparison.filter((c) => c.id !== id) });
    },

    rerunHistory: async (id) => {
      const entry = get().history.find((e) => e.id === id);
      if (entry === undefined) return;
      // 고르기와 같은 요청으로 목록을 채운다 — 시·도는 동 코드의 앞 2자리, 시·군·구는 앞 5자리다(법정동 코드 체계).
      await get().selectSido(`${entry.umd.slice(0, 2)}00000000`);
      await get().selectSgg(`${entry.umd.slice(0, 5)}00000`);
      await get().selectUmd(entry.umd);
      await get().selectComplex(entry.complexId);
      get().selectArea(entry.area);
      get().setInput({ buyDate: entry.buyDate, buyPrice: entry.buyPrice ?? "" });
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
        const name = `${entry.complexName} ${entry.areaLabel}`;
        const query = simulationQuery(entry.complexId, entry.area,
          { buyDate: entry.buyDate, buyPrice: entry.buyPrice ?? "" });
        try {
          const body = await apiClient.get<SimulationSeriesResponse | RealEstateTradeCollecting>(
            `/api/realestate/simulation/series?${query}`);
          if (isCollecting<RealEstateTradeCollecting>(body)) {
            // 부분 결과를 완성된 선처럼 겹치지 않는다.
            failed.push(`${name}(아직 받지 못한 구간이 있습니다 — 실행해서 받으세요)`);
            continue;
          }
          // FR-033 — 잠정 거래가 들어간 선이면 범례가 말한다. `provisionalFrom`은 늘 오므로 점으로 가른다.
          const provisional = body.points.some((p) => p.provisional === true);
          items.push({ id: entry.id, label: provisional ? `${name} (잠정)` : name, start: entry.buyDate, series: body });
        } catch (err) {
          failed.push(err instanceof ApiError && err.code === "unknown_complex"
            ? `${name}(알 수 없는 단지)` : `${name}(${message(err, "알 수 없는 오류")})`);
        }
      }
      set({
        comparison: items,
        comparing: false,
        comparisonError: failed.length === 0 ? null : `${failed.join(" · ")}의 시계열을 불러오지 못했습니다.`,
      });
    },

    refreshIfRan: async () => {
      if (get().summary === null) return;
      await get().run();
    },

    run: async () => {
      if (!automaticRun) retriedAfterFailure = false;
      automaticRun = false;
      const { selection, input } = get();
      if (selection.complexId === null || selection.area === null) {
        set({ error: "단지와 평형을 고르세요." });
        return;
      }
      // FR-006 — 0 이하는 거절한다. 칸이 숫자만 받으므로 남는 것은 0뿐이다.
      if (input.buyPrice !== "" && !/[1-9]/.test(input.buyPrice)) {
        set({ error: "매입가는 0보다 커야 합니다." });
        return;
      }
      set({ ...clearResult(), loading: true, error: null });
      const seq = runSeq;
      const query = simulationQuery(selection.complexId, selection.area, input);
      try {
        const body = await apiClient.get<RealEstateSimulationResponse | RealEstateTradeCollecting>(
          `/api/realestate/simulation?${query}`);
        if (seq !== runSeq) return;
        if (isCollecting<RealEstateTradeCollecting>(body)) {
          set({ collecting: body, progress: null, loading: false });
          watchSimulation(body.jobId);
          return;
        }
        set({
          summary: body.summary, rows: body.rows, condition: body.condition, acquisition: body.acquisition,
          resultTarget: { complex: body.complex, area: body.area },
        });
        // FR-032 — 실행한 조건을 이력에 남긴다. **결과는 넣지 않는다.** 수집 중(202)·거절이면 남기지 않는다 — 아직 결과가 없다.
        if (selection.umd !== null) {
          await saveHistoryFlow("realestate", {
            complexId: body.complex.complexId, complexName: body.complex.name, umd: selection.umd,
            area: body.area.key, areaLabel: body.area.label, buyDate: input.buyDate,
            buyPrice: input.buyPrice === "" ? null : input.buyPrice,
          }, get, set);
        }
        await loadSeries(query, seq);
      } catch (err) {
        if (seq !== runSeq) return;
        if (err instanceof ApiError && err.httpStatus === 409 && err.body !== null) {
          if (err.code === "before_first_trade") {
            // 조용히 옮기지 않는다 — 옮기기는 눌러야 일어난다(FR-005).
            const basis = field(err.body, "basis") === "tax_rules" ? "tax_rules" : "first_trade";
            set({ startable: { startableFrom: field(err.body, "startableFrom"), basis }, loading: false });
            return;
          }
          const rejection = rejectionOf(err.code, err.body);
          if (rejection !== null) {
            set({ rejection, loading: false });
            return;
          }
        }
        set({ error: message(err, "시뮬레이션에 실패했습니다."), loading: false });
      }
    },

    resumeWatching: () => {
      const { complexes, areasCollecting, collecting, selection } = get();
      if (complexes !== null && selection.umd !== null) watchComplexJobs(complexes, selection.umd);
      if (areasCollecting !== null && selection.complexId !== null) {
        watchAreas(areasCollecting.jobId, selection.complexId);
      }
      if (collecting !== null) watchSimulation(collecting.jobId);
    },

    dispose: () => {
      stopWatching("region");
      stopWatching("trade");
      stopWatching("details");
      stopWatching("areas");
      stopWatching("simulation");
    },
  };
});
