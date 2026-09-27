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
 *
 * Lightweight Charts는 포인트 사이를 기본적으로 직선 연결하므로, **끊으려면** 시리즈를
 * 나눠야 한다. 잇는 쪽은 아무것도 하지 않으면 된다.
 *
 * 어느 쪽이든 **포인트를 만들어내지 않는다.** 결측일 위의 툴팁은 그대로 결측 사유를
 * 보여준다 — 선을 잇는 것과 값이 있다고 말하는 것은 다르다.
 */

import type { SeriesGap, SeriesPoint } from "./types";

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
export function splitSeriesAtGaps(
  points: SeriesPoint[],
  gaps: SeriesGap[],
): SeriesPoint[][] {
  if (points.length === 0) return [];

  // 휴장일은 걸러낸다. 여기서 거르지 않으면 주말마다 시리즈가 쪼개진다.
  const breaks = gaps.filter((g) => g.reason === "not_collected");
  if (breaks.length === 0) return [points];

  const boundaries = [...breaks].sort((a, b) => a.from.localeCompare(b.from));
  const segments: SeriesPoint[][] = [];
  let current: SeriesPoint[] = [];

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
