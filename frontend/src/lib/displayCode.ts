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

/**
 * `비트코인(BTC)` — 한글 이름이 없으면 영문 이름(`BitShares(BTS)`). 014 반복 2026-10-10e(FR-032) — 투자 비교의 대상 이름과 코인 검색
 * 결과 줄의 맨 앞 이름이 함께 쓴다. 같은 코인이 두 자리에서 다른 글자가 되지 않게 한 곳에 둔다.
 */
export function coinNameWithSymbol(coin: { name: string; nameKo: string | null; symbol: string }): string {
  return `${coin.nameKo ?? coin.name}(${coin.symbol})`;
}
