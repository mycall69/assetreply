/**
 * 부동산 화면 상태 — 지역·단지·평형 고르기 (T020) — 009 FR-002~FR-004, FR-011, FR-014, FR-015, SC-007, ui-wireframes E2·E9.
 *
 * 예금 화면(`depositStore`)을 본뜬다. 고르는 순서는 시·도 → 시·군·구 → 동 → 단지 → 평형이고, **고를 때마다 그다음 목록을 요청한다.**
 * 목록이 아직 없으면 서버가 202를 준다 — 진행을 구독하고, 끝나면 **같은 목록을 다시 요청**한다(부분 목록을 먼저 보이지 않는다).
 * 실패하면 종류와 사유를 들고 있다 — 화면이 종류마다 다른 말을 한다(FR-014·FR-015).
 *
 * ## 이 테스트가 전제하는 모듈 (T026이 따른다)
 *
 * `@/lib/realEstateProgressStream`
 * - `subscribeRealEstateProgress(jobId: number, handlers: RealEstateProgressHandlers): () => void` — `/api/realestate/progress?jobId=`
 * - `RealEstateProgressSnapshot { jobId: number; kind: "region" | "complex_details" | "trade"; target: string; status: string;
 *   done: number; total: number }`
 * - `RealEstateProgressHandlers { onSnapshot(s); onCompleted(); onFailed(kind: RealEstateFailureKind | null, reason: string) }`
 *
 * `@/stores/realEstateStore` — `useRealEstateStore`
 * - 상태: `regions { sido, sgg, umd }`(각 `RealEstateRegion[] | null` — 받기 전 `null`), `selection { sido, sgg, umd: string | null;
 *   complexId: number | null; area: RealEstateAreaKey | null }`, `regionCollecting`(행정구역 202 본문), `regionProgress`,
 *   `regionFailure: RealEstateFailure | null`, `complexes: RealEstateComplexesResponse | null`, `tradeProgress`, `detailsProgress`,
 *   `areas: RealEstateAreasResponse | null`, `areasCollecting: RealEstateTradeCollecting | null`, `summary`·`rows`(결과 — Phase 4),
 *   `error: string | null`
 * - 동작: `loadSidos()`, `selectSido(code)`, `selectSgg(code)`, `selectUmd(code)`, `selectComplex(complexId)`(모두 `Promise<void>`),
 *   `selectArea(key)`, `dispose()`
 * - 기본 정보 진행의 작업 번호는 응답의 `details.progressUrl`(`…?jobId=11`)에만 있다 — 거기서 읽는다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/apiClient";
import type { RealEstateProgressHandlers } from "@/lib/realEstateProgressStream";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  AREAS_COLLECTING,
  GARAK,
  GARAK_COMPLEXES,
  GARAK_FIRST,
  GYEONGGI,
  GYEONGGI_SGGS,
  HELIO_AREAS,
  HELIO_ID,
  HYUNJIN,
  REGION_COLLECTING,
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

// jsdom에는 `EventSource`가 없다. 구독은 `realEstateProgressStream`의 책임이고, 여기서 보려는 것은 **언제 구독하고 끝나면 무엇을
// 다시 요청하는가**다. 행정구역·기본 정보·실거래가 서로 다른 작업이라 구독을 작업 번호별로 들고 있는다.
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

/** 그 작업을 지금 구독하고 있는가. */
const subscribed = (jobId: number) => progress.subs.some((s) => s.jobId === jobId && s.active);
/** 그 작업의 사건을 살아 있는 구독에 보낸다 — 끊은 구독은 받지 않는다(실제 `EventSource.close()`와 같다). */
function fire(jobId: number, event: (h: RealEstateProgressHandlers) => void): void {
  for (const s of progress.subs.filter((x) => x.jobId === jobId && x.active)) event(s.handlers);
}

type Get = { mock: { calls: unknown[][] } };
/** 그 경로(질의 앞부분)로 나간 요청들. */
const calls = (get: Get, base: string) =>
  get.mock.calls.map(([p]) => String(p)).filter((p) => splitPath(p).base === base);

