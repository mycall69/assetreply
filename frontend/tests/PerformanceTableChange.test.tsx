/**
 * 주식 투자 성과표의 등락 열 (014 반복 2026-10-13b T222) — spec FR-047, SC-029, SC-030, contracts D20.
 *
 * - 가격 열마다 **바로 오른쪽에 그 가격의 등락폭·등락률** — `시작가 | 등락폭 | 등락률 | 종가 | 등락폭 | 등락률`(일시금·적립식). 앞뒤 다른 열의 차례는 그대로다
 * - 보이는 머리글은 "등락폭"·"등락률"이고 화면 읽기 이름은 어느 가격의 등락인지 밝힌다 — 같은 이름이 둘이면 화면 읽기로 가를 수 없다(FR-047 실패 양상)
 * - 값은 서버 글자에 기호·색·부호만 입힌다(외환 표와 같은 값) — 등락폭은 크기만 가격 열과 같은 `formatRate`, 등락률은 부호·%. 없으면 "—"
 * - 칸 `title`은 "{comparedTo} 대비", 분할을 맞춘 칸은 ✂(기호만으로 전하지 않는다)
 * - 날짜 칸은 왼쪽에 고정된다(가로로 밀어도 남는다) — 불투명 배경, 배당락·재투자 행의 색 유지
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RecurringStockTable } from "@/components/recurring/RecurringStockTable";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { PriceChange, RecurringStockRow, SimulationRow } from "@/lib/types";

vi.mock("@/hooks/useInfiniteScroll", () => ({ useInfiniteScroll: () => () => undefined }));

const up = (over: Partial<PriceChange> = {}): PriceChange => ({
  comparedTo: "2026-09-30", absolute: "500.000000", percent: "0.60", direction: "up", split: null, ...over,
});
const down: PriceChange = { comparedTo: "2026-09-30", absolute: "-300.000000", percent: "-0.36", direction: "down", split: null };
const flat: PriceChange = { comparedTo: "2026-09-30", absolute: "0.000000", percent: "0.00", direction: "flat", split: null };

const samsung: SimulationRow = {
  date: "2026-10-01", kind: "period", openPrice: "84000.000000", closePrice: "85300.000000",
  boughtShares: 0, heldShares: 120, cash: "51234.720000", principal: "10000000",
  balance: "10236000.000000", profit: "287235", returnRate: "0.028723",
  openChange: up(), closeChange: down,
};
const dividend: SimulationRow = {
  ...samsung, date: "2026-09-30", kind: "dividend", dividendPerShare: "361", dividendYield: "0.004",
  openChange: flat, closeChange: up({ comparedTo: "2026-09-29", percent: null }),
};
const first: SimulationRow = { ...samsung, date: "2026-09-01", kind: "buy", boughtShares: 120, openChange: null, closeChange: null };
const old: SimulationRow = { ...samsung, date: "2026-08-31" };
delete old.openChange;
delete old.closeChange;
const aapl: SimulationRow = {
  date: "2026-09-15", kind: "period", openPrice: "100.250000", closePrice: "101.500000",
  boughtShares: 0, heldShares: 400, cash: "2.500000", principal: "10000000",
  balance: "40600.000000", balanceKrw: "54810000", profit: "44810000", returnRate: "4.481",
  fxRate: "1350.000000", fxRateDate: "2026-09-15",
  openChange: up({ comparedTo: "2026-09-14", absolute: "0.062500", percent: "0.06", split: { ratio: "4:1" } }),
  closeChange: down,
};

const lump = (rows: SimulationRow[], stockCurrency = "KRW") =>
  render(<PerformanceTable rows={rows} currency="KRW" stockCurrency={stockCurrency} hasMore={false} onLoadMore={vi.fn()} />);

const recurringRow = (over: Partial<RecurringStockRow>): RecurringStockRow => ({
  date: "2026-10-02", kind: "contribution", openPrice: "71200", closePrice: "71800",
  boughtShares: 7, heldShares: 240, pending: "12345", dividendCash: "0", contributed: "16500000",
  contributedKrw: "16500000", balance: "17232000", profit: "744345", returnRate: "0.045112",
  contribution: "500000", tradeFee: "74", openChange: up(), closeChange: down, ...over,
});
const recurring = (rows: RecurringStockRow[], stockCurrency = "KRW") =>
  render(<RecurringStockTable rows={rows} principalCurrency="KRW" stockCurrency={stockCurrency} hasMore={false}
    onLoadMore={vi.fn()} />);

/** 머리글 — 화면 읽기 이름(숨은 글자 포함)과 아래 줄의 통화. */
const headings = () => screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");

