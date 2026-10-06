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
import type { CoverageRow, CurrencyCode, DailyResponse, LatestResponse, PeriodUnit, SeriesResponse } from "@/lib/types";

const DERIVED = { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" };

const COVERAGE: CoverageRow[] = [{
  currency: "USD", coveredFrom: "1964-01-01", coveredThrough: "2026-08-29",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-08-30T00:00:00Z",
}];

const page = (period: PeriodUnit, dates: string[], currency: CurrencyCode = "USD"): DailyResponse => ({
  currency, period, quoteUnit: 1, appliedSpread: DERIVED,
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

  it("전환해도 \"표의 처음으로\" 신호를 내지 않는다 — 창이 움직이지 않는다 (012 FR-001)", async () => {
    // 012 승인 2026-10-06 — 004 FR-005b를 기간 전환에 한해 대체한다. 신호는 먼 날짜(FR-005a)에만 남는다(fxWorkspaceScroll.test.ts).
    vi.spyOn(apiClient, "get").mockResolvedValue(page("weekly", ["2026-08-28"]));
    const before = store().tableEpoch;
    await store().setPeriod("weekly");
    expect(store().tableEpoch).toBe(before);
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

/**
 * 012 FR-002 — 통화 전환의 다시 받기(`loadAll`)가 늦게 오면 그 사이 바뀐 단위·통화의 표를 덮었다(기존 결함 — research R12-1). 표를 붙잡아 두는 동안에도
 * 이전 단위·통화의 행이 섞이지 않는다.
 */
describe("통화 전환과 겹친 전환 (012 FR-002)", () => {
  const latest = (currency: CurrencyCode): LatestResponse => ({
    currency, quotePair: `${currency}/KRW`, date: "2026-08-29", baseRate: "1356.100000", quoteUnit: 1,
    isProvisional: false, fetchedAt: null, change: null,
  });
  const series = (currency: CurrencyCode): SeriesResponse => ({
    currency, quoteUnit: 1, from: "2025-08-29", to: "2026-08-29", downsampled: false, algorithm: "lttb",
    sourcePointCount: 0, points: [], gaps: [],
  } as unknown as SeriesResponse);
  const coverage: CoverageRow[] = ["USD", "JPY"].map((currency) => ({ ...COVERAGE[0], currency: currency as CurrencyCode }));

  /** 느린 요청이 **나간 뒤에** 다음 조작을 하도록 `requested`를 준다 — 조작이 먼저면 요청이 새 단위로 나가 경쟁이 생기지 않는다. */
  function gatedApi(slow: (path: string) => boolean) {
    let release: () => void = () => undefined;
    let sent: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const requested = new Promise<void>((resolve) => { sent = resolve; });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      const currency = (/currency=([A-Z]+)/.exec(path)?.[1] ?? "USD") as CurrencyCode;
      if (slow(path)) { sent(); await gate; }
      if (path.startsWith("/api/fx/coverage")) return { coverage } as never;
      if (path.startsWith("/api/fx/latest")) return latest(currency) as never;
      if (path.startsWith("/api/fx/series")) return series(currency) as never;
      const period = (/period=([a-z]+)/.exec(path)?.[1] ?? "daily") as PeriodUnit;
      return page(period, period === "daily" ? ["2026-08-29"] : ["2026-08-28"], currency) as never;
    });
    return { release: () => release(), requested };
  }

  it("늦게 온 통화 전환의 일 단위 표가 주 단위로 바꾼 표를 덮지 않는다", async () => {
    useFxWorkspaceStore.setState({ coverage });
    const { release, requested } = gatedApi((path) => path.includes("/api/fx/daily") && path.includes("period=daily"));
    const loading = store().loadAll();
    await requested;
    await store().setPeriod("weekly");
    expect(store().daily?.period).toBe("weekly");
    release();
    await loading;
    expect(store().period).toBe("weekly");
    expect(store().daily?.period).toBe("weekly");
    expect(store().daily?.rows.map((r) => r.date)).toEqual(["2026-08-28"]);
  });

  it("통화를 다시 바꾼 뒤 늦게 온 이전 통화의 응답은 쓰지 않는다", async () => {
    useFxWorkspaceStore.setState({ coverage });
    const { release, requested } = gatedApi((path) => path.includes("currency=USD") && !path.startsWith("/api/fx/coverage"));
    const first = store().loadAll();
    await requested;
    useFxWorkspaceStore.setState({ currency: "JPY" });
    await store().loadAll();
    expect(store().daily?.currency).toBe("JPY");
    release();
    await first;
    expect(store().currency).toBe("JPY");
    expect(store().daily?.currency).toBe("JPY");
    expect(store().latest?.currency).toBe("JPY");
  });
});
