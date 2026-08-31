"use client";

/**
 * 외화 스프레드 설정 폼 (T052) — contracts/ui-wireframes.md W4.
 *
 * FR-027: USD → JPY → EUR 순서는 고정이다. 정렬 옵션을 두지 않는다.
 * FR-029: 범위 위반은 **해당 입력 바로 아래**에서 알린다. 상단에 모아 보여주면 어느
 * 칸이 문제인지 사용자가 찾아야 한다.
 * FR-035: 현재 값이 모든 과거 날짜에 적용된다는 사실을 화면이 밝혀야 한다.
 *
 * 값은 문자열로 유지한다. `Number()`를 거치면 헌법 원칙 VI가 입력 단계에서 무너진다.
 */

import { useState } from "react";
import type { SpreadRow } from "@/lib/types";

const FIELDS = [
  { key: "cashBuy", label: "현금 살 때" },
  { key: "cashSell", label: "현금 팔 때" },
  { key: "remitSend", label: "송금 보낼 때" },
  { key: "remitReceive", label: "송금 받을 때" },
] as const;

type FieldKey = (typeof FIELDS)[number]["key"];
type Values = Record<FieldKey, string>;

/** 허용 범위는 0 이상 1 미만 (FR-029). 문자열 비교가 아니라 수치 판정이 필요한 자리다. */
function invalidReason(raw: string): string | null {
  if (raw.trim() === "") return "값을 입력하세요.";
  const n = Number(raw);
  if (Number.isNaN(n)) return "숫자를 입력하세요.";
  if (n < 0 || n >= 1) return "0 이상 1 미만이어야 합니다. 저장되지 않았습니다.";
  return null;
}

export function SpreadForm({
  rows,
  defaults,
  onSave,
  onRestore,
}: {
  rows: SpreadRow[];
  defaults: SpreadRow[];
  onSave: (changes: Record<string, Values>) => void;
  onRestore: (scope: string) => void;
}) {
  const [draft, setDraft] = useState<Record<string, Values>>(() => initialDraft(rows));
  const [errors, setErrors] = useState<Record<string, Partial<Record<FieldKey, string>>>>({});

  const save = () => {
    const found: Record<string, Partial<Record<FieldKey, string>>> = {};
    for (const row of rows) {
      const perField: Partial<Record<FieldKey, string>> = {};
      for (const { key } of FIELDS) {
        const reason = invalidReason(draft[row.currency][key]);
        if (reason) perField[key] = reason;
      }
      if (Object.keys(perField).length > 0) found[row.currency] = perField;
    }
    setErrors(found);
    // 하나라도 범위를 벗어나면 **아무것도 바꾸지 않는다**. 일부만 반영되면 사용자가
    // 의도한 조합과 다른 상태가 남는다 (FR-029).
    if (Object.keys(found).length === 0) onSave(draft);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-xs text-gray-600">
          여기서 정한 값이 <strong>모든 과거 날짜에 동일하게 적용</strong>됩니다. 시점별
          이력은 관리하지 않습니다 — 과거에 실제로 적용됐던 스프레드는 알 수 없기
          때문입니다. 화면의 파생 환율은 &ldquo;현재 조건을 과거에 적용한 가정&rdquo;입니다.
        </p>
        <button
          type="button"
          onClick={() => onRestore("all")}
          className="shrink-0 rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
        >
          전체 기본값 복원
        </button>
      </div>

      {rows.map((row) => {
        const base = defaults.find((d) => d.currency === row.currency);
        const rowErrors = errors[row.currency] ?? {};
        return (
          <section
            key={row.currency}
            data-testid={`spread-${row.currency}`}
            className="rounded-lg border border-gray-200 p-4"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{row.currency}</h3>
              <div className="flex items-center gap-2">
                {row.isDefault === false && (
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                    기본값과 다름
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => onRestore(row.currency)}
                  className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                >
                  기본값 복원
                </button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {FIELDS.map(({ key, label }) => {
                const id = `${row.currency}-${key}`;
                const error = rowErrors[key];
                const baseValue = base?.[key];
                const differs = baseValue !== undefined && draft[row.currency][key] !== baseValue;
                return (
                  <div key={key}>
                    <label htmlFor={id} className="text-xs text-gray-600">
                      {row.currency} {label}
                    </label>
                    <input
                      id={id}
                      value={draft[row.currency][key]}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          [row.currency]: { ...d[row.currency], [key]: e.target.value },
                        }))
                      }
                      className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5 text-sm tabular-nums"
                    />
                    {differs && baseValue && (
                      <p className="mt-1 text-[11px] text-gray-400">← 기본값 {baseValue}</p>
                    )}
                    {error && (
                      <p role="alert" className="mt-1 text-xs text-red-600">
                        ⚠ {error}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

          </section>
        );
      })}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setDraft(initialDraft(rows))}
          className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-700"
        >
          취소
        </button>
        <button
          type="button"
          onClick={save}
          className="rounded bg-gray-900 px-5 py-1.5 text-sm text-white"
        >
          저장
        </button>
      </div>
    </div>
  );
}

function initialDraft(rows: SpreadRow[]): Record<string, Values> {
  return Object.fromEntries(
    rows.map((r) => [
      r.currency,
      { cashBuy: r.cashBuy, cashSell: r.cashSell, remitSend: r.remitSend, remitReceive: r.remitReceive },
    ]),
  );
}
