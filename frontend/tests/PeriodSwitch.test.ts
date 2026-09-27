/**
 * 기간 단위 전환 잔존 방지 (T024) — 004 FR-010, FR-011, FR-019b, SC-010, SC-013.
 *
 * **같은 계열의 결함을 세 번째로 막는다.** 002 오늘 환율 새로고침(FR-036c)은 구현 후에
 * 발견했고, 003 통화 전환(FR-028)과 여기는 요구사항 단계에서 적었다 (research R4-8).
 *
 * 두 겹으로 막는다.
 *  1. 전환 즉시 표를 비운다 (한 프레임도 이전 단위가 남지 않는다)
 *  2. 도착한 응답의 `period`를 현재 선택과 대조해 거른다 (뒤늦은 갱신 차단)
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";
import type { CoverageRow, DailyResponse, PeriodUnit } from "@/lib/types";

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const COVERAGE: CoverageRow[] = [{
  currency: "USD", coveredFrom: "1964-01-01", coveredThrough: "2026-08-29",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-08-30T00:00:00Z",
}];

const page = (period: PeriodUnit, dates: string[]): DailyResponse => ({
  currency: "USD", period, quoteUnit: 1, appliedSpread: DERIVED,
  spreadBasis: "current",
  rows: dates.map((date) => ({
    date, baseRate: "1356.100000", isProvisional: false, derived: DERIVED,
    periodFrom: date, periodTo: date, isOngoing: false,
  })),
  hasMore: true,
  oldestReturned: dates.at(-1) ?? null,
});

const DAILY = page("daily", ["2026-08-29", "2026-08-28"]);

beforeEach(() => {
  vi.restoreAllMocks();
  useFxWorkspaceStore.setState({
    currency: "USD", selectedDate: "2026-08-26", preset: "1y", period: "daily",
    coverage: COVERAGE, daily: DAILY, notice: null, error: null,
    loadingMore: false, loadMoreError: null, tableEpoch: 0,
  });
});

const store = () => useFxWorkspaceStore.getState();

describe("기간 단위 전환", () => {
  it("전환 즉시 이전 단위의 행이 사라진다", async () => {
    // FR-010, SC-010 — 남으면 사용자가 지금 보는 행이 어느 단위의 것인지 알 수 없다.
    vi.spyOn(apiClient, "get").mockResolvedValue(page("weekly", ["2026-08-28"]));
    const pending = store().setPeriod("weekly");
    expect(store().daily).toBeNull();
    await pending;
    expect(store().daily?.rows.map((r) => r.date)).toEqual(["2026-08-28"]);
  });

  it("선택한 단위를 요청에 싣는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(page("monthly", []));
    await store().setPeriod("monthly");
    expect(String(get.mock.calls[0][0])).toContain("period=monthly");
  });

  it("뒤늦게 도착한 이전 단위의 응답은 버린다", async () => {
    // FR-011 — 응답에 실린 `period`를 현재 선택과 대조해 거른다.
    vi.spyOn(apiClient, "get").mockResolvedValue(page("daily", ["2026-08-29"]));
    await store().setPeriod("weekly");
    expect(store().daily).toBeNull();
    expect(store().period).toBe("weekly");
  });

  it("전환하면 스크롤을 처음으로 되돌릴 신호를 낸다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(page("weekly", ["2026-08-28"]));
    const before = store().tableEpoch;
    await store().setPeriod("weekly");
    expect(store().tableEpoch).toBeGreaterThan(before);
  });

  it("단위를 바꿔도 선택 날짜는 그대로다", async () => {
    // FR-019b, SC-013 — 기준일로 옮겨 놓으면 일 단위로 돌아왔을 때 원래 날짜를 잃는다.
    vi.spyOn(apiClient, "get").mockResolvedValue(page("weekly", ["2026-08-28"]));
    await store().setPeriod("weekly");
    expect(store().selectedDate).toBe("2026-08-26");
    await store().setPeriod("daily");
    expect(store().selectedDate).toBe("2026-08-26");
  });

  it("전환에 실패해도 단위 선택은 유지된다", async () => {
    // 선택은 되돌리고 오류만 보이면 사용자는 클릭이 먹지 않은 것으로 여긴다.
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("네트워크"));
    await store().setPeriod("monthly");
    expect(store().period).toBe("monthly");
    expect(store().error).not.toBeNull();
  });

  it("이어 보기도 현재 단위로 요청한다", async () => {
    // 단위를 싣지 않으면 주 단위 표에 일 단위 행이 이어 붙는다 — 오류 없이 섞인다.
    useFxWorkspaceStore.setState({ period: "weekly", daily: page("weekly", ["2026-08-28"]) });
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(page("weekly", ["2026-08-21"]));
    await store().loadMoreDaily();
    expect(String(get.mock.calls[0][0])).toContain("period=weekly");
  });

  it("이어 보기 응답의 단위가 다르면 붙이지 않는다", async () => {
    useFxWorkspaceStore.setState({ period: "weekly", daily: page("weekly", ["2026-08-28"]) });
    vi.spyOn(apiClient, "get").mockResolvedValue(page("daily", ["2026-08-27"]));
    await store().loadMoreDaily();
    expect(store().daily?.rows.map((r) => r.date)).toEqual(["2026-08-28"]);
  });
});
