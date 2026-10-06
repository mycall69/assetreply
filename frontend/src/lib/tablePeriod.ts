/**
 * 일자별 표의 단위 (012) — 주식·가상자산 스토어와 화면이 함께 쓴다. research R12-7·R12-8, contracts/ui-wireframes.md F2.
 */

import type { PeriodUnit } from "@/lib/types";

/**
 * 표 요청에 붙이는 단위. **일이면 붙이지 않는다** — 서버의 기본이 일이고, 기본 단위의 요청 문자열이 지금과 같다(기존 정확 비교 테스트 보호). 시계열
 * 요청에는 붙이지 않는다 — 차트는 단위와 무관하다(FR-007).
 */
export function periodQuery(period: PeriodUnit): string {
  return period === "daily" ? "" : `&period=${period}`;
}

/** 단위 탭의 제목 — 그 표에서의 대표일 규칙(서버 `simulation/period_table`과 같은 말). */
export const STOCK_PERIOD_TITLES: Record<PeriodUnit, string> = {
  daily: "시세가 있는 날마다",
  weekly: "그 주의 금요일 (없으면 그 앞의 마지막 거래일)",
  monthly: "그 달의 말일 (없으면 그 달의 마지막 거래일)",
};

export const CRYPTO_PERIOD_TITLES: Record<PeriodUnit, string> = {
  daily: "일봉마다",
  weekly: "그 주의 금요일 일봉 (없으면 그 앞의 마지막 일봉, 월~금에 없으면 그 주의 마지막 일봉)",
  monthly: "그 달의 말일 일봉 (없으면 그 달의 마지막 일봉)",
};
