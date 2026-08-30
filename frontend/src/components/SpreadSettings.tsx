"use client";

/**
 * 스프레드 설정 화면 (T070) — contracts/ui-sketches.md S5.
 *
 * FR-025: 범위(0 이상 1 미만)를 벗어나면 저장하지 않고 기존 값을 유지한다.
 * FR-026: 현재 설정값이 모든 과거 날짜에 적용됨을 화면에서 밝힌다.
 */

import { useState } from "react";
import type { CurrencyCode, DerivedRates, SpreadRow } from "@/lib/types";

const COLUMNS = [
  { key: "cashBuy", label: "현금 살 때" },
  { key: "cashSell", label: "현금 팔 때" },
  { key: "remitSend", label: "송금 보낼 때" },
  { key: "remitReceive", label: "송금 받을 때" },
] as const;

type Draft = Record<CurrencyCode, DerivedRates>;

/** 0 이상 1 미만인지 검사한다. 문자열 그대로 비교해 정밀도를 잃지 않는다. */
function isValid(raw: string): boolean {
  if (!/^\d*\.?\d+$/.test(raw.trim())) return false;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 && n < 1;
}

export function SpreadSettings({
  rows,
  onSave,
}: {
  rows: SpreadRow[];
  onSave: (currency: CurrencyCode, values: DerivedRates) => void;
}) {
  const [draft, setDraft] = useState<Draft>(
    () =>
      Object.fromEntries(
        rows.map((r) => [r.currency, { ...r, currency: undefined } as unknown as DerivedRates]),
      ) as Draft,
  );
  const [errors, setErrors] = useState<string[]>([]);

  const handleSave = () => {
    const bad: string[] = [];
    for (const row of rows) {
      for (const col of COLUMNS) {
        if (!isValid(draft[row.currency][col.key])) {
          bad.push(`${row.currency} ${col.label}`);
        }
      }
    }
    setErrors(bad);
    if (bad.length > 0) return;
    for (const row of rows) onSave(row.currency, draft[row.currency]);
  };

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-base font-semibold">스프레드 설정</h2>
        <p className="mt-1 text-sm text-gray-500">
          단위: 비율 (0.0018 = 0.18%). 0 이상 1 미만.
        </p>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-500">
            <th className="py-2 font-normal">통화</th>
            {COLUMNS.map((c) => (
              <th key={c.key} className="py-2 font-normal">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.currency} className="border-b border-gray-100">
              <td className="py-2 font-medium">{row.currency}</td>
              {COLUMNS.map((col) => {
                const id = `${row.currency}-${col.key}`;
                const value = draft[row.currency][col.key];
                const invalid = errors.includes(`${row.currency} ${col.label}`);
                return (
                  <td key={col.key} className="py-2 pr-3">
                    <label htmlFor={id} className="sr-only">
                      {row.currency} {col.label}
                    </label>
                    <input
                      id={id}
                      value={value}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          [row.currency]: { ...d[row.currency], [col.key]: e.target.value },
                        }))
                      }
                      className={`w-28 rounded border px-2 py-1 tabular-nums ${
                        invalid ? "border-red-500" : "border-gray-300"
                      }`}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {errors.length > 0 && (
        <p role="alert" className="text-sm text-red-600">
          스프레드는 0 이상 1 미만이어야 합니다 — {errors.join(", ")}. 저장되지 않았습니다.
        </p>
      )}

      <div className="rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        ⓘ 여기 설정한 값이 <strong>모든 과거 날짜</strong>의 조회에 동일하게 적용됩니다.
        시점별 스프레드 이력은 관리하지 않습니다.
      </div>

      <button
        type="button"
        onClick={handleSave}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white"
      >
        저장
      </button>
    </section>
  );
}
