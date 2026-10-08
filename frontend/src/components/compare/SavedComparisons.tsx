"use client";

/**
 * 저장한 비교 (013 T076) — FR-016~FR-019, ui-wireframes F9.
 *
 * 줄마다 이름, "자산군 · 대상 이름들"(셋 넘으면 "외 N개"), 시작일·방식, 저장 시각(한국 시간). **결과를 적지 않는다** — 저장한 것은 조건뿐이고, 결과는
 * 불러올 때 지금 데이터로 다시 계산된다(005 R5-9와 같은 까닭 — 적어 두면 지금 값인 것처럼 읽힌다).
 *
 * 안내는 메뉴 이력 칸(`HistoryNotice`)처럼 보관 위치를 말하되 보관 기간 대신 "지울 때까지 남습니다"다(명확화 3). 목록 받기 실패·불러오는 중·빈 목록은
 * 메뉴 이력 칸과 같은 부품(`HistoryContent`)이다. 저장·삭제 실패는 알림 문구다 — 결과는 그대로다(FR-019).
 */
import { FREQUENCY_TEXT } from "@/components/recurring/InvestmentModeFields";
import { HistoryContent } from "@/components/history/HistoryStates";
import { ASSET_LABEL, METHOD_LABEL, targetName } from "@/lib/compareCondition";
import { formatKst } from "@/lib/format";
import type { SavedComparison } from "@/lib/types";

/** 줄에 이름을 보일 대상 수 — 넘으면 "외 N개". */
const SHOWN_TARGETS = 3;

function targetsText(entry: SavedComparison): string {
  const names = entry.condition.targets.map(targetName);
  const shown = names.slice(0, SHOWN_TARGETS).join(", ");
  const rest = names.length - SHOWN_TARGETS;
  return `${ASSET_LABEL[entry.asset]} · ${shown}${rest > 0 ? ` 외 ${rest}개` : ""}`;
}

function methodText(entry: SavedComparison): string {
  const { start, method, frequency } = entry.condition;
  const plan = method === "recurring" && frequency !== null ? `${METHOD_LABEL[method]} ${FREQUENCY_TEXT[frequency]}` : METHOD_LABEL[method];
  return `${start} · ${plan}`;
}

export function SavedComparisons({
  entries, loading, loadError, saveError, removeError, onRetry, onLoad, onRemove,
}: {
  entries: SavedComparison[];
  loading: boolean;
  loadError: string | null;
  saveError: string | null;
  removeError: string | null;
  onRetry: () => void;
  onLoad: (id: number) => void;
  onRemove: (id: number) => void;
}) {
  return (
    <section aria-label="저장한 비교" className="rounded-lg border border-gray-200 p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">저장한 비교</h3>
        <p data-testid="saved-notice" className="text-xs text-gray-500">
          ⓘ 이 기기의 로컬 DB에 저장됩니다. 지울 때까지 남습니다.
        </p>
      </header>

      {[saveError, removeError].map((error) => error !== null && (
        <p key={error} role="alert"
          className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {error}
        </p>
      ))}

      <HistoryContent loading={loading} loadError={loadError} onRetry={onRetry} empty={entries.length === 0}
        emptyText="아직 저장한 비교가 없습니다.">
        <ul className="divide-y divide-gray-100">
          {entries.map((entry) => (
            <li key={entry.id} data-testid="saved-comparison" className="space-y-0.5 py-2 text-sm">
              <p data-testid="saved-name" className="font-medium">{entry.name}</p>
              <p className="text-gray-600">{targetsText(entry)}</p>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                <span className="tabular-nums">{methodText(entry)}</span>
                <span className="tabular-nums">{formatKst(entry.savedAt)} 저장</span>
                <button type="button" onClick={() => onLoad(entry.id)} aria-label={`${entry.name} 불러오기`}
                  className="rounded border border-gray-300 px-2 py-0.5 text-gray-700 hover:bg-gray-50">
                  불러오기
                </button>
                <button type="button" onClick={() => onRemove(entry.id)} aria-label={`${entry.name} 삭제`}
                  className="rounded px-2 text-gray-400 hover:text-red-600">
                  ×
                </button>
              </p>
            </li>
          ))}
        </ul>
      </HistoryContent>
    </section>
  );
}
