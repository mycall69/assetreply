"use client";

/**
 * 최근 기록 목록 (T059) — contracts/ui-wireframes.md W6.
 *
 * **`고시 없음`과 `구간 실패`를 다른 문구·색으로 쓰는 것이 FR-021의 시각적 귀결이다.**
 * 휴일이라 값이 없는 것과 수집이 실패한 것을 같게 보여주면, 나중에 시계열 공백의
 * 원인을 되짚을 때 기록이 아무 도움이 되지 않는다.
 *
 * 보관 범위를 하단에 명시한다 (FR-023). 오래된 기록이 없는 것이 고장이 아니라
 * 설계임을 알린다.
 */

import type { CollectionEventKind, CollectionEventRow } from "@/lib/types";

const LABELS: Record<CollectionEventKind, { text: string; tone: string }> = {
  job_started: { text: "작업 시작", tone: "text-gray-600" },
  chunk_requested: { text: "구간 요청", tone: "text-gray-600" },
  chunk_stored: { text: "구간 저장", tone: "text-gray-800" },
  chunk_empty: { text: "고시 없음", tone: "text-gray-500" },
  chunk_failed: { text: "구간 실패", tone: "text-red-700" },
  retry: { text: "재시도", tone: "text-amber-700" },
  rate_limited: { text: "한도 소진", tone: "text-red-700" },
  job_finished: { text: "작업 종료", tone: "text-gray-600" },
  log_sink_failed: { text: "파일 기록 실패", tone: "text-amber-700" },
};

function time(iso: string): string {
  return iso.slice(11, 19);
}

export function EventList({
  events,
  jobsKept,
}: {
  events: CollectionEventRow[];
  jobsKept: number;
}) {
  return (
    <section className="rounded-lg border border-gray-200">
      <h3 className="border-b border-gray-200 px-4 py-2 text-sm font-semibold text-gray-900">
        최근 기록
      </h3>

      {events.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-gray-500">
          아직 기록이 없습니다.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {events.map((e, i) => {
            const label = LABELS[e.kind];
            return (
              <li
                key={`${e.jobId}-${e.occurredAt}-${i}`}
                className="flex items-baseline gap-3 px-4 py-1.5 text-xs"
              >
                <span className="shrink-0 tabular-nums text-gray-400">
                  {time(e.occurredAt)}
                </span>
                <span className={`w-20 shrink-0 ${label.tone}`}>{label.text}</span>
                <span className="shrink-0 tabular-nums text-gray-600">
                  {e.chunkFrom && e.chunkTo ? `${e.chunkFrom}~${e.chunkTo}` : ""}
                </span>
                <span className="ml-auto shrink-0 tabular-nums text-gray-700">
                  {e.rowsStored !== null ? `${e.rowsStored}건` : ""}
                </span>
                {e.detail && (
                  <span className="max-w-[40%] truncate text-gray-500">{e.detail}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="border-t border-gray-100 px-4 py-2 text-[11px] text-gray-500">
        최근 {jobsKept}개 작업의 기록만 보관합니다
      </p>
    </section>
  );
}
