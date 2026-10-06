/**
 * 차트 시리즈 구성 (T081 보조, T123) — contracts/ui-chart.md.
 *
 * **`reason`에 따라 다르게 그린다** (2026-09-27 반복으로 개정된 FR-032·FR-032b).
 *
 * - `no_quote`(휴장일·주말) — **잇는다.** 그날은 시장이 열리지 않아 값이 존재하지 않으며,
 *   실제로 존재하는 두 고시일 사이를 잇는 것은 값을 만들어내는 것이 아니다. 세계의 환율
 *   차트가 금요일과 월요일을 잇는 것과 같다. 휴장일마다 끊으면 1년 보기에서 50구간 넘게
 *   쪼개져 추세가 읽히지 않는다.
 * - `not_collected`(미수집) — **끊는다.** 값이 존재할 수 있는데 받지 않은 구간이다.
 *   이으면 구멍 위에 온전한 선이 그려져 사용자가 데이터를 다 가졌다고 믿는다.
 *   헌법 원칙 V가 막으려는 것이 이쪽이다.
 * - `source_missing`(출처 결측, 007) — **끊는다.** 가상자산은 24시간 거래라 휴장이 없다. 받은 구간 안의 빈 날은
 *   값이 있어야 하는데 출처에 없는 날이다 — 이으면 없는 값을 있는 것처럼 그린다(007 FR-023).
 * - `no_price`(시세 없음, 009) — **끊는다.** 36개월 안에 거래가 없어 그 달의 시세가 없다. 이으면 그 사이에 시세가 있었던 것처럼
 *   그려진다(009 FR-026).
 *
 * Lightweight Charts는 포인트 사이를 기본적으로 직선 연결하므로, **끊으려면** 시리즈를
 * 나눠야 한다. 잇는 쪽은 아무것도 하지 않으면 된다.
 *
 * 어느 쪽이든 **포인트를 만들어내지 않는다.** 결측일 위의 툴팁은 그대로 결측 사유를
 * 보여준다 — 선을 잇는 것과 값이 있다고 말하는 것은 다르다.
 */

import { formatAxisNumber, shiftDecimal } from "./format";
import type { SeriesGap, SeriesPoint, SimulationPoint } from "./types";

/**
 * 축 눈금 형식 — 시리즈의 `priceFormat`에 넘긴다 (007 FR-043a·FR-046a, research R7-14).
 *
 * 성과 추이 차트와 이력 비교 차트가 **함께 쓴다.** 결측 규칙을 `splitSeriesAtGaps` 하나로 두는 것과 같은 이유다 —
 * 두 벌이면 한쪽만 고쳐져 같은 화면의 두 수익률 축이 다른 형식으로 보인다. 축은 붙은 시리즈 하나의 형식을 따르므로
 * 쓰는 쪽은 구간·항목마다 만드는 **모든 시리즈에** 준다. 그리기용 숫자를 받는다 — 값의 진실은 툴팁·표의 원본 문자열이다.
 */
export function axisPriceFormat(fractionDigits: number) {
  return {
    type: "custom" as const,
    minMove: 10 ** -fractionDigits,
    formatter: (price: number) => formatAxisNumber(price, fractionDigits),
  };
}

/** 차트 라이브러리에 넘길 형태. `raw`는 표시용 원본 문자열이다. */
export interface ChartDatum {
  time: string;
  value: number;
  raw: string;
}

/**
 * **미수집** 구간을 경계로 포인트를 나눈다. 휴장일은 경계로 삼지 않는다 (FR-032).
 *
 * 각 구간은 별도 시리즈로 그려야 선이 이어지지 않는다.
 */
