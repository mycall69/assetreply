"use client";

/**
 * 수집 진행 화면 (T101) — contracts/ui-sketches.md S4.
 *
 * **중단 화면은 "이미 저장된 구간은 유효하다"를 반드시 말해야 한다** (FR-013).
 * 이 문장이 없으면 사용자는 전부 실패한 것으로 판단하고 처음부터 다시 돌린다.
 */

import type { ProgressState } from "@/lib/types";

const STATUS_LABEL: Record<ProgressState["status"], string> = {
  running: "수집 중",
  succeeded: "완료",
  partial: "부분 성공",
  failed: "실패",
};

export function CollectionProgress({
  state,
  onRetry,
}: {
  state: ProgressState;
  onRetry?: () => void;
}) {
  const stopped = state.status === "partial" || state.status === "failed";
  const percent = state.chunksTotal
    ? Math.round((state.chunksDone / state.chunksTotal) * 100)
    : 0;

  return (
    <section className="rounded-lg border border-gray-200 p-6">
      {stopped ? (
        <p className="text-gray-800">⚠ 수집이 중단되었습니다.</p>
      ) : (
        <p className="text-gray-800">{state.currency} 환율을 수집하고 있습니다.</p>
      )}

      <div className="mt-4 flex items-center gap-4">
        <div
          role="progressbar"
          aria-valuenow={state.chunksDone}
          aria-valuemin={0}
          aria-valuemax={state.chunksTotal}
          aria-label="수집 진행률"
          className="h-2 flex-1 overflow-hidden rounded bg-gray-200"
        >
          <div
            className={`h-full ${stopped ? "bg-amber-500" : "bg-gray-900"}`}
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="text-sm tabular-nums text-gray-600">
          {state.chunksDone} / {state.chunksTotal} 구간
        </span>
      </div>

      <dl className="mt-4 space-y-1 text-sm">
        {state.currentRange && !stopped && (
          <div className="flex gap-3">
            <dt className="w-20 text-gray-500">현재 구간</dt>
            <dd>
              {state.currentRange.from} ~ {state.currentRange.to}
            </dd>
          </div>
        )}
        {state.coveredThrough && (
          <div className="flex gap-3">
            <dt className="w-20 text-gray-500">수집 완료</dt>
            <dd>{state.coveredThrough}까지</dd>
          </div>
        )}
        <div className="flex gap-3">
          <dt className="w-20 text-gray-500">상태</dt>
          <dd>{STATUS_LABEL[state.status]}</dd>
        </div>
      </dl>

      {stopped && (
        <div className="mt-5 space-y-3">
          {state.lastError && (
            <p className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
              사유: {state.lastError}
            </p>
          )}
          {/* FR-013 — 이 문장이 빠지면 사용자가 처음부터 다시 돌린다 */}
          <p className="text-sm text-gray-600">
            위 완료 구간까지의 데이터는 정상적으로 저장되어 조회할 수 있습니다.
          </p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded bg-gray-900 px-4 py-2 text-sm text-white"
            >
              다시 시도
            </button>
          )}
        </div>
      )}
    </section>
  );
}
