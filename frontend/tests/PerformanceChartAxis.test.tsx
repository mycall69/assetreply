/**
 * 성과 추이 차트의 축 눈금 (T051) — 007 FR-043a, SC-015, research R7-14, ui-wireframes C5. 반복 2026-10-04.
 *
 * 두 축 눈금에 **천 단위 쉼표**를 넣는다 — 잔고(왼쪽, KRW)는 소수점 없이 `360,000,000`, 수익률(오른쪽, %)은 소수 2자리
 * `3,200.00`. 쉼표 없는 9자리 눈금은 자릿수를 세어야 읽혀 3,600만과 3억 6천만을 헷갈린다.
 *
 * 축 형식은 시리즈 옵션이고 이 차트는 결측으로 끊긴 **구간마다 시리즈를 새로 만든다**. 첫 구간에만 형식을 주면 축이 다른
 * 시리즈를 따를 때 쉼표가 빠진다 — 오류는 나지 않는다. 그래서 모든 시리즈를 본다.
 *
 * 캔버스는 그리지 않는다 — 시리즈에 넘긴 형식을 본다(`PerformanceChart.test.tsx`와 같은 모의).
 */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { formatAxisNumber } from "@/lib/format";
import type { SimulationSeriesResponse } from "@/lib/types";

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

/** 결측 두 구간으로 세 구간이 된다 — 구간마다 잔고·수익률 두 시리즈, 모두 6개. */
const SERIES: SimulationSeriesResponse = {
  from: "2021-02-27", to: "2021-03-06", principalCurrency: "USD", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: 3,
  points: [
    { date: "2021-02-27", balance: "80000", returnRate: "0.000000" },
    { date: "2021-03-03", balance: "86000", returnRate: "0.068900" },
    { date: "2021-03-06", balance: "92000", returnRate: "0.137800" },
  ],
  gaps: [
    { from: "2021-02-28", to: "2021-03-02", reason: "source_missing" },
    { from: "2021-03-04", to: "2021-03-05", reason: "source_missing" },
  ],
};

const formatOf = (options: Record<string, unknown>) => (options.priceFormat ?? {}) as PriceFormat;
const balanceSeries = () => added.filter((o) => o.priceScaleId === "left");
const returnSeries = () => added.filter((o) => o.priceScaleId === "right");

beforeEach(() => {
  added.length = 0;
});

describe("formatAxisNumber — 축 눈금 전용", () => {
  it.each([
    [360000000, 0, "360,000,000"],
    [120000000, 0, "120,000,000"],
    [0, 0, "0"],
    [1234.6, 0, "1,235"],
    [3200, 2, "3,200.00"],
    [999, 2, "999.00"],
    [-400, 2, "-400.00"],
    [1234567.891, 2, "1,234,567.89"],
    [-1234567, 0, "-1,234,567"],
  ])("%s (%s자리) → %s", (value, digits, shown) => {
    expect(formatAxisNumber(value, digits)).toBe(shown);
  });

  it("0에 아주 가까운 음수는 -0.00이 아니라 0.00이다", () => {
    // 눈금 값은 부동소수 계산이라 0 눈금이 -1e-12로 올 수 있다. 부호가 남으면 손실 눈금처럼 읽힌다.
    expect(formatAxisNumber(-0.001, 2)).toBe("0.00");
    expect(formatAxisNumber(-1e-12, 0)).toBe("0");
  });
});

describe("성과 추이 차트의 축 형식 (FR-043a)", () => {
  it("결측으로 끊긴 모든 구간의 두 시리즈에 형식이 있다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={SERIES} />);
    expect(added).toHaveLength(6);
    for (const options of added) {
      expect(formatOf(options).type).toBe("custom");
      expect(typeof formatOf(options).formatter).toBe("function");
    }
  });

  it("잔고 축(KRW)은 소수점 없이 쉼표를 넣는다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={SERIES} />);
    expect(balanceSeries()).toHaveLength(3);
    for (const options of balanceSeries()) {
      const format = formatOf(options);
      expect(format.minMove).toBe(1);
      expect(format.formatter?.(360000000)).toBe("360,000,000");
      expect(format.formatter?.(80000)).toBe("80,000");
    }
  });

  it("수익률 축은 소수 2자리로 쉼표를 넣는다", () => {
    render(<PerformanceChart collecting={null} loading={false} series={SERIES} />);
    expect(returnSeries()).toHaveLength(3);
    for (const options of returnSeries()) {
      const format = formatOf(options);
      expect(format.minMove).toBe(0.01);
      expect(format.formatter?.(3200)).toBe("3,200.00");
      expect(format.formatter?.(-400)).toBe("-400.00");
    }
  });

  it("잔고 축의 자릿수는 기준 통화를 따른다 — KRW·JPY 0자리, 그 밖 2자리", () => {
    // 006 FR-068 이후 기준은 늘 KRW지만, 기준 통화가 바뀌면 원화 규칙을 남의 통화에 쓰게 된다.
    render(<PerformanceChart collecting={null} loading={false}
      series={{ ...SERIES, basisCurrency: "USD" }} />);
    for (const options of balanceSeries()) {
      expect(formatOf(options).formatter?.(1234.5)).toBe("1,234.50");
    }
  });
});
