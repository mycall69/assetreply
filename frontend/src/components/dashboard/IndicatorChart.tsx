"use client";

/**
 * 지표 추이 그래프 (014 T060) — FR-011~FR-014, contracts D3, research R14-12.
 *
 * - **결측 `gaps` 구간마다 선을 나눈다**(`lib/chartSeries.splitSeriesAtGaps`) — 이어 그리면 그 기간에 값이 움직이지 않은 것처럼 보인다.
 *   휴장은 `gaps`에 없어 선이 이어진다(원칙 V)
 * - 잠정 점(오늘·끝나지 않은 기간·외환 잠정 고시)은 연한 색 선이다 — 앞의 확정 점에서 이어 확정 선과 섞이지 않게 한다
 * - 단위의 전체 기간을 받는다. 처음 보이는 범위만 단위마다 다르다(일 1년 ≈ 250점, 주 5년 ≈ 260점, 월 20년 ≈ 240점, 년 전체) —
 *   끌기·확대로 전체를 본다. 라이브러리는 보이는 범위만 그린다(plan Complexity Tracking — 원칙 VII 해석)
 * - 커서 상자는 서버 문자열에 형식만 입힌다. 숫자 변환은 그리기 전용이고 `lib/chartSeries.toChartData` 안에 있다(원칙 VI)
 *
 * 새 부품이다 — `FxChart`·`PerformanceChart`를 고치지 않는다. 그 차트들의 테스트 모의에는 `setVisibleLogicalRange`가 없다.
 */
import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { splitSeriesAtGaps, toChartData } from "@/lib/chartSeries";
import { formatRate } from "@/lib/format";
import type { IndicatorPoint, IndicatorSeriesResponse, IndicatorUnit } from "@/lib/types";

const SOLID = "#1f2937";
const LIGHT = "#9ca3af";

/** 처음 보이는 점 수 — 년은 전체. */
const INITIAL_SPAN: Record<IndicatorUnit, number | null> = {
  daily: 250,
  weekly: 260,
  monthly: 240,
  yearly: null,
};

const asSeriesPoints = (points: IndicatorPoint[]) => points.map((p) => ({ date: p.date, baseRate: p.value }));

/** 확정 구간과 잠정 구간. 잠정 구간은 바로 앞의 확정 점에서 잇는다. */
function split(points: IndicatorPoint[]): { solid: IndicatorPoint[]; light: IndicatorPoint[] } {
  const first = points.findIndex((p) => p.provisional);
  if (first < 0) return { solid: points, light: [] };
  return { solid: points.slice(0, first), light: points.slice(Math.max(0, first - 1)) };
}

function flags(point: IndicatorPoint): string[] {
  const out: string[] = [];
  if (point.shifted) out.push("📅 옮김");
  if (point.ongoing) out.push("⏳ 끝나지 않은 구간");
  if (point.provisional) out.push("⏳ 잠정");
  return out;
}

export function IndicatorChart({ series }: { series: IndicatorSeriesResponse }) {
  const container = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<IndicatorPoint | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, {
      height: 380,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const { solid, light } = split(series.points);
    for (const segment of splitSeriesAtGaps(solid, series.gaps)) {
      const line = instance.addSeries(LineSeries, {
        color: SOLID, lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
      });
      line.setData(toChartData(asSeriesPoints(segment)).map((d) => ({ time: d.time, value: d.value })));
    }
    if (light.length > 0) {
      const line = instance.addSeries(LineSeries, {
        color: LIGHT, lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
      });
      line.setData(toChartData(asSeriesPoints(light)).map((d) => ({ time: d.time, value: d.value })));
    }
    const byDate = new Map(series.points.map((p) => [p.date, p]));
    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      setHover(time ? byDate.get(time) ?? null : null);
    });
    const span = INITIAL_SPAN[series.unit];
    const count = series.points.length;
    if (span !== null && count > span) {
      instance.timeScale().setVisibleLogicalRange({ from: count - span, to: count - 1 });
    } else {
      instance.timeScale().fitContent();
    }
    return () => instance.remove();
  }, [series]);

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div ref={container} data-testid="indicator-canvas" />
      {hover && (
        <div data-testid="indicator-tooltip"
          className="mt-3 inline-flex flex-wrap items-center gap-3 rounded border border-gray-200 px-3 py-2 text-sm">
          <span className="text-gray-500">{hover.date}</span>
          <span className="tabular-nums font-medium">{formatRate(hover.value)} {series.indicator.unit}</span>
          {flags(hover).map((f) => <span key={f} className="text-xs text-gray-500">{f}</span>)}
        </div>
      )}
      <footer className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
        <span>─ 확정 · ┄ 잠정 · 끊긴 곳은 출처 결측</span>
        <span className="ml-auto">
          {series.downsampled
            ? `표시 ${series.sourcePointCount.toLocaleString()}개 중 ${series.points.length.toLocaleString()}개`
            : `${series.points.length.toLocaleString()}개 전부 표시`}
        </span>
      </footer>
    </section>
  );
}
