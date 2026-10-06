/**
 * 부동산 거주 기간 비율 설정 (010 반복 5, T078) — FR-031, contracts/rest-api `GET`·`PUT /api/realestate/settings/residence`.
 *
 * - 칸 `거주 기간 비율`(백분율, 0~100, 기본 100) — 거주 기간 = 보유 기간 × 이 비율. 비과세의 거주 2년 요건과 장기보유특별공제에 쓴다
 * - 저장은 비율 문자열(50 → "0.5"). 범위 밖·소수 5자리 이상은 저장하지 않고 사유(`role="alert"`)
 * - 설정 화면에 **따로 된 구역**(h2 "부동산 거주 기간 비율") — 보유세 기준 비율 구역과 상태를 공유하지 않는다
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { RealEstateResidenceForm } from "@/components/settings/RealEstateResidenceForm";
import { apiClient } from "@/lib/apiClient";

const DEFAULT = { residenceRatio: "1.000000", isDefault: true };

function renderForm(value = DEFAULT) {
  const onSave = vi.fn();
  render(<RealEstateResidenceForm value={value} onSave={onSave} />);
  return onSave;
}

const box = () => screen.getByLabelText("거주 기간 비율");

async function typeAndSave(typed: string) {
  await userEvent.clear(box());
  if (typed !== "") await userEvent.type(box(), typed);
  await userEvent.click(screen.getByRole("button", { name: "저장" }));
}

describe("거주 기간 비율", () => {
  it("백분율로 보이고 기본값과 뜻을 밝힌다", () => {
    renderForm();
    expect(box()).toHaveValue("100");
    expect(screen.getByText("기본값")).toBeInTheDocument();
    expect(screen.getByText(/거주 기간 = 보유 기간 × 이 비율/)).toBeInTheDocument();
  });

  it("백분율을 비율 문자열로 저장한다 — 0도 된다", async () => {
    const onSave = renderForm();
    await typeAndSave("50");
    expect(onSave).toHaveBeenLastCalledWith("0.5");
    await typeAndSave("0");
    expect(onSave).toHaveBeenLastCalledWith("0");
  });

  it.each([["101", "0 이상 100 이하"], ["-1", "0 이상 100 이하"], ["50.12345", "소수 4자리까지"], ["", "0 이상 100 이하"]])(
    "%s는 저장하지 않고 사유를 보인다", async (typed, reason) => {
      const onSave = renderForm();
      await typeAndSave(typed);
      expect(onSave).not.toHaveBeenCalled();
      expect(screen.getByRole("alert").textContent).toContain(reason);
    });

  it("기본값과 다르면 '기본값으로'가 100%로 되돌린다", async () => {
    const onSave = renderForm({ residenceRatio: "0.500000", isDefault: false });
    expect(box()).toHaveValue("50");
    expect(screen.getByText("변경됨")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "기본값으로" }));
    expect(onSave).toHaveBeenCalledWith("1");
  });
});

describe("설정 화면", () => {
  const SECTION = "부동산 거주 기간 비율";
  const section = () => screen.getByRole("heading", { level: 2, name: SECTION }).parentElement as HTMLElement;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/realestate/settings/residence") return DEFAULT as never;
      if (path === "/api/realestate/settings") return { holdingTaxBaseRatio: "0.600000", isDefault: true } as never;
      if (path === "/api/deposit/settings") return { interestTaxRate: "0.154000", isDefault: true } as never;
      if (path === "/api/crypto/settings") return { tradeFeeRate: "0.000500", isDefault: true } as never;
      if (path === "/api/stocks/settings") {
        return { tradeFeeRate: "0.000150", dividendTaxRate: "0.154000", dividendTaxRateUs: "0.150000", isDefault: true } as never;
      }
      throw new Error(`unexpected ${path}`);
    });
  });

  it("따로 된 구역에서 읽고 저장하면 그 경로로 보낸다", async () => {
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ residenceRatio: "0.500000", isDefault: false } as never);
    render(<SettingsPage />);
    await screen.findByRole("heading", { level: 2, name: SECTION });
    const field = await within(section()).findByLabelText("거주 기간 비율");
    expect(field).toHaveValue("100");
    expect(screen.getByRole("heading", { level: 2, name: "부동산 보유세 기준 비율" })).toBeInTheDocument();
    await userEvent.clear(field);
    await userEvent.type(field, "50");
    await userEvent.click(within(section()).getByRole("button", { name: "저장" }));
    expect(put).toHaveBeenCalledWith("/api/realestate/settings/residence", { residenceRatio: "0.5" });
    expect(await within(section()).findByText(/부동산 화면으로 돌아가면 새 값으로 다시 계산합니다/)).toBeInTheDocument();
  });
});
