"use client";

/**
 * 비교 표 (013 T036·T050·T057·T092) — FR-011, FR-011a, FR-012, FR-013, FR-014, ui-wireframes F5.
 *
 * 대상마다 한 줄이다 — 대상, 기준일, 투자 원금, 시작일 단가, 기준일 단가, 등락, 현재 가치, 비용, 투자 수익, 수익률.
 * 단가 열 셋(반복 2026-10-09)은 서버의 `comparison.unitPrice`다 — 주식은 상장국 통화의 수정주가, 가상자산은 시세 통화의 시가(유효 숫자),
 * 예금은 금리와 %p, 부동산은 그 달 시세. 오름·내림은 글자의 부호로 가른다(계산하지 않는다). 값은 서버의 `comparison` 블록 문자열에 형식만 입힌다 —
 * 표는 합·차이를 계산하지 않는다(헌법 원칙 VI, `tests/compareNoClientFinance`). 정렬은 소수 문자열 견주기다(`lib/decimalOrder`).
 *
 * 수집 중·실패 줄은 맨 아래이고 값 칸은 비운다 — 0이나 빈 막대로 보이면 그 대상이 진 것처럼 읽힌다(FR-013 실패 양상).
 */
import { ExternalLink } from "@/components/ExternalLink";
import type { TargetState } from "@/lib/compareBlock";
import { sortRows } from "@/lib/decimalOrder";
import {
  currencySymbol,
  formatAnnualRate,
  formatMoneyWithSymbol,
  formatPercent,
  formatPrice,
  formatRate,
} from "@/lib/format";
import type { CompareMethod, ComparisonBlock, MainBasis, ProvisionalKind, UnitPrice, UnitPricePoint } from "@/lib/types";
import type { SortKey, SortState } from "@/stores/compareStore";
import { COST_HELP, CostCell } from "./CostCell";

export interface CompareRow {
  key: string;
  name: string;
  href: string | null;
  state: TargetState;
}

/** 단가 칸 둘은 정렬 머리가 아니다 — 대상마다 날짜가 달라 견줄 뜻이 없다. 정렬은 "등락"(등락률)이다. */
type ColumnKey = SortKey | "unitStart" | "unitAsOf";

const COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: "name", label: "대상" },
  { key: "asOf", label: "기준일" },
  { key: "principal", label: "투자 원금" },
  { key: "unitStart", label: "시작일 단가" },
  { key: "unitAsOf", label: "기준일 단가" },
  { key: "unitChange", label: "등락" },
  { key: "currentValue", label: "현재 가치" },
  { key: "cost", label: "비용" },
  { key: "profit", label: "투자 수익" },
  { key: "returnRate", label: "수익률" },
];

const BASIS_TEXT: Record<MainBasis, string> = { after_sale: "매도 후", holding: "보유 중", unavailable: "—" };

const PROVISIONAL_TEXT: Record<ProvisionalKind, string> = {
  unpublished_rate: "미발표 달 금리",
  provisional_price: "잠정 시세",
  estimated_price: "추정 시세",
  not_final: "기준일이 계산 끝 전",
};

const won = (value: string | null): string => (value === null ? "—" : formatMoneyWithSymbol(value, "KRW"));

export const UNIT_HELP = "단가 등락은 1단위 가격만의 변화입니다 — 배당·수수료·세금·환율·적립 시점이 빠져 수익률과 다릅니다. "
  + "주식은 수정주가(분할 반영)입니다";

const MISSING_TEXT = { no_price: "값 없음", no_trades: "시세 없음 — 거래 없음" } as const;

/** 단가 글자 — 주식·부동산은 통화 금액, 가상자산은 유효 숫자(007), 금리는 `2.10%`. 부호가 있는 값은 부호를 앞에 둔다. */
function unitText(unit: UnitPrice, value: string): string {
  if (unit.kind === "rate") return formatAnnualRate(value);
  const currency = unit.currency ?? "KRW";
  if (unit.kind === "coin") {
    const shown = formatPrice(value);
    const negative = shown.startsWith("-");
    const symbol = currencySymbol(currency);
    const prefix = symbol === currency ? `${symbol} ` : symbol;
    return `${negative ? "-" : ""}${prefix}${negative ? shown.slice(1) : shown}`;
  }
  return formatMoneyWithSymbol(value, currency);
}

/** 금리·부동산은 달, 주식·가상자산은 날. */
const unitDate = (unit: UnitPrice, point: UnitPricePoint) =>
  (unit.kind === "rate" || unit.kind === "home" ? point.date.slice(0, 7) : point.date);

