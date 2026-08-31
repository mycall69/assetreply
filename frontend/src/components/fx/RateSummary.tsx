/**
 * 요약 카드 (T031) — contracts/ui-wireframes.md W2.
 *
 * FR-011: 오늘 잠정값이 있으면 그것을, 없으면 마지막 확정값을 가장 큰 비중으로 제시한다.
 * FR-013: 상승·하락을 방향 기호와 색으로 **함께** 구분한다. 색 하나에만 의존하면
 * 색각 이상 사용자가 읽을 수 없다.
 * FR-014: 잠정인지 확정인지 값 근처에서 드러나야 한다.
 */

import { formatRate, unitLabel } from "@/lib/format";
import type { LatestResponse } from "@/lib/types";

const ARROW = { up: "▲", down: "▼", flat: "─" } as const;

export function RateSummary({ latest }: { latest: LatestResponse }) {
  if (latest.status === "no_data" || latest.baseRate === null) {
    return (
      <div className="rounded-lg border border-gray-200 p-5">
        <p className="text-sm text-gray-600">아직 수집된 데이터가 없습니다.</p>
      </div>
    );
  }

  const { change } = latest;
  const tone =
    change?.direction === "up"
      ? "text-red-600"
      : change?.direction === "down"
        ? "text-blue-600"
        : "text-gray-500";

  return (
    <div className="rounded-lg border border-gray-200 p-5">
      <p className="text-xs text-gray-500">
        매매기준율 ({latest.quotePair}) · {unitLabel(latest.quoteUnit)}
      </p>

      <div className="mt-2 flex flex-wrap items-baseline gap-3">
        <span className="text-4xl font-bold tracking-tight tabular-nums">
          {formatRate(latest.baseRate)}
        </span>
        {change && (
          <span data-testid="change" className={`text-sm font-medium ${tone}`}>
            {ARROW[change.direction]} {formatRate(change.absolute)} (
            {change.percent}%)
          </span>
        )}
      </div>

      <p data-testid="summary-meta" className="mt-2 text-xs text-gray-500">
        {latest.isProvisional ? (
          <>
            <span className="mr-1 rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
              ⚠ 잠정
            </span>
            {latest.date} {latest.fetchedAt ? `${latest.fetchedAt} 기준` : ""}
          </>
        ) : (
          <>확정 · {latest.date} 기준</>
        )}
      </p>
    </div>
  );
}
