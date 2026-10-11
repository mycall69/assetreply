/**
 * 확대 구간의 일 단위 자료 — 그래프 (014 반복 2026-10-11c T193) — spec FR-038, SC-023, contracts D17, data-model 16, research R14-31.
 *
 * 두 지점으로 확대가 끝나면 그래프가 받기 함수(`loadDetail`)를 그 범위로 부르고, 받은 점을 그 구간에 끼워 **다시 그린 뒤에도 확대 범위를 지킨다**
 * (`setVisibleRange` 다시). 받는 동안·실패면 상태 줄, 늦게 온 응답(리셋 뒤)은 버리고, 받은 구간 안의 재확대는 다시 받지 않는다. [리셋]이면 원래 점과
 * 처음 범위, 테마·바탕 자료가 바뀌면 받은 자료를 쓰지 않는다. 받기 함수가 없으면 지금처럼 확대만 한다.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { detailSeriesPath, ChartSection } from "@/components/compare/detail/ChartSection";
import { CompareReturnChart, type CompareChartItem, type CompareDetailMap } from "@/components/compare/CompareReturnChart";
import { TrendChart } from "@/components/fx/TrendChart";
import { ComparisonChart, type ComparisonItem } from "@/components/stock/ComparisonChart";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { apiClient } from "@/lib/apiClient";
import type { ZoomRange } from "@/lib/chartZoom";
import type { SeriesResponse, SimulationSeriesResponse } from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";
import { useThemeStore } from "@/stores/themeStore";

type Datum = { time: string; value?: number };
interface Drawn {
  series: { options: Record<string, unknown>; data: Datum[] }[];
  setVisibleRange: ZoomRange[];
  fitContent: number;
}
const chart = vi.hoisted(() => ({
  charts: [] as Drawn[],
  move: null as null | ((param: unknown) => void),
  timeAt: null as string | null,
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => {
    const drawn: Drawn = { series: [], setVisibleRange: [], fitContent: 0 };
    chart.charts.push(drawn);
    return {
      addSeries: (_kind: unknown, options: Record<string, unknown>) => {
        const entry = { options, data: [] as Datum[] };
        drawn.series.push(entry);
        return { setData: (data: Datum[]) => { entry.data = data; } };
      },
      subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
      timeScale: () => ({
        fitContent: () => { drawn.fitContent += 1; },
        setVisibleRange: (range: ZoomRange) => { drawn.setVisibleRange.push(range); },
        coordinateToTime: () => chart.timeAt,
      }),
      priceScale: () => ({ width: () => 60 }),
      remove: () => undefined,
    };
  },
}));

beforeEach(() => {
  vi.restoreAllMocks();
  chart.charts.length = 0;
  chart.move = null;
  chart.timeAt = null;
  useThemeStore.setState({ theme: "light" });
});

const RANGE = { from: "2024-02-01", to: "2024-03-04" };
const series = (dates: string[], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: dates[0], to: dates[dates.length - 1], principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: dates.length,
  points: dates.map((date) => ({ date, balance: "1000", returnRate: "0.1" })), gaps: [], ...over,
});
const BASE = series(["2024-01-02", "2024-02-01", "2024-03-04", "2024-04-01"]);
const DAILY = series(["2024-02-01", "2024-02-02", "2024-02-05", "2024-02-06", "2024-03-04"]);
const MERGED_DATES = ["2024-01-02", "2024-02-01", "2024-02-02", "2024-02-05", "2024-02-06", "2024-03-04", "2024-04-01"];

const latest = () => chart.charts[chart.charts.length - 1];
const drawnDates = (drawn: Drawn, filter: (s: Drawn["series"][number]) => boolean = () => true) =>
  [...new Set(drawn.series.filter(filter).flatMap((s) => s.data.map((d) => d.time)))].sort();
const status = () => screen.queryByTestId("chart-zoom-note")?.textContent ?? null;
const resetButton = () => screen.queryByRole("button", { name: "리셋" });

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

/** 커서를 그 날 위에 두고 누른다(이력 비교는 누를 때의 좌표 → 날짜). */
function pick(surface: string, date: string) {
  chart.timeAt = date;
  act(() => chart.move?.({ time: date, point: { x: 10, y: 10 }, sourceEvent: { clientX: 120, clientY: 50 } }));
  const el = screen.getByTestId(surface);
  fireEvent.mouseDown(el, { clientX: 120, clientY: 50 });
  fireEvent.click(el, { clientX: 120, clientY: 50 });
}
const zoomTo = (surface: string, range: ZoomRange) => { pick(surface, range.from); pick(surface, range.to); };