function UnitCell({ unit, point, testId, split }: {
  unit: UnitPrice | null; point: "start" | "asOf"; testId: string; split?: boolean;
}) {
  if (unit === null) return <td data-testid={testId} className="px-3 py-2 text-right align-top">—</td>;
  const p = unit[point];
  const marks = [p.provisional ? "⏳ 잠정" : null, p.estimated ? "⏳ 추정" : null].filter((m) => m !== null);
  return (
    <td data-testid={testId} className="px-3 py-2 text-right align-top tabular-nums">
      {p.value === null ? "—" : unitText(unit, p.value)}
      <p className="text-xs text-gray-500">{unitDate(unit, p)}</p>
      {p.value === null && p.missing !== undefined && p.missing !== null && (
        <p className="text-xs text-gray-500">{MISSING_TEXT[p.missing]}</p>
      )}
      {split === true && unit.split !== null && <p className="text-xs text-gray-500">분할 반영 {unit.split.ratio}</p>}
      {marks.length > 0 && <p className="text-xs text-amber-700">{marks.join(" · ")}</p>}
    </td>
  );
}

/** 0인가 — 글자로만 본다(`"0"`, `"-0.000000"`). */
const isZero = (value: string) => /^-?0*(\.0*)?$/.test(value.trim());

function ChangeCell({ unit }: { unit: UnitPrice | null }) {
  if (unit === null || unit.change === null) {
    return <td data-testid="unit-change" className="px-3 py-2 text-right align-top">—</td>;
  }
  const negative = unit.change.trimStart().startsWith("-");
  const flat = isZero(unit.change);
  const magnitude = negative ? unit.change.trimStart().slice(1) : unit.change;
  const tone = flat ? "text-gray-600" : negative ? "text-blue-700" : "text-red-700";
  const arrow = flat ? "" : negative ? "▼ " : "▲ ";
  const amount = unit.kind === "rate" ? `${formatRate(magnitude)}%p` : unitText(unit, magnitude);
  return (
    <td data-testid="unit-change" className={`px-3 py-2 text-right align-top tabular-nums ${tone}`}>
      {arrow}{amount}
      <p className="text-xs">{unit.changeRate === null ? "—" : formatPercent(unit.changeRate)}</p>
    </td>
  );
}

/** 정렬 값 — 이름·기준일은 글자, 나머지는 소수 문자열. */
function sortValue(block: ComparisonBlock, key: SortKey): string | null {
  switch (key) {
    case "principal": return block.principal.krw;
    case "currentValue": return block.currentValue;
    case "cost": return block.costs.total;
    case "profit": return block.profit;
    case "returnRate": return block.returnRate;
    // 등락률 — 예금(금리)은 등락률이 없어 %p 차이로 견준다(한 비교 안의 대상은 모두 같은 자산군이다).
    case "unitChange": return block.unitPrice === null ? null : block.unitPrice.changeRate ?? block.unitPrice.change;
    default: return null;
  }
}

/** 표의 줄 차례 — 계산된 줄을 정렬하고 나머지(수집 중·실패)는 맨 아래다. 최종 지표 막대도 이 차례를 쓴다(T057). */
export function sortedRows(rows: CompareRow[], sort: SortState | null): CompareRow[] {
  const done = rows.filter((r) => r.state.status === "ok");
  const rest = rows.filter((r) => r.state.status !== "ok");
  if (sort === null) return [...done, ...rest];
  const blockOf = (r: CompareRow) => (r.state.status === "ok" ? r.state.data.comparison : null);
  let ordered: CompareRow[];
  if (sort.key === "name" || sort.key === "asOf") {
    const text = (r: CompareRow) => (sort.key === "name" ? r.name : blockOf(r)?.asOf ?? "");
    const sign = sort.direction === "asc" ? 1 : -1;
    ordered = [...done].sort((a, b) => sign * text(a).localeCompare(text(b), "ko"));
  } else {
    ordered = sortRows(done, (r) => {
      const block = blockOf(r);
      return block === null ? null : sortValue(block, sort.key);
    }, sort.direction);
  }
  return [...ordered, ...rest];
}

function principalCell(block: ComparisonBlock, method: CompareMethod, summary: Record<string, unknown>) {
  const { amount, currency, krw } = block.principal;
  const main = currency === "KRW" || amount === null
    ? won(krw)
    : `${formatMoneyWithSymbol(amount, currency)} (${won(krw)})`;
  const notes: string[] = [];
  if (method === "hold" && typeof summary.buyPrice === "string") {
    notes.push(`매입가 ${won(summary.buyPrice)} · 취득 비용 포함`);
  }
  const count = typeof summary.contributions === "number" ? summary.contributions
    : typeof summary.installments === "number" ? summary.installments : null;
  if ((method === "recurring" || method === "installment") && count !== null) {
    notes.push(`총 납입 원금 · ${count.toLocaleString("en-US")}회 납입`);
  }
  return (
    <>
      <p className="tabular-nums">{main}</p>
      {notes.map((n) => <p key={n} className="text-xs text-gray-500">{n}</p>)}
    </>
  );
}

