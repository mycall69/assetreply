/**
 * 성과 보드의 KRW 기준과 화면 폭 (T140) — 006 FR-068, FR-069, SC-028, SC-029, ui-wireframes W8. 반복 2026-10-03 #4.
 *
 * 투자 수익·수익률은 **원금 통화와 관계없이 KRW**다. 달러 원금만 달러 기준이면 이력 비교에서 원화 원금 실행과 다른
 * 기준의 수익률이 나란히 놓인다. 투자 원금은 입력한 통화로 보이고, 원화가 아니면 괄호에 KRW 값(첫 매수일 매매기준율로
 * 평가)을 붙인다.
 *
 * 007 반복 2026-10-04(T049, FR-042a) — 기호를 숫자 앞으로 옮겨 아래 기대값을 바꿨다(`10,000,000₩` → `₩10,000,000`).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import StocksPage from "@/app/stocks/page";
import type { SimulationSummary } from "@/lib/types";

vi.mock("lightweight-charts", () => ({ LineSeries: "Line", createChart: vi.fn() }));

const valueOf = (label: string) =>
  screen.getByText(label).nextElementSibling?.textContent ?? "";

const krw: SimulationSummary = {
  principal: "10000000", profit: "19810175", returnRate: "1.981017",
  asOf: "2026-10-02", isFinal: true,
};
const usd: SimulationSummary = {
  principal: "10000", principalKrw: "13520000", profit: "1352000", returnRate: "0.100000",
  asOf: "2026-10-02", isFinal: true,
};

describe("성과 보드 (FR-068)", () => {
  it("원화 원금이면 원금에 괄호가 없다", () => {
    render(<PerformanceBoard summary={krw} currency="KRW" />);
    expect(valueOf("투자 원금")).toBe("₩10,000,000");
    expect(valueOf("투자 수익")).toBe("₩19,810,175");
  });

  it("달러 원금이면 원금은 달러와 괄호에 KRW, 수익은 KRW다", () => {
    render(<PerformanceBoard summary={usd} currency="USD" />);
    expect(valueOf("투자 원금")).toBe("$10,000 (₩13,520,000)");
    expect(valueOf("투자 수익")).toBe("₩1,352,000");
    expect(valueOf("수익률")).toBe("+10.00%");
  });

  it("엔 원금이면 원금은 엔과 괄호에 KRW다", () => {
    render(<PerformanceBoard currency="JPY"
      summary={{ ...usd, principal: "100000", principalKrw: "1045000" }} />);
    expect(valueOf("투자 원금")).toBe("¥100,000 (₩1,045,000)");
  });

  it("기준 줄은 원금 통화와 관계없이 KRW 기준이다", () => {
    render(<PerformanceBoard summary={usd} currency="USD" />);
    expect(screen.getByText(/KRW 기준/)).toBeInTheDocument();
    expect(screen.queryByText(/USD 기준/)).toBeNull();
  });
});

describe("화면 폭 (FR-069)", () => {
  it("주식 화면이 1152px(max-w-6xl)로 묶이지 않는다", () => {
    // 1440px 화면에서 표의 열 15개가 잘리던 원인이다(2026-10-03). 실제 폭은 브라우저로 확인한다(T145).
    const { container } = render(<StocksPage />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).not.toMatch(/max-w-(6xl|5xl|4xl|3xl)/);
  });
});
