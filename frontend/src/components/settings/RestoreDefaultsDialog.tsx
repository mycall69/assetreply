"use client";

/**
 * 기본값 복원 확인창 (T053) — contracts/ui-wireframes.md W4-a.
 *
 * FR-032: 되돌리기 전에 **무엇이 어떻게 바뀌는지** 보여주고 확인을 받는다.
 * "정말 하시겠습니까?"만 묻는 확인창은 사용자가 결과를 모른 채 누르게 한다.
 */

import type { DerivedRates } from "@/lib/types";

const FIELDS = [
  { key: "cashBuy", label: "현금 살 때" },
  { key: "cashSell", label: "현금 팔 때" },
  { key: "remitSend", label: "송금 보낼 때" },
  { key: "remitReceive", label: "송금 받을 때" },
] as const;

export function RestoreDefaultsDialog({
  scope,
  current,
  defaults,
  onConfirm,
  onCancel,
}: {
  /** 통화 코드 또는 `"all"` */
  scope: string;
  current: DerivedRates;
  defaults: DerivedRates;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const scopeLabel = scope === "all" ? "전 통화" : scope;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${scopeLabel} 스프레드 기본값 복원`}
        className="w-full max-w-md rounded-lg bg-white p-5 shadow-lg"
      >
        <h3 className="text-sm font-semibold">
          {scopeLabel} 스프레드를 기본값으로 되돌립니다
        </h3>

        <dl className="mt-4 space-y-1.5 text-sm">
          {FIELDS.map(({ key, label }) => {
            const from = current[key];
            const to = defaults[key];
            const same = from === to;
            return (
              <div
                key={key}
                data-testid={`diff-${key}`}
                className="flex items-center justify-between gap-3"
              >
                <dt className="text-gray-600">{label}</dt>
                <dd className="tabular-nums text-gray-900">
                  {from} → {to}
                  {same && <span className="ml-2 text-xs text-gray-400">(변화 없음)</span>}
                </dd>
              </div>
            );
          })}
        </dl>

        <p className="mt-4 text-xs text-amber-700">현재 입력값은 사라집니다.</p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-700"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded bg-gray-900 px-4 py-1.5 text-sm text-white"
          >
            되돌리기
          </button>
        </div>
      </div>
    </div>
  );
}
