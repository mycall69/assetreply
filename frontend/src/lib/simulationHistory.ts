/**
 * 시뮬레이션 이력 보관 (T088) — 005 FR-035~037b, research R5-9·R5-10.
 *
 * **조건만 저장한다.** 결과는 시세·배당·분할·설정(수수료·세율)·환율의 함수이고,
 * 그중 **설정과 환율이 바뀐다**. 저장하면 갱신 시점을 관리해야 하고 그 관리가 틀리면
 * 조용히 낡은 값을 보여준다 (R5-9). 조건은 사용자가 고른 값이라 바뀌지 않는다.
 *
 * **`localStorage`에 둔다.** 세션 저장소는 탭을 닫으면 사라져 FR-037("브라우저를
 * 닫았다 열어도 남는다")을 만족하지 못한다. 서버에 보내지 않으므로 다른 기기에서
 * 열면 비어 있고, 그래서 화면이 그 사실을 알려야 한다 (FR-037a).
 */

import type {
  DecimalString,
  Frequency,
  PrincipalCurrency,
  SimulationHistoryEntry,
  StockSearchResult,
} from "./types";

/** 저장소 키. 형식이 바뀌면 뒤의 숫자를 올린다 — 낡은 형식을 읽어 깨지지 않도록. */
export const HISTORY_KEY = "assetreplay:stock-history:v1";

/** 저장되는 것의 전부. **결과는 들어가지 않는다.** */
export interface HistoryCondition {
  stock: StockSearchResult;
  start: string;
  /** 일시금이면 원금, 적립식이면 한 번 납입액(011). */
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  /** 011 — 적립식만 담는다. 없으면 일시금이다(011 전 항목과 같은 모양 — research R11-11). */
  mode?: "recurring";
  frequency?: Frequency;
}

export type SaveResult = { ok: true } | { ok: false; reason: string };

/**
 * 조건에서 식별자를 만든다.
 *
 * 조건이 같으면 같은 값이 나와야 한다 — 같은 조건을 다시 돌릴 때마다 줄이 쌓이면
 * 목록이 못 쓰게 된다. 반대로 **재투자 여부 하나만 달라도 다른 값**이어야 한다.
 * 종목만 보고 묶으면 사용자가 비교하려던 두 조건이 하나로 합쳐진다 (FR-036).
 */
export function conditionId(condition: HistoryCondition): string {
  const { stock, start, principal, principalCurrency, reinvest } = condition;
  const base = [
    stock.market, stock.symbol, start, principal, principalCurrency,
    reinvest ? "R" : "N",
  ].join("|");
  // 011 — 같은 조건의 일시금과 적립식이 한 항목으로 뭉치지 않게 방식·주기를 붙인다. 일시금 식별자는 011 전과 같다.
  return condition.mode === "recurring" ? `${base}|recurring:${condition.frequency ?? "monthly"}` : base;
}

function read(): SimulationHistoryEntry[] {
  // 저장소가 깨져 있어도 **던지지 않는다.** 이력은 부가 기능이라 본 기능을 막으면
  // 안 된다 — 던지면 화면 전체가 죽는다.
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (raw === null) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SimulationHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: SimulationHistoryEntry[]): SaveResult {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
    return { ok: true };
  } catch {
    // R5-10 — 보관 한계에 닿았을 때 **조용히 실패하지 않는다.** 사용자는 저장된 줄
    // 알고 다음에 열었을 때 비어 있는 것을 보게 된다.
    return {
      ok: false,
      reason: "이력을 저장하지 못했습니다. 브라우저 저장 공간이 가득 찼을 수 있습니다.",
    };
  }
}

export function loadHistory(): SimulationHistoryEntry[] {
  return read();
}

/** 조건을 이력에 넣는다. 같은 조건이 이미 있으면 맨 앞으로 올린다. */
export function saveHistory(condition: HistoryCondition): SaveResult {
  const id = conditionId(condition);
  const entry: SimulationHistoryEntry = {
    id,
    stock: condition.stock,
    start: condition.start,
    principal: condition.principal,
    principalCurrency: condition.principalCurrency,
    reinvest: condition.reinvest,
    ...(condition.mode === "recurring" ? { mode: "recurring" as const, frequency: condition.frequency } : {}),
    savedAt: new Date().toISOString(),
  };
  // 실패하면 기존 이력은 그대로 남는다 — 저장소에 쓰지 못했을 뿐이다.
  return write([entry, ...read().filter((e) => e.id !== id)]);
}

export function removeHistory(id: string): SaveResult {
  return write(read().filter((e) => e.id !== id));
}
