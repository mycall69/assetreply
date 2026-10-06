/**
 * 부동산 이력과 비교 (T049) — 009 FR-032, FR-033, SC-006, ui-wireframes E7. 008 `depositStoreCompare`와 같은 규칙이다.
 *
 * - **결과가 나온 실행만** 이력에 남는다 — 수집 중(202)·거절(409)이면 아직 결과가 없다
 * - 다시 실행 = **지역 풀다운까지 그 단지의 지역으로 맞추고** 조건을 넣어 곧바로 실행한다 — 지역이 다른 단지를 다시 실행했는데 풀다운이
 *   이전 지역에 남으면 화면이 말하는 지역과 결과의 단지가 어긋난다(SC-007과 같은 이유)
 * - 비교는 고른 이력을 **지금 다시 계산해서**(`simulation/series`) 겹친다 — 저장된 결과가 없다. 범례는 단지·평형, 시작은 매입일. 잠정 거래가
 *   들어간 선이면 "(잠정)" — 부동산 시계열은 `provisionalFrom`이 늘 오므로 **점의 `provisional`**로 판정한다
 * - 빠지는 항목은 조용히 빼지 않는다 — 빼고 비교하면 그 단지가 진 것으로 읽힌다. "…의 시계열을 불러오지 못했습니다"와 이름·사유(받지
 *   않은 구간 — "실행해서 받으세요", 모르는 단지)
 *
 * ## 이 테스트가 전제하는 모듈 (T050이 따른다)
 *
 * `@/stores/realEstateStore`의 `useRealEstateStore`에 더한다:
 * - 상태: `history: RealEstateHistoryEntry[]`, `historySaveError: string | null`, `selectedHistory: string[]`,
 *   `comparison: ComparisonItem[]`(`@/components/stock/ComparisonChart`), `comparing: boolean`, `comparisonError: string | null`
 * - 동작: `restoreHistory()`, `toggleHistory(id)`, `removeHistoryEntry(id)`, `rerunHistory(id): Promise<void>`,
 *   `compareSelected(): Promise<void>`
 * - 실행이 200이면 조건(응답의 단지 id·이름과 평형 키·이름, 고른 동 코드, 매입일, 매입가 또는 `null`)을 남긴다 — 012부터 로컬 DB(이력 대역)다
 * - 다시 실행은 동 코드로 시·도(앞 2자리 + `00000000`)·시·군·구(앞 5자리 + `00000`)를 정해 고르기와 같은 요청으로 목록을 채운다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/apiClient";
import type { RealEstateHistoryEntry, SimulationSeriesResponse } from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";
// 012 승인 2026-10-07 — 012부터 이력은 로컬 DB에 있다. 브라우저 lib 대신 이력 대역에 심고 읽는다(research R12-12).
import { historyStub } from "./support/historyStub";
import {
  GARAK,
  GARAK_COMPLEXES,
  GYEONGGI,
  GYEONGGI_SGGS,
  HELIO_AREAS,
  HELIO_ID,
  SEOUL,
  SEOUL_SGGS,
  SONGPA,
  SONGPA_UMDS,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";
import {
  SIM_COLLECTING,
  SIM_RESULT,
  chooseForRun,
  resetSimulation,
} from "./support/realEstateSimulationFixtures";

vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));

const SIMULATION = "/api/realestate/simulation";
const SERIES_PATH = "/api/realestate/simulation/series";

/** 확정 달만 지나는 선 — 잠정 점이 없다. */
const SERIES: SimulationSeriesResponse = {
  from: "2021-03-15", to: "2026-10-05", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 2, gaps: [], provisionalFrom: "2025-11-01",
  points: [
    { date: "2021-03-15", balance: "2023166667", returnRate: "-0.040307", estimated: false, provisional: false },
    { date: "2024-02-01", balance: "2100000000", returnRate: "-0.003858", estimated: false, provisional: false },
  ],
};
/** 잠정 거래가 들어간 선. */
const PROVISIONAL_SERIES: SimulationSeriesResponse = {
  ...SERIES,
  points: [...SERIES.points,
    { date: "2026-10-05", balance: "2450000000", returnRate: "0.146780", estimated: true, provisional: true }],
};

// 012 승인 2026-10-07 — 조건 모양은 012 전 lib의 조건과 같다(식별자·시각 없음).
type RealEstateHistoryCondition = Omit<RealEstateHistoryEntry, "id" | "savedAt" | "lastRunAt">;

const helio: RealEstateHistoryCondition = {
  complexId: HELIO_ID, complexName: "헬리오시티", umd: GARAK, area: "30k", areaLabel: "30평대(국평)",
  buyDate: "2021-03-15", buyPrice: null,
};

