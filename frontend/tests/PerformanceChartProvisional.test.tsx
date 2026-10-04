/**
 * 성과 차트의 잠정 구간 (T028) — 008 FR-036, SC-005, ui-wireframes D5.
 *
 * 잠정 금리로 계산한 구간은 **연한 색**의 같은 두 선(잔고·수익률)으로 이어 그리고 범례가 "잠정(날짜부터)"을 말한다 — 같은 색으로
 * 그리면 사용자는 잠정 값을 확정 값으로 읽는다(헌법 원칙 V). 경계 점은 양쪽에 넣는다 — 빼면 선이 끊겨 결측처럼 보인다. 축과 축
 * 형식은 확정 구간과 같다(007 FR-043a). `provisionalFrom`이 없으면 005~007과 같은 시리즈다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationSeriesResponse } from "@/lib/types";

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
      return { setData: (data: { time: string; value: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const SERIES: SimulationSeriesResponse = {
  from: "2025-09-15", to: "2026-10-04", principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: 4,
  points: [
    { date: "2025-09-15", balance: "10000000", returnRate: "0.000000" },
    { date: "2026-09-01", balance: "10200000", returnRate: "0.020000" },
    { date: "2026-09-15", balance: "10214884", returnRate: "0.021488" },
    { date: "2026-10-04", balance: "10230000", returnRate: "0.023000" },
  ],
  gaps: [],
  provisionalFrom: "2026-09-15",
};

const times = (e: Added) => e.data.map((d) => d.time);

beforeEach(() => {
  added.length = 0;
});

describe("잠정 구간", () => {
  it("확정 두 선과 잠정 두 선 — 경계 점을 양쪽에 넣는다", () => {
    render(<PerformanceChart series={SERIES} collecting={null} loading={false} />);
    expect(added).toHaveLength(4);
    const [balance, profit, balanceLater, profitLater] = added;
    expect(times(balance)).toEqual(["2025-09-15", "2026-09-01", "2026-09-15"]);
    expect(times(profit)).toEqual(["2025-09-15", "2026-09-01", "2026-09-15"]);
    expect(times(balanceLater)).toEqual(["2026-09-15", "2026-10-04"]);
    expect(times(profitLater)).toEqual(["2026-09-15", "2026-10-04"]);
  });

  it("잠정 선은 같은 축·같은 축 형식에 연한 색이다", () => {
    render(<PerformanceChart series={SERIES} collecting={null} loading={false} />);
    const [balance, profit, balanceLater, profitLater] = added;
    expect(balanceLater.options.priceScaleId).toBe(balance.options.priceScaleId);
    expect(profitLater.options.priceScaleId).toBe(profit.options.priceScaleId);
    expect(balanceLater.options.priceFormat).toEqual(balance.options.priceFormat);
    expect(profitLater.options.priceFormat).toEqual(profit.options.priceFormat);
    expect(balanceLater.options.color).not.toBe(balance.options.color);
    expect(profitLater.options.color).not.toBe(profit.options.color);
  });

  it("범례가 잠정 시작일을 말한다", () => {
    render(<PerformanceChart series={SERIES} collecting={null} loading={false} />);
    expect(screen.getByTestId("chart-legend").textContent).toContain("잠정(2026-09-15부터)");
  });

  it("처음부터 잠정이면 잠정 두 선만이다", () => {
    render(<PerformanceChart series={{ ...SERIES, provisionalFrom: "2025-09-15" }} collecting={null}
      loading={false} />);
    expect(added).toHaveLength(2);
    expect(times(added[0])).toEqual(["2025-09-15", "2026-09-01", "2026-09-15", "2026-10-04"]);
  });

  it.each([null, undefined])("잠정이 없으면(%s) 지금과 같은 두 선이고 범례에 잠정이 없다", (value) => {
    const series = { ...SERIES, provisionalFrom: value } as SimulationSeriesResponse;
    render(<PerformanceChart series={series} collecting={null} loading={false} />);
    expect(added).toHaveLength(2);
    expect(times(added[0])).toHaveLength(4);
    expect(screen.getByTestId("chart-legend").textContent).not.toContain("잠정");
  });
});
