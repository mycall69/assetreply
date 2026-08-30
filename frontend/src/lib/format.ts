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
