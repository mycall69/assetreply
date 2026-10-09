"use client";

/**
 * 지표 카드 (014 T039) — FR-004~FR-007, FR-009, FR-015, FR-018, contracts D1·D2.
 *
 * 값·차이·등락률은 서버 문자열에 형식만 입힌다(원칙 VI — 값 `formatRate`, 등락률 `formatPercent`의 천 단위 쉼표). 오르면 ▲ 빨강,
 * 내리면 ▼ 파랑, 변화 없음은 회색이다(013 비교 표와 같은 색) — 색만으로 구별하지 않는다.
 *
 * 카드의 위쪽은 지표 화면 링크다(접근 이름 "{이름} 추이 보기"). [다시 시도]는 링크 밖에 둔다 — 링크 안의 단추는 누를 때 화면을
 * 옮긴다.
 */
import Link from "next/link";
import { QuoteStateLine } from "@/components/dashboard/QuoteStateLine";
import { formatKst, formatPercent, formatRate } from "@/lib/format";
import type { DashboardIndicator, DashboardQuote } from "@/lib/types";

const RATE_BLANK: Record<NonNullable<DashboardQuote["changeRateBlank"]>, string> = {
  non_positive_base: "직전 값이 0 이하라 등락률을 낼 수 없습니다",
  no_previous: "전일 값을 알 수 없습니다",
};

function tone(direction: DashboardQuote["direction"]): string {
  if (direction === "up") return "text-red-700";
  if (direction === "down") return "text-blue-700";
  return "text-gray-500";
}

function changeText(quote: DashboardQuote): string {
  if (quote.change === null) return "—";
  const magnitude = formatRate(quote.change.replace(/^-/, ""));
  if (quote.direction === "up") return `▲ ${magnitude}`;
  if (quote.direction === "down") return `▼ ${magnitude}`;
  return magnitude;
}

export function IndicatorCard({ indicator, onRetry }: { indicator: DashboardIndicator; onRetry: () => void }) {
  const quote = indicator.quote;
  return (
    <li data-testid="indicator-card" data-indicator={indicator.id}
      className="flex min-w-[13rem] flex-1 basis-56 flex-col rounded-lg border border-gray-200 p-4">
      <Link href={`/dashboard/${indicator.id}`} aria-label={`${indicator.name} 추이 보기`}
        className="block rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900">
        <p className="flex items-baseline justify-between gap-2">
          <span className="font-medium text-gray-900">{indicator.name}</span>
          <span className="text-xs text-gray-500">{indicator.unit}</span>
        </p>
        <p data-testid="card-value" className="mt-1 text-xl font-semibold tabular-nums">
          {quote ? formatRate(quote.value) : "—"}
        </p>
        {quote && (
          <p data-testid="card-change" className={`flex gap-3 text-sm tabular-nums ${tone(quote.direction)}`}>
            <span>{changeText(quote)}</span>
            {quote.changeRate !== null ? (
              <span data-testid="card-rate">{formatPercent(quote.changeRate)}</span>
            ) : (
              <span data-testid="card-rate"
                title={quote.changeRateBlank ? RATE_BLANK[quote.changeRateBlank] : undefined}>—</span>
            )}
          </p>
        )}
        {quote && <QuoteStateLine indicator={indicator} quote={quote} />}
      </Link>
      {(indicator.stale || indicator.status === "failed") && (
        <div className="mt-2 space-y-1 text-xs text-amber-800">
          {indicator.stale && quote && (
            <p data-testid="card-stale">새로 받지 못함 · {formatKst(quote.valueTime)}</p>
          )}
          {indicator.failure && <p>{indicator.failure.message}</p>}
          <button type="button" onClick={onRetry} className="text-gray-700 underline">다시 시도</button>
        </div>
      )}
    </li>
  );
}
