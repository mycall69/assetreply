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

const CURRENCY_SYMBOL: Record<string, string> = { KRW: "₩", USD: "$", JPY: "¥", EUR: "€" };

/** 통화 기호 (006 FR-054). 모르는 통화는 통화 코드 그대로 — 기호를 지어내지 않는다. */
export function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOL[currency] ?? currency;
}

/**
 * 금액 뒤에 통화 기호를 붙인다 — `10,000,000₩`, `1,000$` (006 FR-054, research R6-21).
 *
 * 성과 보드만 쓴다. `formatMoney`는 표·차트·이력이 함께 쓰므로 바꾸지 않는다. 기호는 표시일 뿐
 * 금액 문자열은 건드리지 않는다(헌법 원칙 VI). 손실은 부호가 앞에 온다(`-5,446₩`).
 */
export function formatMoneyWithSymbol(value: DecimalString, currency: string): string {
  return `${formatMoney(value, currency)}${currencySymbol(currency)}`;
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

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/**
 * 목록 기준 시각(UTC ISO)을 한국 시간 `MM-DD HH:mm`으로 (006 FR-029).
 *
 * 하루의 경계가 한국 시간이라(spec Assumptions) 화면도 그 시각으로 보인다. 브라우저의
 * 시간대에 기대지 않는다 — 다른 시간대에서 열면 "오늘 받음"이 어제 날짜로 보인다.
 */
export function formatKst(iso: string): string {
  const shifted = new Date(Date.parse(iso) + KST_OFFSET_MS);
  if (Number.isNaN(shifted.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} `
    + `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`;
}
