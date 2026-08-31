"use client";

/**
 * 특정일 검색 / 하이라이트 (T041) — contracts/ui-wireframes.md W2.
 *
 * 여기서 고른 날짜가 화면 전체의 선택 날짜가 된다(FR-008). 고시가 없는 날도 **선택
 * 가능하다** — 그 사실을 알리는 것이 화면의 역할이다(W3-a).
 */

import type { RangeNotice } from "@/stores/fxWorkspaceStore";

export function DateHighlightInput({
  value,
  notice,
  onChange,
}: {
  value: string | null;
  notice: RangeNotice | null;
  onChange: (date: string) => void;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-5">
      <label htmlFor="highlight-date" className="text-xs text-gray-500">
        특정일 검색 / 하이라이트
      </label>
      <input
        id="highlight-date"
        type="date"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full rounded border border-gray-300 px-3 py-2 text-sm tabular-nums"
      />
      {notice && (
        <p role="alert" className="mt-2 text-xs text-amber-700">
          {notice.message}
        </p>
      )}
    </div>
  );
}
