/**
 * 예금 이력 보관 (T031) — 008 FR-037, data-model "이력".
 *
 * **조건만 저장한다**(투자처·시작일·원금) — 결과는 금리·세율의 함수라 바뀐다(005 R5-9). **주식·가상자산 이력과 다른 키**다 — 섞이면
 * 한쪽 화면에서 다른 자산군의 항목을 다시 실행하려다 "알 수 없는 투자처"가 된다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CRYPTO_HISTORY_KEY, loadCryptoHistory } from "@/lib/cryptoHistory";
import {
  DEPOSIT_HISTORY_KEY,
  loadDepositHistory,
  removeDepositHistory,
  saveDepositHistory,
} from "@/lib/depositHistory";
import { HISTORY_KEY, loadHistory } from "@/lib/simulationHistory";

const condition = { institution: "commercial_bank" as const, start: "2020-01-15", principal: "10000000" };

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("예금 이력", () => {
  it("키는 주식·가상자산과 다르다", () => {
    expect(DEPOSIT_HISTORY_KEY).toBe("assetreplay.depositHistory.v1");
    expect(DEPOSIT_HISTORY_KEY).not.toBe(HISTORY_KEY);
    expect(DEPOSIT_HISTORY_KEY).not.toBe(CRYPTO_HISTORY_KEY);
    saveDepositHistory(condition);
    expect(loadHistory()).toEqual([]);
    expect(loadCryptoHistory()).toEqual([]);
  });

  it("조건만 남기고 결과 수치는 남기지 않는다", () => {
    expect(saveDepositHistory(condition)).toEqual({ ok: true });
    const [entry] = loadDepositHistory();
    expect([entry.institution, entry.start, entry.principal]).toEqual(["commercial_bank", "2020-01-15", "10000000"]);
    expect(Object.keys(entry).sort()).toEqual(["id", "institution", "principal", "savedAt", "start"]);
  });

  it("같은 조건은 한 줄이고 맨 앞으로 오른다", () => {
    saveDepositHistory(condition);
    saveDepositHistory({ ...condition, institution: "savings_bank" });
    saveDepositHistory(condition);
    expect(loadDepositHistory().map((e) => e.institution)).toEqual(["commercial_bank", "savings_bank"]);
  });

  it("지운다", () => {
    saveDepositHistory(condition);
    const [entry] = loadDepositHistory();
    expect(removeDepositHistory(entry.id)).toEqual({ ok: true });
    expect(loadDepositHistory()).toEqual([]);
  });

  it("저장소가 깨져 있어도 던지지 않는다", () => {
    localStorage.setItem(DEPOSIT_HISTORY_KEY, "{not json");
    expect(loadDepositHistory()).toEqual([]);
  });

  it("저장하지 못하면 조용히 넘어가지 않는다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    const result = saveDepositHistory(condition);
    expect(result.ok).toBe(false);
  });
});
