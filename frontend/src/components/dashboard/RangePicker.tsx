/**
 * 보는 기간 단추 (014 반복 2026-10-10b T121) — FR-011, contracts D3.
 *
 * 여덟 개 — 일·주·월·1년·5년·10년·20년·모두. 기간은 **보는 범위**다(점을 묶지 않는다 — 012 전의 단위 단추를 대체). 일·주는 장중 시세,
 * 월 이상은 그 기간의 일봉 전부다. 고른 단추는 `aria-pressed="true"`다.
 */
import { DEFAULT_INDICATOR_RANGE, INDICATOR_RANGES, type IndicatorRange } from "@/lib/types";

export const RANGE_LABELS: Record<IndicatorRange, string> = {
  "1d": "일",
  "5d": "주",
  "1m": "월",
  "1y": "1년",
  "5y": "5년",
  "10y": "10년",
  "20y": "20년",
  all: "모두",
};

export function RangePicker({ value, onChange }: { value: IndicatorRange; onChange: (range: IndicatorRange) => void }) {
  return (
    <div role="group" aria-label="보는 기간" className="inline-flex flex-wrap rounded border border-gray-300">
      {INDICATOR_RANGES.map((range) => (
        <button key={range} type="button" aria-pressed={value === range} onClick={() => onChange(range)}
          className={`px-3 py-1.5 text-sm ${value === range ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-50"}`}>
          {RANGE_LABELS[range]}
        </button>
      ))}
    </div>
  );
}

/** 주소의 `range` — 틀리거나 없으면 처음 기간(1년)이다(서버와 같은 규칙 — 옛 `unit` 주소가 오류가 되지 않는다). */
export function rangeOf(raw: string | string[] | undefined): IndicatorRange {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return INDICATOR_RANGES.find((r) => r === value) ?? DEFAULT_INDICATOR_RANGE;
}
