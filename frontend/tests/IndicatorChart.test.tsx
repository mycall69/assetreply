/**
 * 지표 추이 그래프 (014 T049) — FR-011~FR-014, contracts D3.
 *
 * 이 파일 안에서 `lightweight-charts`를 모의한다(새 그래프는 `setVisibleLogicalRange`를 쓴다 — 기존 차트 테스트의 모의에는 없다).
 *
 * - 결측 `gaps` 구간마다 선을 나눈다. 휴장(빈 날)은 나누지 않는다 — 결측을 이어 그리면 그 기간에 값이 움직이지 않은 것처럼 보인다
 * - 잠정 점은 연한 색 선에 있다(⏳)
 * - 처음 범위는 단위마다 다르다: 일 마지막 약 250점, 주 260, 월 240, 년 전체
 * - 커서 상자는 날짜·형식 입힌 값·📅 옮김·⏳ 끝나지 않은 구간·⏳ 잠정을 보인다
 */
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import type { IndicatorPoint } from "@/lib/types";
import { seriesOf } from "./support/indicatorSeriesFixtures";

const chart = vi.hoisted(() => ({
  series: [] as { options: Record<string, unknown>; data: { time: string; value: number }[] }[],
  range: null as { from: number; to: number } | null,
  fitted: 0,
  crosshair: null as ((param: { time?: string }) => void) | null,
}));

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_type: string, options: Record<string, unknown>) => {
      const entry = { options, data: [] as { time: string; value: number }[] };
      chart.series.push(entry);
      return { setData: (data: { time: string; value: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: (fn: (param: { time?: string }) => void) => { chart.crosshair = fn; },
    timeScale: () => ({
      fitContent: () => { chart.fitted += 1; },
      setVisibleLogicalRange: (r: { from: number; to: number }) => { chart.range = r; },
    }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.series = [];
  chart.range = null;
  chart.fitted = 0;
  chart.crosshair = null;
});

function daily(n: number): IndicatorPoint[] {
  const out: IndicatorPoint[] = [];
  const day = new Date(Date.UTC(2020, 0, 1));
  for (let i = 0; i < n; i += 1) {
    out.push({ date: day.toISOString().slice(0, 10), value: `${100 + i}.000000` });
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return out;
}

describe("선", () => {
  it("결측 구간에서 선을 나누고 휴장은 잇는다", () => {
    const points = [
      { date: "2026-09-14", value: "1.000000" }, { date: "2026-09-15", value: "2.000000" },
      { date: "2026-09-17", value: "3.000000" }, { date: "2026-09-18", value: "4.000000" },
      { date: "2026-09-21", value: "5.000000" },
    ];
    render(<IndicatorChart series={seriesOf({ points, gaps: [{ from: "2026-09-16", to: "2026-09-16", reason: "missing" }] })} />);
    const solid = chart.series.filter((s) => s.options.color === "#1f2937");
    expect(solid.map((s) => s.data.map((d) => d.time))).toEqual([
      ["2026-09-14", "2026-09-15"], ["2026-09-17", "2026-09-18", "2026-09-21"]]);
  });

  it("잠정 점은 연한 색 선에 있다", () => {
    render(<IndicatorChart series={seriesOf()} />);
    const light = chart.series.filter((s) => s.options.color === "#9ca3af");
    expect(light).toHaveLength(1);
    expect(light[0].data.map((d) => d.time)).toEqual(["2026-10-08", "2026-10-09"]);
    const solid = chart.series.filter((s) => s.options.color === "#1f2937");
    expect(solid.flatMap((s) => s.data.map((d) => d.time))).not.toContain("2026-10-09");
  });
});

describe("처음 범위", () => {
  it.each([["daily", 250], ["weekly", 260], ["monthly", 240]] as const)("%s는 마지막 %i점", (unit, span) => {
    render(<IndicatorChart series={seriesOf({ unit, points: daily(1000), sourcePointCount: 1000 })} />);
    expect(chart.range).toEqual({ from: 1000 - span, to: 999 });
  });

  it("년은 전체", () => {
    render(<IndicatorChart series={seriesOf({ unit: "yearly", points: daily(80), sourcePointCount: 80 })} />);
    expect(chart.range).toBeNull();
    expect(chart.fitted).toBe(1);
  });

  it("점이 범위보다 적으면 전체", () => {
    render(<IndicatorChart series={seriesOf({ unit: "daily", points: daily(100), sourcePointCount: 100 })} />);
    expect(chart.range).toBeNull();
    expect(chart.fitted).toBe(1);
  });
});

describe("커서 상자", () => {
  it("날짜·값·표식", () => {
    const points = [
      { date: "2026-09-30", value: "7702.110000", shifted: true },
      { date: "2026-10-09", value: "7793.420000", ongoing: true, provisional: true },
    ];
    render(<IndicatorChart series={seriesOf({ unit: "monthly", points })} />);
    act(() => chart.crosshair?.({ time: "2026-09-30" }));
    const box = screen.getByTestId("indicator-tooltip");
    expect(box).toHaveTextContent("2026-09-30");
    expect(box).toHaveTextContent("7,702.11");
    expect(box).toHaveTextContent("📅 옮김");
    act(() => chart.crosshair?.({ time: "2026-10-09" }));
    expect(screen.getByTestId("indicator-tooltip")).toHaveTextContent("⏳ 끝나지 않은 구간");
    expect(screen.getByTestId("indicator-tooltip")).toHaveTextContent("⏳ 잠정");
  });

  it("범례", () => {
    render(<IndicatorChart series={seriesOf()} />);
    expect(screen.getByText(/─ 확정/)).toBeInTheDocument();
    expect(screen.getByText(/┄ 잠정/)).toBeInTheDocument();
  });
});
