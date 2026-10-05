"use client";

/**
 * 부동산 시뮬레이션 조건 입력 (T039) — 009 FR-002, FR-005, FR-006, FR-007, FR-023, ui-wireframes E1·E3.
 *
 * 예금 폼(`DepositSimulationForm`)과 같되 원금 대신 **매입가(선택)**다. 통화 칸이 없다 — 원화만이다(FR-007).
 *
 * - 매입일은 006 `StartDateInput`이다 — 달력, `‹ ›` 한 달, `« »` 1년. **상한은 오늘(한국 시간)**, **하한은 고른 평형의 시작 가능 날짜**
 * - 시작 가능 날짜보다 이르면 **실행 전에** 그 사실·날짜·근거를 보이고 옮기기 수단을 준다 — 조용히 옮기지 않는다(FR-005, E3). 근거가 첫
 *   거래 달이면 그 달을, 세법 표의 첫 날이면 그 날과 첫 거래 달을 밝힌다
 * - 매입가는 비우면 매입 달의 시세다. 쉼표는 표시에만 있고 값은 숫자 문자열이다(헌법 원칙 VI). 0은 거절한다(FR-006)
 * - 실행의 거절(409)은 종류마다 다른 말과 할 일이다. 매입 달 시세가 없으면 **매입가 칸으로 초점을 옮긴다** — 할 일이 그 칸에 있다
 */

import { useEffect, useLayoutEffect, useRef } from "react";
import { StartDateInput, isStartBlocked, type Startable } from "@/components/stock/StartDateInput";
import { caretAfter, formatPrincipal, normalizePrincipal } from "@/lib/principalFormat";
import { monthOf } from "@/lib/startDate";
import type { RealEstateAreaBucket } from "@/lib/types";
import type { RealEstateInput, RealEstateRejection, RealEstateStartable } from "@/stores/realEstateStore";

/** 매입일의 하한과 근거. 첫 거래 달은 세법 표가 근거일 때 함께 밝힌다. */
export interface RealEstateStartBound {
  startableFrom: string;
  basis: "first_trade" | "tax_rules";
  firstMonth: string | null;
}

/**
 * 고른 평형의 하한 — 실행 뒤 서버가 알려 준 것(409)이 있으면 그것, 없으면 평형 구분의 `startableFrom`. 평형 구분에는 근거가 오지 않지만
 * `startableFrom`이 첫 거래 달의 1일보다 늦으면 세법 표가 막은 것이다(FR-005 — 둘 중 늦은 날).
 */
export function startBoundFor(
  bucket: RealEstateAreaBucket | null, startable: RealEstateStartable | null,
): RealEstateStartBound | null {
  const firstMonth = bucket?.firstMonth ?? null;
  if (startable !== null) return { ...startable, firstMonth };
  if (bucket === null || bucket.startableFrom === null) return null;
  const basis = firstMonth !== null && `${firstMonth}-01` < bucket.startableFrom ? "tax_rules" : "first_trade";
  return { startableFrom: bucket.startableFrom, basis, firstMonth };
}

/** E3의 시작 가능 날짜 안내. */
function boundMessage(bound: RealEstateStartBound, areaLabel: string | null): string {
  const from = bound.startableFrom;
  if (bound.basis === "tax_rules") {
    const first = bound.firstMonth === null ? "" : `(첫 거래는 ${bound.firstMonth})`;
    return `세법 표는 ${from}부터 있습니다${first}. 매입일을 ${from} 이후로 고르세요.`;
  }
  const subject = areaLabel === null ? "" : `${areaLabel} `;
  return `이 단지의 ${subject}거래는 ${monthOf(from)}부터 있습니다. 매입일을 ${from} 이후로 고르세요.`;
}

/** 세목 키 → 이름. 모르는 키는 그대로 보인다 — 지어내지 않는다. */
const TAX_NAMES: Record<string, string> = {
  acquisition: "취득세", brokerage: "중개 보수", property: "재산세", comprehensive: "종부세",
};

