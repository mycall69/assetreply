/**
 * 표의 열별 통화와 배당금 총액 (T140) — 006 FR-066, FR-067, FR-068, SC-026, SC-027, ui-wireframes W8.
 * 반복 2026-10-03 #4.
 *
 * 해외 종목은 **한 행에 통화가 섞인다** — 예수금·배당 소득세·매매 수수료·잔고·배당금 총액은 종목 통화, 잔고 괄호는
 * KRW, 투자금은 입력한 원금 통화, 투자 수익·수익율은 KRW 기준이다. 머리글에 없으면 사용자는 같은 단위로 읽어 잔고와
 * 예수금을 더해 본다. 국내 종목은 모두 KRW라 괄호를 붙이지 않는다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

/** VOO 원화 원금 — 2026-09-28 배당락 행(W8). */
const dividend: SimulationRow = {
  date: "2026-09-28", kind: "dividend", openPrice: "706.280000", closePrice: "706.280000",
  dividendPerShare: "1.823000", dividendYield: "0.002581",
  dividendTotal: "48.070000", dividendTotalNet: "40.860000", dividendTax: "7.210000",
  boughtShares: 0, heldShares: 31, cash: "153.960000", principal: "10000000",
  balance: "21895.000000", balanceKrw: "29602026", profit: "19810175",
  returnRate: "1.981017", fxRate: "1352.000000", fxRateDate: "2026-09-28",
};
const reinvest: SimulationRow = {
  date: "2026-09-30", kind: "reinvest", openPrice: "706.000000", closePrice: "706.000000",
  boughtShares: 1, heldShares: 32, cash: "47.850000", principal: "10000000",
  balance: "22592.000000", balanceKrw: "30544384", tradeFee: "0.105900",
  profit: "20609100", returnRate: "2.060910", fxRate: "1352.000000", fxRateDate: "2026-09-30",
};

function setup(rows: SimulationRow[], currency = "KRW", stockCurrency = "USD") {
  render(<PerformanceTable rows={rows} currency={currency} stockCurrency={stockCurrency}
    hasMore={false} onLoadMore={vi.fn()} />);
}

const headings = () => screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");

/** 그 날짜 행에서 머리글이 `heading`과 같은 열의 글자. */
function cell(date: string, heading: string): string {
  const index = headings().indexOf(heading);
  expect(index, `열 없음: ${heading} (${headings().join(", ")})`).toBeGreaterThanOrEqual(0);
  const row = screen.getByText(date).closest("tr") as HTMLElement;
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

describe("해외 종목의 머리글 (FR-066)", () => {
  it("열마다 통화를 쓴다 — 원화 원금", () => {
    setup([dividend]);
    expect(headings()).toEqual([
      "날짜", "시작가 (USD)", "종가 (USD)", "주당 배당금 (USD)", "배당율", "배당금 총액 (USD)",
      "배당 소득세 (USD)", "구매 주식수", "매매 수수료 (USD)", "보유 주식", "예수금 (USD)",
      "투자금 (KRW)", "잔고 (USD · KRW)", "투자 수익 (KRW)", "수익율 (KRW 기준)", "환율",
    ]);
  });

  it("달러 원금이어도 투자 수익·수익율은 KRW다 — 투자금만 원금 통화다", () => {
    setup([{ ...dividend, principal: "10000" }], "USD");
    const all = headings();
    expect(all).toContain("투자금 (USD)");
    expect(all).toContain("투자 수익 (KRW)");
    expect(all).toContain("수익율 (KRW 기준)");
    expect(all).toContain("예수금 (USD)");
    expect(all).toContain("잔고 (USD · KRW)");
  });
});

describe("해외 종목의 칸", () => {
  it("잔고는 종목 통화이고 괄호에 KRW다", () => {
    setup([dividend]);
    expect(cell("2026-09-28", "잔고 (USD · KRW)")).toBe("21,895.00 (29,602,026)");
  });

  it("예수금·배당 소득세·매매 수수료는 종목 통화다", () => {
    setup([dividend, reinvest]);
    expect(cell("2026-09-28", "예수금 (USD)")).toBe("153.96");
    expect(cell("2026-09-28", "배당 소득세 (USD)")).toBe("7.21");
    expect(cell("2026-09-30", "매매 수수료 (USD)")).toBe("0.10");
  });

  it("투자 수익은 KRW, 투자금은 원금 통화다", () => {
    setup([dividend]);
    expect(cell("2026-09-28", "투자 수익 (KRW)")).toBe("19,810,175");
    expect(cell("2026-09-28", "투자금 (KRW)")).toBe("10,000,000");
  });

  it("달러 원금이면 투자금은 달러, 투자 수익은 KRW다", () => {
    setup([{ ...dividend, principal: "10000", profit: "1352000" }], "USD");
    expect(cell("2026-09-28", "투자금 (USD)")).toBe("10,000");
    expect(cell("2026-09-28", "투자 수익 (KRW)")).toBe("1,352,000");
  });
});

describe("배당금 총액 (FR-067)", () => {
  it("배당락 행에 세전과 괄호에 세후가 있다", () => {
    setup([dividend, reinvest]);
    expect(cell("2026-09-28", "배당금 총액 (USD)")).toBe("48.07 (40.86)");
  });

  it("배당락 행이 아니면 비어 있다", () => {
    setup([dividend, reinvest]);
    expect(cell("2026-09-30", "배당금 총액 (USD)")).toBe("");
  });
});

describe("국내 종목", () => {
  const krx: SimulationRow = {
    date: "2026-09-26", kind: "dividend", openPrice: "84000.000000", closePrice: "84000.000000",
    dividendPerShare: "361.000000", dividendYield: "0.004297",
    dividendTotal: "43320.000000", dividendTotalNet: "36650.720000", dividendTax: "6671.280000",
    boughtShares: 0, heldShares: 120, cash: "51234.720000", principal: "10000000",
    balance: "10080000.000000", profit: "131235", returnRate: "0.013123",
  };

  it("머리글에 통화를 붙이지 않는다 — 모두 KRW다", () => {
    setup([krx], "KRW", "KRW");
    expect(headings()).toEqual([
      "날짜", "시작가", "종가", "주당 배당금", "배당율", "배당금 총액", "배당 소득세", "구매 주식수",
      "매매 수수료", "보유 주식", "예수금", "투자금", "잔고", "투자 수익", "수익율",
    ]);
  });

  it("잔고에 괄호가 없고 배당금 총액은 세전 (세후)다", () => {
    setup([krx], "KRW", "KRW");
    expect(cell("2026-09-26", "잔고")).toBe("10,080,000");
    expect(cell("2026-09-26", "배당금 총액")).toBe("43,320 (36,650)");
    expect(cell("2026-09-26", "예수금")).toBe("51,234");
  });
});
