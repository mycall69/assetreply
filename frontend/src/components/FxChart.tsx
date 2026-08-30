"use client";

/**
 * 환율 추이 차트 (T081, T083, T084) — contracts/ui-chart.md, ui-sketches S3.
 *
 * **결측 구간에서 시리즈를 분리한다.** Lightweight Charts는 포인트 사이를 직선으로
 * 잇기 때문에, 값을 넣지 않는 것만으로는 없는 데이터가 있는 것처럼 보인다
 * (헌법 원칙 V, FR-032).
 *
 * 툴팁은 원본 문자열을 표시한다 — 렌더링용 `number` 변환값을 보여주면 정밀도가 손실된
 * 값을 사용자가 보게 된다.
 */

import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi } from "lightweight-charts";
import { splitSeriesAtGaps, toChartData } from "@/lib/chartSeries";
import { formatRate, unitLabel } from "@/lib/format";
import type { SeriesResponse } from "@/lib/types";

interface Hover {
  date: string;
  raw: string;
}

export function FxChart({
  data,
  onSelectDate,
}: {
  data: SeriesResponse;
  onSelectDate?: (date: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  useEffect(() => {
    if (!container.current) return;

    const instance = createChart(container.current, {
      height: 360,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chart.current = instance;

    // 구간마다 별도 시리즈 — 결측 구간이 선으로 이어지지 않게 한다
    const lookup = new Map<string, string>();
    for (const segment of splitSeriesAtGaps(data.points, data.gaps)) {
      const series = instance.addSeries(LineSeries, {
        color: "#1f2937",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      const chartData = toChartData(segment);
      for (const d of chartData) lookup.set(d.time, d.raw);
      series.setData(chartData.map((d) => ({ time: d.time, value: d.value })));
    }

    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      // 표시 날짜는 **실제 포인트의 날짜**다 (contracts/ui-chart.md)
      const raw = time ? lookup.get(time) : undefined;
      setHover(time && raw ? { date: time, raw } : null);
    });

    instance.timeScale().fitContent();
    return () => {
      instance.remove();
      chart.current = null;
    };
  }, [data]);

  const noQuote = data.gaps.filter((g) => g.reason === "no_quote").length;
  const notCollected = data.gaps.filter((g) => g.reason === "not_collected").length;

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div ref={container} data-testid="chart-canvas" />

      {hover && (
        <div
          data-testid="chart-tooltip"
          className="mt-3 inline-flex items-center gap-4 rounded border border-gray-200 px-3 py-2 text-sm"
        >
          <span className="text-gray-500">{hover.date}</span>
          <span className="tabular-nums font-medium">
            {formatRate(hover.raw)} {unitLabel(data.quoteUnit)}
          </span>
          {onSelectDate && (
            <button
              type="button"
              onClick={() => onSelectDate(hover.date)}
              className="text-gray-600 underline"
            >
              상세 →
            </button>
          )}
        </div>
      )}

      {/* 다운샘플링 사실을 숨기지 않는다 — 사용자가 보는 것이 전수가 아니다 */}
      <footer className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
        {noQuote > 0 && <span>▨ 고시 없음 {noQuote}구간</span>}
        {notCollected > 0 && <span>╌ 미수집 {notCollected}구간</span>}
        <span className="ml-auto">
          {data.downsampled
            ? `표시 ${data.sourcePointCount.toLocaleString()}개 중 ${data.points.length.toLocaleString()}개 (${data.algorithm.toUpperCase()})`
            : `${data.points.length.toLocaleString()}개 전부 표시`}
        </span>
      </footer>
    </section>
  );
}
