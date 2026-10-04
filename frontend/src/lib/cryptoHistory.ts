/**
 * 가상자산 이력 보관 (T044) — 007 FR-045, FR-046. 005의 `simulationHistory`와 같은 규칙이다.
 *
 * **조건만 저장한다** — 결과는 일봉·설정·환율의 함수라 바뀐다(005 R5-9). **주식 이력과 다른 키**다 — 섞이면 한쪽 화면에서 다른
 * 자산군의 항목을 다시 실행하려다 "없는 종목"이 된다. `localStorage`에 둔다 — 브라우저를 닫았다 열어도 남는다.
 */

import type { CoinRef, CryptoHistoryEntry, DecimalString, PrincipalCurrency } from "./types";

/** 저장소 키. 형식이 바뀌면 뒤의 숫자를 올린다 — 낡은 형식을 읽어 깨지지 않도록. */
export const CRYPTO_HISTORY_KEY = "assetreplay:crypto-history:v1";

export interface CryptoHistoryCondition {
  coin: CoinRef;
  start: string;
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
}

export type SaveResult = { ok: true } | { ok: false; reason: string };

/** 조건에서 식별자를 만든다. 같은 조건이면 같은 값 — 다시 돌릴 때마다 줄이 쌓이지 않게 한다. 코인은 id로 가른다. */
export function cryptoConditionId(condition: CryptoHistoryCondition): string {
  const { coin, start, principal, principalCurrency } = condition;
  return [coin.coinId, start, principal, principalCurrency].join("|");
}

function read(): CryptoHistoryEntry[] {
  // 저장소가 깨져 있어도 던지지 않는다 — 이력은 부가 기능이라 본 기능을 막으면 안 된다.
  try {
    const raw = localStorage.getItem(CRYPTO_HISTORY_KEY);
    if (raw === null) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CryptoHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: CryptoHistoryEntry[]): SaveResult {
  try {
    localStorage.setItem(CRYPTO_HISTORY_KEY, JSON.stringify(entries));
    return { ok: true };
  } catch {
    // 보관 한계에 닿았을 때 **조용히 실패하지 않는다**(005 R5-10).
    return { ok: false, reason: "이력을 저장하지 못했습니다. 브라우저 저장 공간이 가득 찼을 수 있습니다." };
  }
}

export function loadCryptoHistory(): CryptoHistoryEntry[] {
  return read();
}

/** 조건을 이력에 넣는다. 같은 조건이 있으면 맨 앞으로 올린다. 검색 결과의 순위·일치 종류 같은 것은 남기지 않는다. */
export function saveCryptoHistory(condition: CryptoHistoryCondition): SaveResult {
  const { coinId, symbol, name, nameKo, slug, currency } = condition.coin;
  const id = cryptoConditionId(condition);
  const entry: CryptoHistoryEntry = {
    id,
    coin: { coinId, symbol, name, nameKo, slug, currency },
    start: condition.start,
    principal: condition.principal,
    principalCurrency: condition.principalCurrency,
    savedAt: new Date().toISOString(),
  };
  return write([entry, ...read().filter((e) => e.id !== id)]);
}

export function removeCryptoHistory(id: string): SaveResult {
  return write(read().filter((e) => e.id !== id));
}
