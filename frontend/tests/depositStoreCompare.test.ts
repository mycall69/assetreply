/**
 * 예금 이력과 비교 (T031) — 008 FR-037, FR-038, SC-005.
 *
 * - 결과가 나온 실행만 이력에 남는다 — 수집 중(202)이면 아직 결과가 없다
 * - 다시 실행 = 조건을 넣고 곧바로 실행
 * - 비교는 고른 이력을 **지금 다시 계산해서** 겹친다(저장된 결과가 없다). 범례에 투자처·시작일, 잠정이면 "(잠정)"
 * - 빠지는 항목은 조용히 빼지 않는다 — 빼고 비교하면 그 투자처가 진 것으로 읽힌다. 이름과 사유를 함께 말한다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { SimulationSeriesResponse } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { COLLECTING, RESULT } from "./support/depositFixtures";
// 012 승인 2026-10-07 — 012부터 이력은 로컬 DB에 있다. 브라우저 lib 대신 이력 대역에 심고 읽는다(research R12-12).
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));

const SERIES: SimulationSeriesResponse = {
  from: "2020-01-15", to: "2026-10-04", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 2, gaps: [], provisionalFrom: null,
  points: [{ date: "2020-01-15", balance: "10000000", returnRate: "0.000000" },
    { date: "2026-10-04", balance: "11557207", returnRate: "0.155721" }],
};

const query = (path: string) => Object.fromEntries(new URLSearchParams(path.split("?")[1]));

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  useDepositStore.getState().dispose();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" },
    rows: [], summary: null, condition: null, collecting: null, progress: null, error: null, startable: null,
    history: [], selectedHistory: [], comparison: [], comparing: false, comparisonError: null,
    historySaveError: null,
  });
});

describe("이력", () => {
  it("결과가 나온 실행만 남긴다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      path.startsWith("/api/deposit/simulation/series") ? SERIES
        : path.startsWith("/api/deposit/simulation?") ? RESULT : { institutions: [], source: "", basis: "" });
    await useDepositStore.getState().run();
    // 012 승인 2026-10-07
    expect(historyStub.entries("deposit").map((e) => [e.institution, e.start, e.principal])).toEqual([
      ["commercial_bank", "2020-01-15", "10000000"]]);
    expect(useDepositStore.getState().history).toHaveLength(1);
  });

  it("수집 중이면 남기지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useDepositStore.getState().run();
    expect(historyStub.entries("deposit")).toEqual([]); // 012 승인 2026-10-07
  });

  it("다시 실행은 조건을 넣고 곧바로 실행한다", async () => {
    // 012 승인 2026-10-07 — 대역에 심고 목록을 받는다.
    historyStub.seed("deposit", [{ institution: "saemaul", start: "2019-01-15", principal: "5000000" }]);
    await useDepositStore.getState().restoreHistory();
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(RESULT);
    const [entry] = useDepositStore.getState().history;
    await useDepositStore.getState().rerunHistory(entry.id);
    expect(useDepositStore.getState().input).toEqual({
      institution: "saemaul", start: "2019-01-15", principal: "5000000" });
    expect(query(String(get.mock.calls[0][0]))).toEqual({
      institution: "saemaul", start: "2019-01-15", principal: "5000000" });
  });

  // 012 승인 2026-10-07 — 대역에 심고 목록을 받는다. 지우기는 서버 요청이라 기다린다.
  it("지우면 비교 선택과 비교 선에서도 빠진다", async () => {
    historyStub.seed("deposit", [{ institution: "saemaul", start: "2019-01-15", principal: "5000000" }]);
    await useDepositStore.getState().restoreHistory();
    const [entry] = useDepositStore.getState().history;
    useDepositStore.setState({ selectedHistory: [entry.id],
      comparison: [{ id: entry.id, label: "새마을금고", start: "2019-01-15", series: SERIES }] });
    await useDepositStore.getState().removeHistoryEntry(entry.id);
    const state = useDepositStore.getState();
    expect([state.history, state.selectedHistory, state.comparison]).toEqual([[], [], []]);
  });
});

describe("비교", () => {
  // 012 승인 2026-10-07 — 대역에 심고 목록을 받는다(나중에 심은 것이 맨 앞이다).
  async function seed(): Promise<string[]> {
    historyStub.seed("deposit", [{ institution: "savings_bank", start: "2020-01-15", principal: "10000000" },
      { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" }]);
    await useDepositStore.getState().restoreHistory();
    const ids = useDepositStore.getState().history.map((e) => e.id);
    useDepositStore.setState({ selectedHistory: ids });
    return ids;
  }

  it("고른 이력을 지금 다시 계산해 겹치고 범례에 투자처를, 잠정이면 (잠정)을 쓴다", async () => {
    await seed();
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      query(path).institution === "savings_bank" ? { ...SERIES, provisionalFrom: "2026-01-15" } : SERIES);
    await useDepositStore.getState().compareSelected();
    expect(get.mock.calls.every(([p]) => String(p).startsWith("/api/deposit/simulation/series?"))).toBe(true);
    const { comparison, comparisonError } = useDepositStore.getState();
    expect(comparisonError).toBeNull();
    expect(comparison.map((c) => [c.label, c.start])).toEqual([
      ["시중은행", "2020-01-15"], ["저축은행 (잠정)", "2020-01-15"]]);
  });

  it("받지 않은 구간이 있거나 모르는 투자처면 이름과 사유를 말하고 나머지로 비교한다", async () => {
    await seed();
    historyStub.seed("deposit", [{ institution: "kakao_bank", start: "2020-01-15", principal: "1000" }]); // 012 승인 2026-10-07
    await useDepositStore.getState().restoreHistory();
    useDepositStore.setState({ selectedHistory: useDepositStore.getState().history.map((e) => e.id) });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      const { institution } = query(path);
      if (institution === "savings_bank") return COLLECTING;
      if (institution === "kakao_bank") {
        throw new ApiError(400, "unknown_institution", "알 수 없는 투자처입니다.", { status: "unknown_institution" });
      }
      return SERIES;
    });
    await useDepositStore.getState().compareSelected();
    const { comparison, comparisonError } = useDepositStore.getState();
    expect(comparison.map((c) => c.label)).toEqual(["시중은행"]);
    expect(comparisonError).toContain("저축은행(아직 받지 못한 구간이 있습니다 — 실행해서 받으세요)");
    expect(comparisonError).toContain("kakao_bank(알 수 없는 투자처)");
    expect(comparisonError).toContain("의 시계열을 불러오지 못했습니다");
  });
});
