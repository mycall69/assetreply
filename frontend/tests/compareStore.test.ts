/**
 * 비교 화면 상태 (013 T018) — FR-002, FR-004, FR-009, FR-010, FR-012a, FR-013, FR-020, SC-002, SC-003, SC-007, data-model 5,
 * research R13-7·R13-8.
 *
 * - 대상마다 비교 경로 하나를 부른다. 질의는 **메뉴 스토어의 질의 함수 출력 그대로**다 — 같은 공통 조건이 대상마다 같게 들어간다(SC-002)
 * - 202면 그 자산군의 진행 스트림을 구독하고, 끝나면 **그 대상만** 다시 요청한다. 연달아 202를 세 번 받으면 수집 실패다
 * - 새 실행은 늦게 온 이전 실행의 응답·스트림 사건을 버린다(FR-012a)
 * - 비교는 이력을 쓰지 않는다(FR-020)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import { isStale, useCompareStore } from "@/stores/compareStore";
import { toQuery as cryptoQuery } from "@/stores/cryptoStore";
import { toQuery as depositQuery } from "@/stores/depositStore";
import { toQuery as stockQuery } from "@/stores/stockStore";
import {
  BTC_T,
  ETH_T,
  HELIO_T,
  HYNIX_T,
  SAMSUNG_T,
  XLK_T,
  apiError,
  collectingStock,
  ok,
  routeCompare,
} from "./support/compareFixtures";
import { historyStub } from "./support/historyStub";

const streams = vi.hoisted(() => ({
  stock: [] as { jobId: number; handlers: StockProgressHandlers; active: boolean }[],
}));
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (jobId: number, handlers: StockProgressHandlers) => {
    const sub = { jobId, handlers, active: true };
    streams.stock.push(sub);
    return () => {
      sub.active = false;
    };
  },
}));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

const STOCK = "/api/comparison/stocks/simulation";

beforeEach(() => {
  vi.restoreAllMocks();
  streams.stock.length = 0;
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02", amount: "10000000" });
});

function addAll(...targets: Parameters<ReturnType<typeof useCompareStore.getState>["addTarget"]>[0][]): void {
  for (const t of targets) useCompareStore.getState().addTarget(t);
}

const stockPath = (t: typeof SAMSUNG_T) => `${STOCK}?${stockQuery({
  stock: t, start: "2020-01-02", principal: "10000000", principalCurrency: "KRW", reinvest: true })}`;

describe("실행 — 대상마다 요청", () => {
  it("주식 대상마다 메뉴의 질의 함수 그대로 부른다", async () => {
    const get = routeCompare((path) => ok(path));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls.map(([p]) => p)).toEqual([stockPath(SAMSUNG_T), stockPath(HYNIX_T)]);
    expect(get.mock.calls[0][0]).toBe(
      `${STOCK}?market=KRX&symbol=005930.KS&start=2020-01-02&principal=10000000&principalCurrency=KRW&reinvest=true`);
  });

  it("가상자산·예금·부동산도 메뉴의 질의 함수다(부동산은 매입가 없이)", async () => {
    const get = routeCompare((path) => ok(path));
    useCompareStore.getState().setAsset("crypto");
    addAll(BTC_T, ETH_T);
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls[0][0]).toBe(`/api/comparison/crypto/simulation?${cryptoQuery({
      coin: { ...BTC_T, slug: null }, start: "2020-01-02", principal: "10000000", principalCurrency: "KRW" })}`);

    get.mockClear();
    useCompareStore.getState().setAsset("deposit");
    addAll({ institution: "commercial_bank" }, { institution: "savings_bank" });
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls[1][0]).toBe(`/api/comparison/deposit/simulation?${depositQuery({
      institution: "savings_bank", start: "2020-01-02", principal: "10000000" })}`);

    get.mockClear();
    useCompareStore.getState().setAsset("realestate");
    addAll(HELIO_T, { ...HELIO_T, area: "20", areaLabel: "20평대" });
    await useCompareStore.getState().runComparison();
    expect(get.mock.calls[0][0]).toBe("/api/comparison/realestate/simulation?complexId=12&area=30k&buyDate=2020-01-02");
  });

  it("200은 결과, 거절은 막힘, 출처 오류는 실패다", async () => {
    routeCompare((path) => (path.includes("005930") ? ok("s")
      : path.includes("000660") ? apiError(400, "before_listing", { startableFrom: "2021-11-29", basis: "listing" })
        : apiError(502, "source_unavailable")));
    addAll(SAMSUNG_T, HYNIX_T, XLK_T);
    await useCompareStore.getState().runComparison();
    const byTarget = useCompareStore.getState().run?.byTarget ?? {};
    expect(byTarget["KRX|005930.KS"].status).toBe("ok");
    expect(byTarget["KRX|000660.KS"].status).toBe("blocked");
    expect(byTarget["NYSE|XLK"].status).toBe("failed");
  });

  it("실행 조건은 결과를 낸 조건으로 남는다", async () => {
    routeCompare(() => ok("s"));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    expect(useCompareStore.getState().run?.condition.targets).toEqual([SAMSUNG_T, HYNIX_T]);
  });

  it("대상이 2개보다 적으면 요청하지 않고 알린다", async () => {
    const get = routeCompare(() => ok("s"));
    addAll(SAMSUNG_T);
    await useCompareStore.getState().runComparison();
    expect(get).not.toHaveBeenCalled();
    expect(useCompareStore.getState().notice).toContain("2개 이상");
  });
});

describe("수집 기다리기", () => {
  it("202면 진행 스트림을 구독하고 끝나면 그 대상만 다시 요청한다", async () => {
    let hynix = 0;
    const get = routeCompare((path) => {
      if (path.includes("000660")) return (hynix += 1) === 1 ? collectingStock(41) : ok("h");
      return ok("s");
    });
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    expect(useCompareStore.getState().run?.byTarget["KRX|000660.KS"].status).toBe("collecting");
    expect(streams.stock.map((s) => s.jobId)).toEqual([41]);

    streams.stock[0].handlers.onSnapshot({ jobId: 41, chunksDone: 1, chunksTotal: 4, rangeStart: "2001-01-01",
      rangeEnd: "2020-01-31", daysDone: 100, daysTotal: 400 });
    const state = useCompareStore.getState().run?.byTarget["KRX|000660.KS"];
    expect(state?.status === "collecting" && state.progress).toEqual({ done: 100, total: 400 });

    get.mockClear();
    streams.stock[0].handlers.onCompleted();
    await vi.waitFor(() => expect(useCompareStore.getState().run?.byTarget["KRX|000660.KS"].status).toBe("ok"));
    expect(get.mock.calls.map(([p]) => p)).toEqual([stockPath(HYNIX_T)]);
    expect(streams.stock[0].active).toBe(false);
  });

  it("스트림이 실패하면 그 대상은 수집 실패이고 다시 시도할 수 있다", async () => {
    let calls = 0;
    routeCompare((path) => (path.includes("000660") ? ((calls += 1) === 1 ? collectingStock(41) : ok("h")) : ok("s")));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    streams.stock[0].handlers.onFailed("출처가 거절했습니다");
    const failed = useCompareStore.getState().run?.byTarget["KRX|000660.KS"];
    expect(failed?.status === "failed" && failed.reason).toContain("출처가 거절했습니다");

    await useCompareStore.getState().retryTarget("KRX|000660.KS");
    expect(useCompareStore.getState().run?.byTarget["KRX|000660.KS"].status).toBe("ok");
  });

  it("연달아 202를 세 번 받으면 수집 실패다 — 끝없이 되풀이하지 않는다", async () => {
    routeCompare((path) => (path.includes("000660") ? collectingStock(41) : ok("s")));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    // 첫 응답이 202(1번째) → 완료 → 다시 202(2번째) → 완료 → 다시 202(3번째)면 더 기다리지 않는다.
    for (let i = 0; i < 2; i += 1) {
      const live = streams.stock.filter((s) => s.active);
      expect(live).toHaveLength(1);
      live[0].handlers.onCompleted();
      if (i === 0) await vi.waitFor(() => expect(streams.stock).toHaveLength(2));
    }
    await vi.waitFor(() => expect(useCompareStore.getState().run?.byTarget["KRX|000660.KS"].status).toBe("failed"));
    const failed = useCompareStore.getState().run?.byTarget["KRX|000660.KS"];
    expect(failed?.status === "failed" && failed.reason).toContain("수집이 끝나지 않았습니다");
  });
});

describe("늦은 응답", () => {
  it("새 실행은 이전 실행의 늦은 응답을 버린다", async () => {
    let release: (value: unknown) => void = () => undefined;
    routeCompare((path) => (path.includes("000660") && !path.includes("2021")
      ? new Promise((resolve) => { release = resolve; }) : ok("x")));
    addAll(SAMSUNG_T, HYNIX_T);
    const first = useCompareStore.getState().runComparison();
    useCompareStore.getState().setStart("2021-01-04");
    await useCompareStore.getState().runComparison();
    release(ok("늦은 응답"));
    await first;
    const state = useCompareStore.getState().run;
    expect(state?.condition.start).toBe("2021-01-04");
    const hynix = state?.byTarget["KRX|000660.KS"];
    expect(hynix?.status === "ok" && hynix.data.target).not.toBe("늦은 응답");
  });

  it("이전 실행의 스트림 완료는 다시 요청하지 않는다", async () => {
    routeCompare((path) => (path.includes("000660") ? collectingStock(41) : ok("s")));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    const old = streams.stock[0];
    routeCompare(() => ok("new"));
    await useCompareStore.getState().runComparison();
    expect(old.active).toBe(false);
    const get = routeCompare(() => ok("late"));
    const before = get.mock.calls.length;
    old.handlers.onCompleted();
    await Promise.resolve();
    expect(get.mock.calls.length).toBe(before);
  });
});

describe("흐림 — 조건이 바뀜", () => {
  it("결과를 낸 조건과 지금 조건이 다르면 흐리고, 되돌리면 풀린다", async () => {
    routeCompare(() => ok("s"));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    expect(isStale(useCompareStore.getState())).toBe(false);
    useCompareStore.getState().setStart("2021-01-04");
    expect(isStale(useCompareStore.getState())).toBe(true);
    useCompareStore.getState().setStart("2020-01-02");
    expect(isStale(useCompareStore.getState())).toBe(false);
  });

  it("대상을 더하거나 빼면 흐린다. 정렬은 조건이 아니다", async () => {
    routeCompare(() => ok("s"));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    useCompareStore.getState().toggleSort("returnRate");
    expect(isStale(useCompareStore.getState())).toBe(false);
    useCompareStore.getState().addTarget(XLK_T);
    expect(isStale(useCompareStore.getState())).toBe(true);
    useCompareStore.getState().removeTarget("NYSE|XLK");
    expect(isStale(useCompareStore.getState())).toBe(false);
  });

  it("실행하지 않았으면 흐리지 않는다", () => {
    addAll(SAMSUNG_T, HYNIX_T);
    expect(isStale(useCompareStore.getState())).toBe(false);
  });
});

describe("대상", () => {
  it("같은 대상은 다시 더하지 않고 알린다", () => {
    expect(useCompareStore.getState().addTarget(SAMSUNG_T)).toBe(true);
    expect(useCompareStore.getState().addTarget({ ...SAMSUNG_T })).toBe(false);
    expect(useCompareStore.getState().targets).toHaveLength(1);
    expect(useCompareStore.getState().notice).toContain("이미 더한 대상");
  });

  it("11번째는 더하지 않고 알린다", () => {
    for (let i = 0; i < 10; i += 1) {
      useCompareStore.getState().addTarget({ ...SAMSUNG_T, symbol: `00000${i}.KS` });
    }
    expect(useCompareStore.getState().addTarget({ ...SAMSUNG_T, symbol: "999999.KS" })).toBe(false);
    expect(useCompareStore.getState().targets).toHaveLength(10);
    expect(useCompareStore.getState().notice).toContain("최대 10개");
  });

  it("예금은 다섯이 끝이다", () => {
    useCompareStore.getState().setAsset("deposit");
    for (const key of ["commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul"] as const) {
      useCompareStore.getState().addTarget({ institution: key });
    }
    expect(useCompareStore.getState().targets).toHaveLength(5);
  });

  it("고를 수 없게 된 원금 통화는 원화로 돌리고 알린다", () => {
    useCompareStore.getState().addTarget(XLK_T);
    useCompareStore.getState().setPrincipalCurrency("USD");
    expect(useCompareStore.getState().principalCurrency).toBe("USD");
    useCompareStore.getState().addTarget(SAMSUNG_T);
    expect(useCompareStore.getState().principalCurrency).toBe("KRW");
    expect(useCompareStore.getState().notice).toContain("원화");
  });
});

describe("자산군 전환", () => {
  it("대상과 결과를 비우고 시작일·금액은 남기며 구독을 모두 푼다", async () => {
    routeCompare((path) => (path.includes("000660") ? collectingStock(41) : ok("s")));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    useCompareStore.getState().setAmount("20000000");
    useCompareStore.getState().setAsset("realestate");
    const state = useCompareStore.getState();
    expect(state.targets).toEqual([]);
    expect(state.run).toBeNull();
    expect(state.amount).toBe("20000000");
    expect(state.start).toBe("2020-01-02");
    expect(state.method).toBe("hold");
    expect(streams.stock.every((s) => !s.active)).toBe(true);
  });

  it("없는 방식은 그 자산군의 기본 방식으로 바뀐다", () => {
    useCompareStore.getState().setMethod("recurring");
    useCompareStore.getState().setAsset("deposit");
    expect(useCompareStore.getState().method).toBe("deposit");
    useCompareStore.getState().setAsset("crypto");
    expect(useCompareStore.getState().method).toBe("lump_sum");
  });
});

describe("이력", () => {
  it("비교는 이력을 쓰지 않는다", async () => {
    routeCompare((path) => (path.includes("000660") ? collectingStock(41) : ok("s")));
    addAll(SAMSUNG_T, HYNIX_T);
    await useCompareStore.getState().runComparison();
    routeCompare(() => ok("h"));
    streams.stock[0].handlers.onCompleted();
    await vi.waitFor(() => expect(useCompareStore.getState().run?.byTarget["KRX|000660.KS"].status).toBe("ok"));
    expect(historyStub.calls().filter((c) => c.method === "PUT")).toEqual([]);
  });
});