const REGIONS = "/api/realestate/regions";
const COMPLEXES = "/api/realestate/complexes";
const AREAS = `/api/realestate/complexes/${HELIO_ID}/areas`;

/** 같은 경로의 응답을 차례로 준다. 나머지는 모두 받아 둔 상태의 응답이다. */
function sequence(base: string, ...answers: unknown[]): Get {
  const queue = [...answers];
  return routeRealEstate((path) => {
    if (splitPath(path).base === base && queue.length > 0) return queue.shift();
    return realEstateRoutes(path);
  });
}

const state = () => useRealEstateStore.getState();

beforeEach(() => {
  vi.restoreAllMocks();
  resetRealEstateStore();
  progress.subs = [];
});

describe("행정구역", () => {
  it("화면을 열면 상위 코드 없이 시·도를 요청한다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await state().loadSidos();
    const sent = calls(get, REGIONS);
    expect(sent).toHaveLength(1);
    expect(splitPath(sent[0]).params.get("parent") ?? "").toBe("");
    expect(state().regions.sido).toEqual(SIDOS.items);
    expect(state().regionCollecting).toBeNull();
    expect(progress.subs).toEqual([]);
  });

  it("처음이라 202면 목록 없이 진행을 구독하고, 끝나면 다시 요청해 시·도를 채운다", async () => {
    const get = sequence(REGIONS, REGION_COLLECTING);
    await state().loadSidos();
    expect(state().regionCollecting).toEqual(REGION_COLLECTING);
    expect(state().regions.sido).toBeNull();
    await vi.waitFor(() => expect(subscribed(7)).toBe(true));

    fire(7, (h) => h.onSnapshot({ jobId: 7, kind: "region", target: "regions", status: "running", done: 3, total: 21 }));
    expect(state().regionProgress?.done).toBe(3);
    expect(state().regionProgress?.total).toBe(21);

    fire(7, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().regions.sido).toEqual(SIDOS.items));
    expect(calls(get, REGIONS)).toHaveLength(2);
    expect(state().regionCollecting).toBeNull();
    expect(state().regionProgress).toBeNull();
  });

  it("그 수집이 실패하면 종류와 사유를 들고 있고 다시 요청하지 않는다(FR-015)", async () => {
    const get = sequence(REGIONS, REGION_COLLECTING);
    await state().loadSidos();
    await vi.waitFor(() => expect(subscribed(7)).toBe(true));
    fire(7, (h) => h.onFailed("auth", "인증키 오류"));
    expect(state().regionFailure).toEqual({ kind: "auth", reason: "인증키 오류" });
    expect(state().regionCollecting).toBeNull();
    expect(state().regions.sido).toBeNull();
    await new Promise((r) => setTimeout(r, 0));
    expect(calls(get, REGIONS)).toHaveLength(1);
  });

  it("실패 뒤 화면을 다시 열면 새 작업을 따라가고 경고를 지운다", async () => {
    sequence(REGIONS, REGION_COLLECTING, { ...REGION_COLLECTING, jobId: 8,
      progressUrl: "/api/realestate/progress?jobId=8" });
    await state().loadSidos();
    await vi.waitFor(() => expect(subscribed(7)).toBe(true));
    fire(7, (h) => h.onFailed("network", "연결 끊김"));
    await state().loadSidos();
    expect(state().regionFailure).toBeNull();
    expect(state().regionCollecting?.jobId).toBe(8);
    await vi.waitFor(() => expect(subscribed(8)).toBe(true));
  });

  it("시·도를 고르면 그 코드를 상위로 시·군·구를 요청한다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await state().selectSido(SEOUL);
    const sent = calls(get, REGIONS);
    expect(sent).toHaveLength(1);
    expect(splitPath(sent[0]).params.get("parent")).toBe(SEOUL);
    expect(state().selection.sido).toBe(SEOUL);
    expect(state().regions.sgg).toEqual(SEOUL_SGGS.items);
  });

  it("시·군·구를 고르면 그 코드를 상위로 동을 요청한다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await state().selectSido(SEOUL);
    await state().selectSgg(SONGPA);
    expect(splitPath(calls(get, REGIONS)[1]).params.get("parent")).toBe(SONGPA);
    expect(state().selection).toMatchObject({ sido: SEOUL, sgg: SONGPA });
    expect(state().regions.umd).toEqual(SONGPA_UMDS.items);
  });

  it("늦게 온 이전 시·도의 응답이 새로 고른 시·도의 하위를 덮지 않는다(SC-007)", async () => {
    // 송파구의 동 목록이 오기 전에 경기도로 바꿨다. 늦게 온 송파구의 동이 경기도 아래에 들어가면 상위를 바꾼 뒤 하위가 남는다.
    let releaseSongpa: (body: unknown) => void = () => undefined;
    const songpaPending = new Promise((resolve) => {
      releaseSongpa = resolve;
    });
    routeRealEstate((path) => {
      const { base, params } = splitPath(path);
      if (base === REGIONS && params.get("parent") === SONGPA) return songpaPending;
      return realEstateRoutes(path);
    });
    await state().selectSido(SEOUL);
    const songpa = state().selectSgg(SONGPA);
    await state().selectSido(GYEONGGI);
    releaseSongpa(SONGPA_UMDS);
    await songpa;
    expect(state().selection).toMatchObject({ sido: GYEONGGI, sgg: null, umd: null });
    expect(state().regions.sgg).toEqual(GYEONGGI_SGGS.items);
    expect(state().regions.umd).toBeNull();
  });
});

