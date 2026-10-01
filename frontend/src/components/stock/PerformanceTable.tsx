"use client";

/**
 * 성과 표 (T043, T048) — 005 FR-024~030, contracts/ui-wireframes.md W4.
 *
 * **월 행의 배당 칸은 비어 있다**(FR-026). 0을 넣으면 "배당이 0원"과 "배당이 없음"을
 * 구별할 수 없다 — 002·003·004가 세운 규약과 같다.
 *
 * **스크롤로 이어 본다**(FR-029). `더 보기` 버튼을 두지 않는다. 004가 세운 방식이며,
 * 감시 지점이 처음부터 보이면 스크롤 없이도 시작된다.
 *
 * 손익을 **색만으로 구별하지 않는다.** 부호를 함께 쓴다 (접근성).
 */

import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { formatMoney, formatPercent, formatRate, formatYield } from "@/lib/format";
import type { SimulationRow } from "@/lib/types";

const COLUMNS = [
  "날짜", "시작가", "주당 배당금", "배당율", "구매 주식수", "보유 주식",
  "예수금", "투자금", "잔고", "투자 수익", "수익율",
] as const;

export function PerformanceTable({
  rows,
  currency,
  hasMore,
  loadingMore = false,
  loadError = null,
  onLoadMore,
}: {
  rows: SimulationRow[];
  currency: string;
  hasMore: boolean;
  loadingMore?: boolean;
  loadError?: string | null;
  onLoadMore: () => void;
}) {
  // 실패한 동안에는 감시를 끊는다. 즉시 다시 관찰하면 같은 오류를 무한히 반복한다.
  const open = hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              {COLUMNS.map((c, i) => (
                <th
                  key={c}
                  scope="col"
                  className={`whitespace-nowrap px-3 py-2.5 font-normal ${
                    i === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.date}:${row.kind}`}
                data-kind={row.kind}
                className={`border-b border-gray-100 last:border-0 ${
                  row.kind === "dividend" ? "bg-amber-50/40" : ""
                }`}
              >
                <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                  {row.date}
                  {row.kind === "dividend" && (
                    <span title="배당락일" className="ml-1 text-amber-700">
                      ◆
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatRate(row.openPrice)}
                </td>
                {/* 월 행은 키 자체가 없다 — 빈 칸이 "배당 없음"을 뜻한다. */}
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.dividendPerShare !== undefined
                    ? formatMoney(row.dividendPerShare, currency)
                    : ""}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.dividendYield !== undefined
                    ? formatYield(row.dividendYield)
                    : ""}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.boughtShares}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {row.heldShares}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatMoney(row.cash, currency)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatMoney(row.principal, currency)}
                </td>
                <td className="px-3 py-2 text-right font-medium tabular-nums">
                  {formatMoney(row.balance, currency)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatMoney(row.profit, currency)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatPercent(row.returnRate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 이어 보기 상태 — 004의 방식. `더 보기` 버튼이 없는 만큼 상태를 말로 알린다. */}
      <div className="flex items-center justify-center gap-3 border-t border-gray-100 px-4 py-3 text-xs">
        <span role="status" aria-live="polite" className="text-gray-500">
          {loadError
            ? loadError
            : loadingMore
              ? "⟳ 불러오는 중…"
              : !hasMore
                ? `${rows.at(-1)?.date ?? "처음"}까지 모두 표시했습니다`
                : ""}
        </span>
        {loadError !== null && (
          <button
            type="button"
            onClick={onLoadMore}
            className="rounded border border-gray-300 px-2.5 py-1 text-gray-700 hover:bg-gray-50"
          >
            다시 시도
          </button>
        )}
      </div>

      {hasMore && loadError === null && (
        <div ref={sentinel} data-testid="scroll-sentinel" aria-hidden="true" className="h-px" />
      )}
    </div>
  );
}
