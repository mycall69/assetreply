/**
 * 이력 비교 차트의 수익률 축 (T054) — 007 FR-046a, SC-016, research R7-14, ui-wireframes C5. 반복 2026-10-04 #2.
 *
 * 수익률 축 눈금에 **천 단위 쉼표**를 넣는다(`1,881.47`). 성과 추이 차트의 수익률 축(FR-043a)과 **같은 형식 함수**
 * (`axisPriceFormat`)를 쓴다 — 두 벌이면 한쪽만 고쳐져 같은 화면의 두 수익률 축이 다른 형식으로 보인다.
 *
 * 비교 차트는 이력 항목마다, 결측으로 끊긴 구간마다 시리즈를 따로 만든다. 일부 시리즈에만 형식을 주면 축이 다른
 * 시리즈를 따를 때 쉼표가 빠진다 — 오류는 나지 않는다. 그래서 모든 시리즈를 본다.
 */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import type { ComparisonItem } from "@/components/stock/ComparisonChart";
import { axisPriceFormat } from "@/lib/chartSeries";
import type { SeriesGap } from "@/lib/types";

interface PriceFormat {
  type?: string;
  minMove?: number;
  formatter?: (price: number) => string;
}

const added: Record<string, unknown>[] = [];

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      added.push(options);
      return { setData: () => undefined };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const item = (
  label: string,
  points: { date: string; balance: string; returnRate: string }[],
  gaps: SeriesGap[],
): ComparisonItem => ({
  id: label,
  label,
  start: points[0].date,
  series: {
    from: points[0].date, to: points[points.length - 1].date, principalCurrency: "USD",
    basisCurrency: "KRW", downsampled: false, algorithm: "lttb", sourcePointCount: points.length,
    points, gaps,
  },
});

/** 결측 없음 — 시리즈 1개. */
const BTC = item("비트코인", [
  { date: "2021-02-27", balance: "80000", returnRate: "0.000000" },
  { date: "2021-03-06", balance: "92000", returnRate: "18.814700" },
], []);

/** 출처 결측 한 구간으로 두 구간 — 시리즈 2개. */
const SOL = item("솔라나", [
  { date: "2021-02-27", balance: "80000", returnRate: "0.000000" },
  { date: "2021-03-03", balance: "86000", returnRate: "0.068900" },
  { date: "2021-03-06", balance: "92000", returnRate: "32.000000" },
], [{ from: "2021-03-04", to: "2021-03-05", reason: "source_missing" }]);

const formatOf = (options: Record<string, unknown>) => (options.priceFormat ?? {}) as PriceFormat;

beforeEach(() => {
  added.length = 0;
});

describe("axisPriceFormat — 두 차트의 공용 축 형식", () => {
  it("수익률(2자리)", () => {
    const format = axisPriceFormat(2);
    expect(format.type).toBe("custom");
    expect(format.minMove).toBe(0.01);
    expect(format.formatter(1881.47)).toBe("1,881.47");
    expect(format.formatter(3200)).toBe("3,200.00");
    expect(format.formatter(-400)).toBe("-400.00");
  });

  it("원화 잔고(0자리)", () => {
    const format = axisPriceFormat(0);
    expect(format.minMove).toBe(1);
    expect(format.formatter(360000000)).toBe("360,000,000");
  });
});

describe("이력 비교 차트의 수익률 축 (FR-046a)", () => {
  it("모든 항목·구간의 시리즈에 수익률 형식이 있다", () => {
    render(<ComparisonChart items={[BTC, SOL]} loading={false} error={null} />);
    expect(added).toHaveLength(3);
    for (const options of added) {
      const format = formatOf(options);
      expect(format.type).toBe("custom");
      expect(format.minMove).toBe(0.01);
      expect(format.formatter?.(1881.47)).toBe("1,881.47");
      expect(format.formatter?.(-400)).toBe("-400.00");
    }
  });
});
