/**
 * 보는 기간 단추 (014 반복 2026-10-10b T107) — FR-011, contracts D3.
 *
 * 여덟 개 — 일·주·월·1년·5년·10년·20년·모두. 고른 단추는 `aria-pressed="true"`다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RangePicker } from "@/components/dashboard/RangePicker";

describe("기간 단추", () => {
  it("여덟 개가 차례대로이고 고른 것이 눌려 있다", () => {
    render(<RangePicker value="5y" onChange={() => undefined} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["일", "주", "월", "1년", "5년", "10년", "20년", "모두"]);
    expect(buttons.filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.textContent)).toEqual(["5년"]);
  });

  it("누르면 그 기간이다", () => {
    const onChange = vi.fn();
    render(<RangePicker value="1y" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "일" }));
    fireEvent.click(screen.getByRole("button", { name: "모두" }));
    expect(onChange.mock.calls).toEqual([["1d"], ["all"]]);
  });
});
