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
 * - 장중 커서 상자는 그 시장의 현지 시각과 한국 시각이다(한국 시장은 하나). 시간 축 눈금·커서 시각 글자도 그 시장의 현지 시각이다 —
 *   라이브러리 기본(UTC)이면 항셍 장중 축이 "05:00"처럼 보였다(T123 실측)
 * - 커서 상자는 그것을 낸 그래프에만 보인다 — 기간을 바꿔도 커서가 움직이지 않으면 옛 기간의 점이 남았다(T123 실측)
 *
 * - (반복 2026-10-10c) 기간은 **처음 보이는 범위**다(R14-22) — 일봉 본문은 저장된 일봉 전부이고 `windows[range]` 이상 첫 점의 차례 ~ 마지막
 *   차례를 `setVisibleLogicalRange`로 놓는다(차례라 휴장을 건너 같은 폭이다). 왼쪽으로 끌면 첫 날까지 보인다. 기간을 바꾸면 그래프를 다시
 *   만들지 않고 범위만 바꾼다. 창 안에 점이 없으면 마지막 30점, 창이 없으면(모두) 전부다
 * - (반복 2026-10-10c) 장중은 받은 점 전부(일 5세션·주 1개월)를 그리고 `window`로 처음 범위를 놓는다. 선은 확정 선과 같은 진한 **실선**이다 —
 *   잠정은 커서 상자의 ⏳ 잠정과 범례로 밝힌다(명확화 2026-10-10c)
 * - (반복 2026-10-10c) 블랙 테마면 `lib/chartTheme`의 팔레트로 다시 만든다(배경·글자·격자·진한 회색 선)
 *
 * 새 부품이다 — `FxChart`·`PerformanceChart`를 고치지 않는다.
 */
import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi, type Time, type TickMarkType, type UTCTimestamp } from "lightweight-charts";
import { failureLabel } from "@/components/dashboard/IndicatorHeader";
import { RANGE_LABELS } from "@/components/dashboard/RangePicker";
import { ink, themedChartOptions } from "@/lib/chartTheme";
import { splitSeriesAtGaps, toChartData, toIntradayData, type IntradayDatum } from "@/lib/chartSeries";
import { formatRate } from "@/lib/format";
import { formatZonedDate, formatZonedDay, formatZonedTime, KST_ZONE } from "@/lib/kstClock";
import type {
  DailyRange, IndicatorChartSeries, IndicatorIntradayResponse, IndicatorPoint, IndicatorRange, IndicatorRangeSeries,
} from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";

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

/** 창 안에 점이 없을 때(오래 멈춘 지표) 보이는 마지막 점 수. */
const STALE_SPAN = 30;

const asSeriesPoints = (points: IndicatorPoint[]) => points.map((p) => ({ date: p.date, baseRate: p.value }));

/**
 * 처음 보이는 범위 — 창 시작 이상 첫 점의 차례 ~ 마지막 차례. 창이 없으면 전부를 맞춘다. 창 안에 점이 없으면 마지막 30점이다.
 * `keys`는 점의 시각 글자(일봉 날짜·장중 ISO)이고 차례대로다 — 글자로 견준다(날짜·ISO는 사전 차례가 시간 차례다).
 */
function showWindow(instance: IChartApi, keys: string[], start: string | null | undefined) {
  if (start === null || start === undefined || keys.length === 0) {
    instance.timeScale().fitContent();
    return;
  }
  const first = keys.findIndex((key) => key >= start);
  const last = keys.length - 1;
  instance.timeScale().setVisibleLogicalRange({ from: first < 0 ? Math.max(0, keys.length - STALE_SPAN) : first, to: last });
}

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

