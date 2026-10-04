/**
 * 가상자산 화면의 환율 대기 (T036) — 007 FR-036, 006 FR-046·FR-047a와 같은 규칙.
 *
 * 일봉이 다 있어도 환율이 비면 202 `fx`다. 외환 수집 스트림을 구독하고 **끝나면 작업을 확인해** 성공이면 다시 요청하고, 실패면
 * 사유를 보이고 멈춘다 — 그대로 다시 요청하면 서버가 실패한 수집을 또 시작해 같은 실패가 끝없이 반복된다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { CollectionStreamHandlers } from "@/lib/collectionStream";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";
import { RESULT } from "./support/cryptoFixtures";

const fx = vi.hoisted(() => ({
  currency: null as string | null,
  handlers: null as CollectionStreamHandlers | null,
}));
vi.mock("@/lib/collectionStream", () => ({
  subscribeCollection: (currency: string, handlers: CollectionStreamHandlers) => {
    fx.currency = currency;
    fx.handlers = handlers;
    return () => undefined;
  },
}));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));

const WAITING_FX = {
  status: "collecting", coinId: BTC.coinId,
  fx: { currency: "USD", state: "queued", busyWith: null, missingFrom: "2026-10-03",
    missingThrough: "2026-10-03" },
};

const job = (status: string, lastError: string | null = null) => ({
  jobs: [{ jobId: 9, currency: "USD", status, rangeStart: "2026-10-03", rangeEnd: "2026-10-03",
    chunksTotal: 1, chunksDone: 1, startedAt: "", finishedAt: "", lastError }],
});

const snapshot = {
  generatedAt: "", callsToday: 1, currency: "USD" as const, targetFrom: "", targetTo: "",
  coveredFrom: null, coveredThrough: null, busyWith: null,
  activeJob: { jobId: 9 } as never,
};

beforeEach(() => {
  vi.restoreAllMocks();
  useCryptoStore.getState().dispose();
  fx.currency = null;
  fx.handlers = null;
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
    summary: null, collecting: null, error: null,
  });
});

describe("환율 대기", () => {
  it("환율 수집이 성공으로 끝나면 다시 요청한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
      if (path.startsWith("/api/fx/jobs")) return Promise.resolve(job("succeeded"));
      return get.mock.calls.filter(([p]) => String(p).startsWith("/api/crypto")).length === 1
        ? Promise.resolve(WAITING_FX) : Promise.resolve(RESULT);
    }) as typeof apiClient.get);
    await useCryptoStore.getState().run();
    expect(fx.currency).toBe("USD");
    expect(useCryptoStore.getState().collecting?.fx?.currency).toBe("USD");

    fx.handlers?.onSnapshot(snapshot);
    fx.handlers?.onIdle({ currency: "USD", callsToday: 1, busyWith: null });
    await vi.waitFor(() => expect(useCryptoStore.getState().summary).not.toBeNull());
  });

  it("환율 수집이 실패로 끝나면 사유를 보이고 다시 요청하지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(((path: string) =>
      path.startsWith("/api/fx/jobs")
        ? Promise.resolve(job("failed", "인증 키가 거절되었습니다."))
        : Promise.resolve(WAITING_FX)) as typeof apiClient.get);
    await useCryptoStore.getState().run();
    fx.handlers?.onSnapshot(snapshot);
    fx.handlers?.onIdle({ currency: "USD", callsToday: 1, busyWith: null });
    await vi.waitFor(() => expect(useCryptoStore.getState().error).toContain("USD 환율을 받지 못했습니다"));
    expect(useCryptoStore.getState().error).toContain("인증 키가 거절되었습니다.");
    const simulations = get.mock.calls.filter(([p]) => String(p).startsWith("/api/crypto"));
    expect(simulations).toHaveLength(1);
  });

  it("다른 통화를 기다리는 중이면 그 수집이 끝날 때 다시 요청한다", async () => {
    const waiting = { ...WAITING_FX, fx: { ...WAITING_FX.fx, state: "waiting", busyWith: "JPY" } };
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(waiting).mockResolvedValueOnce(RESULT);
    await useCryptoStore.getState().run();
    fx.handlers?.onIdle({ currency: "USD", callsToday: 1, busyWith: "JPY" });
    expect(get).toHaveBeenCalledTimes(1);
    fx.handlers?.onIdle({ currency: "USD", callsToday: 1, busyWith: null });
    await vi.waitFor(() => expect(useCryptoStore.getState().summary).not.toBeNull());
  });
});
