/**
 * 성과 차트의 커서 가까이 상자 (010 T024) — FR-009~FR-012, research R10-8·R10-9, data-model 4절, ui-wireframes F2.
 *
 * **값은 그 점의 원본 문자열이고 형식은 표와 같은 함수다**(FR-010). 표와 다른 함수를 쓰면 반올림·자릿수가 갈라져 상자와 표가 조용히
 * 어긋난다 — 주식 가격은 표의 시작가(`formatRate`), 가상자산은 표의 시가(`formatPrice` — 작은 값을 0.00으로 깎지 않는다), 예금 금리는
 * 예금 표(`formatAnnualRate`), 수익률은 표의 `formatPercent`, 금액은 통화 기호를 앞에(`formatMoneyWithSymbol`, 007 FR-042a). 가격의 통화는
 * 자산 자신의 것이고(원금이 KRW여도 USD 주가는 달러) 잔고는 기준 통화다.
 *
 * 값이 없는 칸은 0이 아니라 "—"와 사유다(FR-011, 헌법 원칙 V). 부동산 거래 없는 달은 실거래가 평균만 비고 평가액·투자 수익·수익률은
 * 적용 시세로 그대로다 — 적용 시세를 실거래가 자리에 넣으면 거래가 없던 달에 거래가 있던 것처럼 읽힌다. 값 없는 자리(출처 결측·
 * 시세 없음 — `gapSlots`, 구간마다 하나)는 구간과 사유를 보인다.
 */

import { gapSlots, splitMarks } from "./chartSeries";
import {
  currencySymbol,
  formatAnnualRate,
  formatMoneyWithSymbol,
  formatPercent,
  formatPrice,
  formatRate,
} from "./format";
import type { PriceKind, PriceMissing, SimulationSeriesResponse } from "./types";

/** 상자의 한 줄. 값이 없으면 `value`가 "—"이고 `missing`이 사유다. */
export interface HoverLine {
  label: string;
  value: string;
  missing?: string;
}

export interface HoverView {
  /** 날짜(부동산은 달 — 첫 점·끝 점은 날짜), 값 없는 자리는 구간. */
  title: string;
  lines: HoverLine[];
  /** 주식 분할 표식 점이면 비율과 효력일(FR-008). */
  notes: string[];
  /** 값 없는 자리의 사유. 점이면 `null`. */
  reason: string | null;
}

/** 가격 선의 이름(010 FR-005) — 범례와 상자가 함께 쓴다. */
export const PRICE_NAME: Record<PriceKind, string> = {
  stock_open: "주가",
  crypto_open: "시세",
  deposit_rate: "금리",
  apt_average: "실거래가 평균",
};

const MISSING_TEXT: Record<PriceMissing, string> = {
  unpublished: "미발표",
  missing: "결측",
  no_trades: "거래 없음",
};

const SLOT_REASON = { source_missing: "출처 결측", no_price: "시세 없음" } as const;

const DASH = "—";

/** 커서에서 상자까지(px). */
const HOVER_OFFSET = 12;

type Field = "price" | "balance" | "profit" | "returnRate";

/** 자산군마다 줄의 순서(ui-wireframes F2). 가격이 없는 응답(005~009)은 잔고·수익률만. */
function fields(kind: PriceKind | undefined): Field[] {
  switch (kind) {
    case "stock_open":
    case "crypto_open":
      return ["price", "balance", "returnRate"];
    case "deposit_rate":
      return ["balance", "returnRate", "price"];
    case "apt_average":
      return ["balance", "profit", "returnRate", "price"];
    default:
      return ["balance", "returnRate"];
  }
}

function label(field: Field, kind: PriceKind | undefined): string {
  if (field === "price") return kind === undefined ? "" : PRICE_NAME[kind];
  if (field === "balance") return kind === "apt_average" ? "평가액" : "잔고";
  if (field === "profit") return "투자 수익";
  return "수익률";
}