export function IndicatorChart({ series, range, onRetry }: {
  series: IndicatorChartSeries;
  /** 고른 기간 — 일봉 본문은 기간마다 같고 처음 보이는 범위만 다르다(반복 2026-10-10c). */
  range: IndicatorRange;
  onRetry?: () => void;
}) {
  if (!isIntraday(series)) return <DailyChart series={series} range={range} />;
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

function DailyChart({ series, range }: { series: IndicatorRangeSeries; range: IndicatorRange }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const theme = useThemeStore((s) => s.theme);
  const [hovered, setHovered] = useState<{ of: IndicatorRangeSeries; point: IndicatorPoint } | null>(null);
  const hover = hovered?.of === series ? hovered.point : null;

  // 그래프는 본문·테마가 바뀔 때만 다시 만든다 — 기간(처음 범위)은 아래 효과가 범위만 바꾼다
  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, themedChartOptions(CHART_OPTIONS, theme));
    const { solid, light } = split(series.points);
    for (const segment of splitSeriesAtGaps(solid, series.gaps)) {
      const line = instance.addSeries(LineSeries, {
        color: ink(SOLID, theme), lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
      });
      line.setData(toChartData(asSeriesPoints(segment)).map((d) => ({ time: d.time, value: d.value })));
    }
    if (light.length > 0) {
      const line = instance.addSeries(LineSeries, {
        color: ink(LIGHT, theme), lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
      });
      line.setData(toChartData(asSeriesPoints(light)).map((d) => ({ time: d.time, value: d.value })));
    }
    const byDate = new Map(series.points.map((p) => [p.date, p]));
    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      const point = time ? byDate.get(time) ?? null : null;
      setHovered(point ? { of: series, point } : null);
    });
    chart.current = instance;
    return () => {
      instance.remove();
      chart.current = null;
    };
  }, [series, theme]);

  // 처음 보이는 범위 — 만든 뒤(같은 커밋에서 위 효과 다음)와 기간이 바뀔 때
  useEffect(() => {
    if (chart.current === null) return;
    const start = range === "1d" || range === "5d" ? null : series.windows?.[range as DailyRange];
    showWindow(chart.current, series.points.map((p) => p.date), start);
  }, [series, theme, range]);

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
        <span>─ 확정 · ┄ 잠정 · 끊긴 곳은 출처 결측 · ← 끌면 앞 구간</span>
        <span className="ml-auto">
          {series.downsampled
            ? `표시 ${series.sourcePointCount.toLocaleString()}개 중 ${series.points.length.toLocaleString()}개`
            : `전체 ${series.points.length.toLocaleString()}개`}
          {` · 처음 ${RANGE_LABELS[range]}`}
        </span>
      </footer>
    </section>
  );
}

/** 라이브러리 시각(초 단위 UTC) → ISO 글자. */
const isoOf = (time: Time) => new Date((time as number) * 1000).toISOString();

/**
 * 장중 시간 축 눈금 — 그 시장의 현지 시각. 종류는 라이브러리 `TickMarkType`의 값이다(0 해·1 달·2 날·3 시각·4 초까지) — 열거형을
 * 실행 중에 쓰지 않는다(차트 테스트의 모의에 없다 — 010 주의).
 */
function intradayTick(time: Time, kind: TickMarkType, timeZone: string): string {
  const iso = isoOf(time);
  const [year, month, day] = formatZonedDay(iso, timeZone).split("-");
  if (kind === 0) return `${year}년`;
  if (kind === 1) return `${month.replace(/^0/, "")}월`;
  if (kind === 2) return `${day.replace(/^0/, "")}일`;
  return formatZonedTime(iso, timeZone);
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
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, themedChartOptions({
      ...CHART_OPTIONS,
      timeScale: {
        borderVisible: false, minBarSpacing: MIN_BAR_SPACING, timeVisible: true, secondsVisible: false,
        tickMarkFormatter: (time: Time, kind: TickMarkType) => intradayTick(time, kind, zone),
      },
      localization: {
        timeFormatter: (time: Time) => `${formatZonedDate(isoOf(time), zone)} ${formatZonedTime(isoOf(time), zone)}`,
      },
    }, theme));
    const data = toIntradayData(series.points);
    // 확정 선과 같은 진한 실선(명확화 2026-10-10c) — 점이 모두 잠정인 것은 커서 상자·범례가 밝힌다
    const line = instance.addSeries(LineSeries, {
      color: ink(SOLID, theme), lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
    });
    line.setData(data.map((d) => ({ time: d.time as UTCTimestamp, value: d.value })));
    const byTime = new Map(data.map((d) => [d.time, d]));
    instance.subscribeCrosshairMove((param) => {
      const time = param.time as number | undefined;
      const point = time !== undefined ? byTime.get(time) ?? null : null;
      setHovered(point ? { of: series, point } : null);
    });
    // 처음 보이는 범위는 마지막 세션(일)·최근 5세션(주) — 왼쪽으로 끌면 앞 세션
    showWindow(instance, data.map((d) => d.at), series.window?.from);
    return () => instance.remove();
  }, [series, zone, theme]);

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
        <span>─ 장중 — 모두 잠정(⏳) · 저장하지 않는 시세 · ← 끌면 앞 세션</span>
        {series.notes.includes("market_fx") && <span>시장 환율 — 고시 이력과 다른 계열</span>}
        <span className="ml-auto">{series.points.length.toLocaleString()}개 점</span>
      </footer>
    </section>
  );
}
