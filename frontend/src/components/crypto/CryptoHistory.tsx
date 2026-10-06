"use client";

/**
 * 가상자산 최근 시뮬레이션 (T044) — 007 FR-045, FR-046. 006의 `SimulationHistory`와 같은 규칙에 코인 표시와 다시 실행을 더했다.
 *
 * - 한 줄은 **코인 이름(한글이 있으면 한글)·심볼**·시작일·원금이다 — 같은 심볼의 다른 코인이 같은 줄로 보이면 안 된다(FR-004)
 * - 011 — 적립식 항목은 원금 자리에 "적립식 · 주기 한 번 납입액"을 보인다. 같은 조건의 일시금 줄과 구별된다
 * - **보관 위치를 알린다** — 다른 기기에서 열었을 때 사라진 것으로 오해하지 않게 한다(005 FR-037a)
 * - **수익률을 줄에 적지 않는다** — 결과는 설정과 환율이 바뀌면 달라진다(005 R5-9)
 */

import { ExternalLink } from "@/components/ExternalLink";
import { FREQUENCY_TEXT } from "@/components/recurring/InvestmentModeFields";
import { coinLink } from "@/lib/externalLinks";
import { formatMoney, formatMoneyWithSymbol } from "@/lib/format";
import { isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import type { CryptoHistoryEntry } from "@/lib/types";

const MIN_TO_COMPARE = 2;

export const coinLabel = (coin: { name: string; nameKo: string | null }) => coin.nameKo ?? coin.name;

export function CryptoHistory({
  entries,
  selected,
  comparing,
  saveError,
  onToggle,
  onRemove,
  onCompare,
  onRerun,
}: {
  entries: CryptoHistoryEntry[];
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
          ⓘ 이 브라우저에만 저장됩니다. 브라우저 데이터를 지우면 함께 사라집니다. 주식 이력과 따로입니다.
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
            const label = coinLabel(entry.coin);
            return (
              <li key={entry.id} data-testid="history-row" className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                <input type="checkbox" checked={selected.includes(entry.id)}
                  onChange={() => onToggle(entry.id)} aria-label={`${label} 비교 대상으로 선택`} />
                <span className="min-w-28 font-medium">
                  <ExternalLink href={coinLink(entry.coin)} label={`${label} 네이버 증권에서 보기`}>{label}</ExternalLink>
                </span>
                <span className="text-xs text-gray-500">{entry.coin.symbol}</span>
                <span className="tabular-nums text-gray-600">{entry.start}</span>
                {entry.mode === "recurring" ? (
                  // 011 FR-033 — 방식·주기·한 번 납입액. 같은 조건의 일시금 행과 구별된다.
                  <span className="tabular-nums text-gray-600">
                    적립식 · {FREQUENCY_TEXT[entry.frequency ?? "monthly"]}{" "}
                    {formatMoneyWithSymbol(entry.principal, entry.principalCurrency)}
                  </span>
                ) : (
                  <span className="tabular-nums text-gray-600">
                    {formatMoney(entry.principal, entry.principalCurrency)} {entry.principalCurrency}
                  </span>
                )}
                {!isAllowedPrincipal(entry.principalCurrency, entry.coin.currency) && (
                  // 지우지 않고 사유와 함께 남긴다 — 사용자가 고친 조건으로 다시 실행할 수 있다.
                  <span className="text-xs text-amber-700">막힌 조합 — {principalRule(entry.coin.currency)}</span>
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
