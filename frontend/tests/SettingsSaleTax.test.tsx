/**
 * 설정 화면의 주식 매도 세금 (011 T052) — FR-035, FR-036, ui-wireframes §9.
 *
 * 설정 화면에 "주식 매도 세금" 구역이 있고 `GET/PUT /api/stocks/settings/sale-tax`를 부른다. 저장 뒤 서버가 돌려준 값으로 폼을 다시
 * 그린다(`key` — 다른 설정 구역과 같다). 기존 "주식 매매 조건" 구역은 그대로다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { apiClient } from "@/lib/apiClient";

const DEFAULTS = { saleTaxRateDomestic: "0.0020", capitalGainsRateForeign: "0.22",
  capitalGainsDeductionForeign: "2500000" };

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("설정 화면 — 주식 매도 세금", () => {
  it("구역이 있고 매도 세금 경로로 읽고 저장한 뒤 새 값으로 다시 그린다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/stocks/settings/sale-tax") return { ...DEFAULTS, isDefault: true, defaults: DEFAULTS } as never;
      if (path === "/api/stocks/settings") {
        return { tradeFeeRate: "0.000150", dividendTaxRateDomestic: "0.154000", dividendTaxRateForeign: "0.150000",
          isDefault: true } as never;
      }
      throw new Error(`unexpected ${path}`);
    });
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({
      saleTaxRateDomestic: "0.001500", capitalGainsRateForeign: "0.220000", capitalGainsDeductionForeign: "2500000",
      isDefault: false, defaults: DEFAULTS } as never);
    render(<SettingsPage />);
    expect(await screen.findByRole("heading", { level: 2, name: "주식 매도 세금" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "주식 매매 조건" })).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/api/stocks/settings/sale-tax");

    const box = await screen.findByLabelText("국내 매도 세율");
    await userEvent.clear(box);
    await userEvent.type(box, "0.15");
    const section = screen.getByRole("heading", { level: 2, name: "주식 매도 세금" }).parentElement as HTMLElement;
    await userEvent.click([...section.querySelectorAll("button")].find((b) => b.textContent === "저장")!);
    expect(put).toHaveBeenCalledWith("/api/stocks/settings/sale-tax", { ...DEFAULTS, saleTaxRateDomestic: "0.0015" });
    expect(await screen.findByText("변경됨")).toBeInTheDocument();
    expect(screen.getByLabelText("국내 매도 세율")).toHaveValue("0.15");
  });
});
