/**
 * 회귀 테스트 — `.specify/bugs/fx-stale-coverage/` (2026-10-05).
 *
 * 외환 화면은 커버리지(통화별 축적 범위)를 처음 한 번만 받아 두었다(002 research R2-6 — "세 통화를 한 번에 반환하므로 통화를 바꿔도 다시
 * 받지 않는다"). 003부터 수집이 백그라운드로 돌아 화면을 연 뒤에도 새 통화가 생기고 `coveredThrough`가 는다 — 낡은 캐시에 통화의 행이 없으면
 * 차트가 `to = from`(하루짜리 구간)을 요청해 **안내 없이 비었다**(실측: `series?currency=EUR&from=2025-10-04&to=2025-10-04`).
 *
 *  R1 — 화면을 연 뒤 수집된 통화로 바꾸면 그 통화의 축적 범위로 차트를 요청한다(하루짜리가 아니다)
 *  R2 — 그 통화의 범위 안 날짜를 고르면 "아직 수집된 데이터가 없습니다"가 아니다
 *  R3 — 오늘 환율 새로고침(`loadAll`)이 늘어난 `coveredThrough`까지 차트를 요청한다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type { CoverageRow, CurrencyCode } from "@/lib/types";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";

const row = (currency: CurrencyCode, from: string, through: string): CoverageRow => ({
  currency, coveredFrom: from, coveredThrough: through, firstAvailableDate: from, lastUpdatedAt: `${through}T09:00:00`,
});
const USD = row("USD", "1964-05-04", "2026-10-02");
const JPY = row("JPY", "1977-04-01", "2026-10-02");
const EUR = row("EUR", "1994-04-11", "2026-10-02");

const DERIVED = { cashBuy: "1531.73", cashSell: "1525.61", remitSend: "1529.59", remitReceive: "1527.75" };

/** 서버가 지금 알려 주는 커버리지로 답한다. 차트 요청 경로를 모은다. */
function serve(coverage: CoverageRow[]): string[] {
  const seriesCalls: string[] = [];
  vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    const currency = /currency=([A-Z]+)/.exec(path)?.[1] ?? "USD";
    if (path.startsWith("/api/fx/coverage")) return { coverage } as never;
    if (path.startsWith("/api/fx/latest")) {
      return { currency, quotePair: `${currency}/KRW`, date: "2026-10-02", baseRate: "1528.670000", quoteUnit: 1,
        isProvisional: false, fetchedAt: null, change: null } as never;
    }
    if (path.startsWith("/api/fx/daily")) {
      return { currency, period: "daily", quoteUnit: 1, appliedSpread: DERIVED, spreadBasis: "current", hasMore: true,
        oldestReturned: "2026-10-01", rows: ["2026-10-02", "2026-10-01"].map((date) => ({ date, baseRate: "1528.670000",
          isProvisional: false, derived: DERIVED, periodFrom: date, periodTo: date, isOngoing: false })) } as never;
    }
    if (path.startsWith("/api/fx/series")) {
      seriesCalls.push(path);
      return { currency, quoteUnit: 1, from: "", to: "", downsampled: false, algorithm: "lttb", sourcePointCount: 0,
        points: [], gaps: [] } as never;
    }
    throw new Error(`처리기가 없는 경로: ${path}`);
  });
  return seriesCalls;
}

const range = (path: string) => ({
  from: /from=([\d-]+)/.exec(path)?.[1], to: /to=([\d-]+)/.exec(path)?.[1],
});

beforeEach(() => {
  vi.restoreAllMocks();
  // 화면을 연 때의 캐시 — EUR이 아직 수집되지 않았다.
  useFxWorkspaceStore.setState({
    currency: "USD", selectedDate: "2026-10-02", preset: "1y", period: "daily", coverage: [USD, JPY], daily: null,
    latest: null, series: null, collecting: null, notice: null, presetNotice: null, error: null, loading: false,
    loadingMore: false, loadMoreError: null, tableEpoch: 0,
  });
});

describe("화면을 연 뒤 수집된 통화", () => {
  it("R1 — 그 통화로 바꾸면 축적 범위로 차트를 요청한다(하루짜리 구간이 아니다)", async () => {
    const calls = serve([USD, JPY, EUR]);
    await useFxWorkspaceStore.getState().setCurrency("EUR");

    const last = range(calls.at(-1) ?? "");
    expect(last.to).toBe("2026-10-02");
    expect(last.from).not.toBe(last.to);
    expect(useFxWorkspaceStore.getState().coverageFor("EUR")).toEqual(EUR);
  });

  it("R1 — 프리셋을 바꿔도 축적 범위 안이다", async () => {
    const calls = serve([USD, JPY, EUR]);
    await useFxWorkspaceStore.getState().setCurrency("EUR");
    await useFxWorkspaceStore.getState().setPreset("all");

    expect(range(calls.at(-1) ?? "")).toEqual({ from: "1994-04-11", to: "2026-10-02" });
  });

  it("R2 — 그 통화의 범위 안 날짜를 고르면 '수집된 데이터 없음'이 아니다", async () => {
    serve([USD, JPY, EUR]);
    await useFxWorkspaceStore.getState().setCurrency("EUR");
    await useFxWorkspaceStore.getState().selectDate("2026-10-01");

    expect(useFxWorkspaceStore.getState().notice).toBeNull();
  });
});

describe("늘어난 축적 범위", () => {
  it("R3 — 오늘 환율 새로고침(loadAll)이 늘어난 coveredThrough까지 차트를 요청한다", async () => {
    useFxWorkspaceStore.setState({ coverage: [row("USD", "1964-05-04", "2026-10-01"), JPY] });
    const calls = serve([USD, JPY, EUR]);
    await useFxWorkspaceStore.getState().loadAll();

    expect(range(calls.at(-1) ?? "").to).toBe("2026-10-02");
  });
});
