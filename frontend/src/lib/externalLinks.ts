/**
 * 이름에서 외부 시세 페이지로 (010 반복 1, T049) — FR-024~FR-026, research R10-14·R10-15, data-model 7절.
 *
 * 저장하지 않고 외부를 부르지 않는다 — 자산의 식별에서 규칙으로 URL을 만든다. 규칙은 T040이 실제 페이지로 확인했다. 확인하지 못한 시장은
 * 링크가 없다(`null`) — 틀린 페이지로 보내느니 이름만 둔다.
 */

const STOCK = "https://stock.naver.com";
const SEARCH = "https://search.naver.com/search.naver?query=";

/** 해외 시장의 티커 접미사(T040 실측). NYSE는 접미사가 없고 TSE는 저장소 심볼(`7203.T`)이 그대로 네이버 코드다. */
const WORLD_SUFFIX: Record<string, string> = { NASDAQ: ".O", NYSE: "", AMEX: ".K", TSE: "" };

/** 주식 종목의 네이버 증권 페이지. 국내는 접미사를 뗀 6자리, 해외는 티커와 시장 접미사. */
export function stockLink(stock: { market: string; symbol: string }): string | null {
  if (stock.market === "KRX") {
    const code = stock.symbol.split(".")[0];
    return /^\d{6}$/.test(code) ? `${STOCK}/domestic/stock/${code}/price` : null;
  }
  const suffix = WORLD_SUFFIX[stock.market];
  if (suffix === undefined) return null;
  return `${STOCK}/worldstock/stock/${encodeURIComponent(stock.symbol + suffix)}/price`;
}

/** 코인의 네이버 증권 페이지 — 늘 업비트(업비트에 없는 코인은 네이버 증권 홈으로 간다 — R10-14 한계). */
export function coinLink(coin: { symbol: string }): string {
  return `${STOCK}/crypto/UPBIT/${encodeURIComponent(coin.symbol.toUpperCase())}/price`;
}

/**
 * 단지의 네이버 통합검색 — 네이버 부동산에는 공개 검색 결과 주소가 없다(R10-15). 맨 위 단지 카드가 네이버 부동산 단지 화면으로 이어진다.
 * 법정동 이름을 모르면 단지명만.
 */
export function complexSearchLink(complexName: string, umdName: string | null): string {
  const query = umdName ? `${umdName} ${complexName}` : complexName;
  return `${SEARCH}${encodeURIComponent(query)}`;
}
