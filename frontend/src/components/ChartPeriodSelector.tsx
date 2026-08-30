"use client";

/** 기간 프리셋과 직접 지정 (T082, FR-029) — contracts/ui-chart.md. */

import { useChartStore, type Preset } from "@/stores/chartStore";
import type { CurrencyCode } from "@/lib/apiClient";

const PRESETS: readonly { key: Preset; label: string }[] = [
  { key: "1m", label: "1개월" },
  { key: "1y", label: "1년" },
  { key: "5y", label: "5년" },
  { key: "all", label: "전체" },
];

const CURRENCIES: readonly CurrencyCode[] = ["USD", "JPY", "EUR"];

export function ChartPeriodSelector() {
  const { currency, preset, from, to, setCurrency, setPreset, setRange, fetchSeries } =
    useChartStore();

  return (
    <div className="flex flex-wrap items-end gap-6 rounded-lg border border-gray-200 p-4">
      <fieldset>
        <legend className="mb-2 text-sm text-gray-500">통화</legend>
        <div className="flex gap-4">
          {CURRENCIES.map((c) => (
            <label key={c} className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="chart-currency"
                checked={currency === c}
                onChange={() => setCurrency(c)}
              />
              {c}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm text-gray-500">기간</legend>
        <div className="flex gap-1">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPreset(p.key)}
              className={`rounded px-3 py-1.5 text-sm ${
                preset === p.key ? "bg-gray-900 text-white" : "border border-gray-300"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="flex items-center gap-2">
        <input
          type="date"
          value={from}
          onChange={(e) => setRange(e.target.value, to)}
          aria-label="시작일"
          className="rounded border border-gray-300 px-2 py-1.5 text-sm"
        />
        <span className="text-gray-400">~</span>
        <input
          type="date"
          value={to}
          onChange={(e) => setRange(from, e.target.value)}
          aria-label="종료일"
          className="rounded border border-gray-300 px-2 py-1.5 text-sm"
        />
      </div>

      <button
        type="button"
        onClick={() => void fetchSeries()}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white"
      >
        조회
      </button>
    </div>
  );
}
