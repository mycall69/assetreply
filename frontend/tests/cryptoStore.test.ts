/**
 * 가상자산 시뮬레이션 상태 (T028) — 007 FR-013, FR-020, FR-008, ui-wireframes C7.
 *
 * **부분 결과를 보여주지 않는다**(FR-013). 202면 결과를 비우고 진행을 구독하고, 끝나면 다시 요청한다. 수집이 실패하면 **종류마다
 * 다른 말**로 사유를 보인다(FR-020) — 차단은 기다려도 풀리지 않고, 형식 변경은 고쳐야 하고, 네트워크는 다시 하면 된다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { CryptoProgressHandlers } from "@/lib/cryptoProgressStream";
import type { CryptoFailureKind } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";
import { RESULT } from "./support/cryptoFixtures";

const progress = vi.hoisted(() => ({
  jobId: null as number | null,
  handlers: null as CryptoProgressHandlers | null,
  unsubscribe: vi.fn(),
}));
vi.mock("@/lib/cryptoProgressStream", () => ({
  subscribeCryptoProgress: (jobId: number, handlers: CryptoProgressHandlers) => {
    progress.jobId = jobId;
    progress.handlers = handlers;
    return progress.unsubscribe;
  },
}));
vi.mock("@/lib/collectionStream", () => ({
  subscribeCollection: () => () => undefined,
}));

const COLLECTING = {
  status: "collecting", coinId: BTC.coinId, jobId: 8, missingFrom: "2020-01-01",
  missingThrough: "2021-12-31", progressUrl: "/api/crypto/progress?jobId=8",
};

beforeEach(() => {
  vi.restoreAllMocks();
  useCryptoStore.getState().dispose();
  progress.jobId = null;
  progress.handlers = null;
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
    rows: [], summary: null, collecting: null, error: null, startable: null,
  });
});

describe("실행", () => {
  it("코인 id와 조건을 문자열 그대로 보낸다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(RESULT);
    await useCryptoStore.getState().run();
    const path = get.mock.calls[0][0] as string;
    expect(path.startsWith("/api/crypto/simulation?")).toBe(true);
    const query = new URLSearchParams(path.split("?")[1]);
    expect(Object.fromEntries(query)).toEqual({
      coinId: String(BTC.coinId), start: "2020-01-15", principal: "10000",
      principalCurrency: "USD" });
    const state = useCryptoStore.getState();
    expect(state.rows).toEqual(RESULT.rows);
    expect(state.summary?.boughtOn).toBe("2020-01-01");
  });

  it("코인을 고르지 않았으면 보내지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    useCryptoStore.setState({ input: { ...useCryptoStore.getState().input, coin: null } });
    await useCryptoStore.getState().run();
    expect(get).not.toHaveBeenCalled();
    expect(useCryptoStore.getState().error).toContain("코인");
  });
});

describe("수집 중", () => {
  it("202면 결과 없이 진행을 구독하고, 끝나면 다시 요청한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(COLLECTING)
      .mockResolvedValueOnce(RESULT);
    await useCryptoStore.getState().run();
    expect(useCryptoStore.getState().collecting).toEqual(COLLECTING);
    expect(useCryptoStore.getState().summary).toBeNull();
    expect(progress.jobId).toBe(8);

    progress.handlers?.onSnapshot({ jobId: 8, status: "running", chunksDone: 1, chunksTotal: 2,
      daysDone: 730, daysTotal: 731, missingFrom: "2020-01-01", missingThrough: "2021-12-31" });
    expect(useCryptoStore.getState().progress?.daysDone).toBe(730);

    progress.handlers?.onCompleted();
    await vi.waitFor(() => expect(useCryptoStore.getState().summary).not.toBeNull());
    expect(get).toHaveBeenCalledTimes(2);
    expect(useCryptoStore.getState().collecting).toBeNull();
  });

  it.each<[CryptoFailureKind, string]>([
    ["blocked", "시세 출처가 접근을 막았습니다"],
    ["format", "응답 형식이 바뀌었습니다"],
    ["network", "시세 출처에 연결하지 못했습니다"],
    ["empty", "출처에 이 코인의 시세가 없습니다"],
  ])("수집이 실패하면 종류마다 다른 말로 알린다 — %s", async (kind, text) => {
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useCryptoStore.getState().run();
    progress.handlers?.onFailed(kind, "출처가 준 사유");
    const state = useCryptoStore.getState();
    expect(state.collecting).toBeNull();
    expect(state.error).toContain(text);
  });

  it("화면을 떠나면 구독을 끊는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useCryptoStore.getState().run();
    useCryptoStore.getState().dispose();
    expect(progress.unsubscribe).toHaveBeenCalled();
  });
});

describe("오류", () => {
  it("시작 가능 날짜로 거절되면 그 날짜를 들고 있고 시작일은 바꾸지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(400, "before_listing",
      "2010-07-18부터 시세가 있습니다.", { status: "before_listing", startableFrom: "2010-07-18",
        basis: "price_start", message: "2010-07-18부터 시세가 있습니다." }));
    useCryptoStore.getState().setInput({ start: "2009-01-01" });
    await useCryptoStore.getState().run();
    const state = useCryptoStore.getState();
    expect(state.startable?.startableFrom).toBe("2010-07-18");
    expect(state.input.start).toBe("2009-01-01");
  });

  it("모르는 코인이면 다시 고르라고 한다", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(404, "unknown_coin",
      "목록에서 찾을 수 없는 코인입니다.", { status: "unknown_coin", action: "reselect",
        message: "목록에서 찾을 수 없는 코인입니다." }));
    await useCryptoStore.getState().run();
    expect(useCryptoStore.getState().error).toContain("다시 고르세요");
  });
});
