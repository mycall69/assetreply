"use client";

/**
 * 금리 추이 그래프 (014 반복 2026-10-11d T209) — FR-041, SC-026, contracts D18, research R14-34.
 *
 * - **계단선**이다 — 결정 사이에는 그 금리가 유지된다(선 옵션 `lineType: 1` — WithSteps). 결정 사이를 사선으로 이으면 금리가 서서히 변한
 *   것처럼 보인다(스크린샷의 사선을 버린 까닭). 라이브러리 열거형을 가져오지 않는다 — 기존 차트 테스트 모의에 없다(CLAUDE.md 010)
 * - 점은 결정일에만 있다(`pointMarkersVisible`) — 날마다의 값을 만들지 않는다(원칙 V). 마지막 결정 뒤 오늘까지의 꼬리를 그리지 않는다
 * - 점 위의 숫자는 넣지 않는다(10년 약 90점이 겹친다) — 커서 상자가 결정일·금리·전회대비다(서버 글자 그대로)
 * - 기간(1년·5년·10년·모두)은 **처음 보이는 범위**다 — 결정 이력 전부를 그려 두고 마지막 결정에서 거꾸로 센 범위만 놓는다(차례로 — 지표
 *   그래프와 같은 `setVisibleLogicalRange`). 왼쪽으로 끌면 저장된 첫 결정까지 보인다. "모두"는 전체
 * - 두 지점 확대·[리셋]은 지표 일봉 그래프(FR-039)와 같다 — [리셋]은 그 기간의 처음 범위, 기간을 바꾸면 확대가 풀린다
 * - 블랙 테마면 `lib/chartTheme`의 팔레트로 다시 만든다. 숫자 변환은 그리기 전용이고 `lib/chartSeries.toChartData` 안에 있다(원칙 VI)
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi } from "lightweight-charts";
import { ChartZoomControls } from "@/components/ChartZoomControls";
import { rateChangeText, rateTone } from "@/components/dashboard/PolicyRateTable";
import { useChartZoom } from "@/hooks/useChartZoom";
import { ink, themedChartOptions } from "@/lib/chartTheme";
import { toChartData } from "@/lib/chartSeries";
import { dottedDate, rateWindowStart } from "@/lib/rateFormat";
import type { PolicyRateDecision, RateRange } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";

const SOLID = "#1f2937";

const CHART_OPTIONS = {
  height: 300,
  layout: { attributionLogo: false },
  rightPriceScale: { borderVisible: false },
  timeScale: { borderVisible: false },
};

/** 처음 보이는 범위 — 창 시작 이상 첫 결정의 차례 ~ 마지막 차례. 창이 없으면 전체, 창 안에 결정이 없으면 마지막 결정 하나. */
function showWindow(instance: IChartApi, keys: string[], start: string | null) {
  if (start === null || keys.length === 0) {
    instance.timeScale().fitContent();
    return;
  }
  const first = keys.findIndex((key) => key >= start);
  const last = keys.length - 1;
  instance.timeScale().setVisibleLogicalRange({ from: first < 0 ? last : first, to: last });
}

export function RateChart({ decisions, range, lastDecidedOn }: {
  /** 최신부터(응답 그대로). */
  decisions: PolicyRateDecision[];
  range: RateRange;
  lastDecidedOn: string | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const theme = useThemeStore((s) => s.theme);
  const [hovered, setHovered] = useState<{ of: PolicyRateDecision[]; decision: PolicyRateDecision } | null>(null);
  const hover = hovered?.of === decisions ? hovered.decision : null;
  // 옛것부터의 결정일 — 그래프 점의 차례(처음 범위를 차례로 놓는다)
  const keys = useMemo(() => [...decisions].reverse().map((d) => d.decidedOn), [decisions]);
  const start = rateWindowStart(range, lastDecidedOn);
  const zoom = useChartZoom({
    resetView: () => {
      if (chart.current !== null) showWindow(chart.current, keys, start);
    },
  });
  const { attach: attachZoom, detach: detachZoom, clear: clearZoom, track: trackZoom } = zoom;

  // 그래프는 결정·테마가 바뀔 때만 다시 만든다 — 기간(처음 범위)은 아래 효과가 범위만 바꾼다
  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, themedChartOptions(CHART_OPTIONS, theme));
    const line = instance.addSeries(LineSeries, {
      color: ink(SOLID, theme), lineWidth: 2, lineType: 1, pointMarkersVisible: true,
      priceLineVisible: false, lastValueVisible: false,
    });
    const points = toChartData(decisions.map((d) => ({ date: d.decidedOn, baseRate: d.rate })));
    line.setData(points.map((p) => ({ time: p.time, value: p.value })));
    const byDate = new Map(decisions.map((d) => [d.decidedOn, d]));
    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      const decision = time ? byDate.get(time) ?? null : null;
      trackZoom(param.point === undefined ? undefined : time);
      setHovered(decision ? { of: decisions, decision } : null);
    });
    chart.current = instance;
    attachZoom(instance);
    return () => {
      instance.remove();
      chart.current = null;
      detachZoom();
    };
  }, [decisions, theme, attachZoom, detachZoom, trackZoom]);

  // 처음 보이는 범위 — 만든 뒤(같은 커밋에서 위 효과 다음)와 기간이 바뀔 때. 기간을 바꾸면 확대가 풀린다.
  useEffect(() => {
    if (chart.current === null) return;
    showWindow(chart.current, keys, start);
    return () => clearZoom();
  }, [keys, start, theme, clearZoom]);

  return (
    <section data-testid="rate-chart" className="rounded-lg border border-gray-200 p-4">
      <div className="relative">
        <div ref={container} data-testid="rate-canvas" {...zoom.surface} />
        <ChartZoomControls state={zoom.state} onCancel={zoom.cancel} onReset={zoom.reset} right={zoom.controlsRight} />
      </div>
      {hover && (
        <div data-testid="rate-tooltip"
          className="mt-3 inline-flex flex-wrap items-center gap-3 rounded border border-gray-200 px-3 py-2 text-sm">
          <span className="text-gray-500">{dottedDate(hover.decidedOn)}</span>
          <span className="font-medium tabular-nums">{hover.rate}%</span>
          <span className={`tabular-nums ${rateTone(hover.direction)}`}>{rateChangeText(hover.change, hover.direction)}</span>
        </div>
      )}
      <footer className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
        <span>─ 결정 사이는 그 금리가 유지된다(계단) · ● 결정 · ← 끌면 앞 결정</span>
        <span className="ml-auto">결정 {decisions.length.toLocaleString()}개</span>
      </footer>
    </section>
  );
}
