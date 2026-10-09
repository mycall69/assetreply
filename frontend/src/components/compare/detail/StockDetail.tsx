"use client";

/**
 * 투자 시뮬레이션 모달 — 주식 (013 반복 2026-10-09b T102) — spec FR-011b, ui-wireframes F10.
 *
 * 주식 메뉴 화면(`app/stocks/page.tsx`)의 결과 칸과 **같은 부품·같은 속성**이다 — 일시금은 `PerformanceBoard`·`PerformanceChart`·`PerformanceTable`,
 * 적립식은 `RecurringBoard`·`PerformanceChart`·`RecurringStockTable`. 일자별 표는 일·주·월과 더 보기(모달 스토어 — 메뉴 스토어와 같은 질의).
 */
import { PeriodTableSection } from "@/components/period/PeriodTableSection";
import { RecurringBoard } from "@/components/recurring/RecurringBoard";
import { RecurringStockTable } from "@/components/recurring/RecurringStockTable";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import { STOCK_PERIOD_TITLES } from "@/lib/tablePeriod";
import type { RecurringStockResponse, SimulationResponse } from "@/lib/types";
import type { DetailState } from "@/stores/compareDetailStore";
import { ChartSection } from "./ChartSection";

export function StockDetail({ menu, recurring, principalCurrency, state }: {
  menu: SimulationResponse | RecurringStockResponse;
  /** 그 줄의 방식이 적립식인가(조건의 `method`). */
  recurring: boolean;
  principalCurrency: string;
  state: DetailState;
}) {
  const currency = menu.stock.currency;
  const table = (children: React.ReactNode) => (
    <div data-testid="simulation-modal-table">
      <PeriodTableSection period={state.period} titles={STOCK_PERIOD_TITLES} onPeriod={(p) => void state.setPeriod(p)}
        loading={state.tableLoading} error={state.tableError}>
        {children}
      </PeriodTableSection>
    </div>
  );
  if (recurring) {
    const body = menu as RecurringStockResponse;
    return (
      <>
        <div data-testid="simulation-modal-board">
          <RecurringBoard asset="stock" summary={body.summary} principalCurrency={principalCurrency} quoteCurrency={currency} />
        </div>
        <ChartSection series={state.series} error={state.seriesError} />
        {table(
          <RecurringStockTable rows={body.rows} principalCurrency={principalCurrency} stockCurrency={currency}
            hasMore={body.hasMore} loadingMore={state.loadingMore} loadError={state.loadMoreError}
            onLoadMore={() => void state.loadMore()} period={state.period} />,
        )}
      </>
    );
  }
  const lump = menu as SimulationResponse;
  return (
    <>
      <div data-testid="simulation-modal-board">
        <PerformanceBoard summary={lump.summary} currency={principalCurrency} exchange={lump.exchange ?? undefined} />
      </div>
      <ChartSection series={state.series} error={state.seriesError} />
      {table(
        <PerformanceTable rows={lump.rows} currency={principalCurrency} stockCurrency={currency} summary={lump.summary}
          hasMore={lump.hasMore} loadingMore={state.loadingMore} loadError={state.loadMoreError}
          onLoadMore={() => void state.loadMore()} period={state.period} />,
      )}
    </>
  );
}
