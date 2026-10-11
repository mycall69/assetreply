"use client";

/**
 * 환율 추이 차트 (T081, T083, T084) — contracts/ui-chart.md, ui-sketches S3.
 *
 * **미수집 구간에서 시리즈를 분리한다.** Lightweight Charts는 포인트 사이를 직선으로
 * 잇기 때문에, 값을 넣지 않는 것만으로는 아직 받지 않은 구간이 채워진 것처럼 보인다
 * (헌법 원칙 V, FR-032). 휴장일은 값이 존재하지 않는 날이므로 이어 그린다.
 *
 * 툴팁은 원본 문자열을 표시한다 — 렌더링용 `number` 변환값을 보여주면 정밀도가 손실된
 * 값을 사용자가 보게 된다.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi } from "lightweight-charts";
import { ChartZoomControls } from "@/components/ChartZoomControls";
import { useChartZoom } from "@/hooks/useChartZoom";
import { useZoomDetail } from "@/hooks/useZoomDetail";
import { withDetail } from "@/lib/chartDetail";
import type { ZoomRange } from "@/lib/chartZoom";
import { ink, themedChartOptions } from "@/lib/chartTheme";
import { splitSeriesAtGaps, toChartData } from "@/lib/chartSeries";
import { formatRate, unitLabel } from "@/lib/format";
import type { SeriesResponse } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";

interface Hover {
  date: string;
  raw: string;
}

export function FxChart({
  data,
  onSelectDate,
  loadDetail,
}: {
  data: SeriesResponse;
  onSelectDate?: (date: string) => void;
  /** 014 반복 2026-10-11c — 확대 구간의 고시일 전부(받은 자료가 줄여졌을 때만 — `TrendChart`가 넘긴다). */
  loadDetail?: (range: ZoomRange) => Promise<SeriesResponse>;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  // 014 반복 2026-10-10c — 블랙 테마면 어두운 팔레트로 다시 만든다(밝으면 선택 값 그대로)
  const theme = useThemeStore((s) => s.theme);
  // 014 반복 2026-10-11c(FR-039) — 두 지점 확대·리셋. 줄여진 긴 기간이면 확대 구간의 고시일 전부를 받아 끼운다(FR-038).
  const zoomDetail = useZoomDetail(data, theme, loadDetail);
  const detail = zoomDetail.detail;
  const shown = useMemo(() => (detail === null ? data : withDetail(data, detail.data, detail.range)), [data, detail]);
  const zoom = useChartZoom({ onZoom: zoomDetail.onZoom, onReset: zoomDetail.onReset });
  const { attach: attachZoom, release: releaseZoom, clear: clearZoom, track: trackZoom } = zoom;

  useEffect(() => {
    if (!container.current) return;

    const instance = createChart(container.current, themedChartOptions({
      height: 360,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    }, theme));
    chart.current = instance;
    attachZoom(instance);

    // 구간마다 별도 시리즈 — 미수집 구간이 선으로 이어지지 않게 한다
    const lookup = new Map<string, string>();
    for (const segment of splitSeriesAtGaps(shown.points, shown.gaps)) {
      const series = instance.addSeries(LineSeries, {
        color: ink("#1f2937", theme),
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
      trackZoom(param.point === undefined ? undefined : time);
      setHover(time && raw ? { date: time, raw } : null);
    });

    // 받은 자료로 다시 그렸으면 확대 범위를 지킨다(FR-038) — 아니면 처음 범위.
    if (detail !== null) instance.timeScale().setVisibleRange(detail.range);
    else instance.timeScale().fitContent();
    return () => {
      instance.remove();
      chart.current = null;
      releaseZoom();
    };
  }, [shown, detail, theme, attachZoom, releaseZoom, trackZoom]);

  // 다른 통화·기간·테마로 다시 그리면 처음 범위다(FR-037).
  useEffect(() => () => clearZoom(), [data, theme, clearZoom]);

  // 휴장일 구간 수는 세지 않는다. 이어 그리는 구간을 "없음"이라 부르면 화면과 말이
  // 어긋난다 — 선은 이어져 있는데 범례는 비었다고 말하게 된다 (T124).
  const notCollected = data.gaps.filter((g) => g.reason === "not_collected").length;

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div className="relative">
        <div ref={container} data-testid="chart-canvas" {...zoom.surface} />
        <ChartZoomControls state={zoom.state} onCancel={zoom.cancel} onReset={zoom.reset}
          right={zoom.controlsRight} note={zoomDetail.note} />
      </div>

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
