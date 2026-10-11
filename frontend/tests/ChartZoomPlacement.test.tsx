/**
 * 확대 단추 자리와 외환·지표 그래프의 두 지점 확대 (014 반복 2026-10-11c T194) — spec FR-039, SC-024, contracts D17, research R14-31.
 *
 * - 확대 단추·상태 줄은 그래프 칸의 오른쪽 위, **오른쪽 가격 축 폭 + 8px만큼 왼쪽**·위 4px다(축 숫자를 가리지 않는다). 축 폭은 처음 누를 때만 잰다
 *   (`priceScale("right").width()` — 그릴 때 부르면 그 API가 없는 기존 모의가 깨진다)
 * - 외환 추이·지표 일봉 그래프에도 두 지점 확대가 있다. 지표의 [리셋]은 그 기간의 처음 보이는 범위(`setVisibleLogicalRange`, "모두"면 `fitContent`)이고
 *   기간을 바꾸면 확대가 풀린다. 장중(1일·5일)에는 확대가 없다
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FxChart } from "@/components/FxChart";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SeriesResponse, SimulationSeriesResponse } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";
import { intradayOf, rangeSeriesOf } from "./support/indicatorModalFixtures";

const chart = vi.hoisted(() => ({
  move: null as null | ((param: unknown) => void),
  axisReads: 0,
  axisWidth: 62,
  visibleRange: [] as { from: unknown; to: unknown }[],
  logicalRange: [] as { from: number; to: number }[],
  fitContent: 0,
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
    timeScale: () => ({
      fitContent: () => { chart.fitContent += 1; },
      setVisibleRange: (range: { from: unknown; to: unknown }) => { chart.visibleRange.push(range); },
      setVisibleLogicalRange: (range: { from: number; to: number }) => { chart.logicalRange.push(range); },
      coordinateToTime: () => null,
    }),
    priceScale: () => { chart.axisReads += 1; return { width: () => chart.axisWidth }; },
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.move = null;
  chart.axisReads = 0;
  chart.axisWidth = 62;
  chart.visibleRange.length = 0;
  chart.logicalRange.length = 0;
  chart.fitContent = 0;
  useThemeStore.setState({ theme: "light" });
});

function pick(surface: string, date: string) {
  act(() => chart.move?.({ time: date, point: { x: 10, y: 10 }, sourceEvent: { clientX: 120, clientY: 50 } }));
  const el = screen.getByTestId(surface);
  fireEvent.mouseDown(el, { clientX: 120, clientY: 50 });
  fireEvent.click(el, { clientX: 120, clientY: 50 });
}
const controls = () => screen.queryByTestId("chart-zoom-controls");
const resetButton = () => screen.queryByRole("button", { name: "리셋" });

const SERIES: SimulationSeriesResponse = {
  from: "2024-01-02", to: "2024-04-01", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false, algorithm: "lttb",
  sourcePointCount: 3, gaps: [],
  points: ["2024-01-02", "2024-02-01", "2024-04-01"].map((date) => ({ date, balance: "1000", returnRate: "0.1" })),
};

describe("단추 자리", () => {
  it("오른쪽 가격 축 폭 + 8px만큼 왼쪽, 위 4px다", () => {
    chart.axisWidth = 97;
    render(<PerformanceChart series={SERIES} collecting={null} loading={false} />);
    pick("performance-canvas", "2024-01-02");
    expect(controls()).toHaveStyle({ right: "105px", top: "4px" });
    pick("performance-canvas", "2024-04-01");
    expect(controls()).toHaveStyle({ right: "105px", top: "4px" });
  });

  it("축 폭은 처음 누를 때만 잰다 — 그릴 때는 부르지 않는다", () => {
    render(<PerformanceChart series={SERIES} collecting={null} loading={false} />);
    expect(chart.axisReads).toBe(0);
    pick("performance-canvas", "2024-01-02");
    pick("performance-canvas", "2024-04-01");
    expect(chart.axisReads).toBe(1);
  });
});

describe("외환 추이 그래프", () => {
  const data = {
    currency: "USD", from: "2024-01-02", to: "2024-04-01", quoteUnit: 1, downsampled: false, algorithm: "lttb", sourcePointCount: 3,
    points: ["2024-01-02", "2024-02-01", "2024-04-01"].map((date) => ({ date, baseRate: "1300.0", isProvisional: false })), gaps: [],
  } as unknown as SeriesResponse;

  it("두 지점으로 확대하고 [리셋]이면 처음 범위다", () => {
    render(<FxChart data={data} />);
    const drawn = chart.fitContent;
    pick("chart-canvas", "2024-04-01");
    expect(screen.getByTestId("chart-zoom-status")).toHaveTextContent("시작 2024-04-01");
    pick("chart-canvas", "2024-01-02");
    expect(chart.visibleRange).toEqual([{ from: "2024-01-02", to: "2024-04-01" }]);
    fireEvent.click(resetButton() as HTMLElement);
    expect(chart.fitContent).toBe(drawn + 1);
    expect(resetButton()).toBeNull();
  });
});

describe("지표 일봉 그래프", () => {
  const points = ["2025-10-01", "2025-12-01", "2026-03-02", "2026-06-01", "2026-10-08"].map((date) => ({ date, value: "100.000000" }));
  const series = rangeSeriesOf({ range: "1y", points, windows: { "1m": "2026-09-08", "1y": "2025-12-01", "5y": "2021-10-08" } });

  it("두 지점으로 확대하고 [리셋]이면 그 기간의 처음 범위다 — 전체가 아니다", () => {
    render(<IndicatorChart series={series} range="1y" />);
    const first = chart.logicalRange.at(-1);
    expect(first).toEqual({ from: 1, to: 4 });
    pick("indicator-canvas", "2026-03-02");
    pick("indicator-canvas", "2026-06-01");
    expect(chart.visibleRange).toEqual([{ from: "2026-03-02", to: "2026-06-01" }]);
    const fitted = chart.fitContent;
    fireEvent.click(resetButton() as HTMLElement);
    expect(chart.logicalRange.at(-1)).toEqual({ from: 1, to: 4 });
    expect(chart.fitContent).toBe(fitted);
    expect(resetButton()).toBeNull();
  });

  it("\"모두\"의 [리셋]은 전체다", () => {
    render(<IndicatorChart series={series} range="all" />);
    pick("indicator-canvas", "2026-03-02");
    pick("indicator-canvas", "2026-06-01");
    const fitted = chart.fitContent;
    fireEvent.click(resetButton() as HTMLElement);
    expect(chart.fitContent).toBe(fitted + 1);
  });

  it("기간을 바꾸면 확대가 풀린다", () => {
    const { rerender } = render(<IndicatorChart series={series} range="1y" />);
    pick("indicator-canvas", "2026-03-02");
    pick("indicator-canvas", "2026-06-01");
    expect(resetButton()).not.toBeNull();
    rerender(<IndicatorChart series={series} range="5y" />);
    expect(resetButton()).toBeNull();
  });

  it("장중(1일·5일)에는 확대가 없다", () => {
    render(<IndicatorChart series={intradayOf()} range="1d" />);
    const canvas = screen.getByTestId("indicator-canvas");
    fireEvent.mouseDown(canvas, { clientX: 120, clientY: 50 });
    fireEvent.click(canvas, { clientX: 120, clientY: 50 });
    expect(controls()).toBeNull();
  });
});
