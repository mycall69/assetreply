/**
 * 부동산 시뮬레이션 실행 상태 (T034) — 009 FR-005, FR-006, FR-011, FR-014, FR-023, FR-002, ui-wireframes E3·E9.
 *
 * 예금 화면(`depositStore`·`depositStoreRecheck`)을 본뜬다.
 * - **부분 결과를 보여주지 않는다**(FR-011). 202면 결과를 비우고 진행(받은 달 / 받을 달)을 구독하고, 끝나면 같은 조건으로 다시 요청한다
 * - 수집이 실패하면 **종류마다 다른 말**(E9)로 할 일까지 보인다(FR-014)
 * - **받아 둔 시·군·구**(단지 목록 응답의 `trades.state = "collected"`)에서 실패하면 곧바로 **한 번** 다시 요청한다 — 서버가 받아 둔
 *   거래로 계산해 200 + `recheckFailed`를 준다. `collecting`·`failed`·`none`(받은 적 없거나 중간까지만)이면 다시 요청하지 않는다 — 서버도
 *   200을 주지 않으므로(부분 결과) 같은 실패가 되풀이되며 출처의 하루 한도만 쓴다. 다시 요청은 한 실행에 한 번이고, 사용자가 새로
 *   실행하면 기회가 돌아온다
 * - 409는 종류마다 다르게 들고 있다 — `before_first_trade`는 시작 가능 날짜와 근거(매입일은 **바꾸지 않는다**, FR-005), 나머지는 거절
 *   (`rejection`). 평형을 바꾸면 둘 다 지운다
 *
 * ## 이 테스트가 전제하는 모듈 (T039가 따른다)
 *
 * `@/stores/realEstateStore`의 `useRealEstateStore`에 더한다(Phase 3의 상태·동작은 그대로):
 * - 상태: `input: { buyDate: string; buyPrice: string }`(매입가는 쉼표 없는 숫자 문자열, 비면 그 달 시세), `summary: RealEstateSummary | null`,
 *   `rows: RealEstateRow[]`, `condition: RealEstateCondition | null`, `acquisition: RealEstateAcquisition | null`,
 *   `resultTarget: { complex: RealEstateSimulationResponse["complex"]; area: RealEstateSimulationResponse["area"] } | null`,
 *   `collecting: RealEstateTradeCollecting | null`, `progress: RealEstateProgressSnapshot | null`,
 *   `startable: { startableFrom: string; basis: "first_trade" | "tax_rules" } | null`, `rejection: RealEstateRejection | null`,
 *   `loading: boolean` (`error`는 Phase 3의 것을 쓴다)
 * - `export type RealEstateRejection = { kind: "no_price_at_purchase"; month: string } | { kind: "no_trades_in_area" } |
 *   { kind: "tax_rule_not_covered"; tax: string; date: string } | { kind: "region_retired"; lawdCd: string }`
 * - 동작: `setInput(next: Partial<input>)`, `run(): Promise<void>`. `dispose()`는 실행의 진행 구독도 끊는다
 * - 요청: `GET /api/realestate/simulation?complexId=&area=&buyDate=[&buyPrice=]` — 매입가가 비면 보내지 않는다. 통화는 보내지 않는다(원화만)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/apiClient";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import type { RealEstateFailureKind, RealEstateTrades } from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  COLLECTING_TRADES,
  FAILURE_FRAGMENTS,
  FAILURE_KINDS,
  HELIO_ID,
  failedTrades,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";
import {
  SIM_COLLECTING,
  SIM_RECHECK_FAILED,
  SIM_RESULT,
  chooseForRun,
  resetSimulation,
} from "./support/realEstateSimulationFixtures";

// jsdom에는 `EventSource`가 없다. 여기서 보려는 것은 **언제 구독하고, 끝나거나 실패하면 다시 요청하는가**다.
const progress = vi.hoisted(() => ({
  subs: [] as { jobId: number; handlers: RealEstateProgressHandlers; active: boolean }[],
}));
vi.mock("@/lib/realEstateProgressStream", () => ({
  subscribeRealEstateProgress: (jobId: number, handlers: RealEstateProgressHandlers) => {
    const sub = { jobId, handlers, active: true };
    progress.subs.push(sub);
    return () => {
      sub.active = false;
    };
  },
}));

const subscriptions = (jobId: number) => progress.subs.filter((s) => s.jobId === jobId).length;
const subscribed = (jobId: number) => progress.subs.some((s) => s.jobId === jobId && s.active);
function fire(jobId: number, event: (h: RealEstateProgressHandlers) => void): void {
  for (const s of progress.subs.filter((x) => x.jobId === jobId && x.active)) event(s.handlers);
}

const SIMULATION = "/api/realestate/simulation";
type Get = { mock: { calls: unknown[][] } };
const simulations = (get: Get) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === SIMULATION);

/** 시뮬레이션 응답을 차례로 준다. 나머지 경로는 모두 받아 둔 상태의 응답이다. */
function respond(...answers: unknown[]): Get {
  const queue = [...answers];
  return routeRealEstate((path) =>
    splitPath(path).base === SIMULATION ? queue.shift() : realEstateRoutes(path));
}

