"use client";

/**
 * 주식·가상자산 일자별 표의 기간 표시 (012 T032) — FR-004, FR-004a, FR-010, contracts/ui-wireframes.md F3.
 *
 * 외환 `PeriodRowBadges`와 같은 모양이다(📅·⏳, 글자 설명). 문구만 그 표의 말이다 — 주식은 "시세", 가상자산은 "일봉". 외환 부품을 고치지 않고 따로
 * 두는 이유: 외환은 004 테스트가 문구까지 고정한 검증된 부품이다.
 *
 * - 📅 = 기준일(그 주 금요일·그 달 말일)이 옮겨졌다 — 그날 값이 아니라 다른 날 값이다. 없으면 사용자는 그 값을 금요일·말일의 값으로 오해한다(FR-004)
 * - ⏳ = 구간이 아직 끝나지 않았다(FR-004a). 없으면 이번 달 중간의 값을 "이번 달 값"으로 읽는다
 * - 둘은 서로 다른 사실이고 한 행에 함께 붙을 수 있다 — 하나로 합치지 않는다(004 FR-015b)
 * - 기호만으로 전달하지 않는다 — `title`과 `aria-label`이 같은 글이다. 일 단위에는 표시가 없다
 *
 * 화면은 대표일을 계산하지 않는다 — 서버가 준 `shiftedFrom`·`isOngoing`을 그린다.
 */

import type { PeriodMarked, PeriodUnit } from "@/lib/types";

export type MarkAsset = "stock" | "crypto";

export function PeriodMarks({
  row,
  unit,
  asset,
}: {
  row: PeriodMarked & { date: string };
  unit: PeriodUnit;
  asset: MarkAsset;
}) {
  if (unit === "daily") return null;
  const shifted = row.shiftedFrom;
  if (shifted === undefined && row.isOngoing !== true) return null;

  const anchorName = unit === "weekly" ? "금" : "말일";
  // 조사까지 함께 둔다 — "시세가"·"일봉이"
  const quote = asset === "stock" ? "시세가" : "일봉이";
  const shiftedText = `기준일 ${shifted}(${anchorName})에 ${quote} 없어 ${row.date} 값입니다`;
  const ongoingText = unit === "weekly" ? "이번 주가 아직 끝나지 않았습니다" : "이번 달이 아직 끝나지 않았습니다";

  return (
    <>
      {shifted !== undefined && (
        <span role="img" className="ml-1" title={shiftedText} aria-label={shiftedText}>
          📅
        </span>
      )}
      {row.isOngoing === true && (
        <span role="img" className="ml-1" title={ongoingText} aria-label={ongoingText}>
          ⏳
        </span>
      )}
    </>
  );
}