describe("성과 추이", () => {
  const view = (load?: (range: ZoomRange) => Promise<SimulationSeriesResponse>, data = BASE): ReactElement =>
    <PerformanceChart series={data} collecting={null} loading={false} loadDetail={load} />;

  it("확대가 끝나면 그 범위로 받고, 받은 점을 끼워 확대 범위를 지킨 채 다시 그린다", async () => {
    const wait = deferred<SimulationSeriesResponse>();
    const load = vi.fn(() => wait.promise);
    render(view(load));
    zoomTo("performance-canvas", RANGE);
    expect(load).toHaveBeenCalledWith(RANGE);
    expect(status()).toBe("일 단위 자료를 받는 중…");
    const before = chart.charts.length;
    await act(async () => { wait.resolve(DAILY); });
    expect(chart.charts.length).toBeGreaterThan(before);
    expect(drawnDates(latest())).toEqual(MERGED_DATES);
    expect(latest().setVisibleRange).toEqual([RANGE]);
    expect(latest().fitContent).toBe(0);
    expect(resetButton()).not.toBeNull();
    expect(status()).toBeNull();
  });

  it("받지 못하면 상태 줄이 알리고 확대는 그대로다 — 원래 점", async () => {
    const load = vi.fn(() => Promise.reject(new Error("fail")));
    render(view(load));
    zoomTo("performance-canvas", RANGE);
    await act(async () => undefined);
    expect(status()).toBe("일 단위 자료를 받지 못했습니다 — 받은 점으로 보입니다");
    expect(resetButton()).not.toBeNull();
    expect(drawnDates(latest())).toEqual(BASE.points.map((p) => p.date));
  });

  it("리셋 뒤에 온 응답은 버린다", async () => {
    const wait = deferred<SimulationSeriesResponse>();
    render(view(() => wait.promise));
    zoomTo("performance-canvas", RANGE);
    fireEvent.click(resetButton() as HTMLElement);
    await act(async () => { wait.resolve(DAILY); });
    expect(drawnDates(latest())).toEqual(BASE.points.map((p) => p.date));
    expect(resetButton()).toBeNull();
    expect(status()).toBeNull();
  });

  it("받은 구간 안의 재확대는 다시 받지 않는다", async () => {
    const load = vi.fn(() => Promise.resolve(DAILY));
    render(view(load));
    zoomTo("performance-canvas", RANGE);
    await act(async () => undefined);
    zoomTo("performance-canvas", { from: "2024-02-02", to: "2024-02-06" });
    expect(load).toHaveBeenCalledTimes(1);
    expect(latest().setVisibleRange.at(-1)).toEqual({ from: "2024-02-02", to: "2024-02-06" });
  });

  it("[리셋]이면 원래 점과 처음 범위다", async () => {
    render(view(() => Promise.resolve(DAILY)));
    zoomTo("performance-canvas", RANGE);
    await act(async () => undefined);
    fireEvent.click(resetButton() as HTMLElement);
    expect(drawnDates(latest())).toEqual(BASE.points.map((p) => p.date));
    expect(latest().fitContent).toBe(1);
    expect(resetButton()).toBeNull();
  });

  it("테마·바탕 자료가 바뀌면 받은 자료를 쓰지 않는다", async () => {
    const { rerender } = render(view(() => Promise.resolve(DAILY)));
    zoomTo("performance-canvas", RANGE);
    await act(async () => undefined);
    act(() => useThemeStore.setState({ theme: "dark" }));
    expect(drawnDates(latest())).toEqual(BASE.points.map((p) => p.date));
    expect(resetButton()).toBeNull();
    const other = series(["2023-01-02", "2023-06-01"]);
    rerender(view(() => Promise.resolve(DAILY), other));
    expect(drawnDates(latest())).toEqual(["2023-01-02", "2023-06-01"]);
  });

  it("받기 함수가 없으면 확대만 한다", () => {
    render(view(undefined));
    zoomTo("performance-canvas", RANGE);
    expect(latest().setVisibleRange).toEqual([RANGE]);
    expect(status()).toBeNull();
  });
});

describe("투자 비교 수익률 추이", () => {
  const items: CompareChartItem[] = [
    { key: "a", name: "삼성전자(005930)", series: BASE,
      lineEnd: { date: "2024-04-01", holdingReturnRate: "0.1", afterSaleReturnRate: null },
      valueLine: { points: BASE.points.map((p) => ({ date: p.date, value: "1000" })), afterSaleValue: null }, currentValue: "1000" },
    { key: "b", name: "SK하이닉스(000660)", series: BASE,
      lineEnd: { date: "2024-04-01", holdingReturnRate: "0.1", afterSaleReturnRate: null } },
  ];

  it("받은 대상만 시계열·현재 가치 선에 구간을 끼운다", async () => {
    const detail: CompareDetailMap = {
      a: { series: DAILY, valueLine: { points: DAILY.points.map((p) => ({ date: p.date, value: "1100" })), afterSaleValue: null } },
    };
    render(<CompareReturnChart items={items} loadDetail={() => Promise.resolve(detail)} />);
    zoomTo("compare-canvas", RANGE);
    await act(async () => undefined);
    const drawn = latest();
    const values = drawn.series.filter((s) => s.options.priceScaleId === "left" && s.options.lineVisible !== false);
    expect(drawnDates({ ...drawn, series: values })).toEqual(MERGED_DATES);
    // 대상 b는 받지 않았다 — 원래 점(색으로 가른다).
    const colorB = drawn.series.find((s) => s.options.color !== drawn.series[0].options.color && s.options.priceScaleId !== "left");
    expect(colorB?.data.map((d) => d.time)).toEqual(BASE.points.map((p) => p.date));
    expect(drawn.setVisibleRange).toEqual([RANGE]);
  });
});

