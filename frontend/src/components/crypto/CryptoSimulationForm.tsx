"use client";

/**
 * 가상자산 시뮬레이션 조건 입력 (T033) — 007 FR-002, FR-007~FR-009, ui-wireframes C1.
 *
 * 주식 폼(`SimulationForm`)과 같되 **배당 재투자 칸이 없다** — 배당이 없다. 시작일 상한은 **UTC 어제**다(FR-022). 원금은
 * 문자열로 들고 있다가 문자열로 보낸다(헌법 원칙 VI). 원금 통화는 원화 또는 코인의 시세 통화뿐이다(FR-007).
 */

import { useLayoutEffect, useRef } from "react";
import { StartDateInput, isStartBlocked, type Startable } from "@/components/stock/StartDateInput";
import { allowedPrincipals, isAllowedPrincipal, principalRule } from "@/lib/principalCurrency";
import { caretAfter, formatPrincipal, normalizePrincipal } from "@/lib/principalFormat";
import type { PrincipalCurrency } from "@/lib/types";

export interface CryptoFormValues {
  start: string;
  principal: string;
  principalCurrency: PrincipalCurrency;
}

export function CryptoSimulationForm({
  values,
  disabled,
  limit,
  startable = null,
  quoteCurrency = null,
  onChange,
  onSubmit,
}: {
  values: CryptoFormValues;
  disabled: boolean;
  /** 시작일의 마지막 날 — UTC 어제. */
  limit: string;
  startable?: Startable | null;
  /** 고른 코인의 시세 통화. 원금 통화의 선택지를 정한다. */
  quoteCurrency?: string | null;
  onChange: (next: CryptoFormValues) => void;
  onSubmit: () => void;
}) {
  const set = <K extends keyof CryptoFormValues>(key: K, value: CryptoFormValues[K]) =>
    onChange({ ...values, [key]: value });
  const startBlocked = isStartBlocked(values.start, limit, null, startable);
  const currencies = allowedPrincipals(quoteCurrency);
  const currencyAllowed = isAllowedPrincipal(values.principalCurrency, quoteCurrency);

  // 쉼표가 끼어들면 커서가 끝으로 튄다 — 고친 자리를 기억해 두었다가 되돌린다(006 FR-053과 같다).
  const box = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);
  useLayoutEffect(() => {
    if (caret.current !== null && box.current !== null) {
      box.current.setSelectionRange(caret.current, caret.current);
      caret.current = null;
    }
  });
  const changePrincipal = (typed: string, at: number | null) => {
    const raw = normalizePrincipal(typed);
    const digitsBefore = normalizePrincipal(typed.slice(0, at ?? typed.length)).length;
    caret.current = caretAfter(formatPrincipal(raw), digitsBefore);
    set("principal", raw);
  };

  return (
    <form className="flex flex-wrap items-end gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}>
      <StartDateInput value={values.start} limit={limit} listedOn={null} startable={startable}
        onChange={(start) => set("start", start)} />

      <label className="text-sm">
        <span className="mb-1 block text-gray-500">투자 원금</span>
        <input type="text" inputMode="numeric" ref={box}
          value={formatPrincipal(values.principal)}
          onChange={(e) => changePrincipal(e.target.value, e.target.selectionStart)}
          className="w-36 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
      </label>

      <div className="text-sm">
        <label>
          <span className="mb-1 block text-gray-500">통화</span>
          <select value={values.principalCurrency}
            onChange={(e) => set("principalCurrency", e.target.value as PrincipalCurrency)}
            className="rounded border border-gray-300 px-2 py-1.5">
            {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
            {!currencyAllowed && (
              // 지금 값을 그대로 보인다 — 선택지에서 사라지면 화면이 몰래 다른 통화를 보인다.
              <option value={values.principalCurrency} disabled>{values.principalCurrency}</option>
            )}
          </select>
        </label>
        {!currencyAllowed && (
          <p role="alert" className="mt-1 text-xs text-amber-800">
            ⚠ 이 코인은 {principalRule(quoteCurrency)}. 통화를 다시 고르세요.
          </p>
        )}
      </div>

      <button type="submit" disabled={disabled || startBlocked || !currencyAllowed}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white disabled:bg-gray-400">
        시뮬레이션
      </button>
    </form>
  );
}