describe("단지 목록", () => {
  async function toSongpa() {
    await state().selectSido(SEOUL);
    await state().selectSgg(SONGPA);
  }

  it("동을 고르면 그 동의 단지 목록을 요청한다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await toSongpa();
    await state().selectUmd(GARAK);
    const sent = calls(get, COMPLEXES);
    expect(sent).toHaveLength(1);
    expect(splitPath(sent[0]).params.get("umd")).toBe(GARAK);
    expect(state().selection.umd).toBe(GARAK);
    expect(state().complexes).toEqual(GARAK_COMPLEXES);
    // 다 받아 둔 동이다 — 구독할 작업이 없다.
    expect(progress.subs).toEqual([]);
  });

  it("실거래를 받는 중이면 그 작업을 구독하고, 끝나면 단지 목록을 다시 요청한다 — 실거래에만 있던 단지가 더해진다", async () => {
    const withTrades = complexesWith({ items: [...GARAK_FIRST.items, HYUNJIN] });
    const get = sequence(COMPLEXES, { ...GARAK_FIRST, details: { pending: false, progressUrl: null } }, withTrades);
    await toSongpa();
    await state().selectUmd(GARAK);
    expect(state().complexes?.trades.state).toBe("collecting");
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));

    fire(9, (h) => h.onSnapshot({ jobId: 9, kind: "trade", target: "11710", status: "running", done: 130, total: 250 }));
    expect(state().tradeProgress?.done).toBe(130);

    fire(9, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().complexes?.items).toContainEqual(HYUNJIN));
    expect(calls(get, COMPLEXES)).toHaveLength(2);
    expect(state().tradeProgress).toBeNull();
  });

  it("기본 정보를 채우는 중이면 progressUrl의 작업을 구독하고, 끝나면 다시 요청해 세대수를 붙인다", async () => {
    const get = sequence(COMPLEXES, GARAK_FIRST, GARAK_COMPLEXES);
    await toSongpa();
    await state().selectUmd(GARAK);
    await vi.waitFor(() => expect(subscribed(11)).toBe(true));

    fire(11, (h) => h.onSnapshot({ jobId: 11, kind: "complex_details", target: GARAK, status: "running",
      done: 12, total: 47 }));
    expect(state().detailsProgress?.done).toBe(12);
    expect(state().detailsProgress?.total).toBe(47);

    fire(11, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().complexes?.items[0].households).toBe(9510));
    expect(calls(get, COMPLEXES)).toHaveLength(2);
    expect(state().detailsProgress).toBeNull();
  });

  it("실거래 수집이 실패하면 실거래 상태가 실패와 종류를 가진다 — 단지는 그대로 둔다(FR-014)", async () => {
    // 서버에 다시 물어도 같은 실패를 준다 — 로컬로 표시하든 다시 받든 결과가 같아야 한다.
    sequence(COMPLEXES, GARAK_FIRST, complexesWith({ items: GARAK_FIRST.items, trades: failedTrades("rate_limited") }));
    await toSongpa();
    await state().selectUmd(GARAK);
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    fire(9, (h) => h.onFailed("rate_limited", "하루 한도"));
    await vi.waitFor(() => expect(state().complexes?.trades.state).toBe("failed"));
    expect(state().complexes?.trades.failure?.kind).toBe("rate_limited");
    expect(state().complexes?.items.length).toBeGreaterThan(0);
    expect(state().tradeProgress).toBeNull();
  });

  it("상위를 바꾸면 이전 동의 진행이 끝나도 단지 목록을 다시 요청하지 않는다", async () => {
    const get = sequence(COMPLEXES, GARAK_FIRST);
    await toSongpa();
    await state().selectUmd(GARAK);
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));
    await state().selectSido(GYEONGGI);
    fire(9, (h) => h.onCompleted());
    fire(11, (h) => h.onCompleted());
    await new Promise((r) => setTimeout(r, 0));
    expect(calls(get, COMPLEXES)).toHaveLength(1);
    expect(state().complexes).toBeNull();
  });

  it("모르는 동이면 서버의 사유를 보인다", async () => {
    routeRealEstate((path) => splitPath(path).base === COMPLEXES
      ? new ApiError(400, "unknown_region", "모르는 법정동입니다.", { status: "unknown_region",
        message: "모르는 법정동입니다." })
      : realEstateRoutes(path));
    await toSongpa();
    await state().selectUmd(GARAK);
    expect(state().complexes).toBeNull();
    expect(state().error).toContain("모르는 법정동입니다.");
  });
});