describe("이력 수익률 비교", () => {
  it("항목마다 받은 구간을 끼운다", async () => {
    const items: ComparisonItem[] = [{ id: "h1", label: "삼성전자", start: "2024-01-02", series: BASE }];
    render(<ComparisonChart items={items} loading={false} error={null} loadDetail={() => Promise.resolve({ h1: DAILY })} />);
    zoomTo("comparison-canvas", RANGE);
    await act(async () => undefined);
    expect(drawnDates(latest())).toEqual(MERGED_DATES);
    expect(latest().setVisibleRange).toEqual([RANGE]);
  });
});

describe("화면 연결", () => {
  const fx = (over: Partial<SeriesResponse> = {}): SeriesResponse => ({
    currency: "USD", from: "2004-01-02", to: "2024-04-01", quoteUnit: 1, downsampled: false, algorithm: "lttb", sourcePointCount: 4,
    points: BASE.points.map((p) => ({ date: p.date, baseRate: "1300.0", isProvisional: false })), gaps: [], ...over,
  } as SeriesResponse);

  it("외환은 받은 자료가 줄여졌을 때만 그 통화의 구간을 받는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(fx());
    const { rerender } = render(<TrendChart series={fx()} collecting={null} selectedDate={null} loading={false}
      onSelect={() => undefined} currency="USD" />);
    zoomTo("chart-canvas", RANGE);
    expect(get).not.toHaveBeenCalled();
    rerender(<TrendChart series={fx({ downsampled: true })} collecting={null} selectedDate={null} loading={false}
      onSelect={() => undefined} currency="USD" />);
    zoomTo("chart-canvas", RANGE);
    await act(async () => undefined);
    expect(get).toHaveBeenCalledWith("/api/fx/series?currency=USD&from=2024-02-01&to=2024-03-04&maxPoints=5000");
  });

  it("비교 모달은 주식 줄이면 그 메뉴 시계열 경로로 받고 예금 줄은 받지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(DAILY);
    const { rerender } = render(<ChartSection series={BASE} error={null} path="/api/stocks/simulation/series?symbol=005930.KS" />);
    zoomTo("performance-canvas", RANGE);
    await act(async () => undefined);
    expect(get).toHaveBeenCalledWith(
      "/api/stocks/simulation/series?symbol=005930.KS&viewFrom=2024-02-01&viewTo=2024-03-04&maxPoints=5000");
    get.mockClear();
    rerender(<ChartSection series={series(["2024-01-02", "2024-06-01"])} error={null} path="/api/deposit/simulation/series?x=1" />);
    zoomTo("performance-canvas", { from: "2024-01-02", to: "2024-06-01" });
    expect(get).not.toHaveBeenCalled();
    expect(detailSeriesPath({ open: null })).toBeNull();
  });

  it("주식 메뉴는 받은 시계열의 경로를 기억한다", async () => {
    const run = vi.spyOn(apiClient, "get").mockImplementation(((path: string) => Promise.resolve(path.includes("/series")
      ? BASE : { stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
        condition: { start: "2024-01-02", principal: "10000000", principalCurrency: "KRW", reinvest: true, tradeFeeRate: "0", dividendTaxRate: "0" },
        summary: { principal: "10000000", profit: "1", returnRate: "0.1", asOf: "2024-04-01", isFinal: true },
        rows: [], hasMore: false, oldestReturned: null })) as typeof apiClient.get);
    useStockStore.setState({
      input: { stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" }, start: "2024-01-02",
        principal: "10000000", principalCurrency: "KRW", reinvest: true },
      plan: { mode: "lump_sum", frequency: "monthly" },
    });
    await act(async () => { await useStockStore.getState().run(); });
    const seriesCall = run.mock.calls.map((c) => c[0] as string).find((p) => p.includes("/simulation/series"));
    expect(useStockStore.getState().seriesPath).toBe(seriesCall);
    expect(seriesCall).not.toContain("period=");
  });
});
