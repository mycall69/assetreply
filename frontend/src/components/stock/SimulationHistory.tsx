"use client";

/**
 * 최근 시뮬레이션 (T089) — 005 FR-035~037b, SC-014, SC-018, ui-wireframes W5.
 *
 * **보관 위치를 알린다**(FR-037a). 알리지 않으면 사용자는 계정에 딸린 기록으로 여겨,
 * 다른 기기에서 열었을 때 사라진 것으로 오해한다. 비어 있을 때도 안내를 남기는
 * 이유가 그것이다 — 오해가 생기는 시점이 바로 "비어 있는 것을 봤을 때"다.
 *
 * **수익률을 줄에 적지 않는다.** 결과는 설정과 환율이 바뀌면 달라지는데, 이력에는
 * 조건만 남아 있다(R5-9). 저장 당시 수치를 적어 두면 지금 값인 것처럼 읽힌다.
 */

import { formatMoney } from "@/lib/format";
import { isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import type { SimulationHistoryEntry } from "@/lib/types";

const MIN_TO_COMPARE = 2;

export function SimulationHistory({
  entries,
  selected,
  comparing,
  saveError,
  onToggle,
  onRemove,
  onCompare,
  onRerun,
}: {
  entries: SimulationHistoryEntry[];
  selected: string[];
  comparing: boolean;
  saveError: string | null;
  onToggle: (id: string) => void;
  onRemove: (id: string) => void;
  onCompare: () => void;
  /** 010 FR-018 — 필수다. 선택이면 화면이 넘기기를 잊어도 버튼이 조용히 사라진다(주식에 처음부터 없던 결함의 모양). */
  onRerun: (id: string) => void;
}) {
  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">최근 시뮬레이션</h3>
        {/* FR-037a, SC-018 — 서버에 없다는 사실이 드러나야 한다. */}
        <p data-testid="history-notice" className="text-xs text-gray-500">
          ⓘ 이 브라우저에만 저장됩니다. 브라우저 데이터를 지우면 함께 사라집니다.
        </p>
      </header>

      {saveError !== null && (
        <p
          role="alert"
          className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          {saveError}
        </p>
      )}

      {entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">
          아직 실행한 시뮬레이션이 없습니다.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {entries.map((entry) => (
            <li
              key={entry.id}
              data-testid="history-row"
              className="flex items-center gap-3 py-2 text-sm"
            >
              <input
                type="checkbox"
                checked={selected.includes(entry.id)}
                onChange={() => onToggle(entry.id)}
                aria-label={`${entry.stock.name} 비교 대상으로 선택`}
              />
              <span className="min-w-28 font-medium">{entry.stock.name}</span>
              <span className="tabular-nums text-gray-600">{entry.start}</span>
              <span className="tabular-nums text-gray-600">
                {formatMoney(entry.principal, entry.principalCurrency)}{" "}
                {entry.principalCurrency}
              </span>
              {/* FR-036 — 재투자 여부가 안 보이면 같은 종목의 두 조건이 같은 줄이다. */}
              <span className="text-gray-600">
                재투자 {entry.reinvest ? "O" : "X"}
              </span>
              {!isAllowedPrincipal(entry.principalCurrency, entry.stock.currency) && (
                // 006 FR-050c — 005 시절의 막힌 조합. 지우지 않고 사유와 함께 남긴다.
                <span className="text-xs text-amber-700">
                  막힌 조합 — {principalRule(entry.stock.currency)}
                </span>
              )}
              {/* 010 FR-018 — 가상자산·예금·부동산과 같은 문구·자리. 막힌 조합 행에도 둔다(지금 규칙의 사유가 보인다). */}
              <button
                type="button"
                onClick={() => onRerun(entry.id)}
                aria-label={`${entry.stock.name} 다시 실행`}
                className="ml-auto rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50"
              >
                다시 실행
              </button>
              <button
                type="button"
                onClick={() => onRemove(entry.id)}
                aria-label={`${entry.stock.name} 이력 삭제`}
                className="rounded px-2 text-gray-400 hover:text-red-600"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onCompare}
          // 하나만 고른 비교는 비교가 아니다. 눌리면 사용자는 결과를 기다리게 된다.
          disabled={selected.length < MIN_TO_COMPARE || comparing}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
        >
          {comparing ? "비교하는 중…" : "선택 항목 비교"}
        </button>
      </div>
    </section>
  );
}
