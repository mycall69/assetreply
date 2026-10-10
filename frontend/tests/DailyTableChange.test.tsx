/**
 * 외환 일자별 표의 등락폭·등락율 (014 반복 2026-10-10d T143) — FR-031, contracts D10.
 *
 * - 두 열은 송금 받을 때 오른쪽 끝이다. 앞 여섯 열의 차례는 그대로다
 * - 값은 서버가 `Decimal`로 낸 글자다 — 화면은 기호·색·부호만 입힌다(헌법 원칙 VI)
 * - 오르면 ▲·빨강, 내리면 ▼·파랑, 같으면 0·회색 — 색만으로 전하지 않는다
 * - 비교 대상이 없으면(`change`가 없거나 `null`) "—", 비율만 없으면 등락율만 "—"
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/fx/DailyTable";
import type { DailyChange, DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = {
  cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42",
};

const day = (
  date: string, baseRate: string, change: DailyChange | null | undefined, isProvisional = false,
): PeriodRow => ({
  date, baseRate, isProvisional, derived: DERIVED,
  periodFrom: date, periodTo: date, isOngoing: false,
  ...(change === undefined ? {} : { change }),
});

const up: DailyChange = { comparedTo: "2026-10-07", absolute: "2.300000", percent: "0.16", direction: "up" };
const down: DailyChange = { comparedTo: "2026-10-06", absolute: "-1.100000", percent: "-0.08", direction: "down" };
const flat: DailyChange = { comparedTo: "2026-10-05", absolute: "0.000000", percent: "0.00", direction: "flat" };

const DATA: DailyResponse = {
  currency: "USD", period: "daily", quoteUnit: 1,
  appliedSpread: { cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" },
  spreadBasis: "current",
  rows: [
    day("2026-10-09", "1427.100000", { ...up, comparedTo: "2026-10-08", absolute: "1.800000", percent: "0.13" }, true),
    day("2026-10-08", "1425.300000", up),
    day("2026-10-07", "1423.000000", down),
    day("2026-10-06", "1424.100000", flat),
    day("2026-10-05", "1424.100000", { ...up, absolute: "12.345678", percent: null }),
    day("2026-10-02", "1411.750000", undefined),
    day("2003-01-02", "1186.900000", null),
  ],
  hasMore: false,
  oldestReturned: "2003-01-02",
};

function renderTable() {
  render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
}

/** 그 날짜 행의 마지막 두 칸(등락폭·등락율). */
function changeCells(date: string): [HTMLElement, HTMLElement] {
  const row = screen.getAllByRole("row").find((r) => r.textContent?.startsWith(date));
  if (row === undefined) throw new Error(`행이 없다: ${date}`);
  const cells = within(row).getAllByRole("cell");
  return [cells[cells.length - 2], cells[cells.length - 1]];
}

describe("외환 일자별 표의 등락", () => {
  it("등락폭·등락율이 송금 받을 때 오른쪽 끝에 있다", () => {
    renderTable();
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual([
      "날짜", "매매기준율", "현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때", "등락폭", "등락율",
    ]);
  });

  it("오르면 ▲·빨강이고 등락율에 + 부호가 붙는다", () => {
    renderTable();
    const [absolute, percent] = changeCells("2026-10-08");
    expect(absolute.textContent).toBe("▲ 2.30");
    expect(percent.textContent).toBe("+0.16%");
    expect(absolute.className).toContain("text-red-600");
    expect(percent.className).toContain("text-red-600");
  });

  it("내리면 ▼·파랑이고 서버의 음수 글자 그대로다", () => {
    renderTable();
    const [absolute, percent] = changeCells("2026-10-07");
    expect(absolute.textContent).toBe("▼ 1.10");
    expect(percent.textContent).toBe("-0.08%");
    expect(absolute.className).toContain("text-blue-600");
    expect(percent.className).toContain("text-blue-600");
  });

  it("같으면 기호 없이 0이고 회색이다", () => {
    renderTable();
    const [absolute, percent] = changeCells("2026-10-06");
    expect(absolute.textContent).toBe("0.00");
    expect(percent.textContent).toBe("0.00%");
    expect(absolute.className).toContain("text-gray-500");
  });

  it("등락폭은 매매기준율과 같은 형식(formatRate)이다", () => {
    renderTable();
    const [absolute] = changeCells("2026-10-05");
    expect(absolute.textContent).toBe("▲ 12.34");
  });

  it("비율만 없으면 등락율만 —다", () => {
    renderTable();
    const [absolute, percent] = changeCells("2026-10-05");
    expect(absolute.textContent).not.toBe("—");
    expect(percent.textContent).toBe("—");
  });

  it("change가 없거나 null이면 두 칸 모두 —다", () => {
    renderTable();
    for (const date of ["2026-10-02", "2003-01-02"]) {
      const [absolute, percent] = changeCells(date);
      expect([absolute.textContent, percent.textContent]).toEqual(["—", "—"]);
    }
  });

  it("잠정 행도 등락을 보이고 ⚠는 그대로다", () => {
    renderTable();
    const [absolute, percent] = changeCells("2026-10-09");
    expect([absolute.textContent, percent.textContent]).toEqual(["▲ 1.80", "+0.13%"]);
    expect(screen.getByTitle("잠정값")).toBeInTheDocument();
  });
});
