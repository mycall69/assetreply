/**
 * 대시보드 요청 (014 T036·T058·T078) — contracts/rest-api.md A1~A3·A5.
 *
 * 값은 문자열로 받아 문자열로 둔다(원칙 VI) — 공통 클라이언트(`apiClient`)를 쓴다.
 */
import { apiClient } from "@/lib/apiClient";
import type {
  DashboardQuotesResponse,
  IndicatorCollecting,
  IndicatorSeriesResponse,
  IndicatorUnit,
  NewsListResponse,
  NewsSourceKey,
} from "@/lib/types";

/** 지표 15개의 현재 시세. 출처가 실패해도 200이다 — 실패는 지표마다 싣는다(FR-009). */
export function fetchQuotes(): Promise<DashboardQuotesResponse> {
  return apiClient.get<DashboardQuotesResponse>("/api/dashboard/quotes");
}

/** 지표의 그래프(200) 또는 받는 중·실패(202 — `status`가 있다). */
export function fetchSeries(id: string, unit: IndicatorUnit): Promise<IndicatorSeriesResponse | IndicatorCollecting> {
  return apiClient.get<IndicatorSeriesResponse | IndicatorCollecting>(
    `/api/dashboard/indicators/${encodeURIComponent(id)}/series?unit=${unit}`);
}

/** 다시 시도 — 워커를 곧바로 깨운다(환율은 외환 수집 경로). */
export function requestCollect(id: string): Promise<{ status: string }> {
  return apiClient.post<{ status: string }>(`/api/dashboard/indicators/${encodeURIComponent(id)}/collect`, {});
}

/** 뉴스 칸 하나. 출처가 실패해도 200이다 — 칸마다 따로 실패한다(FR-024). */
export function fetchNews(source: NewsSourceKey): Promise<NewsListResponse> {
  return apiClient.get<NewsListResponse>(`/api/dashboard/news/${source}`);
}
