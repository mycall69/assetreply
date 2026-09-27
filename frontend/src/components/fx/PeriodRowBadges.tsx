"use client";

/**
 * 행 표시 (T034) — 004 FR-013, FR-014, FR-015a, FR-015b.
 * contracts/ui-wireframes.md W2.
 *
 * **셋을 하나의 아이콘으로 합치지 않는다.** 기준일이 옮겨졌다·구간이 진행 중이다·값이
 * 잠정이다는 서로 다른 사실이고, 합치면 사용자가 이유를 알 수 없어 표시가 무의미해진다
 * (FR-015b). 잠정값은 002가 정한 ⚠를 `DailyTable`이 그대로 쓴다.
 *
 * 옮겨진 행은 **원래 기준일을 함께 알린다**. 없으면 사용자는 1,401.20을 7월 17일의
 * 값으로 믿는다 — 값은 정확한데 **무엇의 값인지**를 잘못 알게 된다 (FR-013).
 *
 * `📅`·`⏳`는 장식이 아니라 의미를 지니므로 **기호만으로 전달하지 않는다.** 각각
 * 텍스트 대체를 두고 색에도 기대지 않는다 (ui-wireframes 접근성).
 */

import type { PeriodRow, PeriodUnit } from "@/lib/types";

/** 옮겨지지 않은 행에는 표시가 없다 (FR-014). 늘 있으면 구별의 의미가 사라진다. */
export function PeriodRowBadges({
  row,
  unit,
}: {
  row: PeriodRow;
  unit: PeriodUnit;
}) {
  if (unit === "daily") return null;

  const anchorName = unit === "weekly" ? "금" : "말일";
  const periodName = unit === "weekly" ? "이번 주가" : "이번 달이";

  return (
    <>
      {row.shiftedFrom !== undefined && (
        <span
          role="img"
          className="ml-1"
          title={`기준일 ${row.shiftedFrom}(${anchorName})에 고시가 없어 ${row.date} 값입니다`}
          aria-label={`기준일 ${row.shiftedFrom}(${anchorName})에 고시가 없어 ${row.date} 값입니다`}
        >
          📅
        </span>
      )}
      {row.isOngoing && (
        <span
          role="img"
          className="ml-1"
          title={`${periodName} 아직 끝나지 않았습니다`}
          aria-label={`${periodName} 아직 끝나지 않았습니다`}
        >
          ⏳
        </span>
      )}
    </>
  );
}
