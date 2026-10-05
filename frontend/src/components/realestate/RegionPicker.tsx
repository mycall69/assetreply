"use client";

/**
 * 지역 고르기 (T026) — 009 FR-002, FR-015, SC-007, ui-wireframes E1·E2·E9·접근성.
 *
 * 지역은 **풀다운 셋**(시·도 → 시·군·구 → 법정동)이고 각 `select`에 `label`이 붙는다. 상위를 고르기 전에는 하위를 쓸 수 없다.
 * 고르지 않은 풀다운의 값은 **빈 값**이다 — 첫 항목이 골라진 것처럼 보이면 상위를 바꾼 뒤 하위가 남은 것과 같다(SC-007).
 *
 * - 행정구역을 처음 받는 중이면 풀다운 자리에 진행(받은 쪽 / 쪽 수)을 보인다. 스냅샷이 오기 전에는 숫자를 보이지 않는다
 * - **그 수집이 실패하면** 풀다운 자리에 종류별 문구·할 일(`role="alert"`)을 보이고 풀다운을 막는다(FR-015) — 빈 풀다운만 두면
 *   고를 지역이 없다고 읽는다. 다시 시도는 화면을 다시 열 때다
 */

import type { RealEstateProgressSnapshot } from "@/lib/realEstateProgressStream";
import type { RealEstateRegionCollecting, RealEstateRegionLevel } from "@/lib/types";
import {
  realEstateFailureText,
  type RealEstateFailureNotice,
  type RealEstateRegionLists,
} from "@/stores/realEstateStore";

const LEVELS: ReadonlyArray<readonly [RealEstateRegionLevel, string]> = [
  ["sido", "시·도"],
  ["sgg", "시·군·구"],
  ["umd", "동"],
];

export function RegionPicker({
  regions,
  selection,
  onSelect,
  collecting,
  progress,
  failure,
}: {
  regions: RealEstateRegionLists;
  selection: Record<RealEstateRegionLevel, string | null>;
  onSelect: (level: RealEstateRegionLevel, code: string) => void;
  /** 행정구역을 처음 받는 중(202). */
  collecting: RealEstateRegionCollecting | null;
  /** 그 작업의 진행 — 받은 쪽 / 쪽 수. */
  progress: RealEstateProgressSnapshot | null;
  /** 그 작업의 실패. */
  failure: RealEstateFailureNotice | null;
}) {
  const receiving = collecting !== null && failure === null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
      <span className="w-10 text-gray-500">지역</span>
      {receiving ? (
        <p role="status" className="text-gray-700">
          <span aria-hidden="true">⟳ </span>행정구역 목록을 받고 있습니다
          {progress !== null && progress.total > 0 && (
            <span className="tabular-nums text-gray-500">
              {" | "}{progress.done.toLocaleString("ko-KR")} / {progress.total.toLocaleString("ko-KR")}쪽
            </span>
          )}
        </p>
      ) : (
        <>
          {LEVELS.map(([level, label]) => {
            const items = regions[level];
            const id = `realestate-region-${level}`;
            return (
              <span key={level}>
                <label htmlFor={id} className="sr-only">{label}</label>
                <select
                  id={id}
                  value={selection[level] ?? ""}
                  disabled={failure !== null || items === null}
                  onChange={(e) => {
                    if (e.target.value !== "") onSelect(level, e.target.value);
                  }}
                  className="rounded border border-gray-300 px-2 py-1 disabled:bg-gray-50 disabled:text-gray-400"
                >
                  {/* 고르지 않았음을 보이는 빈 값 — 첫 항목이 골라진 것처럼 보이지 않게 한다. */}
                  <option value="" disabled>{label} 선택</option>
                  {(items ?? []).map((r) => (
                    <option key={r.code} value={r.code}>{r.name}</option>
                  ))}
                </select>
              </span>
            );
          })}
          {failure !== null && (
            <p role="alert"
              className="w-full rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">
              ⚠ 행정구역 목록을 받지 못했습니다. {realEstateFailureText(failure.kind, failure.reason)}
            </p>
          )}
        </>
      )}
    </div>
  );
}
