"use client";

/**
 * 가상자산 일자별 투자 성과 표 (T033) — 007 FR-037~FR-041, ui-wireframes C4.
 *
 * 주식 표(`PerformanceTable`)를 본뜨되 **배당 열이 없다**(FR-037) — 그대로 쓰면 빈 열 다섯이 1440px을 차지한다. 012 — 행은 일·주·월
 * 단위의 기간 행과 첫 매수 행이고, 일 단위에는 결측 구간 행(FR-004b)이 끼어 있다.
 *
 * - 통화는 열 이름 아래 줄(006 R6-26). 시가·수수료·예수금·잔고는 시세 통화, 잔고 괄호는 KRW, 투자 수익·수익율은 KRW 기준(FR-035)
 * - 수량은 소수 8자리(FR-026). 시가는 **유효 숫자를 잃지 않게**(FR-040) — `0.00`으로 보이면 시세가 없다고 읽힌다
 * - 012 FR-008 — 지금의 `◇`(그 달 1일 결측)는 없다. 월 단위는 옮겨진 기준일 표시(📅)가, 일 단위는 결측 구간 행이 대신한다
 * - 표는 **내용 폭**이다(006 버그 table-column-width) — 1440px에서 모든 열이 보이고, 넘치면 표만 스크롤된다(FR-041)
 *
 * 스크롤로 이어 본다(005 FR-029). 손익을 색만으로 구별하지 않는다 — 부호를 함께 쓴다.
 */

import { MissingRowLine } from "@/components/period/MissingRowLine";
import { PeriodLegend } from "@/components/period/PeriodLegend";
import { PeriodMarks } from "@/components/period/PeriodMarks";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { formatMoney, formatPercent, formatPrice, formatQuantity, formatRate } from "@/lib/format";
import type { CryptoSummary, CryptoTableRow, PeriodUnit } from "@/lib/types";

const COLUMNS = [
  "날짜", "시가", "구매 수량", "매매 수수료", "보유 수량", "예수금", "투자금", "잔고", "투자 수익", "수익율",
] as const;
/** 시세 통화 열. 수수료도 예수금에서 빠지는 돈이라 예수금과 같은 통화여야 예수금 변화를 설명할 수 있다. */
const QUOTE_COLUMNS = ["시가", "매매 수수료", "예수금"];
const FX_COLUMN = "환율";
const CELL = "px-1.5 py-2 text-right tabular-nums";

