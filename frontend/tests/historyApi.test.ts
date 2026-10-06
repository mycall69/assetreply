/**
 * 이력 경로 클라이언트 (012 T045) — contracts/rest-api.md 2~6, research R12-12.
 *
 * `apiClient`의 공통 요청 함수를 직접 쓴다 — 시뮬레이션 응답을 모의하는 `apiClient.get` 모의가 이력 요청을 가로채지 않는다. 오류 모양(`ApiError`)은 같다.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import {
  deleteHistory,
  fetchHistory,
  fetchRetention,
  importHistory,
  putHistory,
  saveRetention,
} from "@/lib/historyApi";

function capture(body: unknown = { entries: [], retentionDays: 30 }, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => vi.restoreAllMocks());

const call = (spy: ReturnType<typeof capture>, n = 0) => {
  const [url, init] = spy.mock.calls[n] as [string, RequestInit | undefined];
  return { url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : undefined };
};

describe("이력 경로", () => {
  it("목록", async () => {
    const spy = capture();
    await expect(fetchHistory("stock")).resolves.toEqual({ entries: [], retentionDays: 30 });
    expect(call(spy)).toEqual({ url: "/api/history/stock", method: "GET", body: undefined });
  });

  it("저장은 조건을 condition에 싣는다", async () => {
    const spy = capture();
    await putHistory("crypto", { start: "2024-01-15" });
    expect(call(spy)).toEqual({ url: "/api/history/crypto", method: "PUT", body: { condition: { start: "2024-01-15" } } });
  });

  it("삭제는 식별자를 질의로 인코딩한다", async () => {
    const spy = capture();
    await deleteHistory("stock", "KRX|005930.KS|2024-01-15|500000|KRW|R|recurring:monthly");
    expect(call(spy).url).toBe("/api/history/stock?id=KRX%7C005930.KS%7C2024-01-15%7C500000%7CKRW%7CR%7Crecurring%3Amonthly");
    expect(call(spy).method).toBe("DELETE");
  });

  it("옮기기", async () => {
    const spy = capture({ imported: 1, merged: 0, skipped: 0, entries: [], retentionDays: 30 });
    await expect(importHistory("deposit", [{ start: "2020-01-15" }])).resolves.toMatchObject({ imported: 1 });
    expect(call(spy)).toEqual({ url: "/api/history/deposit/import", method: "POST", body: { entries: [{ start: "2020-01-15" }] } });
  });

  it("보관 기간 읽기·저장 — 무기한은 null이다", async () => {
    const spy = capture({ retentionDays: null, isDefault: false, options: [7, 30, 90, 180, 365, null] });
    await fetchRetention();
    await saveRetention(null);
    expect(call(spy, 0)).toEqual({ url: "/api/history/settings", method: "GET", body: undefined });
    expect(call(spy, 1)).toEqual({ url: "/api/history/settings", method: "PUT", body: { retentionDays: null } });
  });

  it("실패는 ApiError다", async () => {
    capture({ status: "invalid_history", message: "principal" }, 422);
    await expect(putHistory("stock", {})).rejects.toBeInstanceOf(ApiError);
  });

  it("apiClient에 delete가 있다", async () => {
    const spy = capture({});
    await apiClient.delete("/api/history/stock?id=x");
    expect(call(spy).method).toBe("DELETE");
  });
});
