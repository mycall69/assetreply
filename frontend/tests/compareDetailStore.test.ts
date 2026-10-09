/**
 * 투자 시뮬레이션 모달의 상태 (013 반복 2026-10-09b T096) — FR-011b, FR-020, SC-011, data-model 5.3, research R13-19.
 *
 * - 열면 그 줄 조건의 **메뉴** 표 경로와 `/series`를 부른다 — 비교 경로에서 `/comparison`을 뺀 것과 글자까지 같다(일곱 방식)
 * - 202는 진행을 구독하지 않고 까닭과 다시 시도, 오류는 까닭. `/series`만 실패하면 표는 그대로다
 * - 주식·가상자산 단위 전환·이어 받기는 메뉴 스토어와 같은 질의(`period`·`before`), 늦은 응답은 버린다
 * - 이력을 쓰지 않는다(FR-020)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { comparisonPath } from "@/lib/compareApi";
import { COLLECTING_REASON, useCompareDetailStore, type DetailTarget } from "@/stores/compareDetailStore";
import { CASES, SERIES, STOCK_LUMP } from "./support/compareDetailFixtures";
import { apiError, routeCompare } from "./support/compareFixtures";
import { historyStub } from "./support/historyStub";

const store = () => useCompareDetailStore.getState();

const target = (c: (typeof CASES)[number]): DetailTarget => ({
  key: c.label, name: c.name, href: null, condition: c.condition, target: c.target });

beforeEach(() => {
  vi.restoreAllMocks();
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
});

describe("열기", () => {
  it.each(CASES.map((c) => [c.label, c]))("%s — 메뉴 표 경로와 /series를 그 줄의 조건으로 부른다", async (_label, c) => {
    const get = routeCompare((path) => (path.includes("/series") ? SERIES : c.menu));
    await store().openDetail(target(c));
    const paths = get.mock.calls.map(([p]) => p);
    const menu = comparisonPath(c.condition, c.target).replace("/api/comparison/", "/api/");
    expect(menu.startsWith(c.prefix)).toBe(true);
    expect(paths).toContain(menu);
    expect(paths).toContain(`${menu.split("?")[0]}/series?${menu.split("?")[1]}`);
    expect(paths.some((p) => p.includes("/api/comparison/"))).toBe(false);
    expect(store().status).toBe("ok");
    expect(store().menu).toEqual(c.menu);
    expect(store().series).toEqual(SERIES);
  });

  it("202면 진행을 구독하지 않고 까닭이고, 다시 시도하면 다시 부른다", async () => {
    let first = true;
    routeCompare((path) => {
      if (path.includes("/series")) return SERIES;
      const answer = first ? { status: "collecting", jobId: 3 } : STOCK_LUMP;
      first = false;
      return answer;
    });
    await store().openDetail(target(CASES[0]));
    expect([store().status, store().reason]).toEqual(["collecting", COLLECTING_REASON]);
    await store().retry();
    expect(store().status).toBe("ok");
  });

  it("오류는 까닭이다", async () => {
    routeCompare((path) => (path.includes("/series") ? SERIES : apiError(404, "unknown_stock")));
    await store().openDetail(target(CASES[0]));
    expect([store().status, store().reason]).toEqual(["failed", "unknown_stock 메시지"]);
  });

  it("/series만 실패하면 표는 그대로이고 차트 자리의 까닭이다", async () => {
    routeCompare((path) => (path.includes("/series") ? apiError(500, "internal") : STOCK_LUMP));
    await store().openDetail(target(CASES[0]));
    expect(store().status).toBe("ok");
    expect(store().menu).toEqual(STOCK_LUMP);
    expect(store().seriesError).toBe("internal 메시지");
  });
});

describe("일자별 표", () => {
  const menu = comparisonPath(CASES[0].condition, CASES[0].target).replace("/api/comparison/", "/api/");

  it("단위를 바꾸면 메뉴와 같은 period 질의로 표만 다시 받는다", async () => {
    const get = routeCompare((path) => (path.includes("/series") ? SERIES
      : path.includes("period=weekly") ? { ...STOCK_LUMP, rows: [{ date: "2021-08-27" }], hasMore: false } : STOCK_LUMP));
    await store().openDetail(target(CASES[0]));
    await store().setPeriod("weekly");
    expect(get.mock.calls.map(([p]) => p)).toContain(`${menu}&period=weekly`);
    expect(store().period).toBe("weekly");
    expect((store().menu as typeof STOCK_LUMP).rows).toEqual([{ date: "2021-08-27" }]);
    expect(store().series).toEqual(SERIES);
  });

  it("이어 받기는 before 커서로 이어 붙인다", async () => {
    const get = routeCompare((path) => (path.includes("/series") ? SERIES
      : path.includes("before=") ? { ...STOCK_LUMP, rows: [{ date: "2021-07-30" }], hasMore: false, oldestReturned: null }
        : STOCK_LUMP));
    await store().openDetail(target(CASES[0]));
    await store().loadMore();
    expect(get.mock.calls.map(([p]) => p)).toContain(`${menu}&before=2021-08-31`);
    expect((store().menu as typeof STOCK_LUMP).rows.map((r) => r.date)).toEqual(["2021-08-31", "2021-07-30"]);
    expect(store().menu && "hasMore" in store().menu! ? (store().menu as typeof STOCK_LUMP).hasMore : null).toBe(false);
  });

  it("이어 받기가 실패하면 받은 행은 그대로이고 까닭이다", async () => {
    routeCompare((path) => (path.includes("/series") ? SERIES : path.includes("before=") ? apiError(500, "internal") : STOCK_LUMP));
    await store().openDetail(target(CASES[0]));
    await store().loadMore();
    expect((store().menu as typeof STOCK_LUMP).rows).toEqual(STOCK_LUMP.rows);
    expect(store().loadMoreError).toBe("internal 메시지");
  });
});

describe("늦은 응답과 닫기", () => {
  it("다른 줄을 열면 앞 줄의 늦은 응답을 버린다", async () => {
    let release: (v: unknown) => void = () => undefined;
    const slow = new Promise((resolve) => {
      release = resolve;
    });
    routeCompare((path) => {
      if (path.includes("/series")) return SERIES;
      return path.startsWith("/api/stocks/") ? slow : CASES[4].menu;
    });
    const a = store().openDetail(target(CASES[0]));
    await store().openDetail(target(CASES[4]));
    release(STOCK_LUMP);
    await a;
    expect(store().open?.key).toBe(CASES[4].label);
    expect(store().menu).toEqual(CASES[4].menu);
  });

  it("닫으면 비운다 — 닫은 뒤 온 응답도 버린다", async () => {
    let release: (v: unknown) => void = () => undefined;
    routeCompare((path) => (path.includes("/series") ? SERIES : new Promise((resolve) => {
      release = resolve;
    })));
    const pending = store().openDetail(target(CASES[0]));
    store().close();
    release(STOCK_LUMP);
    await pending;
    expect([store().open, store().menu, store().status]).toEqual([null, null, "idle"]);
  });

  it("이력을 쓰지 않는다", async () => {
    routeCompare((path) => (path.includes("/series") ? SERIES : STOCK_LUMP));
    await store().openDetail(target(CASES[0]));
    await store().setPeriod("monthly");
    await store().loadMore();
    store().close();
    expect(historyStub.calls().filter((c) => c.method === "PUT")).toEqual([]);
  });
});
