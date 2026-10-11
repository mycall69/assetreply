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
 *
 * **왼쪽 축은 현재 가치다**(014 반복 2026-10-11b — FR-036, research R14-29). 비교 블록의 `valueLine`이 있으면 왼쪽 가격 축을 켜고 대상마다
 * 가는 선(1px, 그 대상의 색·선 모양, 원화 축 형식)을 그린다 — 점은 서버가 고른 그 날의 원화 총자산이고, 결측·잠정 나누기는 수익률 선과 같은
 * 구간에서 한다. 기준일까지 `currentValue`로 잇고, 매도 후 금액이 있으면 기준일에 점이다(두 축의 범위가 같은 비율로 맞아 일시금의 두 선이
 * 겹친다). `valueLine`에 없는 날은 그 점만 비운다(앞 값으로 메우지 않는다). 키가 없으면(014 전 응답의 대역) 왼쪽 축도 선도 없다.
 *
 * **두 지점 확대**(014 반복 2026-10-11b — FR-037): 차트 칸을 두 번 누르면 그 사이로, 오른쪽 위 [리셋]은 처음 범위로(`useChartZoom`).
 * 누른 날짜는 커서 추적(`time`)이 준다 — 그릴 때 새 API를 부르지 않는다.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { ChartZoomControls } from "@/components/ChartZoomControls";
