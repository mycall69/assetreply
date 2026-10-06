"use client";

/**
 * 투자 방식·주기 칸 (011 T027) — FR-001, FR-002, SC-009, ui-wireframes §1.
 *
 * 투자 방식은 스토어의 `plan`이다 — 일시금 입력 다섯 칸(`input`)과 따로 둔다(research R11-11). 적립식이면 주기 선택과 "언제 넣는지" 안내가
 * 나온다. 안내는 날짜를 계산하지 않는다(서버가 정한다 — `recurringText`).
 */

import { useId } from "react";
import { frequencyNote } from "@/lib/recurringText";
import type { Frequency, InvestmentPlan } from "@/lib/types";

const FREQUENCY_TEXT: Record<Frequency, string> = {
  daily: "매일",
  weekly: "매주",
  monthly: "매달",
  yearly: "매년",
};

const FREQUENCIES: Frequency[] = ["daily", "weekly", "monthly", "yearly"];

export function InvestmentModeFields({
  value,
  start,
  asset,
  disabled = false,
  onChange,
}: {
  value: InvestmentPlan;
  /** 안내 문장의 요일·날짜 — 조건 폼의 시작일. */
  start: string;
  asset: "stock" | "crypto";
  disabled?: boolean;
  onChange: (next: InvestmentPlan) => void;
}) {
  const name = useId();
  const recurring = value.mode === "recurring";
  return (
    <div className="flex flex-wrap items-end gap-4 text-sm">
      <fieldset className="flex items-center gap-3">
        <legend className="mb-1 text-gray-500">투자 방식</legend>
        {(["lump_sum", "recurring"] as const).map((mode) => (
          <label key={mode} className="flex items-center gap-1.5">
            <input
              type="radio"
              name={name}
              value={mode}
              checked={value.mode === mode}
              disabled={disabled}
              onChange={() => onChange({ ...value, mode })}
            />
            {mode === "lump_sum" ? "일시금" : "적립식"}
          </label>
        ))}
      </fieldset>
      {recurring && (
        <>
          <label>
            <span className="mb-1 block text-gray-500">주기</span>
            <select
              aria-label="납입 주기"
              value={value.frequency}
              disabled={disabled}
              onChange={(e) => onChange({ mode: "recurring", frequency: e.target.value as Frequency })}
              className="rounded border border-gray-300 px-2 py-1.5"
            >
              {FREQUENCIES.map((f) => (
                <option key={f} value={f}>{FREQUENCY_TEXT[f]}</option>
              ))}
            </select>
          </label>
          <p className="flex gap-1 pb-1.5 text-xs text-gray-500">
            <span aria-hidden="true">ⓘ</span>
            <span>{frequencyNote(value.frequency, start, asset)}</span>
          </p>
        </>
      )}
    </div>
  );
}

export { FREQUENCY_TEXT };
