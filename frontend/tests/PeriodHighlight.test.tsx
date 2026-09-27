/**
 * 구간 기준 선택 날짜 강조 (T032) — 004 FR-019, FR-019a, FR-019b, FR-020,
 * SC-013, SC-014. contracts/ui-wireframes.md W4.
 *
 * 주·월 단위에서 **선택 날짜가 기준일인 경우가 오히려 드물다.** 기준일만으로 판정하면
 * 강조가 거의 사라지고, 사용자는 선택이 풀린 것으로 오해한다. 그래서 행이 덮는 구간
 * (`periodFrom`~`periodTo`)으로 판정한다 (research R4-7).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/fx/DailyTable";
import { highlightedRow } from "@/stores/fxWorkspaceStore";
import type { DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const week = (date: string, from: string, to: string): PeriodRow => ({
  date, baseRate: "1383.800000", isProvisional: false, derived: DERIVED,
  periodFrom: from, periodTo: to, isOngoing: false,
});

const WEEKLY: DailyResponse = {
  currency: "USD", period: "weekly", quoteUnit: 1, appliedSpread: DERIVED,
  spreadBasis: "current",
  rows: [
    week("2026-09-18", "2026-09-14", "2026-09-20"),
    week("2026-09-11", "2026-09-07", "2026-09-13"),
  ],
  hasMore: false, oldestReturned: "2026-09-11",
};

const props = { onSelect: vi.fn(), onLoadMore: vi.fn() };

describe("구간 포함 판정", () => {
  it("선택 날짜가 속한 구간의 행을 고른다", () => {
    // FR-019 — 2026-09-16(수)은 09-14~09-20 주에 든다.
    expect(highlightedRow(WEEKLY, "2026-09-16")?.date).toBe("2026-09-18");
  });

  it("구간의 경계일도 그 구간에 든다", () => {
    expect(highlightedRow(WEEKLY, "2026-09-14")?.date).toBe("2026-09-18");
    expect(highlightedRow(WEEKLY, "2026-09-20")?.date).toBe("2026-09-18");
  });

  it("기준일 자신도 그 구간에 든다", () => {
    expect(highlightedRow(WEEKLY, "2026-09-18")?.date).toBe("2026-09-18");
  });

  it("어느 구간에도 없으면 고르지 않는다", () => {
    // FR-020 — 그 구간에 고시가 하나도 없는 경우다.
    expect(highlightedRow(WEEKLY, "1990-01-15")).toBeNull();
  });

  it("선택 날짜가 없으면 고르지 않는다", () => {
    expect(highlightedRow(WEEKLY, null)).toBeNull();
  });

  it("표가 없으면 고르지 않는다", () => {
    expect(highlightedRow(null, "2026-09-16")).toBeNull();
  });
});

describe("강조 표시", () => {
  it("선택 날짜가 속한 구간의 행이 강조된다", () => {
    render(<DailyTable data={WEEKLY} selectedDate="2026-09-16" {...props} />);
    const line = screen.getByText("2026-09-18").closest("tr") as HTMLElement;
    expect(line).toHaveAttribute("aria-selected", "true");
  });

  it("강조된 날짜가 선택 날짜와 다르면 그 관계를 알린다", () => {
    // FR-019a, SC-014 — 알리지 않으면 사용자는 자신이 고른 날짜가 바뀌었다고 오해한다.
    render(<DailyTable data={WEEKLY} selectedDate="2026-09-16" {...props} />);
    const note = screen.getByTestId("highlight-note");
    expect(note).toHaveTextContent("2026-09-16");
    expect(note).toHaveTextContent(/속한 주/);
  });

  it("선택 날짜가 곧 기준일이면 덧붙이지 않는다", () => {
    render(<DailyTable data={WEEKLY} selectedDate="2026-09-18" {...props} />);
    expect(screen.queryByTestId("highlight-note")).toBeNull();
  });

  it("속한 구간에 행이 없으면 그 사실을 알린다", () => {
    // FR-020 — 강조가 그냥 사라지면 사용자는 선택이 풀린 것으로 오해한다.
    render(<DailyTable data={WEEKLY} selectedDate="1990-01-15" {...props} />);
    const note = screen.getByTestId("highlight-note");
    expect(note).toHaveTextContent("1990-01-15");
    expect(note).toHaveTextContent(/고시가 없습니다/);
  });

  it("일 단위에서는 덧붙이지 않는다", () => {
    const daily: DailyResponse = {
      ...WEEKLY, period: "daily",
      rows: [week("2026-09-18", "2026-09-18", "2026-09-18")],
    };
    render(<DailyTable data={daily} selectedDate="2026-09-18" {...props} />);
    expect(screen.queryByTestId("highlight-note")).toBeNull();
  });
});
