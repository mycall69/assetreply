/**
 * 지표 모달 테스트의 응답 도우미 (014 반복 2026-10-10b) — contracts A2(range·장중)·A7·A8.
 */
import type {
  IndicatorCommentaryResponse,
  IndicatorIntradayResponse,
  IndicatorRangeSeries,
  IndicatorTableResponse,
  IndicatorTableRow,
} from "@/lib/types";

const INDICATOR = {
  id: "sp500", name: "S&P 500", unit: "포인트", kind: "index" as const, group: "us" as const,
  market: { key: "us_equity", timezone: "America/New_York" }, notes: [] as string[],
};

export function rangeSeriesOf(over: Partial<IndicatorRangeSeries> = {}): IndicatorRangeSeries {
  return {
    indicator: INDICATOR,
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

export function intradayOf(over: Partial<IndicatorIntradayResponse> = {}): IndicatorIntradayResponse {
  return {
    indicator: INDICATOR,
    range: "1d",
    intraday: true,
    status: "ok",
    fetchedAt: "2026-10-09T17:40:00Z",
    points: [
      { time: "2026-10-09T17:30:00Z", value: "7801.250000", provisional: true },
      { time: "2026-10-09T17:35:00Z", value: "7802.500000", provisional: true },
    ],
    notes: [],
    failure: null,
    ...over,
  };
}

export function rowOf(date: string, over: Partial<Extract<IndicatorTableRow, { kind: "period" }>> = {}): IndicatorTableRow {
  return {
    kind: "period", date, open: "7790.120000", high: "7812.500000", low: "7701.330000", close: "7801.250000",
    change: "35.890000", changeRate: "0.004622", provisional: false, ...over,
  };
}

export function tableOf(over: Partial<IndicatorTableResponse> = {}): IndicatorTableResponse {
  return {
    indicator: { id: "sp500", name: "S&P 500", unit: "포인트" },
    period: "daily",
    rows: [
      rowOf("2026-10-09", { open: null, high: null, low: null, close: "7800.000000", change: "34.640000", provisional: true }),
      rowOf("2026-10-08", { change: "-36.410000", changeRate: "-0.004667" }),
    ],
    hasMore: false,
    oldestReturned: "2026-10-08",
    seriesNote: null,
    ...over,
  };
}

export function commentaryOf(over: Partial<IndicatorCommentaryResponse> = {}): IndicatorCommentaryResponse {
  return {
    indicator: "sp500",
    source: "네이버 증권",
    sourceUrl: "https://stock.naver.com/news",
    status: "ok",
    fetchedAt: "2026-10-09T13:30:00Z",
    sessionDate: "2026-10-08",
    items: [
      {
        title: "\"오픈AI 매출 기대 못 미친다\"…S&P500·나스닥 '하락' [뉴욕증시]", summary: "뉴욕증시가 하락 마감했다.",
        publisher: "한국경제", publishedAt: "2026-10-08T21:05:00Z", publishedText: null,
        url: "https://n.news.naver.com/mnews/article/015/0005340900",
      },
    ],
    failure: null,
    ...over,
  };
}
