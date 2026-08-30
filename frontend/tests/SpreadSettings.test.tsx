/**
 * 스프레드 설정 화면 테스트 (T065) — contracts/ui-sketches.md S5.
 *
 * FR-025: 범위를 벗어난 값은 거부하고 기존 값을 유지한다.
 * FR-026: 현재 설정값이 모든 과거 날짜에 적용됨을 화면이 밝혀야 한다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SpreadSettings } from "@/components/SpreadSettings";
import type { SpreadRow } from "@/lib/types";

const ROWS: SpreadRow[] = [
  { currency: "USD", cashBuy: "0.001800", cashSell: "0.001800",
    remitSend: "0.000500", remitReceive: "0.000500" },
  { currency: "JPY", cashBuy: "0.002000", cashSell: "0.002000",
    remitSend: "0.000600", remitReceive: "0.000600" },
  { currency: "EUR", cashBuy: "0.002000", cashSell: "0.002000",
    remitSend: "0.000600", remitReceive: "0.000600" },
];

describe("스프레드 설정", () => {
  it("통화 3종을 표시한다", () => {
    render(<SpreadSettings rows={ROWS} onSave={vi.fn()} />);
    for (const c of ["USD", "JPY", "EUR"]) {
      expect(screen.getByText(c)).toBeInTheDocument();
    }
  });

  it("현재 값을 입력란에 채운다", () => {
    render(<SpreadSettings rows={ROWS} onSave={vi.fn()} />);
    expect(screen.getByLabelText("USD 현금 살 때")).toHaveValue("0.001800");
  });

  it("모든 과거 날짜에 적용된다는 안내를 표시한다", () => {
    render(<SpreadSettings rows={ROWS} onSave={vi.fn()} />);
    expect(screen.getByText(/모든 과거 날짜/)).toBeInTheDocument();
  });

  it("시점별 이력을 관리하지 않음을 밝힌다", () => {
    render(<SpreadSettings rows={ROWS} onSave={vi.fn()} />);
    expect(screen.getByText(/이력은 관리하지 않습니다/)).toBeInTheDocument();
  });

  it("유효한 값을 저장한다", async () => {
    const onSave = vi.fn();
    render(<SpreadSettings rows={ROWS} onSave={onSave} />);
    const input = screen.getByLabelText("USD 현금 살 때");
    await userEvent.clear(input);
    await userEvent.type(input, "0.0025");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalledWith("USD", expect.objectContaining({ cashBuy: "0.0025" }));
  });

  it("범위를 벗어난 값은 저장하지 않는다", async () => {
    const onSave = vi.fn();
    render(<SpreadSettings rows={ROWS} onSave={onSave} />);
    const input = screen.getByLabelText("USD 현금 살 때");
    await userEvent.clear(input);
    await userEvent.type(input, "-0.1");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("범위 위반 시 인라인 오류를 표시한다", async () => {
    render(<SpreadSettings rows={ROWS} onSave={vi.fn()} />);
    const input = screen.getByLabelText("USD 현금 살 때");
    await userEvent.clear(input);
    await userEvent.type(input, "1.5");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    // 안내 문구에도 같은 표현이 있으므로 오류 영역으로 한정한다
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText(/0 이상 1 미만/)).toBeInTheDocument();
    expect(alert.textContent).toMatch(/USD 현금 살 때/);
  });

  it("1 이상은 거부한다", async () => {
    const onSave = vi.fn();
    render(<SpreadSettings rows={ROWS} onSave={onSave} />);
    const input = screen.getByLabelText("USD 현금 팔 때");
    await userEvent.clear(input);
    await userEvent.type(input, "1");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("0은 허용한다", async () => {
    const onSave = vi.fn();
    render(<SpreadSettings rows={ROWS} onSave={onSave} />);
    const input = screen.getByLabelText("EUR 송금 받을 때");
    await userEvent.clear(input);
    await userEvent.type(input, "0");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).toHaveBeenCalled();
  });
});
