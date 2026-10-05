"use client";

/**
 * 시작일 입력 (T061) — 006 FR-001, FR-002, FR-004, FR-005, ui-wireframes W1·W1a.
 *
 * `‹ ›` 한 달, `« »` 1년. 직접 입력도 그대로 둔다. 어제가 속한 달을 넘어가는 이동은 누를 수
 * 없고, 직접 입력한 미래 날짜는 사유를 보인다 — 미래 시작일로 실행하면 행이 없는 결과가 나오고
 * 사용자는 성과가 0이라고 읽는다.
 *
 * **시작일을 몰래 옮기지 않는다**(005 FR-005). 상장일(목록, 실행 전)이나 시세 시작일(실행 뒤)보다
 * 이르면 그 사실과 날짜를 알리고, 옮기기는 **눌러야만** 일어난다(W1a).
 */

import { canShift, isValidDate, monthOf, shift } from "@/lib/startDate";
import type { BeforeListingBody } from "@/lib/types";

/**
 * 실행 뒤 서버가 알려 준 시작 가능 날짜 (006 contracts 2절 `before_listing`). 008 — 예금의 `before_first_month`(투자처의 금리
 * 통계가 시작하는 달, 근거 `rate_start`)도 같은 안내를 쓴다. 009 — 부동산의 `before_first_trade`(근거 `first_trade` 첫 거래 달 ·
 * `tax_rules` 세법 표의 첫 날)도 같다.
 */
export type Startable = Pick<BeforeListingBody, "startableFrom" | "message"> & {
  basis: BeforeListingBody["basis"] | "rate_start" | "first_trade" | "tax_rules";
};

interface Bound {
  date: string;
  message: string;
}

/** 지금 값을 막는 하한. 없으면 `null`. 실행 뒤의 시세 시작일이 상장일보다 확실하다. */
function boundFor(value: string, listedOn: string | null, startable: Startable | null): Bound | null {
  if (startable !== null && value < startable.startableFrom) {
    return { date: startable.startableFrom, message: startable.message };
  }
  if (listedOn !== null && value < listedOn) {
    return {
      date: listedOn,
      message: `이 종목은 ${listedOn}에 상장했습니다. 그 이전은 계산할 수 없습니다.`,
    };
  }
  return null;
}

/** 이 시작일로 실행할 수 없는가 — 형식이 틀렸거나, 미래이거나, 하한보다 이르다. */
export function isStartBlocked(
  value: string, limit: string, listedOn: string | null, startable: Startable | null,
): boolean {
  return !isValidDate(value) || value > limit || boundFor(value, listedOn, startable) !== null;
}

const MOVES = [
  { months: -12, label: "1년 전", glyph: "«" },
  { months: -1, label: "한 달 전", glyph: "‹" },
  { months: 1, label: "한 달 뒤", glyph: "›" },
  { months: 12, label: "1년 뒤", glyph: "»" },
] as const;

export function StartDateInput({
  value,
  limit,
  listedOn,
  startable,
  afterLimitText,
  label = "시작일",
  min,
  onChange,
}: {
  value: string;
  /** 고를 수 있는 마지막 날 — 어제. 예금(008)은 오늘이다. */
  limit: string;
  listedOn: string | null;
  startable: Startable | null;
  /** 마지막 날보다 뒤를 골랐을 때의 사유. 없으면 시세 기준(어제)의 문구다. */
  afterLimitText?: string;
  /** 칸의 이름 — 부동산(009)은 "매입일"이다. */
  label?: string;
  /** 달력의 하한 — 부동산(009)은 고른 평형의 시작 가능 날짜다. 이보다 이른 직접 입력은 위의 안내가 막는다. */
  min?: string;
  onChange: (start: string) => void;
}) {
  const valid = isValidDate(value);
  const bound = valid ? boundFor(value, listedOn, startable) : null;

  const button = (move: (typeof MOVES)[number]) => (
    <button
      key={move.label}
      type="button"
      aria-label={move.label}
      title={move.label}
      disabled={!canShift(value, move.months, limit)}
      onClick={() => onChange(shift(value, move.months, limit))}
      className="rounded border border-gray-300 px-2 py-1.5 text-gray-600 disabled:text-gray-300"
    >
      {move.glyph}
    </button>
  );

  return (
    <div className="text-sm">
      <label htmlFor="start-date" className="mb-1 block text-gray-500">{label}</label>
      <div className="flex items-center gap-1">
        {MOVES.slice(0, 2).map(button)}
        <input
          id="start-date"
          type="date"
          value={value}
          max={limit}
          min={min}
          onChange={(e) => onChange(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1.5"
        />
        {MOVES.slice(2).map(button)}
      </div>

      {!valid && (
        <p role="alert" className="mt-1 text-xs text-red-700">날짜를 YYYY-MM-DD로 입력하세요.</p>
      )}
      {valid && value > limit && (
        <p role="alert" className="mt-1 text-xs text-red-700">
          {afterLimitText ?? `어제(${limit})보다 뒤의 날짜는 계산할 시세가 없습니다.`}
        </p>
      )}
      {bound !== null && (
        <div role="alert" className="mt-1 space-y-1 text-xs text-amber-800">
          <p>⚠ {bound.message}</p>
          <button
            type="button"
            onClick={() => onChange(bound.date)}
            className="rounded border border-amber-300 bg-white px-2 py-0.5"
          >
            {monthOf(bound.date)}로 옮기기
          </button>
        </div>
      )}
    </div>
  );
}
