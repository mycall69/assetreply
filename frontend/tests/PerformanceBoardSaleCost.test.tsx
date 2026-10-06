/**
 * 주식 보드의 매도 수수료·세금 (010 반복 4, T071) — FR-030, ui-wireframes F7.
 *
 * - 보드가 **투자 원금 · 매도 수수료/세금 · 투자 수익 · 수익률** 넷이다. 투자 수익·수익률은 매도 비용을 뺀 값이고 보유 중 값이 칸 안에 함께 보인다 —
 *   보드가 표의 마지막 행과 다른 까닭이 보이지 않으면 사용자는 둘 중 하나가 틀렸다고 여긴다
 * - 매도 칸은 내역(수수료·증권거래세 또는 양도소득세와 차익·공제)을 보인다
 * - 세율 표 밖 기준일은 세금이 `—`와 사유이고, 투자 수익·수익률은 보유 중 값이다(0을 빼지 않는다 — 헌법 원칙 V)
 * - `saleCost`가 없으면(가상자산 등, 반복 4 전 형식) 지금처럼 세 칸이다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { SimulationSummary } from "@/lib/types";

const base: SimulationSummary = {
  principal: "10000000", profit: "46493910", returnRate: "4.649391", asOf: "2026-10-02", isFinal: true,
};
const domestic: SimulationSummary = {
  ...base,
  saleCost: { fee: "8445", tax: "112608", total: "121053", taxKind: "transaction_tax", taxRate: "0.0020",
    gain: null, deduction: null },
  profitAfterSale: "46372857", returnRateAfterSale: "4.637285",
};
const foreign: SimulationSummary = {
  ...base, profit: "43609897", returnRate: "4.360989",
  saleCost: { fee: "7993", tax: "8971703", total: "8979696", taxKind: "capital_gains_tax", taxRate: "0.22",
    gain: "43280472", deduction: "2500000" },
  profitAfterSale: "34630201", returnRateAfterSale: "3.463020",
};
const outside: SimulationSummary = {
  ...base, asOf: "2021-11-30",
  saleCost: { fee: "8445", tax: null, total: null, taxKind: "outside_table", taxRate: null, gain: null, deduction: null },
  profitAfterSale: null, returnRateAfterSale: null,
};

const labels = () => [...document.querySelectorAll("section > div > div > p:first-child")].map((p) => p.textContent);
const cell = (label: string) => screen.getByText(label, { selector: "p" }).parentElement as HTMLElement;

describe("주식 보드의 매도 수수료·세금", () => {
  it("네 칸이다", () => {
    render(<PerformanceBoard summary={domestic} currency="KRW" />);
    expect(labels()).toEqual(["투자 원금", "매도 수수료/세금", "투자 수익", "수익률"]);
  });

  it("국내 — 매도 칸은 합계와 수수료·증권거래세 내역", () => {
    render(<PerformanceBoard summary={domestic} currency="KRW" />);
    const sale = cell("매도 수수료/세금");
    expect(sale).toHaveTextContent("-₩121,053");
    expect(sale).toHaveTextContent("수수료 ₩8,445");
    expect(sale).toHaveTextContent("증권거래세 0.20% ₩112,608");
  });

  it("투자 수익·수익률은 매도 비용을 뺀 값이고 보유 중 값을 함께 보인다", () => {
    render(<PerformanceBoard summary={domestic} currency="KRW" />);
    expect(cell("투자 수익")).toHaveTextContent("₩46,372,857");
    expect(cell("투자 수익")).toHaveTextContent("보유 중 ₩46,493,910");
    expect(cell("수익률")).toHaveTextContent("+463.72%");
    expect(cell("수익률")).toHaveTextContent("보유 중 +464.93%");
    expect(screen.getByText(/매도 수수료·세금은 기준일에 모두 판다고 가정한 값/)).toBeInTheDocument();
  });

  it("해외 — 양도소득세와 차익·공제", () => {
    render(<PerformanceBoard summary={foreign} currency="KRW" />);
    const sale = cell("매도 수수료/세금");
    expect(sale).toHaveTextContent("-₩8,979,696");
    expect(sale).toHaveTextContent("양도소득세 22% ₩8,971,703");
    expect(sale).toHaveTextContent("차익 ₩43,280,472 − 공제 ₩2,500,000");
    expect(cell("투자 수익")).toHaveTextContent("₩34,630,201");
  });

  it("세율 표 밖 — 세금은 —와 사유, 투자 수익·수익률은 보유 중 값", () => {
    render(<PerformanceBoard summary={outside} currency="KRW" />);
    const sale = cell("매도 수수료/세금");
    expect(sale).toHaveTextContent("—");
    expect(sale).toHaveTextContent("세율 표 밖");
    expect(sale).not.toHaveTextContent("₩0");
    expect(cell("투자 수익")).toHaveTextContent("₩46,493,910");
    expect(cell("투자 수익")).toHaveTextContent("매도 세금을 모름");
    expect(cell("수익률")).toHaveTextContent("+464.93%");
  });

  it("saleCost가 없으면 지금처럼 세 칸", () => {
    render(<PerformanceBoard summary={base} currency="KRW" />);
    expect(labels()).toEqual(["투자 원금", "투자 수익", "수익률"]);
    expect(cell("투자 수익")).toHaveTextContent("₩46,493,910");
  });
});
