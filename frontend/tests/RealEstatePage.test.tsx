/**
 * 부동산 화면 (T020) — 009 FR-001~FR-004, FR-007, FR-036, SC-007, ui-wireframes E1·E2.
 *
 * 주식·가상자산·예금과 같은 구성이되 **종목 검색 대신 지역 풀다운 셋 → 단지 풀다운 → 평형 라디오 일곱**이다. 원금은 원화만이라
 * **통화 칸이 없다**(FR-007). 화면 아래에 출처를 밝힌다(FR-036, 헌법 원칙 II). 매입일·매입가·결과는 Phase 4(T034·T039)가 더한다.
 *
 * ## 이 테스트가 전제하는 모듈 (T026이 따른다)
 *
 * `@/app/realestate/page` — `export default function RealEstatePage()`. 열 때 `loadSidos()`, 떠날 때 `dispose()`. `RegionPicker`·
 * `ComplexPicker`·`AreaBucketPicker`를 스토어(`useRealEstateStore`)에 잇는다. 평형 칸의 `waitingForTrades`는 고른 동의 실거래를
 * 다 받지 않았을 때(`complexes.trades.state`가 `collected`가 아님, 또는 평형 202) 참이다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RealEstatePage from "@/app/realestate/page";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  COLLECTING_TRADES,
  GARAK,
  REGION_COLLECTING,
  SEOUL,
  SEOUL_SGGS,
  SIDOS,
  SONGPA,
  SONGPA_UMDS,
  complexesWith,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";

vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));

const SOURCE = "출처: 국토교통부 아파트 매매 실거래가 공개 자료(공공데이터포털) · 행정안전부 법정동코드 · 공동주택관리정보시스템";

const box = (name: string) => screen.getByRole("combobox", { name });

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
});

describe("부동산 화면", () => {
  it("제목과 설명", () => {
    routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    expect(screen.getByRole("heading", { name: "부동산 투자 시뮬레이션" })).toBeInTheDocument();
    expect(screen.getByText(/그때 이 아파트를 샀다면 — 취득 비용과 해마다 낸 보유세를 뺀 지금까지의 성과/))
      .toBeInTheDocument();
  });

  it("열면 시·도 목록을 받아 지역 풀다운에 채운다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    expect(await screen.findByRole("option", { name: "서울특별시" })).toBeInTheDocument();
    const regions = get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === "/api/realestate/regions");
    expect(regions).toHaveLength(1);
  });

  it("풀다운은 시·도 · 시·군·구 · 동 · 단지 넷이고 평형은 라디오 묶음이다 — 통화 칸이 없다(FR-007)", async () => {
    routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    await screen.findByRole("option", { name: "서울특별시" });
    for (const name of ["시·도", "시·군·구", "동", "단지"]) expect(box(name)).toBeInTheDocument();
    expect(screen.getAllByRole("combobox")).toHaveLength(4);
    expect(screen.getByRole("group", { name: "평형" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/통화/)).toBeNull();
  });

  it("화면 아래에 출처를 밝힌다(FR-036)", () => {
    routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    expect(screen.getByText(SOURCE)).toBeInTheDocument();
  });

  it("행정구역을 처음 받는 중이면 지역 자리에 진행을 보인다", async () => {
    routeRealEstate((path) => splitPath(path).base === "/api/realestate/regions" ? REGION_COLLECTING : undefined);
    render(<RealEstatePage />);
    expect(await screen.findByText(/행정구역 목록을 받고 있습니다/)).toBeInTheDocument();
  });

  it("실거래를 받는 중이면 평형 칸이 받은 뒤 고를 수 있다고 안내한다", () => {
    routeRealEstate(realEstateRoutes);
    useRealEstateStore.setState({
      regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
      selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: null, area: null },
      complexes: complexesWith({ trades: COLLECTING_TRADES }),
    });
    render(<RealEstatePage />);
    expect(screen.getByText(/실거래를 받은 뒤 고를 수 있습니다/)).toBeInTheDocument();
    expect(screen.getByText(/120 \/ 250개월/)).toBeInTheDocument();
  });
});

describe("네 번의 풀다운 선택 (SC-007)", () => {
  it("시·도부터 단지까지 넷을 골라 평형까지 고르고, 시·도를 바꾸면 아래가 모두 빈다", async () => {
    routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);

    await screen.findByRole("option", { name: "서울특별시" });
    await userEvent.selectOptions(box("시·도"), "서울특별시");
    await screen.findByRole("option", { name: "송파구" });
    await userEvent.selectOptions(box("시·군·구"), "송파구");
    await screen.findByRole("option", { name: "가락동" });
    await userEvent.selectOptions(box("동"), "가락동");
    // 가락동 단지 목록에 헬리오시티가 입주년도와 함께 있다.
    await screen.findByRole("option", { name: "헬리오시티 · 2018년 입주 · 9,510세대" });
    await userEvent.selectOptions(box("단지"), "헬리오시티 · 2018년 입주 · 9,510세대");
    // 평형 구분을 받은 뒤의(거래 수가 붙은) 항목을 누른다 — 받기 전의 비활성 항목은 눌러도 고를 수 없다.
    const national = await screen.findByRole("radio", { name: /^30평대\(국평\)\s*301건$/ });
    await userEvent.click(national);
    expect(screen.getByRole("radio", { name: /^30평대\(국평\)/ })).toBeChecked();

    await userEvent.selectOptions(box("시·도"), "경기도");
    await screen.findByRole("option", { name: "수원시 장안구" });
    // 고르지 않은 풀다운은 빈 값이다 — 첫 항목이 골라진 것처럼 보이면 하위 선택이 남은 것과 같다.
    expect(box("시·도")).toHaveValue("4100000000");
    expect(box("시·군·구")).toHaveValue("");
    expect(box("동")).toBeDisabled();
    expect(box("단지")).toBeDisabled();
    expect(screen.queryAllByRole("radio").filter((r) => (r as HTMLInputElement).checked)).toEqual([]);
    expect(screen.queryByRole("option", { name: /헬리오시티/ })).toBeNull();
  });
});
