/**
 * 주식 매도 세금 설정 (011 T052) — FR-035~FR-037, SC-007, ui-wireframes §9.
 *
 * - 세 칸 — 국내 매도 세율 · 해외 양도소득세율 · 해외 연간 기본공제. 칸마다 기본값과 근거(현행 세법)를 보인다
 * - 화면은 **백분율**, 계약은 **비율**이다. 변환은 문자열로 한다(헌법 원칙 VI) — `"0.0020"` ↔ `"0.2"`, `"0.22"` ↔ `"22"`
 * - 검증은 서버와 같다 — 세율 0 이상 100 미만·소수 4자리(퍼센트) 이하, 공제 0 이상의 정수(원). 실패하면 저장하지 않고 알린다
 * - "기본값으로"는 서버가 준 `defaults`를 보낸다. 기본값이면 "기본값", 아니면 "변경됨"이다
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StockSaleTaxForm } from "@/components/settings/StockSaleTaxForm";
import type { SaleTaxSettings } from "@/lib/types";

const DEFAULTS = { saleTaxRateDomestic: "0.0020", capitalGainsRateForeign: "0.22",
  capitalGainsDeductionForeign: "2500000" };
const DEFAULT: SaleTaxSettings = { ...DEFAULTS, isDefault: true, defaults: DEFAULTS };

async function replace(label: string, text: string) {
  const box = screen.getByLabelText(label);
  await userEvent.clear(box);
  if (text !== "") await userEvent.type(box, text);
}

describe("주식 매도 세금 설정", () => {
  it("세 칸을 백분율·원으로 보이고 기본값과 근거를 밝힌다", () => {
    render(<StockSaleTaxForm value={DEFAULT} onSave={vi.fn()} />);
    expect(screen.getByLabelText("국내 매도 세율")).toHaveValue("0.2");
    expect(screen.getByLabelText("해외 양도소득세율")).toHaveValue("22");
    expect(screen.getByLabelText("해외 연간 기본공제")).toHaveValue("2,500,000");
    expect(screen.getByText(/기본 0\.20% — 2026년 증권거래세 실질 세율/)).toBeInTheDocument();
    expect(screen.getByText(/기본 22% — 지방소득세 포함/)).toBeInTheDocument();
    expect(screen.getByText(/기본 2,500,000원 — 그해 다른 해외 매도가 없다고 가정/)).toBeInTheDocument();
    expect(screen.getByText("기본값")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "기본값으로" })).toBeNull();
  });

  it("백분율을 비율 문자열로, 공제를 원 문자열로 저장한다", async () => {
    const onSave = vi.fn();
    render(<StockSaleTaxForm value={DEFAULT} onSave={onSave} />);
    await replace("국내 매도 세율", "0.15");
    await replace("해외 양도소득세율", "20");
    await replace("해외 연간 기본공제", "0");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith({ saleTaxRateDomestic: "0.0015", capitalGainsRateForeign: "0.2",
      capitalGainsDeductionForeign: "0" });
  });

  it.each([["국내 매도 세율", "100"], ["국내 매도 세율", "abc"], ["해외 양도소득세율", "0.12345"],
    ["해외 양도소득세율", ""]])("세율이 범위 밖이거나 자릿수가 넘으면 저장하지 않는다 — %s %s", async (label, text) => {
    const onSave = vi.fn();
    render(<StockSaleTaxForm value={DEFAULT} onSave={onSave} />);
    await replace(label, text);
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("0 이상 100 미만");
  });

  it.each(["100.5", "-1", ""])("공제가 0 이상의 정수가 아니면 저장하지 않는다 — %s", async (text) => {
    const onSave = vi.fn();
    render(<StockSaleTaxForm value={DEFAULT} onSave={onSave} />);
    await replace("해외 연간 기본공제", text);
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("0 이상의 정수");
  });

  it("바꾼 값이면 변경됨이고 기본값으로는 서버의 defaults를 보낸다", async () => {
    const onSave = vi.fn();
    render(<StockSaleTaxForm value={{ saleTaxRateDomestic: "0.001500", capitalGainsRateForeign: "0.220000",
      capitalGainsDeductionForeign: "0", isDefault: false, defaults: DEFAULTS }} onSave={onSave} />);
    expect(screen.getByText("변경됨")).toBeInTheDocument();
    expect(screen.getByLabelText("국내 매도 세율")).toHaveValue("0.15");
    await userEvent.click(screen.getByRole("button", { name: "기본값으로" }));
    expect(onSave).toHaveBeenCalledWith(DEFAULTS);
  });
});
