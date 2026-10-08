/**
 * 적립식·정기 적금 비교 실행 (013 T044) — FR-006, FR-007, FR-010, FR-012a.
 *
 * 적립식 질의는 메뉴 스토어의 `toRecurringQuery`(주식·가상자산), 정기 적금은 `toInstallmentQuery`의 출력 그대로다. 방식·주기를 바꾸면
 * 흐린다. 정기 적금인데 적금이 없는 투자처가 대상이면 서버의 400 `installment_not_available`이 막힘(`remove` 갈래)이 된다 — 정기예금
 * 금리로 대신하지 않는다(011).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { isStale, useCompareStore } from "@/stores/compareStore";
import { toRecurringQuery as cryptoRecurring } from "@/stores/cryptoStore";
import { toInstallmentQuery } from "@/stores/depositStore";
import { toRecurringQuery as stockRecurring } from "@/stores/stockStore";
import { BTC_T, ETH_T, HYNIX_T, SAMSUNG_T, apiError, ok, routeCompare } from "./support/compareFixtures";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

beforeEach(() => {
  vi.restoreAllMocks();
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2024-01-15", amount: "500000" });
});

describe("적립식 질의", () => {
  it("주식 적립식은 메뉴의 toRecurringQuery 그대로다", async () => {
    const get = routeCompare(() => ok("s"));
    useCompareStore.getState().setMethod("recurring");
    useCompareStore.getState().setFrequency("weekly");
    useCompareStore.getState().addTarget(SAMSUNG_T);
    useCompareStore.getState().addTarget(HYNIX_T);
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls[0][0]).toBe(`/api/comparison/stocks/recurring-simulation?${stockRecurring(
      { stock: SAMSUNG_T, start: "2024-01-15", principal: "500000", principalCurrency: "KRW", reinvest: true },
      { mode: "recurring", frequency: "weekly" })}`);
    expect(get.mock.calls[0][0]).toBe("/api/comparison/stocks/recurring-simulation?market=KRX&symbol=005930.KS"
      + "&start=2024-01-15&amount=500000&principalCurrency=KRW&frequency=weekly&reinvest=true");
  });

  it("가상자산 적립식은 메뉴의 toRecurringQuery 그대로다", async () => {
    const get = routeCompare(() => ok("c"));
    useCompareStore.getState().setAsset("crypto");
    useCompareStore.getState().setMethod("recurring");
    useCompareStore.getState().addTarget(BTC_T);
    useCompareStore.getState().addTarget(ETH_T);
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls[1][0]).toBe(`/api/comparison/crypto/recurring-simulation?${cryptoRecurring(
      { coin: { ...ETH_T, slug: null }, start: "2024-01-15", principal: "500000", principalCurrency: "KRW" },
      { mode: "recurring", frequency: "monthly" })}`);
  });

  it("정기 적금은 메뉴의 toInstallmentQuery 그대로다", async () => {
    const get = routeCompare(() => ok("d"));
    useCompareStore.getState().setAsset("deposit");
    useCompareStore.getState().setMethod("installment");
    useCompareStore.getState().addTarget({ institution: "commercial_bank" });
    useCompareStore.getState().addTarget({ institution: "mutual_finance" });
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls.map(([p]) => p)).toEqual([
      `/api/comparison/deposit/installment-simulation?${toInstallmentQuery({
        institution: "commercial_bank", start: "2024-01-15", principal: "500000" })}`,
      `/api/comparison/deposit/installment-simulation?${toInstallmentQuery({
        institution: "mutual_finance", start: "2024-01-15", principal: "500000" })}`,
    ]);
  });
});

describe("흐림과 막힘", () => {
  it("방식·주기를 바꾸면 흐린다", async () => {
    routeCompare(() => ok("s"));
    useCompareStore.getState().addTarget(SAMSUNG_T);
    useCompareStore.getState().addTarget(HYNIX_T);
    await useCompareStore.getState().runComparison();
    useCompareStore.getState().setMethod("recurring");
    expect(isStale(useCompareStore.getState())).toBe(true);
    useCompareStore.getState().setMethod("lump_sum");
    expect(isStale(useCompareStore.getState())).toBe(false);

    useCompareStore.getState().setMethod("recurring");
    await useCompareStore.getState().runComparison();
    useCompareStore.getState().setFrequency("daily");
    expect(isStale(useCompareStore.getState())).toBe(true);
  });

  it("정기 적금에 적금이 없는 투자처가 있으면 그 대상이 막힘(빼세요)이다", async () => {
    routeCompare((path) => (path.includes("savings_bank")
      ? apiError(400, "installment_not_available", { allowed: ["commercial_bank", "mutual_finance"] }) : ok("d")));
    useCompareStore.getState().setAsset("deposit");
    useCompareStore.getState().setMethod("installment");
    useCompareStore.getState().addTarget({ institution: "commercial_bank" });
    useCompareStore.getState().addTarget({ institution: "savings_bank" });
    await useCompareStore.getState().runComparison();
    const state = useCompareStore.getState().run?.byTarget.savings_bank;
    expect(state?.status).toBe("blocked");
    expect(state?.status === "blocked" && state.reason.kind).toBe("remove");
    expect(state?.status === "blocked" && state.reason.text).toBe("정기 적금이 없는 투자처");
  });
});
