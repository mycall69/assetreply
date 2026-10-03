/**
 * 성과 보드의 통화 기호 (T122) — 006 FR-054, SC-020, research R6-21, ui-wireframes W5. 반복 2026-10-03 #2.
 *
 * 투자 원금·투자 수익에 **원금 통화의 기호를 숫자 뒤에** 붙인다(`10,000,000₩`, `1,000$`). 숫자만 있으면 원화
 * 원금으로 외화 종목을 볼 때 "… 기준" 줄을 찾아 읽어야 통화를 알고, 놓치면 1,000달러를 1,000원으로 읽는다.
 *
 * `formatMoney`는 표·차트·이력도 쓰므로 바꾸지 않는다 — 기호는 보드에만 붙는다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { currencySymbol, formatMoney, formatMoneyWithSymbol } from "@/lib/format";
import type { SimulationSummary } from "@/lib/types";

describe("통화 기호", () => {
  it.each([
    ["KRW", "₩"],
    ["USD", "$"],
    ["JPY", "¥"],
    ["EUR", "€"],
    ["GBP", "GBP"],
  ])("%s → %s", (currency, symbol) => {
    expect(currencySymbol(currency)).toBe(symbol);
  });

  it.each([
    ["10000000", "KRW", "10,000,000₩"],
    ["188131842", "KRW", "188,131,842₩"],
    ["1000.50", "USD", "1,000.50$"],
    ["1000", "USD", "1,000$"],
    ["100000", "JPY", "100,000¥"],
    ["-5446", "KRW", "-5,446₩"],
  ])("%s %s → %s", (value, currency, shown) => {
    expect(formatMoneyWithSymbol(value, currency)).toBe(shown);
  });

  it("formatMoney는 바뀌지 않는다 — 표·차트·이력이 함께 쓴다", () => {
    expect(formatMoney("10000000", "KRW")).toBe("10,000,000");
  });
});

const summary: SimulationSummary = {
  principal: "10000000", profit: "188131842", returnRate: "18.813100",
  asOf: "2026-10-02", isFinal: true,
};

/** 라벨 바로 아래의 값. 보드는 칸마다 라벨과 값을 한 쌍으로 둔다. */
const valueOf = (label: string) =>
  screen.getByText(label).nextElementSibling?.textContent ?? "";

describe("성과 보드", () => {
  it("원화 원금이면 원금과 수익에 ₩가 숫자 뒤에 붙는다", () => {
    render(<PerformanceBoard summary={summary} currency="KRW" />);
    expect(valueOf("투자 원금")).toBe("10,000,000₩");
    expect(valueOf("투자 수익")).toBe("188,131,842₩");
  });

  it("수익률에는 기호가 없고 기준 줄은 그대로다", () => {
    render(<PerformanceBoard summary={summary} currency="KRW" />);
    expect(valueOf("수익률")).toBe("+1881.31%");
    expect(screen.getByText(/KRW 기준/)).toBeInTheDocument();
  });

  // 006 FR-068(반복 2026-10-03 #4, T140) — 투자 수익은 원금 통화와 관계없이 KRW다. 반복 #2에서는 수익에도 원금
  // 통화의 기호(`120.50$`)를 붙였고 아래 두 테스트가 그것을 고정했다. 원금 괄호의 KRW는 `PerformanceBoardKrw`가 본다.
  it("달러 원금이면 원금은 $, 수익은 ₩다", () => {
    render(<PerformanceBoard currency="USD"
      summary={{ ...summary, principal: "1000", profit: "162900" }} />);
    expect(valueOf("투자 원금")).toBe("1,000$");
    expect(valueOf("투자 수익")).toBe("162,900₩");
  });

  it("엔 원금이면 원금은 ¥, 수익은 ₩다", () => {
    render(<PerformanceBoard currency="JPY"
      summary={{ ...summary, principal: "100000", profit: "12345" }} />);
    expect(valueOf("투자 원금")).toBe("100,000¥");
    expect(valueOf("투자 수익")).toBe("12,345₩");
  });

  it("손실이면 부호가 앞에 온다", () => {
    render(<PerformanceBoard currency="KRW"
      summary={{ ...summary, profit: "-5446", returnRate: "-0.000545" }} />);
    expect(valueOf("투자 수익")).toBe("-5,446₩");
  });
});
