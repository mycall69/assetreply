/**
 * 성과 차트 테스트 (T080) — 005 FR-033, FR-041, ui-wireframes W3.
 *
 * 캔버스 렌더링은 검증 대상이 아니다. **무엇을 어느 축에 그리는가**를 본다.
 *
 * 잔고와 수익률을 한 축에 놓으면 숫자 크기가 달라 한쪽이 평평해지고, 사용자는 그
 * 값이 움직이지 않았다고 읽는다. 오류는 나지 않는다 — 그래서 테스트로 막는다.
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

const SERIES: SimulationSeriesResponse = {
  from: "2021-08-01",
  to: "2021-11-30",
  principalCurrency: "KRW",
  downsampled: false,
  algorithm: "lttb",
  sourcePointCount: 4,
  points: [
    { date: "2021-08-02", balance: "80000", returnRate: "0.000000" },
    { date: "2021-09-01", balance: "86000", returnRate: "0.068900" },
    { date: "2021-10-01", balance: "92000", returnRate: "0.137800" },
    { date: "2021-11-01", balance: "98000", returnRate: "0.206700" },
  ],
  gaps: [{ from: "2021-08-07", to: "2021-08-08", reason: "no_quote" }],
};

const base = { collecting: null, loading: false };

const axisOf = (entry: Added): unknown => entry.options.priceScaleId;

beforeEach(() => {
  added.length = 0;
});

describe("성과 차트", () => {
  it("잔고와 수익률을 함께 그린다", () => {
    // FR-033 — 둘 중 하나만 그리면 "얼마가 됐나"와 "얼마나 올랐나" 중 하나를 잃는다.
    render(<PerformanceChart {...base} series={SERIES} />);
    expect(added).toHaveLength(2);
  });

  it("두 값을 서로 다른 축에 둔다", () => {
    // 한 축에 놓으면 8만과 0.2가 섞여 수익률 선이 바닥에 붙는다.
    render(<PerformanceChart {...base} series={SERIES} />);
    const axes = added.map(axisOf);
    expect(new Set(axes).size).toBe(2);
    expect(axes.every((a) => typeof a === "string" && a !== "")).toBe(true);
  });

  it("두 선이 같은 날짜를 덮는다", () => {
    // 한쪽만 끝점이 빠지면 사용자는 그 구간에 수익이 없었다고 읽는다.
    render(<PerformanceChart {...base} series={SERIES} />);
    const [first, second] = added.map((a) => a.data.map((d) => d.time));
    expect(first).toEqual(second);
    expect(first).toEqual(SERIES.points.map((p) => p.date));
  });

  it("수익률을 백분율 축으로 그린다", () => {
    // 0.2067을 그대로 두면 눈금이 0~0.2라 읽히지 않는다. 20.67이어야 한다.
    render(<PerformanceChart {...base} series={SERIES} />);
    const values = added.flatMap((a) => a.data.map((d) => d.value));
    expect(values).toContain(20.67);
  });

  it("기준 통화를 범례에 밝힌다", () => {
    // FR-041 — 밝히지 않으면 사용자가 어느 통화를 보고 있는지 모른다.
    render(<PerformanceChart {...base} series={SERIES} />);
    expect(screen.getByTestId("chart-legend").textContent).toContain("KRW");
  });

  it("수집 중이면 차트 대신 그 사실을 알린다", () => {
    // FR-049 — 부분 결과를 완성된 차트처럼 보여주지 않는다.
    render(
      <PerformanceChart
        {...base}
        series={null}
        collecting={{
          status: "collecting", market: "KRX", symbol: "005930.KS", jobId: 1,
          missingFrom: "2021-08-01", missingThrough: "2021-11-30",
          progressUrl: "/api/stocks/progress?jobId=1",
        }}
      />,
    );
    expect(screen.getByRole("status").textContent).toContain("수집");
    expect(added).toHaveLength(0);
  });

  it("다운샘플링 사실을 숨기지 않는다", () => {
    // 사용자가 보는 것이 전수가 아니라는 사실이 드러나야 한다.
    render(
      <PerformanceChart {...base}
        series={{ ...SERIES, downsampled: true, sourcePointCount: 9000 }} />,
    );
    expect(screen.getByTestId("chart-legend").textContent).toContain("9,000");
  });
});
