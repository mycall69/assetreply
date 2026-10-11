/**
 * 수익률 그래프의 두 지점 확대·리셋 (014 반복 2026-10-11b T184) — spec FR-037, SC-022, contracts D16, data-model 15, research R14-30.
 *
 * 수익률 선이 있는 세 그래프(투자 비교 수익률 추이·성과 추이·이력 수익률 비교)에서 두 날을 차례로 누르면 그 사이(정렬·양 끝 포함)로
 * 시간 축을 맞추고(`setVisibleRange`), 확대된 동안 오른쪽 위 [리셋]이 처음 범위(`fitContent`)로 되돌린다. 첫 누름 뒤에는 상태 줄과
 * [취소]다. 같은 날·[취소]·Esc는 취소, 끌기(4px 넘게 움직임)와 날짜를 모르는 누름은 무시한다. 시계열·테마가 바뀌어 다시 그리면 처음
 * 범위다. 확대·리셋은 요청을 보내지 않는다.
 *
 * 누른 날짜는 이미 커서를 쫓는 두 그래프는 커서 추적(`subscribeCrosshairMove`의 `time`)이, 커서를 쫓지 않는 이력 비교는 누를 때의
 * `timeScale().coordinateToTime`이 준다. **그릴 때는 기존 모의에 있는 API만 쓴다** — 새 API는 누를 때만 부른다(CLAUDE.md 010).
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompareReturnChart, type CompareChartItem } from "@/components/compare/CompareReturnChart";
import { ComparisonChart, type ComparisonItem } from "@/components/stock/ComparisonChart";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationSeriesResponse } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";
import { series } from "./support/compareFixtures";

const chart = vi.hoisted(() => ({
  move: null as null | ((param: unknown) => void),
  timeAt: null as string | null,
  fitContent: [] as number[],
  setVisibleRange: [] as { from: unknown; to: unknown }[],
  coordinateToTime: [] as number[],
  subscribeClick: 0,
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
    subscribeClick: () => { chart.subscribeClick += 1; },
    timeScale: () => ({
      fitContent: () => { chart.fitContent.push(1); },
      setVisibleRange: (range: { from: unknown; to: unknown }) => { chart.setVisibleRange.push(range); },
      coordinateToTime: (x: number) => { chart.coordinateToTime.push(x); return chart.timeAt; },
    }),
    // 014 승인 2026-10-11(반복 2026-10-11c T195) — 확대 단추를 오른쪽 가격 축 밖에 두려고 처음 누를 때 축 폭을 잰다(FR-039)
    priceScale: () => ({ width: () => 60 }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.move = null;
  chart.timeAt = null;
  chart.fitContent.length = 0;
  chart.setVisibleRange.length = 0;
  chart.coordinateToTime.length = 0;
  chart.subscribeClick = 0;
  useThemeStore.setState({ theme: "light" });
});

const POINTS: [string, string][] = [["2024-01-02", "0"], ["2024-03-04", "0.05"], ["2024-09-30", "0.1"], ["2024-12-30", "0.2"]];
const SERIES: SimulationSeriesResponse = series(POINTS);
const OTHER: SimulationSeriesResponse = series([["2023-01-02", "0"], ["2023-12-28", "0.3"]]);

const compareItems = (s: SimulationSeriesResponse): CompareChartItem[] => [{
  key: "a", name: "삼성전자(005930)", series: s,
  lineEnd: { date: s.points[s.points.length - 1].date, holdingReturnRate: "0.2", afterSaleReturnRate: null },
}];
const historyItems = (s: SimulationSeriesResponse): ComparisonItem[] => [{ id: "h1", label: "삼성전자", start: s.from, series: s }];

interface Case {
  name: string;
  view: (s: SimulationSeriesResponse) => ReactElement;
  surface: string;
  /** 그 날 위에 커서를 둔다 — 커서 추적 그래프는 `time`, 이력 비교는 누를 때의 좌표 → 날짜. */
  hover: (date: string | null) => void;
}

const crosshair = (date: string | null) => act(() => chart.move?.(date === null
  ? { time: undefined, point: undefined }
  : { time: date, point: { x: 10, y: 10 }, sourceEvent: { clientX: 120, clientY: 50 } }));

