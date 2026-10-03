/**
 * 성과 차트의 결측 렌더링 (T081) — 005 FR-034, 001 FR-032.
 *
 * 001이 2026-09-27 반복에서 정한 규칙을 그대로 잇는다.
 *
 * | `reason` | 뜻 | 선 |
 * |----------|-----|-----|
 * | `no_quote` | 휴장일·주말 — 그날은 시장이 열리지 않아 **값이 존재하지 않는다** | 잇는다 |
 * | `not_collected` | 아직 받지 않음 — 값이 존재할 수 있는데 없다 | 끊는다 |
 *
 * 미수집을 이으면 **구멍 위에 온전한 선**이 그려져 사용자가 데이터를 다 가졌다고
 * 믿는다. 반대로 휴장일마다 끊으면 3년 보기에서 수십 구간으로 쪼개져 추세가 안 보인다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SeriesGap, SimulationSeriesResponse } from "@/lib/types";

interface Added {
  options: Record<string, unknown>;
  data: { time: string; value: number }[];
}

const added: Added[] = [];

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry: Added = { options, data: [] };
      added.push(entry);
      return {
        setData: (data: { time: string; value: number }[]) => {
          entry.data = data;
        },
      };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const POINTS = [
  { date: "2021-08-02", balance: "80000", returnRate: "0.000000" },
  { date: "2021-09-01", balance: "86000", returnRate: "0.068900" },
  { date: "2022-06-01", balance: "92000", returnRate: "0.137800" },
  { date: "2022-07-01", balance: "98000", returnRate: "0.206700" },
];

const withGaps = (gaps: SeriesGap[]): SimulationSeriesResponse => ({
  from: "2021-08-01", to: "2022-07-31", principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: POINTS.length,
  points: POINTS, gaps,
});

const HOLIDAY: SeriesGap[] = [
  { from: "2021-09-02", to: "2022-05-31", reason: "no_quote" },
];
const UNCOLLECTED: SeriesGap[] = [
  { from: "2021-09-02", to: "2022-05-31", reason: "not_collected" },
];

const base = { collecting: null, loading: false };

/** 한 축의 시리즈 수 = 그 선이 몇 조각으로 끊겼는가. */
const segmentsOn = (axis: unknown): number =>
  added.filter((a) => a.options.priceScaleId === axis).length;

beforeEach(() => {
  added.length = 0;
});

describe("성과 차트의 결측 구간", () => {
  it("휴장일에서는 선을 잇는다", () => {
    render(<PerformanceChart {...base} series={withGaps(HOLIDAY)} />);
    const axes = [...new Set(added.map((a) => a.options.priceScaleId))];
    expect(axes).toHaveLength(2);
    for (const axis of axes) expect(segmentsOn(axis)).toBe(1);
  });

  it("미수집 구간에서는 선을 끊는다", () => {
    render(<PerformanceChart {...base} series={withGaps(UNCOLLECTED)} />);
    const axes = [...new Set(added.map((a) => a.options.priceScaleId))];
    expect(axes).toHaveLength(2);
    // 잔고와 수익률이 **같이** 끊겨야 한다. 한쪽만 끊기면 두 선이 다른 구간을
    // 말하게 되고, 사용자는 어느 쪽이 맞는지 알 수 없다.
    for (const axis of axes) expect(segmentsOn(axis)).toBe(2);
  });

  it("미수집 구간을 범례에 밝힌다", () => {
    render(<PerformanceChart {...base} series={withGaps(UNCOLLECTED)} />);
    expect(screen.getByTestId("chart-legend").textContent).toContain("미수집");
  });

  it("휴장일을 결측이라 말하지 않는다", () => {
    // 이어진 선을 두고 "없다"고 말하면 화면과 범례가 어긋난다 (001 T124와 같은 이유).
    render(<PerformanceChart {...base} series={withGaps(HOLIDAY)} />);
    expect(screen.getByTestId("chart-legend").textContent).not.toContain("미수집");
  });

  it("끊긴 뒤에도 모든 점이 남는다", () => {
    // 나누는 것은 선이지 데이터가 아니다. 점이 사라지면 구간이 통째로 없어진다.
    render(<PerformanceChart {...base} series={withGaps(UNCOLLECTED)} />);
    const balanceAxis = added[0].options.priceScaleId;
    const times = added
      .filter((a) => a.options.priceScaleId === balanceAxis)
      .flatMap((a) => a.data.map((d) => d.time));
    expect(times).toEqual(POINTS.map((p) => p.date));
  });
});
