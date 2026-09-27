/**
 * 선택 날짜 연동 테스트 (T038) — SC-002, contracts/ui-interaction.md.
 *
 * 세 영역(날짜 입력·차트·표)이 **하나의 상태**를 공유한다. 어느 경로로 바꿔도 같은 값이
 * 되어야 하고, 표 범위 안에서는 네트워크 요청이 나가지 않아야 한다(SC-009: 차트 위에서
 * 시점을 훑는 조작이 1초 이내여야 한다).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";
import type { CoverageRow, DailyResponse } from "@/lib/types";

const COVERAGE: CoverageRow[] = [{
  currency: "USD", coveredFrom: "1964-01-01", coveredThrough: "2026-08-29",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-08-30T00:00:00Z",
}];

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const DAILY: DailyResponse = {
  currency: "USD", period: "daily", quoteUnit: 1, appliedSpread: DERIVED, spreadBasis: "current",
  rows: [
    { date: "2026-08-29", baseRate: "1356.100000", isProvisional: false, derived: DERIVED,
      periodFrom: "2026-08-29", periodTo: "2026-08-29", isOngoing: false },
    { date: "2026-08-14", baseRate: "1372.300000", isProvisional: false, derived: DERIVED,
      periodFrom: "2026-08-14", periodTo: "2026-08-14", isOngoing: false },
  ],
  hasMore: true, oldestReturned: "2026-08-14",
};

describe("선택 날짜 단일 상태", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useFxWorkspaceStore.setState({
      currency: "USD", selectedDate: "2026-08-29", preset: "1y",
      coverage: COVERAGE, daily: DAILY, notice: null, error: null,
    });
  });

  it("표 범위 안의 날짜를 고르면 서버를 부르지 않는다", async () => {
    const get = vi.spyOn(apiClient, "get");
    await useFxWorkspaceStore.getState().selectDate("2026-08-14");
    expect(useFxWorkspaceStore.getState().selectedDate).toBe("2026-08-14");
    expect(get).not.toHaveBeenCalled();
  });

  it("표 범위 밖이면 그 날짜 기준으로 표를 다시 받는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ ...DAILY, rows: [] });
    await useFxWorkspaceStore.getState().selectDate("2019-03-14");
    expect(useFxWorkspaceStore.getState().selectedDate).toBe("2019-03-14");
    const url = String(get.mock.calls[0][0]);
    expect(url).toContain("before=2019-03-15");
  });

  it("조회 가능 범위 밖이면 알리되 선택은 반영한다", async () => {
    // 2026-09-27 변경 — 이전에는 선택을 거절하고 이전 날짜를 유지했다. 그러면 안내는
    // "범위 밖"이라 말하는데 입력은 다른 날짜를 보여줘, 사용자에게는 **클릭이 먹지
    // 않은 것처럼** 보인다. FR-010은 "값을 반환하지 않는다"를 요구할 뿐 선택을
    // 거절하라고 하지 않았다. (.specify/bugs/fx-stale-date-and-tab/)
    const get = vi.spyOn(apiClient, "get");
    await useFxWorkspaceStore.getState().selectDate("1900-01-01");
    expect(useFxWorkspaceStore.getState().selectedDate).toBe("1900-01-01");
    expect(useFxWorkspaceStore.getState().notice?.kind).toBe("out_of_range");
    // 값은 여전히 받지 않는다 — FR-010이 요구하는 것은 이쪽이다.
    expect(get).not.toHaveBeenCalled();
  });

  it("미래 날짜도 범위 밖으로 판정한다", async () => {
    await useFxWorkspaceStore.getState().selectDate("2030-01-01");
    expect(useFxWorkspaceStore.getState().notice?.kind).toBe("out_of_range");
  });
});

describe("기간 프리셋", () => {
  it("전체는 통화의 최초 제공일부터다", async () => {
    const { presetStart } = await import("@/stores/fxWorkspaceStore");
    expect(presetStart("all", COVERAGE[0])).toBe("1964-05-04");
  });

  it("프리셋이 축적 시작일보다 이르면 실제 범위로 잘린다", async () => {
    const { presetStart } = await import("@/stores/fxWorkspaceStore");
    const narrow: CoverageRow = { ...COVERAGE[0], firstAvailableDate: "2026-01-01" };
    expect(presetStart("10y", narrow)).toBe("2026-01-01");
  });
});
