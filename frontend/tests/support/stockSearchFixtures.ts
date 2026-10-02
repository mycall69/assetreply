/**
 * 006 검색 테스트 공용 응답 — contracts/rest-api `GET /api/stocks/search`·`/external`.
 *
 * 경로로 응답을 가른다. 두 엔드포인트를 **한 응답으로 흉내 내면** 로컬과 외부가 같은 결과를
 * 받아 두 영역이 섞였는지 검증할 수 없다.
 */
import { vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type {
  ExternalSearchResponse,
  ListingUnitStatus,
  LocalSearchResponse,
  LocalStockResult,
} from "@/lib/types";

export const SAMSUNG: LocalStockResult = {
  listingId: 1021, country: "KR", market: "KRX", symbol: "005930.KS", code: "005930",
  name: "삼성전자", nameEn: null, currency: "KRW", kind: "stock",
  listedOn: "1975-06-11", listingStatus: "listed", match: "exact",
};
export const SAMSUNG_PREF: LocalStockResult = {
  ...SAMSUNG, listingId: 1022, symbol: "005935.KS", code: "005935", name: "삼성전자우",
  listedOn: "1989-09-25", match: "prefix",
};
export const KODEX200: LocalStockResult = {
  ...SAMSUNG, listingId: 2001, symbol: "069500.KS", code: "069500", name: "KODEX 200",
  kind: "etf", listedOn: "2002-10-14", match: "prefix",
};
export const REIT: LocalStockResult = {
  ...SAMSUNG, listingId: 2002, symbol: "0030R0.KS", code: "0030R0", name: "대신밸류리츠",
  kind: "reit", listedOn: "2025-07-10", match: "contains",
};
export const DELISTED: LocalStockResult = {
  ...SAMSUNG, listingId: 3001, symbol: "123450.KQ", code: "123450", name: "삼성옛종목",
  listingStatus: "missing", match: "prefix",
};

export const READY: ListingUnitStatus[] = [
  { unit: "KOSPI", state: "ready", asOf: "2026-10-02T00:05:12Z" },
  { unit: "KOSDAQ", state: "ready", asOf: "2026-10-02T00:05:40Z" },
];

export const local = (
  results: LocalStockResult[],
  over: Partial<LocalSearchResponse> = {},
): LocalSearchResponse => ({
  query: "삼성", results, truncated: false, lists: READY, ...over,
});

export const TOYOTA = {
  market: "TSE" as const, symbol: "7203.T", name: "Toyota Motor Corporation",
  currency: "JPY", kind: "stock" as const,
};

export const external = (
  results: ExternalSearchResponse["results"] = [],
): ExternalSearchResponse => ({ query: "삼성", results });

type Handler = (path: string) => Promise<unknown>;

/** `apiClient.get`을 경로별 처리기로 바꾼다. 처리기가 없는 경로는 실패로 드러낸다. */
export function routeGet(handlers: { local?: Handler; external?: Handler }) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    if (path.startsWith("/api/stocks/search/external")) {
      return handlers.external ? handlers.external(path) : Promise.resolve(external());
    }
    if (path.startsWith("/api/stocks/search")) {
      return handlers.local ? handlers.local(path) : Promise.resolve(local([]));
    }
    return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
  }) as typeof apiClient.get);
}

/** 끝나지 않는 응답 — "기다리지 않는다"를 검증할 때 쓴다. */
export const pending = (): Promise<never> => new Promise<never>(() => {});
