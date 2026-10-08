"use client";

/**
 * 비교의 수익률 추이 (013 T055) — FR-015(명확화 5), SC-005, research R13-5, ui-wireframes F6.
 *
 * - **선은 보유 중(매도 전) 수익률**이다 — 메뉴 시계열의 `returnRate` 그대로다. 결측 구간에서 끊는 규칙은 메뉴 차트와 같다
 *   (`splitSeriesAtGaps` — 휴장은 잇고 나머지는 끊는다). 잠정 구간(`provisionalFrom` 뒤)은 연한 색이다(원칙 V)
 * - 시계열 마지막 날이 기준일보다 앞이면(주식은 행 날짜에만 점이 있다) **기준일까지 보유 중 값으로 잇는다**. 매도 후 값이 있으면 기준일에
 *   **점만 그리는 시리즈**를 하나 더한다 — 표의 수익률과 같은 값이다. 매도 후 값이 없으면 점을 찍지 않는다(선 끝 값으로 메우지 않는다)
 * - **색만으로 가르지 않는다** — 색 10개에 선 모양(실선·점선)이 번갈고, 범례·커서 상자에 이름이 있다
 * - 모의 객체에 있는 API만 쓴다(`createChart`·`addSeries`·`setData`·`subscribeCrosshairMove`·`timeScale().fitContent`·`remove`) — 열거형도
 *   실행 중에 읽지 않는다(선 모양은 수 상수). 커서 상자는 `sourceEvent`의 화면 좌표로 놓는다(010)
 *
 * 그리기 위해서만 숫자로 바꾼다(`toPerformanceData`) — 상자의 값은 원본 문자열을 형식 함수로 보인다(헌법 원칙 VI).
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { placeHover } from "@/lib/chartHover";
import { axisPriceFormat, splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import { formatPercent } from "@/lib/format";
import type { ComparisonBlock, SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

export interface CompareChartItem {
  key: string;
  name: string;
  series: SimulationSeriesResponse;
  lineEnd: ComparisonBlock["lineEnd"];
}

/** 대상 10개를 가를 색 — 서로 다른 색상(hue)으로 고른다. */
const PALETTE: readonly [number, number, number][] = [
  [37, 99, 235], [220, 38, 38], [22, 163, 74], [217, 119, 6], [147, 51, 234],
  [8, 145, 178], [219, 39, 119], [101, 163, 13], [79, 70, 229], [120, 113, 108],
];
/** 선 모양 — 라이브러리의 `LineStyle` 값(0 실선, 2 점선). 열거형을 실행 중에 읽지 않는다. */
const SOLID = 0;
const DASHED = 2;

