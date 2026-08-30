"use client";

/** 통화·날짜 선택 폼 (T055) — contracts/ui-sketches.md S1. */

import { useRateStore, yesterday } from "@/stores/rateStore";
import type { CurrencyCode } from "@/lib/apiClient";

const CURRENCIES: readonly CurrencyCode[] = ["USD", "JPY", "EUR"];

export function RateQueryForm() {
  const { currency, date, loading, setCurrency, setDate, fetchRate } = useRateStore();

  return (
    <form
      className="flex flex-wrap items-end gap-6 rounded-lg border border-gray-200 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        void fetchRate();
      }}
    >
      <fieldset>
        <legend className="mb-2 text-sm text-gray-500">통화</legend>
        <div className="flex gap-4">
          {CURRENCIES.map((c) => (
            <label key={c} className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="currency"
                value={c}
                checked={currency === c}
                onChange={() => setCurrency(c)}
              />
              {c}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="query-date" className="mb-2 block text-sm text-gray-500">
          날짜
        </label>
        <input
          id="query-date"
          type="date"
          value={date}
          max={yesterday()}
          onChange={(e) => setDate(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white disabled:opacity-50"
      >
        {loading ? "조회 중…" : "조회"}
      </button>
    </form>
  );
}
