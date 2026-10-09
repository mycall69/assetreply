/**
 * 대시보드 요청 (014 T036) — contracts/rest-api.md A1.
 *
 * 값은 문자열로 받아 문자열로 둔다(원칙 VI) — 공통 클라이언트(`apiClient`)를 쓴다.
 */
import { apiClient } from "@/lib/apiClient";
import type { DashboardQuotesResponse } from "@/lib/types";

/** 지표 15개의 현재 시세. 출처가 실패해도 200이다 — 실패는 지표마다 싣는다(FR-009). */
export function fetchQuotes(): Promise<DashboardQuotesResponse> {
  return apiClient.get<DashboardQuotesResponse>("/api/dashboard/quotes");
}
