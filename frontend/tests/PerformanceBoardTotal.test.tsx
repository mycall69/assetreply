/**
 * 일시금 보드의 현재 잔고 (012 T071) — FR-018, SC-010, contracts/ui-wireframes.md F9.
 *
 * - 주식(`saleCost` 있음)은 다섯 칸 — 투자 원금 · 현재 잔고 · 매도 수수료/세금 · 투자 수익 · 수익률. 가상자산(`saleCost` 없음)은 네 칸 — 투자 원금 · 현재 잔고 ·
 *   투자 수익 · 수익률
 * - 현재 잔고는 서버의 `totalKrw`를 원화로 그린다. 원금 통화가 USD여도 원화만이다. 잔고는 손익이 아니라 손익 색이 없다
 * - 칸 안에 "잔고 + 예수금"을 적는다 — 표의 잔고 열(보유 평가액)과 다른 까닭이 보여야 한다
 * - `totalKrw`가 없으면 칸이 없다 — 같은 부품을 쓰는 예금 보드가 바뀌지 않는다
 * - 화면은 원금 + 수익을 더하지 않는다 — 서로 맞지 않는 값을 줘도 서버의 `totalKrw`가 그대로 보인다(헌법 원칙 VI)
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { SimulationSummary } from "@/lib/types";

const stock: SimulationSummary = {
  principal: "10000000", profit: "4630000", returnRate: "0.463000", asOf: "2026-10-02", isFinal: true,
  totalKrw: "14630000",
  saleCost: { fee: "2195", tax: "29260", total: "31455", taxKind: "transaction_tax", taxRate: "0.0020",
    gain: null, deduction: null },
  profitAfterSale: "4598545", returnRateAfterSale: "0.459854",
};
const crypto: SimulationSummary = {
  principal: "10000000", profit: "131035071", returnRate: "13.103507", asOf: "2026-10-05", isFinal: true,
  totalKrw: "141035071",
};
const usd: SimulationSummary = {
  principal: "1000", principalKrw: "1150000", profit: "120000", returnRate: "0.104347", asOf: "2021-10-01",
  isFinal: true, totalKrw: "1270000",
};
const deposit: SimulationSummary = {
  principal: "10000000", profit: "1931326", returnRate: "0.193132", asOf: "2026-10-05", isFinal: true,
};

const labels = () => [...document.querySelectorAll("section > div > div > p:first-child")].map((p) => p.textContent);
const cell = (label: string) => screen.getByText(label, { selector: "p" }).parentElement as HTMLElement;
const value = (label: string) => cell(label).querySelectorAll("p")[1] as HTMLElement;

describe("일시금 보드의 현재 잔고", () => {
  it("주식은 다섯 칸이고 현재 잔고가 투자 원금 다음이다", () => {
    render(<PerformanceBoard summary={stock} currency="KRW" />);
    expect(labels()).toEqual(["투자 원금", "현재 잔고", "매도 수수료/세금", "투자 수익", "수익률"]);
    expect(value("현재 잔고")).toHaveTextContent("₩14,630,000");
  });

  it("가상자산은 네 칸이다", () => {
    render(<PerformanceBoard summary={crypto} currency="KRW" />);
    expect(labels()).toEqual(["투자 원금", "현재 잔고", "투자 수익", "수익률"]);
    expect(value("현재 잔고")).toHaveTextContent("₩141,035,071");
  });

  it("칸 안에 잔고 + 예수금이라고 적고 손익 색이 없다", () => {
    render(<PerformanceBoard summary={stock} currency="KRW" />);
    expect(cell("현재 잔고")).toHaveTextContent("잔고 + 예수금");
    expect(value("현재 잔고").className).not.toMatch(/text-(red|blue)-/);
  });

  it("원금 통화가 USD여도 원화만이다", () => {
    render(<PerformanceBoard summary={usd} currency="USD" />);
    expect(value("현재 잔고")).toHaveTextContent("₩1,270,000");
    expect(value("현재 잔고")).not.toHaveTextContent("$");
  });

  it("totalKrw가 없으면 칸이 없다 — 예금 보드는 그대로다", () => {
    render(<PerformanceBoard summary={deposit} currency="KRW" />);
    expect(labels()).toEqual(["투자 원금", "투자 수익", "수익률"]);
    expect(screen.queryByText("현재 잔고")).toBeNull();
  });

  it("원금 + 수익을 더하지 않고 서버 값을 그린다", () => {
    render(<PerformanceBoard summary={{ ...crypto, totalKrw: "1" }} currency="KRW" />);
    expect(value("현재 잔고")).toHaveTextContent("₩1");
    expect(value("현재 잔고")).not.toHaveTextContent("₩141,035,071");
  });
});
