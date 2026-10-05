/**
 * 실패한 시·군·구에서 단지를 고르면 새 실거래 수집이 보인다 (T054 실측 결함) — 009 FR-011, FR-014, ui-wireframes E2·E9.
 *
 * 마지막 실거래 작업이 실패한 시·군·구(`complexes.trades.state = "failed"`, 예: 하루 한도)에서 단지를 고르면 `GET /areas`가 **202**를 준다 —
 * 서버가 **새 실거래 작업**을 시작했다. 고치기 전에는 평형 쪽 구독이 진행을 버리고 단지 목록의 실거래 상태가 `failed`로 남아, 수집이 이어지는
 * 내내 진행 줄이 없고 지난 실패 경고("하루 호출 한도에 닿았습니다")가 남았다 — 사용자는 아무것도 받지 않는다고 읽는다.
 *
 * 기대: 평형 202를 받으면 **단지 목록의 실거래 상태를 그 작업의 수집 중으로 바꾸고**(받은 달 / 받을 달, 실패 사유 없음) 실거래 진행 구독
 * 하나로 진행을 보인다. 끝나면 단지 목록과 평형을 다시 받는다. 새 작업도 실패하면 **그 작업의** 종류와 사유를 보인다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  AREAS_COLLECTING,
  GARAK,
  GARAK_COMPLEXES,
  HELIO_AREAS,
  HELIO_ID,
  SEOUL,
  SEOUL_SGGS,
  SIDOS,
  SONGPA,
  SONGPA_UMDS,
  complexesWith,
  failedTrades,
  realEstateRoutes,
  resetRealEstateStore,
  routeRealEstate,
  splitPath,
} from "./support/realEstateFixtures";

const progress = vi.hoisted(() => ({
  subs: [] as { jobId: number; handlers: RealEstateProgressHandlers; active: boolean }[],
}));
vi.mock("@/lib/realEstateProgressStream", () => ({
  subscribeRealEstateProgress: (jobId: number, handlers: RealEstateProgressHandlers) => {
    const sub = { jobId, handlers, active: true };
    progress.subs.push(sub);
    return () => {
      sub.active = false;
    };
  },
}));

const subscribed = (jobId: number) => progress.subs.some((s) => s.jobId === jobId && s.active);
const activeSubscriptions = (jobId: number) => progress.subs.filter((s) => s.jobId === jobId && s.active).length;
function fire(jobId: number, event: (h: RealEstateProgressHandlers) => void): void {
  for (const s of progress.subs.filter((x) => x.jobId === jobId && x.active)) event(s.handlers);
}

const COMPLEXES = "/api/realestate/complexes";
const AREAS = `/api/realestate/complexes/${HELIO_ID}/areas`;
/** 하루 한도로 실패한 뒤 단지를 고르자 서버가 시작한 새 작업. */
const RESUMED = { ...AREAS_COLLECTING, jobId: 15, monthsDone: 120, monthsTotal: 250,
  progressUrl: "/api/realestate/progress?jobId=15" };
const FAILED = complexesWith({ trades: failedTrades("rate_limited", "하루 한도") });

type Get = { mock: { calls: unknown[][] } };
const calls = (get: Get, base: string) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === base);

/** 단지 목록은 처음엔 실패 상태, 다시 받으면 다 받은 상태다. 평형은 처음엔 202, 다시 받으면 일곱 구분이다. */
function route(): Get {
  const complexes: unknown[] = [GARAK_COMPLEXES];
  const areas: unknown[] = [RESUMED, HELIO_AREAS];
  return routeRealEstate((path) => {
    const { base } = splitPath(path);
    if (base === COMPLEXES) return complexes.shift() ?? GARAK_COMPLEXES;
    if (base === AREAS) return areas.shift() ?? HELIO_AREAS;
    return realEstateRoutes(path);
  });
}

const state = () => useRealEstateStore.getState();

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
  progress.subs = [];
  // 송파구의 마지막 실거래 작업이 하루 한도로 실패했다 — 가락동 단지 목록이 그 사실을 들고 있다.
  useRealEstateStore.setState({
    regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
    selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: null, area: null },
    complexes: FAILED,
  });
});

describe("실패한 시·군·구에서 평형이 202", () => {
  it("단지 목록의 실거래 상태가 새 작업의 수집 중이 된다 — 지난 실패 사유는 지운다", async () => {
    route();
    await state().selectComplex(HELIO_ID);
    const trades = state().complexes?.trades;
    expect(trades?.state).toBe("collecting");
    expect(trades?.jobId).toBe(15);
    expect([trades?.monthsDone, trades?.monthsTotal]).toEqual([120, 250]);
    expect(trades?.failure).toBeNull();
    // 단지는 그대로 둔다.
    expect(state().complexes?.items).toEqual(FAILED.items);
    expect(state().areasCollecting).toEqual(RESUMED);
  });

  it("그 작업을 실거래 진행으로 한 번만 구독하고 진행을 들고 있다", async () => {
    route();
    await state().selectComplex(HELIO_ID);
    await vi.waitFor(() => expect(subscribed(15)).toBe(true));
    expect(activeSubscriptions(15)).toBe(1);
    fire(15, (h) => h.onSnapshot({ jobId: 15, kind: "trade", target: "11710", status: "running", done: 130, total: 250 }));
    expect(state().tradeProgress?.done).toBe(130);
    expect(state().tradeProgress?.total).toBe(250);
  });

  it("끝나면 단지 목록과 평형을 다시 받는다", async () => {
    const get = route();
    await state().selectComplex(HELIO_ID);
    await vi.waitFor(() => expect(subscribed(15)).toBe(true));
    fire(15, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().areas).toEqual(HELIO_AREAS));
    await vi.waitFor(() => expect(state().complexes?.trades.state).toBe("collected"));
    expect(calls(get, COMPLEXES)).toHaveLength(1);
    expect(calls(get, AREAS)).toHaveLength(2);
    expect(state().areasCollecting).toBeNull();
    expect(state().tradeProgress).toBeNull();
  });

  it("새 작업도 실패하면 그 작업의 종류와 사유를 보인다", async () => {
    route();
    await state().selectComplex(HELIO_ID);
    await vi.waitFor(() => expect(subscribed(15)).toBe(true));
    fire(15, (h) => h.onFailed("network", "연결 끊김"));
    await vi.waitFor(() => expect(state().complexes?.trades.state).toBe("failed"));
    expect(state().complexes?.trades.failure).toEqual({ kind: "network", reason: "연결 끊김" });
    expect(state().areasCollecting).toBeNull();
    expect(state().tradeProgress).toBeNull();
  });
});
