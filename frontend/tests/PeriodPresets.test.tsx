/**
 * 기간 프리셋 선택기 (T090) — 002 FR-015.
 *
 * 2026-09-27 반복에서 6단계 → 10단계가 됐다. 10년과 전체 사이가 비어 있으면
 * USD(62년)에서 장기 추이를 볼 방법이 전체뿐이라, 구간을 좁혀 보려면 직접 지정해야 했다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PeriodPresets } from "@/components/fx/PeriodPresets";
import { PRESETS } from "@/stores/fxWorkspaceStore";

const LABELS = [
  "1개월", "6개월", "1년", "5년", "10년", "20년", "30년", "40년", "50년", "전체",
];

describe("기간 프리셋", () => {
  it("10단계를 모두 제시한다", () => {
    render(<PeriodPresets value="1y" onChange={vi.fn()} />);
    for (const label of LABELS) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("목록 순서가 짧은 구간부터다", () => {
    expect(PRESETS.map((p) => p.label)).toEqual(LABELS);
  });

  it("활성 표시가 하나뿐이다", () => {
    render(<PeriodPresets value="30y" onChange={vi.fn()} />);
    const pressed = screen
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAccessibleName("30년");
  });

  it("고르면 그 키로 알린다", async () => {
    const onChange = vi.fn();
    render(<PeriodPresets value="1y" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "50년" }));
    expect(onChange).toHaveBeenCalledWith("50y");
  });

  it("좁은 화면에서 줄바꿈된다", () => {
    // 10개가 한 줄을 넘치면 **뒤쪽 프리셋을 누를 수 없다**. 6개일 때는 겪지 않던 일이다.
    const { container } = render(<PeriodPresets value="1y" onChange={vi.fn()} />);
    const group = container.querySelector("[role='group']") as HTMLElement;
    expect(group.className).toContain("flex-wrap");
  });
});
