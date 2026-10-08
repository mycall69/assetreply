"use client";

/**
 * 조건이 바뀜 띠 (013 T036) — FR-012a(명확화 6), ui-wireframes F8.
 *
 * 지금 조건이 결과를 낸 조건과 다르면 결과를 흐리고 이 띠를 둔다. 흐리지 않으면 사용자가 옛 결과를 바뀐 조건의 결과로 읽는다.
 */
export function StaleBanner({ onRerun }: { onRerun: () => void }) {
  return (
    <div role="status" aria-label="조건이 바뀜"
      className="flex flex-wrap items-center gap-2 rounded border border-gray-300 bg-gray-50 px-4 py-2 text-sm text-gray-700">
      <span>조건이 바뀌었습니다 — 다시 실행하면 반영됩니다</span>
      <button type="button" onClick={onRerun} className="rounded border border-gray-400 px-2 py-0.5 hover:bg-gray-100">
        다시 실행
      </button>
    </div>
  );
}