export function splitSeriesAtGaps<T extends { date: string }>(
  points: T[],
  gaps: SeriesGap[],
): T[][] {
  if (points.length === 0) return [];

  // 휴장일은 걸러낸다. 여기서 거르지 않으면 주말마다 시리즈가 쪼개진다. 잇는 것은 휴장뿐이다 — 나머지(미수집·출처 결측·
  // 시세 없음)는 모두 끊는다. 새 사유도 끊는 쪽이 기본이다 — 이으면 없는 값을 만들어낸다.
  const breaks = gaps.filter((g) => g.reason !== "no_quote");
  if (breaks.length === 0) return [points];

  const boundaries = [...breaks].sort((a, b) => a.from.localeCompare(b.from));
  const segments: T[][] = [];
  let current: T[] = [];

  for (const point of points) {
    const crossed = boundaries.some(
      (g) => current.length > 0 && current[current.length - 1].date < g.from && point.date > g.to,
    );
    if (crossed) {
      segments.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length > 0) segments.push(current);
  return segments;
}

/**
 * 렌더링용 형태로 변환한다.
 *
 * 차트 라이브러리가 `number`를 요구하므로 변환하되, **원본 문자열을 함께 보존한다.**
 * 툴팁 등 사용자에게 보이는 값에는 원본을 쓴다 — 렌더링용 변환값이 값의 진실이 되면
 * 정밀도가 손실된 값을 사용자가 보게 된다.
 */
export function toChartData(points: SeriesPoint[]): ChartDatum[] {
  return points
    .map((p) => ({ time: p.date, value: Number(p.baseRate), raw: p.baseRate }))
    .sort((a, b) => a.time.localeCompare(b.time));
}

/**
 * 성과 차트용 변환 (005 FR-033).
 *
 * **수익률은 백분율 축으로 그린다.** `0.2067`을 그대로 두면 눈금이 0~0.2라 읽히지
 * 않고, 잔고(8만)와 같은 축에 놓이면 바닥에 붙어 평평해 보인다 — 사용자는 수익이
 * 없었다고 읽는다.
 *
 * 소수점은 **문자열로 옮긴다**. `* 100`은 부동소수 곱이라 `0.1 * 100 = 10.000000000000002`가
 * 되고, 헌법 원칙 VI가 렌더링 경계에서 무너진다. 그래도 라이브러리가 `number`를
 * 요구하므로 마지막에 한 번 변환하되 **원본 문자열을 함께 보존한다** — 사용자에게
 * 보이는 값에는 원본을 쓴다.
 */
export function toPerformanceData(
  points: SimulationPoint[],
  field: "balance" | "returnRate" | "principal",
): ChartDatum[] {
  return points
    // 011 — 누적 납입 원금은 적립식·적금 점에만 있다. 키가 없는 점은 그 선에 넣지 않는다(0으로 그리지 않는다).
    .filter((p) => field !== "principal" || p.principal !== undefined)
    .map((p) => {
      const raw = field === "balance" ? p.balance : field === "principal" ? (p.principal as string) : p.returnRate;
      return {
        time: p.date,
        value: Number(field === "returnRate" ? shiftDecimal(raw, 2) : raw),
        raw,
      };
    })
    .sort((a, b) => a.time.localeCompare(b.time));
}

/**
 * 가격 선의 구간 (010 FR-003, research R10-7).
 *
 * 잔고와 **같은 자리**(`splitSeriesAtGaps` — 미수집·출처 결측·시세 없음)에서 끊고, **가격이 없는 점에서 다시 끊는다** — 예금
 * 미발표·결측 달, 부동산 거래 없는 달. 잔고·수익률은 그 달에도 값이 있으므로 가격 선만 끊긴다. 가격이 없는 점은 어느 구간에도
 * 넣지 않는다 — 앞뒤를 잇거나 직전 값을 끌어오면 없는 가격이 있는 것처럼 보인다(헌법 원칙 V). 점 하나뿐인 구간도 남긴다 —
 * 선은 두 점이 있어야 보이므로 화면이 점으로 그린다. 가격 키가 없는 점(가격 없는 응답)은 그리지 않는다.
 */
export function priceSegments<T extends { date: string; price?: string | null }>(
  points: T[],
  gaps: SeriesGap[],
): T[][] {
  const segments: T[][] = [];
  for (const segment of splitSeriesAtGaps(points, gaps)) {
    let current: T[] = [];
    for (const point of segment) {
      if (point.price === null || point.price === undefined) {
        if (current.length > 0) segments.push(current);
        current = [];
      } else {
        current.push(point);
      }
    }
    if (current.length > 0) segments.push(current);
  }
  return segments;
}

/** 값 없는 자리 하나 — 결측 구간과 그 사유. */
export interface GapSlot {
  time: string;
  from: string;
  to: string;
  reason: "source_missing" | "no_price";
}

/**
 * 값 없는 자리 (010 FR-011, research R10-8).
 *
 * 라이브러리의 시간 축은 어느 시리즈에든 있는 시각만 자리로 둔다 — 점이 없는 출처 결측 날·시세 없음 달에는 커서가 놓일 수 없어 그
 * 사유를 보일 곳이 없다. 점 범위(첫 점 ~ 끝 점) 안의 출처 결측·시세 없음 **구간마다 자리 하나**(`from`)를 둔다. 날마다 두면 안 된다 —
 * 시간 축은 자리마다 같은 폭을 주므로 줄인(다운샘플) 차트에서 결측 하루가 줄인 점 하나(며칠 치)와 같은 폭이 되어 구간이 과장되고,
 * 자리 수가 줄이기 밖에서 늘어난다(헌법 원칙 VII). 휴장(잇는다)·미수집(200에 섞이지 않는다)에는 두지 않는다.
 */
export function gapSlots(points: { date: string }[], gaps: SeriesGap[]): GapSlot[] {
  if (points.length === 0) return [];
  const first = points[0].date;
  const last = points[points.length - 1].date;
  const slots: GapSlot[] = [];
  for (const gap of [...gaps].sort((a, b) => a.from.localeCompare(b.from))) {
    if (gap.reason !== "source_missing" && gap.reason !== "no_price") continue;
    if (gap.from <= first || gap.to >= last) continue;
    slots.push({ time: gap.from, from: gap.from, to: gap.to, reason: gap.reason });
  }
  return slots;
}
