/**
 * 차트 시리즈 구성 (T081 보조) — contracts/ui-chart.md.
 *
 * **결측 구간에서 시리즈를 분리한다.** Lightweight Charts는 포인트 사이를 기본적으로
 * 직선 연결하므로, 값을 넣지 않는 것만으로는 부족하다. 이어 그리면 없는 데이터를
 * 있는 것처럼 보여주게 되어 헌법 원칙 V를 위반한다 (FR-032).
 */

import type { SeriesGap, SeriesPoint } from "./types";

/** 차트 라이브러리에 넘길 형태. `raw`는 표시용 원본 문자열이다. */
export interface ChartDatum {
  time: string;
  value: number;
  raw: string;
}

/**
 * gap을 경계로 포인트를 여러 구간으로 나눈다.
 *
 * 각 구간은 별도 시리즈로 그려야 결측 구간이 선으로 이어지지 않는다.
 */
export function splitSeriesAtGaps(
  points: SeriesPoint[],
  gaps: SeriesGap[],
): SeriesPoint[][] {
  if (points.length === 0) return [];
  if (gaps.length === 0) return [points];

  const boundaries = [...gaps].sort((a, b) => a.from.localeCompare(b.from));
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
