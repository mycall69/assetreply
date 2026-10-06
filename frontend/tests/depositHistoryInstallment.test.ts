/**
 * 예금 이력의 적금 항목 (011 T045) — FR-033, SC-006, data-model 3.
 *
 * - 적금 항목은 선택 칸 `product: "installment"`를 담는다. 식별자는 정기예금 식별자 뒤에 `|installment`
 * - 같은 조건의 정기예금과 적금은 **따로** 항목이다 — 하나로 뭉치면 다른 상품의 결과가 그 항목의 결과처럼 보인다
 * - 정기예금 항목의 식별자·모양은 011 전과 같다(`depositHistory.test.ts` 그대로)
 * - 011 전에 남은 항목(선택 칸 없음)은 그대로 읽힌다
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  DEPOSIT_HISTORY_KEY,
  depositConditionId,
  loadDepositHistory,
  saveDepositHistory,
} from "@/lib/depositHistory";

const DEPOSIT = { institution: "commercial_bank" as const, start: "2015-01-15", principal: "1000000" };

beforeEach(() => localStorage.clear());

describe("예금 적금 이력", () => {
  it("식별자는 정기예금 식별자 뒤에 상품을 붙인다", () => {
    expect(depositConditionId(DEPOSIT)).toBe("commercial_bank|2015-01-15|1000000");
    expect(depositConditionId({ ...DEPOSIT, product: "installment" })).toBe("commercial_bank|2015-01-15|1000000|installment");
  });

  it("같은 조건의 정기예금과 적금은 따로 남고, 정기예금 항목에는 선택 칸이 없다", () => {
    saveDepositHistory(DEPOSIT);
    saveDepositHistory({ ...DEPOSIT, product: "installment" });
    const entries = loadDepositHistory();
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ product: "installment", principal: "1000000" });
    expect(Object.keys(entries[1]).sort()).toEqual(["id", "institution", "principal", "savedAt", "start"]);
  });

  it("011 전에 남은 항목은 그대로 읽힌다", () => {
    const old = { id: "saemaul|2020-01-15|10000000", institution: "saemaul", start: "2020-01-15", principal: "10000000",
      savedAt: "2026-10-01T00:00:00Z" };
    localStorage.setItem(DEPOSIT_HISTORY_KEY, JSON.stringify([old]));
    expect(loadDepositHistory()).toEqual([old]);
  });
});
