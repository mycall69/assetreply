"use client";

/**
 * 시간축 커버리지 막대 (T045) — contracts/ui-wireframes.md W2.
 *
 * 막대 하나가 통화의 전체 대상 기간이다. 왼쪽 끝이 `targetFrom`, 오른쪽 끝이 `targetTo`.
 *
 * **이어받기 표식(▲)이 이 화면의 핵심 요구다** (FR-011). 없으면 사용자는 이어받기가
 * 동작했는지 판단할 수 없다. 처음부터 수집하는 경우에는 두지 않는다 — 모든 막대에 늘
 * 표식이 있으면 의미가 사라진다.
 *
 * 구간을 **색만으로 구별하지 않는다.** 명암과 패턴으로도 갈리고, 진행률 텍스트 대체를
 * 둔다 (접근성).
 */

import type { TimelineSnapshot } from "@/lib/types";

function day(value: string): number {
  return new Date(`${value}T00:00:00`).getTime();
}

/** 기간 안에서의 위치를 백분율로. 범위를 벗어나면 잘라낸다. */
function percent(target: string, from: number, span: number): number {
  if (span <= 0) return 0;
  return Math.min(100, Math.max(0, ((day(target) - from) / span) * 100));
}

export function CurrencyTimeline({ snapshot }: { snapshot: TimelineSnapshot }) {
  const from = day(snapshot.targetFrom);
  const span = day(snapshot.targetTo) - from;

  const coveredStart = snapshot.coveredFrom
    ? percent(snapshot.coveredFrom, from, span)
    : 0;
  const coveredEnd = snapshot.coveredThrough
    ? percent(snapshot.coveredThrough, from, span)
    : 0;
  const coveredWidth = Math.max(0, coveredEnd - coveredStart);

  const active = snapshot.activeJob;
  const chunk = active?.currentChunk ?? null;
  const chunkStart = chunk ? percent(chunk.from, from, span) : 0;
  const chunkWidth = chunk
    ? Math.max(0.5, percent(chunk.to, from, span) - chunkStart)
    : 0;

  // 처음부터 받는 경우에는 표식을 두지 않는다. 늘 있으면 의미가 없다.
  const resumed =
    active !== undefined && active.rangeStart !== snapshot.targetFrom;
  const resumeAt = resumed ? percent(active.rangeStart, from, span) : null;

  const pct = Math.round(coveredWidth);
  const label = snapshot.coveredThrough
    ? `${snapshot.targetFrom}부터 ${snapshot.coveredThrough}까지 수집 완료 (약 ${pct}%)`
    : "아직 수집하지 않았습니다";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] text-gray-500">
        <span>{snapshot.targetFrom.slice(0, 4)}</span>
        <span>{snapshot.targetTo.slice(0, 4)}</span>
      </div>

      <div
        role="img"
        aria-label={label}
        className="relative h-5 w-full overflow-hidden rounded border border-gray-300 bg-[repeating-linear-gradient(45deg,#f3f4f6_0,#f3f4f6_4px,#e5e7eb_4px,#e5e7eb_8px)]"
      >
        {coveredWidth > 0 && (
          <div
            data-testid="covered"
            className="absolute inset-y-0 bg-gray-700"
            style={{ left: `${coveredStart}%`, width: `${coveredWidth}%` }}
          />
        )}
        {chunk && (
          <div
            data-testid="current-chunk"
            // 진행 구간은 완료 구간과 명암·패턴 모두로 갈린다.
            className="absolute inset-y-0 bg-[repeating-linear-gradient(45deg,#f59e0b_0,#f59e0b_3px,#fbbf24_3px,#fbbf24_6px)]"
            style={{ left: `${chunkStart}%`, width: `${chunkWidth}%` }}
          />
        )}
        {resumeAt !== null && (
          <div
            data-testid="resume-marker"
            title={`${active?.rangeStart}부터 이어받는 중`}
            className="absolute inset-y-0 w-0.5 bg-sky-600"
            style={{ left: `${resumeAt}%` }}
          />
        )}
      </div>

      <p className="sr-only">{label}</p>

      {resumed && (
        <p className="text-[11px] text-sky-700">
          ▲ {active?.rangeStart}부터 이어받는 중
        </p>
      )}
    </div>
  );
}
