/**
 * 표시용 종목 코드 (006 FR-025, research R6-20) — 반복 2026-10-03.
 *
 * 고른 종목이 이미 가진 **시세 식별자에서 되돌린다** — 이력·고른 종목에 코드를 따로 저장하지 않는다.
 * 따로 저장하면 이미 브라우저에 남은 이력 항목에는 값이 없다.
 *
 * 국내는 `.KS`·`.KQ`, 일본은 `.T`를 뗀다. 미국은 시세 식별자의 티커 그대로다(`BRK-B`) — 키움 목록의
 * 코드(`BRKb`)는 사용자가 흔히 보는 표기가 아니다.
 */
import type { StockMarket } from "@/lib/types";

const SUFFIX: Partial<Record<StockMarket, RegExp>> = {
  KRX: /\.(KS|KQ)$/,
  TSE: /\.T$/,
};

export function displayCode(market: StockMarket, symbol: string): string {
  const suffix = SUFFIX[market];
  return suffix === undefined ? symbol : symbol.replace(suffix, "");
}

/** `삼성전자(005930)`. 코드는 이름 옆에 한 번만 쓴다. */
export function nameWithCode(stock: { market: StockMarket; symbol: string; name: string }): string {
  return `${stock.name}(${displayCode(stock.market, stock.symbol)})`;
}
