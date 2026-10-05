/**
 * 부동산 이력 보관 (T050) — 009 FR-032, data-model "이력". 005·007·008의 이력과 같은 규칙이다.
 *
 * **조건만 저장한다**(단지·그 단지의 법정동·평형·매입일·직접 넣은 매입가) — 결과는 거래·세법·보유세 기준 비율의 함수라 바뀐다
 * (005 R5-9). **다른 자산군 이력과 다른 키**다 — 섞이면 한쪽 화면에서 다른 자산군의 항목을 다시 실행하려다 "알 수 없는 단지"가 된다.
 * `localStorage`에 둔다 — 브라우저를 닫았다 열어도 남는다.
 */

import type { DecimalString, RealEstateAreaKey, RealEstateHistoryEntry } from "./types";

/** 저장소 키(plan·data-model). 형식이 바뀌면 뒤의 숫자를 올린다 — 낡은 형식을 읽어 깨지지 않도록. */
export const REALESTATE_HISTORY_KEY = "assetreplay:realestate-history:v1";

export interface RealEstateHistoryCondition {
  complexId: number;
  complexName: string;
  /** 그 단지의 법정동 코드 — 시·도는 앞 2자리, 시·군·구는 앞 5자리로 정해진다. */
  umd: string;
  area: RealEstateAreaKey;
  areaLabel: string;
  buyDate: string;
  /** 직접 넣은 매입가(쉼표 없는 원 단위 문자열). 그 달 시세로 샀으면 `null`. */
  buyPrice: DecimalString | null;
}

export type SaveResult = { ok: true } | { ok: false; reason: string };

/** 조건에서 식별자를 만든다. 같은 조건이면 같은 값 — 다시 돌릴 때마다 줄이 쌓이지 않게 한다. */
export function realEstateConditionId({ complexId, area, buyDate, buyPrice }: RealEstateHistoryCondition): string {
  return [complexId, area, buyDate, buyPrice ?? "market"].join("|");
}

function read(): RealEstateHistoryEntry[] {
  // 저장소가 깨져 있어도 던지지 않는다 — 이력은 부가 기능이라 본 기능을 막으면 안 된다.
  try {
    const raw = localStorage.getItem(REALESTATE_HISTORY_KEY);
    if (raw === null) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RealEstateHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: RealEstateHistoryEntry[]): SaveResult {
  try {
    localStorage.setItem(REALESTATE_HISTORY_KEY, JSON.stringify(entries));
    return { ok: true };
  } catch {
    // 보관 한계에 닿았을 때 **조용히 실패하지 않는다**(005 R5-10).
    return { ok: false, reason: "이력을 저장하지 못했습니다. 브라우저 저장 공간이 가득 찼을 수 있습니다." };
  }
}

export function loadRealEstateHistory(): RealEstateHistoryEntry[] {
  return read();
}

/** 조건을 이력에 넣는다. 같은 조건이 있으면 맨 앞으로 올린다. */
export function saveRealEstateHistory(condition: RealEstateHistoryCondition): SaveResult {
  const id = realEstateConditionId(condition);
  const entry: RealEstateHistoryEntry = {
    id, complexId: condition.complexId, complexName: condition.complexName, umd: condition.umd,
    area: condition.area, areaLabel: condition.areaLabel, buyDate: condition.buyDate, buyPrice: condition.buyPrice,
    savedAt: new Date().toISOString(),
  };
  return write([entry, ...read().filter((e) => e.id !== id)]);
}

export function removeRealEstateHistory(id: string): SaveResult {
  return write(read().filter((e) => e.id !== id));
}
