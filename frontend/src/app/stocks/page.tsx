"use client";

/**
 * 주식 투자 시뮬레이션 (T045) — 005 contracts/ui-wireframes.md W1.
 *
 * 경로가 **복수(`stocks`)인 것은 의도된 것이다.** 기존 가드
 * `noUnbuiltAssetRoutes.test.ts`가 그 이름을 전제하므로, 단수로 두면 가드가 실패가
 * 아니라 **통과**한다 — false pass는 실패보다 나쁘다.
 */

import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { PerformanceTable } from "@/components/stock/PerformanceTable";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { SimulationHistory } from "@/components/stock/SimulationHistory";
import { SimulationForm } from "@/components/stock/SimulationForm";
import { StockSearch } from "@/components/stock/StockSearch";
import { useEffect } from "react";
import { useStockStore } from "@/stores/stockStore";

export default function StocksPage() {
  const {
    input, rows, summary, exchange, hasMore, collecting,
    series, seriesError, loading, loadingMore, error, loadMoreError,
    history, historySaveError, selectedHistory, comparison, comparing,
    comparisonError,
    setInput, run, loadMore, refreshIfRan,
    restoreHistory, toggleHistory, removeHistoryEntry, compareSelected,
  } = useStockStore();

  // FR-017 — 설정 화면에 다녀왔을 수 있다. 이미 실행한 결과가 있으면 새 값으로
  // 다시 받는다. 갱신하지 않으면 화면은 정상으로 보이면서 낡은 값을 보여준다.
  useEffect(() => {
    void refreshIfRan();
  }, [refreshIfRan]);

  // FR-037 — 이력은 브라우저에 있다. 서버에서 오지 않으므로 화면이 열릴 때 읽는다.
  useEffect(() => {
    restoreHistory();
  }, [restoreHistory]);

  const currency = input.stock?.currency ?? "KRW";

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">주식 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">
          배당 재투자를 포함한 투자 성과
        </p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <StockSearch
          value={input.stock}
          onSelect={(stock) => setInput({ stock })}
        />
        <SimulationForm
          values={{
            start: input.start,
            principal: input.principal,
            principalCurrency: input.principalCurrency,
            reinvest: input.reinvest,
          }}
          disabled={loading || input.stock === null}
          onChange={(next) => setInput(next)}
          onSubmit={() => void run()}
        />
      </section>

      {error !== null && (
        <p
          role="alert"
          className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {collecting !== null && (
        // FR-047, FR-049 — 진행 상태를 보이되 부분 결과를 보여주지 않는다.
        <p
          role="status"
          className="rounded border border-gray-200 px-4 py-6 text-center text-sm text-gray-600"
        >
          {input.stock?.name ?? "종목"}의 시세를 받고 있습니다. 완료되면 결과가
          표시됩니다.
        </p>
      )}

      {loading && (
        <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>
      )}

      {summary !== null && (
        <PerformanceBoard
          summary={summary}
          currency={input.principalCurrency}
          exchange={exchange ?? undefined}
        />
      )}

      {summary !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
          {seriesError !== null ? (
            // 표는 그대로 둔다 — 차트가 빈 것과 결과가 없는 것은 다른 사건이다.
            <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {seriesError}
            </p>
          ) : (
            <PerformanceChart
              series={series}
              collecting={collecting}
              loading={loading}
            />
          )}
        </section>
      )}

      {summary !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
          <PerformanceTable
            rows={rows}
            currency={input.principalCurrency}
            stockCurrency={currency}
            hasMore={hasMore}
            loadingMore={loadingMore}
            loadError={loadMoreError}
            onLoadMore={() => void loadMore()}
          />
        </section>
      )}

      <SimulationHistory
        entries={history}
        selected={selectedHistory}
        comparing={comparing}
        saveError={historySaveError}
        onToggle={toggleHistory}
        onRemove={removeHistoryEntry}
        onCompare={() => void compareSelected()}
      />

      {(comparing || comparison.length > 0) && (
        <ComparisonChart
          items={comparison}
          loading={comparing}
          error={comparisonError}
        />
      )}
    </div>
  );
}
