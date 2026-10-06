"use client";

/**
 * 기간 표시의 범례 (012 T032) — FR-010, contracts/ui-wireframes.md F3. 외환 `DailyTable` 아래의 범례와 같은 글이다.
 *
 * 주·월에만 둔다 — 일 단위에는 표시가 없어 범례가 뜻을 갖지 않는다.
 */

import type { PeriodUnit } from "@/lib/types";

export function PeriodLegend({ unit }: { unit: PeriodUnit }) {
  if (unit === "daily") return null;
  return (
    <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
      <span className="mr-2">📅 기준일이 옮겨진 행</span>
      <span className="mr-2">⏳ 아직 끝나지 않은 구간</span>
    </p>
  );
}
