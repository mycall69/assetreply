/**
 * 대시보드 요청 (014 T036·T058·T078·T119) — contracts/rest-api.md A1~A3·A5·A7·A8.
 *
 * 값은 문자열로 받아 문자열로 둔다(원칙 VI) — 공통 클라이언트(`apiClient`)를 쓴다.
 */
import { apiClient } from "@/lib/apiClient";
import type {
  DashboardQuotesResponse,
  IndicatorChartSeries,
  IndicatorCollecting,
  IndicatorCommentaryResponse,
  IndicatorRange,
  IndicatorTablePeriod,
  IndicatorTableResponse,
  NewsListResponse,
  NewsSourceKey,
  PolicyRateDetail,
  PolicyRatesResponse,
  RateCommentaryResponse,
} from "@/lib/types";

/** 지표 15개의 현재 시세. 출처가 실패해도 200이다 — 실패는 지표마다 싣는다(FR-009). */
export function fetchQuotes(): Promise<DashboardQuotesResponse> {
  return apiClient.get<DashboardQuotesResponse>("/api/dashboard/quotes");
}

const indicatorPath = (id: string) => `/api/dashboard/indicators/${encodeURIComponent(id)}`;

/**
 * 지표의 그래프 — 일봉 기간(200), 장중(200 — `intraday`가 있다), 받는 중·실패(202 — `status`가 있고 `intraday`가 없다).
 * 반복 2026-10-10b — 질의가 `unit`에서 보는 기간 `range`로 바뀌었다.
 */
export function fetchSeries(id: string, range: IndicatorRange): Promise<IndicatorChartSeries | IndicatorCollecting> {
  return apiClient.get<IndicatorChartSeries | IndicatorCollecting>(`${indicatorPath(id)}/series?range=${range}`);
}

/** 일자별 표 한 쪽(200) 또는 받는 중·실패(202 — 그래프와 같은 본문). `before`가 있으면 그 날짜 앞의 쪽이다. */
export function fetchTable(
  id: string, period: IndicatorTablePeriod, before?: string,
): Promise<IndicatorTableResponse | IndicatorCollecting> {
  const query = before ? `period=${period}&before=${before}` : `period=${period}`;
  return apiClient.get<IndicatorTableResponse | IndicatorCollecting>(`${indicatorPath(id)}/table?${query}`);
}

/** 변화 까닭 — 출처가 실패해도 200이다(`status: "failed"`). */
export function fetchCommentary(id: string): Promise<IndicatorCommentaryResponse> {
  return apiClient.get<IndicatorCommentaryResponse>(`${indicatorPath(id)}/commentary`);
}

/** 다시 시도 — 워커를 곧바로 깨운다(환율은 외환 수집 경로). */
export function requestCollect(id: string): Promise<{ status: string }> {
  return apiClient.post<{ status: string }>(`${indicatorPath(id)}/collect`, {});
}

/** 뉴스 칸 하나. 출처가 실패해도 200이다 — 칸마다 따로 실패한다(FR-024). */
export function fetchNews(source: NewsSourceKey): Promise<NewsListResponse> {
  return apiClient.get<NewsListResponse>(`/api/dashboard/news/${source}`);
}

/* ── 반복 2026-10-11d — 기준금리(contracts A14~A17) ── */

/** 기준금리 칸 — DB만 읽는다(출처를 부르지 않는다). 은행마다 따로 실패한다. */
export function fetchRates(): Promise<PolicyRatesResponse> {
  return apiClient.get<PolicyRatesResponse>("/api/dashboard/rates");
}

const ratePath = (bank: string) => `/api/dashboard/rates/${encodeURIComponent(bank)}`;

/** 금리 모달 — 결정 전부(최신부터). */
export function fetchRateDetail(bank: string): Promise<PolicyRateDetail> {
  return apiClient.get<PolicyRateDetail>(ratePath(bank));
}

/** 금리 변화 까닭 — 출처가 실패해도 200이다(`status: "failed"`). */
export function fetchRateCommentary(bank: string): Promise<RateCommentaryResponse> {
  return apiClient.get<RateCommentaryResponse>(`${ratePath(bank)}/commentary`);
}

/** 다시 시도 — 수집 워커를 곧바로 깨운다(202). */
export function requestRateCollect(): Promise<{ accepted: boolean }> {
  return apiClient.post<{ accepted: boolean }>("/api/dashboard/rates/collect", {});
}
