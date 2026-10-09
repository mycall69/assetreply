/**
 * 대시보드 화면 테스트의 응답 도우미 (014) — contracts/rest-api.md A1.
 *
 * 값은 서버가 내는 문자열 그대로다(원칙 VI). 2026-10-09(한글날) 한국 시간 오후의 모습을 기본으로 둔다.
 */
import type {
  DashboardIndicator,
  DashboardQuote,
  DashboardQuotesResponse,
} from "@/lib/types";

type Base = Pick<DashboardIndicator, "id" | "name" | "group" | "order" | "unit" | "kind" | "market" | "notes">;

export const BASES: Base[] = [
  { id: "kospi", name: "KOSPI", group: "korea", order: 1, unit: "포인트", kind: "index", market: { key: "krx", timezone: "Asia/Seoul" }, notes: [] },
  { id: "kosdaq", name: "KOSDAQ", group: "korea", order: 2, unit: "포인트", kind: "index", market: { key: "krx", timezone: "Asia/Seoul" }, notes: [] },
  { id: "dow", name: "다우존스 산업평균", group: "us", order: 3, unit: "포인트", kind: "index", market: { key: "us_equity", timezone: "America/New_York" }, notes: [] },
  { id: "nasdaq", name: "나스닥 종합", group: "us", order: 4, unit: "포인트", kind: "index", market: { key: "us_equity", timezone: "America/New_York" }, notes: [] },
  { id: "sp500", name: "S&P 500", group: "us", order: 5, unit: "포인트", kind: "index", market: { key: "us_equity", timezone: "America/New_York" }, notes: [] },
  { id: "sox", name: "필라델피아 반도체", group: "us", order: 6, unit: "포인트", kind: "index", market: { key: "us_equity", timezone: "America/New_York" }, notes: [] },
  { id: "nikkei225", name: "니케이 225", group: "asia", order: 7, unit: "포인트", kind: "index", market: { key: "tse", timezone: "Asia/Tokyo" }, notes: [] },
  { id: "hangseng", name: "항셍", group: "asia", order: 8, unit: "포인트", kind: "index", market: { key: "hkex", timezone: "Asia/Hong_Kong" }, notes: [] },
  { id: "shanghai", name: "상해 종합", group: "asia", order: 9, unit: "포인트", kind: "index", market: { key: "sse", timezone: "Asia/Shanghai" }, notes: [] },
  { id: "usd", name: "달러", group: "fx", order: 10, unit: "원", kind: "fx", market: { key: "fx", timezone: "Europe/London" }, notes: ["market_fx"] },
  { id: "jpy", name: "엔(100엔)", group: "fx", order: 11, unit: "원(100엔당)", kind: "fx", market: { key: "fx", timezone: "Europe/London" }, notes: ["market_fx"] },
  { id: "eur", name: "유로", group: "fx", order: 12, unit: "원", kind: "fx", market: { key: "fx", timezone: "Europe/London" }, notes: ["market_fx"] },
  { id: "wti", name: "WTI 원유", group: "commodity", order: 13, unit: "USD/배럴", kind: "future", market: { key: "cme", timezone: "America/New_York" }, notes: ["future_roll"] },
  { id: "gold", name: "금", group: "commodity", order: 14, unit: "USD/트로이온스", kind: "future", market: { key: "cme", timezone: "America/New_York" }, notes: ["future_roll"] },
  { id: "vix", name: "VIX", group: "commodity", order: 15, unit: "포인트", kind: "volatility", market: { key: "cboe", timezone: "America/Chicago" }, notes: [] },
];

export function quoteOf(over: Partial<DashboardQuote> = {}): DashboardQuote {
  return {
    value: "6625.930000",
    valueTime: "2026-10-08T11:05:40Z",
    sessionDate: "2026-10-08",
    state: "holiday",
    provisional: false,
    delayMinutes: null,
    previous: { close: "6803.900000", date: "2026-10-07", from: "history" },
    change: "-177.970000",
    changeRate: "-0.026157",
    changeRateBlank: null,
    direction: "down",
    ...over,
  };
}

export function indicatorOf(id: string, over: Partial<DashboardIndicator> = {}): DashboardIndicator {
  const base = BASES.find((b) => b.id === id);
  if (!base) throw new Error(`모르는 지표 ${id}`);
  return { ...base, status: "ok", quote: quoteOf(), stale: false, failure: null, ...over };
}

export function quotesOf(over: Record<string, Partial<DashboardIndicator>> = {}): DashboardQuotesResponse {
  return {
    fetchedAt: "2026-10-09T05:30:12Z",
    refreshAfterSeconds: 60,
    source: "Yahoo Finance",
    indicators: BASES.map((b) => indicatorOf(b.id, over[b.id] ?? {})),
  };
}
