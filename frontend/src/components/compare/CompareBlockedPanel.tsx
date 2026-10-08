"use client";

/**
 * 비교의 막힘 칸 (013 T036) — FR-010, FR-014, ui-wireframes F4.
 *
 * 대상 하나라도 계산할 수 없으면 결과 자리에 이 칸만 보인다(명확화 1). 막힌 대상마다 이름·까닭·할 일이다. 시작일로 풀리는 대상이 있고
 * **수집 중인 대상이 없을 때만** 가장 이른 시작일을 제안한다 — 수집 중인 대상이 끝난 뒤 제안한 날짜에서 다시 막힐 수 있다(SC-003).
 * 제안을 누르면 시작일만 옮긴다 — 몰래 실행하지 않는다(사용자가 바뀐 기간을 보고 실행한다).
 */
import type { BlockReason } from "@/lib/compareBlock";

export function CompareBlockedPanel({ blocked, suggestion, collecting, onMoveStart }: {
  blocked: { key: string; name: string; reason: BlockReason }[];
  suggestion: string | null;
  collecting: number;
  onMoveStart: (date: string) => void;
}) {
  return (
    <section role="alert" aria-label="비교할 수 없습니다"
      className="space-y-2 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <p className="font-semibold">⚠ 비교할 수 없습니다</p>
      <ul className="list-disc space-y-0.5 pl-5">
        {blocked.map((b) => (
          <li key={b.key}>
            {b.name} — {b.reason.text}{b.reason.kind === "start" ? "" : ` · ${b.reason.action}`}
          </li>
        ))}
      </ul>
      {suggestion !== null && (
        <p>
          모든 대상이 가능한 가장 이른 시작일: <strong>{suggestion}</strong>{" "}
          <button type="button" className="ml-1 rounded border border-amber-400 px-2 py-0.5 hover:bg-amber-100"
            onClick={() => onMoveStart(suggestion)}>
            시작일 옮기기
          </button>
        </p>
      )}
      {suggestion === null && collecting > 0 && (
        <p>수집 중인 대상 {collecting}개 — 끝나면 제안 날짜를 정합니다.</p>
      )}
    </section>
  );
}
