/**
 * 행 표시 3종 (T030, T031) — 004 FR-013, FR-014, FR-015a, FR-015b, SC-007, SC-008,
 * SC-015, SC-016. contracts/ui-wireframes.md W2.
 *
 * **셋을 하나로 뭉뚱그리지 않는다.** 기준일이 옮겨졌다·구간이 진행 중이다·값이
 * 잠정이다는 서로 다른 사실이고, 합치면 사용자가 이유를 알 수 없어 표시가 무의미해진다.
 *
 * 옮겨진 행은 **원래 기준일을 함께 알린다**. 없으면 사용자는 그 값을 금요일·말일의
 * 값으로 믿는다 — 값은 정확한데 무엇의 값인지를 잘못 알게 된다 (FR-013).
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/fx/DailyTable";
import { PeriodRowBadges } from "@/components/fx/PeriodRowBadges";
import type { DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const row = (over: Partial<PeriodRow> = {}): PeriodRow => ({
  date: "2026-07-16", baseRate: "1401.200000", isProvisional: false, derived: DERIVED,
  periodFrom: "2026-07-13", periodTo: "2026-07-19", isOngoing: false, ...over,
});

describe("옮겨진 기준일 표시", () => {
  it("옮겨진 행에 원래 기준일을 알린다", () => {
    // FR-013, SC-007 — 2026-07-17(금)에 고시가 없어 07-16(목) 값이 쓰였다.
    render(<PeriodRowBadges row={row({ shiftedFrom: "2026-07-17" })} unit="weekly" />);
    const badge = screen.getByLabelText(/2026-07-17/);
    expect(badge).toHaveTextContent("📅");
    expect(badge).toHaveAccessibleName(/2026-07-16/);
  });

  it("월 단위는 말일을 원래 기준일로 알린다", () => {
    render(
      <PeriodRowBadges
        row={row({ date: "2026-08-14", shiftedFrom: "2026-08-31",
                   periodFrom: "2026-08-01", periodTo: "2026-08-31" })}
        unit="monthly"
      />,
    );
    expect(screen.getByLabelText(/2026-08-31/)).toHaveAccessibleName(/말일/);
  });

  it("옮겨지지 않은 행에는 표시가 없다", () => {
    // FR-014, SC-008 — 모든 행에 늘 표시가 있으면 구별의 의미가 사라진다.
    const { container } = render(
      <PeriodRowBadges row={row({ date: "2026-07-24" })} unit="weekly" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("일 단위에는 표시가 없다", () => {
    const { container } = render(<PeriodRowBadges row={row()} unit="daily" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("진행 중 표시", () => {
  it("아직 끝나지 않은 주를 알린다", () => {
    // FR-015a, SC-015 — 없으면 사용자는 그 값을 그 주의 마지막 값으로 읽는다.
    render(<PeriodRowBadges row={row({ isOngoing: true })} unit="weekly" />);
    const badge = screen.getByLabelText(/아직 끝나지 않/);
    expect(badge).toHaveTextContent("⏳");
    expect(badge).toHaveAccessibleName(/주/);
  });

  it("아직 끝나지 않은 달을 알린다", () => {
    render(<PeriodRowBadges row={row({ isOngoing: true })} unit="monthly" />);
    expect(screen.getByLabelText(/아직 끝나지 않/)).toHaveAccessibleName(/달/);
  });

  it("기호만으로 전달하지 않는다", () => {
    // 접근성 — `📅`·`⏳`는 장식이 아니라 의미를 지닌다.
    render(
      <PeriodRowBadges row={row({ isOngoing: true, shiftedFrom: "2026-07-17" })} unit="weekly" />,
    );
    for (const badge of screen.getAllByRole("img")) {
      expect(badge).toHaveAccessibleName();
      expect(badge.getAttribute("aria-label")).not.toBe("");
    }
  });
});

describe("세 표시가 겹칠 때", () => {
  const DATA: DailyResponse = {
    currency: "USD", period: "weekly", quoteUnit: 1, appliedSpread: DERIVED,
    spreadBasis: "current",
    rows: [
      row({ date: "2026-09-23", isProvisional: true, isOngoing: true,
            shiftedFrom: "2026-09-25", periodFrom: "2026-09-21", periodTo: "2026-09-27" }),
      row({ date: "2026-09-18", periodFrom: "2026-09-14", periodTo: "2026-09-20" }),
    ],
    hasMore: false, oldestReturned: "2026-09-18",
  };

  const props = { selectedDate: null, onSelect: vi.fn(), onLoadMore: vi.fn() };

  it("셋이 서로 다른 기호로 나타난다", () => {
    // FR-015b, SC-016 — 하나로 합치면 사용자가 이유를 알 수 없다.
    render(<DailyTable data={DATA} {...props} />);
    const line = screen.getByText("2026-09-23").closest("tr") as HTMLElement;
    expect(within(line).getByText("📅")).toBeInTheDocument();
    expect(within(line).getByText("⏳")).toBeInTheDocument();
    expect(within(line).getByTitle("잠정값")).toBeInTheDocument();
  });

  it("조건이 아닌 행에는 그 표시가 없다", () => {
    render(<DailyTable data={DATA} {...props} />);
    const line = screen.getByText("2026-09-18").closest("tr") as HTMLElement;
    expect(within(line).queryByText("📅")).toBeNull();
    expect(within(line).queryByText("⏳")).toBeNull();
  });
});
