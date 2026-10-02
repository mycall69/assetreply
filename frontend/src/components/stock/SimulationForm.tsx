"use client";

/**
 * 시뮬레이션 조건 입력 (T041) — 005 FR-001, FR-003, contracts/ui-wireframes.md W1.
 *
 * 원금을 **문자열로 들고 있다가 문자열로 보낸다.** 숫자로 바꾸면 그 순간 IEEE 754를
 * 거쳐 헌법 원칙 VI가 입력 단계에서 무너진다.
 */

import {
  StartDateInput,
  isStartBlocked,
  type Startable,
} from "@/components/stock/StartDateInput";
import type { PrincipalCurrency } from "@/lib/types";

const CURRENCIES: readonly PrincipalCurrency[] = ["KRW", "USD", "JPY", "EUR"];

export interface FormValues {
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
}

export function SimulationForm({
  values,
  disabled,
  limit,
  listedOn = null,
  startable = null,
  onChange,
  onSubmit,
}: {
  values: FormValues;
  disabled: boolean;
  /** 시작일의 마지막 날 — 어제 (006 FR-004). */
  limit: string;
  /** 고른 종목의 상장일. 하한일 뿐이다 (006 FR-005a). */
  listedOn?: string | null;
  /** 실행 뒤 서버가 알려 준 시작 가능 날짜 (006 FR-005). */
  startable?: Startable | null;
  onChange: (next: FormValues) => void;
  onSubmit: () => void;
}) {
  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) =>
    onChange({ ...values, [key]: value });
  // 실행 전에 막는다 — 미래이거나 하한보다 이른 시작일은 서버가 거절할 요청이다.
  const startBlocked = isStartBlocked(values.start, limit, listedOn, startable);

  return (
    <form
      className="flex flex-wrap items-end gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <StartDateInput
        value={values.start}
        limit={limit}
        listedOn={listedOn}
        startable={startable}
        onChange={(start) => set("start", start)}
      />

      <label className="text-sm">
        <span className="mb-1 block text-gray-500">투자 원금</span>
        <input
          type="text"
          inputMode="numeric"
          value={values.principal}
          onChange={(e) => set("principal", e.target.value)}
          className="w-36 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums"
        />
      </label>

      <label className="text-sm">
        <span className="mb-1 block text-gray-500">통화</span>
        <select
          value={values.principalCurrency}
          onChange={(e) =>
            set("principalCurrency", e.target.value as PrincipalCurrency)
          }
          className="rounded border border-gray-300 px-2 py-1.5"
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 py-1.5 text-sm">
        <input
          type="checkbox"
          checked={values.reinvest}
          onChange={(e) => set("reinvest", e.target.checked)}
        />
        배당 재투자
      </label>

      <button
        type="submit"
        disabled={disabled || startBlocked}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white disabled:bg-gray-400"
      >
        시뮬레이션
      </button>
    </form>
  );
}
