"use client";

/**
 * 주식 수수료·세율 설정 (T065) — 005 FR-015, FR-016, 006 FR-055(배당 소득세 국내·해외).
 *
 * 화면은 **백분율**로 받고 계약은 **비율**로 받는다. 변환을 이 파일 한 곳에 둔다 —
 * 흩뿌리면 한 군데만 틀려도 값이 100배 어긋나는데, 숫자가 그럴듯해 보인다.
 *
 * 숫자가 아니거나 범위를 벗어나면 **저장을 막는다.** 조용히 0으로 떨어뜨리면
 * 수수료·세금이 사라진 결과가 나오는데 값은 그럴듯하고 오류도 없다.
 */

import { useState } from "react";
import type { DecimalString, StockSettings } from "@/lib/types";

export interface StockSettingsChange {
  tradeFeeRate: DecimalString;
  dividendTaxRateDomestic: DecimalString;
  dividendTaxRateForeign: DecimalString;
}

/** 비율(0.000150) → 백분율 표시(0.015). 문자열 조작이라 정밀도를 잃지 않는다. */
function toPercent(rate: DecimalString): string {
  const value = Number(rate) * 100;
  return String(Number(value.toFixed(6)));
}

/** 백분율 입력(0.015) → 비율(0.00015). */
function toRate(percent: string): string | null {
  const trimmed = percent.trim();
  if (trimmed === "" || !/^\d*\.?\d+$/.test(trimmed)) return null;
  const value = Number(trimmed) / 100;
  if (!Number.isFinite(value) || value < 0 || value >= 1) return null;
  return String(Number(value.toFixed(8)));
}

export function StockSettingsForm({
  value,
  onSave,
}: {
  value: StockSettings;
  onSave: (change: StockSettingsChange) => void;
}) {
  const [fee, setFee] = useState(toPercent(value.tradeFeeRate));
  // 006 FR-055 — 국내(KRX)와 해외(그 밖)를 따로 받는다. 해외 종목에 국내 세율을 쓰면 세후 배당이 조용히 줄어든다.
  const [domesticTax, setDomesticTax] = useState(toPercent(value.dividendTaxRateDomestic));
  const [foreignTax, setForeignTax] = useState(toPercent(value.dividendTaxRateForeign));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const tradeFeeRate = toRate(fee);
    const dividendTaxRateDomestic = toRate(domesticTax);
    const dividendTaxRateForeign = toRate(foreignTax);
    if (tradeFeeRate === null || dividendTaxRateDomestic === null
      || dividendTaxRateForeign === null) {
      setError("0 이상 100 미만의 숫자를 입력하세요.");
      return;
    }
    setError(null);
    onSave({ tradeFeeRate, dividendTaxRateDomestic, dividendTaxRateForeign });
  };

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">주식 매매 조건</h3>
        <span className="text-xs text-gray-500">
          {value.isDefault ? "기본값" : "변경됨"}
        </span>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">매매 수수료 (%)</span>
          <input
            type="text"
            inputMode="decimal"
            aria-label="매매 수수료"
            value={fee}
            onChange={(e) => setFee(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">배당 소득세 · 국내 (%)</span>
          <input
            type="text"
            inputMode="decimal"
            aria-label="배당 소득세 (국내)"
            value={domesticTax}
            onChange={(e) => setDomesticTax(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-gray-500">배당 소득세 · 해외 (%)</span>
          <input
            type="text"
            inputMode="decimal"
            aria-label="배당 소득세 (해외)"
            value={foreignTax}
            onChange={(e) => setForeignTax(e.target.value)}
            className="w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums"
          />
        </label>
        <button
          type="button"
          onClick={submit}
          className="self-end rounded bg-gray-900 px-4 py-2 text-sm text-white"
        >
          저장
        </button>
      </div>

      {error !== null && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}

      <p className="text-xs text-gray-500">
        바꾸면 이미 표시된 시뮬레이션 결과가 새 값 기준으로 다시 계산됩니다.
      </p>
    </section>
  );
}
