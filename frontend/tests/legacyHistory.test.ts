/**
 * 브라우저 옛 이력 키 (012 T044) — FR-013, data-model 5.3, research R12-11.
 *
 * - 키 넷은 012 전 화면 lib의 키와 글자까지 같다 — 하나라도 다르면 그 자산군의 이력을 옮기지 못한 채 잃는다
 * - 읽기는 셋으로 나뉜다: 없음(`none`), 읽을 수 없음(`unreadable` — JSON 아님·배열 아님), 항목(`entries`). 읽을 수 없는 키는 옮기지도 지우지도 않는다
 * - 지우기는 그 자산군의 키만 지운다 — 다른 자산군의 키를 건드리면 자산군이 섞이거나 옮기기 전에 잃는다(FR-013 *다른 곳에서 일어남*)
 */
import { beforeEach, describe, expect, it } from "vitest";
import { LEGACY_KEYS, clearLegacy, readLegacy } from "@/lib/legacyHistory";

beforeEach(() => localStorage.clear());

describe("옛 키", () => {
  it("키 넷이 012 전 그대로다", () => {
    expect(LEGACY_KEYS).toEqual({
      stock: "assetreplay:stock-history:v1",
      crypto: "assetreplay:crypto-history:v1",
      deposit: "assetreplay.depositHistory.v1",
      realestate: "assetreplay:realestate-history:v1",
    });
  });

  it("없으면 none이다", () => {
    expect(readLegacy("stock")).toEqual({ status: "none" });
  });

  it("JSON이 아니거나 배열이 아니면 unreadable이다", () => {
    localStorage.setItem(LEGACY_KEYS.crypto, "{깨짐");
    expect(readLegacy("crypto")).toEqual({ status: "unreadable" });
    localStorage.setItem(LEGACY_KEYS.crypto, JSON.stringify({ a: 1 }));
    expect(readLegacy("crypto")).toEqual({ status: "unreadable" });
  });

  it("배열이면 항목이다 — 빈 배열은 none이다", () => {
    localStorage.setItem(LEGACY_KEYS.deposit, JSON.stringify([{ institution: "saemaul", start: "2020-01-15" }]));
    expect(readLegacy("deposit")).toEqual({ status: "entries", entries: [{ institution: "saemaul", start: "2020-01-15" }] });
    localStorage.setItem(LEGACY_KEYS.deposit, "[]");
    expect(readLegacy("deposit")).toEqual({ status: "none" });
  });

  it("지우기는 그 자산군의 키만 지운다", () => {
    for (const key of Object.values(LEGACY_KEYS)) localStorage.setItem(key, "[]");
    clearLegacy("stock");
    expect(localStorage.getItem(LEGACY_KEYS.stock)).toBeNull();
    for (const asset of ["crypto", "deposit", "realestate"] as const) {
      expect(localStorage.getItem(LEGACY_KEYS[asset])).toBe("[]");
    }
  });
});
