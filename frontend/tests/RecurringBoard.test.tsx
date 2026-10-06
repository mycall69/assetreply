/**
 * 적립식 보드 (011 T019) — FR-012, FR-020, SC-009, ui-wireframes §2, research R11-7.
 *
 * 다섯 칸이다 — 총 납입 원금 · 매매 수수료 총액 · 세금 총액 · 투자 수익 · 수익률. 주식·가상자산이 함께 쓴다.
 *
 * - 매수 수수료와 배당 소득세는 이미 총자산에서 빠져 있다. 투자 수익은 기준일 매도 비용만 뺀 값이고, 기준 줄이 그 사실을 말한다(FR-012 실패 양상 —
 *   두 번 차감)
 * - 수익률은 단순 수익률이고, 곁의 도움말이 일시금과 단순 비교하기 어렵다고 말한다(명확화)
 * - 외화 원금이면 총 납입 원금은 원금 통화 다음에 원화를 괄호로 둔다
 * - 세율·공제는 설정값이라고 밝힌다(FR-037)
 * - 가상자산 과세
 *   - 시행 전: ₩0 + "가상자산 과세 시행 전"
 *   - 시행 뒤: "—" + "세법 미반영"이고, 투자 수익·수익률도 "—" + 보유 중 값(0으로 메우지 않는다 — FR-020)
 * - 한 주도 못 산 주식은 "매도할 주식 없음"
 * - 화면은 계산하지 않는다 — 모든 값은 서버 문자열이다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecurringBoard } from "@/components/recurring/RecurringBoard";
import type { RecurringCryptoSummary, RecurringStockSummary } from "@/lib/types";

const STOCK: RecurringStockSummary = {
  contributed: "16500000", contributedKrw: "16500000", contributions: 33, pendingAfterEnd: 0,
  heldShares: 240, pending: "12345", dividendCash: "0", totalKrw: "17890000",
  buyFeeTotal: "2470", dividendTaxTotal: "38000",
  saleCost: { fee: "2680", tax: "35760", total: "38440", taxKind: "transaction_tax", taxRate: "0.0020",
    gain: null, deduction: null },
  feeTotal: "5150", taxTotal: "73760", profit: "1390000", returnRate: "0.084242",
  profitAfterSale: "1351560", returnRateAfterSale: "0.081912", asOf: "2026-10-05", isFinal: true,
};

const CRYPTO: RecurringCryptoSummary = {
  contributed: "3650000", contributedKrw: "3650000", contributions: 365, pendingAfterEnd: 0,
  heldQuantity: "0.04123456", pending: "1234", totalKrw: "4000000", buyFeeTotal: "3650",
  saleCost: { fee: "4000", tax: "0", total: "4000", taxKind: "not_yet_taxed" },
  feeTotal: "7650", taxTotal: "0", profit: "350000", returnRate: "0.095890",
  profitAfterSale: "346000", returnRateAfterSale: "0.094794", asOf: "2026-10-05", isFinal: true,
};

const cell = (label: string) => screen.getByRole("group", { name: label });

describe("적립식 보드 — 주식", () => {
  it("다섯 칸과 각 칸의 구성이 보인다", () => {
    render(<RecurringBoard asset="stock" summary={STOCK} principalCurrency="KRW" quoteCurrency="KRW" />);
    expect(cell("총 납입 원금")).toHaveTextContent("₩16,500,000");
    expect(cell("총 납입 원금")).toHaveTextContent("33회 납입");
    expect(cell("매매 수수료 총액")).toHaveTextContent("-₩5,150");
    expect(cell("매매 수수료 총액")).toHaveTextContent("매수 ₩2,470");
    expect(cell("매매 수수료 총액")).toHaveTextContent("매도 ₩2,680");
    expect(cell("세금 총액")).toHaveTextContent("-₩73,760");
    expect(cell("세금 총액")).toHaveTextContent("배당 소득세 ₩38,000");
    expect(cell("세금 총액")).toHaveTextContent("증권거래세 0.20% ₩35,760");
    expect(cell("세금 총액")).toHaveTextContent("(설정)");
    expect(cell("투자 수익")).toHaveTextContent("₩1,351,560");
    expect(cell("투자 수익")).toHaveTextContent("보유 중 ₩1,390,000");
    expect(cell("수익률")).toHaveTextContent("+8.19%");
    expect(cell("수익률")).toHaveTextContent("보유 중 +8.42%");
  });

  it("매수 수수료·배당 소득세가 이미 빠졌다는 사실과 기준일 매도 가정을 기준 줄이 말한다", () => {
    render(<RecurringBoard asset="stock" summary={STOCK} principalCurrency="KRW" quoteCurrency="KRW" />);
    const basis = screen.getByTestId("recurring-basis");
    expect(basis).toHaveTextContent("2026-10-05 기준");
    expect(basis).toHaveTextContent("매수 수수료·배당 소득세는 이미 총자산에서 빠져 있습니다");
    expect(basis).toHaveTextContent("기준일에 모두 판다고 가정");
    const holding = screen.getByTestId("recurring-holding");
    expect(holding).toHaveTextContent("매수 대기금 ₩12,345");
    expect(holding).toHaveTextContent("배당 현금 ₩0");
    expect(holding).toHaveTextContent("보유 240주");
    expect(holding).not.toHaveTextContent("다음 거래일에 들어갈 납입");
  });

  it("수익률 곁의 도움말이 단순 비교의 한계를 말한다", () => {
    render(<RecurringBoard asset="stock" summary={STOCK} principalCurrency="KRW" quoteCurrency="KRW" />);
    const help = screen.getByRole("note", { name: "수익률 도움말" });
    expect(help).toHaveTextContent("나중에 넣은 돈은 시장에 머문 기간이 짧아, 같은 기간의 일시금 수익률과 단순 비교하기 어렵습니다.");
    expect(cell("수익률").getAttribute("aria-describedby")).toBe(help.id);
  });

  it("외화 원금은 원금 통화 다음에 원화를 괄호로 둔다", () => {
    render(<RecurringBoard asset="stock" principalCurrency="USD" quoteCurrency="USD"
      summary={{ ...STOCK, contributed: "12000", contributedKrw: "16500000", pending: "12.34" }} />);
    expect(cell("총 납입 원금")).toHaveTextContent("$12,000.00 (₩16,500,000)");
    expect(screen.getByTestId("recurring-holding")).toHaveTextContent("매수 대기금 $12.34");
  });

  it("해외 양도소득세는 세율·차익·공제와 설정값임을 밝힌다", () => {
    render(<RecurringBoard asset="stock" principalCurrency="KRW" quoteCurrency="USD" summary={{
      ...STOCK, saleCost: { fee: "2680", tax: "900000", total: "902680", taxKind: "capital_gains_tax",
        taxRate: "0.22", gain: "6590909", deduction: "2500000" } }} />);
    expect(cell("세금 총액")).toHaveTextContent("양도소득세 22% ₩900,000");
    expect(cell("세금 총액")).toHaveTextContent("차익 ₩6,590,909 − 공제 ₩2,500,000");
  });

  it("한 주도 못 샀으면 매도할 주식 없음이다", () => {
    render(<RecurringBoard asset="stock" principalCurrency="KRW" quoteCurrency="KRW" summary={{
      ...STOCK, heldShares: 0, saleCost: { ...STOCK.saleCost, fee: "0", tax: "0", total: "0" } }} />);
    expect(cell("세금 총액")).toHaveTextContent("매도할 주식 없음");
  });

  it("계산 끝 뒤로 미뤄진 납입이 있으면 그 수를 말한다", () => {
    render(<RecurringBoard asset="stock" principalCurrency="KRW" quoteCurrency="KRW"
      summary={{ ...STOCK, pendingAfterEnd: 1 }} />);
    expect(screen.getByTestId("recurring-holding")).toHaveTextContent("다음 거래일에 들어갈 납입 1회");
  });
});

describe("적립식 보드 — 가상자산", () => {
  it("과세 시행 전이면 세금이 ₩0이고 그 사실이 보인다", () => {
    render(<RecurringBoard asset="crypto" summary={CRYPTO} principalCurrency="KRW" quoteCurrency="USD" />);
    expect(cell("세금 총액")).toHaveTextContent("₩0");
    expect(cell("세금 총액")).toHaveTextContent("가상자산 과세 시행 전(2027-01-01 시행 예정)");
    expect(screen.getByTestId("recurring-holding")).toHaveTextContent("보유 0.04123456");
    expect(screen.getByTestId("recurring-basis")).not.toHaveTextContent("배당 소득세");
  });

  it("과세 시행 뒤면 세금·투자 수익·수익률을 비우고 세법 미반영을 말한다", () => {
    render(<RecurringBoard asset="crypto" principalCurrency="KRW" quoteCurrency="USD" summary={{
      ...CRYPTO, saleCost: { fee: "4000", tax: null, total: null, taxKind: "outside_rules" },
      taxTotal: null, profitAfterSale: null, returnRateAfterSale: null }} />);
    expect(cell("세금 총액")).toHaveTextContent("—");
    expect(cell("세금 총액")).toHaveTextContent("세법 미반영");
    expect(cell("세금 총액")).not.toHaveTextContent("₩0");
    expect(cell("투자 수익")).toHaveTextContent("—");
    expect(cell("투자 수익")).toHaveTextContent("보유 중 ₩350,000");
    expect(cell("수익률")).toHaveTextContent("—");
  });
});