/** 기호를 숫자 앞에 — 기호를 모르는 통화는 코드와 공백(`formatMoneyWithSymbol`과 같은 규칙). 가격은 양수다. */
function withSymbol(text: string, currency: string | null | undefined): string {
  if (!currency) return text;
  const symbol = currencySymbol(currency);
  return symbol === currency ? `${currency} ${text}` : `${symbol}${text}`;
}

function priceText(kind: PriceKind, price: string, currency: string | null | undefined): string {
  switch (kind) {
    case "stock_open":
      return withSymbol(formatRate(price), currency);
    case "crypto_open":
      return withSymbol(formatPrice(price), currency);
    case "deposit_rate":
      return `연 ${formatAnnualRate(price)}`;
    case "apt_average":
      return formatMoneyWithSymbol(price, "KRW");
  }
}

/** 응답이 가격을 싣는지 — 점에 `price` 키가 있어야 한다(005~009 응답에는 없다). */
function priceKindOf(series: SimulationSeriesResponse): PriceKind | undefined {
  return series.points.some((p) => p.price !== undefined) ? series.priceKind : undefined;
}

/**
 * 커서가 붙은 시각의 상자 내용. 그 시각에 점도 값 없는 자리도 없으면 `null`이다.
 */
export function hoverView(series: SimulationSeriesResponse, time: string): HoverView | null {
  const kind = priceKindOf(series);
  const monthly = kind === "apt_average";
  const index = series.points.findIndex((p) => p.date === time);

  if (index < 0) {
    if (kind === undefined) return null;
    const slot = gapSlots(series.points, series.gaps).find((s) => s.time === time);
    if (slot === undefined) return null;
    const day = (d: string) => (monthly ? d.slice(0, 7) : d);
    return {
      title: `${day(slot.from)} ~ ${day(slot.to)}`,
      lines: fields(kind).map((field) => ({ label: label(field, kind), value: DASH })),
      notes: [],
      reason: SLOT_REASON[slot.reason],
    };
  }

  const point = series.points[index];
  const edge = index === 0 || index === series.points.length - 1;
  const lines = fields(kind).map((field): HoverLine => {
    const name = label(field, kind);
    if (field === "balance") return { label: name, value: formatMoneyWithSymbol(point.balance, series.basisCurrency) };
    if (field === "returnRate") return { label: name, value: formatPercent(point.returnRate) };
    if (field === "profit") {
      return { label: name, value: point.profit === undefined ? DASH : formatMoneyWithSymbol(point.profit, "KRW") };
    }
    if (point.price === null || point.price === undefined || kind === undefined) {
      return point.priceMissing === undefined
        ? { label: name, value: DASH }
        : { label: name, value: DASH, missing: MISSING_TEXT[point.priceMissing] };
    }
    return { label: name, value: priceText(kind, point.price, series.priceCurrency) };
  });
  const mark = splitMarks(series.points, series.splits ?? []).find((m) => m.date === time);

  return {
    title: monthly && !edge ? point.date.slice(0, 7) : point.date,
    lines,
    notes: mark === undefined ? [] : mark.splits.map((s) => `분할 ${s.denominator}→${s.numerator} (${s.date} 효력)`),
    reason: null,
  };
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

/**
 * 상자의 자리(차트 칸 기준 왼쪽·위, px). 커서 오른쪽 아래 12px — 넘치면 커서 반대쪽, 그래도 넘치면 칸 안으로 붙인다(FR-012).
 */
export function placeHover(
  point: { x: number; y: number },
  box: { width: number; height: number },
  area: { width: number; height: number },
): { left: number; top: number } {
  let left = point.x + HOVER_OFFSET;
  if (left + box.width > area.width) left = point.x - HOVER_OFFSET - box.width;
  let top = point.y + HOVER_OFFSET;
  if (top + box.height > area.height) top = point.y - HOVER_OFFSET - box.height;
  return {
    left: clamp(left, 0, Math.max(0, area.width - box.width)),
    top: clamp(top, 0, Math.max(0, area.height - box.height)),
  };
}
