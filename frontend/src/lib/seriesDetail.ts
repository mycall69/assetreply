/**
 * 확대 구간의 일 단위 자료 받기 (014 반복 2026-10-11c) — spec FR-038, contracts A13, research R14-31.
 *
 * - 받는 그래프: 주식은 **늘**(시계열이 매달 첫 거래일·사건 날뿐이다), 가상자산·외환은 받은 자료가 **줄여졌을 때만**(`downsampled`). 예금·부동산은
 *   받지 않는다(달마다의 자료). 대시보드 지표는 이미 일봉 전부라 이 모듈을 쓰지 않는다
 * - 주식·가상자산은 그 시계열 경로(메뉴·비교)에 보기 구간 질의 `viewFrom`·`viewTo`를, 외환은 이미 있는 `from`·`to`를 싣는다. 구간 안은 줄이지 않게
 *   `maxPoints=5000`(20년 남짓의 거래일)이다
 * - 202(수집 본문)는 받지 못한 것으로 친다 — 원래 점으로 보인다
 * - 투자 비교의 대상마다 받기는 **한 번에 셋**이다(014 반복 2026-10-13 — FR-046, `lib/concurrency`) — 대상 100개를 한꺼번에 보내면 같은 주소 연결
 *   6개를 다 차지한다. 확대마다 새 차례다(앞 확대의 늦은 응답은 `useZoomDetail`이 버린다)
 */
import { apiClient } from "@/lib/apiClient";
import type { ZoomRange } from "@/lib/chartZoom";
import { DETAIL_REQUESTS, createLimiter } from "@/lib/concurrency";
import type { ComparisonBlock, ComparisonResponse, SeriesResponse, SimulationSeriesResponse } from "@/lib/types";

export const DETAIL_MAX_POINTS = 5000;

/** 구간을 받는 그래프인가 — 경로의 자산군과 받은 자료가 줄여졌는지로 정한다. */
export function needsDetail(path: string, series: { downsampled: boolean }): boolean {
  if (path.startsWith("/api/stocks/") || path.startsWith("/api/comparison/stocks/")) return true;
  if (path.startsWith("/api/crypto/") || path.startsWith("/api/comparison/crypto/") || path.startsWith("/api/fx/")) {
    return series.downsampled;
  }
  return false;
}

/** 주식·가상자산 시계열 경로에 보기 구간 질의를 붙인다. */
export function withView(path: string, range: ZoomRange): string {
  const query = `viewFrom=${range.from}&viewTo=${range.to}&maxPoints=${DETAIL_MAX_POINTS}`;
  return `${path}${path.includes("?") ? "&" : "?"}${query}`;
}

/** 외환 시계열의 구간 — 경로가 이미 `from`·`to`를 받는다. */
export function fxDetailPath(currency: string, range: ZoomRange): string {
  return `/api/fx/series?currency=${encodeURIComponent(currency)}&from=${range.from}&to=${range.to}&maxPoints=${DETAIL_MAX_POINTS}`;
}

const collecting = (body: object) => "status" in body && (body as { status: unknown }).status === "collecting";

export async function fetchSeriesDetail(path: string, range: ZoomRange): Promise<SimulationSeriesResponse> {
  const body = await apiClient.get<SimulationSeriesResponse>(withView(path, range));
  if (collecting(body)) throw new Error("collecting");
  return body;
}

export interface CompareDetail {
  series: SimulationSeriesResponse;
  valueLine?: ComparisonBlock["valueLine"];
}

export async function fetchCompareDetail(path: string, range: ZoomRange): Promise<CompareDetail> {
  const body = await apiClient.get<ComparisonResponse>(withView(path, range));
  if (collecting(body)) throw new Error("collecting");
  return { series: body.series, valueLine: body.comparison.valueLine };
}

export async function fetchFxDetail(currency: string, range: ZoomRange): Promise<SeriesResponse> {
  const body = await apiClient.get<SeriesResponse>(fxDetailPath(currency, range));
  if (collecting(body)) throw new Error("collecting");
  return body;
}

/** 시계열 경로와 받은 자료로 그래프의 구간 받기 함수를 만든다 — 받지 않는 그래프면 `undefined`(지금처럼 확대만). */
export function seriesDetailLoader(
  path: string | null, series: SimulationSeriesResponse | null,
): ((range: ZoomRange) => Promise<SimulationSeriesResponse>) | undefined {
  if (path === null || series === null || !needsDetail(path, series)) return undefined;
  return (range) => fetchSeriesDetail(path, range);
}

/** 투자 비교의 대상마다 구간을 받는 함수 — 받을 대상(주식 늘·가상자산은 줄였을 때)이 없으면 `undefined`. 일부만 받으면 받은 대상만 끼운다. */
export function compareDetailLoader(
  entries: { key: string; path: string; series: SimulationSeriesResponse }[],
): ((range: ZoomRange) => Promise<Record<string, CompareDetail>>) | undefined {
  const wanted = entries.filter((entry) => needsDetail(entry.path, entry.series));
  if (wanted.length === 0) return undefined;
  return async (range) => {
    const slots = createLimiter(DETAIL_REQUESTS);
    const settled = await Promise.allSettled(wanted.map((entry) => slots.run(() => fetchCompareDetail(entry.path, range))));
    const out: Record<string, CompareDetail> = {};
    settled.forEach((result, index) => {
      if (result.status === "fulfilled") out[wanted[index].key] = result.value;
    });
    if (Object.keys(out).length === 0) throw new Error("detail");
    return out;
  };
}
