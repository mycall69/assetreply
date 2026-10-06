/**
 * 투자 원금 처음 값 (012 T061) — FR-016, SC-008, data-model 5.4, research R12-14.
 *
 * - 주식·가상자산·예금 화면을 처음 열면 원금이 `"10000000"`(쉼표 없는 저장 형식)이고 통화는 원화다. 빈칸이면 종목만 고르고 실행했을 때 원금을 묻는다
 * - **처음 열 때만**이다 — 방식(적립식)·상품(적금)·원금 통화를 바꿔도 칸의 값을 바꾸지 않는다(011 "방식을 바꾸면 결과는 비우고 조건은 남는다").
 *   바꿀 때마다 기본값으로 되돌리면 사용자가 고친 값이 사라진다
 * - 이력 다시 실행은 항목의 값을 넣는다 — 기본값으로 덮으면 다른 조건의 결과가 그 항목의 결과처럼 보인다
 * - 부동산은 대상이 아니다(매입가는 비우면 그 달 시세다)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { DEFAULT_PRINCIPAL } from "@/lib/principalFormat";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useDepositStore } from "@/stores/depositStore";
import { useRealEstateStore } from "@/stores/realEstateStore";
import { useStockStore } from "@/stores/stockStore";
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const COIN = { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin", currency: "USD" };

beforeEach(() => {
  vi.restoreAllMocks();
  useStockStore.setState(useStockStore.getInitialState(), true);
  useCryptoStore.setState(useCryptoStore.getInitialState(), true);
  useDepositStore.setState(useDepositStore.getInitialState(), true);
});

describe("처음 값", () => {
  it("저장 형식은 쉼표 없는 1천만이다", () => {
    expect(DEFAULT_PRINCIPAL).toBe("10000000");
  });

  it("새로 불러온 세 스토어의 원금이 10000000이고 주식·가상자산 통화는 원화다", async () => {
    vi.resetModules();
    const stock = (await import("@/stores/stockStore")).useStockStore.getState().input;
    const crypto = (await import("@/stores/cryptoStore")).useCryptoStore.getState().input;
    const deposit = (await import("@/stores/depositStore")).useDepositStore.getState().input;
    expect([stock.principal, stock.principalCurrency]).toEqual(["10000000", "KRW"]);
    expect([crypto.principal, crypto.principalCurrency]).toEqual(["10000000", "KRW"]);
    expect(deposit.principal).toBe("10000000");
  });

  it("부동산 매입가는 지금처럼 비어 있다", () => {
    expect(useRealEstateStore.getInitialState().input.buyPrice).toBe("");
  });
});

describe("처음 열 때만이다", () => {
  it("주식 — 적립식·주기·원금 통화를 바꿔도 그대로다", () => {
    useStockStore.getState().setPlan({ mode: "recurring", frequency: "weekly" });
    useStockStore.getState().setInput({ principalCurrency: "USD" });
    useStockStore.getState().setPlan({ mode: "lump_sum", frequency: "weekly" });
    expect(useStockStore.getState().input.principal).toBe("10000000");
    expect(useStockStore.getState().input.principalCurrency).toBe("USD");
  });

  it("가상자산 — 적립식·원금 통화를 바꿔도 그대로다", () => {
    useCryptoStore.getState().setPlan({ mode: "recurring", frequency: "daily" });
    useCryptoStore.getState().setInput({ principalCurrency: "USD" });
    useCryptoStore.getState().selectCoin(COIN);
    expect(useCryptoStore.getState().input.principal).toBe("10000000");
  });

  it("예금 — 적금·투자처를 바꿔도 그대로다", () => {
    useDepositStore.getState().setProduct("installment");
    useDepositStore.getState().selectInstitution("mutual_finance");
    useDepositStore.getState().setProduct("deposit");
    expect(useDepositStore.getState().input.principal).toBe("10000000");
  });

  it("사용자가 고친 값은 화면을 떠났다 돌아와도 남는다", () => {
    useStockStore.getState().setInput({ principal: "5000000" });
    useDepositStore.getState().setInput({ principal: "2000000" });
    useStockStore.getState().dispose();
    useDepositStore.getState().dispose();
    expect(useStockStore.getState().input.principal).toBe("5000000");
    expect(useDepositStore.getState().input.principal).toBe("2000000");
  });
});

describe("이력 다시 실행은 항목의 값이다", () => {
  const pending = () => vi.spyOn(apiClient, "get").mockImplementation(() => new Promise(() => undefined));

  it("주식", async () => {
    historyStub.seed("stock", [{ stock: STOCK, start: "2024-01-15", principal: "3000000", principalCurrency: "KRW",
      reinvest: true }]);
    await useStockStore.getState().restoreHistory();
    pending();
    void useStockStore.getState().rerunHistory(useStockStore.getState().history[0].id);
    expect(useStockStore.getState().input.principal).toBe("3000000");
  });

  it("가상자산", async () => {
    historyStub.seed("crypto", [{ coin: COIN, start: "2024-01-15", principal: "3000000", principalCurrency: "KRW" }]);
    await useCryptoStore.getState().restoreHistory();
    pending();
    void useCryptoStore.getState().rerunHistory(useCryptoStore.getState().history[0].id);
    expect(useCryptoStore.getState().input.principal).toBe("3000000");
  });

  it("예금", async () => {
    historyStub.seed("deposit", [{ institution: "saemaul", start: "2020-01-15", principal: "3000000" }]);
    await useDepositStore.getState().restoreHistory();
    pending();
    void useDepositStore.getState().rerunHistory(useDepositStore.getState().history[0].id);
    expect(useDepositStore.getState().input.principal).toBe("3000000");
  });
});
