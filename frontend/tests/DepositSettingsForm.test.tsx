/**
 * 예금 이자 소득세율 설정 (T024) — 008 FR-030, FR-031, SC-008, ui-wireframes D7.
 *
 * 화면은 **백분율**, 계약은 **비율**이다. 변환은 문자열로 한다(헌법 원칙 VI) — `15.4 / 100`을 `float`로 하면 `0.154`가 아닌 값이
 * 저장될 수 있다. 0 이상 100 미만이 아니면 저장하지 않는다 — 조용히 0으로 떨어뜨리면 세금 없는 결과가 그럴듯하게 나온다.
 * 설정 화면에서 주식·가상자산·예금 칸은 **따로**다(FR-030).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { DepositSettingsForm } from "@/components/settings/DepositSettingsForm";
import { apiClient } from "@/lib/apiClient";

const DEFAULT = { interestTaxRate: "0.154000", isDefault: true };

describe("예금 이자 소득세", () => {
  it("비율을 백분율로 보이고 기본값의 구성을 밝힌다", () => {
    render(<DepositSettingsForm value={DEFAULT} onSave={vi.fn()} />);
    expect(screen.getByLabelText("이자 소득세")).toHaveValue("15.4");
    expect(screen.getByText("기본값")).toBeInTheDocument();
    expect(screen.getByText(/소득세 14% \+ 지방소득세 1\.4%/)).toBeInTheDocument();
  });

  it("백분율을 비율 문자열로 저장한다", async () => {
    const onSave = vi.fn();
    render(<DepositSettingsForm value={DEFAULT} onSave={onSave} />);
    const box = screen.getByLabelText("이자 소득세");
    await userEvent.clear(box);
    await userEvent.type(box, "9.5");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith("0.095");
  });

  it("0%도 저장한다", async () => {
    const onSave = vi.fn();
    render(<DepositSettingsForm value={DEFAULT} onSave={onSave} />);
    const box = screen.getByLabelText("이자 소득세");
    await userEvent.clear(box);
    await userEvent.type(box, "0");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith("0");
  });

  it.each(["abc", "100", "-1", "", "1e-3"])("범위 밖이나 숫자가 아니면 저장하지 않는다 — %s", async (typed) => {
    const onSave = vi.fn();
    render(<DepositSettingsForm value={DEFAULT} onSave={onSave} />);
    const box = screen.getByLabelText("이자 소득세");
    await userEvent.clear(box);
    if (typed !== "") await userEvent.type(box, typed);
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("0 이상 100 미만");
  });

  it("기본값과 다르면 기본값으로 되돌리는 수단이 있다", async () => {
    const onSave = vi.fn();
    render(<DepositSettingsForm value={{ interestTaxRate: "0.095000", isDefault: false }} onSave={onSave} />);
    expect(screen.getByText("변경됨")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "기본값으로" }));
    expect(onSave).toHaveBeenCalledWith("0.154");
  });

  it("기본값이면 되돌리는 수단이 없다", () => {
    render(<DepositSettingsForm value={DEFAULT} onSave={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "기본값으로" })).toBeNull();
  });
});

describe("설정 화면", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("주식·가상자산·예금 칸이 따로 있고 예금 설정은 예금 경로로 저장한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/deposit/settings") return DEFAULT;
      if (path === "/api/crypto/settings") return { tradeFeeRate: "0.001000", isDefault: true };
      if (path === "/api/stocks/settings") {
        return { tradeFeeRate: "0.000150", dividendTaxRate: "0.154000",
          dividendTaxRateUs: "0.150000", isDefault: true };
      }
      throw new Error(`unexpected ${path}`);
    });
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ interestTaxRate: "0.095000", isDefault: false });
    render(<SettingsPage />);
    // 구역 제목(h2)으로 찾는다 — 폼마다 같은 이름의 h3가 또 있다(005·007 폼).
    expect(await screen.findByRole("heading", { level: 2, name: "예금 이자 소득세" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "주식 매매 조건" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "가상자산 거래 조건" })).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/api/deposit/settings");

    const box = await screen.findByLabelText("이자 소득세");
    await userEvent.clear(box);
    await userEvent.type(box, "9.5");
    const deposit = screen.getByRole("heading", { level: 2, name: "예금 이자 소득세" }).parentElement as HTMLElement;
    await userEvent.click([...deposit.querySelectorAll("button")].find((b) => b.textContent === "저장")!);
    expect(put).toHaveBeenCalledWith("/api/deposit/settings", { interestTaxRate: "0.095" });
    expect(await screen.findByText(/예금 화면으로 돌아가면 새 값으로 다시 계산합니다/)).toBeInTheDocument();
  });
});
