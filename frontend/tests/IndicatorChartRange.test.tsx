/**
 * 지표 그래프의 기간 8개 (014 반복 2026-10-10b T107) — FR-011, FR-012, FR-028, SC-002, contracts D3.
 *
 * 이 파일 안에서 `lightweight-charts`를 모의한다.
 *
 * - 일봉 기간은 받은 점 전부를 그리고 처음 범위를 따로 두지 않는다(`fitContent`) — 기간 단추가 범위다
 * - 장중(일·주)은 점이 모두 잠정이라 연한 선 하나다. 시각은 초 단위 UTC 숫자다(라이브러리 그리기 전용)
 * - 장중 커서 상자는 그 시장의 현지 시각과 한국 시간·값·⏳ 잠정이다
 */
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import { intradayOf, rangeSeriesOf } from "./support/indicatorModalFixtures";

const chart = vi.hoisted(() => ({
  series: [] as { options: Record<string, unknown>; data: { time: string | number; value: number }[] }[],
  range: null as { from: number; to: number } | null,
  fitted: 0,
  crosshair: null as ((param: { time?: string | number }) => void) | null,
}));

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_type: string, options: Record<string, unknown>) => {
      const entry = { options, data: [] as { time: string | number; value: number }[] };
      chart.series.push(entry);
      return { setData: (data: { time: string | number; value: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: (fn: (param: { time?: string | number }) => void) => { chart.crosshair = fn; },
    timeScale: () => ({
      fitContent: () => { chart.fitted += 1; },
      setVisibleLogicalRange: (r: { from: number; to: number }) => { chart.range = r; },
    }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  chart.series = [];
  chart.range = null;
  chart.fitted = 0;
  chart.crosshair = null;
});

describe("일봉 기간", () => {
  it("받은 점 전부를 그리고 처음 범위를 두지 않는다", () => {
    const points = Array.from({ length: 600 }, (_, i) => ({
      date: new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10), value: "100.000000",
    }));
    render(<IndicatorChart series={rangeSeriesOf({ range: "5y", points })} />);
    expect(chart.range).toBeNull();
    expect(chart.fitted).toBe(1);
    expect(chart.series.reduce((n, s) => n + s.data.length, 0)).toBe(600);
  });
});

describe("기간 전환", () => {
  it("다른 기간의 그래프로 바뀌면 옛 커서 상자를 남기지 않는다", () => {
    // T123 실측(2026-10-10) — 기간을 바꿔도 커서가 움직이지 않으면 상자가 옛 기간의 점(날짜·값)을 보였다
    const { rerender } = render(<IndicatorChart series={rangeSeriesOf({ range: "1y" })} />);
    act(() => chart.crosshair?.({ time: "2026-10-07" }));
    expect(screen.getByTestId("indicator-tooltip")).toHaveTextContent("2026-10-07");
    rerender(<IndicatorChart series={rangeSeriesOf({ range: "5y", points: [{ date: "2021-10-11", value: "4400.000000" }] })} />);
    expect(screen.queryByTestId("indicator-tooltip")).toBeNull();
  });
});

describe("장중", () => {
  it("점이 모두 잠정이라 연한 선 하나이고 시각은 초 단위 숫자다", () => {
    render(<IndicatorChart series={intradayOf()} />);
    expect(chart.series).toHaveLength(1);
    expect(chart.series[0].options.lineStyle).toBe(2);
    expect(chart.series[0].data.map((d) => d.time)).toEqual([
      Date.UTC(2026, 9, 9, 17, 30) / 1000,
      Date.UTC(2026, 9, 9, 17, 35) / 1000,
    ]);
  });

  it("커서 상자는 현지·한국 시각과 값, 잠정이다", () => {
    render(<IndicatorChart series={intradayOf()} />);
    act(() => chart.crosshair?.({ time: Date.UTC(2026, 9, 9, 17, 35) / 1000 }));
    const box = screen.getByTestId("indicator-tooltip");
    expect(box).toHaveTextContent("10-09 13:35 (한국 02:35)");
    expect(box).toHaveTextContent("7,802.50");
    expect(box).toHaveTextContent("⏳ 잠정");
  });

  it("실패면 까닭과 다시 시도다", () => {
    const onRetry = vi.fn();
    render(<IndicatorChart series={intradayOf({ status: "failed", points: [], failure: { reason: "rate_limited", message: "x", retryAfterSeconds: null } })} onRetry={onRetry} />);
    expect(screen.getByText(/장중 시세를 받지 못했습니다 — 출처 응답 제한/)).toBeInTheDocument();
    act(() => screen.getByRole("button", { name: "다시 시도" }).click());
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("환율 장중은 시장 환율임을 밝힌다", () => {
    render(<IndicatorChart series={intradayOf({ notes: ["market_fx"] })} />);
    expect(screen.getByText("시장 환율 — 고시 이력과 다른 계열")).toBeInTheDocument();
  });
});
