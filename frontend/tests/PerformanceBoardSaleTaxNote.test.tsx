/**
 * 일시금 보드의 매도 세금 메모 (011 T052) — FR-037, ui-wireframes §2a.
 *
 * "매도 수수료/세금" 칸의 메모 끝에 "세율·공제: 설정값(설정 > 주식 매도 세금)"을 더한다 — 세율이 법령 표가 아니라 사용자가 바꿀 수 있는 값임을 밝힌다.
 * 기존 메모 문장(`PerformanceBoardSaleCost.test.tsx`)은 글자 그대로다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { SimulationSummary } from "@/lib/types";

const domestic: SimulationSummary = {
  principal: "10000000", profit: "46493910", returnRate: "4.649391", asOf: "2026-10-02", isFinal: true,
  saleCost: { fee: "8445", tax: "112608", total: "121053", taxKind: "transaction_tax", taxRate: "0.0020",
    gain: null, deduction: null },
  profitAfterSale: "46372857", returnRateAfterSale: "4.637285",
};

const cell = (label: string) => screen.getByText(label, { selector: "p" }).parentElement as HTMLElement;

describe("일시금 보드의 매도 세금 메모", () => {
  it("메모 끝이 설정값임을 밝힌다", () => {
    render(<PerformanceBoard summary={domestic} currency="KRW" />);
    const notes = [...cell("매도 수수료/세금").querySelectorAll("p")].map((p) => p.textContent);
    expect(notes.at(-1)).toBe("세율·공제: 설정값(설정 > 주식 매도 세금)");
    expect(cell("매도 수수료/세금")).toHaveTextContent("증권거래세 0.20% ₩112,608");
  });

  it("매도 비용이 없는 보드(가상자산 등)에는 없다", () => {
    render(<PerformanceBoard summary={{ principal: "10000000", profit: "1", returnRate: "0.1", asOf: "2026-10-02",
      isFinal: true }} currency="KRW" />);
    expect(screen.queryByText(/세율·공제: 설정값/)).toBeNull();
  });
});
