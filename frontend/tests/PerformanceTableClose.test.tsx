/**
 * 주식 표의 종가 열 (010 반복 3, T060) — FR-028, ui-wireframes F6.
 *
 * 잔고가 종가로 평가되므로(잔고 = 보유 주식 × 종가) 표에 그 종가가 보여야 표가 스스로 맞는다. 종가는 시작가 바로 뒤, 시작가와 같은 형식
 * (`formatRate`)·같은 통화 머리말이다. 시작가(매수 가격)는 그대로 남는다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

const aapl: SimulationRow = {
  date: "2026-10-01", kind: "month_first", openPrice: "330.000000", closePrice: "330.320007",
  boughtShares: 0, heldShares: 119, cash: "235.980000", principal: "10000000",
  balance: "39308.080833", balanceKrw: "53286733", profit: "43610637", returnRate: "4.361063",
  fxRate: "1355.700000", fxRateDate: "2026-10-01",
};
const samsung: SimulationRow = {
  date: "2026-10-01", kind: "month_first", openPrice: "84000.000000", closePrice: "85300.000000",
  boughtShares: 0, heldShares: 120, cash: "51234.720000", principal: "10000000",
  balance: "10236000.000000", profit: "287235", returnRate: "0.028723",
};

function setup(rows: SimulationRow[], stockCurrency: string) {
  render(<PerformanceTable rows={rows} currency="KRW" stockCurrency={stockCurrency} hasMore={false} onLoadMore={vi.fn()} />);
}

const headings = () => screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");

function cell(date: string, heading: string): string {
  const index = headings().indexOf(heading);
  expect(index, `열 없음: ${heading} (${headings().join(", ")})`).toBeGreaterThanOrEqual(0);
  const row = screen.getByText(date).closest("tr") as HTMLElement;
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

describe("주식 표의 종가 열", () => {
  it("해외 종목 — 시작가 바로 뒤에 종목 통화의 종가 열이 있다", () => {
    setup([aapl], "USD");
    const all = headings();
    expect(all[all.indexOf("시작가 (USD)") + 1]).toBe("종가 (USD)");
  });

  it("국내 종목 — 통화 머리말 없이 시작가 바로 뒤", () => {
    setup([samsung], "KRW");
    const all = headings();
    expect(all[all.indexOf("시작가") + 1]).toBe("종가");
  });

  it("종가는 시작가와 같은 형식이고 시작가는 그대로 남는다", () => {
    setup([aapl], "USD");
    expect(cell("2026-10-01", "시작가 (USD)")).toBe("330.00");
    expect(cell("2026-10-01", "종가 (USD)")).toBe("330.32");
  });

  it("국내 종목의 종가", () => {
    setup([samsung], "KRW");
    expect(cell("2026-10-01", "시작가")).toBe("84,000.00");
    expect(cell("2026-10-01", "종가")).toBe("85,300.00");
  });
});
