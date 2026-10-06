/**
 * 예금 스토어의 정기 적금 (011 T045) — FR-022, FR-023, FR-029~FR-031, FR-033, FR-034, research R11-9·R11-11.
 *
 * - 상품은 `product` 칸이다(기본 정기예금). `input`(투자처·시작일·금액)은 그대로다 — 적금이면 `input.principal`이 월 납입액이다
 * - 적금 `run()`은 `GET /api/deposit/installment-simulation?institution=…&start=…&amount=…`이고 결과는 `installment`에 들어간다(정기예금 칸은 빈다)
 * - 202는 `series`(적금 → 정기예금)마다 온다 — 진행을 구독하고 끝나면 다시 실행한다. 두 번째 202도 같다
 * - 상품을 바꾸면 결과를 비운다. 적금이 없는 투자처가 골라져 있으면 시중은행으로 바꾸고 그 사실을 알린다
 * - 이력 — 적금 항목은 `product`를 남기고, 다시 실행하면 상품을 맞춘다. 옛 항목은 정기예금이다. 비교 범례에 " · 정기 적금"을 붙인다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { DepositProgressHandlers } from "@/lib/depositProgressStream";
import type { DepositHistoryEntry, SimulationSeriesResponse } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { RESULT } from "./support/depositFixtures";
// 012 승인 2026-10-07 — 012부터 이력은 로컬 DB에 있다. 브라우저 lib 대신 이력 대역에서 읽는다(research R12-12).
import { historyStub } from "./support/historyStub";
import {
  DEPOSIT_COLLECTING,
  INSTALLMENT_COLLECTING,
  INSTALLMENT_INSTITUTIONS,
  INSTALLMENT_RESULT,
} from "./support/installmentFixtures";

const progress = vi.hoisted(() => ({
  jobId: null as number | null,
  handlers: null as DepositProgressHandlers | null,
  unsubscribe: vi.fn(),
}));
vi.mock("@/lib/depositProgressStream", () => ({
  subscribeDepositProgress: (jobId: number, handlers: DepositProgressHandlers) => {
    progress.jobId = jobId;
    progress.handlers = handlers;
    return progress.unsubscribe;
  },
}));

const QUERY = "institution=commercial_bank&start=2015-01-15&amount=1000000";
const SERIES: SimulationSeriesResponse = {
  from: "2015-01-15", to: "2018-01-15", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, priceKind: "installment_rate", priceCurrency: null,
  points: [{ date: "2018-01-15", balance: "37811149", returnRate: "0.021923", principal: "37000000", price: "1.82",
    depositRate: "1.93" }],
  gaps: [], provisionalFrom: null,
};

function mockGet() {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.startsWith("/api/deposit/installment-simulation/series")) return SERIES as never;
    if (path.startsWith("/api/deposit/installment-simulation")) return INSTALLMENT_RESULT as never;
    if (path.startsWith("/api/deposit/institutions")) return INSTALLMENT_INSTITUTIONS as never;
    if (path.startsWith("/api/deposit/simulation/series")) return SERIES as never;
    return RESULT as never;
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  useDepositStore.getState().dispose();
  progress.jobId = null;
  progress.handlers = null;
  localStorage.clear();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2015-01-15", principal: "1000000" },
    product: "deposit", installment: null, productNotice: null, institutions: INSTALLMENT_INSTITUTIONS.institutions,
    rows: [], summary: null, collecting: null, progress: null, error: null, startable: null, history: [],
    selectedHistory: [], comparison: [],
  });
});

describe("적금 실행", () => {
  it("기본 상품은 정기예금이다", () => {
    expect(useDepositStore.getInitialState().product).toBe("deposit");
  });

  it("적금이면 따로 된 경로를 정확한 질의로 부르고 결과는 installment에 들어간다", async () => {
    const get = mockGet();
    useDepositStore.getState().setProduct("installment");
    await useDepositStore.getState().run();
    expect(get).toHaveBeenNthCalledWith(1, `/api/deposit/installment-simulation?${QUERY}`);
    expect(get).toHaveBeenNthCalledWith(2, `/api/deposit/installment-simulation/series?${QUERY}`);
    const state = useDepositStore.getState();
    expect(state.installment?.summary).toEqual(INSTALLMENT_RESULT.summary);
    expect(state.installment?.rows).toEqual(INSTALLMENT_RESULT.rows);
    expect(state.installment?.contracts).toEqual(INSTALLMENT_RESULT.contracts);
    expect(state.installment?.series).toEqual(SERIES);
    expect(state.summary).toBeNull();
    expect(state.input).toEqual({ institution: "commercial_bank", start: "2015-01-15", principal: "1000000" });
  });

  it("202는 계열마다 오고 끝날 때마다 다시 실행한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.startsWith("/api/deposit/institutions")) return INSTALLMENT_INSTITUTIONS as never;
      if (path.includes("/series")) return SERIES as never;
      const calls = get.mock.calls.filter(([p]) => String(p).startsWith("/api/deposit/installment-simulation?"));
      if (calls.length === 1) return INSTALLMENT_COLLECTING as never;
      if (calls.length === 2) return DEPOSIT_COLLECTING as never;
      return INSTALLMENT_RESULT as never;
    });
    useDepositStore.getState().setProduct("installment");
    await useDepositStore.getState().run();
    expect(useDepositStore.getState().collecting?.series).toBe("installment");
    expect(progress.jobId).toBe(41);
    progress.handlers?.onCompleted();
    await vi.waitFor(() => expect(useDepositStore.getState().collecting?.series).toBe("deposit"));
    expect(progress.jobId).toBe(42);
    progress.handlers?.onCompleted();
    await vi.waitFor(() => expect(useDepositStore.getState().installment).not.toBeNull());
    expect(useDepositStore.getState().collecting).toBeNull();
    await vi.waitFor(() => expect(historyStub.entries("deposit")).toHaveLength(1)); // 012 승인 2026-10-07
  });

  it("상품을 바꾸면 두 결과를 모두 비운다", async () => {
    mockGet();
    useDepositStore.getState().setProduct("installment");
    await useDepositStore.getState().run();
    useDepositStore.getState().setProduct("deposit");
    expect(useDepositStore.getState().installment).toBeNull();
    await useDepositStore.getState().run();
    expect(useDepositStore.getState().summary).not.toBeNull();
    useDepositStore.getState().setProduct("installment");
    expect(useDepositStore.getState().summary).toBeNull();
  });

  it("적금이 없는 투자처가 골라져 있으면 시중은행으로 바꾸고 알린다", () => {
    useDepositStore.setState({ input: { institution: "savings_bank", start: "2015-01-15", principal: "1000000" } });
    useDepositStore.getState().setProduct("installment");
    const state = useDepositStore.getState();
    expect(state.input.institution).toBe("commercial_bank");
    expect(state.productNotice).toBe("저축은행은 적금이 없어 시중은행으로 바꿨습니다.");
    useDepositStore.getState().setProduct("deposit");
    expect(useDepositStore.getState().productNotice).toBeNull();
  });

  it("시작이 이르면 적금의 시작 가능 날짜를 들고 있다", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(409, "before_first_month", "이릅니다",
      { status: "before_first_month", startableFrom: "2011-01-01", message: "이릅니다" }));
    useDepositStore.getState().setProduct("installment");
    useDepositStore.getState().setInput({ start: "2010-12-15" });
    await useDepositStore.getState().run();
    expect(useDepositStore.getState().startable?.startableFrom).toBe("2011-01-01");
    expect(useDepositStore.getState().input.start).toBe("2010-12-15");
  });

  it("설정이 바뀐 뒤 다시 받기는 적금 결과에도 한다", async () => {
    const get = mockGet();
    useDepositStore.getState().setProduct("installment");
    await useDepositStore.getState().run();
    get.mockClear();
    await useDepositStore.getState().refreshIfRan();
    expect(get).toHaveBeenNthCalledWith(1, `/api/deposit/installment-simulation?${QUERY}`);
  });

  it("실행한 적금 조건을 상품과 함께 이력에 남긴다", async () => {
    mockGet();
    useDepositStore.getState().setProduct("installment");
    await useDepositStore.getState().run();
    // 012 승인 2026-10-07
    expect(historyStub.entries("deposit")[0]).toMatchObject({ product: "installment", principal: "1000000",
      institution: "commercial_bank" });
  });
});

describe("적금 이력", () => {
  const INSTALLMENT: DepositHistoryEntry = {
    id: "commercial_bank|2015-01-15|1000000|installment", institution: "commercial_bank", start: "2015-01-15",
    principal: "1000000", product: "installment", savedAt: "2026-10-05T00:00:00Z",
  };
  const OLD: DepositHistoryEntry = {
    id: "commercial_bank|2015-01-15|1000000", institution: "commercial_bank", start: "2015-01-15",
    principal: "1000000", savedAt: "2026-10-01T00:00:00Z",
  };

  it("적금 항목을 다시 실행하면 상품을 맞추고 적금 경로로 실행한다", async () => {
    const get = mockGet();
    useDepositStore.setState({ history: [INSTALLMENT] });
    await useDepositStore.getState().rerunHistory(INSTALLMENT.id);
    expect(useDepositStore.getState().product).toBe("installment");
    expect(get).toHaveBeenNthCalledWith(1, `/api/deposit/installment-simulation?${QUERY}`);
  });

  it("옛 항목은 정기예금으로 다시 실행한다", async () => {
    const get = mockGet();
    useDepositStore.setState({ history: [OLD], product: "installment" });
    await useDepositStore.getState().rerunHistory(OLD.id);
    expect(useDepositStore.getState().product).toBe("deposit");
    expect(get.mock.calls[0][0]).toMatch(/^\/api\/deposit\/simulation\?/);
  });

  it("비교는 적금 시계열 경로를 쓰고 범례에 상품을 붙인다", async () => {
    const get = mockGet();
    useDepositStore.setState({ history: [INSTALLMENT, OLD], selectedHistory: [INSTALLMENT.id, OLD.id] });
    await useDepositStore.getState().compareSelected();
    const paths = get.mock.calls.map((c) => c[0]);
    expect(paths).toContain(`/api/deposit/installment-simulation/series?${QUERY}`);
    expect(paths.some((p) => p.startsWith("/api/deposit/simulation/series?"))).toBe(true);
    expect(useDepositStore.getState().comparison.map((c) => c.label)).toEqual(["시중은행 · 정기 적금", "시중은행"]);
  });
});
