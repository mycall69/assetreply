/**
 * 가상자산 거래 수수료율 설정 (T028) — 007 FR-032, FR-033, ui-wireframes C6.
 *
 * 화면은 **백분율**, 계약은 **비율**이다. 변환을 한 곳에 두고 문자열로 한다(헌법 원칙 VI) — `0.1 / 100`을 `float`로 하면
 * `0.001`이 아니라 `0.0010000000000000002`가 될 수 있다. 0 이상 100 미만이 아니면 저장하지 않는다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CryptoSettingsForm } from "@/components/settings/CryptoSettingsForm";

const DEFAULT = { tradeFeeRate: "0.001000", isDefault: true };

describe("가상자산 거래 수수료", () => {
  it("비율을 백분율로 보인다", () => {
    render(<CryptoSettingsForm value={DEFAULT} onSave={vi.fn()} />);
    expect(screen.getByLabelText("거래 수수료")).toHaveValue("0.1");
    expect(screen.getByText("기본값")).toBeInTheDocument();
  });

  it("백분율을 비율 문자열로 저장한다", async () => {
    const onSave = vi.fn();
    render(<CryptoSettingsForm value={DEFAULT} onSave={onSave} />);
    const box = screen.getByLabelText("거래 수수료");
    await userEvent.clear(box);
    await userEvent.type(box, "0.25");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith("0.0025");
  });

  it.each(["abc", "100", "-1", "", "1e-3"])("범위 밖이나 숫자가 아니면 저장하지 않는다 — %s", async (typed) => {
    const onSave = vi.fn();
    render(<CryptoSettingsForm value={DEFAULT} onSave={onSave} />);
    const box = screen.getByLabelText("거래 수수료");
    await userEvent.clear(box);
    if (typed !== "") await userEvent.type(box, typed);
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("0 이상 100 미만");
  });

  it("기본값과 다르면 기본값으로 되돌리는 수단이 있다", async () => {
    const onSave = vi.fn();
    render(<CryptoSettingsForm value={{ tradeFeeRate: "0.002000", isDefault: false }} onSave={onSave} />);
    expect(screen.getByText("변경됨")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "기본값으로" }));
    expect(onSave).toHaveBeenCalledWith("0.001");
  });

  it("기본값이면 되돌리는 수단이 없다", () => {
    render(<CryptoSettingsForm value={DEFAULT} onSave={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "기본값으로" })).toBeNull();
  });
});
