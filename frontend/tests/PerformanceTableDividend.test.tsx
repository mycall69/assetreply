/**
 * 표의 배당 자릿수, 배당 소득세·매매 수수료 열, 재투자 행 (T128) — 006 FR-057, FR-058, FR-059, SC-023, SC-025,
 * ui-wireframes W6. 반복 2026-10-03 #3.
 *
 * **주당 배당금은 종목 통화 값이다.** 원금 통화(원화) 규칙으로 서식하면 소수를 버려, 원화 원금으로 VOO를 볼 때
 * `1.823`달러가 `1`로 보였다(2026-10-03 실측). 소수 3자리로 고정한다. 배당율은 소수 2자리로 채운다.
 */
// 012 승인 2026-10-06 — 고정 행의 종류 이름 month_first → period(012 FR-008). 단언은 그대로다.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

const base = {
  boughtShares: 0, heldShares: 12, cash: "1000", principal: "1000000",
  balance: "1000000", profit: "1000", returnRate: "0.001000",
};

const initial: SimulationRow = {
  ...base, date: "2026-08-03", kind: "period", openPrice: "590.000000", closePrice: "590.000000",
  boughtShares: 12, tradeFee: "1.062000",
};
const dividend: SimulationRow = {
  ...base, date: "2026-09-28", kind: "dividend", openPrice: "590.000000", closePrice: "590.000000",
  dividendPerShare: "1.823000", dividendYield: "0.003100", dividendTax: "3.281400",
};
const reinvest: SimulationRow = {
  ...base, date: "2026-09-30", kind: "reinvest", openPrice: "595.000000", closePrice: "595.000000",
  boughtShares: 1, heldShares: 13, tradeFee: "0.089250",
};
const month: SimulationRow = {
  ...base, date: "2026-10-01", kind: "period", openPrice: "600.000000", closePrice: "600.000000", heldShares: 13,
};

function setup(rows: SimulationRow[], stockCurrency = "USD") {
  render(<PerformanceTable rows={rows} currency="KRW" stockCurrency={stockCurrency}
    hasMore={false} onLoadMore={vi.fn()} />);
}

/** 그 날짜 행에서 머리글이 `heading`으로 시작하는 열의 글자. */
function cell(date: string, heading: string): string {
  const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
  const index = headers.findIndex((h) => h.startsWith(heading));
  expect(index, `열 없음: ${heading} (${headers.join(", ")})`).toBeGreaterThanOrEqual(0);
  const row = screen.getByText(date).closest("tr") as HTMLElement;
  return row.querySelectorAll("td")[index]?.textContent ?? "";
}

describe("배당 자릿수 (FR-057)", () => {
  it("원화 원금에서도 달러 배당을 소수 3자리로 보인다", () => {
    setup([dividend]);
    expect(cell("2026-09-28", "주당 배당금")).toBe("1.823");
  });

  it("원화 종목의 배당도 소수 3자리다", () => {
    setup([{ ...dividend, dividendPerShare: "361.000000" }], "KRW");
    expect(cell("2026-09-28", "주당 배당금")).toBe("361.000");
  });

  it("배당율은 소수 2자리로 채운다", () => {
    setup([{ ...dividend, dividendYield: "0.004000" }]);
    expect(cell("2026-09-28", "배당율")).toBe("0.40%");
  });
});

describe("배당 소득세·매매 수수료 열 (FR-059)", () => {
  // 006 FR-066(반복 2026-10-03 #4, T140) — 세금·수수료는 종목 통화다. 반복 #3에서는 원금 통화(원화)였고 아래
  // 값(`4,590`·`1,062`·`89`)이 그것을 고정했다. 열별 통화 전체는 `PerformanceTableCurrency`가 본다.
  it("배당락 행에 배당 소득세가 종목 통화로 있다", () => {
    setup([initial, dividend, reinvest, month]);
    expect(cell("2026-09-28", "배당 소득세")).toBe("3.28");
    expect(cell("2026-09-28", "매매 수수료")).toBe("");
  });

  it("매수가 있는 행에 매매 수수료가 있다", () => {
    setup([initial, dividend, reinvest, month]);
    expect(cell("2026-08-03", "매매 수수료")).toBe("1.06");
    expect(cell("2026-09-30", "매매 수수료")).toBe("0.08");
    expect(cell("2026-10-01", "매매 수수료")).toBe("");
    expect(cell("2026-10-01", "배당 소득세")).toBe("");
  });
});

describe("재투자 행 (FR-058)", () => {
  it("재투자 행을 글자로 구별한다", () => {
    setup([dividend, reinvest]);
    const row = screen.getByText("2026-09-30").closest("tr") as HTMLElement;
    expect(row).toHaveAttribute("data-kind", "reinvest");
    expect(row.textContent).toContain("재투자");
    expect(cell("2026-09-30", "구매 주식수")).toBe("1");
  });
});
