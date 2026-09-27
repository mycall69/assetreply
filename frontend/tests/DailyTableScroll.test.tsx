/**
 * 이어 보기 표시 (T012, T018) — 004 FR-001, FR-002, FR-004, SC-003, SC-004.
 *
 * `더 보기` 버튼이 사라지고 스크롤이 그 일을 대신한다. 버튼이 사라진 만큼 **상태를
 * 말로 알려야** 한다 — 끝에 도달했는데 알리지 않으면 사용자는 아직 받는 중이라고
 * 여겨 기다린다(FR-002). 조용히 멈추면 데이터가 거기서 끝난 것으로 오해한다(FR-004).
 *
 * 세 상태는 **알림 역할**이다. 눈으로 보는 사용자만 끝을 알면 FR-002가 절반만 성립한다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DailyTable } from "@/components/fx/DailyTable";
import type { DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = {
  cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42",
};

const day = (date: string): PeriodRow => ({
  date, baseRate: "1354.200000", isProvisional: false, derived: DERIVED,
  periodFrom: date, periodTo: date, isOngoing: false,
});

const DATA: DailyResponse = {
  currency: "USD", period: "daily", quoteUnit: 1,
  appliedSpread: { cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" },
  spreadBasis: "current",
  rows: [day("2026-08-30"), day("2026-08-29"), day("2026-08-15")],
  hasMore: true,
  oldestReturned: "2026-08-15",
};

const props = {
  selectedDate: null,
  onSelect: vi.fn(),
  onLoadMore: vi.fn(),
};

describe("이어 보기", () => {
  it("더 보기 버튼이 없다", () => {
    // FR-001 — 002의 버튼 조작을 스크롤이 대체한다.
    render(<DailyTable data={DATA} {...props} />);
    expect(screen.queryByRole("button", { name: "더 보기" })).toBeNull();
  });

  it("끝에 도달하면 그 사실을 알린다", () => {
    // FR-002 — 알리지 않으면 아무 일도 일어나지 않는데 사용자가 기다린다.
    render(<DailyTable data={{ ...DATA, hasMore: false }} {...props} />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("2026-08-15");
    expect(status).toHaveTextContent("모두 표시했습니다");
  });

  it("불러오는 중임을 알린다", () => {
    render(<DailyTable data={DATA} {...props} loadingMore />);
    expect(screen.getByRole("status")).toHaveTextContent("불러오는 중");
  });

  it("실패해도 이미 표시된 행은 남는다", () => {
    // FR-004 — 조용히 멈추면 데이터가 거기서 끝난 것으로 오해한다.
    render(<DailyTable data={DATA} {...props} loadError="이어서 불러오지 못했습니다." />);
    expect(screen.getByText("2026-08-30")).toBeInTheDocument();
    expect(screen.getByText("2026-08-15")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("불러오지 못했습니다");
  });

  it("실패하면 다시 시도할 수단이 있다", async () => {
    const onLoadMore = vi.fn();
    render(
      <DailyTable data={DATA} {...props} onLoadMore={onLoadMore} loadError="실패" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onLoadMore).toHaveBeenCalled();
  });

  it("끝에 도달하면 감시 지점을 두지 않는다", () => {
    // SC-003, SC-004 — 더 받을 것이 없는데 요청이 나가는 경로 자체를 없앤다.
    const { container } = render(
      <DailyTable data={{ ...DATA, hasMore: false }} {...props} />,
    );
    expect(container.querySelector("[data-testid='scroll-sentinel']")).toBeNull();
  });

  it("더 받을 것이 있으면 감시 지점을 둔다", () => {
    const { container } = render(<DailyTable data={DATA} {...props} />);
    expect(container.querySelector("[data-testid='scroll-sentinel']")).not.toBeNull();
  });

  it("실패한 동안에는 감시 지점을 두지 않는다", () => {
    // 실패 즉시 다시 관찰하면 같은 오류를 무한히 반복한다. 재시도는 사람이 고른다.
    const { container } = render(
      <DailyTable data={DATA} {...props} loadError="실패" />,
    );
    expect(container.querySelector("[data-testid='scroll-sentinel']")).toBeNull();
  });
});