const rgb = ([r, g, b]: readonly number[], alpha = 1) => (alpha === 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`);
export const colorOf = (index: number) => rgb(PALETTE[index % PALETTE.length]);
export const lineStyleOf = (index: number) => (index % 2 === 0 ? SOLID : DASHED);

/** 잠정 시작일 앞(확정)과 뒤(잠정 — 앞 구간의 마지막 점에서 잇는다)로 나눈다. */
function splitProvisional(points: SimulationPoint[], from: string | null | undefined): [SimulationPoint[], SimulationPoint[]] {
  if (from === null || from === undefined) return [points, []];
  const confirmed = points.filter((p) => p.date <= from);
  if (confirmed.length === points.length) return [points, []];
  const start = confirmed.length > 0 ? confirmed.length - 1 : 0;
  return [confirmed, points.slice(start)];
}

const percentValue = (rate: string) => toPerformanceData([{ date: "", balance: "0", returnRate: rate }], "returnRate")[0].value;

interface Hover {
  date: string;
  client: { x: number; y: number } | null;
  point: { x: number; y: number };
}

function hoverLine(item: CompareChartItem, date: string): string {
  if (date === item.lineEnd.date && item.lineEnd.holdingReturnRate !== null) {
    const after = item.lineEnd.afterSaleReturnRate;
    return `${item.name} 보유 중 ${formatPercent(item.lineEnd.holdingReturnRate)}`
      + (after === null ? "" : ` · 매도 후 ${formatPercent(after)}`);
  }
  const point = item.series.points.find((p) => p.date === date);
  return `${item.name} ${point === undefined ? "값 없음" : formatPercent(point.returnRate)}`;
}

export function CompareReturnChart({ items }: { items: CompareChartItem[] }) {
  const container = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (hover === null || area.current === null || box.current === null) {
      setPlace(null);
      return;
    }
    const chart = area.current.getBoundingClientRect();
    const size = box.current.getBoundingClientRect();
    const cursor = hover.client === null ? hover.point : { x: hover.client.x - chart.left, y: hover.client.y - chart.top };
    setPlace(placeHover(cursor, { width: size.width, height: size.height }, { width: chart.width, height: chart.height }));
  }, [hover]);

  useEffect(() => {
    if (!container.current || items.length === 0) return;
    const instance = createChart(container.current, {
      height: 360,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const priceFormat = axisPriceFormat(2);
    const line = (color: string, lineStyle: number) => instance.addSeries(LineSeries, {
      color, lineWidth: 2, lineStyle, priceFormat, priceLineVisible: false, lastValueVisible: false,
    });

    items.forEach((item, index) => {
      const base = PALETTE[index % PALETTE.length];
      const lineStyle = lineStyleOf(index);
      for (const segment of splitSeriesAtGaps(item.series.points, item.series.gaps)) {
        const [confirmed, provisional] = splitProvisional(segment, item.series.provisionalFrom);
        for (const [part, alpha] of [[confirmed, 1], [provisional, 0.4]] as const) {
          if (part.length === 0) continue;
          line(rgb(base, alpha), lineStyle).setData(
            toPerformanceData(part, "returnRate").map((d) => ({ time: d.time, value: d.value })));
        }
      }
      const { date, holdingReturnRate, afterSaleReturnRate } = item.lineEnd;
      const last = item.series.points.reduce<SimulationPoint | null>(
        (acc, p) => (acc === null || p.date > acc.date ? p : acc), null);
      // 선 끝을 기준일에 맞춘다 — 마지막 점에서 기준일의 보유 중 값까지(보드의 보유 중 값).
      if (last !== null && last.date < date && holdingReturnRate !== null) {
        line(rgb(base), lineStyle).setData([
          { time: last.date, value: percentValue(last.returnRate) },
          { time: date, value: percentValue(holdingReturnRate) },
        ]);
      }
      // 매도 후 점 — 기준일 하나. 없으면 찍지 않는다.
      if (afterSaleReturnRate !== null) {
        instance.addSeries(LineSeries, {
          color: rgb(base), lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 5, priceFormat,
          priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        }).setData([{ time: date, value: percentValue(afterSaleReturnRate) }]);
      }
    });

    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      const point = param.point;
      const source = param.sourceEvent;
      setHover(time === undefined || point === undefined ? null : {
        date: time, point: { x: point.x, y: point.y },
        client: source === undefined || source === null ? null : { x: source.clientX, y: source.clientY },
      });
    });
    instance.timeScale().fitContent();
    return () => {
      instance.remove();
    };
  }, [items]);

  return (
    <section className="rounded-lg border border-gray-200 p-4" data-testid="compare-chart">
      <h3 className="mb-1 text-sm font-semibold">수익률 추이 (KRW)</h3>
      <p data-testid="compare-basis" className="mb-2 text-xs text-gray-500">선: 보유 중(매도 전) · 끝 점: 매도 후</p>
      <div ref={area} className="relative">
        <div ref={container} />
        {hover && (
          <div ref={box} role="tooltip" data-testid="compare-hover"
            className="pointer-events-none absolute z-10 rounded border border-gray-200 bg-white/95 px-3 py-2 text-xs shadow-md"
            style={place === null ? { left: 0, top: 0, visibility: "hidden" } : { left: place.left, top: place.top }}>
            <p className="mb-1 font-medium text-gray-700">{hover.date}</p>
            <ul className="space-y-0.5 whitespace-nowrap">
              {items.map((item, index) => (
                <li key={item.key} style={{ color: colorOf(index) }}>{hoverLine(item, hover.date)}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <p data-testid="compare-legend" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {items.map((item, index) => (
          <span key={item.key} style={{ color: colorOf(index) }}>
            {lineStyleOf(index) === SOLID ? "━" : "┅"} {item.name}
          </span>
        ))}
      </p>
    </section>
  );
}
