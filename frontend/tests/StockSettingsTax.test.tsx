/**
 * 배당 소득세 국내·해외 (T129) — 006 FR-055, SC-021, ui-wireframes W7. 반복 2026-10-03 #3.
 *
 * 배당 소득세는 국내(기본 15.4%)·해외(기본 15%) 두 칸이다. 화면은 백분율, 계약은 비율이다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StockSettingsForm } from "@/components/settings/StockSettingsForm";
import type { StockSettings } from "@/lib/types";

const DEFAULTS: StockSettings = {
  tradeFeeRate: "0.000150",
  dividendTaxRateDomestic: "0.154000",
  dividendTaxRateForeign: "0.150000",
  isDefault: true,
};

describe("배당 소득세 두 칸", () => {
  it("국내·해외를 따로 백분율로 보인다", () => {
    render(<StockSettingsForm value={DEFAULTS} onSave={vi.fn()} />);
    expect(screen.getByLabelText("배당 소득세 (국내)")).toHaveValue("15.4");
    expect(screen.getByLabelText("배당 소득세 (해외)")).toHaveValue("15");
  });

  it("해외 세율을 바꾸면 세 값을 비율로 넘긴다", async () => {
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const foreign = screen.getByLabelText("배당 소득세 (해외)");
    await userEvent.clear(foreign);
    await userEvent.type(foreign, "10");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith({
      tradeFeeRate: "0.00015",
      dividendTaxRateDomestic: "0.154",
      dividendTaxRateForeign: "0.1",
    });
  });

  it("해외 세율이 범위 밖이면 저장을 막는다", async () => {
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const foreign = screen.getByLabelText("배당 소득세 (해외)");
    await userEvent.clear(foreign);
    await userEvent.type(foreign, "150");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
