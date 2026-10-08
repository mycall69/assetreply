/**
 * 비교 조건 (013 T013) — FR-004, FR-007, FR-012a, data-model 2.
 *
 * 정규 조건은 저장 본문(서버 검증)과 같은 모양이다. 화면은 "지금 조건 = 결과를 낸 조건"을 이것으로 가른다(흐림 — 명확화 6).
 */
import { describe, expect, it } from "vitest";
import {
  allowedCurrencies,
  autoName,
  methodsFor,
  sameCondition,
  targetKey,
  targetName,
  toCondition,
  type CompareInput,
} from "@/lib/compareCondition";
import type { CryptoTarget, RealEstateTarget, StockTarget } from "@/lib/types";

const SAMSUNG: StockTarget = { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const XLK: StockTarget = { market: "NYSE", symbol: "XLK", name: "Technology Select Sector SPDR Fund", currency: "USD" };
const AAPL: StockTarget = { market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD" };
const BTC: CryptoTarget = { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" };
const HELIO: RealEstateTarget = { complexId: 4, name: "헬리오시티아파트", umdName: "가락동", area: "30k", areaLabel: "30평대(국평)" };

const stock = (over: Partial<CompareInput> = {}): CompareInput => ({
  asset: "stock", method: "lump_sum", frequency: "monthly", start: "2020-01-02", amount: "10000000",
  principalCurrency: "KRW", reinvest: true, targets: [SAMSUNG, XLK], ...over,
});

describe("toCondition", () => {
  it("주식 일시금은 data-model 2의 칸이다", () => {
    expect(toCondition(stock())).toEqual({
      v: 1, asset: "stock", method: "lump_sum", frequency: null, start: "2020-01-02", amount: "10000000",
      principalCurrency: "KRW", reinvest: true, targets: [SAMSUNG, XLK],
    });
  });

  it("적립식만 주기가 있다", () => {
    expect(toCondition(stock({ method: "recurring", frequency: "weekly" })).frequency).toBe("weekly");
  });

  it("재투자는 주식만이다 — 가상자산·예금·부동산은 null", () => {
    expect(toCondition({ ...stock(), asset: "crypto", targets: [BTC] }).reinvest).toBeNull();
    expect(toCondition({ ...stock(), asset: "deposit", method: "deposit", targets: [{ institution: "commercial_bank" }] })
      .reinvest).toBeNull();
  });

  it("부동산은 금액이 없고 원화다", () => {
    const cond = toCondition({ ...stock(), asset: "realestate", method: "hold", principalCurrency: "USD", targets: [HELIO] });
    expect(cond.amount).toBeNull();
    expect(cond.principalCurrency).toBe("KRW");
    expect(cond.targets).toEqual([HELIO]);
  });

  it("예금도 원화다", () => {
    expect(toCondition({ ...stock(), asset: "deposit", method: "deposit", principalCurrency: "USD",
      targets: [{ institution: "savings_bank" }] }).principalCurrency).toBe("KRW");
  });

  it("대상의 알려진 칸만 남긴다", () => {
    const loose = { ...BTC, rank: 1, slug: "bitcoin" } as CryptoTarget;
    expect(toCondition({ ...stock(), asset: "crypto", targets: [loose] }).targets).toEqual([BTC]);
  });
});

describe("sameCondition", () => {
  const base = toCondition(stock());

  it("같은 입력이면 같다", () => {
    expect(sameCondition(base, toCondition(stock()))).toBe(true);
  });

  it.each([
    ["시작일", { start: "2020-01-03" }],
    ["금액", { amount: "20000000" }],
    ["통화", { principalCurrency: "USD" as const }],
    ["재투자", { reinvest: false }],
    ["방식", { method: "recurring" as const }],
    ["대상 더하기", { targets: [SAMSUNG, XLK, AAPL] }],
    ["대상 빼기", { targets: [SAMSUNG] }],
    ["대상 차례", { targets: [XLK, SAMSUNG] }],
  ])("%s이 다르면 다르다", (_name, over) => {
    expect(sameCondition(base, toCondition(stock(over)))).toBe(false);
  });

  it("일시금에서 주기를 바꿔도 같다 — 일시금의 조건에 주기가 없다", () => {
    expect(sameCondition(base, toCondition(stock({ frequency: "daily" })))).toBe(true);
  });

  it("결과가 없으면 같지 않다", () => {
    expect(sameCondition(null, base)).toBe(false);
  });
});

describe("대상 키와 이름", () => {
  it.each([
    [SAMSUNG, "KRX|005930.KS"],
    [BTC, "17"],
    [{ institution: "credit_union" as const }, "credit_union"],
    [HELIO, "4|30k"],
  ])("%o → %s", (target, key) => {
    expect(targetKey(target)).toBe(key);
  });

  it("이름은 한국어 이름을 먼저 쓴다", () => {
    expect(targetName(BTC)).toBe("비트코인");
    expect(targetName(SAMSUNG)).toBe("삼성전자");
    expect(targetName({ institution: "saemaul" })).toBe("새마을금고");
    expect(targetName(HELIO)).toBe("헬리오시티아파트 30평대(국평)");
  });
});

describe("autoName", () => {
  it("자산군·대상 수·시작일·방식이다", () => {
    expect(autoName(toCondition(stock({ targets: [SAMSUNG, XLK, AAPL] })))).toBe("주식 3개 · 2020-01-02 · 일시금");
    expect(autoName(toCondition({ ...stock(), asset: "deposit", method: "installment",
      targets: [{ institution: "commercial_bank" }, { institution: "mutual_finance" }] })))
      .toBe("예금 2개 · 2020-01-02 · 정기 적금");
  });
});

describe("allowedCurrencies", () => {
  it("대상이 없으면 원화뿐이다", () => {
    expect(allowedCurrencies("stock", [])).toEqual(["KRW"]);
  });

  it("모든 대상의 통화가 같으면 그 통화도 된다", () => {
    expect(allowedCurrencies("stock", [XLK, AAPL])).toEqual(["KRW", "USD"]);
    expect(allowedCurrencies("crypto", [BTC])).toEqual(["KRW", "USD"]);
  });

  it("국내·해외가 섞이면 원화뿐이다", () => {
    expect(allowedCurrencies("stock", [SAMSUNG, XLK])).toEqual(["KRW"]);
  });

  it("예금·부동산은 원화뿐이다", () => {
    expect(allowedCurrencies("realestate", [HELIO])).toEqual(["KRW"]);
  });
});

describe("methodsFor", () => {
  it("자산군마다 고를 수 있는 방식", () => {
    expect(methodsFor("stock")).toEqual(["lump_sum", "recurring"]);
    expect(methodsFor("crypto")).toEqual(["lump_sum", "recurring"]);
    expect(methodsFor("deposit")).toEqual(["deposit", "installment"]);
    expect(methodsFor("realestate")).toEqual(["hold"]);
  });
});
