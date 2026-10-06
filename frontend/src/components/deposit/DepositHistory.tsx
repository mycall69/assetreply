"use client";

/**
 * 예금 최근 시뮬레이션 (T032) — 008 FR-037, ui-wireframes D6. 007 `CryptoHistory`와 같은 줄이다 — 고르기·다시 실행·삭제.
 *
 * - 한 줄은 **투자처·시작일·원금**이다. 011 — 적금 항목은 "정기 적금 · 월 ₩…"이다(같은 조건의 정기예금 줄과 구별된다)
 * - **보관 위치를 알린다** — 다른 기기에서 열었을 때 사라진 것으로 오해하지 않게 한다(005 FR-037a)
 * - **수익률을 줄에 적지 않는다** — 결과는 세율·금리가 바뀌면 달라진다(005 R5-9)
 */

import { formatMoney, formatMoneyWithSymbol } from "@/lib/format";
import type { DepositHistoryEntry } from "@/lib/types";
import { INSTITUTION_NAMES } from "@/stores/depositStore";

const MIN_TO_COMPARE = 2;

/** 투자처 이름. 이력이 모르는 키를 담고 있으면 키 그대로 보인다 — 지어내지 않는다. */
export const institutionLabel = (key: string): string =>
  (INSTITUTION_NAMES as Record<string, string>)[key] ?? key;

export function DepositHistory({
  entries,
  selected,
  comparing,
  saveError,
  onToggle,
  onRemove,
  onCompare,
  onRerun,
}: {
  entries: DepositHistoryEntry[];
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
          ⓘ 이 브라우저에만 저장됩니다. 브라우저 데이터를 지우면 함께 사라집니다. 주식·가상자산 이력과 따로입니다.
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
            const label = institutionLabel(entry.institution);
            return (
              <li key={entry.id} data-testid="history-row" className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                <input type="checkbox" checked={selected.includes(entry.id)}
                  onChange={() => onToggle(entry.id)} aria-label={`${label} 비교 대상으로 선택`} />
                <span className="min-w-24 font-medium">{label}</span>
                <span className="tabular-nums text-gray-600">{entry.start}</span>
                {entry.product === "installment" ? (
                  // 011 FR-033 — 상품과 월 납입액. 같은 조건의 정기예금 행과 구별된다.
                  <span className="tabular-nums text-gray-600">
                    정기 적금 · 월 {formatMoneyWithSymbol(entry.principal, "KRW")}
                  </span>
                ) : (
                  <span className="tabular-nums text-gray-600">{formatMoney(entry.principal, "KRW")}원</span>
                )}
                <button type="button" onClick={() => onRerun(entry.id)}
                  aria-label={`${label} 다시 실행`}
                  className="rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50">
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
