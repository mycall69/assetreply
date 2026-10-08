/**
 * 비교 경로 요청 (013 T034·T050·T074) — contracts/rest-api.md 1, research R13-2.
 *
 * 비교 경로는 메뉴 경로의 짝이다(`/api/comparison/<자산군>/<메뉴 경로>`). 질의는 **메뉴 스토어가 이미 내보내는 질의 함수**로 만든다 —
 * 같은 함수가 같은 공통 조건으로 대상마다 질의를 만들어, 대상마다 조건이 조금이라도 달라지는 일이 없다(SC-002).
 */
import { toQuery as cryptoQuery } from "@/stores/cryptoStore";
import { toQuery as depositQuery } from "@/stores/depositStore";
import { simulationQuery as realEstateQuery } from "@/stores/realEstateStore";
import { toQuery as stockQuery } from "@/stores/stockStore";
import { apiClient } from "./apiClient";
import type { CompareCondition } from "./compareCondition";
import type {
  CompareCollecting,
  CompareTarget,
  ComparisonResponse,
  CryptoTarget,
  DepositTarget,
  RealEstateTarget,
  StockTarget,
} from "./types";

/** 대상 하나의 비교 경로와 질의. 그 자산군·방식의 경로가 아직 없으면 오류다. */
export function comparisonPath(condition: CompareCondition, target: CompareTarget): string {
  const amount = condition.amount ?? "";
  const { start, principalCurrency } = condition;
  switch (`${condition.asset}:${condition.method}`) {
    case "stock:lump_sum":
      return `/api/comparison/stocks/simulation?${stockQuery({
        stock: target as StockTarget, start, principal: amount, principalCurrency, reinvest: condition.reinvest ?? true })}`;
    case "crypto:lump_sum":
      return `/api/comparison/crypto/simulation?${cryptoQuery({
        coin: { ...(target as CryptoTarget), slug: null }, start, principal: amount, principalCurrency })}`;
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

/** 대상 하나를 계산한다 — 200(결과) 또는 202(수집 본문). 거절은 `ApiError`로 올린다. */
export function fetchComparison(path: string): Promise<ComparisonResponse | CompareCollecting> {
  return apiClient.get<ComparisonResponse | CompareCollecting>(path);
}

export function isCollecting(body: ComparisonResponse | CompareCollecting): body is CompareCollecting {
  return "status" in body && body.status === "collecting";
}
