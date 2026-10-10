/**
 * 지표 화면 그래프 스토어 (014 T048) — FR-010, FR-011, FR-016, data-model 7.
 *
 * - 202(받는 중)면 진행을 구독하고, `completed`에 그래프를 다시 받는다 — 다 받아졌는데 화면이 그래프로 바뀌지 않으면 사용자가
 *   새로고침해야 한다(FR-016 실패 양상)
 * - 기간을 바꾸면 주소 바꾸기 콜백을 부르고 다시 받는다. 늦게 온 옛 기간 응답은 버린다
 *   (014 승인 2026-10-10 — 반복 2026-10-10b T111: 단위 `unit`·`setUnit` → 보는 기간 `range`·`setRange`)
 * - 장중(일·주) 본문은 출처가 실패해도 그래프 자리의 본문이다 — 받는 중(202)으로 읽지 않는다
 * - 없는 지표(404)는 `not_found`, 다시 시도는 POST, 닫으면 구독을 끊는다
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { IndicatorProgressHandlers } from "@/lib/dashboardProgressStream";
import type { IndicatorIntradayResponse, IndicatorSeriesResponse } from "@/lib/types";
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
    await useIndicatorSeriesStore.getState().open("sp500", "5y");
    const s = useIndicatorSeriesStore.getState();
    expect(s.status).toBe("ready");
    expect(s.series && "points" in s.series ? s.series.points : []).toHaveLength(4);
    expect(get).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/series?range=5y");
  });

  it("장중 실패 본문은 받는 중이 아니라 ready다", async () => {
    // 014 승인 2026-10-10 — 장중 본문에도 `status`가 있다(출처 실패). 202로 읽으면 진행을 구독하고 그래프 자리에 "받는 중"이 남는다
    const failed: IndicatorIntradayResponse = {
      indicator: seriesOf().indicator, range: "1d", intraday: true, status: "failed", fetchedAt: null,
      points: [], notes: [], failure: { reason: "rate_limited", message: "한도", retryAfterSeconds: null },
    };
    vi.spyOn(apiClient, "get").mockResolvedValue(failed);
    await useIndicatorSeriesStore.getState().open("sp500", "1d");
    expect(useIndicatorSeriesStore.getState().status).toBe("ready");
    expect(useIndicatorSeriesStore.getState().collecting).toBeNull();
    expect(progress.urls).toEqual([]);
  });

  it("202면 진행을 구독하고 completed에 다시 받아 ready", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(collectingOf()).mockResolvedValueOnce(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
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
    await useIndicatorSeriesStore.getState().open("vix", "1y");
    const s = useIndicatorSeriesStore.getState();
    expect(s.status).toBe("failed");
    expect(s.collecting?.failure?.kind).toBe("rate_limited");
    expect(progress.urls).toEqual([]);
  });

  it("404는 not_found", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(404, "unknown_indicator", "없는 지표입니다"));
    await useIndicatorSeriesStore.getState().open("kospii", "1y");
    expect(useIndicatorSeriesStore.getState().status).toBe("not_found");
  });

  it("그 밖의 실패는 error", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("down"));
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    expect(useIndicatorSeriesStore.getState().status).toBe("error");
  });
});

describe("기간", () => {
  it("기간을 바꾸면 주소 콜백을 부르고 다시 받는다(장중)", async () => {
    // 014 승인 2026-10-10(반복 2026-10-10c T132) — 월~모두 사이는 같은 본문이라 다시 받지 않는다(아래 "처음 보이는 범위").
    // 다시 받는 것은 장중 ↔ 일봉이다 — "모두" → "주"(장중)로 바꿨다
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    const replaceUrl = vi.fn();
    await useIndicatorSeriesStore.getState().setRange("5d", replaceUrl);
    expect(replaceUrl).toHaveBeenCalledWith("5d");
    expect(useIndicatorSeriesStore.getState().range).toBe("5d");
    expect(get).toHaveBeenLastCalledWith("/api/dashboard/indicators/sp500/series?range=5d");
  });

  it("늦게 온 옛 기간 응답은 버린다", async () => {
    let releaseOld: (v: IndicatorSeriesResponse) => void = () => undefined;
    const old = new Promise<IndicatorSeriesResponse>((r) => { releaseOld = r; });
    vi.spyOn(apiClient, "get").mockReturnValueOnce(old).mockResolvedValueOnce(seriesOf({ range: "5y" }));
    const first = useIndicatorSeriesStore.getState().open("sp500", "1y");
    await useIndicatorSeriesStore.getState().setRange("5y", vi.fn());
    releaseOld(seriesOf({ range: "1y" }));
    await first;
    expect(useIndicatorSeriesStore.getState().series?.range).toBe("5y");
  });
});

describe("처음 보이는 범위(반복 2026-10-10c T130)", () => {
  it("월~모두 사이 전환은 다시 받지 않고 기간·주소만 바꾼다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    const replaceUrl = vi.fn();
    for (const range of ["5y", "all", "1m"] as const) {
      await useIndicatorSeriesStore.getState().setRange(range, replaceUrl);
    }
    expect(get).toHaveBeenCalledTimes(1);
    expect(replaceUrl.mock.calls).toEqual([["5y"], ["all"], ["1m"]]);
    expect(useIndicatorSeriesStore.getState().range).toBe("1m");
    expect(useIndicatorSeriesStore.getState().status).toBe("ready");
  });

  it("장중 ↔ 일봉은 받는다", async () => {
    const intraday: IndicatorIntradayResponse = {
      indicator: seriesOf().indicator, range: "1d", intraday: true, status: "ok", fetchedAt: "2026-10-09T14:00:00Z",
      points: [], notes: [], failure: null, window: null,
    };
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) =>
      path.includes("range=1d") || path.includes("range=5d") ? intraday : seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    await useIndicatorSeriesStore.getState().setRange("1d", vi.fn());
    await useIndicatorSeriesStore.getState().setRange("5d", vi.fn());
    await useIndicatorSeriesStore.getState().setRange("1y", vi.fn());
    expect(get.mock.calls.map(([path]) => path)).toEqual([
      "/api/dashboard/indicators/sp500/series?range=1y",
      "/api/dashboard/indicators/sp500/series?range=1d",
      "/api/dashboard/indicators/sp500/series?range=5d",
      "/api/dashboard/indicators/sp500/series?range=1y",
    ]);
  });
});

describe("같은 요청 나누기(반복 2026-10-10c T138)", () => {
  it("받는 중인 같은 본문은 다시 부르지 않는다 — 닫았다 다시 열어도(개발 모드 이중 효과)", async () => {
    // T138 실측 — 모달을 열 때 일봉 전부(약 1MB)를 두 번 받아 그래프가 1.1초에야 그려졌다
    let release: (v: IndicatorSeriesResponse) => void = () => undefined;
    const get = vi.spyOn(apiClient, "get").mockImplementation(
      () => new Promise((resolve) => { release = resolve as (v: IndicatorSeriesResponse) => void; }));
    const first = useIndicatorSeriesStore.getState().open("sp500", "1y");
    useIndicatorSeriesStore.getState().close();
    const second = useIndicatorSeriesStore.getState().open("sp500", "1y");
    release(seriesOf());
    await Promise.all([first, second]);
    expect(get).toHaveBeenCalledTimes(1);
    expect(useIndicatorSeriesStore.getState().status).toBe("ready");
  });

  it("다 받은 뒤에는 다시 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(seriesOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    useIndicatorSeriesStore.getState().close();
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    expect(get).toHaveBeenCalledTimes(2);
  });
});

describe("다시 시도와 닫기", () => {
  it("다시 시도는 POST하고 다시 받는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf());
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: "queued" });
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    await useIndicatorSeriesStore.getState().retryCollect();
    expect(post).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/collect", {});
  });

  it("닫으면 구독을 끊는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(collectingOf());
    await useIndicatorSeriesStore.getState().open("sp500", "1y");
    useIndicatorSeriesStore.getState().close();
    expect(progress.closed).toBe(1);
    expect(useIndicatorSeriesStore.getState().status).toBe("idle");
  });
});
