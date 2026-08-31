"use client";

/**
 * 설정 — 외화 스프레드 (T054, T055) — contracts/ui-wireframes.md W4.
 *
 * 001의 별도 스프레드 탭을 여기로 옮겼다. 저장·복원 후에는 외환 화면의 요약과 표만
 * 다시 받는다 — **차트는 매매기준율만 그리므로 무관하다** (갱신 범위 표).
 */

import { useEffect, useState } from "react";
import { RestoreDefaultsDialog } from "@/components/settings/RestoreDefaultsDialog";
import { SpreadForm } from "@/components/settings/SpreadForm";
import type { DerivedRates, SpreadRow } from "@/lib/types";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";
import { useSpreadStore } from "@/stores/spreadStore";

type Values = Record<"cashBuy" | "cashSell" | "remitSend" | "remitReceive", string>;

const ZERO: DerivedRates = {
  cashBuy: "0", cashSell: "0", remitSend: "0", remitReceive: "0",
};

export default function SettingsPage() {
  const { data, message, error, load, save, restore } = useSpreadStore();
  const reloadRates = useFxWorkspaceStore((s) => s.reloadRates);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  const onSave = async (changes: Record<string, Values>) => {
    await save(changes);
    // 외환 화면의 파생 환율을 새 값으로 다시 산출한다 (FR-034).
    await reloadRates();
  };

  const onConfirmRestore = async () => {
    if (pending === null) return;
    await restore(pending);
    await reloadRates();
    setPending(null);
  };

  const dialogValues = (): { current: DerivedRates; defaults: DerivedRates } => {
    if (data === null || pending === null) return { current: ZERO, defaults: ZERO };
    if (pending === "all") {
      // 전 통화 복원은 대표로 첫 통화의 변화를 보여준다. 범위는 제목이 밝힌다.
      return { current: data.spreads[0] ?? ZERO, defaults: data.defaults[0] ?? ZERO };
    }
    const pick = (rows: SpreadRow[]) => rows.find((r) => r.currency === pending) ?? ZERO;
    return { current: pick(data.spreads), defaults: pick(data.defaults) };
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h2 className="text-xl font-bold tracking-tight">외화 스프레드</h2>

      {error && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {message && <p className="text-sm text-gray-600">{message}</p>}

      {data && (
        <SpreadForm
          rows={data.spreads}
          defaults={data.defaults}
          onSave={(changes) => void onSave(changes)}
          onRestore={(scope) => setPending(scope)}
        />
      )}

      {pending !== null && (
        <RestoreDefaultsDialog
          scope={pending}
          {...dialogValues()}
          onConfirm={() => void onConfirmRestore()}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}
