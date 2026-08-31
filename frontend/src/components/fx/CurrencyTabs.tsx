"use client";

/** 통화 분절 컨트롤 (T030) — FR-006. 코드와 한글 이름을 함께 제시한다. */

import type { CurrencyCode } from "@/lib/apiClient";

const CURRENCIES: ReadonlyArray<{ code: CurrencyCode; name: string }> = [
  { code: "USD", name: "미국 달러" },
  { code: "JPY", name: "일본 엔" },
  { code: "EUR", name: "유로" },
];

export function CurrencyTabs({
  value,
  onChange,
}: {
  value: CurrencyCode;
  onChange: (c: CurrencyCode) => void;
}) {
  return (
    <div role="tablist" aria-label="통화 선택" className="inline-flex rounded-lg border border-gray-300">
      {CURRENCIES.map(({ code, name }) => {
        const active = code === value;
        return (
          <button
            key={code}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(code)}
            className={`px-4 py-2 text-sm first:rounded-l-lg last:rounded-r-lg ${
              active ? "bg-white font-semibold text-gray-900 shadow-sm" : "text-gray-500"
            }`}
          >
            {code} <span className="text-xs text-gray-400">({name})</span>
          </button>
        );
      })}
    </div>
  );
}
