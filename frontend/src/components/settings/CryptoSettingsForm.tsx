"use client";

/**
 * 가상자산 거래 수수료율 설정 (T033) — 007 FR-032, FR-033, ui-wireframes C6.
 *
 * 화면은 **백분율**, 계약은 **비율**이다. 변환은 이 파일에서 **문자열로** 한다(헌법 원칙 VI) — `0.1 / 100`을 부동소수점으로 하면
 * `0.001`이 아닌 값이 저장될 수 있다. 0 이상 100 미만이 아니면 **저장을 막는다** — 조용히 0으로 떨어뜨리면 수수료 없는 결과가
 * 나오는데 값은 그럴듯하다. 주식 설정과 따로 저장한다.
 */

import { useState } from "react";
import { shiftDecimal } from "@/lib/format";
import type { CryptoSettings, DecimalString } from "@/lib/types";

/** 기본 거래 수수료 0.1%의 비율. "기본값으로"가 보낸다. */
const DEFAULT_RATE = "0.001";

/** 비율(`0.001000`) → 백분율(`0.1`). 뒤의 0을 지운다. */
export function toPercent(rate: DecimalString): string {
  const shifted = shiftDecimal(rate, 2);
  return shifted.includes(".") ? shifted.replace(/0+$/, "").replace(/\.$/, "") : shifted;
}

/** 백분율(`0.25`) → 비율(`0.0025`). 0 이상 100 미만의 십진수가 아니면 `null`. */
export function toRate(percent: string): string | null {
  const text = percent.trim();
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  const [whole, fraction = ""] = text.split(".");
  const digits = whole.replace(/^0+(?=\d)/, "");
  if (digits.length > 2) return null; // 100 이상
  const padded = digits.padStart(2, "0");
  const result = `0.${padded}${fraction}`.replace(/0+$/, "").replace(/\.$/, "");
  return result === "0" || result === "" ? "0" : result;
}

export function CryptoSettingsForm({
  value,
  onSave,
}: {
  value: CryptoSettings;
  onSave: (tradeFeeRate: string) => void;
}) {
  const [fee, setFee] = useState(toPercent(value.tradeFeeRate));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const rate = toRate(fee);
    if (rate === null) {
      setError("0 이상 100 미만의 숫자를 입력하세요.");
      return;
    }
    setError(null);
    onSave(rate);
  };

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">가상자산 거래 조건</h3>
        <span className="text-xs text-gray-500">{value.isDefault ? "기본값" : "변경됨"}</span>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">거래 수수료 (%)</span>
          <input type="text" inputMode="decimal" aria-label="거래 수수료" value={fee}
            onChange={(e) => setFee(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
        </label>
        <button type="button" onClick={submit}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
          저장
        </button>
        {!value.isDefault && (
          <button type="button"
            onClick={() => {
              setFee(toPercent(DEFAULT_RATE));
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
        매수 금액에 더해 예수금에서 빠집니다. 주식 매매 수수료와 따로입니다. 바꾸면 시뮬레이션 결과가 새 값으로 다시 계산됩니다.
      </p>
    </section>
  );
}
