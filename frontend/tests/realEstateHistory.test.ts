/**
 * 부동산 이력 보관 (T049) — 009 FR-032, data-model "이력", ui-wireframes E7.
 *
 * **조건만 저장한다** — 단지(id·이름), 그 단지의 법정동, 평형 구분(키·이름), 매입일, 직접 넣은 매입가(없으면 `null` — 그 달 시세).
 * 결과 수치는 남기지 않는다 — 결과는 거래·세법·보유세 기준 비율의 함수라 바뀐다(005 R5-9). **다른 자산군 이력과 다른 키**다 — 섞이면
 * 한쪽 화면에서 다른 자산군의 항목을 다시 실행하려다 "알 수 없는 단지"가 된다.
 *
 * ## 이 테스트가 전제하는 모듈 (T050이 따른다)
 *
 * `@/lib/realEstateHistory`
 * - `REALESTATE_HISTORY_KEY = "assetreplay:realestate-history:v1"`(plan의 키)
 * - `RealEstateHistoryCondition { complexId: number; complexName: string; umd: string; area: RealEstateAreaKey; areaLabel: string;
 *   buyDate: string; buyPrice: string | null }` — `umd`는 그 단지의 법정동 코드다. 시뮬레이션 응답에는 동 이름만 있어, 다시 실행할 때
 *   지역 풀다운(시·도·시·군·구·동)을 맞추려면 실행할 때 고른 동 코드를 함께 남긴다(시·도는 앞 2자리, 시·군·구는 앞 5자리로 정해진다)
 * - `loadRealEstateHistory(): RealEstateHistoryEntry[]`, `saveRealEstateHistory(condition): SaveResult`,
 *   `removeRealEstateHistory(id): SaveResult` — `SaveResult`는 `@/lib/depositHistory`와 같은 `{ ok: true } | { ok: false; reason }`
 *
 * `@/lib/types`: `RealEstateHistoryEntry` = 조건 + `id`(같은 조건이면 같은 값) + `savedAt`
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CRYPTO_HISTORY_KEY, loadCryptoHistory } from "@/lib/cryptoHistory";
import { DEPOSIT_HISTORY_KEY, loadDepositHistory } from "@/lib/depositHistory";
import {
  REALESTATE_HISTORY_KEY,
  type RealEstateHistoryCondition,
  loadRealEstateHistory,
  removeRealEstateHistory,
  saveRealEstateHistory,
} from "@/lib/realEstateHistory";
import { HISTORY_KEY, loadHistory } from "@/lib/simulationHistory";

const condition: RealEstateHistoryCondition = {
  complexId: 12, complexName: "헬리오시티", umd: "1171010700", area: "30k", areaLabel: "30평대(국평)",
  buyDate: "2021-03-15", buyPrice: null,
};

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("부동산 이력", () => {
  it("키는 다른 자산군과 다르다 — 섞이지 않는다", () => {
    expect(REALESTATE_HISTORY_KEY).toBe("assetreplay:realestate-history:v1");
    for (const other of [HISTORY_KEY, CRYPTO_HISTORY_KEY, DEPOSIT_HISTORY_KEY]) expect(REALESTATE_HISTORY_KEY).not.toBe(other);
    saveRealEstateHistory(condition);
    expect(loadHistory()).toEqual([]);
    expect(loadCryptoHistory()).toEqual([]);
    expect(loadDepositHistory()).toEqual([]);
  });

  it("조건만 남기고 결과 수치는 남기지 않는다", () => {
    expect(saveRealEstateHistory(condition)).toEqual({ ok: true });
    const [entry] = loadRealEstateHistory();
    expect(Object.keys(entry).sort()).toEqual([
      "area", "areaLabel", "buyDate", "buyPrice", "complexId", "complexName", "id", "savedAt", "umd"]);
    expect([entry.complexId, entry.complexName, entry.umd, entry.area, entry.areaLabel, entry.buyDate, entry.buyPrice])
      .toEqual([12, "헬리오시티", "1171010700", "30k", "30평대(국평)", "2021-03-15", null]);
  });

  it("그 달 시세로 샀으면 매입가가 null, 직접 넣었으면 쉼표 없는 문자열이다", () => {
    saveRealEstateHistory(condition);
    saveRealEstateHistory({ ...condition, buyPrice: "1500000000" });
    expect(loadRealEstateHistory().map((e) => e.buyPrice)).toEqual(["1500000000", null]);
  });

  it("같은 조건은 한 줄이고 맨 앞으로 오른다", () => {
    saveRealEstateHistory(condition);
    saveRealEstateHistory({ ...condition, area: "20", areaLabel: "20평대" });
    saveRealEstateHistory(condition);
    expect(loadRealEstateHistory().map((e) => e.area)).toEqual(["30k", "20"]);
  });

  it("매입가나 매입일이 다르면 다른 조건이다", () => {
    saveRealEstateHistory(condition);
    saveRealEstateHistory({ ...condition, buyPrice: "1500000000" });
    saveRealEstateHistory({ ...condition, buyDate: "2022-01-03" });
    expect(loadRealEstateHistory()).toHaveLength(3);
    expect(new Set(loadRealEstateHistory().map((e) => e.id)).size).toBe(3);
  });

  it("지운다", () => {
    saveRealEstateHistory(condition);
    const [entry] = loadRealEstateHistory();
    expect(removeRealEstateHistory(entry.id)).toEqual({ ok: true });
    expect(loadRealEstateHistory()).toEqual([]);
  });

  it("저장소가 깨져 있어도 던지지 않는다", () => {
    localStorage.setItem(REALESTATE_HISTORY_KEY, "{not json");
    expect(loadRealEstateHistory()).toEqual([]);
  });

  it("저장하지 못하면 조용히 넘어가지 않는다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    const result = saveRealEstateHistory(condition);
    expect(result.ok).toBe(false);
  });
});
