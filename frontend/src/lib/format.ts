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

/**
 * 연 금리(%) — 출처 문자열(`"3.2"`)을 두 자리로(`3.20%`). 예금 표(008)와 성과 차트의 상자(010)가 함께 쓴다 — 공유 차트가 예금 표 부품을
 * 거꾸로 가져오지 않게 여기에 둔다. 두 곳의 금리가 같은 형식이어야 상자와 표의 값이 같다(010 FR-010).
 */
export function formatAnnualRate(rate: DecimalString): string {
  return `${formatRate(rate)}%`;
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
 * 금액 앞에 통화 기호를 붙인다 — `₩10,000,000`, `$1,000` (007 FR-042a, research R7-14).
 *
 * 006(FR-054)은 숫자 뒤(`10,000,000₩`)였다 — 사용자 요청(2026-10-04)으로 앞으로 옮겼다.
 *
 * 성과 보드만 쓴다. `formatMoney`는 표·차트·이력이 함께 쓰므로 바꾸지 않는다. 기호는 표시일 뿐
 * 금액 문자열은 건드리지 않는다(헌법 원칙 VI). 손실은 부호 → 기호 → 숫자(`-₩5,446`) — `₩-5,446`이면 손실 표시가
 * 숫자 가운데 묻힌다. 기호를 모르는 통화는 코드와 공백(`GBP 1,000`) — 붙이면 코드와 숫자가 한 덩어리로 읽힌다.
 */
export function formatMoneyWithSymbol(value: DecimalString, currency: string): string {
  const shown = formatMoney(value, currency);
  const negative = shown.startsWith("-");
  const symbol = currencySymbol(currency);
  const prefix = symbol === currency ? `${symbol} ` : symbol;
  return `${negative ? "-" : ""}${prefix}${negative ? shown.slice(1) : shown}`;
}

/**
 * 차트 축 눈금에 천 단위 쉼표를 넣는다 — `360,000,000`, `3,200.00` (007 FR-043a, research R7-14).
 *
 * **축 눈금 전용이다.** 그리기용 숫자(차트가 이미 `Number`로 받은 값)를 받는다 — 금액 문자열에 쓰면 IEEE 754를
 * 거쳐 헌법 원칙 VI가 무너진다. 값의 진실은 툴팁·표의 원본 문자열이다. 로캘에 따라 구분자가 바뀌는
 * `toLocaleString`은 쓰지 않는다. 반올림해 0이 되는 음수는 부호를 뗀다 — 0 눈금이 `-0.00`이면 손실처럼 읽힌다.
 */
export function formatAxisNumber(value: number, fractionDigits: number): string {
  const fixed = Math.abs(value).toFixed(fractionDigits);
  const [whole, fraction] = fixed.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const negative = value < 0 && Number(fixed) !== 0;
  return `${negative ? "-" : ""}${grouped}${fraction ? `.${fraction}` : ""}`;
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

/**
 * 주당 배당금 — **소수 3자리**(006 FR-057, research R6-24). 종목 통화 값이라 원금 통화 규칙(`formatMoney`)을
 * 쓰지 않는다 — 원화 원금에서 달러 배당 `1.823`이 `1`로 보였다. 반올림하지 않고 3자리에서 자른다(서버는 6자리).
 */
export function formatDividend(value: DecimalString): string {
  const negative = value.trimStart().startsWith("-");
  const [whole = "0", fraction = ""] = value.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}.${(fraction + "000").slice(0, 3)}`;
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

/* ───────────────────────── 007: 가상자산 ───────────────────────── */

/** 쉼표를 넣은 정수부. */
const group = (whole: string) => whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/**
 * 가상자산 가격 (007 FR-040, SC-009). **유효 숫자를 잃지 않게** — 1 이상이면 소수 2자리, 1 미만이면 유효 숫자 4자리까지(뒤의 0은
 * 지우되 소수 2자리는 둔다). SHIB(0.0000053달러)를 소수 2자리로 보이면 `0.00`이 되어 시세가 없거나 0이라고 읽힌다.
 * 반올림하지 않고 자른다 — 문자열 조작이다(헌법 원칙 VI).
 */
export function formatPrice(value: DecimalString): string {
  const negative = value.trimStart().startsWith("-");
  const [whole = "0", fraction = ""] = value.replace("-", "").split(".");
  const sign = negative ? "-" : "";
  const intPart = whole.replace(/^0+(?=\d)/, "");
  if (intPart !== "0") {
    return `${sign}${group(intPart)}.${(fraction + "00").slice(0, 2)}`;
  }
  const leading = fraction.match(/^0*/)?.[0].length ?? 0;
  if (leading === fraction.length) return `${sign}0.00`;
  const kept = fraction.slice(0, leading + 4).replace(/0+$/, "");
  return `${sign}0.${kept.padEnd(2, "0")}`;
}

/** 가상자산 수량 — 소수 8자리 그대로, 정수부는 3자리마다 쉼표(FR-026). 0은 `0`이다. */
export function formatQuantity(value: DecimalString): string {
  const [whole = "0", fraction = ""] = value.split(".");
  if (/^0*$/.test(whole) && /^0*$/.test(fraction)) return "0";
  return `${group(whole.replace(/^0+(?=\d)/, ""))}.${fraction.padEnd(8, "0").slice(0, 8)}`;
}
