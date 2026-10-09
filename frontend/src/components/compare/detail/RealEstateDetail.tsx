"use client";

/**
 * 투자 시뮬레이션 모달 — 부동산 (013 반복 2026-10-09b T102) — spec FR-011b, ui-wireframes F10.
 *
 * 부동산 메뉴 화면(`app/realestate/page.tsx`)의 결과 칸과 같은 부품·같은 속성이다 — `RealEstateBoard`(취득 비용 포함 — 메뉴 응답의 `complex`·`area`·
 * `condition`·`acquisition`·`summary`를 그대로)·`RealEstateNotice`·`PerformanceChart`·`RealEstatePerformanceTable`(월별).
 */
import { RealEstateBoard } from "@/components/realestate/RealEstateBoard";
import { RealEstateNotice } from "@/components/realestate/RealEstateNotice";
import { RealEstatePerformanceTable } from "@/components/realestate/RealEstatePerformanceTable";
import type { RealEstateSimulationResponse } from "@/lib/types";
import type { DetailState } from "@/stores/compareDetailStore";
import { ChartSection } from "./ChartSection";

export function RealEstateDetail({ menu, state }: { menu: RealEstateSimulationResponse; state: DetailState }) {
  const { complex, area, condition, acquisition, summary, rows } = menu;
  return (
    <>
      <div data-testid="simulation-modal-board" className="space-y-2">
        <RealEstateBoard result={{ complex, area, condition, acquisition, summary }} />
        <RealEstateNotice summary={summary} />
      </div>
      <ChartSection series={state.series} error={state.seriesError} />
      <section data-testid="simulation-modal-table">
        <h3 className="mb-2 text-sm font-semibold">월별 투자 성과</h3>
        <RealEstatePerformanceTable rows={rows} taxGaps={summary.taxGaps} />
      </section>
    </>
  );
}