const state = () => useRealEstateStore.getState();
const settle = () => new Promise((r) => setTimeout(r, 0));

function conflict(code: string, body: Record<string, unknown>): ApiError {
  const message = `${code} 사유`;
  return new ApiError(409, code, message, { status: code, message, ...body });
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
  resetSimulation();
  progress.subs = [];
  chooseForRun();
});

describe("실행", () => {
  it("단지·평형·매입일을 보내고 매입가가 비면 보내지 않는다 — 통화도 보내지 않는다", async () => {
    const get = respond(SIM_RESULT);
    await state().run();
    const sent = simulations(get);
    expect(sent).toHaveLength(1);
    expect(Object.fromEntries(splitPath(sent[0]).params)).toEqual({
      complexId: String(HELIO_ID), area: "30k", buyDate: "2021-03-15" });
  });

  it("매입가를 넣었으면 쉼표 없는 문자열 그대로 보낸다", async () => {
    const get = respond(SIM_RESULT);
    state().setInput({ buyPrice: "2000000000" });
    await state().run();
    expect(splitPath(simulations(get)[0]).params.get("buyPrice")).toBe("2000000000");
  });

  it("결과의 요약·행·조건·취득 비용·대상을 들고 있다", async () => {
    respond(SIM_RESULT);
    await state().run();
    const s = state();
    expect(s.summary).toEqual(SIM_RESULT.summary);
    expect(s.rows).toEqual(SIM_RESULT.rows);
    expect(s.condition).toEqual(SIM_RESULT.condition);
    expect(s.acquisition).toEqual(SIM_RESULT.acquisition);
    expect(s.resultTarget).toEqual({ complex: SIM_RESULT.complex, area: SIM_RESULT.area });
    expect(s.collecting).toBeNull();
    expect(s.error).toBeNull();
    expect(s.loading).toBe(false);
  });

  it("평형을 고르지 않았으면 보내지 않는다", async () => {
    const get = respond(SIM_RESULT);
    useRealEstateStore.setState({ selection: { ...state().selection, area: null } });
    await state().run();
    expect(simulations(get)).toHaveLength(0);
    expect(state().error).toContain("평형");
  });

  it("매입가가 0이면 보내지 않는다(FR-006)", async () => {
    const get = respond(SIM_RESULT);
    state().setInput({ buyPrice: "0" });
    await state().run();
    expect(simulations(get)).toHaveLength(0);
    expect(state().error).toContain("매입가");
  });

  it("평형을 바꾸면 결과를 지운다", async () => {
    respond(SIM_RESULT);
    await state().run();
    state().selectArea("20");
    expect(state().summary).toBeNull();
    expect(state().rows).toEqual([]);
    expect(state().condition).toBeNull();
    expect(state().resultTarget).toBeNull();
  });
});

