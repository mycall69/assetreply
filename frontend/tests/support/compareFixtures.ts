/**
 * 013 투자 비교 테스트 공용 응답 — contracts/rest-api.md 1(비교 경로), data-model 3(`comparison` 블록).
 *
 * 값은 2026-10-07 XLK 보고(012 US6)의 보드 값을 본뜬다 — 현재 잔고 ₩539,297,203, 매도 후 투자 수익 ₩409,114,677.
 */
import { vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type {
  CompareCollecting,
  ComparisonBlock,
  ComparisonResponse,
  CryptoTarget,
  RealEstateTarget,
  SimulationSeriesResponse,
  StockTarget,
} from "@/lib/types";

export const SAMSUNG_T: StockTarget = { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
export const HYNIX_T: StockTarget = { market: "KRX", symbol: "000660.KS", name: "SK하이닉스", currency: "KRW" };
export const XLK_T: StockTarget = { market: "NYSE", symbol: "XLK", name: "Technology Select Sector SPDR Fund", currency: "USD" };
export const AAPL_T: StockTarget = { market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD" };
export const BTC_T: CryptoTarget = { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" };
export const ETH_T: CryptoTarget = { coinId: 18, symbol: "ETH", name: "Ethereum", nameKo: "이더리움", currency: "USD" };
export const HELIO_T: RealEstateTarget = {
  complexId: 12, name: "헬리오시티아파트", umdName: "가락동", area: "30k", areaLabel: "30평대(국평)",
};

export const series = (points: [string, string][], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: points[0]?.[0] ?? "2020-01-02", to: points[points.length - 1]?.[0] ?? "2020-01-02",
  principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false, algorithm: "lttb",
  sourcePointCount: points.length,
  points: points.map(([date, returnRate]) => ({ date, balance: "0", returnRate })),
  gaps: [], ...over,
});

export function block(over: Partial<ComparisonBlock> = {}): ComparisonBlock {
  return {
    asOf: "2026-10-06", isFinal: true,
    principal: { amount: "20000000", currency: "KRW", krw: "20000000" },
    currentValue: "539297203", mainBasis: "after_sale", profit: "409114677", returnRate: "20.455734",
    holding: { profit: "519297203", returnRate: "25.964860" },
    costs: {
      total: "113030970",
      reflected: { total: "2848444", items: [
        { kind: "buy_fee", amount: "5427", inPrincipal: false },
        { kind: "dividend_tax", amount: "2843017", inPrincipal: false }] },
      sale: { total: "110182526", blank: null, items: [
        { kind: "sale_fee", amount: "80884", inPrincipal: false },
        { kind: "capital_gains_tax", amount: "110101642", inPrincipal: false }] },
    },
    lineEnd: { date: "2026-10-06", holdingReturnRate: "25.964860", afterSaleReturnRate: "20.455734" },
    provisional: [], fx: null,
    ...over,
  };
}

export function ok(target: unknown, over: Partial<ComparisonBlock> = {},
  points: [string, string][] = [["2020-01-02", "0"], ["2026-10-01", "25.5"]]): ComparisonResponse {
  return {
    basisCurrency: "KRW", target, condition: {}, exchange: null, summary: {},
    series: series(points), comparison: block(over),
  } as ComparisonResponse;
}

export const collectingStock = (jobId = 41): CompareCollecting => ({
  status: "collecting", market: "KRX", symbol: "000660.KS", jobId, missingFrom: "2001-01-01",
  missingThrough: "2020-01-31", progressUrl: `/api/stocks/progress?jobId=${jobId}`,
});

export const apiError = (status: number, code: string, body: Record<string, unknown> = {}) =>
  new ApiError(status, code, `${code} 메시지`, { status: code, message: `${code} 메시지`, ...body });

/** 경로 → 응답(`Error`면 거절, `Promise`면 그대로). 처리기가 없는 경로는 실패로 드러낸다. */
export function routeCompare(answer: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    const result = answer(path);
    if (result === undefined) return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
    if (result instanceof Promise) return result;
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  }) as typeof apiClient.get);
}
