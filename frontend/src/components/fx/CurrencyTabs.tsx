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
    // 컨테이너에 옅은 배경을 둔다. 없으면 활성 탭의 `bg-white`가 **흰 페이지 배경 위
    // 흰색**이 되어 선택 상태가 보이지 않는다. 분절 컨트롤의 표준 형태는 컨테이너가
    // 회색, 활성 항목이 흰색이다 — 후자만 있으면 절반만 가져온 것이다.
    <div
      role="tablist"
      aria-label="통화 선택"
      className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5"
    >
      {CURRENCIES.map(({ code, name }) => {
        const active = code === value;
        return (
          <button
            key={code}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(code)}
            className={`rounded-md px-4 py-2 text-sm transition ${
              active
                ? "bg-white font-semibold text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {code} <span className="text-xs text-gray-400">({name})</span>
          </button>
        );
      })}
    </div>
  );
}
