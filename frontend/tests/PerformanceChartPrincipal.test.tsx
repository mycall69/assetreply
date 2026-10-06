/**
 * 성과 차트의 누적 납입 원금 선 (011 T006) — FR-015, FR-019, FR-032, research R11-12, ui-wireframes §5.
 *
 * - 적립식·적금 시계열의 점에는 `principal`(그날까지의 원화 총 납입 원금)이 있다. 그때만 잔고 축(`left`)에 **점선** 하나를 더 그린다
 * - 결측 구간(`gaps`)과 잠정 구간(`provisionalFrom`)에서 잔고 선과 같이 끊고 구별한다 — 한쪽만 끊기면 두 선이 다른 구간을 말한다
 * - 범례가 "┄ 누적 납입 원금 (KRW)"을 말한다
 * - **`principal` 키가 없으면 지금과 같은 시리즈·범례다** — 005~010의 차트 테스트가 그대로 통과해야 한다
 *
 * 모의 객체에 `createSeriesMarkers`·`subscribeClick`·`priceScale`이 없다(기존 차트 테스트와 같다).
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

interface Added {
  options: Record<string, unknown>;
  data: { time: string; value?: number }[];
}

const added: Added[] = [];

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry: Added = { options, data: [] };
      added.push(entry);
      return { setData: (data: { time: string; value?: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const pt = (date: string, balance: string, principal: string | undefined): SimulationPoint => ({
  date, balance, returnRate: "0.010000", ...(principal === undefined ? {} : { principal }),
});

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

const RECURRING = series([
  pt("2024-01-15", "500000", "500000"), pt("2024-02-15", "1010000", "1000000"),
  pt("2024-03-15", "1490000", "1500000"), pt("2024-04-15", "2030000", "2000000"),
]);

/** 왼쪽 축의 점선 — 누적 납입 원금 선이다(잔고 선은 실선, 추정 표식은 선이 없다). */
const principalLines = () => added.filter((e) => e.options.priceScaleId === "left" && e.options.lineStyle === 1);

describe("누적 납입 원금 선", () => {
  beforeEach(() => {
    added.length = 0;
  });

  it("점에 principal이 있으면 잔고 축에 점선 하나를 그린다", () => {
    render(<PerformanceChart series={RECURRING} collecting={null} loading={false} />);
    const lines = principalLines();
    expect(lines).toHaveLength(1);
    expect(lines[0].data).toEqual([
      { time: "2024-01-15", value: 500000 }, { time: "2024-02-15", value: 1000000 },
      { time: "2024-03-15", value: 1500000 }, { time: "2024-04-15", value: 2000000 },
    ]);
    expect(lines[0].options).toMatchObject({ priceLineVisible: false, lastValueVisible: false });
  });

  it("미수집 구간에서 잔고 선과 같이 끊긴다", () => {
    const gapped = series(RECURRING.points, {
      gaps: [{ from: "2024-02-16", to: "2024-03-14", reason: "not_collected" }],
    });
    render(<PerformanceChart series={gapped} collecting={null} loading={false} />);
    const balance = added.filter((e) => e.options.priceScaleId === "left" && e.options.lineStyle === undefined
      && e.options.lineVisible !== false);
    expect(principalLines()).toHaveLength(balance.length);
    expect(principalLines().map((e) => e.data.map((d) => d.time))).toEqual(balance.map((e) => e.data.map((d) => d.time)));
  });

  it("잠정 구간은 연한 색으로 이어 그린다", () => {
    render(<PerformanceChart series={series(RECURRING.points, { provisionalFrom: "2024-03-15" })}
      collecting={null} loading={false} />);
    const lines = principalLines();
    expect(lines).toHaveLength(2);
    expect(lines[0].options.color).not.toEqual(lines[1].options.color);
    expect(lines[1].data[0].time).toBe("2024-03-15");
  });

  it("범례가 누적 납입 원금과 기준 통화를 말한다", () => {
    render(<PerformanceChart series={RECURRING} collecting={null} loading={false} />);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("┄ 누적 납입 원금 (KRW)");
  });

  it("principal 키가 없으면 시리즈와 범례가 지금과 같다", () => {
    render(<PerformanceChart series={RECURRING} collecting={null} loading={false} />);
    const withPrincipal = added.length;
    added.length = 0;
    const plain = series(RECURRING.points.map((p) => ({ date: p.date, balance: p.balance, returnRate: p.returnRate })));
    const { unmount } = render(<PerformanceChart series={plain} collecting={null} loading={false} />);
    expect(principalLines()).toHaveLength(0);
    expect(added).toHaveLength(withPrincipal - 1);
    expect(screen.getAllByTestId("chart-legend").at(-1)).not.toHaveTextContent("누적 납입 원금");
    unmount();
  });
});
