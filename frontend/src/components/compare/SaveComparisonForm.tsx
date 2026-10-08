"use client";

/**
 * 비교 저장 칸 (013 T076) — FR-016, ui-wireframes F9.
 *
 * "저장"을 누르면 이름 칸이 열린다 — 처음 값은 자동 이름(`autoName`)이고 사용자가 고친다. 공백만인 이름은 저장 단추가 꺼진다. 저장할 수 없으면(흐림·막힘·
 * 결과 없음 — 스토어 `saveBlockReason`) 여는 단추가 꺼지고 까닭이 곁에 보인다 — 까닭 없이 꺼진 단추는 고장으로 읽힌다. 저장이 실패하면 칸이 열린 채 이름이
 * 남는다(실패 문구는 저장한 비교 칸의 알림 — FR-019).
 */
import { useState } from "react";

export function SaveComparisonForm({ defaultName, reason, saving, onSave }: {
  defaultName: string;
  /** 저장할 수 없는 까닭. `null`이면 저장할 수 있다. */
  reason: string | null;
  saving: boolean;
  /** 앞뒤 공백을 뺀 이름으로 부른다. 성공하면 `true` — 칸이 닫힌다. */
  onSave: (name: string) => Promise<boolean>;
}) {
  const [name, setName] = useState<string | null>(null);

  if (name === null) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button type="button" disabled={reason !== null} onClick={() => setName(defaultName)}
          className="rounded border border-gray-300 px-3 py-1 text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40">
          저장
        </button>
        {reason !== null && <span className="text-xs text-gray-500">{reason}</span>}
      </div>
    );
  }

  const trimmed = name.trim();
  return (
    <form className="flex flex-wrap items-center gap-2 text-sm" onSubmit={(e) => {
      e.preventDefault();
      if (trimmed === "" || saving || reason !== null) return;
      void onSave(trimmed).then((done) => {
        if (done) setName(null);
      });
    }}>
      <input type="text" aria-label="비교 이름" value={name} maxLength={100} onChange={(e) => setName(e.target.value)}
        className="w-80 rounded border border-gray-300 px-2 py-1" />
      <button type="submit" disabled={trimmed === "" || saving || reason !== null}
        className="rounded bg-gray-900 px-3 py-1 text-white disabled:cursor-not-allowed disabled:opacity-40">
        저장
      </button>
      <button type="button" onClick={() => setName(null)}
        className="rounded border border-gray-300 px-3 py-1 text-gray-700 hover:bg-gray-50">
        취소
      </button>
      {reason !== null && <span className="text-xs text-gray-500">{reason}</span>}
    </form>
  );
}
