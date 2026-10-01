/**
 * 표시 서식.
 *
 * 값은 문자열로 받아 문자열로 다룬다. `Number()`로 변환하면 정밀도가 손실되며
 * 헌법 원칙 VI가 API 경계에서 무력화된다. 천 단위 구분만 문자열 조작으로 넣는다.
 */

import type { DecimalString } from "./apiClient";

/** "1012.300000" → "1,012.30" (소수 2자리, 천 단위 구분) */
export function formatRate(value: DecimalString): string {
  const [intPart = "0", fracPart = ""] = value.split(".");
  const sign = intPart.startsWith("-") ? "-" : "";
  const digits = sign ? intPart.slice(1) : intPart;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const frac = (fracPart + "00").slice(0, 2);
  return `${sign}${grouped}.${frac}`;
}

/** 고시 단위 표기. JPY는 100엔당이므로 단위를 함께 보여준다 (FR-007). */
export function unitLabel(quoteUnit: number): string {
  return quoteUnit === 100 ? "원 / 100엔" : "원";
}

/* ───────────────────────── 005: 주식 투자 시뮬레이션 ───────────────────────── */

/**
 * 금액을 통화에 맞춰 표시한다.
 *
 * **원화·엔화에 소수점 금액은 존재하지 않는다.** 서버가 이미 `Decimal`로 자릿수를
 * 맞춰 보내므로 여기서는 천 단위 구분만 넣는다 — 다시 계산하면 그 순간 IEEE 754를
 * 거쳐 헌법 원칙 VI가 표시 단계에서 무너진다.
 */
export function formatMoney(value: DecimalString, currency: string): string {
  const negative = value.trimStart().startsWith("-");
  const digits = value.replace("-", "");
  const [whole, fraction] = digits.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const noDecimals = currency === "KRW" || currency === "JPY";
  const tail = !noDecimals && fraction ? `.${fraction.slice(0, 2)}` : "";
  return `${negative ? "-" : ""}${grouped}${tail}`;
}

/**
 * 비율을 백분율로 표시한다. 부호를 항상 붙인다.
 *
 * **색만으로 손익을 구별하지 않는다**(접근성). 부호가 있어야 흑백·저대비에서도 읽힌다.
 */
export function formatPercent(value: DecimalString, digits = 2): string {
  const scaled = shiftDecimal(value, 2);
  const sign = scaled.startsWith("-") ? "" : "+";
  return `${sign}${trimTo(scaled, digits)}%`;
}

/** 배당율처럼 부호가 의미 없는 비율. 부호를 붙이지 않는다. */
export function formatYield(value: DecimalString, digits = 2): string {
  return `${trimTo(shiftDecimal(value, 2), digits)}%`;
}

/** 소수점을 `places`만큼 오른쪽으로 옮긴다. 문자열 조작이라 정밀도를 잃지 않는다. */
export function shiftDecimal(value: DecimalString, places: number): string {
  const negative = value.trimStart().startsWith("-");
  const digits = value.replace("-", "");
  const [whole, fraction = ""] = digits.split(".");
  const padded = fraction.padEnd(places, "0");
  const moved = `${whole}${padded.slice(0, places)}`.replace(/^0+(?=\d)/, "");
  const rest = padded.slice(places);
  return `${negative ? "-" : ""}${moved}${rest ? `.${rest}` : ""}`;
}

function trimTo(value: string, digits: number): string {
  const [whole, fraction] = value.split(".");
  if (digits === 0) return whole;
  return `${whole}.${(fraction ?? "").padEnd(digits, "0").slice(0, digits)}`;
}
