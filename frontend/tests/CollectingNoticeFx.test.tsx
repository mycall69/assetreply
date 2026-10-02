/**
 * 환율 수집 안내와 다시 요청 (T048) — 006 FR-043, FR-043a, FR-045, FR-046, ui-wireframes W4·W4a,
 * research R6-10.
 *
 * **다시 요청하는 쪽은 화면이다.** 서버에 대기열을 두면 화면을 떠난 뒤에도 수집이 시작되는데, 사용자는
 * 그것을 요청한 적이 없다. **둘 다 끝나기 전에는 결과를 그리지 않는다**(FR-045) — 주식만 끝난 시점의
 * 결과는 환율이 빠진 계산이다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  CollectingNotice,
  FxUnavailableNotice,
} from "@/components/stock/CollectingNotice";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { CollectionStreamHandlers } from "@/lib/collectionStream";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import type {
  FxNotAvailableBefore,
  SimulationCollecting,
  SimulationResponse,
} from "@/lib/types";
import { useStockStore } from "@/stores/stockStore";

const streams = vi.hoisted(() => ({
  fx: [] as { currency: string; handlers: CollectionStreamHandlers; closed: boolean }[],
  stock: [] as { jobId: number; handlers: StockProgressHandlers }[],
}));

vi.mock("@/lib/collectionStream", () => ({
  subscribeCollection: (currency: string, handlers: CollectionStreamHandlers) => {
    const entry = { currency, handlers, closed: false };
    streams.fx.push(entry);
    return () => { entry.closed = true; };
  },
}));

vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (jobId: number, handlers: StockProgressHandlers) => {
    streams.stock.push({ jobId, handlers });
    return () => undefined;
  },
}));

const FX_ONLY = (state: "queued" | "collecting" | "waiting",
  busyWith: "USD" | null = null): SimulationCollecting => ({
  status: "collecting", market: "TSE", symbol: "7203.T",
  fx: { currency: "JPY", state, busyWith, missingFrom: "2020-01-01",
    missingThrough: "2026-10-01" },
});

const BOTH: SimulationCollecting = {
  ...FX_ONLY("queued"), jobId: 31, missingFrom: "2020-01-01", missingThrough: "2026-10-01",
  progressUrl: "/api/stocks/progress?jobId=31",
};

const RESULT: SimulationResponse = {
  stock: { market: "TSE", symbol: "7203.T", name: "토요타", currency: "JPY" },
  condition: { start: "2020-01-01", principal: "1000000", principalCurrency: "KRW",
    reinvest: true, tradeFeeRate: "0", dividendTaxRate: "0" },
  summary: { principal: "1000000", profit: "0", returnRate: "0", asOf: "2026-10-01",
    isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

const latestFx = () => streams.fx[streams.fx.length - 1];
const idle = (busyWith: "USD" | null = null) =>
  latestFx().handlers.onIdle({ currency: "JPY", callsToday: 0, busyWith });
const snapshot = () => latestFx().handlers.onSnapshot({
  generatedAt: "", callsToday: 0, currency: "JPY", targetFrom: "1977-01-01",
  targetTo: "2026-10-01", coveredFrom: null, coveredThrough: null, busyWith: null,
  activeJob: { jobId: 5, rangeStart: "1977-01-01", chunksTotal: 4, chunksDone: 1 },
} as never);

function mockGet(...bodies: unknown[]) {
  const queue = [...bodies];
  return vi.spyOn(apiClient, "get").mockImplementation((() =>
    Promise.resolve(queue.length > 1 ? queue.shift() : queue[0])) as typeof apiClient.get);
}

beforeEach(() => {
  vi.restoreAllMocks();
  streams.fx.length = 0;
  streams.stock.length = 0;
  useStockStore.getState().dispose();
  useStockStore.setState({
    input: { stock: { market: "TSE", symbol: "7203.T", name: "토요타", currency: "JPY" },
      start: "2020-01-01", principal: "1000000", principalCurrency: "KRW", reinvest: true },
    summary: null, collecting: null, error: null, fxBlocked: null,
  });
});

describe("환율 줄 (W4)", () => {
  it.each([
    ["queued", null, /JPY 환율: 대기열에 넣었습니다/],
    ["collecting", null, /JPY 환율을 받고 있습니다/],
    ["waiting", "USD", /JPY 환율: USD 수집이 끝나면 시작합니다/],
  ] as const)("%s", (state, busyWith, text) => {
    render(<CollectingNotice collecting={FX_ONLY(state, busyWith)} stockName="토요타"
      progress={null} />);
    expect(screen.getByRole("status").textContent).toMatch(text);
  });

  it("주식 시세가 다 있으면 시세 진행을 보이지 않는다", () => {
    render(<CollectingNotice collecting={FX_ONLY("queued")} stockName="토요타" progress={null} />);
    expect(screen.queryByText(/시세를 받고 있습니다/)).toBeNull();
  });

  it("둘 다 받는 중이면 둘 다 끝나야 결과가 나온다고 말한다", () => {
    render(<CollectingNotice collecting={BOTH} stockName="토요타" progress={null} />);
    const text = screen.getByRole("status").textContent ?? "";
    expect(text).toContain("토요타의 시세를 받고 있습니다");
    expect(text).toMatch(/JPY 환율/);
    expect(text).toMatch(/둘 다 끝나면 결과가 표시됩니다/);
  });
});

describe("다시 요청", () => {
  it("waiting이면 수집 스트림을 구독하고 다른 통화가 끝나면 다시 요청한다", async () => {
    const get = mockGet(FX_ONLY("waiting", "USD"), RESULT);
    await useStockStore.getState().run();
    expect(useStockStore.getState().summary).toBeNull();
    expect(latestFx().currency).toBe("JPY");

    idle("USD");                                   // 아직 다른 통화가 돈다
    expect(get).toHaveBeenCalledTimes(1);
    idle(null);                                    // 끝났다
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });

  it("queued면 진행을 본 뒤 끝나면 다시 요청한다", async () => {
    const get = mockGet(FX_ONLY("queued"), RESULT);
    await useStockStore.getState().run();
    idle();                                        // 워커가 아직 시작하지 않았다
    expect(get).toHaveBeenCalledTimes(1);
    snapshot();
    idle();
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });

  it("연결하기 전에 끝났으면 두 번째 대기 신호에서 다시 요청한다", async () => {
    // 짧은 구간은 구독이 붙기 전에 끝난다. 진행을 못 봤다고 영원히 기다리면 안 된다.
    const get = mockGet(FX_ONLY("queued"), RESULT);
    await useStockStore.getState().run();
    idle();
    idle();
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });

  it("주식만 끝나도 환율이 남으면 결과를 그리지 않는다", async () => {
    // FR-045.
    mockGet(BOTH, FX_ONLY("collecting"));
    await useStockStore.getState().run();
    streams.stock[0].handlers.onCompleted();
    await vi.waitFor(() => expect(useStockStore.getState().collecting?.fx?.state)
      .toBe("collecting"));
    expect(useStockStore.getState().summary).toBeNull();
    expect(useStockStore.getState().rows).toEqual([]);
  });

  it("화면을 떠나면 구독을 끊는다", async () => {
    mockGet(FX_ONLY("waiting", "USD"));
    await useStockStore.getState().run();
    useStockStore.getState().dispose();
    expect(latestFx().closed).toBe(true);
  });

  it("다시 실행하면 이전 구독을 끊는다", async () => {
    mockGet(FX_ONLY("waiting", "USD"));
    await useStockStore.getState().run();
    const first = latestFx();
    await useStockStore.getState().run();
    expect(first.closed).toBe(true);
  });
});

const BEFORE_FIRST: FxNotAvailableBefore = {
  status: "fx_not_available_before", reason: "before_first_quote",
  message: "1971-01-04 이전의 JPY 환율은 출처에 없습니다.", currency: "JPY",
  availableFrom: "1971-01-04",
};
const BEFORE_PROBE: FxNotAvailableBefore = {
  status: "fx_not_available_before", reason: "before_probe_start",
  message: "JPY 환율 수집 범위가 2000-01-01부터로 설정되어 있습니다. 설정을 바꾸면 받을 수 있습니다.",
  currency: "JPY", availableFrom: "2000-01-01",
};

describe("수집으로 채울 수 없는 구간 (W4a)", () => {
  it("409를 받으면 사유를 들고 있는다", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(
      409, "fx_not_available_before", BEFORE_PROBE.message, { ...BEFORE_PROBE }));
    await useStockStore.getState().run();
    expect(useStockStore.getState().fxBlocked).toEqual(BEFORE_PROBE);
    // 같은 사유를 일반 오류로 한 번 더 말하지 않는다.
    expect(useStockStore.getState().error).toBeNull();
  });

  it("출처에 없으면 그 달로 옮기는 수단을 준다", () => {
    const onMove = vi.fn();
    render(<FxUnavailableNotice blocked={BEFORE_FIRST} onMove={onMove} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("1971-01-04 이전의 JPY 환율은 출처에 없습니다");
    expect(alert.textContent).toMatch(/1971-01 이후로 옮기세요/);
    expect(alert.textContent).not.toMatch(/설정/);
    fireEvent.click(screen.getByRole("button", { name: "1971-01로 옮기기" }));
    expect(onMove).toHaveBeenCalledWith("1971-01-04");
  });

  it("설정 밖이면 풀 수 있는 제약이라 할 일을 함께 말한다", () => {
    // 두 문구를 섞으면 설정으로 풀리는 제약이 영영 불가능한 것으로 읽힌다 (FR-043a).
    render(<FxUnavailableNotice blocked={BEFORE_PROBE} onMove={vi.fn()} />);
    const text = screen.getByRole("alert").textContent ?? "";
    expect(text).toContain("ECOS_PROBE_START_JPY");
    expect(text).not.toMatch(/출처에 없습니다/);
    expect(screen.getByRole("button", { name: "2000-01로 옮기기" })).toBeInTheDocument();
  });
});
