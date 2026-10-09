"use client";

/**
 * 투자 시뮬레이션 모달의 성과 추이 칸 (013 반복 2026-10-09b T102) — 메뉴 화면의 "성과 추이" 칸과 같다: 제목, 차트(`PerformanceChart`), 시계열만 실패하면
 * 차트 자리에 까닭(패널·표는 남는다 — 차트가 빈 것과 결과가 없는 것은 다른 사건이다).
 */
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationSeriesResponse } from "@/lib/types";

export function ChartSection({ series, error }: { series: SimulationSeriesResponse | null; error: string | null }) {
  return (
    <section data-testid="simulation-modal-chart">
      <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
      {error !== null ? (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</p>
      ) : (
        <PerformanceChart series={series} collecting={null} loading={series === null} />
      )}
    </section>
  );
}
