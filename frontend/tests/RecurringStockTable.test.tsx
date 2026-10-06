/**
 * 주식 적립식 표 (011 T020) — FR-014, SC-010, ui-wireframes §3.
 *
 * - 열: 날짜 · 납입액 · 환율 · 시작가 · 종가 · 구매 주식수 · 매매 수수료 · 배당(세후) · 보유 주식 · 매수 대기금 · 배당 현금 · 총 납입 원금 · 잔고 · 투자 수익 ·
 *   수익률. 환율 열은 해외 종목만, 배당 열·배당 현금 열은 배당 행이 있을 때만이다(빈 열을 남기지 않는다)
 * - 구분 표시
 *   - 납입은 "＋"이고, 매수 0이면 회색이다(모으는 중)
 *   - 배당은 "◆", 재투자는 "⟳ 재투자"
 * - 같은 날의 다른 사건은 행이 따로이고, 키는 `날짜:종류`다
 * - 미뤄진 납입은 "+n회(원래 날짜)"로 보인다 — 원래 날짜를 잃지 않는다
 * - 원화 원금 해외 종목은 납입 행의 환전 환율과 고시일, 그 밖의 행은 평가 환율
 * - 끝없는 스크롤·상태 줄·센티널은 지금 표와 같다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RecurringStockTable } from "@/components/recurring/RecurringStockTable";
import type { RecurringStockRow } from "@/lib/types";

const row = (over: Partial<RecurringStockRow>): RecurringStockRow => ({
  date: "2026-09-15", kind: "contribution", openPrice: "71200", closePrice: "71800",
  boughtShares: 7, heldShares: 240, pending: "12345", dividendCash: "0", contributed: "16500000",
  contributedKrw: "16500000", balance: "17232000", profit: "744345", returnRate: "0.045112",
  contribution: "500000", tradeFee: "74", ...over,
});

const base = { principalCurrency: "KRW", stockCurrency: "KRW", hasMore: false, loadingMore: false, loadError: null,
  onLoadMore: vi.fn() };

/** 열 이름 — 아래 줄의 단위 표시(작은 글자)만 뺀다. 열 이름 자체의 괄호("배당(세후)")는 남긴다(사용자 승인 2026-10-06 — 처음엔 괄호를 모두 지웠다). */
const header = () => screen.getAllByRole("columnheader").map((h) => {
  const copy = h.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("span").forEach((s) => s.remove());
  return copy.textContent?.trim();
});

describe("적립식 표", () => {
  it("배당이 없는 국내 종목은 배당·환율 열이 없다", () => {
    render(<RecurringStockTable {...base} rows={[row({})]} />);
    expect(header()).toEqual(["날짜", "납입액", "시작가", "종가", "구매 주식수", "매매 수수료", "보유 주식", "매수 대기금",
      "총 납입 원금", "잔고", "투자 수익", "수익률"]);
  });

  it("배당 행이 있으면 배당(세후)과 배당 현금 열이 있다", () => {
    render(<RecurringStockTable {...base} rows={[
      row({ kind: "dividend", contribution: undefined, tradeFee: undefined, boughtShares: 0, dividendCash: "846",
        dividendPerShare: "361", dividendTotal: "1000", dividendTax: "154", dividendTotalNet: "846" }),
      row({}),
    ]} />);
    expect(header()).toContain("배당(세후)");
    expect(header()).toContain("배당 현금");
    const dividend = screen.getAllByRole("row").find((r) => r.getAttribute("data-kind") === "dividend");
    expect(dividend).toBeDefined();
    const cellWithTitle = within(dividend as HTMLElement).getByTitle(/주당 배당금/);
    expect(cellWithTitle).toHaveTextContent("846");
    expect(cellWithTitle.getAttribute("title")).toContain("세전 1,000");
  });

  it("구분 표시 — 납입은 ＋(매수 0이면 회색), 배당 ◆, 재투자 ⟳", () => {
    render(<RecurringStockTable {...base} rows={[
      row({ date: "2026-09-16", kind: "reinvest", contribution: undefined }),
      row({ date: "2026-09-15", kind: "contribution", boughtShares: 0, tradeFee: undefined }),
      row({ date: "2026-09-15", kind: "dividend", contribution: undefined, dividendTotalNet: "846" }),
      row({ date: "2026-09-01", kind: "period", contribution: undefined, boughtShares: 0, tradeFee: undefined }),
    ]} />);
    const rows = screen.getAllByRole("row").slice(1);
    // 012 승인 2026-10-06 — 그 달 첫 거래일 행은 기간 행(period)이다(FR-008).
    expect(rows.map((r) => r.getAttribute("data-kind"))).toEqual(["reinvest", "contribution", "dividend", "period"]);
    expect(rows[0]).toHaveTextContent("⟳ 재투자");
    expect(rows[1]).toHaveTextContent("＋");
    expect(rows[1].querySelector("[data-idle='true']")).not.toBeNull();
    expect(rows[2]).toHaveTextContent("◆");
  });

  it("미뤄진 납입은 원래 날짜와 횟수를 보인다", () => {
    render(<RecurringStockTable {...base} rows={[
      row({ date: "2026-09-23", contribution: "1000000", deferred: ["2026-09-15", "2026-09-22"] })]} />);
    expect(screen.getByText("+2회(09-15·09-22)")).toBeInTheDocument();
  });

  it("원화 원금 해외 종목은 환율 열이 있고 납입 행은 환전 환율·고시일이다", () => {
    render(<RecurringStockTable {...base} stockCurrency="USD" rows={[
      row({ date: "2026-03-03", fxRate: "1460.8", fxRateDate: "2026-03-03", exchangeRate: "1463.356400",
        exchangeRateDate: "2026-03-03", balance: "1000.50", balanceKrw: "1461530" }),
      row({ date: "2026-03-02", kind: "period", contribution: undefined, fxRate: "1455.1", fxRateDate: "2026-02-27" }),
    ]} />);
    expect(header()).toContain("환율");
    const [contribution, month] = screen.getAllByRole("row").slice(1);
    expect(contribution).toHaveTextContent("환전 1,463.35");
    expect(month).toHaveTextContent("1,455.10");
    expect(month).toHaveTextContent("02-27");
  });

  it("끝에 닿으면 상태 줄이 알리고 더 받을 것이 있으면 센티널을 둔다", () => {
    const { container, rerender } = render(<RecurringStockTable {...base} rows={[row({})]} />);
    expect(screen.getByRole("status")).toHaveTextContent("모두 표시했습니다");
    rerender(<RecurringStockTable {...base} hasMore rows={[row({})]} />);
    expect(container.querySelector("[data-testid='scroll-sentinel']")).not.toBeNull();
  });
});
