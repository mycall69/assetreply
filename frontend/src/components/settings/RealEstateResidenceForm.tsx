"use client";

/**
 * 부동산 거주 기간 비율 설정 (010 반복 5, T081) — FR-031, contracts/rest-api `GET`·`PUT /api/realestate/settings/residence`.
 *
 * 거주 기간 = 보유 기간 × 이 비율이다 — 양도소득세 매도비용의 비과세 거주 2년 요건과 장기보유특별공제(1세대 1주택 표2)에 쓴다. 화면은
 * **백분율**(100 %), 계약은 **비율**(`"1.000000"`)이다. 보유세 기준 비율과 달리 **0%도 된다**(거주하지 않음). 0 이상 100 이하가 아니거나
 * 백분율 소수 4자리를 넘으면 저장을 막는다 — 조용히 반올림하면 넣은 값과 다른 세금이 나온다.
 */

import { useState } from "react";
import { toPercent } from "@/components/settings/CryptoSettingsForm";
import { toRatio } from "@/components/settings/RealEstateSettingsForm";
import type { RealEstateResidenceSetting } from "@/lib/types";

/** 기본 100% — 보유 내내 거주. "기본값으로"가 보낸다. */
const DEFAULT_RATIO = "1";
const MAX_PERCENT_PLACES = 4;

/** 백분율 → 비율. 0도 받는다(보유세 기준 비율의 `toRatio`는 0을 거절한다). */
function toResidenceRatio(percent: string): string | null {
  return toRatio(percent) ?? (/^0+(\.0+)?$/.test(percent.trim()) ? "0" : null);
}

export function RealEstateResidenceForm({
  value,
  onSave,
}: {
  value: RealEstateResidenceSetting;
  onSave: (residenceRatio: string) => void;
}) {
  const [ratio, setRatio] = useState(toPercent(value.residenceRatio));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const saved = toResidenceRatio(ratio);
    if (saved === null) {
      setError("0 이상 100 이하의 숫자를 입력하세요.");
      return;
    }
    if ((ratio.trim().split(".")[1] ?? "").length > MAX_PERCENT_PLACES) {
      setError(`백분율 소수 ${MAX_PERCENT_PLACES}자리까지 입력하세요.`);
      return;
    }
    setError(null);
    onSave(saved);
  };

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">부동산 양도소득세 조건</h3>
        <span className="text-xs text-gray-500">{value.isDefault ? "기본값" : "변경됨"}</span>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">거주 기간 비율 (%)</span>
          <input type="text" inputMode="decimal" aria-label="거주 기간 비율" value={ratio}
            onChange={(e) => setRatio(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
        </label>
        <button type="button" onClick={submit} className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
          저장
        </button>
        {!value.isDefault && (
          <button type="button"
            onClick={() => {
              setRatio(toPercent(DEFAULT_RATIO));
              setError(null);
              onSave(DEFAULT_RATIO);
            }}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700">
            기본값으로
          </button>
        )}
      </div>
      {error !== null && <p role="alert" className="text-xs text-red-700">{error}</p>}
      <p className="text-xs text-gray-500">
        기본값 100% — 거주 기간 = 보유 기간 × 이 비율. 1세대 1주택·부부 5:5로 계산하는 양도소득세(비과세의 거주 2년 요건, 장기보유특별공제의
        거주분)에 쓰고, 바꾸면 부동산 보드의 매도비용이 새 값으로 다시 계산됩니다.
      </p>
    </section>
  );
}
