/**
 * 성과 표의 열 폭 (T148) — 버그 `table-column-width`(.specify/bugs/table-column-width/), 006 FR-069.
 *
 * 표가 칸 폭 전체(`w-full`)라 넓은 화면에서 남는 폭이 열마다 나뉘었다 — 1920px에서 칸 1,646px에 내용 1,024px, 남는 622px가 열
 * 사이로 벌어져 값이 `0`인 `구매 주식수` 열이 108px였다(2026-10-03 사용자 보고). 열 폭은 **내용**(값과 열 이름 중 넓은 쪽)이어야
 * 한다. 테두리 상자도 표에 맞춘다 — 상자만 칸 폭이면 표 오른쪽에 빈 테두리가 남는다.
 *
 * jsdom은 배치를 재지 못해 **폭 규칙만** 본다. 실제 폭은 브라우저 실측이 검사다(quickstart 35).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

const row: SimulationRow = {
  date: "2026-10-01", kind: "month_first", openPrice: "2670.000000",
  boughtShares: 0, heldShares: 3164, cash: "703", principal: "20000000",
  balance: "8447880", profit: "-11551416", returnRate: "-0.577500",
};

function setup() {
  render(<PerformanceTable rows={[row]} currency="KRW" stockCurrency="KRW"
    hasMore={false} onLoadMore={vi.fn()} />);
  return screen.getByRole("table");
}

const classes = (el: Element) => el.className.split(/\s+/);

describe("열 폭 (FR-069)", () => {
  it("표가 칸 폭으로 늘어나지 않고 내용 폭이다", () => {
    const table = setup();
    expect(classes(table)).not.toContain("w-full");
    expect(classes(table)).toContain("w-max");
  });

  it("좁은 화면에서는 표만 가로로 스크롤된다", () => {
    const table = setup();
    expect(classes(table.parentElement as HTMLElement)).toContain("overflow-x-auto");
  });

  it("테두리 상자가 표에 맞고 칸보다 넓어지지 않는다", () => {
    const box = setup().closest(".rounded-lg") as HTMLElement;
    expect(classes(box)).toContain("w-fit");
    expect(classes(box)).toContain("max-w-full");
  });
});
