/**
 * 주식 설정 (T058) — 005 FR-015, FR-016, FR-017.
 *
 * **설정이 바뀌면 이미 표시된 결과가 새 값 기준으로 다시 제시되어야 한다.**
 * 갱신되지 않으면 화면은 정상으로 보이면서 낡은 값을 보여주고, 사용자는 새 설정이
 * 반영된 결과로 읽는다 (002 FR-034와 같은 계열).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StockSettingsForm } from "@/components/settings/StockSettingsForm";
import type { StockSettings } from "@/lib/types";

// 006 FR-055(반복 2026-10-03 #3, T129) — 배당 소득세가 국내·해외 두 칸이 되었다. 이 파일은 국내 칸을 본다.
const DEFAULTS: StockSettings = {
  tradeFeeRate: "0.000150",
  dividendTaxRateDomestic: "0.154000",
  dividendTaxRateForeign: "0.150000",
  isDefault: true,
};

describe("주식 설정", () => {
  it("두 항목을 백분율로 보여준다", () => {
    render(<StockSettingsForm value={DEFAULTS} onSave={vi.fn()} />);
    expect(screen.getByLabelText(/매매 수수료/)).toHaveValue("0.015");
    expect(screen.getByLabelText("배당 소득세 (국내)")).toHaveValue("15.4");
  });

  it("기본값이면 그 사실을 알린다", () => {
    // 002 FR-033과 같은 규약 — 기본값에서 벗어났는지 사용자가 알아야 한다.
    render(<StockSettingsForm value={DEFAULTS} onSave={vi.fn()} />);
    expect(screen.getByText(/기본값/)).toBeInTheDocument();
  });

  it("기본값과 다르면 다르게 말한다", () => {
    render(
      <StockSettingsForm
        value={{ ...DEFAULTS, tradeFeeRate: "0.000300", isDefault: false }}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText(/변경됨/)).toBeInTheDocument();
  });

  it("저장하면 비율로 환산해 넘긴다", async () => {
    // 화면은 백분율로 받고 계약은 비율로 받는다. 변환을 한 곳에 둔다.
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const fee = screen.getByLabelText(/매매 수수료/);
    await userEvent.clear(fee);
    await userEvent.type(fee, "0.03");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith({
      tradeFeeRate: "0.0003",
      dividendTaxRateDomestic: "0.154",
      dividendTaxRateForeign: "0.15",
    });
  });

  it("100% 이상은 저장을 막는다", async () => {
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const tax = screen.getByLabelText("배당 소득세 (국내)");
    await userEvent.clear(tax);
    await userEvent.type(tax, "150");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("숫자가 아니면 저장을 막는다", async () => {
    // 조용히 0으로 떨어지면 수수료·세금이 사라지는데 오류가 없다.
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const fee = screen.getByLabelText(/매매 수수료/);
    await userEvent.clear(fee);
    await userEvent.type(fee, "공짜");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("0은 허용한다", async () => {
    // 수수료 0%는 현실적인 설정이고 참조 구현과 대조할 때도 쓴다.
    const onSave = vi.fn();
    render(<StockSettingsForm value={DEFAULTS} onSave={onSave} />);
    const fee = screen.getByLabelText(/매매 수수료/);
    await userEvent.clear(fee);
    await userEvent.type(fee, "0");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ tradeFeeRate: "0" }),
    );
  });
});