export function CryptoPerformanceTable({
  rows,
  currency,
  quoteCurrency,
  summary,
  hasMore,
  loadingMore = false,
  loadError = null,
  onLoadMore,
  period = "daily",
}: {
  rows: CryptoTableRow[];
  /** 입력한 원금 통화 — 투자금 열의 통화다. */
  currency: string;
  /** 코인의 시세 통화(USD). */
  quoteCurrency: string;
  /** 요약 — 일봉이 끊겼다는 안내를 표에서도 보이기 위해서다(FR-024). */
  summary?: CryptoSummary;
  hasMore: boolean;
  loadingMore?: boolean;
  loadError?: string | null;
  onLoadMore: () => void;
  /** 012 — 표의 단위. 주·월이면 기간 표시와 범례를 그린다. */
  period?: PeriodUnit;
}) {
  const open = hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);
  const showFx = rows.some((r) => r.kind !== "missing" && r.fxRate !== undefined);
  const columnCount = COLUMNS.length + (showFx ? 1 : 0);
  const foreign = quoteCurrency !== "KRW";

  const unitOf = (column: string): string | null => {
    if (QUOTE_COLUMNS.includes(column)) return quoteCurrency;
    if (column === "투자금") return currency;
    if (column === "잔고") return foreign ? `${quoteCurrency} · KRW` : quoteCurrency;
    if (column === "투자 수익") return "KRW";
    if (column === "수익율") return "KRW 기준";
    return null;
  };

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  const cutOff = summary !== undefined && !summary.isFinal;

  return (
    <div className="w-fit max-w-full rounded-lg border border-gray-200">
      {cutOff && (
        // FR-024 — 보드에만 두면 표를 보던 사용자는 마지막 행을 오늘까지의 결과로 읽는다.
        <p data-testid="table-asof"
          className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          ⚠ <span className="tabular-nums">{summary.asOf}</span> 이후 일봉이 없습니다. 아래 행은 그 날짜까지의 결과입니다.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-max text-xs">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              {[...COLUMNS, ...(showFx ? [FX_COLUMN] : [])].map((c, i) => {
                const unit = unitOf(c);
                return (
                  <th key={c} scope="col"
                    className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${
                      i === 0 ? "text-left" : "text-right"}`}>
                    {c}
                    {unit !== null && (
                      <>
                        {" "}
                        <span className="block text-gray-400">({unit})</span>
                      </>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => row.kind === "missing" ? (
              <MissingRowLine key={`${row.date}:missing`} row={row} colSpan={columnCount} />
            ) : (
              <tr key={`${row.date}:${row.kind}`} data-kind={row.kind} className="border-b border-gray-100 last:border-0">
                <td className="whitespace-nowrap px-1.5 py-2 tabular-nums">
                  {row.date}
                  <PeriodMarks row={row} unit={period} asset="crypto" />
                </td>
                <td className={CELL}>{formatPrice(row.openPrice)}</td>
                <td className={CELL}>{formatQuantity(row.boughtQuantity)}</td>
                <td className={CELL}>
                  {row.tradeFee !== undefined ? formatMoney(row.tradeFee, quoteCurrency) : ""}
                </td>
                <td className={CELL}>{formatQuantity(row.heldQuantity)}</td>
                <td className={CELL}>{formatMoney(row.cash, quoteCurrency)}</td>
                <td className={CELL}>{formatMoney(row.principal, currency)}</td>
                <td className={`whitespace-nowrap font-medium ${CELL}`}>
                  {formatMoney(row.balance, quoteCurrency)}
                  {row.balanceKrw !== undefined && (
                    <>
                      {" "}
                      <span className="font-normal text-gray-500">
                        ({formatMoney(row.balanceKrw, "KRW")})
                      </span>
                    </>
                  )}
                </td>
                <td className={CELL}>{formatMoney(row.profit, "KRW")}</td>
                <td className={CELL}>{formatPercent(row.returnRate)}</td>
                {showFx && (
                  <td className={`whitespace-nowrap ${CELL}`}>
                    {row.fxRate !== undefined ? formatRate(row.fxRate) : ""}
                    {/* 006 FR-041c — 쓴 환율의 날짜가 행 날짜와 다를 수 있다. 기호만으로 전달하지 않는다. */}
                    {row.fxRateDate !== undefined && row.fxRateDate !== row.date && (
                      <span role="img" className="ml-1"
                        title={`${row.date}에 환율 고시가 없어 ${row.fxRateDate} 값을 썼습니다`}
                        aria-label={`${row.date}에 환율 고시가 없어 ${row.fxRateDate} 값을 썼습니다`}>
                        📅
                      </span>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PeriodLegend unit={period} />

      <div className="flex items-center justify-center gap-3 border-t border-gray-100 px-4 py-3 text-xs">
        <span role="status" aria-live="polite" className="text-gray-500">
          {loadError
            ? loadError
            : loadingMore
              ? "⟳ 불러오는 중…"
              : !hasMore
                ? `${rows.at(-1)?.date ?? "처음"}까지 모두 표시했습니다`
                : ""}
        </span>
        {loadError !== null && (
          <button type="button" onClick={onLoadMore}
            className="rounded border border-gray-300 px-2.5 py-1 text-gray-700 hover:bg-gray-50">
            다시 시도
          </button>
        )}
      </div>

      {hasMore && loadError === null && (
        <div ref={sentinel} data-testid="scroll-sentinel" aria-hidden="true" className="h-px" />
      )}
    </div>
  );
}
