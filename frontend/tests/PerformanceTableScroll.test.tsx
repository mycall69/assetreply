/**
 * 성과 표의 이어 보기 (T047) — 005 FR-029, FR-030, SC-012.
 *
 * 004가 세운 방식을 잇는다. `더 보기` 버튼이 사라진 만큼 **상태를 말로 알려야** 한다 —
 * 끝에 도달했는데 알리지 않으면 사용자는 아직 받는 중이라고 여겨 기다린다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow } from "@/lib/types";

const row = (date: string): SimulationRow => ({
  date, kind: "month_first", openPrice: "40000", closePrice: "40000", boughtShares: 0,
  heldShares: 2, cash: "6997", principal: "86997", balance: "80000",
  profit: "0", returnRate: "0.000000",
});

const base = {
  rows: [row("2024-08-01"), row("2024-07-01")],
  currency: "KRW",
  loadingMore: false,
  loadError: null,
  onLoadMore: vi.fn(),
};

describe("이어 보기", () => {
  it("더 보기 버튼이 없다", () => {
    render(<PerformanceTable {...base} hasMore />);
    expect(screen.queryByRole("button", { name: "더 보기" })).toBeNull();
  });

  it("더 받을 것이 있으면 감시 지점을 둔다", () => {
    const { container } = render(<PerformanceTable {...base} hasMore />);
    expect(container.querySelector("[data-testid='scroll-sentinel']")).not.toBeNull();
  });

  it("끝에 도달하면 감시 지점을 두지 않는다", () => {
    // SC-012 — 더 받을 것이 없는데 요청이 나가는 경로 자체를 없앤다.
    const { container } = render(<PerformanceTable {...base} hasMore={false} />);
    expect(container.querySelector("[data-testid='scroll-sentinel']")).toBeNull();
  });

  it("끝에 도달하면 그 사실을 알린다", () => {
    // FR-030 — 알리지 않으면 아직 받는 중이라고 여겨 기다린다.
    render(<PerformanceTable {...base} hasMore={false} />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("2024-07-01");
    expect(status).toHaveTextContent("모두 표시했습니다");
  });

  it("불러오는 중임을 알린다", () => {
    render(<PerformanceTable {...base} hasMore loadingMore />);
    expect(screen.getByRole("status")).toHaveTextContent("불러오는 중");
  });

  it("실패해도 이미 표시된 행은 남는다", () => {
    render(
      <PerformanceTable {...base} hasMore loadError="이어서 불러오지 못했습니다." />,
    );
    expect(screen.getByText("2024-08-01")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("불러오지 못했습니다");
  });

  it("실패하면 다시 시도할 수단이 있다", async () => {
    const onLoadMore = vi.fn();
    render(
      <PerformanceTable {...base} hasMore loadError="실패" onLoadMore={onLoadMore} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onLoadMore).toHaveBeenCalled();
  });

  it("실패한 동안에는 감시 지점을 두지 않는다", () => {
    // 즉시 다시 관찰하면 같은 오류를 무한히 반복한다. 재시도는 사람이 고른다.
    const { container } = render(
      <PerformanceTable {...base} hasMore loadError="실패" />,
    );
    expect(container.querySelector("[data-testid='scroll-sentinel']")).toBeNull();
  });
});
