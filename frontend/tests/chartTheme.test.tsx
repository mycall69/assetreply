/**
 * 차트 다섯 종의 테마 (014 반복 2026-10-10c T131) — FR-030, SC-015, research R14-23.
 *
 * 이 파일 안에서 `lightweight-charts`를 모의한다(기존 차트 테스트와 같은 API만 — `applyOptions`·열거형을 쓰지 않는다).
 *
 * - 블랙이면 배경·글자·격자가 어두운 팔레트이고 진한 회색 선은 밝은 회색이다 — 화면만 어두워지고 차트가 흰 상자로 남지 않는다
 * - 테마를 바꾸면 차트를 **다시 만든다**
 * - 밝으면 선택 값이 이 반복 전과 같다(배경·격자를 넣지 않는다)
 */
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompareReturnChart } from "@/components/compare/CompareReturnChart";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import { FxChart } from "@/components/FxChart";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { DARK_CHART } from "@/lib/chartTheme";
import type { SeriesResponse, SimulationSeriesResponse } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";
import { series as compareSeries } from "./support/compareFixtures";
import { rangeSeriesOf } from "./support/indicatorModalFixtures";

const chart = vi.hoisted(() => ({
  options: [] as Record<string, unknown>[],
  series: [] as Record<string, unknown>[],
}));

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: (_el: unknown, options: Record<string, unknown>) => {
    chart.options.push(options);
    return {
      addSeries: (_type: string, options: Record<string, unknown>) => {
        chart.series.push(options);
        return { setData: () => undefined };
      },
      subscribeCrosshairMove: () => undefined,
      subscribeClick: () => undefined,
      timeScale: () => ({ fitContent: () => undefined, setVisibleLogicalRange: () => undefined }),
      remove: () => undefined,
    };
  },
}));

const FX: SeriesResponse = {
  currency: "USD", quoteUnit: 1, from: "2026-08-01", to: "2026-08-30", algorithm: "lttb",
  points: [{ date: "2026-08-14", baseRate: "1372.300000" }, { date: "2026-08-29", baseRate: "1356.100000" }],
  gaps: [], downsampled: false, sourcePointCount: 2,
};
const SIM: SimulationSeriesResponse = {
  from: "2021-08-01", to: "2021-11-30", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 2, gaps: [],
  points: [{ date: "2021-08-02", balance: "80000", returnRate: "0.000000" }, { date: "2021-09-01", balance: "86000", returnRate: "0.068900" }],
};

const CHARTS = [
  ["FxChart", () => <FxChart data={FX} />],
  ["PerformanceChart", () => <PerformanceChart series={SIM} collecting={null} loading={false} />],
  ["ComparisonChart", () => <ComparisonChart items={[{ id: "a", label: "A", start: "2021-08-01", series: SIM }]} loading={false} error={null} />],
  ["CompareReturnChart", () => <CompareReturnChart items={[{ key: "a", name: "A", series: compareSeries([["2020-01-02", "0"], ["2021-01-04", "1.5"]]),
    lineEnd: { date: "2021-01-04", holdingReturnRate: "1.5", afterSaleReturnRate: "1.2" } }]} />],
  ["IndicatorChart", () => <IndicatorChart series={rangeSeriesOf()} range="1y" />],
] as const;

beforeEach(() => {
  chart.options = [];
  chart.series = [];
  document.documentElement.classList.remove("dark");
  useThemeStore.setState({ theme: "light" });
});

afterEach(() => {
  document.documentElement.classList.remove("dark");
  useThemeStore.setState({ theme: "light" });
});

type Layout = { attributionLogo?: boolean; background?: { color?: string }; textColor?: string };
const last = () => chart.options[chart.options.length - 1] as { layout?: Layout; grid?: { vertLines?: { color?: string } } };

describe.each(CHARTS)("%s", (_name, view) => {
  it("밝으면 선택 값이 그대로다", () => {
    render(view());
    expect(last().layout).toEqual({ attributionLogo: false });
    expect(last().grid).toBeUndefined();
  });

  it("블랙이면 어두운 배경·글자·격자이고 진한 회색 선이 없다", () => {
    useThemeStore.setState({ theme: "dark" });
    render(view());
    expect(last().layout).toEqual({ attributionLogo: false, background: { color: DARK_CHART.background }, textColor: DARK_CHART.text });
    expect(last().grid?.vertLines?.color).toBe(DARK_CHART.grid);
    expect(chart.series.map((s) => s.color)).not.toContain("#1f2937");
  });

  it("테마를 바꾸면 다시 만든다", () => {
    render(view());
    const before = chart.options.length;
    act(() => useThemeStore.getState().set("dark"));
    expect(chart.options.length).toBe(before + 1);
    expect(last().layout?.background?.color).toBe(DARK_CHART.background);
  });
});
