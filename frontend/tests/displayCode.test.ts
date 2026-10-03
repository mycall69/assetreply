/**
 * 표시용 코드 (T112) — 006 FR-025, SC-019, research R6-20. 반복 2026-10-03.
 *
 * 고른 종목이 이미 가진 **시세 식별자**에서 되돌린다 — 이력·고른 종목에 따로 저장하지 않는다. 미국은 키움 목록의
 * 코드(`BRKb`)가 아니라 사용자가 흔히 보는 티커(`BRK-B`)다.
 */
import { describe, expect, it } from "vitest";
import { displayCode, nameWithCode } from "@/lib/displayCode";

describe("표시용 코드", () => {
  it.each([
    ["KRX", "005930.KS", "005930"],
    ["KRX", "247540.KQ", "247540"],
    ["KRX", "0030R0.KS", "0030R0"],
    ["KRX", "02826K.KS", "02826K"],
    ["TSE", "7203.T", "7203"],
    ["NASDAQ", "AAPL", "AAPL"],
    ["NYSE", "BRK-B", "BRK-B"],
    ["AMEX", "SPY", "SPY"],
  ] as const)("%s %s → %s", (market, symbol, code) => {
    expect(displayCode(market, symbol)).toBe(code);
  });

  it("종목명 옆에 괄호로 붙인다", () => {
    expect(nameWithCode({ market: "KRX", symbol: "005930.KS", name: "삼성전자" }))
      .toBe("삼성전자(005930)");
    expect(nameWithCode({ market: "TSE", symbol: "7203.T", name: "토요타자동차" }))
      .toBe("토요타자동차(7203)");
  });
});
