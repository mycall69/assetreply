/**
 * 수익률 추이의 현재 가치 축 (014 반복 2026-10-11b T183) — spec FR-036, SC-021, contracts D15·A12, data-model 14, research R14-29.
 *
 * 비교 블록의 `valueLine`이 있으면 왼쪽 가격 축을 켜고 대상마다 **현재 가치 가는 선**(1px, 그 대상의 색·선 모양, 원화 축 형식)을
 * 그린다. 결측·잠정 나누기는 수익률 선과 같은 자리이고, 기준일까지 `currentValue`로 잇고, 매도 후면 기준일에 매도 후 금액 점이다.
 * 커서 상자의 대상 줄마다 현재 가치(`₩`)가 붙는다. `valueLine`이 없으면(014 전 응답의 대역) 지금과 같다.
 *
 * 모의는 기존 차트 테스트와 같은 API만 둔다(CLAUDE.md 010) — 그 밖의 API를 그릴 때 부르면 이 테스트가 깨진다.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { CompareReturnChart, colorOf, lineStyleOf, type CompareChartItem } from "@/components/compare/CompareReturnChart";
import { apiClient } from "@/lib/apiClient";
import type { ComparisonBlock } from "@/lib/types";
import { useCompareStore } from "@/stores/compareStore";
import { HYNIX_T, SAMSUNG_T, ok, series } from "./support/compareFixtures";

type Datum = { time: string; value?: number };
const chart = vi.hoisted(() => ({
  options: null as null | Record<string, unknown>,
  series: [] as { options: Record<string, unknown>; data: Datum[] }[],
  move: null as null | ((param: unknown) => void),
}));
vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: (_el: unknown, options: Record<string, unknown>) => {
    // 다시 만든 차트의 시리즈만 센다(앞 차트는 `remove`로 사라졌다).
    chart.options = options;
    chart.series.length = 0;
    return {
      addSeries: (_kind: unknown, options: Record<string, unknown>) => {
        const entry = { options, data: [] as Datum[] };
        chart.series.push(entry);
        return { setData: (data: Datum[]) => { entry.data = data; } };
      },
      subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
      timeScale: () => ({ fitContent: () => undefined }),
      remove: () => undefined,
    };
  },
}));

beforeEach(() => {
  chart.options = null;
  chart.series.length = 0;
  chart.move = null;
});

type ValueLine = NonNullable<ComparisonBlock["valueLine"]>;
const line = (values: [string, string][], afterSaleValue: string | null = "12045573"): ValueLine => ({
  points: values.map(([date, value]) => ({ date, value })), afterSaleValue,
});

const item = (key: string, name: string, over: Partial<CompareChartItem> = {}): CompareChartItem => ({
  key, name,
  series: series([["2024-01-02", "0"], ["2025-01-02", "0.1"], ["2026-10-01", "0.25"]]),
  lineEnd: { date: "2026-10-06", holdingReturnRate: "0.259648", afterSaleReturnRate: "0.204557" },
  valueLine: line([["2024-01-02", "10000000"], ["2025-01-02", "11000000"], ["2026-10-01", "12500000"]]),
  currentValue: "12596486",
  ...over,
});

const valueSeries = () => chart.series.filter((s) => s.options.priceScaleId === "left");
const valueLines = () => valueSeries().filter((s) => s.options.lineVisible !== false);
const returnLines = () => chart.series.filter((s) => s.options.priceScaleId !== "left" && s.options.lineVisible !== false);
const hoverAt = (time: string) => act(() => chart.move?.({ time, point: { x: 10, y: 10 }, sourceEvent: { clientX: 200, clientY: 120 } }));

describe("왼쪽 축", () => {
  it("현재 가치가 있으면 왼쪽 가격 축을 켠다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    expect((chart.options?.leftPriceScale as { visible?: boolean } | undefined)?.visible).toBe(true);
  });

  it("현재 가치 선은 원화 축 형식이다 — 소수 없음·천 단위 쉼표", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    const format = valueLines()[0].options.priceFormat as { minMove: number; formatter: (n: number) => string };
    expect(format.minMove).toBe(1);
    expect(format.formatter(12596486)).toBe("12,596,486");
  });

  it("`valueLine`이 없으면 왼쪽 축·현재 가치 선이 없다 — 014 전과 같다", () => {
    render(<CompareReturnChart items={[item("a", "XLK", { valueLine: undefined, currentValue: undefined })]} />);
    expect(valueSeries()).toEqual([]);
    expect((chart.options?.leftPriceScale as { visible?: boolean } | undefined)?.visible).not.toBe(true);
    expect(screen.queryByTestId("compare-axes")).toBeNull();
  });
});

describe("현재 가치 선", () => {
  it("대상마다 그 대상의 색·선 모양의 1px 선이고 수익률 선은 2px 오른쪽 축이다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)"), item("b", "SK하이닉스(000660)")]} />);
    const values = valueLines().filter((s) => s.data.length === 3);
    expect(values).toHaveLength(2);
    values.forEach((s, index) => {
      expect(s.options.lineWidth).toBe(1);
      expect(s.options.color).toBe(colorOf(index));
      expect(s.options.lineStyle).toBe(lineStyleOf(index));
    });
    expect(returnLines().every((s) => s.options.lineWidth === 2)).toBe(true);
  });

  it("점마다 그 날의 현재 가치다 — 그리기 위해서만 숫자다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    const [first] = valueLines();
    expect(first.data.map((d) => d.time)).toEqual(["2024-01-02", "2025-01-02", "2026-10-01"]);
    expect(first.data.map((d) => d.value)).toEqual([10000000, 11000000, 12500000]);
  });

  it("결측 구간에서 수익률 선과 같은 자리에서 끊는다", () => {
    const broken = series([["2024-01-02", "0"], ["2024-03-04", "0.1"], ["2024-06-03", "0.2"]],
      { gaps: [{ from: "2024-02-01", to: "2024-02-28", reason: "not_collected" }] });
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)", {
      series: broken,
      valueLine: line([["2024-01-02", "10000000"], ["2024-03-04", "11000000"], ["2024-06-03", "12000000"]], null),
      lineEnd: { date: "2024-06-03", holdingReturnRate: "0.2", afterSaleReturnRate: null }, currentValue: "12000000",
    })]} />);
    expect(valueLines().map((s) => s.data.map((d) => d.time))).toEqual([["2024-01-02"], ["2024-03-04", "2024-06-03"]]);
    expect(returnLines().map((s) => s.data.map((d) => d.time))).toEqual([["2024-01-02"], ["2024-03-04", "2024-06-03"]]);
  });

  it("잠정 구간은 연한 색의 따로 된 선이다 — 수익률 선과 같은 경계", () => {
    const provisional = series([["2026-06-01", "0.1"], ["2026-08-01", "0.2"], ["2026-09-01", "0.3"]],
      { provisionalFrom: "2026-08-01" });
    render(<CompareReturnChart items={[item("a", "시중은행", {
      series: provisional,
      valueLine: line([["2026-06-01", "11000000"], ["2026-08-01", "12000000"], ["2026-09-01", "13000000"]], null),
      lineEnd: { date: "2026-09-01", holdingReturnRate: "0.3", afterSaleReturnRate: null }, currentValue: "13000000",
    })]} />);
    const [confirmed, light] = valueLines();
    expect(confirmed.data.map((d) => d.time)).toEqual(["2026-06-01", "2026-08-01"]);
    expect(light.data.map((d) => d.time)).toEqual(["2026-08-01", "2026-09-01"]);
    expect(light.options.color).not.toBe(confirmed.options.color);
  });

  it("`valueLine`에 없는 날은 그 점만 비운다 — 앞 값으로 메우지 않는다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)", {
      valueLine: line([["2024-01-02", "10000000"], ["2026-10-01", "12500000"]]),
    })]} />);
    expect(valueLines()[0].data.map((d) => d.time)).toEqual(["2024-01-02", "2026-10-01"]);
  });
});

describe("기준일의 끝", () => {
  it("시계열 마지막 날이 기준일보다 앞이면 기준일의 현재 가치까지 잇는다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    const connector = valueLines().find((s) => s.data.length === 2 && s.data[1].time === "2026-10-06");
    expect(connector?.data).toEqual([{ time: "2026-10-01", value: 12500000 }, { time: "2026-10-06", value: 12596486 }]);
    expect(connector?.options.lineWidth).toBe(1);
  });

  it("마지막 날이 기준일이면 잇지 않는다", () => {
    render(<CompareReturnChart items={[item("a", "비트코인(BTC)", {
      lineEnd: { date: "2026-10-01", holdingReturnRate: "0.25", afterSaleReturnRate: null }, currentValue: "12500000",
      valueLine: line([["2024-01-02", "10000000"], ["2025-01-02", "11000000"], ["2026-10-01", "12500000"]], null),
    })]} />);
    expect(valueLines()).toHaveLength(1);
  });

  it("매도 후 금액이 있으면 기준일에 왼쪽 축의 점이다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    const dots = valueSeries().filter((s) => s.options.lineVisible === false);
    expect(dots).toHaveLength(1);
    expect(dots[0].options.pointMarkersVisible).toBe(true);
    expect(dots[0].data).toEqual([{ time: "2026-10-06", value: 12045573 }]);
  });

  it("매도 후 금액이 없으면 점이 없다", () => {
    render(<CompareReturnChart items={[item("a", "시중은행", {
      lineEnd: { date: "2026-10-06", holdingReturnRate: "0.259648", afterSaleReturnRate: null },
      valueLine: line([["2024-01-02", "10000000"], ["2025-01-02", "11000000"], ["2026-10-01", "12500000"]], null),
    })]} />);
    expect(valueSeries().filter((s) => s.options.lineVisible === false)).toEqual([]);
  });
});

describe("커서 상자·축 설명", () => {
  it("대상 줄마다 그 날의 현재 가치가 붙는다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    hoverAt("2025-01-02");
    expect(screen.getByTestId("compare-hover")).toHaveTextContent("삼성전자(005930) +10.00% · ₩11,000,000");
  });

  it("기준일에는 보유 중·매도 후 금액이 함께다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    hoverAt("2026-10-06");
    expect(screen.getByTestId("compare-hover"))
      .toHaveTextContent("삼성전자(005930) 보유 중 +25.96% (₩12,596,486) · 매도 후 +20.45% (₩12,045,573)");
  });

  it("값이 없는 대상은 지금처럼 값 없음이다", () => {
    const short = series([["2024-01-02", "0"]]);
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)"), item("b", "SK하이닉스(000660)", {
      series: short, valueLine: line([["2024-01-02", "10000000"]], null),
      lineEnd: { date: "2024-01-02", holdingReturnRate: "0", afterSaleReturnRate: null }, currentValue: "10000000",
    })]} />);
    hoverAt("2025-01-02");
    expect(screen.getByTestId("compare-hover")).toHaveTextContent("SK하이닉스(000660) 값 없음");
  });

  it("`valueLine`이 없으면 커서 상자는 지금과 같다", () => {
    render(<CompareReturnChart items={[item("a", "XLK", { valueLine: undefined, currentValue: undefined })]} />);
    hoverAt("2025-01-02");
    const box = screen.getByTestId("compare-hover");
    expect(box).toHaveTextContent("XLK +10.00%");
    expect(box.textContent).not.toContain("₩");
  });

  it("축 설명 한 줄이 있고 선 기준 줄은 그대로다", () => {
    render(<CompareReturnChart items={[item("a", "삼성전자(005930)")]} />);
    expect(screen.getByTestId("compare-axes")).toHaveTextContent("굵은 선 수익률(오른쪽 축, %) · 가는 선 현재 가치(왼쪽 축, KRW)");
    expect(screen.getByTestId("compare-basis")).toHaveTextContent("선: 보유 중(매도 전) · 끝 점: 매도 후");
  });
});

describe("비교 화면", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useCompareStore.getState().dispose();
    useCompareStore.setState(useCompareStore.getInitialState(), true);
    useCompareStore.setState({ start: "2020-01-02" });
    for (const t of [SAMSUNG_T, HYNIX_T]) useCompareStore.getState().addTarget(t);
  });

  it("비교 블록의 `valueLine`·`currentValue`를 수익률 추이에 넘긴다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
      if (path.startsWith("/api/stocks/search")) return Promise.resolve({ query: "", results: [], truncated: false, lists: [] });
      const hynix = path.includes("000660");
      return Promise.resolve(ok(hynix ? HYNIX_T : SAMSUNG_T, {
        currentValue: hynix ? "13000000" : "12596486",
        valueLine: line([["2020-01-02", "10000000"], ["2026-10-01", hynix ? "12900000" : "12500000"]]),
      }));
    }) as typeof apiClient.get);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByTestId("compare-chart");
    await waitFor(() => expect(valueLines().filter((s) => s.data.length === 2 && s.data[0].time === "2020-01-02")).toHaveLength(2));
    const connectors = valueLines().filter((s) => s.data[1]?.time === "2026-10-06");
    expect(connectors.map((s) => s.data[1].value).sort()).toEqual([12596486, 13000000]);
    expect(screen.getByTestId("compare-axes")).toBeInTheDocument();
  });
});
