"use client";

/**
 * 가상자산 투자 시뮬레이션 (T033) — 007 FR-001, ui-wireframes C1~C7.
 *
 * 주식 화면과 같은 구성이다 — 코인 검색 → 시작일·원금·원금 통화 → 시뮬레이션 → 성과 보드·일자별 표. **배당 재투자 칸이 없다.**
 * 화면 머리에 일봉 기준(UTC 하루)을 밝힌다(FR-021) — 한국 시간 하루로 읽으면 날짜가 하루 어긋나 보인다. 시작일 상한은 UTC
 * 어제다(FR-022). 경로 이름(`crypto`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)가 전제하는 이름이다.
 *
 * 011 — 투자 방식(일시금·적립식)을 고른다. 적립식이면 다섯 칸 보드(`RecurringBoard`)·적립식 표(`RecurringCryptoTable`)·누적 납입 원금
 * 점선이 있는 차트를 그리고, 일시금 보드·표는 없다(한 번에 한쪽만).
 */

import { useEffect, useMemo } from "react";
import { useHeightHold } from "@/hooks/useHeightHold";
import { TableWithHistory } from "@/components/TableWithHistory";
import { PeriodTableSection } from "@/components/period/PeriodTableSection";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { CryptoSimulationForm } from "@/components/crypto/CryptoSimulationForm";
import { InvestmentModeFields } from "@/components/recurring/InvestmentModeFields";
import { RecurringBoard } from "@/components/recurring/RecurringBoard";
import { RecurringCryptoTable } from "@/components/recurring/RecurringCryptoTable";
import { CollectingNotice, FxUnavailableNotice } from "@/components/stock/CollectingNotice";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { formatPercent } from "@/lib/format";
import { amountLabel } from "@/lib/recurringText";
import { utcYesterday } from "@/lib/startDate";
import { CRYPTO_PERIOD_TITLES } from "@/lib/tablePeriod";
import type { PeriodUnit } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";

/** 코인의 표시 이름 — 한글 이름이 있으면 그것, 없으면 영문 이름. */
const coinName = (coin: { name: string; nameKo: string | null } | null) =>
  coin === null ? "코인" : (coin.nameKo ?? coin.name);

export default function CryptoPage() {
  const {
    input, plan, recurring, setPlan, rows, summary, condition, exchange, hasMore, series, seriesError, collecting,
    progress, fxBlocked,
    startable, loading, loadingMore, error, loadMoreError,
    tablePeriod, tableLoading, tableError, setTablePeriod,
    history, historySaveError, historyLoading, historyLoadError, historyNotice, retentionDays,
    selectedHistory, comparison, comparing, comparisonError,
    setInput, selectCoin, run, loadMore, refreshIfRan, dispose,
    restoreHistory, toggleHistory, removeHistoryEntry, rerunHistory, compareSelected,
  } = useCryptoStore();

  // 012 FR-006 — 표의 단위를 바꾸는 동안 바꾸기 직전 높이를 붙잡는다(주식·외환과 같은 훅).
  const { ref: workspace, style: holdStyle, hold } = useHeightHold<HTMLDivElement>();
  const switchPeriod = (period: PeriodUnit) => hold(() => setTablePeriod(period));

  // FR-033 — 설정 화면에 다녀왔을 수 있다. 실행한 결과가 있으면 새 수수료로 다시 받는다.
  useEffect(() => {
    void refreshIfRan();
  }, [refreshIfRan]);
  // 화면을 떠나면 진행 구독을 끊는다.
  useEffect(() => dispose, [dispose]);
  // FR-045 — 이력은 로컬 DB에 있다(012). 화면이 열릴 때 그 자산군의 옛 브라우저 이력을 옮긴 뒤 목록을 받는다(012 FR-013).
  useEffect(() => {
    void restoreHistory();
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
    <div ref={workspace} className="space-y-5" style={holdStyle}>
      <header>
        <h2 className="text-2xl font-bold tracking-tight">가상자산 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">
          {plan.mode === "recurring" ? "정해진 주기로 사 모은 투자 성과" : "매수 후 보유한 투자 성과"} (일봉 기준: UTC 하루)
        </p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <CoinSearch value={input.coin} onSelect={selectCoin} />
        {/* 011 FR-001 — 투자 방식. 바꾸면 결과가 빈다(조건은 남는다). */}
        <InvestmentModeFields value={plan} start={input.start} asset="crypto" disabled={loading} onChange={setPlan} />
        <CryptoSimulationForm
          principalLabel={amountLabel(plan.mode)}
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

      {recurring !== null && (
        // 011 FR-012·FR-020 — 적립식 보드(다섯 칸). 과세 시행 전이면 세금 0과 그 사실을 보인다.
        <RecurringBoard asset="crypto" summary={recurring.summary} principalCurrency={input.principalCurrency}
          quoteCurrency={quote ?? "USD"} />
      )}

      {recurring !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
          {recurring.seriesError !== null ? (
            <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {recurring.seriesError}
            </p>
          ) : (
            // 점은 일봉마다, 출처 결측에서 끊긴다. 누적 납입 원금 점선이 함께다(FR-019).
            <PerformanceChart series={recurring.series} collecting={collecting} loading={loading} />
          )}
        </section>
      )}

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

      {/* 010 FR-015~FR-017 — 넓은 창이면 성과 표 오른쪽(sticky), 좁으면 지금처럼 표 아래. 경계는 표의 실제 폭이다. */}
      <TableWithHistory
        table={recurring !== null ? (
          <PeriodTableSection period={tablePeriod} titles={CRYPTO_PERIOD_TITLES} onPeriod={switchPeriod}
            loading={tableLoading} error={tableError}>
            <RecurringCryptoTable
              rows={recurring.rows}
              principalCurrency={input.principalCurrency}
              quoteCurrency={quote ?? "USD"}
              hasMore={recurring.hasMore}
              loadingMore={loadingMore}
              loadError={loadMoreError}
              onLoadMore={() => void loadMore()}
              period={tablePeriod}
            />
          </PeriodTableSection>
        ) : summary !== null ? (
          <PeriodTableSection period={tablePeriod} titles={CRYPTO_PERIOD_TITLES} onPeriod={switchPeriod}
            loading={tableLoading} error={tableError}>
            <CryptoPerformanceTable
              rows={rows}
              currency={input.principalCurrency}
              quoteCurrency={quote ?? "USD"}
              summary={summary}
              hasMore={hasMore}
              loadingMore={loadingMore}
              loadError={loadMoreError}
              onLoadMore={() => void loadMore()}
              period={tablePeriod}
            />
          </PeriodTableSection>
        ) : null}
        history={(
          <CryptoHistory
            entries={history}
            selected={selectedHistory}
            comparing={comparing}
            saveError={historySaveError}
            loading={historyLoading}
            loadError={historyLoadError}
            onRetry={() => void restoreHistory()}
            notice={historyNotice}
            retentionDays={retentionDays}
            onToggle={toggleHistory}
            onRemove={(id) => void removeHistoryEntry(id)}
            onCompare={() => void compareSelected()}
            onRerun={(id) => void rerunHistory(id)}
          />
        )}
      />

      {(comparing || comparison.length > 0 || comparisonError !== null) && (
        // FR-046 — 모두 KRW 기준 수익률로 겹친다. 주식 이력과 섞이지 않는다.
        <ComparisonChart items={comparison} loading={comparing} error={comparisonError} />
      )}
    </div>
  );
}
