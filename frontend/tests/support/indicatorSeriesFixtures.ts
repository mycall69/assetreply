/**
 * 지표 화면 테스트의 응답 도우미 (014) — contracts/rest-api.md A2.
 */
import type { IndicatorCollecting, IndicatorSeriesResponse } from "@/lib/types";

export function seriesOf(over: Partial<IndicatorSeriesResponse> = {}): IndicatorSeriesResponse {
  return {
    indicator: {
      id: "sp500", name: "S&P 500", unit: "포인트", kind: "index", group: "us",
      market: { key: "us_equity", timezone: "America/New_York" }, notes: [],
    },
    // 014 승인 2026-10-10(반복 2026-10-10b T111) — 단위 `unit` → 보는 기간 `range`
    range: "1y",
    history: {
      source: "yahoo", firstDate: "1927-12-30", lastDate: "2026-10-08", tailPending: false,
      lastSuccessAt: "2026-10-09T04:30:02Z", lastFailure: null,
    },
    points: [
      { date: "2026-10-06", value: "7701.110000" },
      { date: "2026-10-07", value: "7801.770000" },
      { date: "2026-10-08", value: "7765.360000" },
      { date: "2026-10-09", value: "7793.420000", provisional: true },
    ],
    gaps: [],
    downsampled: false,
    sourcePointCount: 4,
    ...over,
  };
}

export function collectingOf(over: Partial<IndicatorCollecting> = {}): IndicatorCollecting {
  return {
    status: "collecting",
    indicator: { id: "sp500", name: "S&P 500" },
    progress: { firstDay: "1927-12-30", coveredFrom: "2010-01-04", coveredThrough: "2026-10-08", remainingDays: 29957 },
    failure: null,
    progressUrl: "/api/dashboard/indicators/sp500/progress",
    ...over,
  };
}
