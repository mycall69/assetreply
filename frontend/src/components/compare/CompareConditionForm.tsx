"use client";

/**
 * 비교의 공통 조건 (013 T036·T050) — FR-005~FR-009, ui-wireframes F3.
 *
 * 시작일·금액·통화·재투자는 **모든 대상에 같다** — 한 번만 정한다(SC-008). 시작일 칸은 메뉴의 `StartDateInput` 하나다(상한은 자산군의
 * 메뉴와 같다). 부동산은 금액이 없다 — 매입가는 대상마다 그 달 시세다(FR-008). 원금 통화는 원화 + 모든 대상의 통화가 같을 때 그 통화다.
 */
import { useLayoutEffect, useMemo, useRef } from "react";
import { StartDateInput } from "@/components/stock/StartDateInput";
import { allowedCurrencies } from "@/lib/compareCondition";
import { caretAfter, formatPrincipal, normalizePrincipal } from "@/lib/principalFormat";
import { kstToday, localYesterday, utcYesterday } from "@/lib/startDate";
import type { CompareAsset, CompareMethod, CompareTarget, PrincipalCurrency } from "@/lib/types";

interface Props {
  asset: CompareAsset;
  method: CompareMethod;
  start: string;
  amount: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  targets: CompareTarget[];
  methodFields?: React.ReactNode;
  onStart: (start: string) => void;
  onAmount: (amount: string) => void;
  onCurrency: (currency: PrincipalCurrency) => void;
  onReinvest: (reinvest: boolean) => void;
  onRun: () => void;
}

const AMOUNT_LABEL: Record<CompareMethod, string> = {
  lump_sum: "투자 원금", recurring: "한 번 납입액", deposit: "투자 원금", installment: "월 납입액", hold: "",
};

/** 시작일의 마지막 날 — 메뉴와 같다(주식 어제, 가상자산 UTC 어제, 예금·부동산 한국 시간 오늘). */
function limitFor(asset: CompareAsset): string {
  if (asset === "stock") return localYesterday();
  if (asset === "crypto") return utcYesterday();
  return kstToday();
}

export function CompareConditionForm(props: Props) {
  const { asset, method, start, amount, principalCurrency, reinvest, targets } = props;
  const limit = useMemo(() => limitFor(asset), [asset]);
  const currencies = allowedCurrencies(asset, targets);

  // 쉼표가 끼어들면 다시 그린 뒤 커서가 끝으로 튄다 — 메뉴의 원금 칸과 같은 처리다.
  const box = useRef<HTMLInputElement>(null);
  const pendingCaret = useRef<number | null>(null);
  useLayoutEffect(() => {
    if (pendingCaret.current !== null && box.current !== null) {
      box.current.setSelectionRange(pendingCaret.current, pendingCaret.current);
      pendingCaret.current = null;
    }
  });
  const changeAmount = (typed: string, caret: number | null) => {
    const raw = normalizePrincipal(typed);
    const digitsBefore = normalizePrincipal(typed.slice(0, caret ?? typed.length)).length;
    pendingCaret.current = caretAfter(formatPrincipal(raw), digitsBefore);
    props.onAmount(asset === "deposit" ? raw.replace(/\..*$/, "") : raw);
  };

  const enough = targets.length >= 2;
  return (
    <form className="space-y-3" onSubmit={(e) => {
      e.preventDefault();
      props.onRun();
    }}>
      {props.methodFields ?? null}
      <div className="flex flex-wrap items-end gap-4">
        <StartDateInput value={start} limit={limit} listedOn={null} startable={null}
          label={asset === "realestate" ? "매입일" : "시작일"} onChange={props.onStart} />

        {asset === "realestate" ? (
          <p className="pb-1.5 text-sm text-gray-500">매입가는 대상마다 그 달 시세입니다</p>
        ) : (
          <label className="text-sm">
            <span className="mb-1 block text-gray-500">{AMOUNT_LABEL[method]}</span>
            <input type="text" inputMode="numeric" ref={box} value={formatPrincipal(amount)}
              onChange={(e) => changeAmount(e.target.value, e.target.selectionStart)}
              className="w-36 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
          </label>
        )}

        {(asset === "stock" || asset === "crypto") && (
          <label className="text-sm">
            <span className="mb-1 block text-gray-500">통화</span>
            <select value={principalCurrency} onChange={(e) => props.onCurrency(e.target.value as PrincipalCurrency)}
              className="rounded border border-gray-300 px-2 py-1.5">
              {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}

        {asset === "stock" && (
          <label className="inline-flex items-center gap-1.5 pb-1.5 text-sm">
            <input type="checkbox" checked={reinvest} onChange={(e) => props.onReinvest(e.target.checked)} />
            배당 재투자
          </label>
        )}

        <div className="pb-0.5">
          <button type="submit" disabled={!enough}
            className="rounded bg-gray-900 px-4 py-1.5 text-sm text-white disabled:cursor-not-allowed disabled:opacity-40">
            비교 실행
          </button>
          {!enough && <p className="mt-1 text-xs text-gray-500">비교하려면 대상이 2개 이상이 필요합니다</p>}
        </div>
      </div>
    </form>
  );
}
