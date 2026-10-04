"use client";

/**
 * 예금 이자 소득세율 설정 (T026) — 008 FR-030, FR-031, ui-wireframes D7.
 *
 * 화면은 **백분율**, 계약은 **비율**이다. 변환은 가상자산 수수료와 같은 함수로 **문자열로** 한다(헌법 원칙 VI). 0 이상 100 미만이
 * 아니면 **저장을 막는다** — 조용히 0으로 떨어뜨리면 세금 없는 결과가 나오는데 값은 그럴듯하다. 백분율 소수 4자리를 넘어도 막는다 —
 * 저장할 때 조용히 반올림된다(반복 #2). 주식·가상자산 설정과 따로 저장한다.
 */

import { useState } from "react";
import { toPercent, toRate } from "@/components/settings/CryptoSettingsForm";
import type { DepositSettings } from "@/lib/types";

/** 기본 이자 소득세 15.4%(소득세 14% + 지방소득세 1.4%)의 비율. "기본값으로"가 보낸다. */
const DEFAULT_RATE = "0.154";

/** 백분율 소수 자릿수 상한 — 비율로 6자리, 저장 자릿수(`DECIMAL(9,6)`)와 같다(FR-030, 반복 #2). 가상자산 칸은 따로다. */
const MAX_PERCENT_PLACES = 4;

export function DepositSettingsForm({
  value,
  onSave,
}: {
  value: DepositSettings;
  onSave: (interestTaxRate: string) => void;
}) {
  const [tax, setTax] = useState(toPercent(value.interestTaxRate));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const rate = toRate(tax);
    if (rate === null) {
      setError("0 이상 100 미만의 숫자를 입력하세요.");
      return;
    }
    if ((tax.trim().split(".")[1] ?? "").length > MAX_PERCENT_PLACES) {
      // 저장 자릿수(비율 6자리)를 넘으면 조용히 반올림되어 넣은 세율과 달라진다(FR-030, 반복 #2).
      setError(`백분율 소수 ${MAX_PERCENT_PLACES}자리까지 입력하세요.`);
      return;
    }
    setError(null);
    onSave(rate);
  };

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">예금 이자 조건</h3>
        <span className="text-xs text-gray-500">{value.isDefault ? "기본값" : "변경됨"}</span>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">이자 소득세 (%)</span>
          <input type="text" inputMode="decimal" aria-label="이자 소득세" value={tax}
            onChange={(e) => setTax(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
        </label>
        <button type="button" onClick={submit}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
          저장
        </button>
        {!value.isDefault && (
          <button type="button"
            onClick={() => {
              setTax(toPercent(DEFAULT_RATE));
              setError(null);
              onSave(DEFAULT_RATE);
            }}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700">
            기본값으로
          </button>
        )}
      </div>
      {error !== null && <p role="alert" className="text-xs text-red-700">{error}</p>}
      <p className="text-xs text-gray-500">
        기본값 15.4% — 소득세 14% + 지방소득세 1.4%. 만기 이자에서 떼고, 주식의 배당 소득세와 따로입니다. 바꾸면 예금 시뮬레이션
        결과가 새 값으로 다시 계산됩니다.
      </p>
    </section>
  );
}
