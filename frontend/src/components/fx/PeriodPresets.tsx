"use client";

/**
 * 기간 프리셋 (T040) — FR-015.
 *
 * 6단계(1개월/6개월/1년/5년/10년/전체). 일 단위 데이터에서 하루·일주일 구간은 표시할
 * 점이 너무 적어 추이로서 의미가 없으므로 제외했다 (spec Assumptions).
 */

import { PRESETS, type Preset } from "@/stores/fxWorkspaceStore";

export function PeriodPresets({
  value,
  onChange,
}: {
  value: Preset;
  onChange: (p: Preset) => void;
}) {
  return (
    <div role="group" aria-label="기간 선택" className="flex gap-1">
      {PRESETS.map(({ key, label }) => {
        const active = key === value;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(key)}
            className={`rounded px-2.5 py-1 text-xs ${
              active ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
