/**
 * 차트 범례의 결측 (T040) — 007 FR-023, FR-043, ui-wireframes C5.
 *
 * 선이 끊긴 이유를 범례가 말해야 한다 — "결측 N구간". 휴장(이어 그린 구간)은 세지 않는다 — 선은 이어져 있는데 범례만 비었다고
 * 말하게 된다(001 T124와 같은 이유).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SeriesGap, SimulationSeriesResponse } from "@/lib/types";

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const POINTS = [
  { date: "2021-02-27", balance: "80000", returnRate: "0.000000" },
  { date: "2021-03-03", balance: "86000", returnRate: "0.068900" },
  { date: "2021-03-06", balance: "92000", returnRate: "0.137800" },
];

const series = (gaps: SeriesGap[]): SimulationSeriesResponse => ({
  from: "2021-02-27", to: "2021-03-06", principalCurrency: "USD", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: POINTS.length, points: POINTS, gaps,
});

describe("범례", () => {
  it("출처 결측 구간 수를 쓴다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={series([
      { from: "2021-02-28", to: "2021-03-02", reason: "source_missing" },
      { from: "2021-03-04", to: "2021-03-05", reason: "source_missing" }])} />);
    expect(screen.getByTestId("chart-legend").textContent).toContain("결측 2구간");
  });

  it("결측이 없으면 쓰지 않는다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={series([])} />);
    expect(screen.getByTestId("chart-legend").textContent).not.toContain("결측");
  });

  it("휴장은 결측으로 세지 않는다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={series([
      { from: "2021-02-28", to: "2021-03-02", reason: "no_quote" }])} />);
    expect(screen.getByTestId("chart-legend").textContent).not.toContain("결측");
  });
});
