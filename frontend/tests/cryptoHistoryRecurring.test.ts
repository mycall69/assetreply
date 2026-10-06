/**
 * 가상자산 이력의 적립식 항목 (011 T036) — FR-033, SC-006, data-model 3.
 *
 * - 적립식 항목은 선택 칸 `mode: "recurring"`·`frequency`를 담는다. 식별자는 일시금 식별자 뒤에 `|recurring:{주기}`
 * - 같은 조건의 일시금과 적립식은 **따로** 항목이다
 * - 일시금 항목의 식별자·모양은 011 전과 같다(`cryptoHistory.test.ts` 그대로)
 * - 011 전에 남은 항목(선택 칸 없음)은 그대로 읽힌다
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  CRYPTO_HISTORY_KEY,
  cryptoConditionId,
  loadCryptoHistory,
  saveCryptoHistory,
} from "@/lib/cryptoHistory";
import { BTC } from "./support/coinSearchFixtures";

const LUMP = { coin: BTC, start: "2024-01-15", principal: "10000", principalCurrency: "KRW" as const };

beforeEach(() => localStorage.clear());

describe("가상자산 적립식 이력", () => {
  it("식별자는 일시금 식별자 뒤에 방식·주기를 붙인다", () => {
    expect(cryptoConditionId(LUMP)).toBe("17|2024-01-15|10000|KRW");
    expect(cryptoConditionId({ ...LUMP, mode: "recurring", frequency: "daily" }))
      .toBe("17|2024-01-15|10000|KRW|recurring:daily");
  });

  it("같은 조건의 일시금과 적립식은 따로 남고, 일시금 항목에는 선택 칸이 없다", () => {
    saveCryptoHistory(LUMP);
    saveCryptoHistory({ ...LUMP, mode: "recurring", frequency: "daily" });
    const entries = loadCryptoHistory();
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ mode: "recurring", frequency: "daily", principal: "10000" });
    expect(Object.keys(entries[1]).sort()).toEqual(["coin", "id", "principal", "principalCurrency", "savedAt", "start"]);
  });

  it("011 전에 남은 항목은 그대로 읽힌다", () => {
    const old = { id: "17|2020-01-15|10000|USD", coin: { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인",
      slug: "bitcoin", currency: "USD" }, start: "2020-01-15", principal: "10000", principalCurrency: "USD",
      savedAt: "2026-10-01T00:00:00Z" };
    localStorage.setItem(CRYPTO_HISTORY_KEY, JSON.stringify([old]));
    expect(loadCryptoHistory()).toEqual([old]);
  });
});