describe("평형", () => {
  async function toGarak() {
    await state().selectSido(SEOUL);
    await state().selectSgg(SONGPA);
    await state().selectUmd(GARAK);
  }

  it("단지를 고르면 그 단지의 평형 구분을 요청한다", async () => {
    const get = routeRealEstate(realEstateRoutes);
    await toGarak();
    await state().selectComplex(HELIO_ID);
    expect(calls(get, AREAS)).toHaveLength(1);
    expect(state().selection.complexId).toBe(HELIO_ID);
    expect(state().areas).toEqual(HELIO_AREAS);
    expect(state().areasCollecting).toBeNull();
  });

  it("실거래를 받기 전이라 202면 평형 없이 진행을 구독하고, 끝나면 다시 요청한다", async () => {
    const get = sequence(AREAS, AREAS_COLLECTING);
    await toGarak();
    await state().selectComplex(HELIO_ID);
    expect(state().areas).toBeNull();
    expect(state().areasCollecting).toEqual(AREAS_COLLECTING);
    await vi.waitFor(() => expect(subscribed(9)).toBe(true));

    fire(9, (h) => h.onCompleted());
    await vi.waitFor(() => expect(state().areas).toEqual(HELIO_AREAS));
    expect(calls(get, AREAS)).toHaveLength(2);
    expect(state().areasCollecting).toBeNull();
  });

  it("평형을 고르면 그 구분을 들고 있다", async () => {
    routeRealEstate(realEstateRoutes);
    await toGarak();
    await state().selectComplex(HELIO_ID);
    state().selectArea("30k");
    expect(state().selection.area).toBe("30k");
  });
});

describe("구독", () => {
  it("화면을 떠나면 진행 구독을 모두 끊는다", async () => {
    sequence(COMPLEXES, GARAK_FIRST);
    await state().selectSido(SEOUL);
    await state().selectSgg(SONGPA);
    await state().selectUmd(GARAK);
    await vi.waitFor(() => expect(subscribed(9) && subscribed(11)).toBe(true));
    state().dispose();
    expect(subscribed(9)).toBe(false);
    expect(subscribed(11)).toBe(false);
  });
});
