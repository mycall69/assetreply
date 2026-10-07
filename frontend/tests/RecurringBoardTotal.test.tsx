/**
 * 적립식 보드의 현재 잔고 (012 T072) — FR-018, SC-010, contracts/ui-wireframes.md F9.
 *
 * - 여섯 칸이다 — 총 납입 원금 · 현재 잔고 · 매매 수수료 총액 · 세금 총액 · 투자 수익 · 수익률. 주식·가상자산이 함께 쓴다
 * - 현재 잔고는 서버의 `totalKrw`(011 — 원화 총자산)를 원화로 그린다. 손익 색이 없다
 * - 칸 안에 무엇을 더한 값인지 적는다 — 주식 "잔고 + 매수 대기금 + 배당 현금", 가상자산 "잔고 + 매수 대기금"
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

const names = () => screen.getAllByRole("group").map((g) => g.getAttribute("aria-label") ?? g.querySelector("p")?.textContent);
const cell = (label: string) => screen.getByRole("group", { name: label });

describe("적립식 보드의 현재 잔고", () => {
  it.each([
    ["주식", <RecurringBoard key="s" asset="stock" summary={STOCK} principalCurrency="KRW" quoteCurrency="KRW" />],
    ["가상자산", <RecurringBoard key="c" asset="crypto" summary={CRYPTO} principalCurrency="KRW" quoteCurrency="USD" />],
  ])("%s — 여섯 칸이고 현재 잔고가 총 납입 원금 다음이다", (_, board) => {
    render(board);
    expect(names()).toEqual(["총 납입 원금", "현재 잔고", "매매 수수료 총액", "세금 총액", "투자 수익", "수익률"]);
  });

  it("주식 — 현재 잔고는 totalKrw이고 잔고 + 매수 대기금 + 배당 현금이라고 적는다", () => {
    render(<RecurringBoard asset="stock" summary={STOCK} principalCurrency="KRW" quoteCurrency="KRW" />);
    expect(cell("현재 잔고")).toHaveTextContent("₩17,890,000");
    expect(cell("현재 잔고")).toHaveTextContent("잔고 + 매수 대기금 + 배당 현금");
    expect(cell("현재 잔고").innerHTML).not.toMatch(/text-(red|blue)-/);
  });

  it("가상자산 — 현재 잔고는 totalKrw이고 잔고 + 매수 대기금이라고 적는다", () => {
    render(<RecurringBoard asset="crypto" summary={CRYPTO} principalCurrency="USD" quoteCurrency="USD" />);
    expect(cell("현재 잔고")).toHaveTextContent("₩4,000,000");
    expect(cell("현재 잔고")).toHaveTextContent("잔고 + 매수 대기금");
    expect(cell("현재 잔고")).not.toHaveTextContent("배당 현금");
  });
});
