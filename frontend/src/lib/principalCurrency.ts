/**
 * 원금 통화 조합 (T080) — 006 FR-050, FR-050b~050d, research R6-11.
 *
 * 원금 통화는 **원화 또는 종목 통화**뿐이다. 유로는 고를 수 없다 — 지원 시장 가운데 유로로 거래되는
 * 곳이 없다(FR-050d). 판정의 근거는 서버의 같은 규칙이다(`check_principal_currency`). 화면이 먼저
 * 막는 것은 거절당할 요청을 보내지 않기 위해서다 — 서버만 막으면 고른 뒤 매번 거절당한다.
 */

import type { PrincipalCurrency } from "./types";

const SELECTABLE: readonly PrincipalCurrency[] = ["KRW", "USD", "JPY"];

/** 그 종목에 고를 수 있는 원금 통화. 종목을 고르기 전에는 원화뿐이다. */
export function allowedPrincipals(stockCurrency: string | null): PrincipalCurrency[] {
  const own = SELECTABLE.find((c) => c === stockCurrency);
  return own === undefined || own === "KRW" ? ["KRW"] : ["KRW", own];
}

export function isAllowedPrincipal(code: string, stockCurrency: string | null): boolean {
  return (allowedPrincipals(stockCurrency) as string[]).includes(code);
}

/** 그 종목의 규칙을 사람이 읽는 말로. */
export function principalRule(stockCurrency: string | null): string {
  const allowed = allowedPrincipals(stockCurrency);
  return allowed.length === 1
    ? "원화 원금만 고를 수 있습니다"
    : `${allowed.join(" 또는 ")} 원금만 고를 수 있습니다`;
}