function cells(date: string, heading: string): HTMLElement {
  const index = headings().indexOf(heading);
  expect(index, `열 없음: ${heading} (${headings().join(", ")})`).toBeGreaterThanOrEqual(0);
  const row = screen.getAllByRole("row").find((r) => (within(r).queryAllByRole("cell")[0]?.textContent ?? "").startsWith(date));
  expect(row, `행 없음: ${date}`).toBeDefined();
  return within(row as HTMLElement).getAllByRole("cell")[index];
}

const LUMP_KRW = [
  "날짜", "시작가", "시작가 등락폭", "시작가 등락률", "종가", "종가 등락폭", "종가 등락률", "주당 배당금", "배당율", "배당금 총액",
  "배당 소득세", "구매 주식수", "매매 수수료", "보유 주식", "예수금", "투자금", "잔고", "투자 수익", "수익율",
];

describe("열 차례와 머리글", () => {
  it("일시금 — 시작가·종가 바로 뒤에 두 열씩, 다른 열 차례는 그대로다", () => {
    lump([samsung]);
    expect(headings()).toEqual(LUMP_KRW);
  });

  it("보이는 글자는 등락폭·등락률이고 화면 읽기 이름이 가격을 밝힌다", () => {
    lump([samsung]);
    for (const price of ["시작가", "종가"]) {
      for (const name of ["등락폭", "등락률"]) {
        const header = screen.getByRole("columnheader", { name: `${price} ${name}` });
        const hidden = header.querySelector(".sr-only");
        expect(hidden?.textContent?.trim()).toBe(price);
        expect((header.textContent ?? "").replace(hidden?.textContent ?? "", "").trim()).toBe(name);
      }
    }
  });

  it("해외 종목 — 등락폭 아래 줄에 종목 통화, 등락률은 통화 없음", () => {
    lump([aapl], "USD");
    const all = headings();
    const at = all.indexOf("시작가 (USD)");
    expect(all.slice(at, at + 6)).toEqual([
      "시작가 (USD)", "시작가 등락폭 (USD)", "시작가 등락률", "종가 (USD)", "종가 등락폭 (USD)", "종가 등락률",
    ]);
  });

  it("적립식 — 같은 꼴(납입액 뒤 시작가 묶음·종가 묶음)", () => {
    recurring([recurringRow({})]);
    expect(headings().slice(0, 9)).toEqual([
      "날짜", "납입액", "시작가", "시작가 등락폭", "시작가 등락률", "종가", "종가 등락폭", "종가 등락률", "구매 주식수",
    ]);
  });

  it("적립식 해외 — 등락폭에만 종목 통화", () => {
    recurring([recurringRow({ fxRate: "1350.000000", fxRateDate: "2026-10-02" })], "USD");
    const all = headings();
    expect(all).toContain("시작가 등락폭 (USD)");
    expect(all).toContain("종가 등락률");
  });
});

