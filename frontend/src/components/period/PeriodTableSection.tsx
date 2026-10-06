"use client";

/**
 * 일자별 표의 절 — 제목과 단위 탭 (012 T035) — FR-003, FR-006, FR-010, contracts/ui-wireframes.md F2·F5.
 *
 * 외환 "일자별 환율 상세"와 같은 배치다 — 왼쪽이 제목, 오른쪽이 단위 탭(`PeriodTabs`). 단위를 바꾸는 동안에는 표 자리에 "불러오는 중"을 보이고(이전
 * 단위의 행을 남기지 않는다 — 004 FR-010과 같다), 받지 못하면 그 사유를 보인다. 고른 단위는 남는다.
 *
 * 창이 움직이지 않게 하는 일(높이 붙잡기)은 화면이 `onPeriod`를 `useHeightHold`로 감싸 한다 — 이 절은 표의 자리만 맡는다.
 */

import type { ReactNode } from "react";
import { PeriodTabs } from "@/components/fx/PeriodTabs";
import type { PeriodUnit } from "@/lib/types";

export function PeriodTableSection({
  period,
  titles,
  onPeriod,
  loading,
  error,
  children,
}: {
  period: PeriodUnit;
  titles: Record<PeriodUnit, string>;
  onPeriod: (period: PeriodUnit) => void;
  loading: boolean;
  error: string | null;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">일자별 투자 성과</h3>
        <PeriodTabs value={period} onChange={onPeriod} titles={titles} />
      </div>
      {loading ? (
        <p role="status" className="rounded-lg border border-gray-200 px-4 py-6 text-center text-sm text-gray-500">
          ⟳ 불러오는 중…
        </p>
      ) : error !== null ? (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </p>
      ) : (
        children
      )}
    </section>
  );
}
