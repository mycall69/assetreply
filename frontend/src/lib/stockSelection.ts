/**
 * 고른 종목의 등록 (013 T032 — 006 `stockStore.selectStock`에서 꺼냈다) — 006 FR-030, 013 FR-003.
 *
 * 검색이 고른 것은 `StockChoice`(목록 행 또는 일본 외부 결과)이고 **종목 식별은 등록 응답이 정한다.** 주식 메뉴와 비교 화면이 이 함수
 * 하나로 등록한다 — 따로 만들면 한쪽만 본문이 바뀌어 다른 종목이 계산될 수 있다.
 */
import { apiClient } from "./apiClient";
import type { SelectionResponse, StockChoice } from "./types";

export function selectionBody(choice: StockChoice): Record<string, unknown> {
  if (choice.source === "listing") {
    return { source: "listing", listingId: choice.listingId };
  }
  const { market, symbol, name, currency } = choice.result;
  return { source: "external", market, symbol, name, currency };
}

/** 등록하고 응답(거래소·심볼·이름·통화·상장일)을 돌려준다. 실패는 그대로 올린다. */
export function registerStock(choice: StockChoice): Promise<SelectionResponse> {
  return apiClient.post<SelectionResponse>("/api/stocks/selection", selectionBody(choice));
}
