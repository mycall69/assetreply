"use client";

/**
 * 부동산 최근 시뮬레이션 (T050) — 009 FR-032, ui-wireframes E7. 008 `DepositHistory`와 같은 줄이다 — 고르기·다시 실행·삭제.
 *
 * - 한 줄은 **단지·평형·매입일·매입가**다. 매입가는 직접 넣었으면 금액, 아니면 "그 달 시세"
 * - **보관 위치를 알린다** — 다른 기기에서 열었을 때 사라진 것으로 오해하지 않게 한다(005 FR-037a)
 * - **수익률을 줄에 적지 않는다** — 결과는 거래·세법·비율이 바뀌면 달라진다(005 R5-9)
 * - 버튼·고르기의 이름은 단지·평형·매입일이다 — 같은 단지·평형을 다른 날 산 줄이 여럿일 수 있다
 */

import { formatMoney } from "@/lib/format";
import type { RealEstateHistoryEntry } from "@/lib/types";

const MIN_TO_COMPARE = 2;

export function RealEstateHistory({
  entries,
  selected,
  comparing,
  saveError,
  onToggle,
  onRemove,
  onCompare,
  onRerun,
}: {
  entries: RealEstateHistoryEntry[];
  selected: string[];
  comparing: boolean;
  saveError: string | null;
  onToggle: (id: string) => void;
  onRemove: (id: string) => void;
  onCompare: () => void;
  onRerun: (id: string) => void;
}) {
  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">최근 시뮬레이션</h3>
        <p data-testid="history-notice" className="text-xs text-gray-500">
          ⓘ 이 브라우저에만 저장됩니다. 브라우저 데이터를 지우면 함께 사라집니다. 다른 자산군 이력과 따로입니다.
        </p>
      </header>

      {saveError !== null && (
        <p role="alert" className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {saveError}
        </p>
      )}

      {entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">아직 실행한 시뮬레이션이 없습니다.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {entries.map((entry) => {
            const name = `${entry.complexName} ${entry.areaLabel}`;
            // 같은 단지·평형을 다른 날 산 줄을 가른다.
            const label = `${name} ${entry.buyDate}`;
            return (
              <li key={entry.id} data-testid="history-row" className="flex items-center gap-3 py-2 text-sm">
                <input type="checkbox" checked={selected.includes(entry.id)}
                  onChange={() => onToggle(entry.id)} aria-label={`${label} 비교 대상으로 선택`} />
                <span className="min-w-48 font-medium">{name}</span>
                <span className="tabular-nums text-gray-600">{entry.buyDate}</span>
                <span className="tabular-nums text-gray-600">
                  {entry.buyPrice === null ? "그 달 시세" : `${formatMoney(entry.buyPrice, "KRW")}원`}
                </span>
                <button type="button" onClick={() => onRerun(entry.id)}
                  aria-label={`${label} 다시 실행`}
                  className="ml-auto rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50">
                  다시 실행
                </button>
                <button type="button" onClick={() => onRemove(entry.id)} aria-label={`${label} 이력 삭제`}
                  className="rounded px-2 text-gray-400 hover:text-red-600">
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-3 flex justify-end">
        <button type="button" onClick={onCompare}
          // 하나만 고른 비교는 비교가 아니다.
          disabled={selected.length < MIN_TO_COMPARE || comparing}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40">
          {comparing ? "비교하는 중…" : "선택 항목 비교"}
        </button>
      </div>
    </section>
  );
}
