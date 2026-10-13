/**
 * 대상이 많은 수익률 추이 (014 반복 2026-10-13 T214) — spec FR-046, SC-028, research R14-37, ui-wireframes D19.
 *
 * - 선은 **색 10 × 선 모양 2 = 짝 20**이다 — 첫 10개는 지금 그대로(색 10·실선/점선 번갈음), 11~20번째는 같은 색에 선 모양을 뒤집는다. 짝이
 *   10개뿐이면 1번째와 11번째가 색·모양까지 같아 범례로도 가를 수 없다(실패 양상 *조용히 틀림*)
 * - 대상 11개 이상의 커서 상자는 **커서 세로 자리에 가장 가까운 10개**를 그 날 수익률 높은 차례로 보이고 끝 줄 "외 N개 — 비교 표에 모두
 *   있습니다"다 — 100줄이면 그래프를 덮는다. 대상 10개 이하는 지금 그대로다(대상 전부·대상 차례)
 * - 가까운 대상 찾기(`priceToCoordinate`)는 **커서 움직임에서만** 부른다 — 그릴 때 부르면 기존 차트 모의가 깨진다(CLAUDE.md 010). 모의는 이 파일
 *   인라인이고, 좌표는 값 그대로(세로 자리 = 그리는 값)다
 */
import { act, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompareReturnChart, type CompareChartItem } from "@/components/compare/CompareReturnChart";
import { series } from "./support/compareFixtures";

const chart = vi.hoisted(() => ({
  series: [] as { options: Record<string, unknown>; data: { time: string; value?: number }[] }[],
  move: null as null | ((param: unknown) => void),
  coordinateCalls: 0,
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry = { options, data: [] as { time: string; value?: number }[] };
      chart.series.push(entry);
      return {
        setData: (data: { time: string; value?: number }[]) => { entry.data = data; },
        priceToCoordinate: (price: number) => {
          chart.coordinateCalls += 1;
          return price;
        },
      };
    },
    subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.series.length = 0;
  chart.move = null;
  chart.coordinateCalls = 0;
});

/** 대상 `i`의 2023-01-02 수익률은 `i`(그리는 값 i × 100), 끝은 기준일 하나 — 대상마다 수익률 선이 하나다. */
const item = (i: number, over: Partial<CompareChartItem> = {}): CompareChartItem => ({
  key: `k${i}`, name: `대상${i}`,
  series: series([["2020-01-02", "0"], ["2023-01-02", String(i)], ["2026-10-01", "1"]]),
  lineEnd: { date: "2026-10-01", holdingReturnRate: "1", afterSaleReturnRate: null },
  ...over,
});
const many = (count: number) => Array.from({ length: count }, (_, i) => item(i));
const lines = () => chart.series.filter((s) => s.options.lineVisible !== false);
const hoverAt = (y: number) => act(() => chart.move?.({
  time: "2023-01-02", point: { x: 10, y }, sourceEvent: { clientX: 200, clientY: 120 } }));
const hoverRows = () => within(screen.getByTestId("compare-hover")).getAllByRole("listitem").map((li) => li.textContent);

describe("선 모양 짝 20", () => {
  it("대상 20개는 색·선 모양 짝이 모두 다르고 첫 10개는 지금 그대로다", () => {
    render(<CompareReturnChart items={many(20)} />);
    const drawn = lines();
    expect(drawn).toHaveLength(20);
    const pairs = drawn.map((s) => `${String(s.options.color)}|${String(s.options.lineStyle)}`);
    expect(new Set(pairs).size).toBe(20);
    expect(drawn.slice(0, 10).map((s) => s.options.lineStyle)).toEqual([0, 2, 0, 2, 0, 2, 0, 2, 0, 2]);
    expect(drawn.slice(10, 20).map((s) => s.options.lineStyle)).toEqual([2, 0, 2, 0, 2, 0, 2, 0, 2, 0]);
    // 11번째는 1번째와 같은 색에 모양만 다르다
    expect(drawn[10].options.color).toBe(drawn[0].options.color);
  });

  it("21번째부터 짝이 되풀이된다 — 범례에 이름과 선 모양이 있다", () => {
    render(<CompareReturnChart items={many(21)} />);
    const drawn = lines();
    expect(drawn[20].options.color).toBe(drawn[0].options.color);
    expect(drawn[20].options.lineStyle).toBe(drawn[0].options.lineStyle);
    const legend = screen.getByTestId("compare-legend");
    expect(legend.textContent).toContain("━ 대상0");
    expect(legend.textContent).toContain("┅ 대상10");
    expect(legend.textContent).toContain("━ 대상11");
    expect(legend.textContent).toContain("━ 대상20");
  });

  it("그릴 때 가까운 대상 찾기를 부르지 않는다", () => {
    render(<CompareReturnChart items={many(30)} />);
    expect(chart.coordinateCalls).toBe(0);
  });
});

describe("커서 상자", () => {
  it("대상 30개면 커서에 가까운 10개를 수익률 높은 차례로, 끝 줄에 나머지 수다", () => {
    render(<CompareReturnChart items={many(30)} />);
    // 세로 자리 1550 — 가까운 열은 대상 11~20(값 1100~2000)이다
    hoverAt(1550);
    const rows = hoverRows();
    expect(rows).toHaveLength(11);
    expect(rows.slice(0, 10)).toEqual(Array.from({ length: 10 }, (_, n) => {
      const i = 20 - n;
      return `대상${i} +${(i * 100).toLocaleString("en-US")}.00%`;
    }));
    expect(rows[10]).toBe("외 20개 — 비교 표에 모두 있습니다");
  });

  it("커서를 옮기면 그 자리에 가까운 대상으로 바뀐다", () => {
    render(<CompareReturnChart items={many(30)} />);
    hoverAt(0);
    expect(hoverRows().slice(0, 10)).toEqual(Array.from({ length: 10 }, (_, n) => {
      const i = 9 - n;
      return `대상${i} +${(i * 100).toLocaleString("en-US")}.00%`;
    }));
  });

  it("그 날 값이 없는 대상은 고르지 않고 나머지 수에 든다", () => {
    const items = [...many(10), item(10, { series: series([["2024-01-02", "0"], ["2026-10-01", "1"]]) }),
      item(11, { series: series([["2024-01-02", "0"], ["2026-10-01", "1"]]) })];
    render(<CompareReturnChart items={items} />);
    hoverAt(5000);
    const rows = hoverRows();
    expect(rows).toHaveLength(11);
    expect(rows.some((r) => r?.startsWith("대상10 ") || r?.startsWith("대상11 "))).toBe(false);
    expect(rows[10]).toBe("외 2개 — 비교 표에 모두 있습니다");
  });

  it("대상 10개는 지금 그대로다 — 대상 전부를 대상 차례로", () => {
    render(<CompareReturnChart items={many(10)} />);
    hoverAt(1550);
    const rows = hoverRows();
    expect(rows).toHaveLength(10);
    expect(rows[0]).toBe("대상0 +0.00%");
    expect(rows[9]).toBe("대상9 +900.00%");
    expect(chart.coordinateCalls).toBe(0);
  });
});
