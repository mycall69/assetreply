"use client";

/**
 * 성과 보드 (T042, T078, T099) — 005 FR-031, FR-032, FR-014b, FR-041.
 * contracts/ui-wireframes.md W2. 006 FR-054 — 원금·수익에 원금 통화의 기호(`10,000,000₩`).
 *
 * **기준 구간을 함께 쓴다.** 계산의 마지막 날이 오늘이 아니면(상장폐지·거래정지)
 * 그 사실이 드러나야 한다 — 알리지 않으면 사용자는 보드를 **오늘까지의 결과**로
 * 읽는다. 상장폐지는 대개 큰 손실인데 화면에는 폐지 직전의 수익률이 남는다.
 *
 * **기준 통화를 밝힌다**(FR-041). 밝히지 않으면 사용자가 어느 쪽을 보고 있는지 모른다.
 *
 * 손익을 **색만으로 구별하지 않는다.** 부호를 함께 쓴다 (접근성).
 */

import { formatMoneyWithSymbol, formatPercent, formatRate } from "@/lib/format";
import type { ExchangeInfo, SimulationSummary } from "@/lib/types";

export function PerformanceBoard({
  summary,
  currency,
  exchange,
}: {
  summary: SimulationSummary;
  currency: string;
  exchange?: ExchangeInfo;
}) {
  const negative = summary.profit.trimStart().startsWith("-");

  return (
    <section className="rounded-lg border border-gray-200">
      <div className="grid gap-px bg-gray-200 sm:grid-cols-3">
        <Cell label="투자 원금">
          {formatMoneyWithSymbol(summary.principal, currency)}
        </Cell>
        <Cell label="투자 수익" emphasis={negative ? "loss" : "gain"}>
          {formatMoneyWithSymbol(summary.profit, currency)}
        </Cell>
        <Cell label="수익률" emphasis={negative ? "loss" : "gain"}>
          {formatPercent(summary.returnRate)}
        </Cell>
      </div>

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {/* FR-031 — 어느 날짜까지의 결과인지 알 수 없으면 오늘까지로 읽는다. */}
        <span className="tabular-nums">{summary.asOf}</span> 기준 ·{" "}
        <span>{currency} 기준</span>
      </p>

      {!summary.isFinal && (
        // FR-014b — 계산의 마지막 날이 오늘이 아니다. 알리지 않으면 폐지 직전
        // 수익률을 오늘 값으로 읽는다.
        <p
          role="status"
          className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800"
        >
          ⚠ {summary.asOf} 이후 시세가 없습니다. 그 날짜까지의 결과입니다.
        </p>
      )}

      {exchange !== undefined && (
        // FR-021, FR-022 — 적용된 환율과 그 날짜가 드러나야 한다. 투자 시작일에
        // 고시가 없었다면 날짜가 다를 수 있다.
        <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
          환전 <span className="tabular-nums">{exchange.rateDate}</span> 현금 살 때{" "}
          <span className="tabular-nums">{formatRate(exchange.rate)}</span>
          <span className="ml-1">
            (스프레드 {formatPercent(exchange.spreadDiscount, 0).replace("+", "")} 우대)
          </span>
        </p>
      )}
    </section>
  );
}

function Cell({
  label,
  children,
  emphasis,
}: {
  label: string;
  children: React.ReactNode;
  emphasis?: "gain" | "loss";
}) {
  return (
    <div className="bg-white px-4 py-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold tabular-nums ${
          emphasis === "loss"
            ? "text-blue-700"
            : emphasis === "gain"
              ? "text-red-700"
              : "text-gray-900"
        }`}
      >
        {children}
      </p>
    </div>
  );
}
