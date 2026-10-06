/**
 * 예금 상품 고르기 (011 T045) — FR-022, ui-wireframes §7.
 *
 * "상품" fieldset에 라디오 둘(정기예금 · 정기 적금)이다. 기본은 정기예금이다 — 011 전과 같은 화면으로 열린다(FR-039). 방향키 이동은 브라우저의
 * 라디오 묶음 동작(같은 `name`)이다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductPicker } from "@/components/deposit/ProductPicker";

describe("상품 고르기", () => {
  it("상품 묶음에 라디오 둘이고 지금 값이 골라져 있다", () => {
    render(<ProductPicker value="deposit" onChange={vi.fn()} />);
    const group = screen.getByRole("group", { name: "상품" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => r.closest("label")?.textContent)).toEqual(["정기예금", "정기 적금"]);
    expect(screen.getByRole("radio", { name: "정기예금" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "정기 적금" })).not.toBeChecked();
  });

  it("고르면 상품을 알린다", () => {
    const onChange = vi.fn();
    render(<ProductPicker value="deposit" onChange={onChange} />);
    fireEvent.click(screen.getByRole("radio", { name: "정기 적금" }));
    expect(onChange).toHaveBeenCalledWith("installment");
  });

  it("막으면 둘 다 고를 수 없다", () => {
    render(<ProductPicker value="installment" disabled onChange={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "정기예금" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "정기 적금" })).toBeDisabled();
  });
});
