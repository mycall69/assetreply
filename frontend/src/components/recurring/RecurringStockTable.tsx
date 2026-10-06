"use client";

/**
 * 주식 적립식 표 (011 T027) — FR-014, SC-010, ui-wireframes §3.
 *
 * - 행은 사건이다 — 납입(매수 0이어도) · 배당 · 재투자 · 그 달 첫 거래일(그날 납입이 없을 때만). 같은 날의 다른 사건은 행이 따로이고
 *   키는 `날짜:종류`다(지금 표의 배당락 행·월 행과 같다)
 * - 미뤄진 납입은 원래 날짜를 잃지 않는다 — "+n회(원래 날짜)"
 * - 열을 아낀다 — 배당은 세후 한 칸이고 상세는 칸 제목(`title`)으로 보인다. 배당·환율 열은 그 값이 있을 때만 둔다(빈 열을 남기지 않는다).
 *   1440px에서 표가 잘리지 않아야 한다(SC-010)
 * - 화면은 계산하지 않는다 — 서식만 입힌다
 */

import { PeriodLegend } from "@/components/period/PeriodLegend";
import { PeriodMarks } from "@/components/period/PeriodMarks";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { formatDividend, formatMoney, formatPercent, formatRate } from "@/lib/format";
import type { PeriodUnit, RecurringStockRow } from "@/lib/types";

interface Props {
  rows: RecurringStockRow[];
  principalCurrency: string;
  stockCurrency: string;
  hasMore: boolean;
  loadingMore?: boolean;
  loadError?: string | null;
  onLoadMore: () => void;
  /** 012 — 표의 단위. 주·월이면 기간 표시와 범례를 그린다. */
  period?: PeriodUnit;
}

const MARK: Record<RecurringStockRow["kind"], string> = {
  contribution: "＋",
  dividend: "◆",
  reinvest: "⟳ 재투자",
  period: "",
};

const BG: Record<RecurringStockRow["kind"], string> = {
  contribution: "",
  dividend: "bg-amber-50",
  reinvest: "bg-emerald-50",
  period: "",
};

const short = (iso: string) => iso.slice(5);

function deferredText(deferred: string[] | undefined): string | null {
  if (deferred === undefined || deferred.length === 0) return null;
  return `+${deferred.length}회(${deferred.map(short).join("·")})`;
}

