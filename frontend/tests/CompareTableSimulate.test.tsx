/**
 * 비교 표의 마지막 열 "투자 시뮬레이션" (013 반복 2026-10-09b T098) — FR-011, FR-011b, ui-wireframes F5.
 *
 * 계산된 줄에만 단추가 있고 누르면 그 줄의 키로 `onSimulate`를 부른다. 수집 중·실패 줄은 빈 칸이다(결과가 없다). `onSimulate`는 선택 속성이다 — 주지
 * 않으면 단추가 없다. 머리는 화면 읽기용 글자뿐이다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CompareTable, type CompareRow } from "@/components/compare/CompareTable";
import { SAMSUNG_T, XLK_T, collectingStock, ok } from "./support/compareFixtures";

const okRow = (key: string, name: string, target: unknown = SAMSUNG_T): CompareRow => ({
  key, name, href: null, state: { status: "ok", data: ok(target) } });
const pending: CompareRow = { key: "h", name: "SK하이닉스", href: null,
  state: { status: "collecting", body: collectingStock(41), progress: null, repeats: 1 } };
const failed: CompareRow = { key: "f", name: "NAVER", href: null, state: { status: "failed", reason: "출처에 연결하지 못했습니다" } };

function renderTable(rows: CompareRow[], onSimulate?: (key: string) => void) {
  return render(<CompareTable rows={rows} method="lump_sum" sort={null} onSort={vi.fn()} onRetry={vi.fn()}
    onSimulate={onSimulate} />);
}

const lastCell = (name: string) => {
  const row = screen.getAllByRole("row").find((r) => r.textContent?.includes(name)) as HTMLElement;
  const cells = within(row).getAllByRole("cell");
  return cells[cells.length - 1];
};

describe("투자 시뮬레이션 열", () => {
  it("계산된 줄에 이름을 밝힌 단추가 있고 누르면 그 줄의 키다", () => {
    const onSimulate = vi.fn();
    renderTable([okRow("a", "삼성전자"), okRow("b", "XLK", XLK_T)], onSimulate);
    fireEvent.click(screen.getByRole("button", { name: "XLK 투자 시뮬레이션" }));
    expect(onSimulate).toHaveBeenCalledWith("b");
    expect(within(lastCell("삼성전자")).getByRole("button")).toHaveTextContent("투자 시뮬레이션");
  });

  it("수집 중·실패 줄은 빈 칸이다", () => {
    renderTable([okRow("a", "삼성전자"), pending, failed], vi.fn());
    expect(lastCell("SK하이닉스").textContent).toBe("");
    expect(within(lastCell("NAVER")).queryByRole("button", { name: /투자 시뮬레이션/ })).toBeNull();
    expect(screen.getAllByRole("button", { name: /투자 시뮬레이션$/ })).toHaveLength(1);
  });

  it("onSimulate를 주지 않으면 단추가 없다", () => {
    renderTable([okRow("a", "삼성전자")]);
    expect(screen.queryByRole("button", { name: /투자 시뮬레이션/ })).toBeNull();
    expect(lastCell("삼성전자").textContent).toBe("");
  });

  it("머리는 화면 읽기용 글자뿐이다", () => {
    renderTable([okRow("a", "삼성전자")], vi.fn());
    const heads = screen.getAllByRole("columnheader");
    const last = heads[heads.length - 1];
    expect(last).toHaveTextContent("투자 시뮬레이션");
    expect(within(last).getByText("투자 시뮬레이션").className).toContain("sr-only");
    expect(within(last).queryByRole("button")).toBeNull();
  });
});
