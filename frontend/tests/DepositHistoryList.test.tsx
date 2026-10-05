/**
 * 예금 최근 시뮬레이션 (T031) — 008 FR-037, ui-wireframes D6.
 *
 * 한 줄은 투자처·시작일·원금이다. **수익률을 적지 않는다** — 결과는 세율·금리가 바뀌면 달라진다(005 R5-9). 보관 위치와
 * 주식·가상자산 이력과 따로라는 사실을 알린다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DepositHistory } from "@/components/deposit/DepositHistory";
import type { DepositHistoryEntry } from "@/lib/types";

const ENTRIES: DepositHistoryEntry[] = [
  { id: "a", institution: "commercial_bank", start: "2020-01-15", principal: "10000000", savedAt: "2026-10-04T00:00:00Z" },
  { id: "b", institution: "savings_bank", start: "2020-01-15", principal: "10000000", savedAt: "2026-10-04T00:00:00Z" },
];

function renderHistory(selected: string[] = [], handlers = {}) {
  const props = { onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn(), ...handlers };
  render(<DepositHistory entries={ENTRIES} selected={selected} comparing={false} saveError={null} {...props} />);
  return props;
}

describe("예금 이력", () => {
  it("한 줄은 투자처·시작일·원금이고 수익률이 없다", () => {
    renderHistory();
    const rows = screen.getAllByTestId("history-row");
    expect(rows).toHaveLength(2);
    const text = rows[0].textContent ?? "";
    expect(text).toContain("시중은행");
    expect(text).toContain("2020-01-15");
    expect(text).toContain("10,000,000원");
    expect(text).not.toMatch(/%/);
  });

  it("보관 위치와 다른 자산군 이력과 따로라는 사실을 알린다", () => {
    renderHistory();
    expect(screen.getByTestId("history-notice").textContent).toContain("이 브라우저에만 저장됩니다");
    expect(screen.getByTestId("history-notice").textContent).toContain("주식·가상자산 이력과 따로입니다");
  });

  it("다시 실행·삭제·고르기", async () => {
    const props = renderHistory();
    const row = screen.getAllByTestId("history-row")[1];
    await userEvent.click(within(row).getByRole("button", { name: "저축은행 다시 실행" }));
    await userEvent.click(within(row).getByRole("button", { name: "저축은행 이력 삭제" }));
    await userEvent.click(within(row).getByRole("checkbox", { name: "저축은행 비교 대상으로 선택" }));
    expect(props.onRerun).toHaveBeenCalledWith("b");
    expect(props.onRemove).toHaveBeenCalledWith("b");
    expect(props.onToggle).toHaveBeenCalledWith("b");
  });

  it("둘 이상 골라야 비교할 수 있다", async () => {
    renderHistory(["a"]);
    expect(screen.getByRole("button", { name: "선택 항목 비교" })).toBeDisabled();
  });

  it("둘을 고르면 비교한다", async () => {
    const props = renderHistory(["a", "b"]);
    await userEvent.click(screen.getByRole("button", { name: "선택 항목 비교" }));
    expect(props.onCompare).toHaveBeenCalled();
  });
});
