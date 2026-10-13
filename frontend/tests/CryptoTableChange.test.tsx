/**
 * 가상자산 투자 성과표의 등락 열 (014 반복 2026-10-13b T222) — spec FR-047, SC-029, SC-030, contracts D20.
 *
 * - 시가 바로 오른쪽에 등락폭·등락률(일시금·적립식) — 화면 읽기 이름은 "시가 등락폭"·"시가 등락률"
 * - 등락폭은 크기만 시가와 같은 `formatPrice`(유효 숫자 — 007 FR-040), 등락률은 부호·%. 시세 통화 줄은 등락폭에만
 * - 결측 구간 행(012)은 표 폭 그대로다 — `colSpan`이 늘어난 열 수와 같지 않으면 그 행이 표보다 짧다(FR-047 실패 양상)
 * - 날짜 칸은 왼쪽에 고정된다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { RecurringCryptoTable } from "@/components/recurring/RecurringCryptoTable";
import type { CryptoRow, MissingRow, PriceChange, RecurringCryptoRow } from "@/lib/types";
import { LATEST_ROW, RESULT } from "./support/cryptoFixtures";

vi.mock("@/hooks/useInfiniteScroll", () => ({ useInfiniteScroll: () => () => undefined }));

const change = (over: Partial<PriceChange>): PriceChange => ({
  comparedTo: "2021-03-01", absolute: "1263.589844", percent: "2.07", direction: "up", split: null, ...over,
});
const gap: MissingRow = { kind: "missing", date: "2021-03-08", dateTo: "2021-03-12" };
const priced: CryptoRow = { ...LATEST_ROW, date: "2021-03-13", openChange: change({ comparedTo: "2021-03-07" }) };
const tiny: CryptoRow = {
  ...LATEST_ROW, date: "2021-03-07", openPrice: "0.00000529999988",
  openChange: change({ comparedTo: "2021-03-06", absolute: "-0.00000012340000", percent: "-2.28", direction: "down" }),
};
const bought: CryptoRow = { ...RESULT.rows[2] as CryptoRow, date: "2021-03-02", openChange: null };

const lump = (rows: (CryptoRow | MissingRow)[]) =>
  render(<CryptoPerformanceTable rows={rows} currency="USD" quoteCurrency="USD" summary={RESULT.summary}
    hasMore={false} onLoadMore={() => undefined} />);

const recurringRow = (over: Partial<RecurringCryptoRow>): RecurringCryptoRow => ({
  date: "2024-01-16", kind: "contribution", openPrice: "42742.6484375", contribution: "100",
  boughtQuantity: "0.00233710", heldQuantity: "0.00467420", pending: "0", contributed: "200", contributedKrw: "262000",
  balance: "199.78", balanceKrw: "262311", profit: "311", returnRate: "0.001187", tradeFee: "0.0999",
  fxRate: "1312.000000", fxRateDate: "2024-01-16", openChange: change({ comparedTo: "2024-01-15" }), ...over,
});
const recurring = (rows: (RecurringCryptoRow | MissingRow)[], quoteCurrency = "USD") =>
  render(<RecurringCryptoTable rows={rows} principalCurrency="USD" quoteCurrency={quoteCurrency} hasMore={false}
    onLoadMore={() => undefined} />);

const headings = () => screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");

function cells(date: string, heading: string): HTMLElement {
  const index = headings().indexOf(heading);
  expect(index, `열 없음: ${heading} (${headings().join(", ")})`).toBeGreaterThanOrEqual(0);
  const row = screen.getAllByRole("row").find((r) => (within(r).queryAllByRole("cell")[0]?.textContent ?? "").startsWith(date));
  expect(row, `행 없음: ${date}`).toBeDefined();
  return within(row as HTMLElement).getAllByRole("cell")[index];
}

describe("일시금", () => {
  it("시가 바로 뒤에 두 열이고 다른 열 차례는 그대로다", () => {
    lump([priced]);
    expect(headings().map((h) => h.replace(/ \(.*\)$/, ""))).toEqual([
      "날짜", "시가", "시가 등락폭", "시가 등락률", "구매 수량", "매매 수수료", "보유 수량", "예수금", "투자금", "잔고",
      "투자 수익", "수익율", "환율"]);
    expect(headings()).toContain("시가 등락폭 (USD)");
    expect(headings()).toContain("시가 등락률");
    expect(screen.getByRole("columnheader", { name: /^시가 등락폭/ }).querySelector(".sr-only")?.textContent?.trim()).toBe("시가");
  });

  it("값 — 크기만 formatPrice, 등락률 부호·%, title", () => {
    lump([priced, tiny]);
    const amount = cells("2021-03-13", "시가 등락폭 (USD)");
    expect(amount.textContent).toBe("▲ 1,263.58");
    expect(amount.className).toContain("text-red-600");
    expect(amount).toHaveAttribute("title", "2021-03-07 대비");
    expect(cells("2021-03-13", "시가 등락률").textContent).toBe("+2.07%");
    // 유효 숫자를 잃지 않는다 — 0.00이면 움직임이 없다고 읽힌다
    expect(cells("2021-03-07", "시가 등락폭 (USD)").textContent).toBe("▼ 0.0000001234");
    expect(cells("2021-03-07", "시가 등락률").textContent).toBe("-2.28%");
  });

  it("첫 매수(null)는 —다", () => {
    lump([bought]);
    expect(cells("2021-03-02", "시가 등락폭 (USD)").textContent).toBe("—");
    expect(cells("2021-03-02", "시가 등락률").textContent).toBe("—");
  });

  it("결측 구간 행은 늘어난 열 수만큼 걸친다", () => {
    lump([priced, gap, bought]);
    const line = screen.getAllByRole("row").find((r) => (r.textContent ?? "").includes("2021-03-08")) as HTMLElement;
    const only = within(line).getAllByRole("cell");
    expect(only).toHaveLength(1);
    expect(Number(only[0].getAttribute("colspan"))).toBe(headings().length);
  });

  it("날짜 칸이 고정된다", () => {
    lump([priced]);
    expect(screen.getAllByRole("columnheader")[0].className).toMatch(/\bsticky\b/);
    const date = cells("2021-03-13", "날짜");
    expect(date.className).toMatch(/\bsticky\b/);
    expect(date.className).toMatch(/\bleft-0\b/);
    expect(date.className).toMatch(/\bbg-white\b/);
  });
});

describe("적립식", () => {
  it("시가 바로 뒤에 두 열, 해외 시세면 등락폭에 시세 통화", () => {
    recurring([recurringRow({})]);
    const names = headings();
    const at = names.indexOf("시가 (USD)");
    expect(names.slice(at, at + 4)).toEqual(["시가 (USD)", "시가 등락폭 (USD)", "시가 등락률", "구매 수량"]);
  });

  it("원화 시세면 통화 줄이 없다", () => {
    recurring([recurringRow({ fxRate: undefined, fxRateDate: undefined })], "KRW");
    expect(headings()).toContain("시가 등락폭");
  });

  it("값과 결측 행 폭", () => {
    recurring([recurringRow({}), { kind: "missing", date: "2024-01-14", dateTo: "2024-01-14" },
      recurringRow({ date: "2024-01-13", openChange: null })]);
    expect(cells("2024-01-16", "시가 등락폭 (USD)").textContent).toBe("▲ 1,263.58");
    expect(cells("2024-01-16", "시가 등락률").textContent).toBe("+2.07%");
    expect(cells("2024-01-13", "시가 등락폭 (USD)").textContent).toBe("—");
    const line = screen.getAllByRole("row").find((r) => (r.textContent ?? "").includes("2024-01-14")) as HTMLElement;
    expect(Number(within(line).getAllByRole("cell")[0].getAttribute("colspan"))).toBe(headings().length);
    expect(cells("2024-01-16", "날짜").className).toMatch(/\bsticky\b/);
  });
});
