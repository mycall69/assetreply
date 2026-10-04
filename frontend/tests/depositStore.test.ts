/**
 * 예금 시뮬레이션 상태 (T016) — 008 FR-002~FR-007, FR-011, FR-016, ui-wireframes D2·D8.
 *
 * **부분 결과를 보여주지 않는다**(FR-011). 202면 결과를 비우고 진행(받은 달 / 받을 달)을 구독하고, 끝나면 다시 요청한다. 수집이
 * 실패하면 **종류마다 다른 말**로 할 일까지 보인다(FR-016) — 인증은 설정을 고치고, 한도는 기다리고, 형식은 고치고, 연결은 다시 한다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { DepositProgressHandlers } from "@/lib/depositProgressStream";
import type { DepositFailureKind } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { COLLECTING, RESULT } from "./support/depositFixtures";

const progress = vi.hoisted(() => ({
  jobId: null as number | null,
  handlers: null as DepositProgressHandlers | null,
  unsubscribe: vi.fn(),
}));
vi.mock("@/lib/depositProgressStream", () => ({
  subscribeDepositProgress: (jobId: number, handlers: DepositProgressHandlers) => {
    progress.jobId = jobId;
    progress.handlers = handlers;
    return progress.unsubscribe;
  },
}));

beforeEach(() => {
  vi.restoreAllMocks();
  useDepositStore.getState().dispose();
  progress.jobId = null;
  progress.handlers = null;
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" },
    rows: [], summary: null, collecting: null, progress: null, error: null, startable: null,
  });
});

describe("실행", () => {
  it("투자처·시작일·원금을 문자열 그대로 보낸다 — 통화는 보내지 않는다(원화만)", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(RESULT);
    await useDepositStore.getState().run();
    const path = get.mock.calls[0][0] as string;
    expect(path.startsWith("/api/deposit/simulation?")).toBe(true);
    expect(Object.fromEntries(new URLSearchParams(path.split("?")[1]))).toEqual({
      institution: "commercial_bank", start: "2020-01-15", principal: "10000000" });
    const state = useDepositStore.getState();
    expect(state.rows).toEqual(RESULT.rows);
    expect(state.summary?.profit).toBe("1557207");
    expect(state.condition?.interestTaxRate).toBe("0.154000");
  });

  it("원금이 비었으면 보내지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    useDepositStore.getState().setInput({ principal: "" });
    await useDepositStore.getState().run();
    expect(get).not.toHaveBeenCalled();
    expect(useDepositStore.getState().error).toContain("원금");
  });

  it("투자처를 바꾸면 결과를 지운다 — 이전 투자처의 결과가 새 이름 아래 남지 않는다(D2)", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(RESULT);
    await useDepositStore.getState().run();
    useDepositStore.getState().selectInstitution("saemaul");
    const state = useDepositStore.getState();
    expect(state.input.institution).toBe("saemaul");
    expect(state.summary).toBeNull();
    expect(state.rows).toEqual([]);
  });
});

describe("수집 중", () => {
  it("202면 결과 없이 진행을 구독하고, 끝나면 다시 요청한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValueOnce(COLLECTING)
      .mockResolvedValueOnce(RESULT);
    await useDepositStore.getState().run();
    expect(useDepositStore.getState().collecting).toEqual(COLLECTING);
    expect(useDepositStore.getState().summary).toBeNull();
    expect(progress.jobId).toBe(3);

    progress.handlers?.onSnapshot({ jobId: 3, status: "running", institution: "commercial_bank",
      monthsDone: 0, monthsTotal: 82, missingFrom: "2020-01", missingThrough: "2026-10" });
    expect(useDepositStore.getState().progress?.monthsTotal).toBe(82);

    progress.handlers?.onCompleted();
    await vi.waitFor(() => expect(useDepositStore.getState().summary).not.toBeNull());
    const simulations = get.mock.calls.filter(([p]) => String(p).startsWith("/api/deposit/simulation?"));
    expect(simulations).toHaveLength(2);
    expect(useDepositStore.getState().collecting).toBeNull();
  });

  it.each<[DepositFailureKind, string]>([
    ["auth", "인증키 설정을 확인하세요"],
    ["rate_limited", "잠시 뒤 다시 실행하세요"],
    ["format", "어댑터를 고쳐야 합니다"],
    ["network", "다시 실행하면 이어서 받습니다"],
  ])("수집이 실패하면 종류마다 할 일까지 말한다 — %s", async (kind, text) => {
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useDepositStore.getState().run();
    progress.handlers?.onFailed(kind, "출처가 준 사유");
    const state = useDepositStore.getState();
    expect(state.collecting).toBeNull();
    expect(state.error).toContain(text);
  });

  it("화면을 떠나면 구독을 끊는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useDepositStore.getState().run();
    useDepositStore.getState().dispose();
    expect(progress.unsubscribe).toHaveBeenCalled();
  });
});

describe("오류", () => {
  it("시작 가능 날짜보다 이르면 그 날짜를 들고 있고 시작일은 바꾸지 않는다(FR-006)", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(409, "before_first_month",
      "2012-01-01부터 금리가 있습니다.", { status: "before_first_month", startableFrom: "2012-01-01",
        message: "2012-01-01부터 금리가 있습니다." }));
    useDepositStore.getState().setInput({ start: "2010-01-01" });
    await useDepositStore.getState().run();
    const state = useDepositStore.getState();
    expect(state.startable?.startableFrom).toBe("2012-01-01");
    expect(state.input.start).toBe("2010-01-01");
  });

  it("시작 달이 결측이면 그 사실과 달을 보인다(FR-007)", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(409, "rate_missing",
      "2020-01 금리 통계가 비어 있어 가입할 수 없습니다.",
      { status: "rate_missing", month: "2020-01", message: "2020-01 금리 통계가 비어 있어 가입할 수 없습니다." }));
    await useDepositStore.getState().run();
    expect(useDepositStore.getState().error).toContain("2020-01");
  });
});
