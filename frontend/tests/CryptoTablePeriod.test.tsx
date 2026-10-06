/**
 * 가상자산 표의 기간 단위 — 결측 구간 행·◇ 없음 (012 T022) — FR-004b, FR-008, contracts/ui-wireframes.md F4.
 *
 * - `missing` 행은 한 칸에 걸친 글 "날짜~날짜 출처 결측 — 값 없음"이다. 값 칸이 없다 — 메우지 않는다(원칙 V)
 * - 지금의 ◇(1일 결측)는 없어진다 — 월 단위는 옮겨진 기준일 표시가, 일 단위는 결측 구간 행이 대신한다(FR-008)
 * - 표시·범례는 주식 표와 같다(문구만 "일봉")
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { RecurringCryptoTable } from "@/components/recurring/RecurringCryptoTable";
import type { CryptoTableRow, RecurringCryptoTableRow } from "@/lib/types";

const hold = (date: string, over: Partial<CryptoTableRow> = {}): CryptoTableRow => ({
  date, kind: "period", openPrice: "50000", boughtQuantity: "0.00000000", heldQuantity: "0.20000000", cash: "0.5",
  principal: "10000", balance: "10000", profit: "120000", returnRate: "0.0100", ...over,
} as CryptoTableRow);

const ROWS: CryptoTableRow[] = [
  hold("2021-03-13"),
  { kind: "missing", date: "2021-03-08", dateTo: "2021-03-12" },
  hold("2021-03-07"),
  { kind: "missing", date: "2021-03-05", dateTo: "2021-03-05" },
  hold("2021-03-02", { kind: "buy", boughtQuantity: "0.20000000", tradeFee: "1.5" }),
];

const base = { currency: "USD", quoteCurrency: "USD", hasMore: false, onLoadMore: () => undefined };

describe("가상자산 일시금 표", () => {
  it("결측 구간 행은 한 칸의 글이고 값 칸이 없다", () => {
    render(<CryptoPerformanceTable {...base} rows={ROWS} period="daily" />);
    const gaps = screen.getAllByRole("row").filter((r) => r.getAttribute("data-kind") === "missing");
    expect(gaps.map((r) => r.textContent)).toEqual([
      "2021-03-08~03-12 출처 결측 — 값 없음", "2021-03-05 출처 결측 — 값 없음"]);
    for (const gap of gaps) {
      const cells = within(gap).getAllByRole("cell");
      expect(cells).toHaveLength(1);
      expect(Number(cells[0].getAttribute("colspan"))).toBeGreaterThan(1);
    }
  });

  it("결측 구간 행은 그 자리에 있다", () => {
    render(<CryptoPerformanceTable {...base} rows={ROWS} period="daily" />);
    const order = screen.getAllByRole("row").slice(1).map((r) => r.textContent?.slice(0, 10));
    expect(order).toEqual(["2021-03-13", "2021-03-08", "2021-03-07", "2021-03-05", "2021-03-02"]);
  });

  it("◇가 어디에도 없다", () => {
    render(<CryptoPerformanceTable {...base} rows={ROWS} period="daily" />);
    expect(screen.queryByText(/◇/)).toBeNull();
  });

  it("옮겨짐 표시는 일봉의 말이다", () => {
    render(<CryptoPerformanceTable {...base} period="weekly"
      rows={[hold("2021-03-04", { shiftedFrom: "2021-03-05" })]} />);
    expect(screen.getByRole("img", { name: "기준일 2021-03-05(금)에 일봉이 없어 2021-03-04 값입니다" })).toBeInTheDocument();
    expect(screen.getByText("📅 기준일이 옮겨진 행")).toBeInTheDocument();
  });
});

const rec = (date: string, over: Partial<RecurringCryptoTableRow> = {}): RecurringCryptoTableRow => ({
  date, kind: "contribution", openPrice: "50000", contribution: "100", boughtQuantity: "0.00200000",
  heldQuantity: "0.02000000", pending: "0", contributed: "1000", contributedKrw: "1000", balance: "1000",
  profit: "10", returnRate: "0.0100", ...over,
} as RecurringCryptoTableRow);

describe("가상자산 적립식 표", () => {
  it("결측 구간 행을 그리고 ◇ 1일 결측이 없다", () => {
    render(<RecurringCryptoTable rows={[rec("2021-03-13"), { kind: "missing", date: "2021-03-08", dateTo: "2021-03-12" },
      rec("2021-03-07")]} principalCurrency="USD" quoteCurrency="USD" hasMore={false} onLoadMore={() => undefined}
      period="daily" />);
    expect(screen.getByText("2021-03-08~03-12 출처 결측 — 값 없음")).toBeInTheDocument();
    expect(screen.queryByText(/1일 결측/)).toBeNull();
  });
});
