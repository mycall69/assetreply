"use client";

/**
 * 수집 현황 화면 (T103) — contracts/ui-sketches.md S6.
 *
 * **실패 사유를 목록 안에 펼쳐 보여준다.** 별도 화면으로 숨기면 SC-011(사후 확인)의
 * 목적이 흐려진다.
 */

import type { CoverageRow, JobRow } from "@/lib/types";

const STATUS_LABEL: Record<JobRow["status"], string> = {
  running: "진행 중",
  succeeded: "성공",
  partial: "부분 성공",
  failed: "실패",
};

export function CollectionStatus({
  coverage,
  jobs,
  onStart,
}: {
  coverage: CoverageRow[];
  jobs: JobRow[];
  onStart?: () => void;
}) {
  return (
    <div className="space-y-8">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">수집 커버리지</h2>
          {onStart && (
            <button
              type="button"
              onClick={onStart}
              className="rounded bg-gray-900 px-4 py-1.5 text-sm text-white"
            >
              지금 수집
            </button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 font-normal">통화</th>
              <th className="py-2 font-normal">수집 완료 구간</th>
              <th className="py-2 font-normal">최초 제공일</th>
              <th className="py-2 font-normal">마지막 갱신</th>
            </tr>
          </thead>
          <tbody>
            {coverage.map((c) => (
              <tr key={c.currency} className="border-b border-gray-100 align-top">
                <td className="py-2 font-medium">
                  {c.currency}
                  {c.staleProvisional && (
                    <span aria-hidden className="ml-1 text-amber-600">⚠</span>
                  )}
                </td>
                <td className="py-2 tabular-nums">
                  {c.coveredFrom} ~ {c.coveredThrough}
                  {/* 잠정 잔존 = 확정 전환이 안 일어났다는 뜻. 해소 방법을 함께 적는다 (FR-043a). */}
                  {c.staleProvisional && (
                    <p data-testid={`stale-${c.currency}`} className="mt-1 text-xs text-amber-700">
                      ⚠ {c.staleProvisional.date}의 값이 아직 확정되지 않았습니다.
                      이 통화의 수집을 실행하면 해소됩니다.
                    </p>
                  )}
                </td>
                <td className="py-2 tabular-nums">{c.firstAvailableDate ?? "—"}</td>
                <td className="py-2 tabular-nums text-gray-500">
                  {c.lastUpdatedAt.slice(0, 16).replace("T", " ")}
                </td>
              </tr>
            ))}
            {coverage.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-gray-500">
                  아직 수집된 데이터가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold">최근 수집 작업</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 font-normal">통화</th>
              <th className="py-2 font-normal">상태</th>
              <th className="py-2 font-normal">구간</th>
              <th className="py-2 font-normal">진행</th>
              <th className="py-2 font-normal">종료</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <>
                <tr key={j.jobId} className="border-b border-gray-100">
                  <td className="py-2 font-medium">{j.currency}</td>
                  <td className="py-2">{STATUS_LABEL[j.status]}</td>
                  <td className="py-2 tabular-nums">
                    {j.rangeStart}~{j.rangeEnd}
                  </td>
                  <td className="py-2 tabular-nums">
                    {j.chunksDone}/{j.chunksTotal}
                  </td>
                  <td className="py-2 tabular-nums text-gray-500">
                    {j.finishedAt?.slice(0, 16).replace("T", " ") ?? "—"}
                  </td>
                </tr>
                {j.lastError && (
                  <tr key={`${j.jobId}-error`} className="border-b border-gray-100">
                    <td colSpan={5} className="pb-2 pl-4 text-sm text-amber-700">
                      └ {j.lastError}
                    </td>
                  </tr>
                )}
              </>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-500">
                  수집 이력이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
