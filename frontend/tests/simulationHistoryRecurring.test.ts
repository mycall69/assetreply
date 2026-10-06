/**
 * 주식 이력의 적립식 항목 (011 T021) — FR-033, SC-006, data-model 3, research R11-11.
 *
 * - 적립식 항목은 선택 칸 `mode: "recurring"`·`frequency`를 담는다. 식별자는 일시금 식별자 뒤에 `|recurring:{주기}`
 * - 같은 조건의 일시금과 적립식은 **따로** 항목이다 — 하나로 뭉치면 다른 방식의 결과가 그 항목의 결과처럼 보인다
 * - 일시금 항목의 식별자·모양은 011 전과 같다(`simulationHistory.test.ts` 그대로)
 * - 011 전에 남은 항목(선택 칸 없음)은 그대로 읽힌다
 */
import { beforeEach, describe, expect, it } from "vitest";
import { conditionId, HISTORY_KEY, loadHistory, saveHistory } from "@/lib/simulationHistory";

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const LUMP = { stock: STOCK, start: "2024-01-15", principal: "500000", principalCurrency: "KRW" as const, reinvest: true };

beforeEach(() => localStorage.clear());

describe("적립식 이력", () => {
  it("식별자는 일시금 식별자 뒤에 방식·주기를 붙인다", () => {
    expect(conditionId(LUMP)).toBe("KRX|005930.KS|2024-01-15|500000|KRW|R");
    expect(conditionId({ ...LUMP, mode: "recurring", frequency: "monthly" }))
      .toBe("KRX|005930.KS|2024-01-15|500000|KRW|R|recurring:monthly");
    expect(conditionId({ ...LUMP, mode: "recurring", frequency: "weekly" }))
      .not.toBe(conditionId({ ...LUMP, mode: "recurring", frequency: "monthly" }));
  });

  it("같은 조건의 일시금과 적립식은 따로 남는다", () => {
    saveHistory(LUMP);
    saveHistory({ ...LUMP, mode: "recurring", frequency: "monthly" });
    const entries = loadHistory();
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ mode: "recurring", frequency: "monthly", principal: "500000" });
    expect(entries[1]).not.toHaveProperty("mode");
    expect(entries[1]).not.toHaveProperty("frequency");
  });

  it("011 전에 남은 항목은 그대로 읽힌다", () => {
    const old = { id: "KRX|005930.KS|2020-01-02|10000000|KRW|R", stock: STOCK, start: "2020-01-02",
      principal: "10000000", principalCurrency: "KRW", reinvest: true, savedAt: "2026-10-01T00:00:00Z" };
    localStorage.setItem(HISTORY_KEY, JSON.stringify([old]));
    expect(loadHistory()).toEqual([old]);
  });
});
