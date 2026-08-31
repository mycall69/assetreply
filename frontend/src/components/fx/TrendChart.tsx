"use client";

/**
 * 환율 트렌드 차트 (T041~T044) — contracts/ui-wireframes.md W2.
 *
 * 001의 `FxChart`를 감싸 002가 요구하는 세 가지를 더한다.
 * - 선택 날짜 강조와 그 날짜의 값 표시 (FR-016)
 * - 잠정 구간 구분 (FR-017a)
 * - 선택 날짜가 현재 기간 밖일 때의 안내 (contracts/ui-interaction)
 *
 * 결측 구간을 잇지 않는 규칙은 001의 `FxChart`가 이미 지킨다(FR-017, 헌법 원칙 V).
 */

import { FxChart } from "@/components/FxChart";
import { formatRate } from "@/lib/format";
import type { SeriesCollecting, SeriesResponse } from "@/lib/types";

export function TrendChart({
  series,
  collecting,
  selectedDate,
  loading,
  onSelect,
}: {
  series: SeriesResponse | null;
  collecting: SeriesCollecting | null;
  selectedDate: string | null;
  loading: boolean;
  onSelect: (date: string) => void;
}) {
  if (collecting) {
    return (
      <p role="status" className="py-12 text-center text-sm text-gray-600">
        아직 수집되지 않은 구간이 있어 수집을 시작했습니다. 완료되면 차트가 표시됩니다.
      </p>
    );
  }
  if (loading || series === null) {
    return <p className="py-12 text-center text-sm text-gray-500">불러오는 중…</p>;
  }
  if (series.points.length === 0) {
    return <p className="py-12 text-center text-sm text-gray-500">표시할 구간이 없습니다.</p>;
  }

  const first = series.points[0].date;
  const last = series.points[series.points.length - 1].date;
  const outsideRange =
    selectedDate !== null && (selectedDate < first || selectedDate > last);
  const selectedPoint = series.points.find((p) => p.date === selectedDate) ?? null;
  const provisionalCount = series.points.filter((p) => p.isProvisional).length;

  return (
    <div>
      {/* 선택 날짜 정보를 차트 위에 라벨로 둔다 (W2의 날짜 칩). */}
      {selectedDate && !outsideRange && (
        <p data-testid="highlight-label" className="mb-2 text-xs">
          <span className="rounded bg-red-700 px-2 py-0.5 text-white tabular-nums">
            {selectedDate}
          </span>{" "}
          {selectedPoint ? (
            <span className="text-gray-700 tabular-nums">
              {formatRate(selectedPoint.baseRate)}
            </span>
          ) : (
            // FR-018: 강조선이 값을 가리키지 않는다는 사실이 드러나야 한다.
            <span className="text-gray-500">이 날짜에는 고시가 없습니다</span>
          )}
        </p>
      )}

      {outsideRange && (
        <p role="status" className="mb-2 text-xs text-amber-700">
          선택한 날짜({selectedDate})가 현재 기간 밖입니다. 기간을 넓히면 표시됩니다.
        </p>
      )}

      <FxChart data={series} onSelectDate={onSelect} />

      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        <span>─ 확정</span>
        {provisionalCount > 0 && (
          <span data-testid="provisional-legend" className="text-amber-700">
            ╌ 잠정 ({provisionalCount}개)
          </span>
        )}
        <span>▨ 고시 없음 · ╌╌ 미수집</span>
        {series.downsampled && (
          <span>
            표시 {series.points.length}개 / 원본 {series.sourcePointCount}개 (LTTB)
          </span>
        )}
      </p>
    </div>
  );
}
