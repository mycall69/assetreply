/**
 * 가상자산 적립식 표 (011 T036) — FR-017, FR-019, ui-wireframes §4.
 *
 * - 열: 날짜 · 납입액 · 환율 · 시가 · 구매 수량 · 매매 수수료 · 보유 수량 · 매수 대기금 · 총 납입 원금 · 잔고 · 투자 수익 · 수익률. 환율 열은
 *   환율이 있는 행이 있을 때만이다(원화 시세 코인이면 빈 열을 남기지 않는다)
 * - 수량은 `formatQuantity`(소수 8자리)다. 사지 않은 행의 구매 수량·수수료는 "—"이다
 * - 납입은 "＋", 그 달 1일 일봉이 없어 다른 날이 그 달의 행이면 "◇ 1일 결측"이다(007 FR-030 — 기호만으로 전달하지 않는다)
 * - 미뤄진 납입은 "+n회(원래 날짜)"로 보인다 — 원래 날짜를 잃지 않는다
 * - 원화 원금이면 납입 행은 환전 환율("환전 …")과 고시일이다
 * - 끝없는 스크롤·상태 줄·센티널은 주식 적립식 표와 같다
 * - 화면은 계산하지 않는다 — 서식만 입힌다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RecurringCryptoTable } from "@/components/recurring/RecurringCryptoTable";
import type { RecurringCryptoRow } from "@/lib/types";

const row = (over: Partial<RecurringCryptoRow>): RecurringCryptoRow => ({
  date: "2024-01-05", kind: "contribution", openPrice: "52000000", contribution: "30000",
  boughtQuantity: "0.00057635", heldQuantity: "0.00098002", pending: "0.22017", contributed: "50000",
  contributedKrw: "50000", balance: "50961.04", profit: "961", returnRate: "0.019225", tradeFee: "29.9702", ...over,
});

const base = { principalCurrency: "KRW", quoteCurrency: "KRW", hasMore: false, loadingMore: false, loadError: null,
  onLoadMore: vi.fn() };

/** 열 이름 — 아래 줄의 단위 표시(작은 글자)만 뺀다. */
const header = () => screen.getAllByRole("columnheader").map((h) => {
  const copy = h.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("span").forEach((s) => s.remove());
  return copy.textContent?.trim();
});

describe("가상자산 적립식 표", () => {
  it("원화 시세 코인은 환율 열이 없다", () => {
    render(<RecurringCryptoTable {...base} rows={[row({})]} />);
    expect(header()).toEqual(["날짜", "납입액", "시가", "구매 수량", "매매 수수료", "보유 수량", "매수 대기금", "총 납입 원금",
      "잔고", "투자 수익", "수익률"]);
  });

  it("수량은 소수 8자리이고 납입은 ＋다", () => {
    render(<RecurringCryptoTable {...base} rows={[row({})]} />);
    const [line] = screen.getAllByRole("row").slice(1);
    expect(line.getAttribute("data-kind")).toBe("contribution");
    expect(line).toHaveTextContent("＋");
    expect(line).toHaveTextContent("0.00057635");
    expect(line).toHaveTextContent("0.00098002");
  });

  it("그 달 첫 일봉 행은 사지 않았으면 —이고, 1일이 없으면 ◇ 1일 결측이다", () => {
    render(<RecurringCryptoTable {...base} rows={[
      row({ date: "2024-03-02", kind: "month_first", contribution: undefined, boughtQuantity: "0.00000000",
        tradeFee: undefined, firstDayMissing: "2024-03-01" }),
    ]} />);
    const [line] = screen.getAllByRole("row").slice(1);
    expect(line.getAttribute("data-kind")).toBe("month_first");
    expect(line).toHaveTextContent("◇ 1일 결측");
    expect(screen.getByTitle("2024-03-01 일봉이 없어 03-02 일봉을 썼습니다")).toBeInTheDocument();
    expect(line).not.toHaveTextContent("＋");
    expect(line.querySelectorAll("td")[3]).toHaveTextContent("—");
    expect(line.querySelectorAll("td")[4]).toHaveTextContent("—");
  });

  it("미뤄진 납입은 원래 날짜와 횟수를 보인다", () => {
    render(<RecurringCryptoTable {...base} rows={[row({ deferred: ["2024-01-03", "2024-01-04"] })]} />);
    expect(screen.getByText("+2회(01-03·01-04)")).toBeInTheDocument();
  });

  it("원화 원금 달러 시세 코인은 환율 열이 있고 납입 행은 환전 환율·고시일이다", () => {
    render(<RecurringCryptoTable {...base} quoteCurrency="USD" rows={[
      row({ date: "2024-01-08", openPrice: "42000.12345678", fxRate: "1351.2", fxRateDate: "2024-01-08",
        exchangeRate: "1353.565000", exchangeRateDate: "2024-01-05", balance: "15.26", balanceKrw: "20619" }),
    ]} />);
    expect(header()).toContain("환율");
    const [line] = screen.getAllByRole("row").slice(1);
    expect(line).toHaveTextContent("환전 1,353.56");
    expect(line).toHaveTextContent("01-05");
    expect(line).toHaveTextContent("₩20,619");
  });

  it("끝에 닿으면 상태 줄이 알리고 더 받을 것이 있으면 센티널을 둔다", () => {
    const { container, rerender } = render(<RecurringCryptoTable {...base} rows={[row({})]} />);
    expect(screen.getByRole("status")).toHaveTextContent("모두 표시했습니다");
    rerender(<RecurringCryptoTable {...base} hasMore rows={[row({})]} />);
    expect(container.querySelector("[data-testid='scroll-sentinel']")).not.toBeNull();
  });
});
