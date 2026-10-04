/**
 * 가상자산 이력 보관 (T043) — 007 FR-045, FR-046, 005 R5-9·R5-10.
 *
 * **조건만 저장한다** — 결과는 일봉·설정·환율의 함수라 바뀐다. **주식 이력과 다른 키**다 — 섞이면 주식 화면에서 코인을 다시
 * 실행하려다 "없는 종목"이 된다. 코인은 id와 이름·심볼을 함께 남긴다 — 심볼은 유일하지 않다(FR-004).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  CRYPTO_HISTORY_KEY,
  loadCryptoHistory,
  removeCryptoHistory,
  saveCryptoHistory,
} from "@/lib/cryptoHistory";
import { HISTORY_KEY, loadHistory, saveHistory } from "@/lib/simulationHistory";
import { BTC, MAX_TOKEN } from "./support/coinSearchFixtures";

const condition = { coin: BTC, start: "2020-01-15", principal: "10000",
  principalCurrency: "USD" as const };

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("가상자산 이력", () => {
  it("조건과 코인 식별만 남기고 결과는 남기지 않는다", () => {
    expect(saveCryptoHistory(condition)).toEqual({ ok: true });
    const [entry] = loadCryptoHistory();
    expect(entry.coin).toEqual({ coinId: BTC.coinId, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인",
      slug: "bitcoin", currency: "USD" });
    expect([entry.start, entry.principal, entry.principalCurrency]).toEqual(["2020-01-15", "10000", "USD"]);
    expect(Object.keys(entry).sort()).toEqual(
      ["coin", "id", "principal", "principalCurrency", "savedAt", "start"]);
  });

  it("주식 이력과 키가 달라 서로 보이지 않는다", () => {
    expect(CRYPTO_HISTORY_KEY).not.toBe(HISTORY_KEY);
    saveCryptoHistory(condition);
    saveHistory({ stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
      start: "2020-01-01", principal: "1000000", principalCurrency: "KRW", reinvest: true });
    expect(loadCryptoHistory()).toHaveLength(1);
    expect(loadHistory()).toHaveLength(1);
    expect(loadHistory()[0].stock.name).toBe("삼성전자");
  });

  it("같은 조건은 한 줄이고 맨 앞으로 오른다", () => {
    saveCryptoHistory(condition);
    saveCryptoHistory({ ...condition, coin: MAX_TOKEN });
    saveCryptoHistory(condition);
    const entries = loadCryptoHistory();
    expect(entries.map((e) => e.coin.coinId)).toEqual([BTC.coinId, MAX_TOKEN.coinId]);
  });

  it("원금이 다르면 다른 줄이다", () => {
    saveCryptoHistory(condition);
    saveCryptoHistory({ ...condition, principal: "20000" });
    expect(loadCryptoHistory()).toHaveLength(2);
  });

  it("지운다", () => {
    saveCryptoHistory(condition);
    const [entry] = loadCryptoHistory();
    expect(removeCryptoHistory(entry.id)).toEqual({ ok: true });
    expect(loadCryptoHistory()).toEqual([]);
  });

  it("저장소가 깨져 있어도 던지지 않는다", () => {
    localStorage.setItem(CRYPTO_HISTORY_KEY, "{깨짐");
    expect(loadCryptoHistory()).toEqual([]);
  });

  it("저장 공간이 차면 조용히 실패하지 않는다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    const result = saveCryptoHistory(condition);
    expect(result.ok).toBe(false);
  });
});
