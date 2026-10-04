/**
 * 투자처 고르기 (T016) — 008 FR-003, FR-006, ui-wireframes D1·D2·접근성.
 *
 * 종목 검색 대신 **라디오 버튼 다섯**이다. `fieldset`·`legend`로 묶고, 각 항목의 설명을 `aria-describedby`로 잇는다. 이름은
 * 목록을 받기 전에도 보인다 — 다섯은 고정이고, 설명·시작 가능 달만 서버가 준다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InstitutionPicker } from "@/components/deposit/InstitutionPicker";
import type { DepositInstitutionKey } from "@/lib/types";
import { INSTITUTIONS } from "./support/depositFixtures";

function renderPicker(value: DepositInstitutionKey = "commercial_bank", loaded = true) {
  const onChange = vi.fn();
  render(<InstitutionPicker institutions={loaded ? INSTITUTIONS.institutions : null} value={value}
    onChange={onChange} />);
  return onChange;
}

describe("투자처 고르기", () => {
  it("fieldset과 legend로 묶인 라디오 다섯이다", () => {
    renderPicker();
    const group = screen.getByRole("group", { name: "투자처" });
    expect(group.tagName).toBe("FIELDSET");
    expect(screen.getAllByRole("radio")).toHaveLength(5);
  });

  it("목록을 받기 전에도 다섯 이름이 보인다", () => {
    renderPicker("commercial_bank", false);
    expect(screen.getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual([
      "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul"]);
    expect(screen.getByRole("radio", { name: "새마을금고" })).toBeInTheDocument();
  });

  it("고른 투자처 아래에 설명과 시작 가능 달을 보인다", () => {
    renderPicker();
    expect(screen.getByText(/예금은행 정기예금\(1년\) 평균 — 일반·특수은행 포함 · 2012-01부터/))
      .toBeInTheDocument();
  });

  it("받기 전이라 시작 가능 달을 모르면 설명만 보인다", () => {
    renderPicker("savings_bank");
    const note = screen.getByText(/상호저축은행 정기예금\(1년\) 평균/);
    expect(note.textContent).not.toContain("부터");
  });

  it("각 항목의 설명을 aria-describedby로 잇는다", () => {
    renderPicker();
    expect(screen.getByRole("radio", { name: "신협" }))
      .toHaveAccessibleDescription("신협 정기예탁금(1년) 평균");
  });

  it("누르면 그 키를 알린다", async () => {
    const onChange = renderPicker();
    await userEvent.click(screen.getByRole("radio", { name: "저축은행" }));
    expect(onChange).toHaveBeenCalledWith("savings_bank");
  });

  it("방향키로 다음 투자처를 고른다", async () => {
    const onChange = renderPicker();
    screen.getByRole("radio", { name: "시중은행" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("savings_bank");
  });
});
