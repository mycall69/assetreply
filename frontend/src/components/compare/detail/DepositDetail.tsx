"use client";

/**
 * 투자 시뮬레이션 모달 — 예금 (013 반복 2026-10-09b T102) — spec FR-011b, ui-wireframes F10.
 *
 * 예금 메뉴 화면(`app/deposit/page.tsx`)의 결과 칸과 같은 부품·같은 속성이다 — 정기예금은 `PerformanceBoard`(안내 줄 `depositBoardNotes` — 메뉴와 같은
 * 함수, 계산 끝 안내 없음)·`DepositNotice`·`PerformanceChart`·`DepositPerformanceTable`, 정기 적금은 `InstallmentBoard`·`DepositNotice`·`PerformanceChart`·
 * `InstallmentTable`. 표는 행을 한 번에 받는다(쪽 넘김·단위가 없다 — 메뉴와 같다).
 */
import { DepositNotice } from "@/components/deposit/DepositNotice";
import { DepositPerformanceTable } from "@/components/deposit/DepositPerformanceTable";
import { InstallmentBoard } from "@/components/deposit/InstallmentBoard";
import { InstallmentTable } from "@/components/deposit/InstallmentTable";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { depositBoardNotes } from "@/lib/boardNotes";
import type { DepositSimulationResponse, InstallmentResponse } from "@/lib/types";
import type { DetailState } from "@/stores/compareDetailStore";
import { ChartSection } from "./ChartSection";

export function DepositDetail({ menu, installment, state }: {
  menu: DepositSimulationResponse | InstallmentResponse;
  /** 그 줄의 방식이 정기 적금인가(조건의 `method`). */
  installment: boolean;
  state: DetailState;
}) {
  if (installment) {
    const body = menu as InstallmentResponse;
    return (
      <>
        <div data-testid="simulation-modal-board" className="space-y-2">
          <InstallmentBoard summary={body.summary} institutionName={body.institution.name} taxRate={body.condition.interestTaxRate} />
          <DepositNotice summary={body.summary} start={body.condition.start} />
        </div>
        <ChartSection series={state.series} error={state.seriesError} />
        <section data-testid="simulation-modal-table">
          <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
          <InstallmentTable rows={body.rows} />
        </section>
      </>
    );
  }
  const body = menu as DepositSimulationResponse;
  return (
    <>
      <div data-testid="simulation-modal-board" className="space-y-2">
        <PerformanceBoard summary={body.summary} currency="KRW" notFinalNotice={false}
          notes={depositBoardNotes(body.summary, body.condition, body.institution.name)} />
        <DepositNotice summary={body.summary} start={body.condition.start} />
      </div>
      <ChartSection series={state.series} error={state.seriesError} />
      <section data-testid="simulation-modal-table">
        <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
        <DepositPerformanceTable rows={body.rows} />
      </section>
    </>
  );
}
