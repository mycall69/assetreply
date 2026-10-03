/**
 * 007 코인 검색 테스트 공용 응답 — contracts/rest-api `GET /api/crypto/search`.
 *
 * 값은 2026-10-03 출처 목록의 실제 값이다(ui-wireframes C2).
 */
import { vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { CoinListStatus, CoinSearchResponse, CoinSearchResult } from "@/lib/types";

export const BTC: CoinSearchResult = {
  coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin",
  currency: "USD", rank: 1, listStatus: "listed", firstAvailableDate: "2010-07-18", match: "prefix",
};
export const BTS: CoinSearchResult = {
  coinId: 1402, symbol: "BTS", name: "BitShares", nameKo: null, slug: "bitshares",
  currency: "USD", rank: 1355, listStatus: "listed", firstAvailableDate: null, match: "contains",
};
export const MAX_TOKEN: CoinSearchResult = {
  coinId: 801, symbol: "MAX", name: "MAX Exchange Token", nameKo: null, slug: "max-exchange-token",
  currency: "USD", rank: 763, listStatus: "listed", firstAvailableDate: null, match: "exact",
};
export const MAXCOIN: CoinSearchResult = {
  ...MAX_TOKEN, coinId: 5410, name: "MaxCoin", slug: "maxcoin", rank: 5359,
  listStatus: "missing",
};

export const AS_OF = "2026-10-03T00:05:12Z";

export const READY: CoinListStatus = {
  state: "ready", asOf: AS_OF, koreanNames: { state: "ready", asOf: AS_OF },
};
export const NEVER: CoinListStatus = {
  state: "never", asOf: null, koreanNames: { state: "never", asOf: null },
};
export const REFRESHING: CoinListStatus = {
  state: "refreshing", asOf: AS_OF, koreanNames: { state: "refreshing", asOf: AS_OF },
};

export const response = (
  results: CoinSearchResult[],
  list: CoinListStatus = READY,
): CoinSearchResponse => ({ query: "btc", results, truncated: false, list });

/** `apiClient.get`을 코인 검색 응답으로 바꾼다. 다른 경로는 실패로 드러낸다. */
export function routeSearch(reply: (path: string) => Promise<unknown>) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    if (path.startsWith("/api/crypto/search")) return reply(path);
    return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
  }) as typeof apiClient.get);
}
