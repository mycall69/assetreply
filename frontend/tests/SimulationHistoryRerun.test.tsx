/**
 * 주식 이력의 다시 실행 버튼 (010 T027) — FR-018, FR-019, ui-wireframes F4.
 *
 * 행마다 "다시 실행" — 가상자산·예금·부동산과 같은 문구·자리(삭제 `×` 앞), `aria-label`은 `{행 이름} 다시 실행`. 막힌 조합 행에도 있다 —
 * 누르면 조건이 들어가고 지금 규칙의 사유가 보인다(조건을 고쳐 다시 실행할 수 있게).
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimulationHistory } from "@/components/stock/SimulationHistory";
import type { SimulationHistoryEntry } from "@/lib/types";

const APPLE_EUR: SimulationHistoryEntry = {
  id: "eur", stock: { market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD" },
  start: "2020-01-02", principal: "5000", principalCurrency: "EUR", reinvest: true, savedAt: "2026-10-05T00:00:00Z",
};
const SAMSUNG_KRW: SimulationHistoryEntry = {
  id: "ok", stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  start: "2021-08-01", principal: "86997", principalCurrency: "KRW", reinvest: false, savedAt: "2026-10-05T00:00:00Z",
};

function draw(onRerun = vi.fn()) {
  render(<SimulationHistory entries={[APPLE_EUR, SAMSUNG_KRW]} selected={[]} comparing={false} saveError={null}
    onToggle={vi.fn()} onRemove={vi.fn()} onCompare={vi.fn()} onRerun={onRerun} />);
  return onRerun;
}

describe("다시 실행", () => {
  it("행마다 버튼이 있고 누르면 그 항목으로 부른다", () => {
    const onRerun = draw();
    fireEvent.click(screen.getByRole("button", { name: "삼성전자 다시 실행" }));
    expect(onRerun).toHaveBeenCalledWith("ok");
  });

  it("막힌 조합 행에도 있다", () => {
    const onRerun = draw();
    const row = screen.getAllByTestId("history-row")[0];
    expect(within(row).getByText(/막힌 조합/)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "Apple Inc. 다시 실행" }));
    expect(onRerun).toHaveBeenCalledWith("eur");
  });

  it("삭제 앞에 둔다", () => {
    draw();
    const row = screen.getAllByTestId("history-row")[1];
    const buttons = within(row).getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(buttons).toEqual(["삼성전자 다시 실행", "삼성전자 이력 삭제"]);
    expect(within(row).getByRole("button", { name: "삼성전자 다시 실행" })).toHaveTextContent("다시 실행");
  });
});
