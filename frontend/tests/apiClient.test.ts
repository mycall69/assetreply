/**
 * API 클라이언트 요청 주소 테스트.
 *
 * 백엔드는 프론트엔드와 **다른 포트**에서 돈다(8080 vs 3030). 절대 URL로 직접 호출하면
 * 교차 출처가 되어 브라우저가 막는다. Next.js rewrite 프록시를 두고 **상대 경로**로
 * 요청해 동일 출처를 유지한다 — 그래서 여기서 검증하는 것은 "호스트를 붙이지 않는다"다.
 *
 * SSE(`EventSource`)는 CORS 설정이 훨씬 까다로워 프록시 방식의 이점이 더 크다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { subscribeProgress } from "@/lib/progressStream";

describe("API 요청 주소", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GET은 호스트 없이 상대 경로로 요청한다", async () => {
    await apiClient.get("/api/fx/coverage");
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toBe("/api/fx/coverage");
    expect(url).not.toMatch(/^https?:\/\//);
  });

  it("PUT도 상대 경로를 쓴다", async () => {
    await apiClient.put("/api/fx/spreads/USD", { cashBuy: "0.0018" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toBe("/api/fx/spreads/USD");
    expect(url).not.toMatch(/^https?:\/\//);
  });

  it("POST도 상대 경로를 쓴다", async () => {
    await apiClient.post("/api/fx/collect", { currency: "USD" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toBe("/api/fx/collect");
  });
});

describe("진행률 SSE 주소", () => {
  it("EventSource도 상대 경로로 연결한다", () => {
    const created: string[] = [];
    class FakeEventSource {
      constructor(url: string) { created.push(url); }
      addEventListener() {}
      close() {}
    }
    vi.stubGlobal("EventSource", FakeEventSource);

    const unsubscribe = subscribeProgress(7, { onProgress: vi.fn(), onCompleted: vi.fn() });
    unsubscribe();

    expect(created[0]).toBe("/api/fx/progress?jobId=7");
    expect(created[0]).not.toMatch(/^https?:\/\//);
    vi.unstubAllGlobals();
  });
});