describe("칸", () => {
  it("오름은 ▲·빨강, 등락률은 +와 %다", () => {
    lump([samsung]);
    const amount = cells("2026-10-01", "시작가 등락폭");
    expect(amount).toHaveTextContent("▲ 500.00");
    expect(amount.className).toContain("text-red-600");
    const rate = cells("2026-10-01", "시작가 등락률");
    expect(rate).toHaveTextContent("+0.60%");
    expect(rate.className).toContain("text-red-600");
  });

  it("내림은 ▼·파랑·크기만, 등락률은 서버 부호 그대로다", () => {
    lump([samsung]);
    const amount = cells("2026-10-01", "종가 등락폭");
    expect(amount.textContent).toBe("▼ 300.00");
    expect(amount.className).toContain("text-blue-600");
    expect(cells("2026-10-01", "종가 등락률").textContent).toBe("-0.36%");
  });

  it("같으면 0·회색이고 기호가 없다", () => {
    lump([dividend]);
    const amount = cells("2026-09-30", "시작가 등락폭");
    expect(amount.textContent).toBe("0.00");
    expect(amount.className).toContain("text-gray-500");
    expect(cells("2026-09-30", "시작가 등락률").textContent).toBe("0.00%");
  });

  it("비율만 없으면 등락률만 —다", () => {
    lump([dividend]);
    expect(cells("2026-09-30", "종가 등락폭").textContent).toBe("▲ 500.00");
    expect(cells("2026-09-30", "종가 등락률").textContent).toBe("—");
  });

  it("비교할 행이 없으면(null) 두 칸 —, 키가 없어도 —다", () => {
    lump([first, old]);
    for (const date of ["2026-09-01", "2026-08-31"]) {
      for (const heading of ["시작가 등락폭", "시작가 등락률", "종가 등락폭", "종가 등락률"]) {
        expect(cells(date, heading).textContent).toBe("—");
      }
    }
  });

  it("칸 title은 비교한 날짜다 — 주·월 표에서 어느 행과 견줬는지", () => {
    lump([dividend]);
    expect(cells("2026-09-30", "시작가 등락폭")).toHaveAttribute("title", "2026-09-30 대비");
    expect(cells("2026-09-30", "종가 등락률")).toHaveAttribute("title", "2026-09-29 대비");
    lump([first]);
    expect(cells("2026-09-01", "시작가 등락폭")).not.toHaveAttribute("title");
  });

  it("분할을 맞춘 칸은 ✂ — 이름과 title로 밝힌다", () => {
    lump([aapl], "USD");
    const amount = cells("2026-09-15", "시작가 등락폭 (USD)");
    expect(amount.textContent).toContain("▲ 0.06");
    const mark = within(amount).getByRole("img", { name: "4:1 분할 반영 — 직전 값을 분할 비율로 맞춰 견줬습니다" });
    expect(mark).toHaveTextContent("✂");
    expect(mark).toHaveAttribute("title", "4:1 분할 반영 — 직전 값을 분할 비율로 맞춰 견줬습니다");
    expect(within(cells("2026-09-15", "종가 등락폭 (USD)")).queryByRole("img")).toBeNull();
  });

  it("다른 칸의 값은 그대로다", () => {
    lump([samsung]);
    expect(cells("2026-10-01", "시작가").textContent).toBe("84,000.00");
    expect(cells("2026-10-01", "종가").textContent).toBe("85,300.00");
    expect(cells("2026-10-01", "보유 주식").textContent).toBe("120");
  });

  it("적립식도 같은 칸이다", () => {
    recurring([recurringRow({}), recurringRow({ date: "2026-09-04", openChange: null, closeChange: null })]);
    expect(cells("2026-10-02", "시작가 등락폭").textContent).toBe("▲ 500.00");
    expect(cells("2026-10-02", "종가 등락률").textContent).toBe("-0.36%");
    expect(cells("2026-09-04", "종가 등락폭").textContent).toBe("—");
  });
});

describe("날짜 칸 고정", () => {
  it("일시금 — 머리·몸의 첫 칸이 왼쪽에 고정되고 배경이 불투명하다", () => {
    lump([samsung, dividend]);
    const head = screen.getAllByRole("columnheader")[0];
    expect(head.className).toMatch(/\bsticky\b/);
    expect(head.className).toMatch(/\bleft-0\b/);
    expect(head.className).toMatch(/\bbg-white\b/);
    const plain = cells("2026-10-01", "날짜");
    expect(plain.className).toMatch(/\bsticky\b.*\bleft-0\b|\bleft-0\b.*\bsticky\b/);
    expect(plain.className).toMatch(/\bbg-white\b/);
    // 배당락 행은 행의 옅은 색을 불투명한 흰 바탕 위에 겹친다 — 밀린 칸이 비쳐 보이지 않는다
    const marked = cells("2026-09-30", "날짜");
    expect(marked.className).toMatch(/\bbg-white\b/);
    expect(marked.className).toContain("from-amber-50/40");
  });

  it("적립식 — 행 색과 같은 불투명 배경", () => {
    recurring([recurringRow({}), recurringRow({ date: "2026-09-25", kind: "dividend" })]);
    expect(screen.getAllByRole("columnheader")[0].className).toMatch(/\bsticky\b/);
    expect(cells("2026-10-02", "날짜").className).toMatch(/\bsticky\b/);
    expect(cells("2026-10-02", "날짜").className).toMatch(/\bbg-white\b/);
    expect(cells("2026-09-25", "날짜").className).toMatch(/\bbg-amber-50\b/);
  });
});
