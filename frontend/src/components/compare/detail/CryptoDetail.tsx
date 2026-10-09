"use client";

/**
 * 투자 시뮬레이션 모달 — 가상자산 (013 반복 2026-10-09b T102) — spec FR-011b, ui-wireframes F10.
 *
 * 가상자산 메뉴 화면(`app/crypto/page.tsx`)의 결과 칸과 같은 부품·같은 속성이다 — 일시금은 `PerformanceBoard`(안내 줄 `cryptoBoardNotes` — 메뉴와 같은
 * 함수)·`PerformanceChart`·`CryptoPerformanceTable`, 적립식은 `RecurringBoard`·`PerformanceChart`·`RecurringCryptoTable`.
 */
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { PeriodTableSection } from "@/components/period/PeriodTableSection";
import { RecurringBoard } from "@/components/recurring/RecurringBoard";
import { RecurringCryptoTable } from "@/components/recurring/RecurringCryptoTable";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { cryptoBoardNotes } from "@/lib/boardNotes";
import { CRYPTO_PERIOD_TITLES } from "@/lib/tablePeriod";
import type { CryptoSimulationResponse, RecurringCryptoResponse } from "@/lib/types";
import type { DetailState } from "@/stores/compareDetailStore";
import { ChartSection } from "./ChartSection";

export function CryptoDetail({ menu, recurring, principalCurrency, state }: {
  menu: CryptoSimulationResponse | RecurringCryptoResponse;
  recurring: boolean;
  principalCurrency: string;
  state: DetailState;
}) {
  const quote = menu.coin.currency;
  const table = (children: React.ReactNode) => (
    <div data-testid="simulation-modal-table">
      <PeriodTableSection period={state.period} titles={CRYPTO_PERIOD_TITLES} onPeriod={(p) => void state.setPeriod(p)}
        loading={state.tableLoading} error={state.tableError}>
        {children}
      </PeriodTableSection>
    </div>
  );
  if (recurring) {
    const body = menu as RecurringCryptoResponse;
    return (
      <>
        <div data-testid="simulation-modal-board">
          <RecurringBoard asset="crypto" summary={body.summary} principalCurrency={principalCurrency} quoteCurrency={quote} />
        </div>
        <ChartSection series={state.series} error={state.seriesError} />
        {table(
          <RecurringCryptoTable rows={body.rows} principalCurrency={principalCurrency} quoteCurrency={quote}
            hasMore={body.hasMore} loadingMore={state.loadingMore} loadError={state.loadMoreError}
            onLoadMore={() => void state.loadMore()} period={state.period} />,
        )}
      </>
    );
  }
  const lump = menu as CryptoSimulationResponse;
  return (
    <>
      <div data-testid="simulation-modal-board">
        <PerformanceBoard summary={lump.summary} currency={principalCurrency} exchange={lump.exchange ?? undefined}
          notes={cryptoBoardNotes(lump.summary, lump.condition)} />
      </div>
      <ChartSection series={state.series} error={state.seriesError} />
      {table(
        <CryptoPerformanceTable rows={lump.rows} currency={principalCurrency} quoteCurrency={quote} summary={lump.summary}
          hasMore={lump.hasMore} loadingMore={state.loadingMore} loadError={state.loadMoreError}
          onLoadMore={() => void state.loadMore()} period={state.period} />,
      )}
    </>
  );
}
