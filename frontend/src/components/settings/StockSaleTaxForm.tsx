"use client";

/**
 * 주식 매도 세금 설정 (011 T054) — FR-035~FR-037, ui-wireframes §9.
 *
 * 세 칸이다 — 국내 매도 세율 · 해외 양도소득세율 · 해외 연간 기본공제. 칸마다 기본값과 그 근거(현행 세법)를 보인다. 보드가 기준일에 모두
 * 판다고 가정할 때만 쓴다 — 표·차트의 보유 중 값에는 들어가지 않는다(FR-038).
 *
 * - 화면은 **백분율**, 계약은 **비율**이다. 변환은 문자열로 한다(`toPercent`·`toRate` — 헌법 원칙 VI). 숫자로 바꾸면 `0.2 / 100`이
 *   `0.002`가 아닌 값이 될 수 있다
 * - 검증은 서버와 같다 — 세율 0 이상 100 미만·소수 4자리(퍼센트) 이하, 공제 0 이상의 정수(원). 실패하면 **저장하지 않고** 알린다 — 조용히
 *   0이나 기본값으로 바꾸면 세금이 다른 결과가 그럴듯하게 나온다
 * - 공제 칸은 친 글자를 그대로 들고 있다가 저장할 때 쉼표만 지운다 — 부호·소수점을 몰래 버리면 `-1`이 `1`로 저장된다
 * - "기본값으로"는 서버가 준 `defaults`를 보낸다 — 기본값을 화면에 두 번 적지 않는다
 */

import { useState } from "react";
import { toPercent, toRate } from "@/components/settings/CryptoSettingsForm";
import { formatPrincipal } from "@/lib/principalFormat";
import type { SaleTaxSettings, SaleTaxValues } from "@/lib/types";

const RATE_ERROR = "세율은 0 이상 100 미만의 숫자(소수 4자리까지)를 입력하세요.";
const DEDUCTION_ERROR = "공제는 0 이상의 정수(원)를 입력하세요.";

/** 퍼센트 문자열 → 비율 문자열. 범위 밖·소수 4자리 넘음·숫자 아님이면 `null`. */
function rateOf(percent: string): string | null {
  const fraction = percent.trim().split(".")[1] ?? "";
  return fraction.length > 4 ? null : toRate(percent);
}

/** 공제 문자열(쉼표 허용) → 원 문자열. 0 이상의 정수(15자리 이하)가 아니면 `null`. */
function deductionOf(text: string): string | null {
  const digits = text.trim().replace(/,/g, "");
  return /^\d{1,15}$/.test(digits) ? digits.replace(/^0+(?=\d)/, "") : null;
}

export function StockSaleTaxForm({
  value,
  onSave,
}: {
  value: SaleTaxSettings;
  onSave: (next: SaleTaxValues) => void;
}) {
  const [domestic, setDomestic] = useState(toPercent(value.saleTaxRateDomestic));
  const [foreign, setForeign] = useState(toPercent(value.capitalGainsRateForeign));
  const [deduction, setDeduction] = useState(formatPrincipal(value.capitalGainsDeductionForeign));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const domesticRate = rateOf(domestic);
    const foreignRate = rateOf(foreign);
    if (domesticRate === null || foreignRate === null) {
      setError(RATE_ERROR);
      return;
    }
    const won = deductionOf(deduction);
    if (won === null) {
      setError(DEDUCTION_ERROR);
      return;
    }
    setError(null);
    onSave({ saleTaxRateDomestic: domesticRate, capitalGainsRateForeign: foreignRate,
      capitalGainsDeductionForeign: won });
  };

  const field = "w-28 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums";
  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">주식 매도 세금</h3>
        <span className="text-xs text-gray-500">{value.isDefault ? "기본값" : "변경됨"}</span>
      </div>
      <div className="grid gap-3 text-sm">
        <label className="flex flex-wrap items-center gap-2">
          <span className="w-36 text-gray-500">국내 매도 세율</span>
          <input type="text" inputMode="decimal" aria-label="국내 매도 세율" value={domestic}
            onChange={(e) => setDomestic(e.target.value)} className={field} />
          <span className="text-gray-600">%</span>
          <span className="text-xs text-gray-500">
            기본 0.20% — 2026년 증권거래세 실질 세율(코스피 거래세 + 농어촌특별세, 코스닥과 같다)
          </span>
        </label>
        <label className="flex flex-wrap items-center gap-2">
          <span className="w-36 text-gray-500">해외 양도소득세율</span>
          <input type="text" inputMode="decimal" aria-label="해외 양도소득세율" value={foreign}
            onChange={(e) => setForeign(e.target.value)} className={field} />
          <span className="text-gray-600">%</span>
          <span className="text-xs text-gray-500">기본 22% — 지방소득세 포함</span>
        </label>
        <label className="flex flex-wrap items-center gap-2">
          <span className="w-36 text-gray-500">해외 연간 기본공제</span>
          <input type="text" inputMode="numeric" aria-label="해외 연간 기본공제" value={deduction}
            onChange={(e) => setDeduction(e.target.value)} className={`${field} w-36`} />
          <span className="text-gray-600">원</span>
          <span className="text-xs text-gray-500">기본 2,500,000원 — 그해 다른 해외 매도가 없다고 가정</span>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={submit} className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
          저장
        </button>
        {!value.isDefault && (
          <button type="button"
            onClick={() => {
              setError(null);
              onSave(value.defaults);
            }}
            className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700">
            기본값으로
          </button>
        )}
      </div>
      {error !== null && <p role="alert" className="text-xs text-red-700">{error}</p>}
      <p className="text-xs text-gray-500">
        ⓘ 매도 세금은 시뮬레이션 보드가 기준일에 모두 판다고 가정할 때만 씁니다. 저장하면 다음 실행부터 반영됩니다.
      </p>
    </section>
  );
}
