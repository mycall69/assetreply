/**
 * 확대 구간의 일 단위 자료 끼워 그리기 — 순수 규칙 (014 반복 2026-10-11c) — spec FR-038, data-model 16, research R14-31.
 *
 * 받은 구간 [from, to]의 점은 받은 자료로, 그 밖은 원래 점 그대로다(끌어 옮기면 보인다). 결측 구간은 원래 것과 받은 것을 합친다 — 같은
 * 구간은 한 번. 날짜는 `YYYY-MM-DD` 글자라 글자 차례가 날짜 차례다 — 날짜를 계산하지 않고, 값도 계산하지 않는다(받은 글자 그대로).
 */
import type { ZoomRange } from "@/lib/chartZoom";
import type { SeriesGap } from "@/lib/types";

interface Dated {
  date: string;
}

interface WithPoints<P extends Dated> {
  points: P[];
  gaps: SeriesGap[];
}

/** 받은 구간이 새 구간을 덮는가 — 덮으면 다시 받지 않는다. */
export function covers(received: ZoomRange, range: ZoomRange): boolean {
  return received.from <= range.from && range.to <= received.to;
}

/** 구간 밖의 원래 점 + 받은 점(날짜 차례). */
export function spliceWindow<P extends Dated>(base: P[], detail: P[], range: ZoomRange): P[] {
  const outside = base.filter((p) => p.date < range.from || p.date > range.to);
  return [...outside, ...detail].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

export function mergeGaps(base: SeriesGap[], detail: SeriesGap[]): SeriesGap[] {
  const seen = new Set<string>();
  const out: SeriesGap[] = [];
  for (const gap of [...base, ...detail]) {
    const key = `${gap.from}|${gap.to}|${gap.reason}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(gap);
  }
  return out.sort((a, b) => (a.from < b.from ? -1 : a.from > b.from ? 1 : 0));
}

/** 시계열에 받은 구간을 끼운다 — 점·결측만 바꾸고 나머지 칸(기준 통화·잠정 시작 등)은 원래 것이다. */
export function withDetail<P extends Dated, S extends WithPoints<P>>(base: S, detail: S, range: ZoomRange): S {
  return { ...base, points: spliceWindow(base.points, detail.points, range), gaps: mergeGaps(base.gaps, detail.gaps) };
}

/** 비교 블록의 현재 가치 선(`valueLine`)에도 같은 구간을 끼운다. 매도 후 금액은 원래 것이다(기준일의 값). */
export function withValueDetail<L extends { points: Dated[] }>(base: L, detail: L, range: ZoomRange): L {
  return { ...base, points: spliceWindow(base.points, detail.points, range) };
}
