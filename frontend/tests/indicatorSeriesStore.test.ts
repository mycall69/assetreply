/**
 * 지표 화면 그래프 스토어 (014 T048) — FR-010, FR-011, FR-016, data-model 7.
 *
 * - 202(받는 중)면 진행을 구독하고, `completed`에 그래프를 다시 받는다 — 다 받아졌는데 화면이 그래프로 바뀌지 않으면 사용자가
 *   새로고침해야 한다(FR-016 실패 양상)
 * - 단위를 바꾸면 주소 바꾸기 콜백을 부르고 다시 받는다. 늦게 온 옛 단위 응답은 버린다
 * - 없는 지표(404)는 `not_found`, 다시 시도는 POST, 닫으면 구독을 끊는다
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { IndicatorProgressHandlers } from "@/lib/dashboardProgressStream";
import type { IndicatorSeriesResponse } from "@/lib/types";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { collectingOf, seriesOf } from "./support/indicatorSeriesFixtures";

const progress = vi.hoisted(() => ({
  handlers: null as IndicatorProgressHandlers | null, urls: [] as string[], closed: 0,
}));
vi.mock("@/lib/dashboardProgressStream", () => ({
  subscribeIndicatorProgress: (url: string, handlers: IndicatorProgressHandlers) => {
    progress.handlers = handlers;
    progress.urls.push(url);
    return () => { progress.closed += 1; };
  },
}));

beforeEach(() => {
  progress.handlers = null;
  progress.urls = [];
  progress.closed = 0;
  useIndicatorSeriesStore.getState().close();
});

afterEach(() => {
  useIndicatorSeriesStore.getState().close();
  vi.restoreAllMocks();
});

describe("받기", () => {
  it("200이면 ready와 그래프", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "monthly");
    const s = useIndicatorSeriesStore.getState();
    expect(s.status).toBe("ready");
    expect(s.series?.points).toHaveLength(4);
    expect(get).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/series?unit=monthly");
  });

  it("202면 진행을 구독하고 completed에 다시 받아 ready", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(collectingOf()).mockResolvedValueOnce(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "daily");
    expect(useIndicatorSeriesStore.getState().status).toBe("collecting");
    expect(progress.urls).toEqual(["/api/dashboard/indicators/sp500/progress"]);
    progress.handlers?.onSnapshot({ firstDay: "1927-12-30", coveredFrom: "2000-01-03", coveredThrough: "2026-10-08", remainingDays: 26300 });
    expect(useIndicatorSeriesStore.getState().collecting?.progress?.coveredFrom).toBe("2000-01-03");
    progress.handlers?.onCompleted();
    await vi.waitFor(() => expect(useIndicatorSeriesStore.getState().status).toBe("ready"));
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("202 failed는 failed와 까닭", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf({
      status: "failed", failure: { kind: "rate_limited", message: "한도", at: "2026-10-09T05:00:00Z" } }));
    await useIndicatorSeriesStore.getState().open("vix", "daily");
    const s = useIndicatorSeriesStore.getState();
    expect(s.status).toBe("failed");
    expect(s.collecting?.failure?.kind).toBe("rate_limited");
    expect(progress.urls).toEqual([]);
  });

  it("404는 not_found", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(404, "unknown_indicator", "없는 지표입니다"));
    await useIndicatorSeriesStore.getState().open("kospii", "daily");
    expect(useIndicatorSeriesStore.getState().status).toBe("not_found");
  });

  it("그 밖의 실패는 error", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("down"));
    await useIndicatorSeriesStore.getState().open("sp500", "daily");
    expect(useIndicatorSeriesStore.getState().status).toBe("error");
  });
});

describe("단위", () => {
  it("단위를 바꾸면 주소 콜백을 부르고 다시 받는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "daily");
    const replaceUrl = vi.fn();
    await useIndicatorSeriesStore.getState().setUnit("yearly", replaceUrl);
    expect(replaceUrl).toHaveBeenCalledWith("yearly");
    expect(useIndicatorSeriesStore.getState().unit).toBe("yearly");
    expect(get).toHaveBeenLastCalledWith("/api/dashboard/indicators/sp500/series?unit=yearly");
  });

  it("늦게 온 옛 단위 응답은 버린다", async () => {
    let releaseOld: (v: IndicatorSeriesResponse) => void = () => undefined;
    const old = new Promise<IndicatorSeriesResponse>((r) => { releaseOld = r; });
    vi.spyOn(apiClient, "get").mockReturnValueOnce(old).mockResolvedValueOnce(seriesOf({ unit: "monthly" }));
    const first = useIndicatorSeriesStore.getState().open("sp500", "daily");
    await useIndicatorSeriesStore.getState().setUnit("monthly", vi.fn());
    releaseOld(seriesOf({ unit: "daily" }));
    await first;
    expect(useIndicatorSeriesStore.getState().series?.unit).toBe("monthly");
  });
});

describe("다시 시도와 닫기", () => {
  it("다시 시도는 POST하고 다시 받는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf());
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: "queued" });
    await useIndicatorSeriesStore.getState().open("sp500", "daily");
    await useIndicatorSeriesStore.getState().retryCollect();
    expect(post).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/collect", {});
  });

  it("닫으면 구독을 끊는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf());
    await useIndicatorSeriesStore.getState().open("sp500", "daily");
    useIndicatorSeriesStore.getState().close();
    expect(progress.closed).toBe(1);
    expect(useIndicatorSeriesStore.getState().status).toBe("idle");
  });
});
