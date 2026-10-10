/**
 * 지표 그래프의 처음 보이는 범위 (014 반복 2026-10-10c T130) — FR-011, FR-012, SC-002, contracts A2·D3, research R14-22.
 *
 * 이 파일 안에서 `lightweight-charts`를 모의한다.
 *
 * - 기간은 **처음 보이는 범위**다 — 받은 점(일봉 전부)을 모두 그리고 `setVisibleLogicalRange`로 창 시작 이상 첫 점의 차례 ~ 마지막 차례를 보인다.
 *   왼쪽으로 끌면 앞 구간이 이어서 보인다(라이브러리 기본 동작). "모두"(창 없음)는 전부를 맞춘다
 * - 기간을 바꾸면 그래프를 **다시 만들지 않고** 보이는 범위만 바꾼다 — 같은 본문이다
 * - 창 안에 점이 없으면(오래 멈춘 지표) 마지막 30점이다
 * - 장중(일·주)은 확정 선과 같은 **진한 실선**이고, 처음 범위는 본문의 `window`다
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import type { IndicatorPoint } from "@/lib/types";
import { intradayOf, rangeSeriesOf } from "./support/indicatorModalFixtures";

const chart = vi.hoisted(() => ({
  created: 0,
  series: [] as { options: Record<string, unknown>; data: { time: string | number; value: number }[] }[],
  range: null as { from: number; to: number } | null,
  fitted: 0,
}));

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => {
    chart.created += 1;
    return {
      addSeries: (_type: string, options: Record<string, unknown>) => {
        const entry = { options, data: [] as { time: string | number; value: number }[] };
        chart.series.push(entry);
        return { setData: (data: { time: string | number; value: number }[]) => { entry.data = data; } };
      },
      subscribeCrosshairMove: () => undefined,
      timeScale: () => ({
        fitContent: () => { chart.fitted += 1; },
        setVisibleLogicalRange: (r: { from: number; to: number }) => { chart.range = r; },
      }),
      remove: () => undefined,
    };
  },
}));

beforeEach(() => {
  chart.created = 0;
  chart.series = [];
  chart.range = null;
  chart.fitted = 0;
});

/** 2024-01-01부터 날마다(휴장 없이 — 차례 계산만 본다). */
function daily(n: number): IndicatorPoint[] {
  return Array.from({ length: n }, (_, i) => ({
    date: new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10), value: `${100 + i}.000000`,
  }));
}

const POINTS = daily(1000); // 2024-01-01 ~ 2026-09-26
const WINDOWS = { "1m": "2026-08-26", "1y": "2025-10-09", "5y": "2021-10-09", "10y": "2016-10-09", "20y": "2006-10-09", all: null };
const series = rangeSeriesOf({ points: POINTS, sourcePointCount: 1000, windows: WINDOWS });
const first = (start: string) => POINTS.findIndex((p) => p.date >= start);

describe("일봉 기간", () => {
  it("받은 점 전부를 그리고 처음 범위는 창 시작 이상 첫 점부터 마지막까지다", () => {
    render(<IndicatorChart series={series} range="1y" />);
    expect(chart.series.reduce((n, s) => n + s.data.length, 0)).toBe(1000);
    expect(chart.range).toEqual({ from: first("2025-10-09"), to: 999 });
  });

  it("창이 첫 점보다 앞이면 처음부터다", () => {
    render(<IndicatorChart series={series} range="5y" />);
    expect(chart.range).toEqual({ from: 0, to: 999 });
  });

  it("모두는 전부를 맞춘다", () => {
    render(<IndicatorChart series={series} range="all" />);
    expect(chart.fitted).toBe(1);
    expect(chart.range).toBeNull();
  });

  it("기간을 바꾸면 다시 만들지 않고 보이는 범위만 바꾼다", () => {
    const { rerender } = render(<IndicatorChart series={series} range="1y" />);
    rerender(<IndicatorChart series={series} range="1m" />);
    expect(chart.created).toBe(1);
    expect(chart.range).toEqual({ from: first("2026-08-26"), to: 999 });
  });

  it("창 안에 점이 없으면 마지막 30점이다", () => {
    const stale = rangeSeriesOf({ points: POINTS, windows: { ...WINDOWS, "1m": "2027-01-01" } });
    render(<IndicatorChart series={stale} range="1m" />);
    expect(chart.range).toEqual({ from: 970, to: 999 });
  });
});

describe("장중", () => {
  const intraday = intradayOf({
    points: [
      { time: "2026-10-08T13:30:00Z", value: "7700.000000", provisional: true },
      { time: "2026-10-08T20:00:00Z", value: "7710.000000", provisional: true },
      { time: "2026-10-09T13:30:00Z", value: "7790.000000", provisional: true },
      { time: "2026-10-09T20:00:00Z", value: "7801.000000", provisional: true },
    ],
    window: { from: "2026-10-09T13:30:00Z", to: "2026-10-09T20:00:00Z" },
  });

  it("확정 선과 같은 진한 실선이다", () => {
    render(<IndicatorChart series={intraday} range="1d" />);
    expect(chart.series).toHaveLength(1);
    expect(chart.series[0].options.color).toBe("#1f2937");
    expect(chart.series[0].options.lineStyle ?? 0).toBe(0);
    expect(screen.getByText(/장중 — 모두 잠정/)).toBeInTheDocument();
  });

  it("처음 범위는 window다 — 왼쪽으로 끌면 앞 세션", () => {
    render(<IndicatorChart series={intraday} range="1d" />);
    expect(chart.series[0].data).toHaveLength(4);
    expect(chart.range).toEqual({ from: 2, to: 3 });
  });

  it("window가 없으면 전부를 맞춘다", () => {
    render(<IndicatorChart series={intradayOf({ window: null })} range="5d" />);
    expect(chart.fitted).toBe(1);
  });
});
