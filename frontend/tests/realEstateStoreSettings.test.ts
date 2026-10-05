/**
 * 설정을 바꾸고 부동산 화면으로 돌아오면 다시 계산한다 (T042) — 009 FR-034, US2(008 FR-031·SC-008과 같다).
 *
 * 결과를 저장하지 않으므로(005 R5-9) 돌아온 화면이 **실행한 결과가 있으면** 같은 조건으로 다시 요청한다 — 보유세 기준 비율이 바뀌면
 * 재산세·종부세와 수익이 달라진다. 다시 요청하지 않으면 이전 비율로 계산한 결과가 새 비율의 결과처럼 남는다. 실행한 적이 없으면
 * 요청하지 않는다 — 열자마자 조건 없이 요청하면 오류가 보인다. 수집 중(202)이면 진행이 끝날 때 어차피 다시 요청한다.
 *
 * ## 이 테스트가 전제하는 모듈 (T044가 따른다)
 *
 * `@/stores/realEstateStore`의 `useRealEstateStore`에 `refreshIfRan(): Promise<void>`를 더한다 — 결과(`summary`)가 있을 때만 `run()`과
 * 같은 질의로 다시 요청한다. 화면(`@/app/realestate/page`)은 열 때 부른다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import { useRealEstateStore } from "@/stores/realEstateStore";
import { realEstateRoutes, resetRealEstateStore, routeRealEstate, splitPath } from "./support/realEstateFixtures";
import {
  SIM_COLLECTING,
  SIM_RESULT,
  chooseForRun,
  resetSimulation,
} from "./support/realEstateSimulationFixtures";

const progress = vi.hoisted(() => ({ subs: [] as { jobId: number; handlers: RealEstateProgressHandlers }[] }));
vi.mock("@/lib/realEstateProgressStream", () => ({
  subscribeRealEstateProgress: (jobId: number, handlers: RealEstateProgressHandlers) => {
    progress.subs.push({ jobId, handlers });
    return () => undefined;
  },
}));

const SIMULATION = "/api/realestate/simulation";
type Get = { mock: { calls: unknown[][] } };
const simulations = (get: Get) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === SIMULATION);

/** 새 비율(65%)로 다시 계산한 결과 — 보유세가 늘었다. */
const RECALCULATED = {
  ...SIM_RESULT,
  condition: { ...SIM_RESULT.condition, holdingTaxBaseRatio: "0.650000" },
  summary: { ...SIM_RESULT.summary, holdingTaxTotal: "35130766", profit: "306729567" },
};

const state = () => useRealEstateStore.getState();

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
  resetSimulation();
  progress.subs = [];
  chooseForRun();
});

describe("설정 뒤 다시 계산", () => {
  it("실행한 결과가 있으면 같은 조건으로 다시 요청하고 새 비율의 결과를 보인다", async () => {
    const answers: unknown[] = [SIM_RESULT, RECALCULATED];
    const get = routeRealEstate((path) => splitPath(path).base === SIMULATION ? answers.shift() : realEstateRoutes(path));
    state().setInput({ buyPrice: "2000000000" });
    await state().run();
    await state().refreshIfRan();
    expect(simulations(get)).toHaveLength(2);
    expect(simulations(get)[1]).toBe(simulations(get)[0]);
    expect(state().condition?.holdingTaxBaseRatio).toBe("0.650000");
    expect(state().summary?.holdingTaxTotal).toBe("35130766");
  });

  it("실행한 적이 없으면 요청하지 않는다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await state().refreshIfRan();
    expect(simulations(get)).toHaveLength(0);
  });

  it("수집 중(202)이라 결과가 없으면 요청하지 않는다 — 진행이 끝나면 다시 요청한다", async () => {
    const get = routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_COLLECTING : realEstateRoutes(path));
    await state().run();
    await state().refreshIfRan();
    expect(simulations(get)).toHaveLength(1);
  });

  it("거절된 실행 뒤에는 요청하지 않는다 — 결과가 없다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    useRealEstateStore.setState({ rejection: { kind: "no_trades_in_area" } });
    await state().refreshIfRan();
    expect(simulations(get)).toHaveLength(0);
  });
});
