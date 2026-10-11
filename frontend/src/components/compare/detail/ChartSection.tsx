"use client";

/**
 * 투자 시뮬레이션 모달의 성과 추이 칸 (013 반복 2026-10-09b T102) — 메뉴 화면의 "성과 추이" 칸과 같다: 제목, 차트(`PerformanceChart`), 시계열만 실패하면
 * 차트 자리에 까닭(패널·표는 남는다 — 차트가 빈 것과 결과가 없는 것은 다른 사건이다).
 */
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { menuSeriesPath } from "@/lib/compareApi";
import { seriesDetailLoader } from "@/lib/seriesDetail";
import type { SimulationSeriesResponse } from "@/lib/types";
import type { DetailState } from "@/stores/compareDetailStore";

/** 그 줄의 메뉴 시계열 경로 — 확대 구간의 일 단위 자료를 같은 경로로 받는다(014 반복 2026-10-11c — 주식 늘·가상자산은 줄였을 때만). */
export const detailSeriesPath = (state: Pick<DetailState, "open">) =>
  (state.open === null ? null : menuSeriesPath(state.open.condition, state.open.target));

export function ChartSection({ series, error, path = null }: {
  series: SimulationSeriesResponse | null;
  error: string | null;
  /** 014 반복 2026-10-11c — 그 시계열을 받은 메뉴 경로(주식·가상자산). 없으면 확대만 한다. */
  path?: string | null;
}) {
  return (
    <section data-testid="simulation-modal-chart">
      <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
      {error !== null ? (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p>
      ) : (
        <PerformanceChart series={series} collecting={null} loading={series === null}
          loadDetail={seriesDetailLoader(path, series)} />
      )}
    </section>
  );
}
