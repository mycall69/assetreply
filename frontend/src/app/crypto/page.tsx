"use client";

/**
 * 가상자산 투자 시뮬레이션 (T033) — 007 FR-001, ui-wireframes C1~C7.
 *
 * 주식 화면과 같은 구성이다 — 코인 검색 → 시작일·원금·원금 통화 → 시뮬레이션 → 성과 보드·일자별 표. **배당 재투자 칸이 없다.**
 * 화면 머리에 일봉 기준(UTC 하루)을 밝힌다(FR-021) — 한국 시간 하루로 읽으면 날짜가 하루 어긋나 보인다. 시작일 상한은 UTC
 * 어제다(FR-022). 경로 이름(`crypto`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)가 전제하는 이름이다.
 */

import { useEffect, useMemo } from "react";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { CryptoSimulationForm } from "@/components/crypto/CryptoSimulationForm";
import { CollectingNotice, FxUnavailableNotice } from "@/components/stock/CollectingNotice";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { formatPercent } from "@/lib/format";
import { utcYesterday } from "@/lib/startDate";
import { useCryptoStore } from "@/stores/cryptoStore";

/** 코인의 표시 이름 — 한글 이름이 있으면 그것, 없으면 영문 이름. */
const coinName = (coin: { name: string; nameKo: string | null } | null) =>
  coin === null ? "코인" : (coin.nameKo ?? coin.name);

export default function CryptoPage() {
  const {
    input, rows, summary, condition, exchange, hasMore, series, seriesError, collecting, progress,
    fxBlocked,
    startable, loading, loadingMore, error, loadMoreError,
    history, historySaveError, selectedHistory, comparison, comparing, comparisonError,
    setInput, selectCoin, run, loadMore, refreshIfRan, dispose,
    restoreHistory, toggleHistory, removeHistoryEntry, rerunHistory, compareSelected,
  } = useCryptoStore();

  // FR-033 — 설정 화면에 다녀왔을 수 있다. 실행한 결과가 있으면 새 수수료로 다시 받는다.
  useEffect(() => {
    void refreshIfRan();
  }, [refreshIfRan]);
  // 화면을 떠나면 진행 구독을 끊는다.
  useEffect(() => dispose, [dispose]);
  // FR-045 — 이력은 브라우저에 있다. 화면이 열릴 때 읽는다.
  useEffect(() => {
    restoreHistory();
  }, [restoreHistory]);

  // 시작일의 마지막 날 — UTC 어제. 화면을 연 때로 정한다(서버도 계산 끝을 UTC 어제로 잡는다).
  const limit = useMemo(() => utcYesterday(), []);
  const quote = input.coin?.currency ?? null;

  const notes: string[] = [];
  if (summary !== null) {
    // C3 — 매수일이 시작 월 1일이 아니면(1일 결측) 그 날짜가 드러나야 한다. 늘 보이면 조건을 확인하기 쉽다.
    notes.push(`매수일 ${summary.boughtOn}`);
    if (condition !== null) notes.push(`수수료 ${formatPercent(condition.tradeFeeRate, 2).replace("+", "")}`);
  }

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">가상자산 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">매수 후 보유한 투자 성과 (일봉 기준: UTC 하루)</p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <CoinSearch value={input.coin} onSelect={selectCoin} />
        <CryptoSimulationForm
          values={{ start: input.start, principal: input.principal,
            principalCurrency: input.principalCurrency }}
          disabled={loading || input.coin === null}
          limit={limit}
          startable={startable}
          quoteCurrency={quote}
          onChange={(next) => setInput(next)}
          onSubmit={() => void run()}
        />
      </section>

      {error !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {fxBlocked !== null && (
        <FxUnavailableNotice blocked={fxBlocked} onMove={(start) => setInput({ start })} />
      )}

      {collecting !== null && (
        // FR-013 — 진행을 보이되 부분 결과를 보여주지 않는다.
        <CollectingNotice collecting={collecting} stockName={coinName(input.coin)} progress={progress} />
      )}

      {loading && <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>}

      {summary !== null && (
        <PerformanceBoard summary={summary} currency={input.principalCurrency}
          exchange={exchange ?? undefined} notes={notes} />
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
            // 점은 일봉마다, 출처 결측에서 끊긴다(FR-023, FR-043).
            <PerformanceChart series={series} collecting={collecting} loading={loading} />
          )}
        </section>
      )}

      {summary !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
          <CryptoPerformanceTable
            rows={rows}
            currency={input.principalCurrency}
            quoteCurrency={quote ?? "USD"}
            summary={summary}
            hasMore={hasMore}
            loadingMore={loadingMore}
            loadError={loadMoreError}
            onLoadMore={() => void loadMore()}
          />
        </section>
      )}

      <CryptoHistory
        entries={history}
        selected={selectedHistory}
        comparing={comparing}
        saveError={historySaveError}
        onToggle={toggleHistory}
        onRemove={removeHistoryEntry}
        onCompare={() => void compareSelected()}
        onRerun={(id) => void rerunHistory(id)}
      />

      {(comparing || comparison.length > 0 || comparisonError !== null) && (
        // FR-046 — 모두 KRW 기준 수익률로 겹친다. 주식 이력과 섞이지 않는다.
        <ComparisonChart items={comparison} loading={comparing} error={comparisonError} />
      )}
    </div>
  );
}
