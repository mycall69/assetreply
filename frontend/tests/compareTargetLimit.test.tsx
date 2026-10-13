/**
 * 투자 비교의 대상 수 한도와 연결 차례 (014 반복 2026-10-13 T214) — spec FR-045, FR-046, SC-027, SC-028, research R14-35·R14-36,
 * contracts A18, ui-wireframes D19.
 *
 * - 더하기 한도는 **설정 값**이다(예금은 min(5, 설정)). 화면을 열 때마다 읽고, 읽지 못하면 기본 20과 알림이다 — 10이나 0으로 두면 알림 없이
 *   다른 한도가 걸린다(FR-045 실패 양상 *조용히 틀림*)
 * - 설정보다 대상이 많은 저장한 비교는 **자르지 않고** 모두 실행하고 알린다. 더하기만 막는다
 * - 비교 요청은 한 번에 **3개**, 진행 구독은 한 번에 **2개**, 확대 구간 요청은 한 번에 **3개**이고 나머지는 대상 차례로 기다린다 — 한꺼번에
 *   열면 구독이 같은 주소 연결 6개를 다 차지해 화면이 오류 없이 멈춘다(FR-046 실패 양상 *조용히 멈춤*). 늦게 연 구독도 이미 끝난 작업의 완료를
 *   받으면 그 대상을 다시 요청한다
 * - 차례 한도(`lib/concurrency`)는 순수하다 — 들어온 차례로 시작하고, 기다리는 중에 그만두면 줄에서 빠지며, 시작한 것을 그만두면 자리를 비운다
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { apiClient } from "@/lib/apiClient";
import { COMPARE_REQUESTS, COMPARE_STREAMS, DETAIL_REQUESTS, createLimiter } from "@/lib/concurrency";
import { DEFAULT_MAX_TARGETS, maxTargets, type CompareCondition } from "@/lib/compareCondition";
import { compareDetailLoader } from "@/lib/seriesDetail";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import type { StockTarget } from "@/lib/types";
import { limitNotices, targetLimit, useCompareStore } from "@/stores/compareStore";
import { useCompareRealEstatePicker } from "@/stores/compareRealEstatePicker";
import { SAMSUNG_T, collectingStock, ok, routeCompare } from "./support/compareFixtures";
import { compareSettingsStub } from "./support/compareSettingsStub";
import { local, SAMSUNG } from "./support/stockSearchFixtures";

const streams = vi.hoisted(() => ({
  stock: [] as { jobId: number; handlers: StockProgressHandlers; active: boolean }[],
  done: new Set<number>(),
  active: 0,
  most: 0,
}));
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (jobId: number, handlers: StockProgressHandlers) => {
    const sub = { jobId, handlers, active: true };
    streams.stock.push(sub);
    streams.active += 1;
    streams.most = Math.max(streams.most, streams.active);
    // 이미 끝난 작업에 늦게 붙으면 서버가 곧바로 `completed`를 보낸다(DB의 작업 상태 — research R14-36)
    if (streams.done.has(jobId)) queueMicrotask(() => { if (sub.active) handlers.onCompleted(); });
    return () => {
      if (sub.active) streams.active -= 1;
      sub.active = false;
    };
  },
}));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

beforeEach(() => {
  vi.restoreAllMocks();
  // 앞 테스트가 남긴 구독을 먼저 닫는다 — 닫힘이 셈을 줄이므로 센 값을 비우기 전에.
  useCompareStore.getState().dispose();
  streams.stock.length = 0;
  streams.done.clear();
  streams.active = 0;
  streams.most = 0;
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02", amount: "10000000" });
  useCompareRealEstatePicker.getState().dispose();
  useCompareRealEstatePicker.setState(useCompareRealEstatePicker.getInitialState(), true);
});

const stockN = (i: number): StockTarget => ({ ...SAMSUNG_T, symbol: `${String(i).padStart(6, "0")}.KS`, name: `종목${i}` });
const stocks = (count: number) => Array.from({ length: count }, (_, i) => stockN(i));
const store = () => useCompareStore.getState();
const keyOf = (t: StockTarget) => `${t.market}|${t.symbol}`;
const symbolOf = (path: string) => /symbol=([^&]+)/.exec(path)?.[1] ?? "";

function condition(targets: StockTarget[]): CompareCondition {
  return { v: 1, asset: "stock", method: "lump_sum", frequency: null, start: "2020-01-02", amount: "10000000",
    principalCurrency: "KRW", reinvest: true, targets };
}

describe("더하기 한도 = 설정", () => {
  it("설정을 읽기 전 한도는 기본 20이다 — 21번째는 더하지 않고 알린다", () => {
    expect(DEFAULT_MAX_TARGETS).toBe(20);
    for (const t of stocks(20)) expect(store().addTarget(t)).toBe(true);
    expect(store().addTarget(stockN(20))).toBe(false);
    expect(store().targets).toHaveLength(20);
    expect(store().notice).toBe("최대 20개까지 비교할 수 있습니다.");
  });

  it("읽은 설정만큼 더한다 — 알림 글자에 그 값이다", async () => {
    compareSettingsStub.set(30);
    await store().loadLimit();
    expect(store().limit).toBe(30);
    expect(targetLimit(store())).toBe(30);
    for (const t of stocks(30)) expect(store().addTarget(t)).toBe(true);
    expect(store().addTarget(stockN(30))).toBe(false);
    expect(store().notice).toBe("최대 30개까지 비교할 수 있습니다.");
  });

  it("100으로 정하면 100개까지다", async () => {
    compareSettingsStub.set(100);
    await store().loadLimit();
    for (const t of stocks(100)) store().addTarget(t);
    expect(store().targets).toHaveLength(100);
    expect(store().addTarget(stockN(100))).toBe(false);
    expect(store().notice).toBe("최대 100개까지 비교할 수 있습니다.");
  });

  it("예금은 min(5, 설정)이다", async () => {
    expect(maxTargets("deposit", 20)).toBe(5);
    expect(maxTargets("deposit", 3)).toBe(3);
    expect(maxTargets("stock", 3)).toBe(3);
    compareSettingsStub.set(3);
    await store().loadLimit();
    store().setAsset("deposit");
    for (const key of ["commercial_bank", "savings_bank", "credit_union", "mutual_finance"] as const) {
      store().addTarget({ institution: key });
    }
    expect(store().targets).toHaveLength(3);
    expect(store().notice).toBe("최대 3개까지 비교할 수 있습니다.");
  });

  it("설정을 읽지 못하면 기본 20으로 두고 알린다 — 다음에 읽으면 풀린다", async () => {
    compareSettingsStub.set(50);
    compareSettingsStub.fail("GET");
    await store().loadLimit();
    expect(store().limit).toBe(20);
    expect(store().limitStatus).toBe("error");
    expect(limitNotices(store())).toEqual(["투자 비교 설정을 읽지 못해 기본 20개로 제한합니다"]);
    compareSettingsStub.heal();
    await store().loadLimit();
    expect(store().limit).toBe(50);
    expect(limitNotices(store())).toEqual([]);
  });
});

describe("설정보다 많은 저장한 비교", () => {
  it("자르지 않고 모두 실행하고 알린다 — 더하기는 막히고 빼서 설정 이하면 풀린다", async () => {
    compareSettingsStub.set(10);
    await store().loadLimit();
    const get = routeCompare((path) => ok(symbolOf(path)));
    useCompareStore.setState({ saved: { ...store().saved, entries: [
      { id: 7, name: "30개", asset: "stock", condition: condition(stocks(30)), savedAt: "2026-10-13T00:00:00Z" }] } });
    await store().openSaved(7);
    expect(store().targets).toHaveLength(30);
    expect(get).toHaveBeenCalledTimes(30);
    expect(Object.values(store().run?.byTarget ?? {}).filter((s) => s.status === "ok")).toHaveLength(30);
    expect(limitNotices(store())).toEqual(
      ["이 비교의 대상 30개는 지금 설정(최대 10개)보다 많습니다 — 더 더할 수는 없고 실행·저장은 됩니다"]);
    expect(store().addTarget(stockN(99))).toBe(false);
    expect(store().targets).toHaveLength(30);
    for (const t of stocks(30).slice(10)) store().removeTarget(keyOf(t));
    expect(limitNotices(store())).toEqual([]);
    expect(store().addTarget(stockN(99))).toBe(false);
    store().removeTarget(keyOf(stockN(0)));
    expect(store().addTarget(stockN(99))).toBe(true);
  });
});

describe("비교 요청 — 한 번에 3개, 대상 차례", () => {
  it("대상 10개면 동시에 셋까지이고, 늦게 온 응답도 제 대상 자리에 채운다", async () => {
    expect(COMPARE_REQUESTS).toBe(3);
    const pending: { symbol: string; resolve: (v: unknown) => void }[] = [];
    let inFlight = 0;
    let most = 0;
    const calls: string[] = [];
    routeCompare((path) => {
      const symbol = symbolOf(path);
      calls.push(symbol);
      inFlight += 1;
      most = Math.max(most, inFlight);
      return new Promise((resolve) => {
        pending.push({ symbol, resolve: (v) => { inFlight -= 1; resolve(v); } });
      });
    });
    for (const t of stocks(10)) store().addTarget(t);
    const running = store().runComparison();
    await vi.waitFor(() => expect(pending).toHaveLength(3));
    expect(calls).toEqual(stocks(3).map((t) => t.symbol));
    // 차례를 거꾸로 답한다 — 셋째를 먼저
    pending[2].resolve(ok(pending[2].symbol));
    await vi.waitFor(() => expect(pending).toHaveLength(4));
    let answered = new Set([2]);
    while (answered.size < 10) {
      const next = pending.findIndex((_, i) => !answered.has(i));
      if (next === -1) {
        await vi.waitFor(() => expect(pending.length).toBeGreaterThan(answered.size));
        continue;
      }
      pending[next].resolve(ok(pending[next].symbol));
      answered = new Set([...answered, next]);
      await Promise.resolve();
    }
    await running;
    expect(most).toBe(3);
    expect(calls).toEqual(stocks(10).map((t) => t.symbol));
    for (const t of stocks(10)) {
      const state = store().run?.byTarget[keyOf(t)];
      expect(state?.status === "ok" && state.data.target).toBe(t.symbol);
    }
  });

  it("다시 실행하면 앞 실행의 기다리는 요청은 보내지 않는다", async () => {
    const pending: (() => void)[] = [];
    const calls: string[] = [];
    routeCompare((path) => {
      calls.push(`${path.includes("2021") ? "새" : "옛"}:${symbolOf(path)}`);
      return path.includes("2021") ? ok(symbolOf(path))
        : new Promise((resolve) => pending.push(() => resolve(ok(symbolOf(path)))));
    });
    for (const t of stocks(6)) store().addTarget(t);
    const first = store().runComparison();
    await vi.waitFor(() => expect(pending).toHaveLength(3));
    store().setStart("2021-01-04");
    const second = store().runComparison();
    for (const release of pending) release();
    await second;
    await first;
    expect(calls.filter((c) => c.startsWith("옛"))).toHaveLength(3);
    expect(calls.filter((c) => c.startsWith("새"))).toHaveLength(6);
    expect(Object.values(store().run?.byTarget ?? {}).every((s) => s.status === "ok")).toBe(true);
  });
});

describe("진행 구독 — 한 번에 2개", () => {
  it("수집 중 대상 다섯은 구독 둘씩이고, 끝나면 다음 차례가 구독한다", async () => {
    expect(COMPARE_STREAMS).toBe(2);
    const ready = new Set<string>();
    routeCompare((path) => {
      const symbol = symbolOf(path);
      return ready.has(symbol) ? ok(symbol) : collectingStock(100 + Number.parseInt(symbol, 10));
    });
    for (const t of stocks(5)) store().addTarget(t);
    await store().runComparison();
    await vi.waitFor(() => expect(streams.stock).toHaveLength(2));
    expect(streams.active).toBe(2);
    // 기다리는 대상은 "수집 중" 그대로다
    expect(store().run?.byTarget[keyOf(stockN(4))].status).toBe("collecting");
    for (let done = 0; done < 5; done += 1) {
      await vi.waitFor(() => expect(streams.stock.length).toBeGreaterThan(done));
      const sub = streams.stock[done];
      ready.add(stockN(sub.jobId - 100).symbol);
      sub.handlers.onCompleted();
      await vi.waitFor(() => expect(store().run?.byTarget[keyOf(stockN(sub.jobId - 100))].status).toBe("ok"));
    }
    expect(streams.most).toBe(2);
    expect(streams.stock.map((s) => s.jobId)).toEqual([100, 101, 102, 103, 104]);
    expect(Object.values(store().run?.byTarget ?? {}).every((s) => s.status === "ok")).toBe(true);
  });

  it("차례를 기다리는 동안 끝난 작업도 늦게 붙으면 완료를 받고 다시 요청한다", async () => {
    const ready = new Set<string>();
    routeCompare((path) => {
      const symbol = symbolOf(path);
      return ready.has(symbol) ? ok(symbol) : collectingStock(100 + Number.parseInt(symbol, 10));
    });
    for (const t of stocks(3)) store().addTarget(t);
    await store().runComparison();
    await vi.waitFor(() => expect(streams.stock).toHaveLength(2));
    // 셋째 작업은 기다리는 동안 끝났다
    streams.done.add(102);
    ready.add(stockN(2).symbol);
    ready.add(stockN(0).symbol);
    streams.stock[0].handlers.onCompleted();
    await vi.waitFor(() => expect(store().run?.byTarget[keyOf(stockN(2))].status).toBe("ok"));
    expect(streams.most).toBe(2);
  });

  it("다시 실행하면 기다리던 구독도 풀린다", async () => {
    routeCompare((path) => collectingStock(100 + Number.parseInt(symbolOf(path), 10)));
    for (const t of stocks(4)) store().addTarget(t);
    await store().runComparison();
    await vi.waitFor(() => expect(streams.stock).toHaveLength(2));
    routeCompare((path) => ok(symbolOf(path)));
    await store().runComparison();
    expect(streams.active).toBe(0);
    expect(streams.stock).toHaveLength(2);
  });
});

describe("확대 구간 요청 — 한 번에 3개", () => {
  it("대상 열의 구간을 셋씩 받는다", async () => {
    expect(DETAIL_REQUESTS).toBe(3);
    const pending: (() => void)[] = [];
    let inFlight = 0;
    let most = 0;
    vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
      inFlight += 1;
      most = Math.max(most, inFlight);
      return new Promise<unknown>((resolve) => pending.push(() => { inFlight -= 1; resolve(ok(symbolOf(path))); }));
    }) as typeof apiClient.get);
    const entries = stocks(10).map((t) => ({
      key: keyOf(t), path: `/api/comparison/stocks/simulation?symbol=${t.symbol}`, series: ok(t.symbol).series }));
    const load = compareDetailLoader(entries);
    const result = load?.({ from: "2021-01-04", to: "2021-03-31" });
    for (let n = 0; n < 10; n += 1) {
      await vi.waitFor(() => expect(pending.length).toBeGreaterThan(n));
      pending[n]();
    }
    const out = await result;
    expect(most).toBe(3);
    expect(Object.keys(out ?? {})).toHaveLength(10);
  });
});

describe("화면", () => {
  function route() {
    return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
      if (path.startsWith("/api/stocks/search/external")) return Promise.resolve({ query: "", results: [] });
      if (path.startsWith("/api/stocks/search")) return Promise.resolve(local([SAMSUNG]));
      return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
    }) as typeof apiClient.get);
  }

  it("열 때마다 설정을 읽어 칩의 한도와 안내에 쓴다", async () => {
    route();
    compareSettingsStub.set(40);
    store().addTarget(SAMSUNG_T);
    const { unmount } = render(<ComparePage />);
    expect(await screen.findByText("비교 대상 (1/40)")).toBeInTheDocument();
    expect(screen.getByText("ⓘ 최대 40개 · 2개 이상이어야 실행할 수 있습니다 · 설정에서 바꿀 수 있습니다")).toBeInTheDocument();
    unmount();
    compareSettingsStub.set(60);
    render(<ComparePage />);
    expect(await screen.findByText("비교 대상 (1/60)")).toBeInTheDocument();
    expect(compareSettingsStub.calls().filter((c) => c.method === "GET")).toHaveLength(2);
  });

  it("설정을 읽지 못하면 알림을 보이고 한도는 20이다", async () => {
    route();
    compareSettingsStub.fail("GET");
    render(<ComparePage />);
    expect(await screen.findByText("투자 비교 설정을 읽지 못해 기본 20개로 제한합니다")).toBeInTheDocument();
    expect(screen.getByText("비교 대상 (0/20)")).toBeInTheDocument();
  });

  it("설정보다 많은 대상이면 화면에 알린다", async () => {
    route();
    compareSettingsStub.set(2);
    for (const t of stocks(3)) useCompareStore.setState((s) => ({ targets: [...s.targets, t] }));
    render(<ComparePage />);
    expect(await screen.findByText("이 비교의 대상 3개는 지금 설정(최대 2개)보다 많습니다 — 더 더할 수는 없고 실행·저장은 됩니다"))
      .toBeInTheDocument();
  });
});

describe("차례 한도(순수)", () => {
  it("들어온 차례로 한도만큼 시작하고, 끝나면 다음을 시작한다", async () => {
    const limiter = createLimiter(2);
    const started: number[] = [];
    const releases: (() => void)[] = [];
    for (let i = 0; i < 4; i += 1) {
      limiter.enter((release) => {
        started.push(i);
        releases.push(release);
      });
    }
    await Promise.resolve();
    expect(started).toEqual([0, 1]);
    releases[1]();
    expect(started).toEqual([0, 1, 2]);
    releases[1]();
    expect(started).toEqual([0, 1, 2]);
    releases[0]();
    expect(started).toEqual([0, 1, 2, 3]);
  });

  it("기다리는 중에 그만두면 줄에서 빠지고, 시작한 것을 그만두면 멈추고 자리를 비운다", async () => {
    const limiter = createLimiter(1);
    const started: string[] = [];
    const stopped: string[] = [];
    const enter = (name: string) => limiter.enter(() => {
      started.push(name);
      return () => stopped.push(name);
    });
    const a = enter("a");
    const b = enter("b");
    enter("c");
    await Promise.resolve();
    b();
    a();
    expect(stopped).toEqual(["a"]);
    expect(started).toEqual(["a", "c"]);
    a();
    expect(stopped).toEqual(["a"]);
  });

  it("run은 값과 실패를 그대로 넘기고 자리를 비운다", async () => {
    const limiter = createLimiter(1);
    await expect(limiter.run(async () => 7)).resolves.toBe(7);
    await expect(limiter.run(async () => { throw new Error("x"); })).rejects.toThrow("x");
    await expect(limiter.run(async () => "다음")).resolves.toBe("다음");
  });
});
