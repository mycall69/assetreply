/**
 * 브라우저 옛 이력 키 (012 T055) — FR-013, data-model 5.3, research R12-11.
 *
 * 012 전에는 이력이 브라우저 저장소(자산군마다 키 하나)에 있었다. 012부터는 로컬 DB에 있고, 화면을 처음 열 때 그 자산군의 옛 키를 한 번 옮긴 뒤 지운다
 * — 두 곳에 있으면 어느 쪽이 맞는지 알 수 없다. 키는 012 전 lib의 키와 글자까지 같다.
 *
 * 읽기는 던지지 않는다 — 이력은 부가 기능이라 본 기능을 막으면 안 된다(012 전과 같다).
 */

import type { HistoryAsset } from "@/lib/historyApi";

export const LEGACY_KEYS: Readonly<Record<HistoryAsset, string>> = {
  stock: "assetreplay:stock-history:v1",
  crypto: "assetreplay:crypto-history:v1",
  deposit: "assetreplay.depositHistory.v1",
  realestate: "assetreplay:realestate-history:v1",
};

export type LegacyRead =
  | { status: "none" }
  /** JSON이 아니거나 배열이 아니다 — 옮기지도 지우지도 않는다(지우면 사용자가 되살릴 길이 없다). */
  | { status: "unreadable" }
  | { status: "entries"; entries: unknown[] };

export function readLegacy(asset: HistoryAsset): LegacyRead {
  let raw: string | null;
  try {
    raw = localStorage.getItem(LEGACY_KEYS[asset]);
  } catch {
    return { status: "none" };
  }
  if (raw === null) return { status: "none" };
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return { status: "unreadable" };
    return parsed.length === 0 ? { status: "none" } : { status: "entries", entries: parsed };
  } catch {
    return { status: "unreadable" };
  }
}

/** 그 자산군의 키만 지운다 — 옮기기가 성공한 뒤에만 부른다. */
export function clearLegacy(asset: HistoryAsset): void {
  try {
    localStorage.removeItem(LEGACY_KEYS[asset]);
  } catch {
    // 지우지 못해도 다음에 다시 옮기면 서버가 같은 조건으로 합친다 — 잃는 것이 없다
  }
}
