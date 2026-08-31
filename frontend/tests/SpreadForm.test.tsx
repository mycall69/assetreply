/**
 * 설정 — 외화 스프레드 폼 테스트 (T048) — contracts/ui-wireframes.md W4.
 *
 * FR-027: USD → JPY → EUR 순서 고정.
 * FR-029: 범위 위반은 **해당 입력 바로 아래**에서 알린다. 상단에 모아 보여주면 어느 칸이
 * 문제인지 찾아야 한다.
 * FR-033: 기본값과 다르면 드러나야 한다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SpreadForm } from "@/components/settings/SpreadForm";
import type { SpreadRow } from "@/lib/types";

const DEFAULTS: SpreadRow[] = [
  { currency: "USD", cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" },
  { currency: "JPY", cashBuy: "0.002000", cashSell: "0.002000", remitSend: "0.000600", remitReceive: "0.000600" },
  { currency: "EUR", cashBuy: "0.002000", cashSell: "0.002000", remitSend: "0.000600", remitReceive: "0.000600" },
];

const ROWS = DEFAULTS.map((d, i) => ({ ...d, isDefault: i !== 0, cashBuy: i === 0 ? "0.002500" : d.cashBuy }));

const props = { rows: ROWS, defaults: DEFAULTS, onSave: vi.fn(), onRestore: vi.fn() };

describe("스프레드 설정 폼", () => {
  it("통화를 USD → JPY → EUR 순서로 제시한다", () => {
    render(<SpreadForm {...props} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings[0]).toContain("USD");
    expect(headings[1]).toContain("JPY");
    expect(headings[2]).toContain("EUR");
  });

  it("통화마다 4종 입력을 제공한다", () => {
    render(<SpreadForm {...props} />);
    for (const label of ["USD 현금 살 때", "USD 현금 팔 때", "USD 송금 보낼 때", "USD 송금 받을 때"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });

  it("기본값과 다른 통화를 표시한다", () => {
    render(<SpreadForm {...props} />);
    const usd = screen.getByTestId("spread-USD");
    expect(within(usd).getByText(/기본값과 다름/)).toBeInTheDocument();
    expect(within(screen.getByTestId("spread-JPY")).queryByText(/기본값과 다름/)).toBeNull();
  });

  it("범위를 벗어난 값은 해당 입력 옆에서 알린다", async () => {
    render(<SpreadForm {...props} />);
    const input = screen.getByLabelText("USD 현금 살 때");
    await userEvent.clear(input);
    await userEvent.type(input, "1.5");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));

    const field = input.closest("div") as HTMLElement;
    expect(within(field).getByRole("alert").textContent).toMatch(/0 이상 1 미만/);
  });

  it("범위를 벗어나면 저장하지 않는다", async () => {
    const onSave = vi.fn();
    render(<SpreadForm {...props} onSave={onSave} />);
    const input = screen.getByLabelText("USD 현금 살 때");
    await userEvent.clear(input);
    await userEvent.type(input, "-0.1");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("모든 과거 날짜에 동일 적용됨을 안내한다", () => {
    render(<SpreadForm {...props} />);
    expect(screen.getByText(/모든 과거 날짜에 동일하게 적용/)).toBeInTheDocument();
  });

  it("시점별 이력을 관리하지 않는 이유를 밝힌다", () => {
    render(<SpreadForm {...props} />);
    expect(screen.getByText(/과거에 실제로 적용됐던 스프레드는 알 수 없/)).toBeInTheDocument();
  });
});
