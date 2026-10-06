"use client";

/**
 * 적립식 보드 (011 T027) — FR-012, FR-020, ui-wireframes §2. 주식·가상자산이 함께 쓴다.
 *
 * 다섯 칸이다 — 총 납입 원금 · 매매 수수료 총액 · 세금 총액 · 투자 수익 · 수익률.
 *
 * **화면은 계산하지 않는다.** 모든 값은 서버 문자열이고 여기서는 서식만 입힌다(`noClientSideFinance`).
 * - 투자 수익·수익률은 기준일 매도 비용을 뺀 값이다. 매수 수수료와 배당 소득세는 이미 총자산에서 빠져 있다 — 다시 빼면 두 번 차감된다(FR-012)
 * - 수익률은 단순 수익률이고 곁의 도움말이 일시금과의 비교 한계를 말한다(명확화)
 * - 가상자산 과세가 시행된 뒤의 기준일은 세금을 0으로 메우지 않고 "—"와 "세법 미반영"이다(FR-020)
 * - 가상자산의 외화 매수 대기금은 유효 숫자를 잃지 않는다 — 소수 8자리로 사고 남은 돈이라 1센트에 못 미친다. "$0.00"이면 없다고
 *   읽힌다(T039 실측, 007 FR-040과 같은 이유)
 */

import { useId } from "react";
import { currencySymbol, formatMoneyWithSymbol, formatPercent, formatPrice, formatQuantity } from "@/lib/format";
import type {
  CryptoSaleCost,
  RecurringCryptoSummary,
  RecurringStockSummary,
  SaleCost,
} from "@/lib/types";

const HELP = "나중에 넣은 돈은 시장에 머문 기간이 짧아, 같은 기간의 일시금 수익률과 단순 비교하기 어렵습니다.";

const won = (v: string) => formatMoneyWithSymbol(v, "KRW");
/** `formatMoneyWithSymbol`과 같은 앞붙임 — 기호가 없는 통화는 코드와 빈칸이다. */
const symbolPrefix = (currency: string) => {
  const symbol = currencySymbol(currency);
  return symbol === currency ? `${symbol} ` : symbol;
};
const minusWon = (v: string) => formatMoneyWithSymbol(v.startsWith("-") ? v : `-${v}`, "KRW");
const percent = (v: string | null, digits: number) => (v === null ? "" : `${formatPercent(v, digits).replace("+", "")} `);

type Props =
  | { asset: "stock"; summary: RecurringStockSummary; principalCurrency: string; quoteCurrency: string }
  | { asset: "crypto"; summary: RecurringCryptoSummary; principalCurrency: string; quoteCurrency: string };

function stockTaxNotes(summary: RecurringStockSummary): string[] {
  const sale: SaleCost = summary.saleCost;
  const lines = [`배당 소득세 ${won(summary.dividendTaxTotal)}`];
  if (summary.heldShares === 0) {
    lines.push("매도할 주식 없음");
    return lines;
  }
  if (sale.tax === null) return [...lines, "매도 세금 —"];
  if (sale.taxKind === "capital_gains_tax") {
    lines.push(`양도소득세 ${percent(sale.taxRate, 0)}${won(sale.tax)} (설정)`);
    if (sale.gain !== null && sale.deduction !== null) {
      lines.push(`차익 ${won(sale.gain)} − 공제 ${won(sale.deduction)}`);
    }
  } else {
    lines.push(`증권거래세 ${percent(sale.taxRate, 2)}${won(sale.tax)} (설정)`);
  }
  return lines;
}

function cryptoTax(sale: CryptoSaleCost): { value: string; notes: string[] } {
  if (sale.taxKind === "outside_rules" || sale.tax === null) {
    return { value: "—", notes: ["세법 미반영 — 가상자산 과세 시행(2027-01-01) 뒤의 기준일"] };
  }
  return { value: won(sale.tax), notes: ["가상자산 과세 시행 전(2027-01-01 시행 예정)"] };
}

