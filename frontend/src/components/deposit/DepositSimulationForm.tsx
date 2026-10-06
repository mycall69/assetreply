"use client";

/**
 * 예금 시뮬레이션 조건 입력 (T021) — 008 FR-002, FR-004, FR-005, ui-wireframes D1.
 *
 * 가상자산 폼(`CryptoSimulationForm`)과 같되 **통화 칸·재투자 칸이 없다** — 원금은 원화만이고(FR-004) 만기마다 늘
 * 재예치한다(FR-002). 단위 "원"을 글자로 둔다. 시작일 상한은 **오늘(한국 시간)**이다(FR-005) — 예금은 오늘까지의 경과
 * 이자가 붙는다. 원금은 문자열로 들고 있다가 문자열로 보낸다(헌법 원칙 VI).
 */

import { useLayoutEffect, useRef } from "react";
import { StartDateInput, isStartBlocked, type Startable } from "@/components/stock/StartDateInput";
import { caretAfter, formatPrincipal, normalizePrincipal } from "@/lib/principalFormat";

export interface DepositFormValues {
  start: string;
  principal: string;
}

export function DepositSimulationForm({
  values,
  disabled,
  limit,
  startable = null,
  principalLabel = "투자 원금",
  onChange,
  onSubmit,
}: {
  values: DepositFormValues;
  disabled: boolean;
  /** 시작일의 마지막 날 — 오늘(한국 시간). */
  limit: string;
  startable?: Startable | null;
  /** 011 — 금액 칸의 이름. 정기예금이면 "투자 원금", 정기 적금이면 "월 납입액"이다(값·쉼표 처리는 같다). */
  principalLabel?: string;
  onChange: (next: DepositFormValues) => void;
  onSubmit: () => void;
}) {
  const startBlocked = isStartBlocked(values.start, limit, null, startable);

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
    // 원화에 소수점 금액은 없다 — 점 뒤를 버린다(서버도 원 단위 정수만 받는다).
    const raw = normalizePrincipal(typed).split(".")[0];
    const digitsBefore = normalizePrincipal(typed.slice(0, at ?? typed.length)).length;
    caret.current = caretAfter(formatPrincipal(raw), digitsBefore);
    onChange({ ...values, principal: raw });
  };

  return (
    <form className="flex flex-wrap items-end gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}>
      <StartDateInput value={values.start} limit={limit} listedOn={null} startable={startable}
        afterLimitText={`오늘(${limit})보다 뒤의 날짜는 계산할 수 없습니다.`}
        onChange={(start) => onChange({ ...values, start })} />

      <label className="text-sm">
        <span className="mb-1 block text-gray-500">{principalLabel}</span>
        <span className="flex items-center gap-1.5">
          <input type="text" inputMode="numeric" ref={box}
            value={formatPrincipal(values.principal)}
            onChange={(e) => changePrincipal(e.target.value, e.target.selectionStart)}
            className="w-36 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
          <span className="text-gray-600">원</span>
        </span>
      </label>

      <button type="submit" disabled={disabled || startBlocked}
        className="rounded bg-gray-900 px-5 py-2 text-sm text-white disabled:bg-gray-400">
        시뮬레이션
      </button>
    </form>
  );
}
