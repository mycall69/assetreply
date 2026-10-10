/**
 * 투자 비교 수익률 추이의 블랙 배경 색 (014 T154 실측 결함 — 반복 2026-10-10c FR-030, SC-015).
 *
 * T154 실측 — 블랙 배경에서 범례 글자(선 색)의 대비가 3.72(파랑)·3.98(빨강)였다. 선 팔레트가 밝은 바탕용(600 계열)이라 어두운 바탕의 글자로
 * 읽히지 않는다. 10c 실측(T137)은 비교를 실행하지 않아 범례가 없었다.
 *
 * - 블랙이면 범례·커서 상자 글자와 선이 같은 색이고, 그 색의 대비가 차트 바탕(`DARK_CHART.background`)에서 4.5:1 이상이다
 * - 밝으면 이 반복 전 팔레트 그대로다(FR-026)
 *
 * 이 파일 안에서 `lightweight-charts`를 모의한다(기존 차트 테스트와 같은 API만).
 */
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompareReturnChart } from "@/components/compare/CompareReturnChart";
import { DARK_CHART } from "@/lib/chartTheme";
import { useThemeStore } from "@/stores/themeStore";
import { series } from "./support/compareFixtures";

const chart = vi.hoisted(() => ({ series: [] as Record<string, unknown>[] }));

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_type: string, options: Record<string, unknown>) => {
      chart.series.push(options);
      return { setData: () => undefined };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

/** 이 반복 전(013)의 밝은 바탕 팔레트 — 밝은 테마는 이대로여야 한다. */
const LIGHT = [
  "rgb(37, 99, 235)", "rgb(220, 38, 38)", "rgb(22, 163, 74)", "rgb(217, 119, 6)", "rgb(147, 51, 234)",
  "rgb(8, 145, 178)", "rgb(219, 39, 119)", "rgb(101, 163, 13)", "rgb(79, 70, 229)", "rgb(120, 113, 108)",
];

const ITEMS = LIGHT.map((_, i) => ({
  key: `t${i}`, name: `대상${i}(T${i})`,
  series: series([["2020-01-02", "0"], ["2021-01-04", String(i)]]),
  lineEnd: { date: "2021-01-04", holdingReturnRate: String(i), afterSaleReturnRate: null },
}));

function channels(color: string): number[] {
  const m = color.match(/^rgba?\((\d+), (\d+), (\d+)/);
  if (m === null) throw new Error(`색이 아니다: ${color}`);
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function hex(color: string): number[] {
  return [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
}

function luminance([r, g, b]: number[]): number {
  const f = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(a: number[], b: number[]): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const legendColors = () =>
  [...screen.getByTestId("compare-legend").querySelectorAll("span")].map((s) => s.style.color);

beforeEach(() => {
  chart.series.length = 0;
});

afterEach(() => {
  useThemeStore.setState({ theme: "light" });
});

describe("블랙 배경", () => {
  it("범례 글자의 대비가 차트 바탕에서 4.5:1 이상이다", () => {
    useThemeStore.setState({ theme: "dark" });
    render(<CompareReturnChart items={ITEMS} />);
    const ratios = legendColors().map((c) => contrast(channels(c), hex(DARK_CHART.background)));
    expect(ratios).toHaveLength(LIGHT.length);
    for (const ratio of ratios) expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("선과 범례가 같은 색이다", () => {
    useThemeStore.setState({ theme: "dark" });
    render(<CompareReturnChart items={ITEMS} />);
    const lines = new Set(chart.series.map((o) => String(o.color)).filter((c) => c.startsWith("rgb(")));
    expect(lines).toEqual(new Set(legendColors()));
  });
});

describe("밝은 배경", () => {
  it("이 반복 전 팔레트 그대로다", () => {
    render(<CompareReturnChart items={ITEMS} />);
    expect(legendColors()).toEqual(LIGHT);
  });
});
