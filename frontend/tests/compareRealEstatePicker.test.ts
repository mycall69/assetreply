/**
 * 비교 화면의 부동산 고르기 (013 T016) — FR-003, research R13-9.
 *
 * 고르기 흐름(시·도 → 시·군·구 → 법정동 → 단지 → 평형, 목록 202·진행)은 부동산 메뉴와 **같은 코드**다. 비교 화면은 같은 상태
 * 생성기로 만든 **따로 된 인스턴스**를 쓴다 — 메뉴 스토어를 그대로 쓰면 비교에서 단지를 고를 때 메뉴의 결과와 진행 중 실행이
 * 지워진다(FR-003 실패 양상 — 설계 중 확인). 진행 구독도 인스턴스마다다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import { useCompareRealEstatePicker } from "@/stores/compareRealEstatePicker";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  AREAS_COLLECTING,
  GARAK,
  HELIO_ID,
  RESULT_PLACEHOLDER,
  SEOUL,
  SONGPA,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";

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

function resetPicker(): void {
  useCompareRealEstatePicker.getState().dispose();
  useCompareRealEstatePicker.setState(useCompareRealEstatePicker.getInitialState(), true);
}

beforeEach(() => {
  vi.restoreAllMocks();
  progress.subs.length = 0;
  resetRealEstateStore();
  resetPicker();
});

async function pickHelio(): Promise<void> {
  const picker = useCompareRealEstatePicker.getState();
  await picker.loadSidos();
  await picker.selectSido(SEOUL);
  await picker.selectSgg(SONGPA);
  await picker.selectUmd(GARAK);
  await picker.selectComplex(HELIO_ID);
  picker.selectArea("30k");
}

describe("비교 인스턴스", () => {
  it("메뉴와 같은 차례로 목록을 받는다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await pickHelio();
    const bases = get.mock.calls.map(([path]) => splitPath(path as string).base);
    expect(bases).toEqual([
      "/api/realestate/regions", "/api/realestate/regions", "/api/realestate/regions",
      "/api/realestate/complexes", `/api/realestate/complexes/${HELIO_ID}/areas`,
    ]);
    const { selection, areas } = useCompareRealEstatePicker.getState();
    expect(selection).toEqual({ sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: HELIO_ID, area: "30k" });
    expect(areas?.buckets.length).toBeGreaterThan(0);
  });

  it("비교에서 고르면 메뉴의 고르기와 결과는 그대로다", async () => {
    routeRealEstate(realEstateRoutes);
    useRealEstateStore.setState({
      selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: 99, area: "20" },
      ...RESULT_PLACEHOLDER,
    });
    await pickHelio();
    const menu = useRealEstateStore.getState();
    expect(menu.selection).toEqual({ sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: 99, area: "20" });
    expect(menu.summary).toEqual(RESULT_PLACEHOLDER.summary);
    expect(menu.rows).toEqual(RESULT_PLACEHOLDER.rows);
  });

  it("메뉴에서 고르면 비교의 고르기는 그대로다", async () => {
    routeRealEstate(realEstateRoutes);
    await pickHelio();
    await useRealEstateStore.getState().loadSidos();
    await useRealEstateStore.getState().selectSido(SEOUL);
    expect(useCompareRealEstatePicker.getState().selection.area).toBe("30k");
  });

  it("진행 구독이 인스턴스마다다 — 메뉴를 닫아도 비교의 구독은 남는다", async () => {
    routeRealEstate((path) => (path.endsWith(`/complexes/${HELIO_ID}/areas`) ? AREAS_COLLECTING : realEstateRoutes(path)));
    await pickHelio();
    const watching = progress.subs.filter((s) => s.active);
    expect(watching.length).toBeGreaterThan(0);
    useRealEstateStore.getState().dispose();
    expect(progress.subs.filter((s) => s.active)).toEqual(watching);
    expect(useCompareRealEstatePicker.getState().areasCollecting).not.toBeNull();
    expect(useRealEstateStore.getState().areasCollecting).toBeNull();
  });
});
