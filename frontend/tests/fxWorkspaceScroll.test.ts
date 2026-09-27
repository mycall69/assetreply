/**
 * 이어 보기 상태 (T013, T016, T017) — 004 FR-003, FR-004, FR-005, FR-005a, FR-005b.
 *
 * **덧붙이지 않고 교체하면 보던 위치가 처음으로 튄다** (FR-003, research R4-6).
 * 002의 `더 보기`는 한 번에 한 번씩이라 티가 덜 났지만, 스크롤로 연속 호출하면 매번 튄다.
 *
 * 반대로 아주 과거의 날짜를 고를 때는 **버려야** 한다 (FR-005a). 이어 붙이면 30년을
 * 건너뛸 때 그 사이 전부를 한꺼번에 받게 된다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";
import type { CoverageRow, DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const COVERAGE: CoverageRow[] = [{
  currency: "USD", coveredFrom: "1964-01-01", coveredThrough: "2026-08-29",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-08-30T00:00:00Z",
}];

const day = (date: string): PeriodRow => ({
  date, baseRate: "1356.100000", isProvisional: false, derived: DERIVED,
  periodFrom: date, periodTo: date, isOngoing: false,
});

const page = (dates: string[], hasMore: boolean): DailyResponse => ({
  currency: "USD", period: "daily", quoteUnit: 1, appliedSpread: DERIVED,
  spreadBasis: "current", rows: dates.map(day), hasMore,
  oldestReturned: dates.at(-1) ?? null,
});

const FIRST = page(["2026-08-29", "2026-08-28"], true);

beforeEach(() => {
  vi.restoreAllMocks();
  useFxWorkspaceStore.setState({
    currency: "USD", selectedDate: "2026-08-29", preset: "1y",
    coverage: COVERAGE, daily: FIRST, notice: null, error: null,
    loadingMore: false, loadMoreError: null, tableEpoch: 0,
  });
});

const store = () => useFxWorkspaceStore.getState();

describe("이어 보기", () => {
  it("새 행을 기존 배열 끝에 덧붙인다", async () => {
    // FR-003 — 전체를 교체하면 보던 행이 화면에서 벗어난다 (SC-002).
    vi.spyOn(apiClient, "get").mockResolvedValue(
      page(["2026-08-27", "2026-08-26"], false));
    await store().loadMoreDaily();
    expect(store().daily?.rows.map((r) => r.date)).toEqual([
      "2026-08-29", "2026-08-28", "2026-08-27", "2026-08-26"]);
  });

  it("가장 오래된 날짜를 커서로 삼는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(page([], false));
    await store().loadMoreDaily();
    expect(String(get.mock.calls[0][0])).toContain("before=2026-08-28");
  });

  it("끝에 도달했으면 요청하지 않는다", async () => {
    // SC-003 — 더 받을 것이 없는데 계속 요청하면 안 된다.
    useFxWorkspaceStore.setState({ daily: { ...FIRST, hasMore: false } });
    const get = vi.spyOn(apiClient, "get");
    await store().loadMoreDaily();
    expect(get).not.toHaveBeenCalled();
  });

  it("이미 불러오는 중이면 다시 요청하지 않는다", async () => {
    // SC-004 — 중복 요청은 오류 없이 성공하면서 같은 행을 두 번 그린다.
    useFxWorkspaceStore.setState({ loadingMore: true });
    const get = vi.spyOn(apiClient, "get");
    await store().loadMoreDaily();
    expect(get).not.toHaveBeenCalled();
  });

  it("실패해도 이미 쌓인 행은 남는다", async () => {
    // FR-004 — 조용히 멈추면 데이터가 거기서 끝난 것으로 오해한다.
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("네트워크"));
    await store().loadMoreDaily();
    expect(store().daily?.rows).toHaveLength(2);
    expect(store().loadMoreError).not.toBeNull();
    expect(store().loadingMore).toBe(false);
  });

  it("재시도가 성공하면 실패 표시가 사라진다", async () => {
    useFxWorkspaceStore.setState({ loadMoreError: "이어서 불러오지 못했습니다." });
    vi.spyOn(apiClient, "get").mockResolvedValue(page(["2026-08-27"], false));
    await store().loadMoreDaily();
    expect(store().loadMoreError).toBeNull();
    expect(store().daily?.rows).toHaveLength(3);
  });

  it("이어 보기 실패는 화면 전체 오류로 올리지 않는다", async () => {
    // 표 아래에서 말해야 한다. 상단 경고로 올리면 표가 멀쩡한데 화면이 고장 난 것처럼 보인다.
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("네트워크"));
    await store().loadMoreDaily();
    expect(store().error).toBeNull();
  });
});

describe("과거 날짜 선택", () => {
  it("쌓아 둔 행을 버리고 그 날짜 주변부터 다시 받는다", async () => {
    // FR-005a — 이어 붙이면 30년치를 한꺼번에 받게 된다 (SC-017).
    vi.spyOn(apiClient, "get").mockResolvedValue(
      page(["1990-01-15", "1990-01-12"], true));
    await store().selectDate("1990-01-15");
    expect(store().daily?.rows.map((r) => r.date)).toEqual([
      "1990-01-15", "1990-01-12"]);
  });

  it("표를 새로 받으면 스크롤을 처음으로 되돌릴 신호를 낸다", async () => {
    // FR-005b — 이전 위치에 머무르면 새로 받은 내용과 화면이 어긋난다.
    vi.spyOn(apiClient, "get").mockResolvedValue(page(["1990-01-15"], true));
    const before = store().tableEpoch;
    await store().selectDate("1990-01-15");
    expect(store().tableEpoch).toBeGreaterThan(before);
  });

  it("표 안의 날짜를 고르면 표도 스크롤도 그대로다", async () => {
    const get = vi.spyOn(apiClient, "get");
    const before = store().tableEpoch;
    await store().selectDate("2026-08-28");
    expect(get).not.toHaveBeenCalled();
    expect(store().tableEpoch).toBe(before);
    expect(store().daily?.rows).toHaveLength(2);
  });
});