/** E3의 거절 문구 — 사실과 할 일. */
function rejectionMessage(rejection: RealEstateRejection, areaLabel: string | null): string {
  const area = areaLabel ?? "이 평형";
  switch (rejection.kind) {
    case "no_price_at_purchase":
      return `${rejection.month}에는 ${area} 시세가 없습니다(36개월 안에 거래 없음). 실제 매입가를 넣으면 계산할 수 있습니다.`;
    case "no_trades_in_area":
      return `이 단지에 ${area} 거래가 없습니다. 다른 평형을 고르세요.`;
    case "tax_rule_not_covered":
      // FR-023 — 가까운 해의 세법으로 대신하지 않는다.
      return `${TAX_NAMES[rejection.tax] ?? rejection.tax}(${rejection.date} 기준)에 적용할 세법 표가 없습니다. 가까운 해의 세법으로 `
        + "대신하지 않습니다 — 세법 표를 갱신해야 합니다.";
    case "region_retired":
      return "이 단지의 시·군·구가 행정구역 개편으로 바뀌었습니다. 지역에서 다시 골라 실행하면 새 코드로 받습니다.";
  }
}

const PRICE_HINT_ID = "realestate-buy-price-hint";

export function RealEstateSimulationForm({
  values,
  disabled,
  limit,
  areaLabel,
  startBound,
  rejection,
  onChange,
  onSubmit,
}: {
  values: RealEstateInput;
  disabled: boolean;
  /** 매입일의 마지막 날 — 오늘(한국 시간). */
  limit: string;
  /** 고른 평형의 이름 — 안내 문구에 쓴다. */
  areaLabel: string | null;
  startBound: RealEstateStartBound | null;
  rejection: RealEstateRejection | null;
  onChange: (next: RealEstateInput) => void;
  onSubmit: () => void;
}) {
  const startable: Startable | null = startBound === null ? null : {
    startableFrom: startBound.startableFrom, basis: startBound.basis, message: boundMessage(startBound, areaLabel),
  };
  const dateBlocked = isStartBlocked(values.buyDate, limit, null, startable);
  // 칸이 숫자만 받으므로 0 이하는 0뿐이다.
  const zeroPrice = values.buyPrice !== "" && !/[1-9]/.test(values.buyPrice);

  // 쉼표가 끼어들면 커서가 끝으로 튄다 — 고친 자리를 기억해 두었다가 되돌린다(006 FR-053과 같다).
  const box = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);
  useLayoutEffect(() => {
    if (caret.current !== null && box.current !== null) {
      box.current.setSelectionRange(caret.current, caret.current);
      caret.current = null;
    }
  });
  // FR-006 — 매입 달 시세가 없으면 할 일(매입가 넣기)이 있는 칸으로 초점을 옮긴다.
  useEffect(() => {
    if (rejection?.kind === "no_price_at_purchase") box.current?.focus();
  }, [rejection]);

  const changePrice = (typed: string, at: number | null) => {
    // 원 미만은 없다 — 점 뒤를 버린다(서버도 원 단위 정수만 받는다).
    const raw = normalizePrincipal(typed).split(".")[0];
    const digitsBefore = normalizePrincipal(typed.slice(0, at ?? typed.length)).length;
    caret.current = caretAfter(formatPrincipal(raw), digitsBefore);
    onChange({ ...values, buyPrice: raw });
  };

  return (
    <form className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}>
      <div className="flex flex-wrap items-end gap-4">
        <StartDateInput value={values.buyDate} limit={limit} listedOn={null} startable={startable}
          label="매입일" min={startBound?.startableFrom}
          afterLimitText={`오늘(${limit})보다 뒤의 날짜는 계산할 수 없습니다.`}
          onChange={(buyDate) => onChange({ ...values, buyDate })} />

        <label className="text-sm">
          <span className="mb-1 block text-gray-500">매입가</span>
          <span className="flex items-center gap-1.5">
            <input type="text" inputMode="numeric" ref={box}
              value={formatPrincipal(values.buyPrice)}
              aria-describedby={PRICE_HINT_ID}
              onChange={(e) => changePrice(e.target.value, e.target.selectionStart)}
              className="w-40 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
            <span className="text-gray-600">원</span>
            <span id={PRICE_HINT_ID} className="text-xs text-gray-400">(비우면 그 달 시세)</span>
          </span>
        </label>

        <button type="submit" disabled={disabled || dateBlocked || zeroPrice}
          className="rounded bg-gray-900 px-5 py-2 text-sm text-white disabled:bg-gray-400">
          시뮬레이션
        </button>
      </div>

      {zeroPrice && (
        <p role="alert" className="text-xs text-red-700">매입가는 0보다 커야 합니다. 비우면 그 달 시세로 계산합니다.</p>
      )}
      {rejection !== null && (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          ⚠ {rejectionMessage(rejection, areaLabel)}
        </p>
      )}
    </form>
  );
}
