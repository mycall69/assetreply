/**
 * 투자 비교 대상의 표시 이름 (014 반복 2026-10-10e T151) — FR-032, SC-017, data-model §11.
 *
 * 비교 화면의 이름 자리(칩·표·막힘 안내·범례·막대·모달 머리·저장 목록)가 모두 `targetName` 하나를 거친다. 주식은 006의 표시 코드
 * (`nameWithCode` — 메뉴 검색·고른 종목과 같은 글자), 가상자산은 한글 이름(없으면 영문 이름) + (심볼)이다. 예금·부동산은 그대로다.
 */
import { describe, expect, it } from "vitest";
import { targetName } from "@/lib/compareCondition";
import { coinNameWithSymbol } from "@/lib/displayCode";
import type { CryptoTarget, StockTarget } from "@/lib/types";
import { BTC_T, ETH_T, HELIO_T, SAMSUNG_T } from "./support/compareFixtures";

const VOO: StockTarget = { market: "NYSE", symbol: "VOO", name: "S&P 500 뱅가드 ETF", currency: "USD" };
const BRK: StockTarget = { market: "NYSE", symbol: "BRK-B", name: "버크셔 해서웨이 B", currency: "USD" };
const ECOPRO: StockTarget = { market: "KRX", symbol: "247540.KQ", name: "에코프로비엠", currency: "KRW" };
const TOYOTA: StockTarget = { market: "TSE", symbol: "7203.T", name: "도요타자동차", currency: "JPY" };
const BTS: CryptoTarget = { coinId: 1402, symbol: "BTS", name: "BitShares", nameKo: null, currency: "USD" };

describe("주식 — 이름(표시 코드)", () => {
  it("미국은 시세 티커 그대로다", () => {
    expect(targetName(VOO)).toBe("S&P 500 뱅가드 ETF(VOO)");
    expect(targetName(BRK)).toBe("버크셔 해서웨이 B(BRK-B)");
  });

  it("국내는 .KS·.KQ를 뗀다 — 시세 식별자 그대로면 메뉴와 다른 글자다", () => {
    expect(targetName(SAMSUNG_T)).toBe("삼성전자(005930)");
    expect(targetName(ECOPRO)).toBe("에코프로비엠(247540)");
  });

  it("일본은 .T를 뗀다", () => {
    expect(targetName(TOYOTA)).toBe("도요타자동차(7203)");
  });
});

describe("가상자산 — 한글 이름(없으면 영문 이름)(심볼)", () => {
  it("한글 이름이 있으면 한글 이름이다", () => {
    expect(targetName(BTC_T)).toBe("비트코인(BTC)");
    expect(targetName(ETH_T)).toBe("이더리움(ETH)");
  });

  it("한글 이름이 없어도 괄호를 빼먹지 않는다", () => {
    expect(targetName(BTS)).toBe("BitShares(BTS)");
  });

  it("검색 결과 줄과 같은 함수다", () => {
    expect(coinNameWithSymbol(BTC_T)).toBe("비트코인(BTC)");
    expect(coinNameWithSymbol(BTS)).toBe("BitShares(BTS)");
  });
});

describe("예금·부동산 — 그대로", () => {
  it("투자처 이름과 단지 평형이다", () => {
    expect(targetName({ institution: "saemaul" })).toBe("새마을금고");
    expect(targetName(HELIO_T)).toBe("헬리오시티아파트 30평대(국평)");
  });
});
