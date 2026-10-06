/**
 * 주식 표의 기간 단위 표시 (012 T021) — FR-004, FR-004a, FR-005, FR-010, contracts/ui-wireframes.md F3.
 *
 * - 서버가 준 `shiftedFrom`·`isOngoing`을 날짜 칸 옆에 📅·⏳로 그린다 — 화면은 대표일을 계산하지 않는다
 * - `buy`(첫 매수)·`period`(기간 행)는 지금 월 행처럼 그린다. 배당락 ◆·재투자 ⟳·납입 ＋ 기호는 그대로다
 * - 범례는 주·월에만 있다. 일 단위는 표시도 범례도 없다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecurringStockTable } from "@/components/recurring/RecurringStockTable";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { RecurringStockRow, SimulationRow } from "@/lib/types";

const row = (over: Partial<SimulationRow>): SimulationRow => ({
  date: "2026-10-02", kind: "period", openPrice: "52000", closePrice: "52050", boughtShares: 0, heldShares: 200,
  cash: "12000", principal: "10000000", balance: "10410000", profit: "422000", returnRate: "0.0422", ...over,
});

const ROWS: SimulationRow[] = [
  row({ date: "2026-10-12", shiftedFrom: "2026-10-16", isOngoing: true }),
  row({ date: "2026-10-08", shiftedFrom: "2026-10-09" }),
  row({ date: "2026-10-02" }),
  row({ date: "2026-09-25", kind: "dividend", dividendPerShare: "500", dividendYield: "0.0098", dividendTax: "15400",
    dividendTotal: "100000", dividendTotalNet: "84600" }),
  row({ date: "2026-09-01", kind: "buy", boughtShares: 199, tradeFee: "1492.5" }),
];

const base = { currency: "KRW", hasMore: false, onLoadMore: () => undefined };

const rowOf = (date: string, kind: string) =>
  screen.getAllByRole("row").find((r) => r.getAttribute("data-kind") === kind && r.textContent?.includes(date)) as HTMLElement;

describe("주식 일시금 표", () => {
  it("옮겨짐·진행 중 표시를 그 행의 날짜 칸에 글자 설명과 함께 그린다", () => {
    render(<PerformanceTable {...base} rows={ROWS} period="weekly" />);
    const top = rowOf("2026-10-12", "period");
    expect(within(top).getByRole("img", { name: "기준일 2026-10-16(금)에 시세가 없어 2026-10-12 값입니다" })).toBeInTheDocument();
    expect(within(top).getByRole("img", { name: "이번 주가 아직 끝나지 않았습니다" })).toBeInTheDocument();
    const shifted = rowOf("2026-10-08", "period");
    expect(within(shifted).getAllByRole("img")).toHaveLength(1);
    expect(within(rowOf("2026-10-02", "period")).queryByRole("img")).toBeNull();  // 옮겨지지 않은 행에는 표시가 없다
  });

  it("매수·기간 행을 그리고 배당락 기호는 그대로다", () => {
    render(<PerformanceTable {...base} rows={ROWS} period="weekly" />);
    expect(rowOf("2026-09-01", "buy")).toHaveTextContent("199");
    expect(within(rowOf("2026-09-25", "dividend")).getByTitle("배당락일")).toHaveTextContent("◆");
  });

  it("사건 행이 대표 행이면 그 행에 표시가 붙는다", () => {
    render(<PerformanceTable {...base} period="monthly"
      rows={[row({ date: "2026-09-29", kind: "reinvest", boughtShares: 1, tradeFee: "7.8", shiftedFrom: "2026-09-30" })]} />);
    const reinvest = rowOf("2026-09-29", "reinvest");
    expect(within(reinvest).getByRole("img", { name: "기준일 2026-09-30(말일)에 시세가 없어 2026-09-29 값입니다" })).toBeInTheDocument();
    expect(within(reinvest).getByTitle("배당 재투자")).toBeInTheDocument();
  });

  it("범례는 주·월에만 있다", () => {
    const { unmount } = render(<PerformanceTable {...base} rows={ROWS} period="monthly" />);
    expect(screen.getByText("📅 기준일이 옮겨진 행")).toBeInTheDocument();
    unmount();
    render(<PerformanceTable {...base} rows={[row({ date: "2026-10-12" })]} period="daily" />);
    expect(screen.queryByText("📅 기준일이 옮겨진 행")).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });
});

const recurring = (over: Partial<RecurringStockRow>): RecurringStockRow => ({
  date: "2026-10-12", kind: "contribution", openPrice: "53000", closePrice: "53050", contribution: "1000000",
  boughtShares: 18, heldShares: 120, pending: "40000", dividendCash: "0", contributed: "6000000",
  contributedKrw: "6000000", balance: "6366000", profit: "406000", returnRate: "0.0676", ...over,
});

describe("주식 적립식 표", () => {
  it("대표일의 납입 행에 표시가 붙고 ＋와 미뤄진 납입 표기는 그대로다", () => {
    render(<RecurringStockTable rows={[
      recurring({ shiftedFrom: "2026-10-16", isOngoing: true, deferred: ["2026-10-09"] }),
      recurring({ date: "2026-10-08", kind: "period", contribution: undefined, boughtShares: 0, shiftedFrom: "2026-10-09" }),
    ]} principalCurrency="KRW" stockCurrency="KRW" hasMore={false} onLoadMore={() => undefined} period="weekly" />);
    const top = rowOf("2026-10-12", "contribution");
    expect(top).toHaveTextContent("＋");
    expect(top).toHaveTextContent("+1회(10-09)");
    expect(within(top).getByRole("img", { name: "이번 주가 아직 끝나지 않았습니다" })).toBeInTheDocument();
    expect(within(rowOf("2026-10-08", "period")).getByRole("img", { name: "기준일 2026-10-09(금)에 시세가 없어 2026-10-08 값입니다" }))
      .toBeInTheDocument();
    expect(screen.getByText("⏳ 아직 끝나지 않은 구간")).toBeInTheDocument();
  });
});
