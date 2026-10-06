/**
 * 투자 방식·주기 칸 (011 T018) — FR-001, FR-002, SC-009, ui-wireframes §1.
 *
 * - "투자 방식" 묶음(fieldset/legend)에 라디오 둘(일시금·적립식), 방향키로 고른다
 * - 적립식이면 주기 선택(aria-label "납입 주기" — 매일·매주·매달·매년)과 안내 문장이 나온다. 일시금이면 둘 다 없다
 * - 바꾸면 `onChange`로 방식·주기를 함께 넘긴다
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InvestmentModeFields } from "@/components/recurring/InvestmentModeFields";
import type { InvestmentPlan } from "@/lib/types";

const LUMP: InvestmentPlan = { mode: "lump_sum", frequency: "monthly" };
const RECURRING: InvestmentPlan = { mode: "recurring", frequency: "monthly" };

describe("투자 방식", () => {
  it("일시금이면 라디오 둘만 있고 주기 선택이 없다", () => {
    render(<InvestmentModeFields value={LUMP} start="2024-01-15" asset="stock" onChange={() => undefined} />);
    const group = screen.getByRole("group", { name: "투자 방식" });
    expect(group).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "일시금" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "적립식" })).not.toBeChecked();
    expect(screen.queryByRole("combobox", { name: "납입 주기" })).not.toBeInTheDocument();
  });

  it("적립식을 고르면 방식과 지금 주기를 함께 넘긴다", () => {
    const onChange = vi.fn();
    render(<InvestmentModeFields value={LUMP} start="2024-01-15" asset="stock" onChange={onChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(onChange).toHaveBeenCalledWith({ mode: "recurring", frequency: "monthly" });
  });

  it("적립식이면 주기 넷과 안내 문장이 보인다", () => {
    render(<InvestmentModeFields value={RECURRING} start="2024-01-15" asset="stock" onChange={() => undefined} />);
    const select = screen.getByRole("combobox", { name: "납입 주기" });
    expect([...select.querySelectorAll("option")].map((o) => [o.value, o.textContent])).toEqual([
      ["daily", "매일"], ["weekly", "매주"], ["monthly", "매달"], ["yearly", "매년"],
    ]);
    expect((select as HTMLSelectElement).value).toBe("monthly");
    expect(screen.getByText("매달 15일(휴장이면 다음 거래일)에 넣습니다.")).toBeInTheDocument();
  });

  it("주기를 바꾸면 적립식 그대로 새 주기를 넘긴다", () => {
    const onChange = vi.fn();
    render(<InvestmentModeFields value={RECURRING} start="2024-01-15" asset="crypto" onChange={onChange} />);
    fireEvent.change(screen.getByRole("combobox", { name: "납입 주기" }), { target: { value: "daily" } });
    expect(onChange).toHaveBeenCalledWith({ mode: "recurring", frequency: "daily" });
  });

  it("라디오는 같은 이름 묶음이라 방향키로 옮길 수 있다", () => {
    render(<InvestmentModeFields value={LUMP} start="2024-01-15" asset="stock" onChange={() => undefined} />);
    const radios = screen.getAllByRole("radio");
    expect(new Set(radios.map((r) => (r as HTMLInputElement).name)).size).toBe(1);
  });

  it("막혀 있으면 고를 수 없다", () => {
    render(<InvestmentModeFields value={RECURRING} start="2024-01-15" asset="stock" disabled
      onChange={() => undefined} />);
    expect(screen.getByRole("radio", { name: "적립식" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "납입 주기" })).toBeDisabled();
  });
});
