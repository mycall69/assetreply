"use client";

/**
 * 비교 표의 비용 칸 (013 T036) — FR-011(명확화 4), ui-wireframes F5.
 *
 * 비용은 **기간 전체 비용**이다 — 합과 두 몫(이미 반영된 몫 · 기준일 매도 가정 몫). 몫을 나누지 않으면 사용자가 "현재 가치 − 비용"을 손에
 * 쥘 돈으로 읽어 같은 비용을 두 번 뺀다(FR-011 실패 양상). 펼치면 항목이 글자로 보인다. 메뉴가 비우는 항목은 "—"와 까닭이다 — 0으로
 * 메우지 않는다(원칙 V). 값은 서버 문자열에 형식만 입힌다(원칙 VI).
 */
import { useId, useState } from "react";
import { formatMoneyWithSymbol } from "@/lib/format";
import type { ComparisonCosts, CostItemKind } from "@/lib/types";

const KIND_TEXT: Record<CostItemKind, string> = {
  buy_fee: "매수 수수료",
  dividend_tax: "배당 소득세",
  interest_tax_matured: "만기 이자 소득세",
  interest_tax_open: "경과 이자 소득세",
  acquisition_tax: "취득세",
  education_tax: "지방교육세",
  rural_tax: "농어촌특별세",
  brokerage_buy: "매수 중개 보수",
  property_tax: "재산세",
  comprehensive_tax: "종합부동산세",
  sale_fee: "매도 수수료",
  transaction_tax: "증권거래세",
  capital_gains_tax: "양도소득세",
  crypto_tax: "가상자산 소득세",
  brokerage_sale: "매도 중개 보수",
  transfer_income_tax: "양도소득세",
  transfer_local_tax: "지방소득세",
};

const BLANK_TEXT: Record<string, string> = {
  outside_rules: "과세 시행일 뒤 — 세법 표 밖",
  outside_table: "세법 표 밖",
};

export const COST_HELP = "반영 몫은 현재 가치(부동산 취득 비용은 투자 원금)에 이미 들어 있습니다 — 그래서 현재 가치 − 비용 − 투자 원금은 투자 수익과 다릅니다. "
  + "매도 가정 몫은 기준일에 판다고 가정한 비용입니다.";

const won = (value: string | null): string => (value === null ? "—" : formatMoneyWithSymbol(value, "KRW"));
const minus = (value: string | null): string => (value === null || value === "0" ? won(value) : `-${won(value)}`);

export function CostCell({ name, costs }: { name: string; costs: ComparisonCosts }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const items = [...costs.reflected.items, ...(costs.sale?.items ?? [])];
  const blank = costs.sale?.blank ?? null;
  return (
    <div className="space-y-0.5">
      <p className="tabular-nums">{minus(costs.total)}</p>
      <p className="text-xs text-gray-500">반영 {won(costs.reflected.total)}</p>
      {costs.sale !== null && <p className="text-xs text-gray-500">매도 가정 {won(costs.sale.total)}</p>}
      {blank !== null && <p className="text-xs text-amber-700">{BLANK_TEXT[blank] ?? blank}</p>}
      <button type="button" className="text-xs text-blue-700 underline" aria-expanded={open} aria-controls={listId}
        aria-label={`${name} 비용 내역`} onClick={() => setOpen(!open)}>
        ⓘ 내역
      </button>
      {open && (
        <ul id={listId} aria-label={`${name} 비용 내역`} className="text-xs text-gray-600">
          {items.map((item, index) => (
            <li key={`${item.kind}-${index}`}>
              {KIND_TEXT[item.kind]} {won(item.amount)}{item.inPrincipal ? " (투자 원금에 포함)" : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
