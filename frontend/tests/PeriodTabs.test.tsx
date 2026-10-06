/**
 * 기간 단위 선택기 (T023) — 004 FR-006, FR-007, SC-005.
 *
 * 002의 `CurrencyTabs`와 **같은 분절 컨트롤 형태**를 쓴다 — 컨테이너가 회색, 활성
 * 항목이 흰색. 통화 선택기와 같은 모양이라 사용자가 한 번만 익히면 된다.
 *
 * 002에서 활성 탭의 `bg-white`가 흰 배경 위 흰색이 되어 선택이 보이지 않는 결함을
 * 겪었다(.specify/bugs/fx-stale-date-and-tab/). 여기서도 같은 함정이 있다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PeriodTabs } from "@/components/fx/PeriodTabs";

describe("기간 단위 선택기", () => {
  it("일·주·월 셋을 제시한다", () => {
    render(<PeriodTabs value="daily" onChange={vi.fn()} />);
    for (const label of ["일", "주", "월"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument();
    }
  });

  it("기본 선택은 일 단위다", () => {
    // FR-007, SC-005 — 화면 최초 진입 시 일 단위여야 한다.
    render(<PeriodTabs value="daily" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute(
      "aria-selected", "true");
  });

  it("활성 탭만 선택 상태로 읽힌다", () => {
    render(<PeriodTabs value="weekly" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute(
      "aria-selected", "true");
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute(
      "aria-selected", "false");
    expect(screen.getByRole("tab", { name: "월" })).toHaveAttribute(
      "aria-selected", "false");
  });

  it("활성 탭이 눈으로도 구별된다", () => {
    // 색만으로 구별하지 않는다. 굵기가 함께 달라야 흑백·저대비에서도 읽힌다.
    render(<PeriodTabs value="monthly" onChange={vi.fn()} />);
    const active = screen.getByRole("tab", { name: "월" });
    const idle = screen.getByRole("tab", { name: "일" });
    expect(active.className).toContain("font-semibold");
    expect(idle.className).not.toContain("font-semibold");
  });

  it("고르면 선택을 알린다", async () => {
    const onChange = vi.fn();
    render(<PeriodTabs value="daily" onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: "월" }));
    expect(onChange).toHaveBeenCalledWith("monthly");
  });

  it("키보드로 이동해 고를 수 있다", async () => {
    const onChange = vi.fn();
    render(<PeriodTabs value="daily" onChange={onChange} />);
    await userEvent.tab();
    await userEvent.tab();
    expect(screen.getByRole("tab", { name: "주" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("weekly");
  });

  it("선택 목록임을 보조 기술에 알린다", () => {
    render(<PeriodTabs value="daily" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist")).toHaveAccessibleName("기간 단위 선택");
  });
});

/**
 * 012 T019 — 주식·가상자산 표가 같은 탭을 쓴다(FR-010). 탭 제목만 그 표의 말로 바꾼다 — 기본값은 지금 외환 문구다(위 검사들이 그대로 돈다).
 */
describe("탭 제목 (012 FR-010)", () => {
  it("titles를 주면 세 탭의 제목이 그 값이다", () => {
    const titles = { daily: "시세가 있는 날마다", weekly: "그 주의 금요일", monthly: "그 달의 말일" };
    render(<PeriodTabs value="daily" onChange={vi.fn()} titles={titles} />);
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute("title", "시세가 있는 날마다");
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute("title", "그 주의 금요일");
    expect(screen.getByRole("tab", { name: "월" })).toHaveAttribute("title", "그 달의 말일");
  });

  it("titles를 주지 않으면 외환 문구 그대로다", () => {
    render(<PeriodTabs value="daily" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "일" })).toHaveAttribute("title", "모든 고시일");
    expect(screen.getByRole("tab", { name: "주" })).toHaveAttribute("title", "그 주의 금요일 (없으면 그 주의 마지막 고시일)");
  });
});
