/**
 * 설정을 바꾸고 예금 화면으로 돌아오면 다시 계산한다 (T024) — 008 FR-031, SC-008.
 *
 * 결과를 저장하지 않으므로(005 R5-9) 돌아온 화면이 **실행한 결과가 있으면** 같은 조건으로 다시 요청한다 — 007 `refreshIfRan`과
 * 같다. 실행한 적이 없으면 요청하지 않는다 — 열자마자 원금 없이 요청하면 오류가 보인다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { useDepositStore } from "@/stores/depositStore";
import { RESULT } from "./support/depositFixtures";

vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));

const simulations = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.filter(([p]) => String(p).startsWith("/api/deposit/simulation?"));

beforeEach(() => {
  vi.restoreAllMocks();
  useDepositStore.getState().dispose();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2020-01-15", principal: "10000000" },
    rows: [], summary: null, condition: null, collecting: null, progress: null, error: null, startable: null,
  });
});

describe("설정 뒤 다시 계산", () => {
  it("실행한 결과가 있으면 같은 조건으로 다시 요청하고 새 세율을 보인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.startsWith("/api/deposit/simulation?")) {
        const changed = simulations(get).length > 1;
        return changed ? { ...RESULT, condition: { ...RESULT.condition, interestTaxRate: "0.000000" } } : RESULT;
      }
      return { institutions: [], source: "", basis: "" };
    });
    await useDepositStore.getState().run();
    await useDepositStore.getState().refreshIfRan();
    expect(simulations(get)).toHaveLength(2);
    expect(simulations(get)[1][0]).toBe(simulations(get)[0][0]);
    expect(useDepositStore.getState().condition?.interestTaxRate).toBe("0.000000");
  });

  it("실행한 적이 없으면 요청하지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    await useDepositStore.getState().refreshIfRan();
    expect(get).not.toHaveBeenCalled();
  });
});
