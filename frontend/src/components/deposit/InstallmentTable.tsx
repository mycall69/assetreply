"use client";

/**
 * 적금 일자별 표 (011 T049) — FR-032, ui-wireframes §8.
 *
 * - 열 13개 — 날짜 · 구분 · 회차 · 적용 금리 · 금액 · 이자(세전) · 이자 소득세 · 세후 이자 · 적금 평가 · 예금 평가 · 평가액 · 투자 수익 ·
 *   수익률. 금액 열의 통화(KRW)는 열 이름 아래 줄이다(006 R6-26)
 * - **구분은 글자**다 — 납입 · 월 · 적금 만기 · 예금 만기 · 예금 가입, 잠정이면 "·잠정"(색만으로 전달하지 않는다)
 * - 적용 금리는 금리와 그 금리의 달이다. 잠정이면 "(26-08 대신)"처럼 대신 쓴 달을 밝힌다(008 `rateCell`과 같다)
 * - 예금 가입 행의 금액 `title`이 원금의 구성(예금 만기 + 적금 만기)을 말한다
 * - 같은 날의 다른 사건은 행이 따로다(키 `날짜:종류`). 행은 최신순으로 한 번에 모두 온다(008과 같다)
 * - 화면은 계산하지 않는다 — 서식만 입힌다
 */

import { formatAnnualRate, formatMoney, formatMoneyWithSymbol, formatPercent } from "@/lib/format";
import type { InstallmentRow, InstallmentRowKind } from "@/lib/types";

const KIND_TEXT: Record<InstallmentRowKind, string> = {
  installment: "납입",
  month: "월",
  installment_maturity: "적금 만기",
  deposit_maturity: "예금 만기",
  deposit_join: "예금 가입",
};

const INTEREST_HELP = "만기 행의 이자입니다. 다른 행은 비어 있습니다 — 경과 이자는 평가 칸에 들어 있습니다.";

const COLUMNS: readonly { name: string; unit: string | null; title?: string }[] = [
  { name: "날짜", unit: null },
  { name: "구분", unit: null },
  { name: "회차", unit: null, title: "적금 납입의 회차(n/12)" },
  { name: "적용 금리", unit: null, title: "연 금리와 그 금리의 달. 잠정이면 대신 쓴 달입니다." },
  { name: "금액", unit: "KRW", title: "납입액 · 만기 금액 · 정기예금 원금" },
  { name: "이자(세전)", unit: "KRW", title: INTEREST_HELP },
  { name: "이자 소득세", unit: "KRW", title: INTEREST_HELP },
  { name: "세후 이자", unit: "KRW", title: INTEREST_HELP },
  { name: "적금 평가", unit: "KRW" },
  { name: "예금 평가", unit: "KRW" },
  { name: "평가액", unit: "KRW" },
  { name: "투자 수익", unit: "KRW" },
  { name: "수익률", unit: null },
];

const CELL = "whitespace-nowrap px-1.5 py-2 text-right tabular-nums";

/** `2026-01` → `26-01`. */
const shortMonth = (month: string) => month.slice(2);

function rateCell(row: InstallmentRow): string {
  if (row.rate === undefined || row.rateMonth === undefined) return "";
  const month = shortMonth(row.rateMonth);
  return `${formatAnnualRate(row.rate)} (${row.provisional ? `${month} 대신` : month})`;
}

const money = (v: string | undefined) => (v === undefined ? "" : formatMoney(v, "KRW"));

export function InstallmentTable({ rows }: { rows: InstallmentRow[] }) {
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
                className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${i < 2 ? "text-left" : "text-right"}`}>
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
            <tr key={`${row.date}:${row.kind}`} data-kind={row.kind}
              className={`border-b border-gray-100 last:border-0 ${row.provisional ? "text-gray-500" : ""} ${
                row.kind === "deposit_join" ? "bg-emerald-50" : row.kind.endsWith("maturity") ? "bg-amber-50" : ""}`}>
              <td className="whitespace-nowrap px-1.5 py-2 tabular-nums">{row.date}</td>
              <td className="whitespace-nowrap px-1.5 py-2">{KIND_TEXT[row.kind]}{row.provisional ? "·잠정" : ""}</td>
              <td className={CELL}>{row.installmentNo === undefined ? "" : `${row.installmentNo}/12`}</td>
              <td className={CELL}>{rateCell(row)}</td>
              <td className={CELL}
                title={row.kind === "deposit_join" && row.fromDeposit !== undefined && row.fromInstallment !== undefined
                  ? `원금 = 예금 만기 ${formatMoneyWithSymbol(row.fromDeposit, "KRW")} + 적금 만기 `
                    + formatMoneyWithSymbol(row.fromInstallment, "KRW")
                  : undefined}>
                {money(row.amount)}
              </td>
              <td className={CELL}>{money(row.interest)}</td>
              <td className={CELL}>{money(row.tax)}</td>
              <td className={CELL}>{money(row.afterTax)}</td>
              <td className={CELL}>{money(row.installmentValue)}</td>
              <td className={CELL}>{money(row.depositValue)}</td>
              <td className={`font-medium ${CELL}`}>{money(row.balance)}</td>
              <td className={CELL}>{money(row.profit)}</td>
              <td className={CELL}>{formatPercent(row.returnRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
