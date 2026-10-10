/**
 * 고른 대상의 상장일 경로 (014 반복 2026-10-10g — FR-034, contracts A11, research R14-27).
 *
 * 주식·가상자산 메뉴의 고른 줄이 묻는다. 경로는 대상을 담은 글자 하나다 — 고른 줄의 훅이 이 글자로 "같은 대상인가"를 가른다.
 *
 * 공통 요청 함수(`request`)를 직접 쓴다 — `apiClient.get`을 거치지 않는다(012 이력 클라이언트와 같은 까닭). 상장일은 표시 전용이라
 * 시뮬레이션과 실패 영역이 다르고, 시뮬레이션 응답을 모의하는 테스트가 이 요청까지 가로채면 무관한 단언이 흔들린다.
 */
import { request } from "@/lib/apiClient";
import type { CoinRef, ListingDate, StockSearchResult } from "@/lib/types";

export interface ListingLookup {
  listing: ListingDate | null;
}

export const stockListingPath = (stock: StockSearchResult): string =>
  `/api/stocks/listing-date?market=${encodeURIComponent(stock.market)}&symbol=${encodeURIComponent(stock.symbol)}`;

export const coinListingPath = (coin: Pick<CoinRef, "coinId">): string =>
  `/api/crypto/listing-date?coinId=${coin.coinId}`;

/** 상장일을 묻는다. 모르면 `null`이다. 실패는 그대로 올린다(`ApiError`). */
export async function fetchListing(path: string): Promise<ListingDate | null> {
  const body = await request<ListingLookup>(path);
  return body.listing ?? null;
}
