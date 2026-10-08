/**
 * 비교의 수익률 추이 (013 T052) — FR-015, SC-005, research R13-5, ui-wireframes F6.
 *
 * 선은 메뉴 시계열의 보유 중(매도 전) 수익률이다. 결측 구간에서 끊고 잠정 구간은 연한 색이다. 시계열 마지막 날이 기준일보다 앞이면
 * 기준일까지 보유 중 값으로 잇고, 매도 후 값이 있으면 기준일에 **점만 그리는 시리즈**를 하나 더한다(명확화 5). 색만으로 가르지 않는다
 * — 선 모양이 번갈고 범례·커서 상자에 이름이 있다.
 *
 * 모의는 기존 차트 테스트와 같은 API만 둔다(`createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·
 * `remove`) — 새 차트가 그 밖의 API를 실행 중에 쓰면 이 테스트가 깨진다(CLAUDE.md 010).
 */
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompareReturnChart, type CompareChartItem } from "@/components/compare/CompareReturnChart";
import { series } from "./support/compareFixtures";

const chart = vi.hoisted(() => ({
  series: [] as { options: Record<string, unknown>; data: { time: string; value?: number }[] }[],
  move: null as null | ((param: unknown) => void),
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry = { options, data: [] as { time: string; value?: number }[] };
      chart.series.push(entry);
      return { setData: (data: { time: string; value?: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.series.length = 0;
  chart.move = null;
});

const item = (key: string, name: string, over: Partial<CompareChartItem> = {}): CompareChartItem => ({
  key, name,
  series: series([["2020-01-02", "0"], ["2023-01-02", "1.5"], ["2026-10-01", "25.5"]]),
  lineEnd: { date: "2026-10-06", holdingReturnRate: "25.964860", afterSaleReturnRate: "20.455734" },
  ...over,
});

const lines = () => chart.series.filter((s) => s.options.lineVisible !== false);
const points = () => chart.series.filter((s) => s.options.lineVisible === false);

describe("선", () => {
  it("대상마다 보유 중 수익률(백분율) 선이다", () => {
    render(<CompareReturnChart items={[item("a", "XLK"), item("b", "삼성전자")]} />);
    const first = lines()[0];
    expect(first.data.map((d) => d.time)).toEqual(["2020-01-02", "2023-01-02", "2026-10-01"]);
    expect(first.data[2].value).toBeCloseTo(2550);
  });

  it("결측 구간에서 끊는다 — 휴장은 잇는다", () => {
    const broken = series([["2020-01-02", "0"], ["2020-03-02", "0.1"], ["2020-06-01", "0.2"]],
      { gaps: [{ from: "2020-02-01", to: "2020-02-28", reason: "not_collected" }] });
    render(<CompareReturnChart items={[item("a", "XLK", { series: broken,
      lineEnd: { date: "2020-06-01", holdingReturnRate: "0.2", afterSaleReturnRate: null } })]} />);
    expect(lines().map((s) => s.data.map((d) => d.time))).toEqual([["2020-01-02"], ["2020-03-02", "2020-06-01"]]);
  });

  it("잠정 구간은 연한 색의 따로 된 시리즈다", () => {
    const provisional = series([["2026-06-01", "0.1"], ["2026-08-01", "0.2"], ["2026-09-01", "0.3"]],
      { provisionalFrom: "2026-08-01" });
    render(<CompareReturnChart items={[item("a", "시중은행", { series: provisional,
      lineEnd: { date: "2026-09-01", holdingReturnRate: "0.3", afterSaleReturnRate: null } })]} />);
    const [confirmed, light] = lines();
    expect(confirmed.data.map((d) => d.time)).toEqual(["2026-06-01", "2026-08-01"]);
    expect(light.data.map((d) => d.time)).toEqual(["2026-08-01", "2026-09-01"]);
    expect(light.options.color).not.toBe(confirmed.options.color);
  });
});

describe("기준일의 끝", () => {
  it("시계열 마지막 날이 기준일보다 앞이면 보유 중 값으로 기준일까지 잇는다", () => {
    render(<CompareReturnChart items={[item("a", "XLK")]} />);
    const connector = lines().find((s) => s.data.length === 2 && s.data[1].time === "2026-10-06");
    expect(connector?.data[0].time).toBe("2026-10-01");
    expect(connector?.data[1].value).toBeCloseTo(2596.486);
  });

  it("마지막 날이 기준일이면 잇지 않는다", () => {
    render(<CompareReturnChart items={[item("a", "BTC", {
      lineEnd: { date: "2026-10-01", holdingReturnRate: "25.5", afterSaleReturnRate: null } })]} />);
    expect(lines()).toHaveLength(1);
  });

  it("매도 후 값이 있으면 기준일에 점만 그리는 시리즈다", () => {
    render(<CompareReturnChart items={[item("a", "XLK")]} />);
    const [point] = points();
    expect(point.options.pointMarkersVisible).toBe(true);
    expect(point.data).toHaveLength(1);
    expect(point.data[0].time).toBe("2026-10-06");
    expect(point.data[0].value).toBeCloseTo(2045.5734);
  });

  it("매도 후 값이 없으면 점이 없다 — 선 끝 값으로 메우지 않는다", () => {
    render(<CompareReturnChart items={[item("a", "시중은행", {
      lineEnd: { date: "2026-10-06", holdingReturnRate: "25.964860", afterSaleReturnRate: null } })]} />);
    expect(points()).toEqual([]);
  });
});

describe("구별", () => {
  it("대상 10개는 색 10개가 모두 다르고 선 모양이 번갈아다", () => {
    const items = Array.from({ length: 10 }, (_, i) => item(`k${i}`, `대상${i}`, {
      lineEnd: { date: "2026-10-01", holdingReturnRate: "25.5", afterSaleReturnRate: null } }));
    render(<CompareReturnChart items={items} />);
    const firstLines = lines();
    expect(new Set(firstLines.map((s) => s.options.color)).size).toBe(10);
    expect(firstLines.map((s) => s.options.lineStyle)).toEqual([0, 2, 0, 2, 0, 2, 0, 2, 0, 2]);
  });

  it("범례에 이름, 설명에 선·점의 뜻이 있다", () => {
    render(<CompareReturnChart items={[item("a", "XLK"), item("b", "삼성전자")]} />);
    expect(screen.getByTestId("compare-legend").textContent).toMatch(/XLK.*삼성전자/);
    expect(screen.getByTestId("compare-basis")).toHaveTextContent("선: 보유 중(매도 전) · 끝 점: 매도 후");
  });
});

describe("커서 상자", () => {
  it("그날 대상마다 값을, 없는 대상은 값 없음을 보인다", () => {
    const short = series([["2020-01-02", "0"], ["2023-01-02", "1.5"]]);
    render(<CompareReturnChart items={[item("a", "XLK"), item("b", "삼성전자", { series: short,
      lineEnd: { date: "2023-01-02", holdingReturnRate: "1.5", afterSaleReturnRate: null } })]} />);
    act(() => chart.move?.({ time: "2026-10-01", point: { x: 10, y: 10 }, sourceEvent: { clientX: 200, clientY: 120 } }));
    const box = screen.getByTestId("compare-hover");
    expect(box).toHaveTextContent("2026-10-01");
    expect(box).toHaveTextContent("XLK +2550.00%");
    expect(box).toHaveTextContent("삼성전자 값 없음");
  });

  it("기준일에는 보유 중·매도 후 두 값이다", () => {
    render(<CompareReturnChart items={[item("a", "XLK")]} />);
    act(() => chart.move?.({ time: "2026-10-06", point: { x: 10, y: 10 }, sourceEvent: { clientX: 200, clientY: 120 } }));
    expect(screen.getByTestId("compare-hover")).toHaveTextContent("XLK 보유 중 +2596.48% · 매도 후 +2045.57%");
  });

  it("차트를 벗어나면 사라진다", () => {
    render(<CompareReturnChart items={[item("a", "XLK")]} />);
    act(() => chart.move?.({ time: "2026-10-01", point: { x: 10, y: 10 }, sourceEvent: { clientX: 200, clientY: 120 } }));
    act(() => chart.move?.({ time: undefined, point: undefined }));
    expect(screen.queryByTestId("compare-hover")).toBeNull();
  });
});
