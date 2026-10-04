/**
 * 확인 실패 뒤 자동 다시 요청 (T037) — 008 FR-016a, SC-014, ui-wireframes D8(반복 2026-10-04).
 *
 * 금리를 **받아 둔 투자처**(투자처 목록의 `firstMonth`가 있다)의 수집이 실패하면 화면이 곧바로 한 번 다시 요청한다 — 서버는 받아 둔
 * 금리로 계산해 200 + `recheckFailed`를 준다. 다시 요청하지 않으면 실패한 그 실행이 결과 없이 끝나 사용자는 계산할 수 없다고 읽는다.
 * **받은 적 없는 투자처는 다시 요청하지 않는다** — 같은 실패가 되풀이되며 출처 호출만 쓴다. 다시 요청은 한 실행에 한 번이다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { DepositProgressHandlers } from "@/lib/depositProgressStream";
import type { DepositFailureKind, DepositInstitution, DepositSimulationResponse } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { COLLECTING, INSTITUTIONS, RESULT } from "./support/depositFixtures";

const progress = vi.hoisted(() => ({ handlers: null as DepositProgressHandlers | null, subscribed: 0 }));
vi.mock("@/lib/depositProgressStream", () => ({
  subscribeDepositProgress: (_jobId: number, handlers: DepositProgressHandlers) => {
    progress.handlers = handlers;
    progress.subscribed += 1;
    return () => undefined;
  },
}));

const RECHECK_FAILED: DepositSimulationResponse = {
  ...RESULT,
  summary: { ...RESULT.summary, recheckFailed: { kind: "auth", reason: "인증키 오류" } },
};

/** 시중은행은 받아 둔 투자처, 저축은행은 받은 적 없는 투자처다(픽스처의 `firstMonth`). */
const LIST: DepositInstitution[] = INSTITUTIONS.institutions;

/** 호출 기록만 본다. */
type Get = { mock: { calls: unknown[][] } };
const simulations = (get: Get) =>
  get.mock.calls.filter(([p]) => String(p).startsWith("/api/deposit/simulation?"));

/** 시뮬레이션 응답을 차례로 준다. 시계열·목록은 늘 같은 값이다. */
function respond(...answers: unknown[]): Get {
  const queue = [...answers];
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path.startsWith("/api/deposit/simulation/series")) return { points: [], gaps: [] };
    if (path.startsWith("/api/deposit/institutions")) return INSTITUTIONS;
    return queue.shift();
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  progress.handlers = null;
  progress.subscribed = 0;
  useDepositStore.getState().dispose();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" },
    institutions: LIST,
    rows: [], summary: null, condition: null, collecting: null, progress: null, error: null, startable: null,
  });
});

describe("받아 둔 투자처", () => {
  it.each<DepositFailureKind>(["auth", "rate_limited", "format", "network"])(
    "실패(%s)하면 곧바로 한 번 다시 요청해 결과와 확인 실패를 보인다", async (kind) => {
      const get = respond(COLLECTING, RECHECK_FAILED);
      await useDepositStore.getState().run();
      progress.handlers?.onFailed(kind, "사유");
      await vi.waitFor(() => expect(useDepositStore.getState().summary).not.toBeNull());
      const state = useDepositStore.getState();
      expect(simulations(get)).toHaveLength(2);
      expect(simulations(get)[1][0]).toBe(simulations(get)[0][0]);
      expect(state.summary?.recheckFailed).toEqual({ kind: "auth", reason: "인증키 오류" });
      expect(state.error).toBeNull();
      expect(state.collecting).toBeNull();
    });

  it("다시 요청한 실행이 또 실패하면 더 요청하지 않는다 — 한 실행에 한 번", async () => {
    const get = respond(COLLECTING, COLLECTING);
    await useDepositStore.getState().run();
    progress.handlers?.onFailed("network", "사유");
    await vi.waitFor(() => expect(progress.subscribed).toBe(2));
    progress.handlers?.onFailed("network", "사유");
    await new Promise((r) => setTimeout(r, 0));
    expect(simulations(get)).toHaveLength(2);
    expect(useDepositStore.getState().error).toContain("다시 실행하면 이어서 받습니다");
  });

  it("사용자가 새로 실행하면 다시 한 번의 기회가 생긴다", async () => {
    const get = respond(COLLECTING, COLLECTING, COLLECTING, RECHECK_FAILED);
    await useDepositStore.getState().run();
    progress.handlers?.onFailed("network", "사유");
    await vi.waitFor(() => expect(progress.subscribed).toBe(2));
    progress.handlers?.onFailed("network", "사유");
    await useDepositStore.getState().run();
    progress.handlers?.onFailed("network", "사유");
    await vi.waitFor(() => expect(useDepositStore.getState().summary).not.toBeNull());
    expect(simulations(get)).toHaveLength(4);
  });
});

describe("받은 적 없는 투자처", () => {
  it("다시 요청하지 않고 실패 문구만 보인다", async () => {
    useDepositStore.setState({ input: { institution: "savings_bank", start: "2020-01-15", principal: "10000000" } });
    // 서버는 요청한 투자처의 202를 준다 — 공용 픽스처는 시중은행이다.
    const get = respond({ ...COLLECTING, institution: "savings_bank" });
    await useDepositStore.getState().run();
    progress.handlers?.onFailed("auth", "사유");
    await new Promise((r) => setTimeout(r, 0));
    expect(simulations(get)).toHaveLength(1);
    expect(useDepositStore.getState().error).toContain("인증키 설정을 확인하세요");
    expect(useDepositStore.getState().summary).toBeNull();
  });

  it("투자처 목록을 받지 못했으면 받아 둔 줄 모른다 — 다시 요청하지 않는다", async () => {
    useDepositStore.setState({ institutions: null });
    const get = respond(COLLECTING);
    await useDepositStore.getState().run();
    progress.handlers?.onFailed("auth", "사유");
    await new Promise((r) => setTimeout(r, 0));
    expect(simulations(get)).toHaveLength(1);
    expect(useDepositStore.getState().error).toContain("인증키 설정을 확인하세요");
  });
});