import { useChartZoom } from "@/hooks/useChartZoom";
import { placeHover } from "@/lib/chartHover";
import { axisPriceFormat, splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import { themedChartOptions } from "@/lib/chartTheme";
import { formatMoneyWithSymbol, formatPercent } from "@/lib/format";
import type { ComparisonBlock, DecimalString, SimulationPoint, SimulationSeriesResponse } from "@/lib/types";
import { useThemeStore, type Theme } from "@/stores/themeStore";

export interface CompareChartItem {
  key: string;
  name: string;
  series: SimulationSeriesResponse;
  lineEnd: ComparisonBlock["lineEnd"];
  /** 014 반복 2026-10-11b — 현재 가치 선(비교 블록 그대로). 없으면 왼쪽 축·가는 선을 그리지 않는다. */
  valueLine?: ComparisonBlock["valueLine"];
  /** 기준일의 현재 가치(비교 표의 그 칸) — 가는 선을 기준일까지 잇는 값. */
  currentValue?: DecimalString | null;
}

/** 대상 10개를 가를 색 — 서로 다른 색상(hue)으로 고른다. */
const PALETTE: readonly [number, number, number][] = [
  [37, 99, 235], [220, 38, 38], [22, 163, 74], [217, 119, 6], [147, 51, 234],
  [8, 145, 178], [219, 39, 119], [101, 163, 13], [79, 70, 229], [120, 113, 108],
];
/**
 * 블랙 배경의 같은 색상 — 위 팔레트의 밝은 쪽(400 계열). 014 T154 실측 — 밝은 바탕용 색은 어두운 바탕에서 범례 글자 대비가 3.72였다
 * (SC-015 4.5:1). 범례·커서 상자 글자와 선이 같은 색이어야 짝이 맞으므로 선도 이 색이다. 밝은 배경은 위 팔레트 그대로다(FR-026).
 */
const DARK_PALETTE: readonly [number, number, number][] = [
  [96, 165, 250], [248, 113, 113], [74, 222, 128], [251, 191, 36], [192, 132, 252],
  [34, 211, 238], [244, 114, 182], [163, 230, 53], [129, 140, 248], [168, 162, 158],
];
const paletteOf = (theme: Theme) => (theme === "dark" ? DARK_PALETTE : PALETTE);
/** 선 모양 — 라이브러리의 `LineStyle` 값(0 실선, 2 점선). 열거형을 실행 중에 읽지 않는다. */
const SOLID = 0;
const DASHED = 2;
/** 014 반복 2026-10-11b — 현재 가치는 왼쪽 축이다(수익률은 오른쪽 — 라이브러리 기본). */
const VALUE_AXIS = "left";

const rgb = ([r, g, b]: readonly number[], alpha = 1) => (alpha === 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`);
export const colorOf = (index: number, theme: Theme = "light") => {
  const palette = paletteOf(theme);
  return rgb(palette[index % palette.length]);
};
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
const moneyValue = (value: string) => toPerformanceData([{ date: "", balance: value, returnRate: "0" }], "balance")[0].value;
const won = (value: string | null | undefined) => (value === null || value === undefined ? null : formatMoneyWithSymbol(value, "KRW"));

/** 구간의 점을 그 날의 현재 가치로 — `valueLine`에 없는 날은 뺀다(앞 값으로 메우지 않는다). */
function valueData(part: SimulationPoint[], values: Map<string, string>) {
  const known = part.flatMap((p) => {
    const value = values.get(p.date);
    return value === undefined ? [] : [{ ...p, balance: value }];
  });
  return toPerformanceData(known, "balance").map((d) => ({ time: d.time, value: d.value }));
}

interface Hover {
  date: string;
  client: { x: number; y: number } | null;
  point: { x: number; y: number };
}

function hoverLine(item: CompareChartItem, date: string): string {
  // 014 반복 2026-10-11b — 현재 가치가 있으면 금액을 덧붙인다(표와 같은 형식). 없으면 014 전과 같은 글자다.
  const line = item.valueLine;
  if (date === item.lineEnd.date && item.lineEnd.holdingReturnRate !== null) {
    const after = item.lineEnd.afterSaleReturnRate;
    const holdingValue = line === undefined ? null : won(item.currentValue);
    const afterValue = line === undefined ? null : won(line.afterSaleValue);
    return `${item.name} 보유 중 ${formatPercent(item.lineEnd.holdingReturnRate)}`
      + (holdingValue === null ? "" : ` (${holdingValue})`)
      + (after === null ? "" : ` · 매도 후 ${formatPercent(after)}${afterValue === null ? "" : ` (${afterValue})`}`);
  }
  const point = item.series.points.find((p) => p.date === date);
  if (point === undefined) return `${item.name} 값 없음`;
  const value = won(line?.points.find((v) => v.date === date)?.value);
  return `${item.name} ${formatPercent(point.returnRate)}${value === null ? "" : ` · ${value}`}`;
}

export function CompareReturnChart({ items }: { items: CompareChartItem[] }) {
  const container = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  // 014 반복 2026-10-10c — 블랙 테마면 어두운 팔레트로 다시 만든다(밝으면 선택 값 그대로). 대상 색은 두 바탕에서 다 보인다
  const theme = useThemeStore((s) => s.theme);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  const zoom = useChartZoom();
  const { attach: attachZoom, detach: detachZoom, track: trackZoom } = zoom;
  const hasValue = items.some((item) => item.valueLine !== undefined);

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
    const withValue = items.some((item) => item.valueLine !== undefined);
    const instance = createChart(container.current, themedChartOptions({
      height: 360,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      // 014 반복 2026-10-11b — 현재 가치가 있을 때만 왼쪽 축을 켠다(없으면 014 전과 같은 옵션).
      ...(withValue ? { leftPriceScale: { visible: true, borderVisible: false } } : {}),
      timeScale: { borderVisible: false },
    }, theme));
    attachZoom(instance);
    const priceFormat = axisPriceFormat(2);
    const valueFormat = axisPriceFormat(0);
    const line = (color: string, lineStyle: number) => instance.addSeries(LineSeries, {
      color, lineWidth: 2, lineStyle, priceFormat, priceLineVisible: false, lastValueVisible: false,
    });
    const valueSeries = (color: string, lineStyle: number) => instance.addSeries(LineSeries, {
      color, lineWidth: 1, lineStyle, priceScaleId: VALUE_AXIS, priceFormat: valueFormat,
      priceLineVisible: false, lastValueVisible: false,
    });

    items.forEach((item, index) => {
      const palette = paletteOf(theme);
      const base = palette[index % palette.length];
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

      // 014 반복 2026-10-11b — 현재 가치 가는 선(왼쪽 축). 수익률 선과 같은 구간·같은 잠정 경계로 나눈다.
      const valueLine = item.valueLine;
      if (valueLine === undefined) return;
      const values = new Map(valueLine.points.map((v) => [v.date, v.value]));
      for (const segment of splitSeriesAtGaps(item.series.points, item.series.gaps)) {
        const [confirmed, provisional] = splitProvisional(segment, item.series.provisionalFrom);
        for (const [part, alpha] of [[confirmed, 1], [provisional, 0.4]] as const) {
          const data = valueData(part, values);
          if (data.length > 0) valueSeries(rgb(base, alpha), lineStyle).setData(data);
        }
      }
      const lastValue = last === null ? undefined : values.get(last.date);
      if (last !== null && last.date < date && lastValue !== undefined
        && item.currentValue !== null && item.currentValue !== undefined) {
        valueSeries(rgb(base), lineStyle).setData([
          { time: last.date, value: moneyValue(lastValue) },
          { time: date, value: moneyValue(item.currentValue) },
        ]);
      }
      if (valueLine.afterSaleValue !== null) {
        instance.addSeries(LineSeries, {
          color: rgb(base), lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 3, priceScaleId: VALUE_AXIS,
          priceFormat: valueFormat, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        }).setData([{ time: date, value: moneyValue(valueLine.afterSaleValue) }]);
      }
    });

    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      const point = param.point;
      const source = param.sourceEvent;
      trackZoom(point === undefined ? undefined : time);
      setHover(time === undefined || point === undefined ? null : {
        date: time, point: { x: point.x, y: point.y },
        client: source === undefined || source === null ? null : { x: source.clientX, y: source.clientY },
      });
    });
    instance.timeScale().fitContent();
    return () => {
      instance.remove();
      // 다시 만든 차트는 처음 범위다 — 확대 단추가 남으면 확대된 것처럼 보인다(FR-037).
      detachZoom();
    };
  }, [items, theme, attachZoom, detachZoom, trackZoom]);

  return (
    <section className="rounded-lg border border-gray-200 p-4" data-testid="compare-chart">
      <h3 className="mb-1 text-sm font-semibold">수익률 추이 (KRW)</h3>
      <p data-testid="compare-basis" className="mb-2 text-xs text-gray-500">선: 보유 중(매도 전) · 끝 점: 매도 후</p>
      {hasValue && (
        <p data-testid="compare-axes" className="mb-2 text-xs text-gray-500">
          굵은 선 수익률(오른쪽 축, %) · 가는 선 현재 가치(왼쪽 축, KRW)
        </p>
      )}
      <div ref={area} className="relative">
        <div ref={container} data-testid="compare-canvas" {...zoom.surface} />
        <ChartZoomControls state={zoom.state} onCancel={zoom.cancel} onReset={zoom.reset} />
        {hover && (
          <div ref={box} role="tooltip" data-testid="compare-hover"
            className="pointer-events-none absolute z-10 rounded border border-gray-200 bg-white/95 px-3 py-2 text-xs shadow-md"
            style={place === null ? { left: 0, top: 0, visibility: "hidden" } : { left: place.left, top: place.top }}>
            <p className="mb-1 font-medium text-gray-700">{hover.date}</p>
            <ul className="space-y-0.5 whitespace-nowrap">
              {items.map((item, index) => (
                <li key={item.key} style={{ color: colorOf(index, theme) }}>{hoverLine(item, hover.date)}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <p data-testid="compare-legend" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {items.map((item, index) => (
          <span key={item.key} style={{ color: colorOf(index, theme) }}>
            {lineStyleOf(index) === SOLID ? "━" : "┅"} {item.name}
          </span>
        ))}
      </p>
    </section>
  );
}
