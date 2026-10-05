/**
 * 지역 고르기 (T020) — 009 FR-002, FR-015, SC-007, ui-wireframes E1·E2·E9·접근성.
 *
 * - 지역은 **풀다운 셋**(시·도 → 시·군·구 → 동)이다. 각 `select`에 `label`이 붙는다. 상위를 고르기 전에는 하위를 쓸 수 없다
 * - 고르지 않은 풀다운의 값은 **빈 값**이다 — 첫 항목이 골라진 것처럼 보이면 상위를 바꾼 뒤 하위가 남은 것과 같다(SC-007)
 * - 행정구역을 처음 받는 중이면 풀다운 자리에 "행정구역 목록을 받고 있습니다 | 3 / 21쪽"
 * - **그 수집이 실패하면** 풀다운 자리에 종류별 문구·할 일(`role="alert"`)을 보이고 풀다운은 비활성이다(FR-015). 빈 풀다운만 두면
 *   사용자는 고를 지역이 없다고 읽는다. 받아 둔 목록이 있으면(30일 갱신 실패) 그 목록을 쓰고 경고하지 않는다
 * - **상위를 바꾸면 하위를 비운다**(SC-007) — 시·도를 바꾸면 시·군·구·동·단지·평형·결과, 동을 바꾸면 단지·평형·결과. 스토어로 본다
 *
 * ## 이 테스트가 전제하는 모듈 (T026이 따른다)
 *
 * `@/components/realestate/RegionPicker` — `export function RegionPicker(props)`
 * - `regions: { sido: RealEstateRegion[] | null; sgg: RealEstateRegion[] | null; umd: RealEstateRegion[] | null }` — 받기 전 `null`
 * - `selection: { sido: string | null; sgg: string | null; umd: string | null }`
 * - `onSelect: (level: RealEstateRegionLevel, code: string) => void`
 * - `collecting: RealEstateRegionCollecting | null` — 행정구역 202
 * - `progress: RealEstateProgressSnapshot | null` — 그 작업의 진행(받은 쪽 / 쪽 수)
 * - `failure: RealEstateFailure | null` — 그 작업의 실패(종류·사유)
 *
 * 스토어(`useRealEstateStore`)의 상태·동작은 `realEstateStore.test.ts`의 머리말을 본다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegionPicker } from "@/components/realestate/RegionPicker";
import type { RealEstateFailureKind } from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  FAILURE_FRAGMENTS,
  FAILURE_KINDS,
  GANGNAM,
  GANGNAM_UMDS,
  GARAK,
  GARAK_COMPLEXES,
  GYEONGGI,
  GYEONGGI_SGGS,
  HELIO_AREAS,
  HYUNDAI_OLD,
  MUNJEONG,
  MUNJEONG_COMPLEXES,
  REGION_COLLECTING,
  SEOUL,
  SEOUL_SGGS,
  SIDOS,
  SONGPA,
  SONGPA_UMDS,
  chooseHelio,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
} from "./support/realEstateFixtures";

vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));

type Props = ComponentProps<typeof RegionPicker>;

const EMPTY: Props = {
  regions: { sido: null, sgg: null, umd: null },
  selection: { sido: null, sgg: null, umd: null },
  onSelect: () => undefined,
  collecting: null,
  progress: null,
  failure: null,
};

function renderPicker(over: Partial<Props> = {}) {
  const onSelect = vi.fn();
  render(<RegionPicker {...EMPTY} onSelect={onSelect} {...over} />);
  return onSelect;
}

const select = (name: string) => screen.getByRole("combobox", { name });
/** 고를 수 있는 항목의 이름 — 빈 값(안내) 항목은 뺀다. */
const choices = (name: string) =>
  within(select(name)).getAllByRole("option")
    .filter((o) => (o as HTMLOptionElement).value !== "")
    .map((o) => o.textContent);

const LOADED: Partial<Props> = { regions: { sido: SIDOS.items, sgg: null, umd: null } };

describe("풀다운 셋", () => {
  it("label이 붙은 select 셋이다 — 시·도 · 시·군·구 · 동", () => {
    renderPicker(LOADED);
    for (const name of ["시·도", "시·군·구", "동"]) {
      expect(screen.getByLabelText(name).tagName).toBe("SELECT");
    }
    expect(screen.getAllByRole("combobox")).toHaveLength(3);
  });

  it("시·도는 받은 순서(가나다)대로 보이고, 고르기 전에는 빈 값이다", () => {
    renderPicker(LOADED);
    expect(choices("시·도")).toEqual(["강원특별자치도", "경기도", "서울특별시"]);
    expect(select("시·도")).toHaveValue("");
  });

  it("상위를 고르기 전에는 하위 풀다운을 쓸 수 없다", () => {
    renderPicker(LOADED);
    expect(select("시·도")).toBeEnabled();
    expect(select("시·군·구")).toBeDisabled();
    expect(select("동")).toBeDisabled();
  });

  it("고른 값을 보인다", () => {
    renderPicker({
      regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
      selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK },
    });
    expect(select("시·도")).toHaveValue(SEOUL);
    expect(select("시·군·구")).toHaveValue(SONGPA);
    expect(select("동")).toHaveValue(GARAK);
    expect(choices("동")).toEqual(["가락동", "문정동"]);
  });

  it("고르면 그 단계와 코드를 알린다", async () => {
    const onSelect = renderPicker({
      regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
      selection: { sido: SEOUL, sgg: SONGPA, umd: null },
    });
    await userEvent.selectOptions(select("시·도"), "경기도");
    expect(onSelect).toHaveBeenLastCalledWith("sido", GYEONGGI);
    await userEvent.selectOptions(select("시·군·구"), "강남구");
    expect(onSelect).toHaveBeenLastCalledWith("sgg", GANGNAM);
    await userEvent.selectOptions(select("동"), "가락동");
    expect(onSelect).toHaveBeenLastCalledWith("umd", GARAK);
  });
});

