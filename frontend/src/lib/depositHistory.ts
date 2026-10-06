/**
 * 예금 이력 보관 (T032) — 008 FR-037, data-model "이력". 005·007의 이력과 같은 규칙이다.
 *
 * **조건만 저장한다**(투자처·시작일·원금) — 결과는 금리·세율의 함수라 바뀐다(005 R5-9). **주식·가상자산 이력과 다른 키**다 —
 * 섞이면 한쪽 화면에서 다른 자산군의 항목을 다시 실행하려다 "알 수 없는 투자처"가 된다. `localStorage`에 둔다 — 브라우저를
 * 닫았다 열어도 남는다.
 */

import type { DecimalString, DepositHistoryEntry, DepositInstitutionKey } from "./types";

/** 저장소 키(data-model). 형식이 바뀌면 뒤의 숫자를 올린다 — 낡은 형식을 읽어 깨지지 않도록. */
export const DEPOSIT_HISTORY_KEY = "assetreplay.depositHistory.v1";

export interface DepositHistoryCondition {
  institution: DepositInstitutionKey;
  start: string;
  /** 정기예금이면 원금, 적금이면 월 납입액(011). */
  principal: DecimalString;
  /** 011 — 적금만 담는다. 없으면 정기예금이다(011 전 항목과 같은 모양 — research R11-11). */
  product?: "installment";
}

export type SaveResult = { ok: true } | { ok: false; reason: string };

/** 조건에서 식별자를 만든다. 같은 조건이면 같은 값 — 다시 돌릴 때마다 줄이 쌓이지 않게 한다. */
export function depositConditionId({ institution, start, principal, product }: DepositHistoryCondition): string {
  const base = [institution, start, principal].join("|");
  // 011 — 같은 조건의 정기예금과 적금이 한 항목으로 뭉치지 않게 상품을 붙인다. 정기예금 식별자는 011 전과 같다.
  return product === "installment" ? `${base}|installment` : base;
}

function read(): DepositHistoryEntry[] {
  // 저장소가 깨져 있어도 던지지 않는다 — 이력은 부가 기능이라 본 기능을 막으면 안 된다.
  try {
    const raw = localStorage.getItem(DEPOSIT_HISTORY_KEY);
    if (raw === null) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as DepositHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: DepositHistoryEntry[]): SaveResult {
  try {
    localStorage.setItem(DEPOSIT_HISTORY_KEY, JSON.stringify(entries));
    return { ok: true };
  } catch {
    // 보관 한계에 닿았을 때 **조용히 실패하지 않는다**(005 R5-10).
    return { ok: false, reason: "이력을 저장하지 못했습니다. 브라우저 저장 공간이 가득 찼을 수 있습니다." };
  }
}

export function loadDepositHistory(): DepositHistoryEntry[] {
  return read();
}

/** 조건을 이력에 넣는다. 같은 조건이 있으면 맨 앞으로 올린다. */
export function saveDepositHistory(condition: DepositHistoryCondition): SaveResult {
  const id = depositConditionId(condition);
  const entry: DepositHistoryEntry = {
    id, institution: condition.institution, start: condition.start, principal: condition.principal,
    ...(condition.product === "installment" ? { product: "installment" as const } : {}),
    savedAt: new Date().toISOString(),
  };
  return write([entry, ...read().filter((e) => e.id !== id)]);
}

export function removeDepositHistory(id: string): SaveResult {
  return write(read().filter((e) => e.id !== id));
}