function OkCells({ row, block, method, summary }: {
  row: CompareRow; block: ComparisonBlock; method: CompareMethod; summary: Record<string, unknown>;
}) {
  const basis = BASIS_TEXT[block.mainBasis];
  const negative = block.profit !== null && block.profit.trimStart().startsWith("-");
  const tone = block.profit === null ? "" : negative ? "text-blue-700" : "text-red-700";
  return (
    <>
      <td className="px-3 py-2 align-top">
        <ExternalLink href={row.href} label={`${row.name} 새 탭에서 보기`}>{row.name}</ExternalLink>
        {block.fx !== null && (
          <p className="text-xs text-gray-500">
            {block.fx.currency} · {formatRate(block.fx.valuationRate)}({block.fx.valuationRateDate} ECOS 매매기준율)
          </p>
        )}
      </td>
      <td className="px-3 py-2 align-top tabular-nums">
        {block.asOf}
        {block.provisional.length > 0 && (
          <p className="text-xs text-amber-700">⏳ {block.provisional.map((k) => PROVISIONAL_TEXT[k]).join(" · ")}</p>
        )}
      </td>
      <td className="px-3 py-2 text-right align-top">{principalCell(block, method, summary)}</td>
      <UnitCell unit={block.unitPrice} point="start" testId="unit-start" split />
      <UnitCell unit={block.unitPrice} point="asOf" testId="unit-asof" />
      <ChangeCell unit={block.unitPrice} />
      <td className="px-3 py-2 text-right align-top tabular-nums">{won(block.currentValue)}</td>
      <td className="px-3 py-2 text-right align-top"><CostCell name={row.name} costs={block.costs} /></td>
      <td className={`px-3 py-2 text-right align-top tabular-nums ${tone}`}>
        {won(block.profit)}
        <p className="text-xs text-gray-500">{basis}</p>
      </td>
      <td className={`px-3 py-2 text-right align-top tabular-nums ${tone}`}>
        {block.returnRate === null ? "—" : formatPercent(block.returnRate)}
        <p className="text-xs text-gray-500">{basis}</p>
      </td>
    </>
  );
}

function PendingCells({ row, onRetry }: { row: CompareRow; onRetry: (key: string) => void }) {
  const { state } = row;
  let status: React.ReactNode = "계산 중…";
  if (state.status === "collecting") {
    const { missingFrom, missingThrough } = state.body;
    const range = missingFrom !== undefined && missingThrough !== undefined ? ` · ${missingFrom} ~ ${missingThrough} 받는 중` : "";
    const percent = state.progress !== null && state.progress.total > 0
      ? Math.floor((state.progress.done * 100) / state.progress.total) : null;
    status = (
      <>
        <span>수집 중{range}</span>
        {percent !== null && (
          <span role="progressbar" aria-label={`${row.name} 수집 진행`} aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={percent} className="ml-2 inline-block h-1.5 w-24 rounded bg-gray-200 align-middle">
            <span className="block h-1.5 rounded bg-blue-500" style={{ width: `${percent}%` }} />
          </span>
        )}
      </>
    );
  } else if (state.status === "failed") {
    status = (
      <>
        <span>수집 실패 — {state.reason}</span>
        <button type="button" className="ml-2 text-blue-700 underline" aria-label={`${row.name} 다시 시도`}
          onClick={() => onRetry(row.key)}>
          다시 시도
        </button>
      </>
    );
  }
  return (
    <>
      <td className="px-3 py-2 align-top">
        {row.name}
        <p className="text-xs text-gray-500">{status}</p>
      </td>
      {COLUMNS.slice(1).map((c) => <td key={c.key} className="px-3 py-2" />)}
    </>
  );
}

export function CompareTable({ rows, method, sort, onSort, onRetry }: {
  rows: CompareRow[];
  method: CompareMethod;
  sort: SortState | null;
  onSort: (key: SortKey) => void;
  onRetry: (key: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <p className="mb-1 text-xs text-gray-500">
        기준 통화 KRW · 열 머리를 눌러 정렬 · 매도 비용을 빼는 자산군은 기준일에 판다고 가정한 값입니다
      </p>
      <table aria-label="비교 표" className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-500">
            {COLUMNS.map((c) => {
              const active = sort?.key === c.key;
              const key = c.key;
              return (
                <th key={c.key} scope="col" className="px-3 py-2 font-medium"
                  aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : undefined}>
                  {key === "unitStart" || key === "unitAsOf" ? c.label : (
                    <button type="button" onClick={() => onSort(key)}>
                      {c.label}{active ? (sort.direction === "asc" ? " ▲" : " ▼") : ""}
                    </button>
                  )}
                  {c.key === "unitChange" && (
                    <span role="note" aria-label="등락 도움말" title={UNIT_HELP} className="ml-1 cursor-help text-gray-400">ⓘ</span>
                  )}
                  {c.key === "cost" && (
                    <span role="note" aria-label="비용 도움말" title={COST_HELP} className="ml-1 cursor-help text-gray-400">ⓘ</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows(rows, sort).map((row) => (
            <tr key={row.key} className="border-b border-gray-100">
              {row.state.status === "ok"
                ? <OkCells row={row} block={row.state.data.comparison} method={method} summary={row.state.data.summary} />
                : <PendingCells row={row} onRetry={onRetry} />}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