describe("처음 목록 진행", () => {
  it("행정구역을 처음 받는 중이면 받은 쪽 / 쪽 수를 보인다", () => {
    renderPicker({
      collecting: REGION_COLLECTING,
      progress: { jobId: 7, kind: "region", target: "regions", status: "running", done: 3, total: 21 },
    });
    const status = screen.getByRole("status").textContent ?? "";
    expect(status).toContain("행정구역 목록을 받고 있습니다");
    expect(status).toContain("3 / 21쪽");
  });

  it("진행이 아직 없으면 숫자 없이 받는 중이라고만 말한다 — 0 / 0은 멈춘 것처럼 읽힌다", () => {
    renderPicker({ collecting: REGION_COLLECTING });
    const status = screen.getByRole("status").textContent ?? "";
    expect(status).toContain("행정구역 목록을 받고 있습니다");
    expect(status).not.toContain("0 / 0");
  });
});

describe("행정구역 수집 실패 (FR-015)", () => {
  it.each<RealEstateFailureKind>(FAILURE_KINDS)(
    "지역 자리에 받지 못한 사실과 종류별 문구·할 일을 보이고 풀다운을 막는다 — %s", (kind) => {
      renderPicker({ failure: { kind, reason: "출처가 준 사유" } });
      const alert = screen.getByRole("alert").textContent ?? "";
      expect(alert).toContain("행정구역 목록을 받지 못했습니다");
      for (const fragment of FAILURE_FRAGMENTS[kind]) expect(alert).toContain(fragment);
      expect(select("시·도")).toBeDisabled();
      for (const box of screen.getAllByRole("combobox")) expect(box).toBeDisabled();
    });

  it("종류마다 다른 말을 한다 — 인증 실패와 연결 실패의 문구가 섞이지 않는다", () => {
    renderPicker({ failure: { kind: "auth", reason: "인증키 오류" } });
    const alert = screen.getByRole("alert").textContent ?? "";
    expect(alert).not.toContain(FAILURE_FRAGMENTS.network[0]);
    expect(alert).not.toContain(FAILURE_FRAGMENTS.rate_limited[0]);
  });

  it("받아 둔 목록이 있으면 경고하지 않고 풀다운을 쓸 수 있다", () => {
    // 30일 갱신이 실패해도 서버는 받아 둔 목록으로 200을 준다 — 화면은 실패를 모른다.
    renderPicker(LOADED);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(select("시·도")).toBeEnabled();
  });
});

describe("상위를 바꾸면 하위를 비운다 (SC-007)", () => {
  const store = () => useRealEstateStore.getState();

  beforeEach(() => {
    vi.restoreAllMocks();
    resetRealEstateStore();
    routeRealEstate(realEstateRoutes);
    chooseHelio();
  });

  it("시·도를 바꾸면 시·군·구·동·단지·평형·결과가 빈다", async () => {
    await store().selectSido(GYEONGGI);
    const state = store();
    expect(state.selection).toEqual({ sido: GYEONGGI, sgg: null, umd: null, complexId: null, area: null });
    expect(state.regions.sgg).toEqual(GYEONGGI_SGGS.items);
    expect(state.regions.umd).toBeNull();
    expect(state.complexes).toBeNull();
    expect(state.areas).toBeNull();
    expect(state.summary).toBeNull();
    expect(state.rows).toEqual([]);
  });

  it("시·군·구를 바꾸면 동·단지·평형·결과가 비고 시·도는 남는다", async () => {
    await store().selectSgg(GANGNAM);
    const state = store();
    expect(state.selection).toEqual({ sido: SEOUL, sgg: GANGNAM, umd: null, complexId: null, area: null });
    expect(state.regions.sgg).toEqual(SEOUL_SGGS.items);
    expect(state.regions.umd).toEqual(GANGNAM_UMDS.items);
    expect(state.complexes).toBeNull();
    expect(state.areas).toBeNull();
    expect(state.summary).toBeNull();
    expect(state.rows).toEqual([]);
  });

  it("동을 바꾸면 단지·평형·결과가 비고 시·도·시·군·구는 남는다", async () => {
    await store().selectUmd(MUNJEONG);
    const state = store();
    expect(state.selection).toEqual({ sido: SEOUL, sgg: SONGPA, umd: MUNJEONG, complexId: null, area: null });
    expect(state.regions.umd).toEqual(SONGPA_UMDS.items);
    expect(state.complexes).toEqual(MUNJEONG_COMPLEXES);
    expect(state.areas).toBeNull();
    expect(state.summary).toBeNull();
    expect(state.rows).toEqual([]);
  });

  it("단지를 바꾸면 평형·결과가 빈다", async () => {
    // 고른 헬리오시티에서 다른 단지로 — 같은 값을 다시 고르는 것은 바꾼 것이 아니다.
    const other = HYUNDAI_OLD.complexId;
    vi.restoreAllMocks();
    routeRealEstate((path) => path === `/api/realestate/complexes/${other}/areas`
      ? { ...HELIO_AREAS, complexId: other } : realEstateRoutes(path));
    await store().selectComplex(other);
    const state = store();
    expect(state.selection).toEqual({ sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: other, area: null });
    expect(state.complexes).toEqual(GARAK_COMPLEXES);
    expect(state.summary).toBeNull();
    expect(state.rows).toEqual([]);
  });
});
