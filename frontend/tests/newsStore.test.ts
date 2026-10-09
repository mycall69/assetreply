/**
 * 대시보드 뉴스 스토어 (014 T069) — FR-024, data-model 7.
 *
 * - `loadAll`은 세 칸을 **동시에** 부르고, 온 것부터 그 칸의 상태를 바꾼다 — 가장 느린 출처가 다른 칸을 막지 않는다
 * - `retry(source)`는 그 칸만 다시 부른다
 * - 서버가 출처 실패를 200으로 실어 보내면 `failed`, 서버 요청 자체가 실패하면 `error`다
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { NewsListResponse, NewsSourceKey } from "@/lib/types";
import { initialColumns, useNewsStore } from "@/stores/newsStore";
import { failedOf, newsOf } from "./support/newsFixtures";

const newsCalls = (get: { mock: { calls: unknown[][] } }, source: NewsSourceKey) =>
  get.mock.calls.filter(([p]) => p === `/api/dashboard/news/${source}`).length;

beforeEach(() => {
  useNewsStore.setState({ columns: initialColumns() });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("loadAll", () => {
  it("세 칸을 동시에 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(() => new Promise(() => undefined));
    void useNewsStore.getState().loadAll();
    expect(newsCalls(get, "kr")).toBe(1);
    expect(newsCalls(get, "us")).toBe(1);
    expect(newsCalls(get, "jp")).toBe(1);
    const { columns } = useNewsStore.getState();
    expect([columns.kr.status, columns.us.status, columns.jp.status]).toEqual(["loading", "loading", "loading"]);
  });

  it("온 것부터 그 칸의 상태를 바꾼다", async () => {
    const resolvers: Partial<Record<NewsSourceKey, (v: NewsListResponse) => void>> = {};
    vi.spyOn(apiClient, "get").mockImplementation((path: string) => {
      const source = path.split("/").pop() as NewsSourceKey;
      return new Promise((resolve) => { resolvers[source] = resolve as (v: NewsListResponse) => void; });
    });
    const all = useNewsStore.getState().loadAll();
    resolvers.us?.(newsOf("us"));
    await vi.waitFor(() => expect(useNewsStore.getState().columns.us.status).toBe("ready"));
    expect(useNewsStore.getState().columns.kr.status).toBe("loading");
    expect(useNewsStore.getState().columns.us.list?.items).toHaveLength(10);
    resolvers.kr?.(newsOf("kr"));
    resolvers.jp?.(newsOf("jp"));
    await all;
    const { columns } = useNewsStore.getState();
    expect([columns.kr.status, columns.us.status, columns.jp.status]).toEqual(["ready", "ready", "ready"]);
  });

  it("출처 실패는 failed와 그 까닭이다 — 다른 칸은 그대로", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.endsWith("/us")) {
        return failedOf("us", { reason: "rate_limited", message: "요청을 제한했습니다(429).", retryAfterSeconds: 60 });
      }
      return newsOf(path.endsWith("/kr") ? "kr" : "jp");
    });
    await useNewsStore.getState().loadAll();
    const { columns } = useNewsStore.getState();
    expect(columns.us.status).toBe("failed");
    expect(columns.us.failure).toEqual({ reason: "rate_limited", message: "요청을 제한했습니다(429).", retryAfterSeconds: 60 });
    expect(columns.kr.status).toBe("ready");
    expect(columns.jp.status).toBe("ready");
  });

  it("서버 요청이 실패하면 error다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.endsWith("/jp")) throw new Error("down");
      return newsOf(path.endsWith("/kr") ? "kr" : "us");
    });
    await useNewsStore.getState().loadAll();
    const { columns } = useNewsStore.getState();
    expect(columns.jp.status).toBe("error");
    expect(columns.kr.status).toBe("ready");
  });
});

describe("retry", () => {
  it("그 칸만 다시 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.endsWith("/us")) {
        return failedOf("us", { reason: "connection", message: "연결하지 못했습니다.", retryAfterSeconds: 60 });
      }
      return newsOf(path.endsWith("/kr") ? "kr" : "jp");
    });
    await useNewsStore.getState().loadAll();
    get.mockImplementation(async () => newsOf("us"));
    await useNewsStore.getState().retry("us");
    expect(newsCalls(get, "us")).toBe(2);
    expect(newsCalls(get, "kr")).toBe(1);
    expect(newsCalls(get, "jp")).toBe(1);
    expect(useNewsStore.getState().columns.us.status).toBe("ready");
  });

  it("늦게 온 옛 응답은 버린다", async () => {
    let releaseOld: (v: NewsListResponse) => void = () => undefined;
    const get = vi.spyOn(apiClient, "get")
      .mockImplementationOnce(() => new Promise((resolve) => { releaseOld = resolve as (v: NewsListResponse) => void; }))
      .mockImplementationOnce(async () => newsOf("kr", { fetchedAt: "2026-10-09T13:40:00Z" }));
    const old = useNewsStore.getState().retry("kr");
    await useNewsStore.getState().retry("kr");
    releaseOld(newsOf("kr", { fetchedAt: "2026-10-09T13:00:00Z" }));
    await old;
    expect(get).toHaveBeenCalledTimes(2);
    expect(useNewsStore.getState().columns.kr.list?.fetchedAt).toBe("2026-10-09T13:40:00Z");
  });
});
