/**
 * 투자 비교 표의 상장일 열 (014 반복 2026-10-10f T160) — FR-033, contracts D12.
 *
 * - 주식·가상자산(일시금·적립식) 표에만 대상과 기준일 사이 "상장일" 열이 있다. 예금·부동산 표는 그대로다
 * - 값은 비교 블록 `listing{date, basis}`다 — 키움 상장일이면 날짜만, Yahoo 첫 거래일은 `첫 거래일`, 코인 첫 일봉은 `첫 일봉`을
 *   작은 글자로 밝힌다. 모르면 "—"와 까닭(`title`)
 * - 머리를 눌러 정렬한다 — 날짜 글자 견주기, 비운 칸은 오름·내림 모두 끝이다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CompareTable, type CompareRow } from "@/components/compare/CompareTable";
import type { CompareMethod, ListingDate } from "@/lib/types";
import type { SortState } from "@/stores/compareStore";
import { ok, SAMSUNG_T } from "./support/compareFixtures";

const row = (key: string, name: string, listing: ListingDate | null | undefined): CompareRow => ({
  key, name, href: null,
  state: { status: "ok", data: ok(SAMSUNG_T, listing === undefined ? {} : { listing }) },
});

const ROWS = [
  row("voo", "S&P 500 뱅가드 ETF(VOO)", { date: "2010-09-09", basis: "first_trade" }),
  row("ss", "삼성전자(005930)", { date: "1975-06-11", basis: "listing" }),
  row("btc", "비트코인(BTC)", { date: "2010-07-18", basis: "first_bar" }),
  row("x", "모르는 것", null),
];

function renderTable(method: CompareMethod, sort: SortState | null = null, rows = ROWS) {
  return render(<CompareTable rows={rows} method={method} sort={sort} onSort={vi.fn()} onRetry={vi.fn()} />);
}

const heads = () => screen.getAllByRole("columnheader").map((h) => (h.textContent ?? "").replace(/[▲▼ⓘ]/g, "").trim());
const listingCells = () => screen.getAllByTestId("listing-cell");
const order = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent ?? "");

describe("상장일 열", () => {
  it.each(["lump_sum", "recurring"] as const)("%s 표는 대상과 기준일 사이에 있다", (method) => {
    renderTable(method);
    expect(heads().slice(0, 3)).toEqual(["대상", "상장일", "기준일"]);
  });

  it.each(["deposit", "installment", "hold"] as const)("%s 표에는 없다", (method) => {
    renderTable(method);
    expect(heads()).not.toContain("상장일");
    expect(screen.queryAllByTestId("listing-cell")).toHaveLength(0);
  });

  it("날짜와 기준 — 키움 상장일은 날짜만, Yahoo는 첫 거래일, 코인은 첫 일봉", () => {
    renderTable("lump_sum");
    const [voo, ss, btc] = listingCells();
    expect(voo.textContent).toBe("2010-09-09첫 거래일");
    expect(ss.textContent).toBe("1975-06-11");
    expect(btc.textContent).toBe("2010-07-18첫 일봉");
    expect(voo.getAttribute("title")).toMatch(/시세 출처\(Yahoo\)가 시세를 가진 첫 날/);
  });

  it("모르면 —와 까닭이다(014 전 응답의 칸 없음도 같다)", () => {
    renderTable("lump_sum", null, [row("x", "모르는 것", null), row("y", "옛 응답", undefined)]);
    for (const cell of listingCells()) {
      expect(cell.textContent).toBe("—");
      expect(cell.getAttribute("title")).toMatch(/출처가 상장일을 주지 않았습니다/);
    }
  });

  it("오름차순 정렬 — 비운 칸은 끝", () => {
    renderTable("lump_sum", { key: "listing", direction: "asc" });
    expect(order()).toEqual(["삼성전자(005930)", "비트코인(BTC)", "S&P 500 뱅가드 ETF(VOO)", "모르는 것"]);
  });

  it("내림차순 정렬 — 비운 칸은 여전히 끝", () => {
    renderTable("lump_sum", { key: "listing", direction: "desc" });
    expect(order()).toEqual(["S&P 500 뱅가드 ETF(VOO)", "비트코인(BTC)", "삼성전자(005930)", "모르는 것"]);
  });
});
