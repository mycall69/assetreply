/**
 * 외부 시세 페이지 URL (010 반복 1, T044) — FR-024~FR-026, SC-007, research R10-14·R10-15, data-model 7절.
 *
 * 저장하지 않고 외부를 부르지 않는다 — 자산의 식별에서 규칙으로 URL을 만든다. 규칙은 T040이 실제 페이지로 확인했다.
 * - 국내 `KRX`: `domestic/stock/{접미사를 뗀 6자리}` — 코스피·코스닥 같다
 * - 해외: `worldstock/stock/{티커}{접미사}` — NASDAQ `.O`, NYSE 없음, AMEX `.K`. 일본 `TSE`는 저장소 심볼 그대로(`7203.T`)
 * - 그 밖의 시장은 링크 없음(`null`) — 틀린 페이지로 보내지 않는다
 * - 가상자산: `crypto/UPBIT/{심볼}` — 늘 UPBIT(업비트 상장 여부를 모른다)
 * - 부동산: 네이버 통합검색 `{법정동} {단지명}` — 네이버 부동산에는 공개 검색 결과 주소가 없다. 법정동 이름을 모르면 단지명만
 */
import { describe, expect, it } from "vitest";
import { coinLink, complexSearchLink, stockLink } from "@/lib/externalLinks";

const STOCK = "https://stock.naver.com";

describe("stockLink", () => {
  it.each([
    [{ market: "KRX", symbol: "005930.KS" }, `${STOCK}/domestic/stock/005930/price`],
    [{ market: "KRX", symbol: "053800.KQ" }, `${STOCK}/domestic/stock/053800/price`],
    [{ market: "NASDAQ", symbol: "NVDA" }, `${STOCK}/worldstock/stock/NVDA.O/price`],
    [{ market: "NASDAQ", symbol: "JEPQ" }, `${STOCK}/worldstock/stock/JEPQ.O/price`],
    [{ market: "NYSE", symbol: "KO" }, `${STOCK}/worldstock/stock/KO/price`],
    [{ market: "AMEX", symbol: "IOSX" }, `${STOCK}/worldstock/stock/IOSX.K/price`],
    [{ market: "TSE", symbol: "7203.T" }, `${STOCK}/worldstock/stock/7203.T/price`],
  ])("%o → %s", (stock, url) => {
    expect(stockLink(stock)).toBe(url);
  });

  it("규칙을 확인하지 못한 시장은 링크가 없다", () => {
    expect(stockLink({ market: "LSE", symbol: "VOD" })).toBeNull();
  });

  it("국내 종목코드가 6자리가 아니면 링크가 없다 — 틀린 페이지로 보내지 않는다", () => {
    expect(stockLink({ market: "KRX", symbol: "ABC.KS" })).toBeNull();
  });
});

describe("coinLink", () => {
  it("업비트 경로로 심볼을 대문자로", () => {
    expect(coinLink({ symbol: "BTC" })).toBe(`${STOCK}/crypto/UPBIT/BTC/price`);
    expect(coinLink({ symbol: "eth" })).toBe(`${STOCK}/crypto/UPBIT/ETH/price`);
  });
});

describe("complexSearchLink", () => {
  const SEARCH = "https://search.naver.com/search.naver?query=";

  it("법정동 이름과 단지명으로 네이버 검색 — 공백·한글은 인코딩한다", () => {
    expect(complexSearchLink("헬리오시티아파트", "가락동"))
      .toBe(`${SEARCH}${encodeURIComponent("가락동 헬리오시티아파트")}`);
  });

  it("법정동 이름을 모르면 단지명만", () => {
    expect(complexSearchLink("헬리오시티아파트", null)).toBe(`${SEARCH}${encodeURIComponent("헬리오시티아파트")}`);
  });
});