type Get = { mock: { calls: unknown[][] } };
const paths = (get: Get, base: string) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === base);
const params = (path: string) => Object.fromEntries(splitPath(path).params);

const state = () => useRealEstateStore.getState();

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  resetRealEstateStore();
  resetSimulation();
  useRealEstateStore.setState({
    history: [], historySaveError: null, selectedHistory: [], comparison: [], comparing: false, comparisonError: null,
  });
});

describe("이력", () => {
  it("결과가 나온 실행만 남긴다 — 응답의 단지·평형과 고른 동, 매입일, 그 달 시세면 null", async () => {
    chooseForRun();
    routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_RESULT
      : splitPath(path).base === SERIES_PATH ? SERIES : realEstateRoutes(path));
    await state().run();
    // 012 승인 2026-10-07
    expect((historyStub.entries("realestate") as unknown as RealEstateHistoryEntry[]).map((e) => [e.complexId, e.complexName, e.umd, e.area, e.areaLabel, e.buyDate,
      e.buyPrice])).toEqual([[HELIO_ID, "헬리오시티", GARAK, "30k", "30평대(국평)", "2021-03-15", null]]);
    expect(state().history).toHaveLength(1);
  });

  it("직접 넣은 매입가는 그대로 남긴다", async () => {
    chooseForRun();
    routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_RESULT : realEstateRoutes(path));
    state().setInput({ buyPrice: "2000000000" });
    await state().run();
    expect(historyStub.entries("realestate")[0].buyPrice).toBe("2000000000"); // 012 승인 2026-10-07
  });

  it("수집 중이면 남기지 않는다", async () => {
    chooseForRun();
    routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_COLLECTING : realEstateRoutes(path));
    await state().run();
    expect(historyStub.entries("realestate")).toEqual([]); // 012 승인 2026-10-07
  });

  it("거절되면 남기지 않는다", async () => {
    chooseForRun();
    routeRealEstate((path) => splitPath(path).base === SIMULATION
      ? new ApiError(409, "no_trades_in_area", "거래가 없습니다.", { status: "no_trades_in_area", message: "거래가 없습니다." })
      : realEstateRoutes(path));
    await state().run();
    expect(historyStub.entries("realestate")).toEqual([]); // 012 승인 2026-10-07
  });

  it("다시 실행 — 지역 풀다운까지 그 단지의 지역으로 맞추고 조건을 넣어 곧바로 실행한다", async () => {
    historyStub.seed("realestate", [{ ...helio, buyDate: "2022-06-15", buyPrice: "2100000000" }]); // 012 승인 2026-10-07
    await state().restoreHistory();
    // 지금은 다른 지역(경기도)을 보고 있다.
    useRealEstateStore.setState({
      regions: { sido: null, sgg: GYEONGGI_SGGS.items, umd: null },
      selection: { sido: GYEONGGI, sgg: null, umd: null, complexId: null, area: null },
    });
    const get = routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_RESULT : realEstateRoutes(path));
    await state().rerunHistory(state().history[0].id);

    const s = state();
    expect(s.selection).toEqual({ sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: HELIO_ID, area: "30k" });
    expect(s.regions.sgg).toEqual(SEOUL_SGGS.items);
    expect(s.regions.umd).toEqual(SONGPA_UMDS.items);
    expect(s.complexes).toEqual(GARAK_COMPLEXES);
    expect(s.areas).toEqual(HELIO_AREAS);
    expect(s.input).toEqual({ buyDate: "2022-06-15", buyPrice: "2100000000" });
    const sent = paths(get, SIMULATION);
    expect(sent).toHaveLength(1);
    expect(params(sent[0])).toEqual({ complexId: String(HELIO_ID), area: "30k", buyDate: "2022-06-15",
      buyPrice: "2100000000" });
    expect(s.summary).not.toBeNull();
  });

  it("그 달 시세로 산 이력을 다시 실행하면 매입가 칸이 빈다", async () => {
    historyStub.seed("realestate", [helio]); // 012 승인 2026-10-07
    await state().restoreHistory();
    useRealEstateStore.setState({ input: { buyDate: "2020-01-01", buyPrice: "999" } });
    const get = routeRealEstate((path) => splitPath(path).base === SIMULATION ? SIM_RESULT : realEstateRoutes(path));
    await state().rerunHistory(state().history[0].id);
    expect(state().input).toEqual({ buyDate: "2021-03-15", buyPrice: "" });
    expect(params(paths(get, SIMULATION)[0])).not.toHaveProperty("buyPrice");
  });

  // 012 승인 2026-10-07 — 대역에 심고 목록을 받는다. 지우기는 서버 요청이라 기다린다.
  it("지우면 비교 선택과 비교 선에서도 빠진다", async () => {
    historyStub.seed("realestate", [helio]);
    await state().restoreHistory();
    const [entry] = state().history;
    useRealEstateStore.setState({ selectedHistory: [entry.id],
      comparison: [{ id: entry.id, label: "헬리오시티 30평대(국평)", start: "2021-03-15", series: SERIES }] });
    await state().removeHistoryEntry(entry.id);
    const s = state();
    expect([s.history, s.selectedHistory, s.comparison]).toEqual([[], [], []]);
    expect(historyStub.entries("realestate")).toEqual([]);
  });

  it("고르기는 켜고 끈다", async () => {
    historyStub.seed("realestate", [helio]); // 012 승인 2026-10-07
    await state().restoreHistory();
    const [entry] = state().history;
    state().toggleHistory(entry.id);
    expect(state().selectedHistory).toEqual([entry.id]);
    state().toggleHistory(entry.id);
    expect(state().selectedHistory).toEqual([]);
  });
});