describe("수집 중 (FR-011)", () => {
  it("202면 결과 없이 진행을 구독하고, 끝나면 같은 조건으로 다시 요청한다", async () => {
    const get = respond(SIM_COLLECTING, SIM_RESULT);
    await state().run();
    expect(state().collecting).toEqual(SIM_COLLECTING);
    expect(state().summary).toBeNull();
    expect(state().rows).toEqual([]);
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));

    fire(9, (h) => h.onSnapshot({ jobId: 9, kind: "trade", target: "11710", status: "running", done: 130, total: 250 }));
    expect(state().progress?.done).toBe(130);

    fire(9, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().summary).not.toBeNull());
    expect(simulations(get)).toHaveLength(2);
    expect(simulations(get)[1]).toBe(simulations(get)[0]);
    expect(state().collecting).toBeNull();
    expect(state().progress).toBeNull();
  });

  it("화면을 떠나면 실행의 진행 구독을 끊는다", async () => {
    respond(SIM_COLLECTING);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    state().dispose();
    expect(subscribed(9)).toBe(false);
  });
});

describe("수집 실패 — 받은 적 없거나 중간까지만 받은 시·군·구 (E9)", () => {
  const notCollected: [string, RealEstateTrades][] = [
    ["collecting", COLLECTING_TRADES],
    ["failed", failedTrades("rate_limited")],
    ["none", { ...COLLECTING_TRADES, state: "none", jobId: null, progressUrl: null }],
  ];

  it.each(notCollected)("trades.state = %s면 다시 요청하지 않는다", async (_label, trades) => {
    chooseForRun(trades);
    const get = respond(SIM_COLLECTING);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed("rate_limited", "하루 한도"));
    await settle();
    expect(simulations(get)).toHaveLength(1);
    expect(state().summary).toBeNull();
    expect(state().collecting).toBeNull();
  });

  it.each<RealEstateFailureKind>(FAILURE_KINDS)("종류마다 문구와 할 일을 보인다 — %s", async (kind) => {
    chooseForRun(COLLECTING_TRADES);
    respond(SIM_COLLECTING);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed(kind, "출처가 준 사유"));
    await settle();
    for (const fragment of FAILURE_FRAGMENTS[kind]) expect(state().error).toContain(fragment);
  });
});

describe("수집 실패 — 받아 둔 시·군·구 (E9, 008 FR-016a와 같다)", () => {
  it.each<RealEstateFailureKind>(FAILURE_KINDS)(
    "실패(%s)하면 곧바로 한 번 다시 요청해 결과와 확인 실패를 보인다", async (kind) => {
      const get = respond(SIM_COLLECTING, SIM_RECHECK_FAILED);
      await state().run();
      await vi.waitFor(() => expect(subscribed(9)).toBe(true));
      fire(9, (h) => h.onFailed(kind, "사유"));
      await vi.waitFor(() => expect(state().summary).not.toBeNull());
      expect(simulations(get)).toHaveLength(2);
      expect(simulations(get)[1]).toBe(simulations(get)[0]);
      expect(state().summary?.recheckFailed).toEqual({ kind: "auth", reason: "공공데이터포털 인증 실패" });
      expect(state().error).toBeNull();
      expect(state().collecting).toBeNull();
    });

  it("다시 요청한 실행이 또 실패하면 더 요청하지 않는다 — 한 실행에 한 번", async () => {
    const get = respond(SIM_COLLECTING, SIM_COLLECTING);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed("network", "사유"));
    await vi.waitFor(() => expect(subscriptions(9)).toBe(2));
    fire(9, (h) => h.onFailed("network", "사유"));
    await settle();
    expect(simulations(get)).toHaveLength(2);
    expect(state().error).toContain("다시 실행하면 이어서 받습니다");
  });

  it("사용자가 새로 실행하면 다시 한 번의 기회가 생긴다", async () => {
    const get = respond(SIM_COLLECTING, SIM_COLLECTING, SIM_COLLECTING, SIM_RECHECK_FAILED);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed("network", "사유"));
    await vi.waitFor(() => expect(subscriptions(9)).toBe(2));
    fire(9, (h) => h.onFailed("network", "사유"));
    await state().run();
    await vi.waitFor(() => expect(subscriptions(9)).toBe(3));
    fire(9, (h) => h.onFailed("network", "사유"));
    await vi.waitFor(() => expect(state().summary).not.toBeNull());
    expect(simulations(get)).toHaveLength(4);
  });

  it("받아 둔 시·군·구인지 모르면(단지 목록 없음) 다시 요청하지 않는다", async () => {
    useRealEstateStore.setState({ complexes: null });
    const get = respond(SIM_COLLECTING);
    await state().run();
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed("auth", "사유"));
    await settle();
    expect(simulations(get)).toHaveLength(1);
    expect(state().error).toContain("인증키 설정과 활용신청을 확인하세요");
  });

  it("확인 실패 결과는 그대로 보인다 — 처음부터 200 + recheckFailed면 다시 요청하지 않는다", async () => {
    const get = respond(SIM_RECHECK_FAILED);
    await state().run();
    expect(state().summary?.recheckFailed?.kind).toBe("auth");
    expect(simulations(get)).toHaveLength(1);
  });
});