export function RecurringBoard(props: Props) {
  const { summary, principalCurrency, quoteCurrency } = props;
  const helpId = useId();
  const sale = summary.saleCost;
  const after = summary.profitAfterSale;
  const negative = (after ?? summary.profit).trimStart().startsWith("-");
  const tax = props.asset === "stock"
    ? { value: summary.taxTotal === null ? "—" : minusWon(summary.taxTotal), notes: stockTaxNotes(props.summary) }
    : cryptoTax(props.summary.saleCost);

  return (
    <section className="rounded-lg border border-gray-200">
      <div className="grid gap-px bg-gray-200 sm:grid-cols-5">
        <Cell label="총 납입 원금" notes={[`${summary.contributions.toLocaleString("en-US")}회 납입`]}>
          {principalCurrency === "KRW" ? won(summary.contributedKrw) : (
            <>
              {formatMoneyWithSymbol(summary.contributed, principalCurrency)}{" "}
              <span className="text-base font-normal text-gray-500">({won(summary.contributedKrw)})</span>
            </>
          )}
        </Cell>
        <Cell label="매매 수수료 총액" notes={[`매수 ${won(summary.buyFeeTotal)}`, `매도 ${won(sale.fee)}`]}>
          {minusWon(summary.feeTotal)}
        </Cell>
        <Cell label="세금 총액" notes={tax.notes}>{tax.value}</Cell>
        <Cell label="투자 수익" emphasis={after === null ? undefined : negative ? "loss" : "gain"}
          notes={["매도 비용을 뺀 값", `보유 중 ${won(summary.profit)}`]}>
          {after === null ? "—" : won(after)}
        </Cell>
        <Cell label="수익률" emphasis={after === null ? undefined : negative ? "loss" : "gain"} describedBy={helpId}
          notes={["매도 비용을 뺀 값", `보유 중 ${formatPercent(summary.returnRate)}`]}>
          {summary.returnRateAfterSale === null ? "—" : formatPercent(summary.returnRateAfterSale)}
          <span id={helpId} role="note" aria-label="수익률 도움말" title={HELP}
            className="ml-1 cursor-help align-top text-xs font-normal text-gray-400">
            ⓘ<span className="sr-only">{HELP}</span>
          </span>
        </Cell>
      </div>

      <p data-testid="recurring-basis" className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        <span className="tabular-nums">{summary.asOf}</span> 기준 · KRW 기준 ·{" "}
        {props.asset === "stock" ? "매수 수수료·배당 소득세는 이미 총자산에서 빠져 있습니다" : "매수 수수료는 이미 총자산에서 빠져 있습니다"}
        {" "}· 매도 비용: 기준일에 모두 판다고 가정한 값 — 일자별 표는 보유 중 평가
      </p>
      <p data-testid="recurring-holding" className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        매수 대기금 {props.asset === "crypto" && quoteCurrency !== "KRW"
          ? `${symbolPrefix(quoteCurrency)}${formatPrice(summary.pending)}`
          : formatMoneyWithSymbol(summary.pending, quoteCurrency)}
        {props.asset === "stock" && <> · 배당 현금 {formatMoneyWithSymbol(props.summary.dividendCash, quoteCurrency)}</>}
        {" "}· 보유 {props.asset === "stock"
          ? `${props.summary.heldShares.toLocaleString("en-US")}주`
          : formatQuantity(props.summary.heldQuantity)}
        {summary.pendingAfterEnd > 0 && <> · 다음 거래일에 들어갈 납입 {summary.pendingAfterEnd}회</>}
      </p>

      {!summary.isFinal && (
        <p role="status" className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          ⚠ {summary.asOf} 이후 시세가 없습니다. 그 날짜까지의 결과입니다.
        </p>
      )}
    </section>
  );
}

function Cell({
  label,
  children,
  emphasis,
  notes = [],
  describedBy,
}: {
  label: string;
  children: React.ReactNode;
  emphasis?: "gain" | "loss";
  notes?: string[];
  describedBy?: string;
}) {
  return (
    <div role="group" aria-label={label} aria-describedby={describedBy} className="bg-white px-4 py-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${
        emphasis === "loss" ? "text-blue-700" : emphasis === "gain" ? "text-red-700" : "text-gray-900"}`}>
        {children}
      </p>
      {notes.map((note) => (
        <p key={note} className="mt-0.5 text-xs text-gray-500 tabular-nums">{note}</p>
      ))}
    </div>
  );
}