describe("비교 (FR-033)", () => {
  // 012 승인 2026-10-07 — 대역에 심고 목록을 받는다(나중에 심은 것이 맨 앞이다).
  async function seed(...conditions: RealEstateHistoryCondition[]): Promise<void> {
    historyStub.seed("realestate", conditions);
    await state().restoreHistory();
    useRealEstateStore.setState({ selectedHistory: state().history.map((e) => e.id) });
  }

  const twenty: RealEstateHistoryCondition = { ...helio, area: "20", areaLabel: "20평대", buyPrice: "1500000000" };

  it("고른 이력을 지금 다시 계산해 겹친다 — 범례는 단지·평형, 시작은 매입일, 잠정 선이면 (잠정)", async () => {
    await seed(twenty, helio);
    const get = routeRealEstate((path) => params(path).area === "30k" ? PROVISIONAL_SERIES : SERIES);
    await state().compareSelected();
    const sent = get.mock.calls.map(([p]) => String(p));
    expect(sent.every((p) => splitPath(p).base === SERIES_PATH)).toBe(true);
    expect(sent.map(params)).toEqual([
      { complexId: String(HELIO_ID), area: "30k", buyDate: "2021-03-15" },
      { complexId: String(HELIO_ID), area: "20", buyDate: "2021-03-15", buyPrice: "1500000000" },
    ]);
    const { comparison, comparisonError, comparing } = state();
    expect(comparisonError).toBeNull();
    expect(comparing).toBe(false);
    expect(comparison.map((c) => [c.label, c.start])).toEqual([
      ["헬리오시티 30평대(국평) (잠정)", "2021-03-15"], ["헬리오시티 20평대", "2021-03-15"]]);
  });

  it("하나만 골랐으면 비교하지 않는다", async () => {
    await seed(helio);
    const get = routeRealEstate(() => SERIES);
    await state().compareSelected();
    expect(get).not.toHaveBeenCalled();
    expect(state().comparison).toEqual([]);
  });

  it("받지 않은 구간이 있거나 모르는 단지면 이름과 사유를 말하고 나머지로 비교한다", async () => {
    const gone = { ...helio, complexId: 987654, complexName: "옛 단지" };
    await seed(twenty, gone, helio);
    routeRealEstate((path) => {
      const { complexId, area } = params(path);
      if (complexId === "987654") {
        return new ApiError(400, "unknown_complex", "모르는 단지입니다.", { status: "unknown_complex", message: "모르는 단지입니다." });
      }
      return area === "20" ? SIM_COLLECTING : SERIES;
    });
    await state().compareSelected();
    const { comparison, comparisonError } = state();
    expect(comparison.map((c) => c.label)).toEqual(["헬리오시티 30평대(국평)"]);
    expect(comparisonError).toContain("헬리오시티 20평대(아직 받지 못한 구간이 있습니다 — 실행해서 받으세요)");
    expect(comparisonError).toContain("옛 단지 30평대(국평)(알 수 없는 단지)");
    expect(comparisonError).toContain("의 시계열을 불러오지 못했습니다");
  });

  it("그 밖의 실패는 서버의 사유를 이름과 함께 말한다", async () => {
    await seed(twenty, helio);
    routeRealEstate((path) => params(path).area === "20"
      ? new ApiError(409, "region_retired", "시·군·구 코드가 바뀌었습니다.",
        { status: "region_retired", message: "시·군·구 코드가 바뀌었습니다.", lawdCd: "11710" })
      : SERIES);
    await state().compareSelected();
    expect(state().comparison).toHaveLength(1);
    expect(state().comparisonError).toContain("헬리오시티 20평대(시·군·구 코드가 바뀌었습니다.)");
  });
});
