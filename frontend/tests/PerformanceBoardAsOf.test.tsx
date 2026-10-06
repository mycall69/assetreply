/**
 * 계산 기준일 표시 (T098) — 005 FR-014a, FR-014b, SC-026, SC-027.
 *
 * **표에만 표시하고 보드가 "오늘까지"로 남으면 둘이 어긋난다**(FR-014b). 상장폐지는
 * 대개 큰 손실인데 알리지 않으면 화면에는 폐지 직전 수익률이 최종 성과처럼 남는다.
 */
// 012 승인 2026-10-06 — 고정 행의 종류 이름 month_first → period(012 FR-008). 단언은 그대로다.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import type { SimulationRow, SimulationSummary } from "@/lib/types";

const CUT: SimulationSummary = {
  principal: "86997", profit: "-50000", returnRate: "-0.574700",
  asOf: "2021-09-02", isFinal: false,
};
const LIVE: SimulationSummary = { ...CUT, asOf: "2026-10-01", isFinal: true };

const ROWS: SimulationRow[] = [{
  date: "2021-09-01", kind: "period", openPrice: "30000", closePrice: "30000",
  boughtShares: 0, heldShares: 2, cash: "100", principal: "86997",
  balance: "60000", profit: "-26897", returnRate: "-0.309200",
}];

describe("보드의 기준일", () => {
  it("계산의 마지막 날을 적는다", () => {
    render(<PerformanceBoard summary={CUT} currency="KRW" />);
    // 기준 줄과 경고 줄 양쪽에 나온다 — 어느 한 쪽만 보는 사용자가 있다.
    expect(screen.getAllByText(/2021-09-02/).length).toBeGreaterThan(0);
  });

  it("시세가 끊겼으면 그 사실을 알린다", () => {
    // SC-026, SC-027
    render(<PerformanceBoard summary={CUT} currency="KRW" />);
    expect(screen.getByRole("status").textContent).toMatch(/시세가 없습니다|끊/);
  });

  it("끝까지 있으면 경고하지 않는다", () => {
    // "확인했고 아니다"와 "확인하지 않았다"가 구별되어야 한다.
    render(<PerformanceBoard summary={LIVE} currency="KRW" />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("표의 기준일", () => {
  it("시세가 끊겼으면 표에서도 드러난다", () => {
    // SC-027 — 보드에만 있으면 표를 보던 사용자는 마지막 행을 오늘로 읽는다.
    render(
      <PerformanceTable rows={ROWS} currency="KRW" summary={CUT} hasMore={false}
        onLoadMore={() => undefined} />,
    );
    const note = screen.getByTestId("table-asof");
    expect(note.textContent).toContain("2021-09-02");
    expect(note.textContent).toMatch(/시세가 없습니다|끊/);
  });

  it("끝까지 있으면 표에 경고를 두지 않는다", () => {
    render(
      <PerformanceTable rows={ROWS} currency="KRW" summary={LIVE} hasMore={false}
        onLoadMore={() => undefined} />,
    );
    expect(screen.queryByTestId("table-asof")).toBeNull();
  });

  it("요약이 없으면 아무 말도 하지 않는다", () => {
    // 모르는 것을 "끊겼다"고 말하면 멀쩡한 종목이 폐지된 것처럼 보인다.
    render(
      <PerformanceTable rows={ROWS} currency="KRW" hasMore={false}
        onLoadMore={() => undefined} />,
    );
    expect(screen.queryByTestId("table-asof")).toBeNull();
  });
});
