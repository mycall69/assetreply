/**
 * 일자별 상세 표 테스트 (T025) — contracts/ui-wireframes.md W2.
 *
 * FR-021: 고시 없는 날은 행을 만들지 않는다 — 날짜가 연속하지 않는 것이 정상이다.
 * FR-024: 파생 4종이 "현재 스프레드를 과거에 적용한 가정"임을 밝혀야 한다.
 * FR-025: 잠정 행을 구분한다.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/fx/DailyTable";
import type { DailyResponse } from "@/lib/types";

const DERIVED = {
  cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42",
};

const DATA: DailyResponse = {
  currency: "USD", quoteUnit: 1,
  appliedSpread: { cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" },
  spreadBasis: "current",
  rows: [
    { date: "2026-08-30", baseRate: "1354.200000", isProvisional: true, derived: DERIVED },
    { date: "2026-08-29", baseRate: "1356.100000", isProvisional: false, derived: DERIVED },
    // 08-16 ~ 08-28은 고시 없음 — 행이 없는 것이 정상
    { date: "2026-08-15", baseRate: "1368.500000", isProvisional: false, derived: DERIVED },
  ],
  hasMore: true,
  oldestReturned: "2026-08-15",
};

describe("일자별 상세 표", () => {
  it("6개 열을 표시한다", () => {
    render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    for (const h of ["날짜", "매매기준율", "현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때"]) {
      expect(screen.getByRole("columnheader", { name: h })).toBeInTheDocument();
    }
  });

  it("고시 없는 날의 행을 만들지 않는다", () => {
    render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    expect(screen.queryByText("2026-08-20")).toBeNull();
    expect(screen.getAllByRole("row")).toHaveLength(4); // 헤더 + 3행
  });

  it("파생값이 가정임을 밝힌다", () => {
    render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    expect(screen.getByText(/현재 스프레드를 각 날짜에 적용한 가정/)).toBeInTheDocument();
  });

  it("잠정 행을 구분해 표시한다", () => {
    render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    const row = screen.getByText("2026-08-30").closest("tr") as HTMLElement;
    expect(within(row).getByTitle("잠정값")).toBeInTheDocument();
  });

  it("선택 날짜의 행을 강조한다", () => {
    render(<DailyTable data={DATA} selectedDate="2026-08-15" onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    const row = screen.getByText("2026-08-15").closest("tr") as HTMLElement;
    expect(row).toHaveAttribute("aria-selected", "true");
  });

  it("행을 지정하면 선택 날짜가 바뀐다", async () => {
    const onSelect = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    render(<DailyTable data={DATA} selectedDate={null} onSelect={onSelect} onLoadMore={vi.fn()} />);
    await userEvent.click(screen.getByText("2026-08-29"));
    expect(onSelect).toHaveBeenCalledWith("2026-08-29");
  });

  it("더 보기가 있으면 버튼을 노출한다", () => {
    render(<DailyTable data={DATA} selectedDate={null} onSelect={vi.fn()} onLoadMore={vi.fn()} />);
    expect(screen.getByRole("button", { name: "더 보기" })).toBeInTheDocument();
  });
});
