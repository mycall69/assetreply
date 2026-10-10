"use client";

/**
 * 비교 차트 (T090) — 005 FR-038~040, SC-015, ui-wireframes W6.
 *
 * **수익률(%)로 겹친다.** 통화가 다른 종목의 잔고를 같은 축에 놓으면 숫자 크기가
 * 달라 한쪽이 평평해지고, 사용자는 그 종목이 움직이지 않았다고 읽는다. 오류는 나지
 * 않는다 — 선이 그려지고 축도 정상이다.
 *
 * **비교 기준을 밝힌다**(FR-039, SC-015). 기준은 응답의 `basisCurrency`다 — 006 FR-068부터 원금
 * 통화와 관계없이 KRW라, 원금 통화가 다른 이력끼리도 그대로 겹칠 수 있다. 원금 통화로 판정하면
 * 기준이 같은데 "다르다"는 틀린 경고가 나온다. 기준이 다르면 그 사실이 드러나야 한다.
 *
 * **수익률 축 눈금에 천 단위 쉼표를 넣는다**(007 FR-046a, 반복 2026-10-04 #2) — `1,881.47`. 성과 추이 차트의 수익률 축과
 * 같은 형식 함수(`axisPriceFormat`)를 쓴다. 이력 항목마다, 결측으로 끊긴 구간마다 시리즈가 따로라 **모든 시리즈에** 준다 —
 * 일부에만 주면 축이 다른 시리즈를 따를 때 쉼표가 빠진다.
 */

import { useEffect, useRef } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { axisPriceFormat, splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import { ink, themedChartOptions } from "@/lib/chartTheme";
import type { SimulationSeriesResponse } from "@/lib/types";
import { useThemeStore } from "@/stores/themeStore";

/** 비교 대상 한 건. `series`는 그 조건으로 **지금 다시 받은** 시계열이다. */
export interface ComparisonItem {
  id: string;
  label: string;
  start: string;
  series: SimulationSeriesResponse;
}

/** 항목마다 다른 색. 같은 색이면 범례로도 어느 선인지 가릴 수 없다. */
const COLORS = ["#1f2937", "#b45309", "#1d4ed8", "#be123c", "#047857"];

function basisText(items: ComparisonItem[]): string {
  const currencies = [...new Set(items.map((i) => i.series.basisCurrency))];
  if (currencies.length <= 1) {
    return `※ 모두 ${currencies[0] ?? ""} 기준 수익률입니다`;
  }
  // 기준 통화가 다르면 각자 다른 환율 변동이 섞여 있다. 같은 잣대로 읽으면 안 된다는
  // 사실이 드러나야 한다 (SC-015).
  return (
    `※ 기준 통화가 다릅니다 (${currencies.join(" · ")}). ` +
    "각 수익률은 그 통화 기준이라 환율 변동이 서로 다르게 섞여 있습니다."
  );
}

export function ComparisonChart({
  items,
  loading,
  error,
}: {
  items: ComparisonItem[];
  loading: boolean;
  error: string | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const drawable = !loading && items.length > 0;
  // 014 반복 2026-10-10c — 블랙 테마면 어두운 팔레트로 다시 만든다(밝으면 선택 값 그대로)
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    if (!container.current || !drawable) return;

    const instance = createChart(container.current, themedChartOptions({
      height: 360,
      layout: { attributionLogo: false },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    }, theme));

    const returnFormat = axisPriceFormat(2);

    items.forEach((item, index) => {
      const color = ink(COLORS[index % COLORS.length], theme);
      // 결측 규칙은 성과 차트와 같다 — 휴장일은 잇고 미수집은 끊는다 (FR-034).
      for (const segment of splitSeriesAtGaps(item.series.points, item.series.gaps)) {
        const line = instance.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          priceFormat: returnFormat,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        line.setData(
          toPerformanceData(segment, "returnRate").map((d) => ({
            time: d.time, value: d.value,
          })),
        );
      }
    });

    instance.timeScale().fitContent();
    return () => {
      instance.remove();
    };
  }, [items, drawable, theme]);

  if (loading) {
    return (
      <p role="status" className="py-12 text-center text-sm text-gray-500">
        비교할 시계열을 불러오는 중…
      </p>
    );
  }

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <h3 className="mb-2 text-sm font-semibold">수익률 비교</h3>

      {error !== null && (
        // 조용히 빠지면 사용자는 그 종목이 비교에서 졌다고 읽는다.
        <p
          role="alert"
          className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          {error}
        </p>
      )}

      <div ref={container} data-testid="comparison-canvas" />

      <footer className="mt-4 space-y-1 text-xs text-gray-500">
        <p data-testid="comparison-legend" className="flex flex-wrap gap-x-4 gap-y-1">
          {items.map((item, index) => (
            <span key={item.id} style={{ color: ink(COLORS[index % COLORS.length], theme) }}>
              {/* FR-040 — 시작일이 다르면 선의 시작점으로도 보이지만 범례에도 적는다. */}
              ─ {item.label} ({item.start} 시작)
            </span>
          ))}
        </p>
        <p data-testid="comparison-basis">{basisText(items)}</p>
      </footer>
    </section>
  );
}