export function RecurringStockTable({
  rows, principalCurrency, stockCurrency, hasMore, loadingMore = false, loadError = null, onLoadMore,
  period = "daily",
}: Props) {
  const open = hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);
  const showFx = rows.some((r) => r.fxRate !== undefined || r.exchangeRate !== undefined);
  const showDividend = rows.some((r) => r.kind === "dividend");
  const foreign = stockCurrency !== "KRW";
  const money = (v: string, currency: string) => formatMoney(v, currency);

  const columns: { name: string; unit: string | null }[] = [
    { name: "날짜", unit: null },
    { name: "납입액", unit: foreign ? principalCurrency : null },
    ...(showFx ? [{ name: "환율", unit: "KRW" }] : []),
    { name: "시작가", unit: foreign ? stockCurrency : null },
    { name: "종가", unit: foreign ? stockCurrency : null },
    { name: "구매 주식수", unit: null },
    { name: "매매 수수료", unit: foreign ? stockCurrency : null },
    ...(showDividend ? [{ name: "배당(세후)", unit: foreign ? stockCurrency : null }] : []),
    { name: "보유 주식", unit: null },
    { name: "매수 대기금", unit: foreign ? stockCurrency : null },
    ...(showDividend ? [{ name: "배당 현금", unit: foreign ? stockCurrency : null }] : []),
    { name: "총 납입 원금", unit: foreign ? principalCurrency : null },
    { name: "잔고", unit: foreign ? `${stockCurrency} · KRW` : null },
    { name: "투자 수익", unit: foreign ? "KRW" : null },
    { name: "수익률", unit: foreign ? "KRW 기준" : null },
  ];

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  return (
    <div className="w-fit max-w-full rounded-lg border border-gray-200">
      <div className="overflow-x-auto">
        <table className="w-max text-xs">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              {columns.map((c, i) => (
                <th key={c.name} scope="col"
                  className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${i === 0 ? "text-left" : "text-right"}`}>
                  {c.name}
                  {c.unit !== null && <> <span className="block text-gray-400">({c.unit})</span></>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const idle = row.kind === "contribution" && row.boughtShares === 0;
              const deferred = deferredText(row.deferred);
              const fx = row.exchangeRate !== undefined
                ? { text: `환전 ${formatRate(row.exchangeRate)}`, date: row.exchangeRateDate }
                : row.fxRate !== undefined ? { text: formatRate(row.fxRate), date: row.fxRateDate } : null;
              return (
                <tr key={`${row.date}:${row.kind}`} data-kind={row.kind}
                  className={`border-b border-gray-100 last:border-0 ${BG[row.kind]}`}>
                  <td className="whitespace-nowrap px-1.5 py-1.5 text-left tabular-nums">
                    {row.date}{" "}
                    {MARK[row.kind] !== "" && (
                      <span data-idle={idle ? "true" : undefined}
                        className={idle ? "text-gray-400" : row.kind === "contribution" ? "text-emerald-700" : ""}>
                        {MARK[row.kind]}
                      </span>
                    )}
                    <PeriodMarks row={row} unit={period} asset="stock" />
                  </td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">
                    {row.contribution === undefined ? "" : money(row.contribution, principalCurrency)}
                    {deferred !== null && <span className="block text-gray-500">{deferred}</span>}
                  </td>
                  {showFx && (
                    <td className="whitespace-nowrap px-1.5 py-1.5 text-right tabular-nums">
                      {fx === null ? "" : (
                        <>
                          {fx.text}
                          {fx.date !== undefined && fx.date !== row.date && (
                            <span className="block text-gray-500">({short(fx.date)})</span>
                          )}
                        </>
                      )}
                    </td>
                  )}
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{formatRate(row.openPrice)}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{formatRate(row.closePrice)}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{row.boughtShares > 0 ? row.boughtShares : "—"}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">
                    {row.tradeFee === undefined ? "—" : money(row.tradeFee, stockCurrency)}
                  </td>
                  {showDividend && (
                    <td className="px-1.5 py-1.5 text-right tabular-nums"
                      title={row.dividendTotalNet === undefined ? undefined
                        : `주당 배당금 ${formatDividend(row.dividendPerShare ?? "0")} · 세전 ${money(row.dividendTotal ?? "0", stockCurrency)}`
                          + ` · 세금 ${money(row.dividendTax ?? "0", stockCurrency)}`}>
                      {row.dividendTotalNet === undefined ? "" : money(row.dividendTotalNet, stockCurrency)}
                    </td>
                  )}
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{row.heldShares.toLocaleString("en-US")}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{money(row.pending, stockCurrency)}</td>
                  {showDividend && (
                    <td className="px-1.5 py-1.5 text-right tabular-nums">{money(row.dividendCash, stockCurrency)}</td>
                  )}
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{money(row.contributed, principalCurrency)}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">
                    {money(row.balance, stockCurrency)}
                    {row.balanceKrw !== undefined && (
                      <span className="block text-gray-500">{money(row.balanceKrw, "KRW")}</span>
                    )}
                  </td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{money(row.profit, "KRW")}</td>
                  <td className="px-1.5 py-1.5 text-right tabular-nums">{formatPercent(row.returnRate)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <PeriodLegend unit={period} />

      <p role="status" className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {loadingMore ? "⟳ 불러오는 중…"
          : loadError !== null ? (
            <>
              {loadError}{" "}
              <button type="button" onClick={onLoadMore} className="underline">다시 시도</button>
            </>
          ) : hasMore ? "" : `${rows[rows.length - 1].date}까지 모두 표시했습니다.`}
      </p>
      {hasMore && <div ref={sentinel} data-testid="scroll-sentinel" />}
    </div>
  );
}
