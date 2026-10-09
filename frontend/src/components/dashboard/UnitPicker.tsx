/**
 * 그래프 단위 단추 (014 T060) — FR-011, contracts D3.
 *
 * 단위는 **점 하나가 나타내는 기간**이다(명확화 1). 고른 단추는 `aria-pressed="true"`다.
 */
import type { IndicatorUnit } from "@/lib/types";

const UNITS: { unit: IndicatorUnit; label: string }[] = [
  { unit: "daily", label: "일" },
  { unit: "weekly", label: "주" },
  { unit: "monthly", label: "월" },
  { unit: "yearly", label: "년" },
];

export function UnitPicker({ value, onChange }: { value: IndicatorUnit; onChange: (unit: IndicatorUnit) => void }) {
  return (
    <div role="group" aria-label="그래프 단위" className="inline-flex rounded border border-gray-300">
      {UNITS.map(({ unit, label }) => (
        <button key={unit} type="button" aria-pressed={value === unit} onClick={() => onChange(unit)}
          className={`px-4 py-1.5 text-sm ${value === unit ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-50"}`}>
          {label}
        </button>
      ))}
    </div>
  );
}
