/**
 * 비교 경로 요청 (013 T034·T050·T074·T100) — contracts/rest-api.md 1~4, research R13-2·R13-19.
 *
 * 비교 경로는 메뉴 경로의 짝이다(`/api/comparison/<자산군>/<메뉴 경로>`). 질의는 **메뉴 스토어가 이미 내보내는 질의 함수**로 만든다 —
 * 같은 함수가 같은 공통 조건으로 대상마다 질의를 만들어, 대상마다 조건이 조금이라도 달라지는 일이 없다(SC-002).
 */
import { toQuery as cryptoQuery, toRecurringQuery as cryptoRecurringQuery } from "@/stores/cryptoStore";
import { toQuery as depositQuery, toInstallmentQuery } from "@/stores/depositStore";
import { simulationQuery as realEstateQuery } from "@/stores/realEstateStore";
import { toQuery as stockQuery, toRecurringQuery as stockRecurringQuery } from "@/stores/stockStore";
import { apiClient, request } from "./apiClient";
import type { CompareCondition } from "./compareCondition";
import type {
  CompareCollecting,
  CompareTarget,
  ComparisonResponse,
  CryptoTarget,
  DepositTarget,
  RealEstateTarget,
  SavedComparisonCreated,
  SavedComparisonList,
  StockTarget,
} from "./types";

/** 대상 하나의 비교 경로와 질의. 그 자산군·방식의 경로가 아직 없으면 오류다. */
export function comparisonPath(condition: CompareCondition, target: CompareTarget): string {
  const amount = condition.amount ?? "";
  const { start, principalCurrency } = condition;
  const plan = { mode: "recurring" as const, frequency: condition.frequency ?? "monthly" };
  switch (`${condition.asset}:${condition.method}`) {
    case "stock:lump_sum":
      return `/api/comparison/stocks/simulation?${stockQuery({
        stock: target as StockTarget, start, principal: amount, principalCurrency, reinvest: condition.reinvest ?? true })}`;
    case "crypto:lump_sum":
      return `/api/comparison/crypto/simulation?${cryptoQuery({
        coin: { ...(target as CryptoTarget), slug: null }, start, principal: amount, principalCurrency })}`;
    case "stock:recurring":
      return `/api/comparison/stocks/recurring-simulation?${stockRecurringQuery({
        stock: target as StockTarget, start, principal: amount, principalCurrency, reinvest: condition.reinvest ?? true },
      plan)}`;
    case "crypto:recurring":
      return `/api/comparison/crypto/recurring-simulation?${cryptoRecurringQuery({
        coin: { ...(target as CryptoTarget), slug: null }, start, principal: amount, principalCurrency }, plan)}`;
    case "deposit:installment":
      return `/api/comparison/deposit/installment-simulation?${toInstallmentQuery({
        institution: (target as DepositTarget).institution, start, principal: amount })}`;
    case "deposit:deposit":
      return `/api/comparison/deposit/simulation?${depositQuery({
        institution: (target as DepositTarget).institution, start, principal: amount })}`;
    case "realestate:hold": {
      const { complexId, area } = target as RealEstateTarget;
      return `/api/comparison/realestate/simulation?${realEstateQuery(complexId, area, { buyDate: start, buyPrice: "" })}`;
    }
    default:
      throw new Error(`비교 경로가 없는 방식입니다: ${condition.asset}/${condition.method}`);
  }
}

/**
 * 그 대상의 **메뉴 표 경로**(013 반복 2026-10-09b — 투자 시뮬레이션 모달, research R13-19). 비교 경로에서 `/comparison`을 뺀 것이다 — 같은 질의
 * 함수가 만든 같은 질의라, 메뉴에서 같은 조건으로 실행한 응답과 같다.
 */
export function menuPath(condition: CompareCondition, target: CompareTarget): string {
  return comparisonPath(condition, target).replace("/api/comparison/", "/api/");
}

/** 메뉴의 성과 추이 경로 — 표 경로에 `/series`를 붙인다. 메뉴처럼 `maxPoints`를 붙이지 않는다(서버 기본 다운샘플링). */
export function menuSeriesPath(condition: CompareCondition, target: CompareTarget): string {
  const path = menuPath(condition, target);
  const at = path.indexOf("?");
  return at === -1 ? `${path}/series` : `${path.slice(0, at)}/series${path.slice(at)}`;
}

/** 대상 하나를 계산한다 — 200(결과) 또는 202(수집 본문). 거절은 `ApiError`로 올린다. */
export function fetchComparison(path: string): Promise<ComparisonResponse | CompareCollecting> {
  return apiClient.get<ComparisonResponse | CompareCollecting>(path);
}

export function isCollecting(body: ComparisonResponse | CompareCollecting): body is CompareCollecting {
  return "status" in body && body.status === "collecting";
}

/* 저장한 비교 (T074) — 공통 요청 함수(`request`)를 직접 쓴다. 비교 경로를 모의하는 테스트(`apiClient.get` 모의)가 저장 요청까지 가로채지 않는다(012
 * 이력 클라이언트와 같은 까닭). 오류 모양(`ApiError`)은 같다. */

export const fetchSavedComparisons = () => request<SavedComparisonList>("/api/comparison/saved");

/** 늘 새 항목이다(같은 조건·이름이어도). 조건은 결과를 낸 정규 조건이다 — 결과를 싣지 않는다. */
export const postSavedComparison = (name: string, condition: CompareCondition) =>
  request<SavedComparisonCreated>("/api/comparison/saved", { method: "POST", body: JSON.stringify({ name, condition }) });

/** 없는 `id`도 200이다(멱등). */
export const deleteSavedComparison = (id: number) =>
  request<SavedComparisonList>(`/api/comparison/saved/${id}`, { method: "DELETE" });
