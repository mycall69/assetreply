"use client";

/**
 * 적금 보드 (011 T049) — FR-031, ui-wireframes §8.
 *
 * 여섯 칸이다 — 총 납입 원금(낸 회차) · 세후 이자 합계(적금 · 예금) · 이자 소득세 합계 · 평가액(적금 · 예금) · 투자 수익 · 수익률.
 *
 * **화면은 계산하지 않는다.** 구성(적금 · 예금)까지 모든 값은 서버 문자열이고 여기서는 서식만 입힌다(`noClientSideFinance`).
 * - 투자 수익 = 평가액 − 총 납입 원금, 수익률 = 투자 수익 ÷ 총 납입 원금(서버가 낸다)
 * - 기준 줄은 결과가 어느 조건의 것인지 말한다 — 기준일·투자처·세율과 지금 적금(가입·금리·만기·낸 회차)·지금 예금(가입·금리)
 * - 손익을 색만으로 구별하지 않는다 — 부호를 함께 쓴다
 */

import { formatAnnualRate, formatMoneyWithSymbol, formatPercent, taxPercent } from "@/lib/format";
import type { InstallmentSummary } from "@/lib/types";

const won = (v: string) => formatMoneyWithSymbol(v, "KRW");
const signed = (v: string) => (v.trimStart().startsWith("-") ? won(v) : `+${won(v)}`);
const minus = (v: string) => won(v.startsWith("-") ? v : `-${v}`);

function basisLine(summary: InstallmentSummary, institutionName: string, taxRate: string): string {
  const parts = [`${summary.asOf} 기준`, institutionName, `세율 ${taxPercent(taxRate)}`];
  const saving = summary.currentInstallment;
  if (saving !== null) {
    parts.push(`지금 적금 ${saving.joinedOn} 가입 · ${formatAnnualRate(saving.rate)} · 만기 ${saving.maturesOn}`
      + `(${saving.paid}/12회)`);
  }
  const held = summary.currentDeposit;
  if (held !== null) parts.push(`지금 예금 ${held.joinedOn} 가입 · ${formatAnnualRate(held.rate)}`);
  return parts.join(" · ");
}

export function InstallmentBoard({
  summary,
  institutionName,
  taxRate,
}: {
  summary: InstallmentSummary;
  institutionName: string;
  /** 결과에 쓴 이자 소득세율(조건의 `interestTaxRate`). */
  taxRate: string;
}) {
  const loss = summary.profit.trimStart().startsWith("-");
  return (
    <section className="rounded-lg border border-gray-200">
      <div className="grid gap-px bg-gray-200 sm:grid-cols-6">
        <Cell label="총 납입 원금" notes={[`${summary.installments.toLocaleString("en-US")}회 납입`]}>
          {won(summary.contributed)}
        </Cell>
        <Cell label="세후 이자 합계"
          notes={[`적금 ${won(summary.installmentAfterTax)} · 예금 ${won(summary.depositAfterTax)}`]}>
          {signed(summary.afterTaxTotal)}
        </Cell>
        <Cell label="이자 소득세 합계">{minus(summary.taxTotal)}</Cell>
        <Cell label="평가액"
          notes={[`적금 ${won(summary.installmentValue)} · 예금 ${won(summary.depositValue)}`]}>
          {won(summary.balance)}
        </Cell>
        <Cell label="투자 수익" emphasis={loss ? "loss" : "gain"}>{signed(summary.profit)}</Cell>
        <Cell label="수익률" emphasis={loss ? "loss" : "gain"}>{formatPercent(summary.returnRate)}</Cell>
      </div>
      <p data-testid="installment-basis" className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {basisLine(summary, institutionName, taxRate)}
      </p>
    </section>
  );
}

function Cell({
  label,
  children,
  emphasis,
  notes = [],
}: {
  label: string;
  children: React.ReactNode;
  emphasis?: "gain" | "loss";
  notes?: string[];
}) {
  return (
    <div role="group" aria-label={label} className="bg-white px-4 py-3">
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
