/**
 * 비교 차트 테스트 (T087) — 005 FR-038~040, SC-015, ui-wireframes W6.
 *
 * **수익률(%)로 겹친다.** 통화가 다른 잔고를 같은 축에 놓으면 숫자 크기가 달라
 * 한쪽이 평평해지고, 사용자는 그 종목이 움직이지 않았다고 읽는다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";

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

const item = (
  name: string,
  start: string,
  principalCurrency: "KRW" | "USD",
  points: { date: string; balance: string; returnRate: string }[],
): ComparisonItem => ({
  id: `${name}-${start}`,
  label: name,
  start,
  series: {
    from: start, to: "2024-01-01", principalCurrency, basisCurrency: "KRW",
    downsampled: false, algorithm: "lttb", sourcePointCount: points.length,
    points, gaps: [],
  },
});

const SAMSUNG = item("삼성전자", "2021-08-01", "KRW", [
  { date: "2021-08-02", balance: "86000", returnRate: "0.000000" },
  { date: "2022-08-01", balance: "120000", returnRate: "0.390000" },
]);
const APPLE = item("Apple Inc.", "2022-01-03", "KRW", [
  { date: "2022-01-03", balance: "86000", returnRate: "0.000000" },
  { date: "2022-08-01", balance: "180000", returnRate: "1.090000" },
]);
const APPLE_USD = item("Apple Inc.", "2022-01-03", "USD", APPLE.series.points);

const base = { loading: false, error: null };

beforeEach(() => {
  added.length = 0;
});

describe("비교 차트", () => {
  it("고른 항목들을 한 차트에 겹친다", () => {
    // FR-038
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE]} />);
    expect(added).toHaveLength(2);
  });

  it("잔고가 아니라 수익률을 그린다", () => {
    // FR-039 — 8만과 18만을 겹치면 통화가 다를 때 한쪽이 평평해진다.
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE]} />);
    const values = added.flatMap((a) => a.data.map((d) => d.value));
    expect(values).toContain(39);
    expect(values).toContain(109);
    expect(values).not.toContain(120000);
  });

  it("모두 같은 원금 통화면 그 기준을 밝힌다", () => {
    // SC-015 — 기준이 드러나지 않으면 사용자는 무엇끼리 비교했는지 모른다.
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE]} />);
    expect(screen.getByTestId("comparison-basis").textContent).toContain("KRW");
  });

  it("원금 통화가 달라도 기준이 KRW로 같으면 한 기준으로 말한다", () => {
    // 006 FR-068(반복 2026-10-03 #4, T140) — 수익률은 원금 통화와 관계없이 KRW다. 반복 #3까지는 원금 통화 기준이라
    // "원금 통화가 다릅니다"라고 경고했고 이 테스트가 그것을 고정했다. 지금 그 경고는 거짓이다.
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE_USD]} />);
    const basis = screen.getByTestId("comparison-basis").textContent ?? "";
    expect(basis).toContain("KRW");
    expect(basis).not.toContain("USD");
    expect(basis).not.toMatch(/다릅니다|다른/);
  });

  it("기준 통화가 다르면 그 사실을 드러낸다", () => {
    // FR-039, SC-015 — 기준이 다르면 같은 잣대로 읽으면 안 된다는 사실이 드러나야 한다.
    const other = { ...APPLE, series: { ...APPLE.series, basisCurrency: "USD" as const } };
    render(<ComparisonChart {...base} items={[SAMSUNG, other]} />);
    const basis = screen.getByTestId("comparison-basis").textContent ?? "";
    expect(basis).toContain("KRW");
    expect(basis).toContain("USD");
    expect(basis).toMatch(/다릅니다|다른/);
  });

  it("시작일이 다르면 각 시작 시점을 범례에 적는다", () => {
    // FR-040 — 선이 시작하는 지점으로도 보이지만 범례에도 적는다.
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE]} />);
    const legend = screen.getByTestId("comparison-legend").textContent ?? "";
    expect(legend).toContain("2021-08-01");
    expect(legend).toContain("2022-01-03");
  });

  it("항목마다 다른 색을 쓴다", () => {
    // 같은 색이면 어느 선이 어느 종목인지 범례로도 가릴 수 없다.
    render(<ComparisonChart {...base} items={[SAMSUNG, APPLE]} />);
    const colors = added.map((a) => a.options.color);
    expect(new Set(colors).size).toBe(2);
  });

  it("불러오는 중에는 그 사실을 알린다", () => {
    render(<ComparisonChart {...base} items={[]} loading />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(added).toHaveLength(0);
  });

  it("일부를 못 받았으면 알린다", () => {
    // 조용히 빠지면 사용자는 그 종목이 비교에서 졌다고 읽는다.
    render(
      <ComparisonChart {...base} items={[SAMSUNG]}
        error="Apple Inc.의 시계열을 불러오지 못했습니다." />,
    );
    expect(screen.getByRole("alert").textContent).toContain("Apple Inc.");
  });
});
