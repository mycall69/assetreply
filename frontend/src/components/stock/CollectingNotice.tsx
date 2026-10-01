"use client";

/**
 * 수집 중 안내 (T095) — 005 FR-047, FR-049, ui-wireframes W7.
 *
 * **부분 결과를 보여주지 않는다**(FR-049). 받은 만큼만 계산한 수익률은 값이 멀쩡해
 * 보이지만 틀린 값이며, 사용자는 그것을 최종 결과로 읽는다. 그래서 숫자 대신 **진행과
 * 기다릴 이유**를 보인다.
 */

import type { StockProgressSnapshot } from "@/lib/stockProgressStream";
import type { SimulationCollecting } from "@/lib/types";

export function CollectingNotice({
  collecting,
  stockName,
  progress,
}: {
  collecting: SimulationCollecting;
  stockName: string;
  progress: StockProgressSnapshot | null;
}) {
  const total = progress?.chunksTotal ?? 0;
  const done = progress?.chunksDone ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <section
      role="status"
      className="space-y-3 rounded-lg border border-gray-200 px-4 py-5 text-sm text-gray-700"
    >
      <p className="font-medium">{stockName}의 시세를 받고 있습니다</p>

      {total > 0 ? (
        <div className="space-y-1">
          <div
            role="progressbar"
            aria-valuenow={done}
            aria-valuemin={0}
            aria-valuemax={total}
            aria-label={`${stockName} 수집 진행`}
            className="h-2 w-full overflow-hidden rounded bg-gray-100"
          >
            <div className="h-full bg-gray-700" style={{ width: `${percent}%` }} />
          </div>
          <p className="text-xs tabular-nums text-gray-500">
            {done} / {total} 구간
          </p>
        </div>
      ) : (
        // 0/0을 보이면 멈춘 것처럼 읽힌다. 아직 시작 단계라는 사실을 말한다.
        <p className="text-xs text-gray-500">시작하는 중…</p>
      )}

      <p className="text-xs tabular-nums text-gray-500">
        받을 구간: {collecting.missingFrom} ~ {collecting.missingThrough}
      </p>
      <p className="text-xs text-gray-500">완료되면 결과가 표시됩니다.</p>
    </section>
  );
}
