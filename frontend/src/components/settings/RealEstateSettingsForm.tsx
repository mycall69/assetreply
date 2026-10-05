"use client";

/**
 * 부동산 보유세 기준 비율 설정 (T044) — 009 FR-034, ui-wireframes E8.
 *
 * 화면은 **백분율**(60 %), 계약은 **비율**(`"0.600000"`)이다. 변환은 **문자열로** 한다(헌법 원칙 VI). **0 초과 100 이하**가 아니면
 * 저장을 막는다 — 0이면 보유세가 없는 결과가 그럴듯하게 나온다. 백분율 소수 4자리(비율 6자리)를 넘어도 막는다 — 저장할 때 조용히
 * 반올림되어 넣은 값과 달라진다(008과 같은 자릿수 규칙). 다른 자산군 설정과 따로 저장한다.
 */

import { useState } from "react";
import { toPercent } from "@/components/settings/CryptoSettingsForm";
import type { RealEstateSettings } from "@/lib/types";

/** 기본 보유세 기준 비율 60%의 비율. "기본값으로"가 보낸다. */
const DEFAULT_RATIO = "0.6";

/** 백분율 소수 자릿수 상한 — 비율로 6자리, 저장 자릿수와 같다(FR-034). */
const MAX_PERCENT_PLACES = 4;

/**
 * 백분율(`60.1234`) → 비율(`0.601234`). 0 초과 100 이하의 십진수가 아니면 `null`. 끝의 0을 지운다(60 → `"0.6"`, 100 → `"1"`).
 * 숫자로 바꾸지 않고 소수점만 옮긴다.
 */
export function toRatio(percent: string): string | null {
  const text = percent.trim();
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  const [whole, fraction = ""] = text.split(".");
  const digits = whole.replace(/^0+(?=\d)/, "");
  if (digits.length > 3) return null;
  if (digits.length === 3) {
    // 100까지만 — 100.5는 넘는다.
    return digits === "100" && !/[1-9]/.test(fraction) ? "1" : null;
  }
  const ratio = `0.${digits.padStart(2, "0")}${fraction}`.replace(/0+$/, "").replace(/\.$/, "");
  return ratio === "0" ? null : ratio;
}

export function RealEstateSettingsForm({
  value,
  onSave,
}: {
  value: RealEstateSettings;
  onSave: (holdingTaxBaseRatio: string) => void;
}) {
  const [ratio, setRatio] = useState(toPercent(value.holdingTaxBaseRatio));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const saved = toRatio(ratio);
    if (saved === null) {
      setError("0 초과 100 이하의 숫자를 입력하세요.");
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
        <h3 className="text-sm font-semibold">부동산 보유세 조건</h3>
        <span className="text-xs text-gray-500">{value.isDefault ? "기본값" : "변경됨"}</span>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">보유세 기준 비율 (%)</span>
          <input type="text" inputMode="decimal" aria-label="보유세 기준 비율" value={ratio}
            onChange={(e) => setRatio(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
        </label>
        <button type="button" onClick={submit}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
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
        기본값 60% — 실거래 시세의 60%를 공시가격으로 봅니다. 재산세·종부세의 기준 금액이고, 바꾸면 부동산 시뮬레이션 결과가 새 값으로
        다시 계산됩니다.
      </p>
    </section>
  );
}
