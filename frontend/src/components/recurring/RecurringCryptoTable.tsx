"use client";

/**
 * 가상자산 적립식 표 (011 T039) — FR-017, FR-019, ui-wireframes §4.
 *
 * - 행은 납입(매수 0이어도)과 그 달 첫 일봉(그날 납입이 없을 때만)이다. 하루에 행이 많아야 하나라 키는 날짜다
 * - 수량은 소수 8자리(`formatQuantity`), 시가는 유효 숫자를 잃지 않게(`formatPrice` — 007 FR-040)
 * - 외화 시세의 수수료·대기금·잔고도 유효 숫자를 잃지 않는다. 적립식은 한 번 납입액이 작아 수수료가 1센트에 못 미친다 — "0.00"이면
 *   수수료가 없다고 읽힌다(T039 실측). 원화 시세는 원 단위 그대로다
 * - "◇ 1일 결측" = 그 달 1일 일봉이 출처에 없어 다른 날이 그 달의 첫 행이다(007 FR-030). 기호만으로 전달하지 않는다
 * - 미뤄진 납입은 원래 날짜를 잃지 않는다 — "+n회(원래 날짜)"
 * - 환율 열은 환율이 있는 행이 있을 때만 둔다(원화 시세 코인이면 빈 열을 남기지 않는다). 원화 원금 납입 행은 환전 환율이다
 * - 화면은 계산하지 않는다 — 서식만 입힌다
 */

import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { formatMoney, formatMoneyWithSymbol, formatPercent, formatPrice, formatQuantity, formatRate } from "@/lib/format";
import type { RecurringCryptoRow } from "@/lib/types";

interface Props {
  rows: RecurringCryptoRow[];
  principalCurrency: string;
  /** 코인의 시세 통화. */
  quoteCurrency: string;
  hasMore: boolean;
  loadingMore?: boolean;
  loadError?: string | null;
  onLoadMore: () => void;
}

const short = (iso: string) => iso.slice(5);
const CELL = "px-1.5 py-1.5 text-right tabular-nums";

function deferredText(deferred: string[] | undefined): string | null {
  if (deferred === undefined || deferred.length === 0) return null;
  return `+${deferred.length}회(${deferred.map(short).join("·")})`;
}

/** 사지 않은 행 — 수량 문자열이 0이다("0.00000000"). 화면은 값을 계산하지 않고 문자열만 본다. */
const nothingBought = (quantity: string) => /^0*\.?0*$/.test(quantity);

export function RecurringCryptoTable({
  rows, principalCurrency, quoteCurrency, hasMore, loadingMore = false, loadError = null, onLoadMore,
}: Props) {
  const open = hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);
  const showFx = rows.some((r) => r.fxRate !== undefined || r.exchangeRate !== undefined);
  const foreign = quoteCurrency !== "KRW";
  const quoteMoney = (value: string) => (foreign ? formatPrice(value) : formatMoney(value, quoteCurrency));

  const columns: { name: string; unit: string | null }[] = [
    { name: "날짜", unit: null },
    { name: "납입액", unit: foreign ? principalCurrency : null },
    ...(showFx ? [{ name: "환율", unit: "KRW" }] : []),
    { name: "시가", unit: foreign ? quoteCurrency : null },
    { name: "구매 수량", unit: null },
    { name: "매매 수수료", unit: foreign ? quoteCurrency : null },
    { name: "보유 수량", unit: null },
    { name: "매수 대기금", unit: foreign ? quoteCurrency : null },
    { name: "총 납입 원금", unit: foreign ? principalCurrency : null },
    { name: "잔고", unit: foreign ? `${quoteCurrency} · KRW` : null },
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
              const bought = !nothingBought(row.boughtQuantity);
              const idle = row.kind === "contribution" && !bought;
              const deferred = deferredText(row.deferred);
              const fx = row.exchangeRate !== undefined
                ? { text: `환전 ${formatRate(row.exchangeRate)}`, date: row.exchangeRateDate }
                : row.fxRate !== undefined ? { text: formatRate(row.fxRate), date: row.fxRateDate } : null;
              return (
                <tr key={row.date} data-kind={row.kind} className="border-b border-gray-100 last:border-0">
                  <td className="whitespace-nowrap px-1.5 py-1.5 text-left tabular-nums">
                    {row.date}
                    {row.kind === "contribution" && (
                      <>
                        {" "}
                        <span data-idle={idle ? "true" : undefined}
                          className={idle ? "text-gray-400" : "text-emerald-700"}>＋</span>
                      </>
                    )}
                    {row.firstDayMissing !== undefined && (
                      <span className="ml-1 text-amber-700"
                        title={`${row.firstDayMissing} 일봉이 없어 ${short(row.date)} 일봉을 썼습니다`}>
                        ◇ 1일 결측
                      </span>
                    )}
                  </td>
                  <td className={CELL}>
                    {row.contribution === undefined ? "" : formatMoney(row.contribution, principalCurrency)}
                    {deferred !== null && <span className="block text-gray-500">{deferred}</span>}
                  </td>
                  {showFx && (
                    <td className={`whitespace-nowrap ${CELL}`}>
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
                  <td className={CELL}>{formatPrice(row.openPrice)}</td>
                  <td className={CELL}>{bought ? formatQuantity(row.boughtQuantity) : "—"}</td>
                  <td className={CELL}>
                    {row.tradeFee === undefined ? "—" : quoteMoney(row.tradeFee)}
                  </td>
                  <td className={CELL}>{formatQuantity(row.heldQuantity)}</td>
                  <td className={CELL}>{quoteMoney(row.pending)}</td>
                  <td className={CELL}>{formatMoney(row.contributed, principalCurrency)}</td>
                  <td className={`whitespace-nowrap ${CELL}`}>
                    {quoteMoney(row.balance)}
                    {row.balanceKrw !== undefined && (
                      <span className="block text-gray-500">{formatMoneyWithSymbol(row.balanceKrw, "KRW")}</span>
                    )}
                  </td>
                  <td className={CELL}>{formatMoney(row.profit, "KRW")}</td>
                  <td className={CELL}>{formatPercent(row.returnRate)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

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
