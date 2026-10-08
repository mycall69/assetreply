/**
 * 고른 종목의 등록 (013 T015) — FR-003, research R13-9.
 *
 * 검색이 고른 것은 `StockChoice`이고 종목 식별(거래소·심볼·통화)은 등록 응답이 정한다. 비교 화면과 주식 메뉴가 **같은 함수**로
 * 등록한다 — 따로 만들면 한쪽만 본문이 바뀌어 다른 종목이 계산될 수 있다(FR-003 실패 양상).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/apiClient";
import { registerStock } from "@/lib/stockSelection";
import type { StockChoice } from "@/lib/types";
import { SAMSUNG, TOYOTA } from "./support/stockSearchFixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("registerStock", () => {
  it("목록 결과는 목록 번호로 등록하고 응답의 종목을 돌려준다", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW", listedOn: "1975-06-11",
    });
    const choice: StockChoice = { source: "listing", listingId: SAMSUNG.listingId, preview: SAMSUNG };
    await expect(registerStock(choice)).resolves.toEqual({
      market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW", listedOn: "1975-06-11",
    });
    expect(post).toHaveBeenCalledWith("/api/stocks/selection", { source: "listing", listingId: 1021 });
  });

  it("외부 결과는 거래소·심볼·이름·통화로 등록한다", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ ...TOYOTA, listedOn: null });
    await registerStock({ source: "external", result: TOYOTA });
    expect(post).toHaveBeenCalledWith("/api/stocks/selection", {
      source: "external", market: "TSE", symbol: "7203.T", name: "Toyota Motor Corporation", currency: "JPY",
    });
  });

  it("실패는 그대로 올린다", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(new ApiError(404, "unknown_stock", "없는 종목"));
    await expect(registerStock({ source: "listing", listingId: 1, preview: SAMSUNG })).rejects.toBeInstanceOf(ApiError);
  });
});
