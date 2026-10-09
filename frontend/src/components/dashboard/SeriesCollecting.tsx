/**
 * 지표 화면 — 받는 중·실패 (014 T060) — FR-016, contracts D4.
 *
 * 받는 중에는 그래프를 그리지 않는다 — 받은 만큼만 그린 선을 완성된 것처럼 보이지 않는다(FR-016). 진행은 받은 기간과 첫 날이다.
 */
import { failureLabel } from "@/components/dashboard/IndicatorHeader";
import { KST_ZONE, formatZonedTime } from "@/lib/kstClock";
import type { IndicatorCollecting } from "@/lib/types";

export function SeriesCollecting({ collecting, name, onRetry }: {
  collecting: IndicatorCollecting;
  name: string;
  onRetry: () => void;
}) {
  if (collecting.status === "failed") {
    const failure = collecting.failure;
    return (
      <section role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p>
          이력을 받지 못했습니다 — {failureLabel(failure?.kind)}
          {failure?.at && <> · {formatZonedTime(failure.at, KST_ZONE)}</>}
        </p>
        <button type="button" onClick={onRetry} className="mt-2 underline">다시 시도</button>
      </section>
    );
  }
  const progress = collecting.progress;
  return (
    <section aria-live="polite" className="rounded-lg border border-gray-200 p-4 text-sm text-gray-700">
      <p>{name} 이력을 받는 중입니다</p>
      {progress && progress.coveredFrom && (
        <p className="mt-1 text-xs text-gray-500">
          {progress.coveredFrom} ~ {progress.coveredThrough} 받음 (첫 날 {progress.firstDay ?? "확인 중"})
        </p>
      )}
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded bg-gray-100">
        <div className="h-full w-1/3 animate-pulse rounded bg-gray-400" />
      </div>
    </section>
  );
}
