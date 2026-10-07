/**
 * 해외 주식 매도 칸의 양도차익 구성 (012 T080) — FR-019, SC-011, contracts/ui-wireframes.md F10.
 *
 * - 일시금 매도 칸·주식 적립식 세금 칸에 "매도금액 ₩X − 취득가 ₩Y − 수수료 ₩Z" 줄과 취득가 설명 줄이 "차익 − 공제" 줄 **바로 앞**에 있다 — 차익이 "현재 잔고 −
 *   원금"보다 작은 까닭(배당 재투자 매수의 취득가·예수금·수수료)이 보인다(2026-10-07 보고, 버그 평가 `foreign-sale-tax-gain`)
 * - 값은 서버의 `saleKrw`·`acquisitionKrw`·`feesKrw`다 — 화면은 빼지 않는다(헌법 원칙 VI)
 * - 국내 종목·세 값이 없는 응답(US6 전 형식)에는 두 줄이 없다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecurringBoard } from "@/components/recurring/RecurringBoard";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { RecurringStockSummary, SaleCost, SimulationSummary } from "@/lib/types";

const XLK_SALE: SaleCost = {
  fee: "80884", tax: "110101642", total: "110182526", taxKind: "capital_gains_tax", taxRate: "0.22",
  gain: "502962012", deduction: "2500000", saleKrw: "539229405", acquisitionKrw: "36181082", feesKrw: "86311",
};
const XLK: SimulationSummary = {
  principal: "20000000", profit: "519297203", returnRate: "25.964860", asOf: "2026-10-06", isFinal: true,
  totalKrw: "539297203", saleCost: XLK_SALE, profitAfterSale: "409114677", returnRateAfterSale: "20.455733",
};
const DOMESTIC: SimulationSummary = {
  principal: "10000000", profit: "4630000", returnRate: "0.463000", asOf: "2026-10-02", isFinal: true, totalKrw: "14630000",
  saleCost: { fee: "2195", tax: "29260", total: "31455", taxKind: "transaction_tax", taxRate: "0.0020", gain: null,
    deduction: null, saleKrw: null, acquisitionKrw: null, feesKrw: null },
  profitAfterSale: "4598545", returnRateAfterSale: "0.459854",
};
const BEFORE_US6: SimulationSummary = {
  ...XLK, saleCost: { fee: "80884", tax: "110101642", total: "110182526", taxKind: "capital_gains_tax", taxRate: "0.22",
    gain: "502962012", deduction: "2500000" },
};
const RECURRING: RecurringStockSummary = {
  contributed: "16500000", contributedKrw: "16500000", contributions: 33, pendingAfterEnd: 0, heldShares: 240,
  pending: "12.34", dividendCash: "0", totalKrw: "17890000", buyFeeTotal: "2470", dividendTaxTotal: "38000",
  saleCost: { fee: "2680", tax: "73040", total: "75720", taxKind: "capital_gains_tax", taxRate: "0.22", gain: "2832000",
    deduction: "2500000", saleKrw: "17875000", acquisitionKrw: "15038000", feesKrw: "5000" },
  feeTotal: "5150", taxTotal: "111040", profit: "1390000", returnRate: "0.084242",
  profitAfterSale: "1314280", returnRateAfterSale: "0.079653", asOf: "2026-10-05", isFinal: true,
};

const BREAKDOWN = "매도금액 ₩539,229,405 − 취득가 ₩36,181,082 − 수수료 ₩86,311";
const saleLines = () => [...(screen.getByText("매도 수수료/세금", { selector: "p" }).parentElement as HTMLElement)
  .querySelectorAll("p")].slice(2).map((p) => p.textContent);

describe("일시금 매도 칸의 양도차익 구성", () => {
  it("해외 — 두 줄이 차익 − 공제 바로 앞에 있다", () => {
    render(<PerformanceBoard summary={XLK} currency="KRW" />);
    const lines = saleLines();
    const at = lines.indexOf(BREAKDOWN);
    expect(at).toBeGreaterThan(-1);
    expect(lines[at + 1]).toBe("취득가는 모든 매수(배당 재투자 포함) · 예수금은 팔지 않음");
    expect(lines[at + 2]).toBe("차익 ₩502,962,012 − 공제 ₩2,500,000");
  });

  it("국내에는 없다", () => {
    render(<PerformanceBoard summary={DOMESTIC} currency="KRW" />);
    expect(screen.queryByText(/^매도금액/)).toBeNull();
    expect(screen.queryByText(/취득가는 모든 매수/)).toBeNull();
  });

  it("세 값이 없는 응답(US6 전 형식)에는 없다", () => {
    render(<PerformanceBoard summary={BEFORE_US6} currency="KRW" />);
    expect(screen.queryByText(/^매도금액/)).toBeNull();
    expect(screen.getByText("차익 ₩502,962,012 − 공제 ₩2,500,000")).toBeInTheDocument();
  });

  it("서버 값을 그린다 — 빼지 않는다", () => {
    render(<PerformanceBoard summary={{ ...XLK, saleCost: { ...XLK_SALE, saleKrw: "1", acquisitionKrw: "2", feesKrw: "3" } }}
      currency="KRW" />);
    expect(screen.getByText("매도금액 ₩1 − 취득가 ₩2 − 수수료 ₩3")).toBeInTheDocument();
  });
});

describe("주식 적립식 세금 칸의 양도차익 구성", () => {
  it("해외 — 같은 줄과 적립식 설명이 차익 − 공제 바로 앞에 있다", () => {
    render(<RecurringBoard asset="stock" summary={RECURRING} principalCurrency="KRW" quoteCurrency="USD" />);
    const lines = [...screen.getByRole("group", { name: "세금 총액" }).querySelectorAll("p")].slice(2).map((p) => p.textContent);
    const at = lines.indexOf("매도금액 ₩17,875,000 − 취득가 ₩15,038,000 − 수수료 ₩5,000");
    expect(at).toBeGreaterThan(-1);
    expect(lines[at + 1]).toBe("취득가는 모든 매수(납입·배당 재투자) · 매수 대기금은 팔지 않음");
    expect(lines[at + 2]).toBe("차익 ₩2,832,000 − 공제 ₩2,500,000");
  });
});
