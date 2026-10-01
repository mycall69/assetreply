/**
 * 성과 표 (T032) — 005 FR-024, FR-025, FR-026, FR-028.
 *
 * **월 행의 배당 칸은 비어 있다.** 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할
 * 수 없다 — 002·003·004가 세운 규약과 같다.
 *
 * **날짜는 실제 거래일이다.** "2024년 8월"이 아니라 "2024-08-01"이다.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

const monthRow: SimulationRow = {
  date: "2024-08-01", kind: "month_first", openPrice: "201500.000000",
  boughtShares: 0, heldShares: 1, cash: "6274", principal: "86997",
  balance: "201500", profit: "120777", returnRate: "1.388300",
};

const dividendRow: SimulationRow = {
  date: "2024-06-27", kind: "dividend", openPrice: "229500.000000",
  dividendPerShare: "300.000000", dividendYield: "0.001307",
  boughtShares: 0, heldShares: 1, cash: "6274", principal: "86997",
  balance: "229500", profit: "148777", returnRate: "1.710100",
};

const props = {
  rows: [monthRow, dividendRow],
  currency: "KRW",
  hasMore: false,
  loadingMore: false,
  loadError: null,
  onLoadMore: vi.fn(),
};

describe("성과 표", () => {
  it("열 구성이 명세와 같다", () => {
    render(<PerformanceTable {...props} />);
    for (const label of [
      "날짜", "시작가", "주당 배당금", "배당율", "구매 주식수", "보유 주식",
      "예수금", "투자금", "잔고", "투자 수익", "수익율",
    ]) {
      expect(screen.getByRole("columnheader", { name: label })).toBeInTheDocument();
    }
  });

  it("날짜가 실제 거래일이다", () => {
    // FR-028 — "2024년 8월"이 아니다.
    render(<PerformanceTable {...props} />);
    expect(screen.getByText("2024-08-01")).toBeInTheDocument();
    expect(screen.queryByText(/2024년 8월/)).toBeNull();
  });

  it("월 행의 배당 칸이 비어 있다", () => {
    // FR-026 — 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다.
    render(<PerformanceTable {...props} />);
    const line = screen.getByText("2024-08-01").closest("tr") as HTMLElement;
    expect(within(line).queryByText("0.001307")).toBeNull();
    expect(within(line).queryByText(/^0$/)).not.toBe(null); // 구매 주식수는 0이 맞다
  });

  it("배당락 행에 주당 배당금과 배당율이 보인다", () => {
    render(<PerformanceTable {...props} />);
    const line = screen.getByText("2024-06-27").closest("tr") as HTMLElement;
    expect(within(line).getByText(/300/)).toBeInTheDocument();
    expect(within(line).getByText(/0\.13%/)).toBeInTheDocument();
  });

  it("배당락 행을 월 행과 구별한다", () => {
    // FR-025 — 두 종류가 섞여 있으면 어느 것이 무엇인지 알 수 없다.
    render(<PerformanceTable {...props} />);
    const dividend = screen.getByText("2024-06-27").closest("tr") as HTMLElement;
    expect(dividend).toHaveAttribute("data-kind", "dividend");
    const month = screen.getByText("2024-08-01").closest("tr") as HTMLElement;
    expect(month).toHaveAttribute("data-kind", "month_first");
  });

  it("수익이 음수면 부호로도 드러난다", () => {
    // 색만으로 구별하지 않는다 (접근성).
    render(
      <PerformanceTable
        {...props}
        rows={[{ ...monthRow, profit: "-5446", returnRate: "-0.062600" }]}
      />,
    );
    expect(screen.getByText(/-5,446|−5,446/)).toBeInTheDocument();
  });

  it("행이 없으면 빈 표가 아니라 그 사실을 알린다", () => {
    render(<PerformanceTable {...props} rows={[]} />);
    expect(screen.getByText(/표시할 행이 없습니다/)).toBeInTheDocument();
  });
});
