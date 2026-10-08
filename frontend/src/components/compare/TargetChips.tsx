"use client";

/**
 * 고른 대상 칩 (013 T036) — FR-004, ui-wireframes F2.
 *
 * 칩 차례는 더한 차례다(표의 처음 차례 — FR-012). 대상마다 빼기 단추가 있다.
 */
import { targetKey, targetName } from "@/lib/compareCondition";
import type { CompareTarget } from "@/lib/types";

export function TargetChips({ targets, max, onRemove }: {
  targets: CompareTarget[];
  max: number;
  onRemove: (key: string) => void;
}) {
  return (
    <div className="space-y-1.5 text-sm">
      <p className="text-gray-500">비교 대상 ({targets.length}/{max})</p>
      {targets.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="고른 비교 대상">
          {targets.map((target) => {
            const key = targetKey(target);
            const name = targetName(target);
            return (
              <li key={key} className="inline-flex items-center gap-1 rounded-full border border-gray-300 px-3 py-0.5">
                <span>{name}</span>
                <button type="button" aria-label={`${name} 빼기`} onClick={() => onRemove(key)}
                  className="ml-1 text-gray-400 hover:text-red-600">
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-gray-400">ⓘ 최대 {max}개 · 2개 이상이어야 실행할 수 있습니다</p>
    </div>
  );
}
