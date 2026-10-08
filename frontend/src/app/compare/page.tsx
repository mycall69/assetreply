"use client";

/**
 * 투자 비교 (013 T037·T057·T077) — FR-001~FR-019, ui-wireframes F1~F9.
 *
 * 자산군 하나를 고르고 대상 2~10개를 메뉴와 같은 부품으로 더해 공통 조건으로 실행한다. 대상마다 비교 경로를 부르고(계산된 대상부터 —
 * 명확화 2), 막힌 대상이 하나라도 있으면 결과 대신 막힘 칸이다(명확화 1). 결과를 본 뒤 조건을 바꾸면 흐린다(명확화 6).
 *
 * 비교는 **이력을 쓰지 않는다**(FR-020) — 메뉴 스토어의 실행을 부르지 않고 `useCompareStore`만 쓴다. 일자별 투자 성과표는 없다.
 */
import { useEffect } from "react";
import { AssetPicker } from "@/components/compare/AssetPicker";
import { CompareBlockedPanel } from "@/components/compare/CompareBlockedPanel";
import { CompareConditionForm } from "@/components/compare/CompareConditionForm";
import { CompareMetricBars, type MetricItem } from "@/components/compare/CompareMetricBars";
import { CompareReturnChart, type CompareChartItem } from "@/components/compare/CompareReturnChart";
import { CompareTable, sortedRows, type CompareRow } from "@/components/compare/CompareTable";
import { CompareTargetPicker } from "@/components/compare/CompareTargetPicker";
import { StaleBanner } from "@/components/compare/StaleBanner";
import { ProductPicker } from "@/components/deposit/ProductPicker";
import { InvestmentModeFields } from "@/components/recurring/InvestmentModeFields";
import { TargetChips } from "@/components/compare/TargetChips";
import { overall, suggestion, type BlockReason } from "@/lib/compareBlock";
import { maxTargets, targetName } from "@/lib/compareCondition";
import { coinLink, complexSearchLink, stockLink } from "@/lib/externalLinks";
import type { CompareTarget } from "@/lib/types";
import { isStale, runRows, useCompareStore } from "@/stores/compareStore";

/** 대상 이름의 바깥 링크 — 메뉴와 같은 규칙(010 반복 1). 예금은 링크가 없다. */
function linkOf(target: CompareTarget): string | null {
  if ("market" in target) return stockLink(target);
  if ("coinId" in target) return coinLink(target);
  if ("complexId" in target) return complexSearchLink(target.name, target.umdName);
  return null;
}

export default function ComparePage() {
  const store = useCompareStore();
  const {
    asset, method, frequency, start, amount, principalCurrency, reinvest, targets, notice, run, sort,
    setAsset, setMethod, setFrequency, setStart, setAmount, setPrincipalCurrency, setReinvest, addTarget, removeTarget,
    toggleSort,
    runComparison, retryTarget, moveStart, dispose,
  } = store;

  // 화면을 떠나면 대상별 진행 구독을 모두 끊는다 — 남기면 떠난 화면이 다시 요청을 보낸다.
  useEffect(() => dispose, [dispose]);

  const stale = isStale(store);
  const rows: CompareRow[] = run === null ? [] : runRows(run).map(({ key, target, state }) => ({
    key, name: targetName(target), href: linkOf(target), state }));
  const states = rows.map((r) => r.state);
  const status = run === null ? null : overall(states);
  const blocked = rows.flatMap((r) => (r.state.status === "blocked"
    ? [{ key: r.key, name: r.name, reason: r.state.reason as BlockReason }] : []));
  const proposal = suggestion(states);
  // 그래프에는 계산된 대상만 — 수집 중 대상은 끝나면 더해진다(명확화 2). 선은 실행 차례라 정렬해도 색이 바뀌지 않고, 막대는 표의 지금 정렬이다.
  const chartItems: CompareChartItem[] = rows.flatMap((r) => (r.state.status === "ok"
    ? [{ key: r.key, name: r.name, series: r.state.data.series, lineEnd: r.state.data.comparison.lineEnd }] : []));
  const metricItems: MetricItem[] = sortedRows(rows, sort).flatMap((r) => (r.state.status === "ok"
    ? [{
      key: r.key, name: r.name, returnRate: r.state.data.comparison.returnRate, profit: r.state.data.comparison.profit,
      provisional: r.state.data.comparison.provisional.length > 0,
    }] : []));

  // 투자 방식 — 메뉴와 같은 부품이다(주식·가상자산 `InvestmentModeFields`, 예금 `ProductPicker`). 부동산은 하나뿐이다.
  const methodFields = asset === "stock" || asset === "crypto"
    ? (
      <InvestmentModeFields asset={asset} start={start}
        value={{ mode: method === "recurring" ? "recurring" : "lump_sum", frequency }}
        onChange={(plan) => {
          setMethod(plan.mode);
          setFrequency(plan.frequency);
        }} />
    )
    : asset === "deposit"
      ? <ProductPicker value={method === "installment" ? "installment" : "deposit"} onChange={setMethod} />
      : <p className="text-sm"><span className="mr-4 text-gray-500">투자 방식</span>매입 후 보유</p>;

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">투자 비교</h2>
        <p className="mt-1 text-sm text-gray-500">같은 돈을 같은 날 넣었다면 — 한 자산군의 대상 여러 개를 같은 조건으로 나란히</p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <AssetPicker value={asset} onChange={setAsset} />
        <CompareTargetPicker asset={asset} method={method} targets={targets} onAdd={addTarget} onRemove={removeTarget} />
        <TargetChips targets={targets} max={maxTargets(asset)} onRemove={removeTarget} />
      </section>

      <section className="rounded-lg border border-gray-200 p-4">
        <CompareConditionForm asset={asset} method={method} start={start} amount={amount}
          principalCurrency={principalCurrency} reinvest={reinvest} targets={targets} methodFields={methodFields}
          onStart={setStart} onAmount={setAmount} onCurrency={setPrincipalCurrency} onReinvest={setReinvest}
          onRun={() => void runComparison()} />
      </section>

      {notice !== null && (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">{notice}</p>
      )}

      {run !== null && status === "blocked" && (
        <CompareBlockedPanel blocked={blocked} suggestion={proposal.date} collecting={proposal.collecting}
          onMoveStart={moveStart} />
      )}

      {run !== null && status !== "blocked" && (
        <section className="space-y-3">
          {stale && <StaleBanner onRerun={() => void runComparison()} />}
          <div className={stale ? "space-y-5 opacity-50" : "space-y-5"} data-testid="compare-result">
            <CompareTable rows={rows} method={run.condition.method} sort={sort} onSort={toggleSort}
              onRetry={(key) => void retryTarget(key)} />
            {chartItems.length > 0 && (
              <>
                <CompareReturnChart items={chartItems} />
                <CompareMetricBars items={metricItems} />
              </>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