describe("실행의 거절 (409, E3)", () => {
  it.each([
    ["first_trade", "2020-02-01"],
    ["tax_rules", "2006-01-01"],
  ] as const)("시작 가능 날짜보다 이르면 그 날짜와 근거(%s)를 들고 있고 매입일은 바꾸지 않는다", async (basis, from) => {
    routeRealEstate((path) => splitPath(path).base === SIMULATION
      ? conflict("before_first_trade", { startableFrom: from, basis }) : realEstateRoutes(path));
    state().setInput({ buyDate: "2005-12-26" });
    await state().run();
    expect(state().startable).toEqual({ startableFrom: from, basis });
    expect(state().input.buyDate).toBe("2005-12-26");
    expect(state().rejection).toBeNull();
    expect(state().summary).toBeNull();
  });

  it.each([
    ["no_price_at_purchase", { month: "2019-05" }, { kind: "no_price_at_purchase", month: "2019-05" }],
    ["no_trades_in_area", {}, { kind: "no_trades_in_area" }],
    ["tax_rule_not_covered", { tax: "property", date: "2021-06-01" },
      { kind: "tax_rule_not_covered", tax: "property", date: "2021-06-01" }],
    ["region_retired", { lawdCd: "42110" }, { kind: "region_retired", lawdCd: "42110" }],
  ] as const)("%s는 거절로 들고 있다", async (code, body, expected) => {
    routeRealEstate((path) => splitPath(path).base === SIMULATION ? conflict(code, body) : realEstateRoutes(path));
    await state().run();
    expect(state().rejection).toEqual(expected);
    expect(state().startable).toBeNull();
    expect(state().summary).toBeNull();
  });

  it("400은 서버의 사유를 보인다", async () => {
    routeRealEstate((path) => splitPath(path).base === SIMULATION
      ? new ApiError(400, "start_after_end", "2026-10-05까지 고를 수 있습니다.",
        { status: "start_after_end", message: "2026-10-05까지 고를 수 있습니다.", lastDay: "2026-10-05" })
      : realEstateRoutes(path));
    await state().run();
    expect(state().error).toContain("2026-10-05까지 고를 수 있습니다.");
    expect(state().rejection).toBeNull();
  });

  it("다시 실행하면 이전 거절을 지운다", async () => {
    const answers: unknown[] = [conflict("no_trades_in_area", {}), SIM_RESULT];
    routeRealEstate((path) => splitPath(path).base === SIMULATION ? answers.shift() : realEstateRoutes(path));
    await state().run();
    expect(state().rejection).not.toBeNull();
    await state().run();
    expect(state().rejection).toBeNull();
    expect(state().summary).not.toBeNull();
  });

  it("평형을 바꾸면 시작 가능 날짜와 거절을 지운다", async () => {
    routeRealEstate((path) => splitPath(path).base === SIMULATION
      ? conflict("before_first_trade", { startableFrom: "2020-02-01", basis: "first_trade" }) : realEstateRoutes(path));
    await state().run();
    state().selectArea("20");
    expect(state().startable).toBeNull();
    expect(state().rejection).toBeNull();
  });
});
