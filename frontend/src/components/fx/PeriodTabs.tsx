"use client";

/**
 * 기간 단위 분절 컨트롤 (T027) — 004 FR-006, FR-007, contracts/ui-wireframes.md W1.
 *
 * 002의 `CurrencyTabs`와 **같은 형태**를 쓴다 — 컨테이너가 회색, 활성 항목이 흰색.
 * 통화 선택기와 같은 모양이라 사용자가 한 번만 익히면 된다.
 *
 * 컨테이너의 옅은 배경이 없으면 활성 항목의 `bg-white`가 **흰 페이지 배경 위 흰색**이
 * 되어 선택 상태가 보이지 않는다. 002에서 실제로 겪은 결함이다.
 *
 * 색만으로 구별하지 않는다. 굵기가 함께 달라야 흑백·저대비에서도 읽힌다.
 */

import type { PeriodUnit } from "@/lib/types";

const UNITS: ReadonlyArray<{ unit: PeriodUnit; label: string; title: string }> = [
  { unit: "daily", label: "일", title: "모든 고시일" },
  { unit: "weekly", label: "주", title: "그 주의 금요일 (없으면 그 주의 마지막 고시일)" },
  { unit: "monthly", label: "월", title: "그 달의 말일 (없으면 그 달의 마지막 고시일)" },
];

export function PeriodTabs({
  value,
  onChange,
}: {
  value: PeriodUnit;
  onChange: (unit: PeriodUnit) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="기간 단위 선택"
      className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5"
    >
      {UNITS.map(({ unit, label, title }) => {
        const active = unit === value;
        return (
          <button
            key={unit}
            type="button"
            role="tab"
            title={title}
            aria-selected={active}
            onClick={() => onChange(unit)}
            className={`rounded-md px-3 py-1 text-sm transition ${
              active
                ? "bg-white font-semibold text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
