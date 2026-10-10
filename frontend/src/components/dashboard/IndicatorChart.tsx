"use client";

/**
 * 지표 추이 그래프 (014 T060 → 반복 2026-10-10b T121) — FR-011~FR-014, FR-028, contracts D3, research R14-12·R14-19.
 *
 * - **보는 기간이 범위다**(반복 2026-10-10b — 012 전의 "단위마다 처음 보이는 점 수"를 대체). 일봉 기간(월 이상)은 그 기간의 일봉 전부를
 *   받아 모두 보인다(`fitContent`) — 주 이상도 일봉이라 촘촘하다. 장중(일·주)은 저장하지 않는 시세이고 점이 모두 잠정이라 연한 선 하나다
 * - 막대 간격 하한을 낮춘다(`MIN_BAR_SPACING`) — 라이브러리 기본(0.5px)이면 1,000px에 2,000점까지만 들어가 S&P "모두"(약 2만 5천 점)가
 *   2019년부터만 보였다(10년도 잘렸다 — T123 실측). 바닥 글자는 "전부 표시"인데 그래프는 일부였다
 * - **결측 `gaps` 구간마다 선을 나눈다**(`lib/chartSeries.splitSeriesAtGaps`) — 이어 그리면 그 기간에 값이 움직이지 않은 것처럼 보인다.
 *   휴장은 `gaps`에 없어 선이 이어진다(원칙 V). 장중의 빈 값은 출처가 주지 않아 점이 없다(선이 이어진다)
 * - 잠정 점(오늘·외환 잠정 고시)은 연한 색 선이다 — 앞의 확정 점에서 이어 확정 선과 섞이지 않게 한다
 * - 커서 상자는 서버 문자열에 형식만 입힌다. 숫자 변환은 그리기 전용이고 `lib/chartSeries`의 `toChartData`·`toIntradayData` 안에 있다(원칙 VI)
 * - 장중 커서 상자는 그 시장의 현지 시각과 한국 시각이다(한국 시장은 하나)
 * - 커서 상자는 그것을 낸 그래프에만 보인다 — 기간을 바꿔도 커서가 움직이지 않으면 옛 기간의 점이 남았다(T123 실측)
 *
 * 새 부품이다 — `FxChart`·`PerformanceChart`를 고치지 않는다.
 */
import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { failureLabel } from "@/components/dashboard/IndicatorHeader";
import { splitSeriesAtGaps, toChartData, toIntradayData, type IntradayDatum } from "@/lib/chartSeries";
import { formatRate } from "@/lib/format";
import { formatZonedDate, formatZonedTime, KST_ZONE } from "@/lib/kstClock";
import type { IndicatorChartSeries, IndicatorIntradayResponse, IndicatorPoint, IndicatorRangeSeries } from "@/lib/types";

const SOLID = "#1f2937";
const LIGHT = "#9ca3af";

/** 막대 간격 하한(px) — 1,000px에 10만 점까지 들어간다(S&P "모두"는 약 2만 5천 점). */
const MIN_BAR_SPACING = 0.01;

const CHART_OPTIONS = {
  height: 380,
  layout: { attributionLogo: false },
  rightPriceScale: { borderVisible: false },
  timeScale: { borderVisible: false, minBarSpacing: MIN_BAR_SPACING },
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

function isIntraday(series: IndicatorChartSeries): series is IndicatorIntradayResponse {
  return "intraday" in series;
}

export function IndicatorChart({ series, onRetry }: { series: IndicatorChartSeries; onRetry?: () => void }) {
  if (!isIntraday(series)) return <DailyChart series={series} />;
  if (series.status === "failed") {
    return (
      <section role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p>장중 시세를 받지 못했습니다 — {failureLabel(series.failure?.reason)}</p>
        {onRetry && <button type="button" onClick={onRetry} className="mt-2 underline">다시 시도</button>}
      </section>
    );
  }
  return <IntradayChart series={series} />;
}

function DailyChart({ series }: { series: IndicatorRangeSeries }) {
  const container = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<{ of: IndicatorRangeSeries; point: IndicatorPoint } | null>(null);
  const hover = hovered?.of === series ? hovered.point : null;

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, CHART_OPTIONS);
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
      const point = time ? byDate.get(time) ?? null : null;
      setHovered(point ? { of: series, point } : null);
    });
    instance.timeScale().fitContent();
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

/** 장중 시각 — 그 시장의 현지 `MM-DD HH:mm`, 현지가 한국이 아니면 한국 시각을 덧붙인다. */
function intradayTime(at: string, timeZone: string): string {
  const local = `${formatZonedDate(at, timeZone)} ${formatZonedTime(at, timeZone)}`;
  return timeZone === KST_ZONE ? local : `${local} (한국 ${formatZonedTime(at, KST_ZONE)})`;
}

function IntradayChart({ series }: { series: IndicatorIntradayResponse }) {
  const container = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<{ of: IndicatorIntradayResponse; point: IntradayDatum } | null>(null);
  const hover = hovered?.of === series ? hovered.point : null;
  const zone = series.indicator.market.timezone;

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, {
      ...CHART_OPTIONS,
      timeScale: { borderVisible: false, minBarSpacing: MIN_BAR_SPACING, timeVisible: true, secondsVisible: false },
    });
    const data = toIntradayData(series.points);
    const line = instance.addSeries(LineSeries, {
      color: LIGHT, lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
    });
    line.setData(data.map((d) => ({ time: d.time as UTCTimestamp, value: d.value })));
    const byTime = new Map(data.map((d) => [d.time, d]));
    instance.subscribeCrosshairMove((param) => {
      const time = param.time as number | undefined;
      const point = time !== undefined ? byTime.get(time) ?? null : null;
      setHovered(point ? { of: series, point } : null);
    });
    instance.timeScale().fitContent();
    return () => instance.remove();
  }, [series]);

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div ref={container} data-testid="indicator-canvas" />
      {hover && (
        <div data-testid="indicator-tooltip"
          className="mt-3 inline-flex flex-wrap items-center gap-3 rounded border border-gray-200 px-3 py-2 text-sm">
          <span className="text-gray-500">{intradayTime(hover.at, zone)}</span>
          <span className="tabular-nums font-medium">{formatRate(hover.raw)} {series.indicator.unit}</span>
          <span className="text-xs text-gray-500">⏳ 잠정</span>
        </div>
      )}
      <footer className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
        <span>┄ 장중 잠정 — 저장하지 않는 시세</span>
        {series.notes.includes("market_fx") && <span>시장 환율 — 고시 이력과 다른 계열</span>}
        <span className="ml-auto">{series.points.length.toLocaleString()}개 점</span>
      </footer>
    </section>
  );
}
