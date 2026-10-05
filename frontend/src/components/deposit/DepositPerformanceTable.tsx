"use client";

/**
 * 예금 일자별 투자 성과 표 (T021) — 008 FR-032~FR-034, ui-wireframes D4.
 *
 * - 열 10개(FR-032). 금액 열의 통화(KRW)는 열 이름 아래 줄이다(006 R6-26)
 * - **구분은 글자**다 — 가입·월·만기·재예치, 잠정이면 "·잠정"(FR-033). 색만으로 전달하지 않는다
 * - 적용 금리 칸은 금리와 그 금리의 달. 잠정이면 "(26-08 대신)"처럼 대신 쓴 달을 밝힌다(FR-033)
 * - 월 행의 이자·세금·세후 이자는 그날까지의 **경과분**, 만기 행은 만기 이자다 — 머리글 도움말로 밝힌다(FR-032)
 * - 행은 최신순으로 한 번에 모두 온다(행이 적다). 표는 **내용 폭**이다 — 1440px에서 모든 열이 보인다(FR-034)
 *
 * 손익은 부호와 함께 쓴다(접근성).
 */

import { formatAnnualRate, formatMoney, formatPercent } from "@/lib/format";
import type { DepositRow, DepositRowKind } from "@/lib/types";

const KIND_TEXT: Record<DepositRowKind, string> = {
  join: "가입", month: "월", maturity: "만기", reinvest: "재예치",
};

const INTEREST_HELP = "월 행은 그날까지의 경과분, 만기 행은 만기 이자입니다. 가입·재예치 행은 0입니다.";

const COLUMNS: readonly { name: string; unit: string | null; title?: string }[] = [
  { name: "날짜", unit: null },
  { name: "구분", unit: null },
  { name: "적용 금리", unit: null, title: "연 금리와 그 금리의 달. 잠정이면 대신 쓴 달입니다." },
  { name: "예치 원금", unit: "KRW" },
  { name: "이자(세전)", unit: "KRW", title: INTEREST_HELP },
  { name: "이자 소득세", unit: "KRW", title: INTEREST_HELP },
  { name: "세후 이자", unit: "KRW", title: INTEREST_HELP },
  { name: "잔고", unit: "KRW" },
  { name: "투자 수익", unit: "KRW" },
  { name: "수익률", unit: null },
];

const CELL = "whitespace-nowrap px-1.5 py-2 text-right tabular-nums";

/** `2026-01` → `26-01`. */
const shortMonth = (month: string) => month.slice(2);

function rateCell(row: DepositRow): string {
  const month = shortMonth(row.rateMonth);
  return `${formatAnnualRate(row.rate)} (${row.provisional ? `${month} 대신` : month})`;
}

export function DepositPerformanceTable({ rows }: { rows: DepositRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  return (
    <div className="w-fit max-w-full overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-max text-xs">
        <thead>
          <tr className="border-b border-gray-200 text-xs text-gray-500">
            {COLUMNS.map((c, i) => (
              <th key={c.name} scope="col" title={c.title}
                className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${
                  i < 2 ? "text-left" : "text-right"}`}>
                {c.name}
                {c.unit !== null && (
                  <>
                    {" "}
                    <span className="block text-gray-400">({c.unit})</span>
                  </>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.date}-${row.kind}`}
              className={`border-b border-gray-100 last:border-0 ${row.provisional ? "text-gray-500" : ""}`}>
              <td className="whitespace-nowrap px-1.5 py-2 tabular-nums">{row.date}</td>
              <td className="whitespace-nowrap px-1.5 py-2">
                {KIND_TEXT[row.kind]}{row.provisional ? "·잠정" : ""}
              </td>
              <td className={CELL}>{rateCell(row)}</td>
              <td className={CELL}>{formatMoney(row.principal, "KRW")}</td>
              <td className={CELL}>{formatMoney(row.interest, "KRW")}</td>
              <td className={CELL}>{formatMoney(row.tax, "KRW")}</td>
              <td className={CELL}>{formatMoney(row.afterTax, "KRW")}</td>
              <td className={CELL}>{formatMoney(row.balance, "KRW")}</td>
              <td className={CELL}>{formatMoney(row.profit, "KRW")}</td>
              <td className={CELL}>{formatPercent(row.returnRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
