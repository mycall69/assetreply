/**
 * 전역 셸 사이드바 테스트 (T007) — contracts/ui-wireframes.md W1.
 *
 * FR-005: 아직 구현되지 않은 자산군은 준비 중임이 드러나야 하며, 선택 시 빈 화면이나
 * 오류로 이어져서는 안 된다. 가장 확실한 방법은 이동할 경로를 만들지 않는 것이다
 * (research R2-9). 포커스가 갔는데 아무 일도 없는 상태가 가장 혼란스러우므로
 * 키보드 순서에서도 제외한다.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sidebar, MENU } from "@/components/shell/Sidebar";

describe("전역 내비게이션 사이드바", () => {
  it("메뉴 8개를 정해진 순서로 표시한다", () => {
    render(<Sidebar current="/fx" />);
    const labels = MENU.map((m) => m.label);
    // 2026-10-03(007 analyze M3): 헌법 원칙 IX의 자산군 순서대로 외환 → 가상자산 → 주식이다. 005가 주식을 먼저 만들며
    // 주식을 가상자산 앞에 두었던 것을 바로잡는다.
    expect(labels).toEqual([
      "대시보드", "외환", "가상자산", "주식", "예금", "부동산", "투자 비교", "설정",
    ]);
    for (const label of labels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("브랜드 영역을 표시한다", () => {
    render(<Sidebar current="/fx" />);
    expect(screen.getByText("AssetReplay")).toBeInTheDocument();
    expect(screen.getByText("Professional Simulation")).toBeInTheDocument();
  });

  it("준비되지 않은 자산군은 링크가 아니다", () => {
    render(<Sidebar current="/fx" />);
    // 2026-10-02: 005가 주식을 구현해 목록에서 뺐다. 2026-10-03: 007이 가상자산을 구현해 뺐다.
    // 2026-10-04: 008이 예금을 구현해 뺐다. 2026-10-05: 009가 부동산을 구현해 뺐다.
    for (const label of ["투자 비교", "대시보드"]) {
      const item = screen.getByText(label).closest("li");
      expect(item).not.toBeNull();
      expect(within(item as HTMLElement).queryByRole("link")).toBeNull();
    }
  });

  it("준비되지 않은 항목은 준비 중임을 표시한다", () => {
    render(<Sidebar current="/fx" />);
    // 2026-10-05: 009가 부동산을 구현해 3 → 2(대시보드·투자 비교).
    expect(screen.getAllByText("준비중").length).toBe(2);
  });

  it("준비되지 않은 항목은 키보드 포커스 대상이 아니다", () => {
    render(<Sidebar current="/fx" />);
    // 007이 가상자산을 구현해 준비되지 않은 항목의 예를 예금으로 바꿨다. 008이 예금을 구현해 부동산으로 바꿨다.
    // 009가 부동산을 구현해 투자 비교로 바꿨다.
    const item = screen.getByText("투자 비교").closest("li") as HTMLElement;
    const focusable = item.querySelectorAll("a, button, [tabindex]:not([tabindex='-1'])");
    expect(focusable.length).toBe(0);
  });

  it("준비된 자산군만 이동 가능하다", () => {
    // 2026-10-02: 005가 주식을 더했다. 2026-10-03: 007이 가상자산을 더했다. 2026-10-04: 008이 예금을 더했다.
    // 2026-10-05: 009가 부동산을 더했다.
    render(<Sidebar current="/fx" />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href")).sort()).toEqual(
      ["/crypto", "/deposit", "/fx", "/realestate", "/settings", "/stocks"],
    );
  });

  it("부동산은 /realestate로 가는 링크이고 준비중이 아니다", () => {
    // 009 FR-001, ui-wireframes E1 — 부동산의 "준비중"이 사라진다.
    render(<Sidebar current="/fx" />);
    const item = screen.getByText("부동산").closest("li") as HTMLElement;
    expect(within(item).getByRole("link")).toHaveAttribute("href", "/realestate");
    expect(within(item).queryByText("준비중")).toBeNull();
  });

  it("현재 위치를 색이 아닌 표식으로도 구별한다", () => {
    render(<Sidebar current="/fx" />);
    const active = screen.getByText("외환").closest("li") as HTMLElement;
    expect(active).toHaveAttribute("aria-current", "page");
  });
});