const CASES: Case[] = [
  { name: "투자 비교 수익률 추이", view: (s) => <CompareReturnChart items={compareItems(s)} />, surface: "compare-canvas", hover: crosshair },
  {
    name: "성과 추이", view: (s) => <PerformanceChart series={s} collecting={null} loading={false} />,
    surface: "performance-canvas", hover: crosshair,
  },
  {
    name: "이력 수익률 비교", view: (s) => <ComparisonChart items={historyItems(s)} loading={false} error={null} />,
    surface: "comparison-canvas", hover: (date) => { chart.timeAt = date; },
  },
];

/** 누르기 — 같은 자리에서 눌렀다 뗀다. `to`가 있으면 그만큼 끌고 뗀다. */
function press(surface: string, at = 120, to = at) {
  const el = screen.getByTestId(surface);
  fireEvent.mouseDown(el, { clientX: at, clientY: 50 });
  fireEvent.click(el, { clientX: to, clientY: 50 });
}

const status = () => screen.queryByTestId("chart-zoom-status");
const resetButton = () => screen.queryByRole("button", { name: "리셋" });

describe.each(CASES)("$name", ({ view, surface, hover }) => {
  const pick = (date: string) => { hover(date); press(surface); };

  it("첫 누름이면 오른쪽 위에 시작 날짜와 [취소]이고 그래프는 그대로다", () => {
    render(view(SERIES));
    pick("2024-03-04");
    expect(status()).toHaveTextContent("시작 2024-03-04 · 끝 지점을 누르세요");
    expect(screen.getByRole("button", { name: "취소" })).toBeInTheDocument();
    expect(chart.setVisibleRange).toEqual([]);
    expect(resetButton()).toBeNull();
  });

  it("다른 날을 누르면 두 날 사이로 확대하고 [리셋]이 보인다 — 앞뒤 차례와 무관하다", () => {
    render(view(SERIES));
    pick("2024-09-30");
    pick("2024-03-04");
    expect(chart.setVisibleRange).toEqual([{ from: "2024-03-04", to: "2024-09-30" }]);
    expect(status()).toBeNull();
    expect(resetButton()).toHaveAttribute("title", "처음 범위로 되돌립니다");
  });

  it("[리셋]이면 처음 범위로 돌아가고 단추가 사라진다", () => {
    render(view(SERIES));
    const drawn = chart.fitContent.length;
    pick("2024-03-04");
    pick("2024-09-30");
    fireEvent.click(resetButton() as HTMLElement);
    expect(chart.fitContent.length).toBe(drawn + 1);
    expect(resetButton()).toBeNull();
    expect(status()).toBeNull();
  });

  it("확대 안에서 다시 확대할 수 있고 리셋은 처음 범위다", () => {
    render(view(SERIES));
    const drawn = chart.fitContent.length;
    pick("2024-01-02");
    pick("2024-12-30");
    pick("2024-03-04");
    // 확대된 채 고르는 동안에도 [리셋]으로 처음 범위로 갈 수 있다.
    expect(status()).toHaveTextContent("시작 2024-03-04");
    expect(resetButton()).not.toBeNull();
    pick("2024-09-30");
    expect(chart.setVisibleRange).toEqual([{ from: "2024-01-02", to: "2024-12-30" }, { from: "2024-03-04", to: "2024-09-30" }]);
    fireEvent.click(resetButton() as HTMLElement);
    expect(chart.fitContent.length).toBe(drawn + 1);
    expect(resetButton()).toBeNull();
  });

  it("같은 날을 다시 누르면 취소다", () => {
    render(view(SERIES));
    pick("2024-03-04");
    pick("2024-03-04");
    expect(status()).toBeNull();
    expect(chart.setVisibleRange).toEqual([]);
  });

  it("[취소]와 Esc는 고르기를 취소한다", () => {
    render(view(SERIES));
    pick("2024-03-04");
    fireEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(status()).toBeNull();
    pick("2024-03-04");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(status()).toBeNull();
    // 취소 뒤 누르면 다시 시작 지점이다(앞의 고르기가 남지 않는다).
    pick("2024-09-30");
    expect(status()).toHaveTextContent("시작 2024-09-30");
    expect(chart.setVisibleRange).toEqual([]);
  });

  it("고르는 동안의 Esc는 고르기만 취소한다 — 모달의 Esc(문서 처리기)까지 가지 않는다", () => {
    const modalEsc = vi.fn();
    document.addEventListener("keydown", modalEsc);
    render(view(SERIES));
    pick("2024-03-04");
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(status()).toBeNull();
    expect(modalEsc).not.toHaveBeenCalled();
    // 고르는 중이 아니면 Esc는 지금처럼 모달까지 간다.
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(modalEsc).toHaveBeenCalledTimes(1);
    document.removeEventListener("keydown", modalEsc);
  });

  it("끌어 옮긴 것은 누르기가 아니다", () => {
    render(view(SERIES));
    hover("2024-03-04");
    press(surface, 100, 160);
    expect(status()).toBeNull();
    pick("2024-03-04");
    hover("2024-09-30");
    press(surface, 100, 103);
    expect(chart.setVisibleRange).toEqual([{ from: "2024-03-04", to: "2024-09-30" }]);
  });

  it("커서 날짜를 모르면 무시한다 — 직전 날짜로 고르지 않는다", () => {
    render(view(SERIES));
    hover("2024-03-04");
    hover(null);
    press(surface);
    expect(status()).toBeNull();
  });

  it("시계열이 바뀌어 다시 그리면 처음 범위·단추 없음이다", () => {
    const { rerender } = render(view(SERIES));
    pick("2024-03-04");
    pick("2024-09-30");
    expect(resetButton()).not.toBeNull();
    rerender(view(OTHER));
    expect(resetButton()).toBeNull();
    pick("2023-01-02");
    rerender(view(SERIES));
    expect(status()).toBeNull();
  });

  it("테마가 바뀌어 다시 그리면 처음 범위·단추 없음이다", () => {
    render(view(SERIES));
    pick("2024-03-04");
    pick("2024-09-30");
    act(() => useThemeStore.setState({ theme: "dark" }));
    expect(resetButton()).toBeNull();
  });

  it("그릴 때는 새 API를 부르지 않는다 — 확대·리셋은 요청을 보내지 않는다", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(view(SERIES));
    expect(chart.setVisibleRange).toEqual([]);
    expect(chart.coordinateToTime).toEqual([]);
    expect(chart.subscribeClick).toBe(0);
    pick("2024-03-04");
    pick("2024-09-30");
    fireEvent.click(resetButton() as HTMLElement);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});

describe("이력 수익률 비교의 날짜", () => {
  it("누른 화면 좌표를 그래프 칸 기준으로 바꿔 묻는다", () => {
    render(<ComparisonChart items={historyItems(SERIES)} loading={false} error={null} />);
    chart.timeAt = "2024-03-04";
    press("comparison-canvas", 240);
    // jsdom의 칸 위치는 0이다 — 왼쪽 가격 축이 없어 그래프 칸이 칸의 왼쪽 끝에서 시작한다.
    expect(chart.coordinateToTime).toEqual([240]);
    expect(status()).toHaveTextContent("시작 2024-03-04");
  });
});

describe("확대 그래프", () => {
  const source = (path: string) => readFileSync(resolve(__dirname, "../src", path), "utf8");

  // 014 승인 2026-10-11(반복 2026-10-11c T195) — 외환 추이·지표 일봉 그래프에도 두 지점 확대를 더한다(FR-039 — FR-037의 "대상 밖"을 대체).
  // 지표 장중 그래프는 대상 밖이다(ChartZoomPlacement.test.tsx).
  it("수익률 그래프 셋과 외환·지표 그래프가 같은 훅과 단추를 쓴다", () => {
    for (const path of ["components/compare/CompareReturnChart.tsx", "components/stock/PerformanceChart.tsx",
      "components/stock/ComparisonChart.tsx", "components/FxChart.tsx", "components/dashboard/IndicatorChart.tsx"]) {
      expect(source(path)).toMatch(/useChartZoom/);
      expect(source(path)).toMatch(/ChartZoomControls/);
    }
  });
});
