/**
 * 부동산 보유세 기준 비율 설정 (T042) — 009 FR-034, US2, ui-wireframes E8, contracts/rest-api `GET`·`PUT /api/realestate/settings`.
 *
 * 화면은 **백분율**(60 %), 계약은 **비율**(`"0.600000"`)이다. 변환은 문자열로 한다(헌법 원칙 VI) — `60.1234 / 100`을 `float`로 하면
 * `0.601234`가 아닌 값이 저장될 수 있다. **0 초과 100 이하**가 아니거나 숫자가 아니면 저장하지 않고 사유를 보인다 — 0이면 보유세가
 * 없는 결과가 그럴듯하게 나온다. 백분율 소수 4자리(비율 6자리)를 넘어도 막는다 — 저장할 때 조용히 반올림되어 넣은 값과 달라진다
 * (008과 같은 자릿수 규칙). 설정 화면에서 부동산 칸은 다른 자산군 칸과 **따로** 저장한다.
 *
 * ## 이 테스트가 전제하는 모듈 (T044가 따른다)
 *
 * - `@/lib/types`: `RealEstateSettings { holdingTaxBaseRatio: DecimalString; isDefault: boolean }`
 * - `@/components/settings/RealEstateSettingsForm` — `export function RealEstateSettingsForm({ value, onSave })`
 *   - `value: RealEstateSettings`, `onSave: (holdingTaxBaseRatio: string) => void` — 비율 문자열(끝의 0을 지운다: 60 → `"0.6"`)
 *   - 칸의 이름(`aria-label`)은 "보유세 기준 비율", 버튼은 "저장"·"기본값으로"(기본값과 다를 때만), 상태 글자 "기본값"·"변경됨"
 *   - 거절 사유는 `role="alert"`
 * - `@/app/settings/page` — 구역 제목(h2) "부동산 보유세 기준 비율", `GET`·`PUT /api/realestate/settings`, 저장 뒤 "저장했습니다. 부동산
 *   화면으로 돌아가면 새 값으로 다시 계산합니다."(E8, 008과 같다), 저장 실패(422)는 그 구역에 서버의 사유
 * - `@/app/realestate/page` — 열 때 `refreshIfRan()`을 부른다(`realEstateStoreSettings.test.ts`)
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RealEstatePage from "@/app/realestate/page";
import SettingsPage from "@/app/settings/page";
import { RealEstateSettingsForm } from "@/components/settings/RealEstateSettingsForm";
import { ApiError, apiClient } from "@/lib/apiClient";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  chooseHelio,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";
import { SIM_RESULT, resetSimulation } from "./support/realEstateSimulationFixtures";

vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));

const DEFAULT = { holdingTaxBaseRatio: "0.600000", isDefault: true };

function renderForm(value = DEFAULT) {
  const onSave = vi.fn();
  render(<RealEstateSettingsForm value={value} onSave={onSave} />);
  return onSave;
}

const box = () => screen.getByLabelText("보유세 기준 비율");

async function typeAndSave(typed: string) {
  await userEvent.clear(box());
  if (typed !== "") await userEvent.type(box(), typed);
  await userEvent.click(screen.getByRole("button", { name: "저장" }));
}

describe("보유세 기준 비율", () => {
  it("비율을 백분율로 보이고 기본값이라는 사실과 뜻을 밝힌다", () => {
    renderForm();
    expect(box()).toHaveValue("60");
    expect(screen.getByText("기본값")).toBeInTheDocument();
    expect(screen.getByText(/실거래 시세의 60%를 공시가격으로/)).toBeInTheDocument();
  });

  it("소수가 있는 비율도 끝의 0을 지운 백분율로 보인다", () => {
    renderForm({ holdingTaxBaseRatio: "0.655000", isDefault: false });
    expect(box()).toHaveValue("65.5");
  });

  it("백분율을 비율 문자열로 저장한다", async () => {
    const onSave = renderForm();
    await typeAndSave("65");
    expect(onSave).toHaveBeenCalledWith("0.65");
  });

  it("백분율 소수 4자리까지는 비율 6자리로 저장한다", async () => {
    const onSave = renderForm();
    await typeAndSave("60.1234");
    expect(onSave).toHaveBeenCalledWith("0.601234");
  });

  it("100%는 저장한다 — 0 초과 100 이하", async () => {
    const onSave = renderForm();
    await typeAndSave("100");
    expect(onSave).toHaveBeenCalledWith("1");
  });

  it("가장 작은 값(0.0001%)도 저장한다", async () => {
    const onSave = renderForm();
    await typeAndSave("0.0001");
    expect(onSave).toHaveBeenCalledWith("0.000001");
  });

  it.each(["0", "101", "100.5", "abc", "-1", "", "1e-3"])(
    "0 초과 100 이하의 숫자가 아니면 저장하지 않고 사유를 보인다 — %s", async (typed) => {
      const onSave = renderForm();
      await typeAndSave(typed);
      expect(onSave).not.toHaveBeenCalled();
      expect(screen.getByRole("alert").textContent).toContain("0 초과 100 이하");
    });

  it("백분율 소수 4자리를 넘으면 저장하지 않는다 — 조용히 반올림하지 않는다", async () => {
    const onSave = renderForm();
    await typeAndSave("60.12345");
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("소수 4자리까지");
  });

  it("고쳐서 다시 저장하면 사유가 사라진다", async () => {
    const onSave = renderForm();
    await typeAndSave("0");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await typeAndSave("70");
    expect(onSave).toHaveBeenCalledWith("0.7");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("기본값과 다르면 기본값(60%)으로 되돌리는 수단이 있다", async () => {
    const onSave = renderForm({ holdingTaxBaseRatio: "0.650000", isDefault: false });
    expect(screen.getByText("변경됨")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "기본값으로" }));
    expect(onSave).toHaveBeenCalledWith("0.6");
    expect(box()).toHaveValue("60");
  });

  it("기본값이면 되돌리는 수단이 없다", () => {
    renderForm();
    expect(screen.queryByRole("button", { name: "기본값으로" })).toBeNull();
  });
});

describe("설정 화면", () => {
  const SECTION = "부동산 보유세 기준 비율";
  const section = () => screen.getByRole("heading", { level: 2, name: SECTION }).parentElement as HTMLElement;

  /** 설정 화면이 부르는 모든 경로. 부동산 칸은 부동산 경로에서만 읽는다. */
  function routeSettings() {
    return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/realestate/settings") return DEFAULT;
      if (path === "/api/deposit/settings") return { interestTaxRate: "0.154000", isDefault: true };
      if (path === "/api/crypto/settings") return { tradeFeeRate: "0.001000", isDefault: true };
      if (path === "/api/stocks/settings") {
        return { tradeFeeRate: "0.000150", dividendTaxRate: "0.154000", dividendTaxRateUs: "0.150000", isDefault: true };
      }
      throw new Error(`unexpected ${path}`);
    });
  }

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("다른 자산군 칸과 따로 있고 부동산 경로에서 읽는다", async () => {
    const get = routeSettings();
    render(<SettingsPage />);
    expect(await screen.findByRole("heading", { level: 2, name: SECTION })).toBeInTheDocument();
    for (const name of ["주식 매매 조건", "가상자산 거래 조건", "예금 이자 소득세"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(get).toHaveBeenCalledWith("/api/realestate/settings");
    expect(await within(section()).findByLabelText("보유세 기준 비율")).toHaveValue("60");
    // 예금 칸과 섞이지 않는다 — 부동산 구역에는 이자 소득세 칸이 없다.
    expect(within(section()).queryByLabelText("이자 소득세")).toBeNull();
  });

  it("부동산 칸을 저장하면 부동산 경로로 비율을 보내고 돌아가면 다시 계산한다고 알린다", async () => {
    routeSettings();
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ holdingTaxBaseRatio: "0.650000", isDefault: false });
    render(<SettingsPage />);
    await screen.findByRole("heading", { level: 2, name: SECTION });
    const field = await within(section()).findByLabelText("보유세 기준 비율");
    await userEvent.clear(field);
    await userEvent.type(field, "65");
    await userEvent.click(within(section()).getByRole("button", { name: "저장" }));
    expect(put).toHaveBeenCalledWith("/api/realestate/settings", { holdingTaxBaseRatio: "0.65" });
    expect(put).toHaveBeenCalledTimes(1);
    expect(await within(section()).findByText(/부동산 화면으로 돌아가면 새 값으로 다시 계산합니다/)).toBeInTheDocument();
    expect(within(section()).getByText("변경됨")).toBeInTheDocument();
  });

  it("서버가 거절하면(422) 그 구역에 사유를 보인다", async () => {
    routeSettings();
    vi.spyOn(apiClient, "put").mockRejectedValue(new ApiError(422, "invalid_setting",
      "보유세 기준 비율은 0 초과 1 이하여야 합니다.",
      { status: "invalid_setting", message: "보유세 기준 비율은 0 초과 1 이하여야 합니다." }));
    render(<SettingsPage />);
    await screen.findByRole("heading", { level: 2, name: SECTION });
    const field = await within(section()).findByLabelText("보유세 기준 비율");
    await userEvent.clear(field);
    await userEvent.type(field, "65");
    await userEvent.click(within(section()).getByRole("button", { name: "저장" }));
    expect((await within(section()).findByRole("alert")).textContent)
      .toContain("보유세 기준 비율은 0 초과 1 이하여야 합니다.");
  });
});

describe("부동산 화면으로 돌아오면 (FR-034)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetRealEstateStore();
    resetSimulation();
  });

  it("실행한 결과가 있으면 화면을 열 때 같은 조건으로 다시 요청한다", async () => {
    const get = routeRealEstate((path) =>
      splitPath(path).base === "/api/realestate/simulation" ? SIM_RESULT : realEstateRoutes(path));
    chooseHelio();
    useRealEstateStore.setState({ summary: SIM_RESULT.summary, rows: SIM_RESULT.rows, condition: SIM_RESULT.condition,
      acquisition: SIM_RESULT.acquisition, resultTarget: { complex: SIM_RESULT.complex, area: SIM_RESULT.area } });
    render(<RealEstatePage />);
    await vi.waitFor(() => expect(get.mock.calls.map(([p]) => splitPath(String(p)).base))
      .toContain("/api/realestate/simulation"));
  });

  it("실행한 적이 없으면 다시 요청하지 않는다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    await screen.findByRole("option", { name: "서울특별시" });
    expect(get.mock.calls.map(([p]) => splitPath(String(p)).base)).not.toContain("/api/realestate/simulation");
  });
});
