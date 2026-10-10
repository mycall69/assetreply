/**
 * 일자별 표 스토어 (014 반복 2026-10-10b T108) — FR-016, FR-029, data-model §7.
 *
 * - 처음은 일 단위다. 단위를 바꾸면 처음부터 다시 받는다
 * - 더 받기는 `before = oldestReturned`이고 뒤에 붙인다
 * - 늦게 온 옛 응답은 버린다(`seq`). 202는 받는 중이다
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { IndicatorTableResponse } from "@/lib/types";
import { useIndicatorTableStore } from "@/stores/indicatorTableStore";
import { collectingOf } from "./support/indicatorSeriesFixtures";
import { rowOf, tableOf } from "./support/indicatorModalFixtures";

beforeEach(() => useIndicatorTableStore.getState().close());
afterEach(() => {
  useIndicatorTableStore.getState().close();
  vi.restoreAllMocks();
});

describe("열기·단위", () => {
  it("처음은 일 단위이고 단위를 바꾸면 처음부터다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(tableOf());
    await useIndicatorTableStore.getState().open("sp500");
    expect(get).toHaveBeenLastCalledWith("/api/dashboard/indicators/sp500/table?period=daily");
    expect(useIndicatorTableStore.getState().status).toBe("ready");
    get.mockResolvedValue(tableOf({ period: "weekly", rows: [rowOf("2026-10-09")] }));
    await useIndicatorTableStore.getState().setPeriod("weekly");
    expect(get).toHaveBeenLastCalledWith("/api/dashboard/indicators/sp500/table?period=weekly");
    expect(useIndicatorTableStore.getState().rows).toHaveLength(1);
  });

  it("단위를 바꾸는 동안 앞 표를 남긴다", async () => {
    // T124 실측(2026-10-10) — 단위를 누르면 표와 단위 단추가 함께 사라졌다가 다시 붙어 모달이 위아래로 흔들렸다
    let release: (v: IndicatorTableResponse) => void = () => undefined;
    vi.spyOn(apiClient, "get")
      .mockResolvedValueOnce(tableOf())
      .mockImplementationOnce(() => new Promise((resolve) => { release = resolve as (v: IndicatorTableResponse) => void; }));
    await useIndicatorTableStore.getState().open("sp500");
    const pending = useIndicatorTableStore.getState().setPeriod("weekly");
    const during = useIndicatorTableStore.getState();
    expect(during.status).toBe("loading");
    expect(during.period).toBe("weekly");
    expect(during.table?.period).toBe("daily");
    expect(during.rows.map((r) => r.date)).toEqual(["2026-10-09", "2026-10-08"]);
    release(tableOf({ period: "weekly", rows: [rowOf("2026-10-09", { isOngoing: true })] }));
    await pending;
    expect(useIndicatorTableStore.getState().status).toBe("ready");
    expect(useIndicatorTableStore.getState().rows).toHaveLength(1);
  });

  it("받는 중이면 collecting이다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf());
    await useIndicatorTableStore.getState().open("sp500");
    expect(useIndicatorTableStore.getState().status).toBe("collecting");
  });
});

describe("같은 요청 나누기(반복 2026-10-10c T138)", () => {
  it("받는 중인 같은 첫 쪽은 다시 부르지 않는다 — 닫았다 다시 열어도", async () => {
    let release: (v: IndicatorTableResponse) => void = () => undefined;
    const get = vi.spyOn(apiClient, "get").mockImplementation(
      () => new Promise((resolve) => { release = resolve as (v: IndicatorTableResponse) => void; }));
    const first = useIndicatorTableStore.getState().open("sp500");
    useIndicatorTableStore.getState().close();
    const second = useIndicatorTableStore.getState().open("sp500");
    release(tableOf());
    await Promise.all([first, second]);
    expect(get).toHaveBeenCalledTimes(1);
    expect(useIndicatorTableStore.getState().status).toBe("ready");
  });
});

describe("더 받기", () => {
  it("before = oldestReturned이고 뒤에 붙인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(tableOf({ hasMore: true, oldestReturned: "2026-10-08" }));
    await useIndicatorTableStore.getState().open("sp500");
    get.mockResolvedValueOnce(tableOf({ rows: [rowOf("2026-10-07")], hasMore: false, oldestReturned: "2026-10-07" }));
    await useIndicatorTableStore.getState().loadMore();
    expect(get).toHaveBeenLastCalledWith("/api/dashboard/indicators/sp500/table?period=daily&before=2026-10-08");
    expect(useIndicatorTableStore.getState().rows.map((r) => r.date)).toEqual(["2026-10-09", "2026-10-08", "2026-10-07"]);
    expect(useIndicatorTableStore.getState().hasMore).toBe(false);
  });

  it("늦게 온 옛 단위 응답은 버린다", async () => {
    let release: (v: IndicatorTableResponse) => void = () => undefined;
    vi.spyOn(apiClient, "get")
      .mockImplementationOnce(() => new Promise((resolve) => { release = resolve as (v: IndicatorTableResponse) => void; }))
      .mockResolvedValueOnce(tableOf({ period: "monthly", rows: [rowOf("2026-09-30")] }));
    const old = useIndicatorTableStore.getState().open("sp500");
    await useIndicatorTableStore.getState().setPeriod("monthly");
    release(tableOf());
    await old;
    expect(useIndicatorTableStore.getState().period).toBe("monthly");
    expect(useIndicatorTableStore.getState().rows.map((r) => r.date)).toEqual(["2026-09-30"]);
  });
});
