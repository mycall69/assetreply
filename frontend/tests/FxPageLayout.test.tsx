/**
 * 외환 화면 — 왼쪽 정렬, 통화를 바꿔도 화면 그대로 (010 반복 1, T046) — FR-022, FR-023, SC-008, research R10-16·R10-17.
 *
 * - 본문이 가운데 정렬(`mx-auto`)이 아니다 — 넓은 창에서 다른 네 화면처럼 왼쪽에서 시작한다
 * - **통화를 바꾸면 화면이 튀던 원인은 높이 무너짐이다**(실측 — R10-16): 바꾸는 순간 일자별 표·트렌드 차트가 "불러오는 중"으로 바뀌어 문서가 창보다
 *   짧아지고 브라우저가 스크롤을 끌어내린다. 그래서 바꾸기 **직전** 본문 높이를 최소 높이로 붙잡고, 새 통화가 다 오면 놓는다
 * - 개발 모드에서는 StrictMode가 효과를 두 번 실행해 `DailyTable`의 "첫 렌더에서는 움직이지 않음" 장치가 무력해졌다 — 다시 붙은 표가 창을 표로
 *   옮겼다. `DailyTable`은 `resetKey`가 정말 바뀌었을 때만 표의 처음으로 간다(004 FR-005b — 기간 단위 전환·먼 날짜 고르기는 그대로)
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FxPage from "@/app/fx/page";
import { DailyTable } from "@/components/fx/DailyTable";
import { apiClient } from "@/lib/apiClient";
import type { CoverageRow, DailyResponse, LatestResponse, PeriodRow, SeriesResponse } from "@/lib/types";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const DERIVED = { cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42" };
const day = (date: string): PeriodRow => ({
  date, baseRate: "1354.200000", isProvisional: false, derived: DERIVED, periodFrom: date, periodTo: date,
  isOngoing: false,
});
const DAILY: DailyResponse = {
  currency: "USD", period: "daily", quoteUnit: 1, appliedSpread: DERIVED, spreadBasis: "current",
  rows: [day("2026-08-28"), day("2026-08-27")], hasMore: true, oldestReturned: "2026-08-27",
};
const COVERAGE: CoverageRow[] = ["USD", "JPY", "EUR"].map((currency) => ({
  currency: currency as CoverageRow["currency"], coveredFrom: "2000-01-01", coveredThrough: "2026-08-28",
  firstAvailableDate: "2000-01-04", lastUpdatedAt: "2026-08-29T00:00:00Z",
}));
const latest = (currency: string): LatestResponse => ({
  currency: currency as LatestResponse["currency"], quotePair: `${currency}/KRW`, date: "2026-08-28",
  baseRate: "1356.100000", quoteUnit: currency === "JPY" ? 100 : 1, isProvisional: false, fetchedAt: null, change: null,
});
const series = (currency: string): SeriesResponse => ({
  currency: currency as SeriesResponse["currency"], quoteUnit: 1, from: "2025-08-28", to: "2026-08-28", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, points: [{ date: "2026-08-28", baseRate: "1356.100000" }] as never, gaps: [],
});

function answer(path: string): unknown {
  const currency = /currency=([A-Z]+)/.exec(path)?.[1] ?? "USD";
  if (path.startsWith("/api/fx/coverage")) return { coverage: COVERAGE };
  if (path.startsWith("/api/fx/latest")) return latest(currency);
  if (path.startsWith("/api/fx/daily")) return { ...DAILY, currency };
  if (path.startsWith("/api/fx/series")) return series(currency);
  throw new Error(`처리기가 없는 경로: ${path}`);
}

const workspace = () => screen.getByRole("heading", { name: "외환 데이터 분석" }).closest("header")?.parentElement as HTMLElement;

beforeEach(() => {
  vi.restoreAllMocks();
  useFxWorkspaceStore.setState({
    currency: "USD", selectedDate: null, preset: "1y", period: "daily", coverage: [], daily: null, latest: null,
    series: null, notice: null, error: null, loading: false, loadingMore: false, loadMoreError: null, tableEpoch: 0,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("외환 화면 배치", () => {
  it("본문이 가운데 정렬이 아니다 — 다른 화면처럼 왼쪽에서 시작한다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    render(<FxPage />);
    await screen.findByRole("table");
    expect(workspace()).not.toHaveClass("mx-auto");
  });

  it("통화를 바꾸는 동안 바꾸기 직전 높이를 붙잡고, 새 통화가 오면 놓는다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const height = this.querySelector?.("h2")?.textContent === "외환 데이터 분석" ? 2186 : 0;
      return { width: 1000, height, top: 0, left: 0, right: 1000, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    render(<FxPage />);
    await screen.findByRole("table");
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      await gate;
      return answer(path) as never;
    });
    await userEvent.click(screen.getByRole("tab", { name: /JPY/ }));
    expect(workspace().style.minHeight).toBe("2186px");
    expect(screen.queryByRole("table")).toBeNull();  // 표는 비워진다 — 이전 통화의 값이 남지 않는다
    await act(async () => { release(); });
    await screen.findByRole("table");
    await waitFor(() => expect(workspace().style.minHeight).toBe(""));
  });
});

describe("DailyTable — resetKey가 바뀔 때만 표의 처음으로", () => {
  const props = { selectedDate: null, onSelect: vi.fn(), onLoadMore: vi.fn(), loadingMore: false, loadError: null };

  it("StrictMode에서 붙을 때는 움직이지 않고, resetKey가 바뀌면 움직인다", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const { rerender, unmount } = render(<StrictMode><DailyTable data={DAILY} resetKey={3} {...props} /></StrictMode>);
    expect(scroll).not.toHaveBeenCalled();
    rerender(<StrictMode><DailyTable data={DAILY} resetKey={3} {...props} /></StrictMode>);
    expect(scroll).not.toHaveBeenCalled();
    rerender(<StrictMode><DailyTable data={DAILY} resetKey={4} {...props} /></StrictMode>);
    expect(scroll).toHaveBeenCalledTimes(1);
    unmount();
    // 통화를 바꾸면 표가 떨어졌다 다시 붙는다 — 같은 resetKey면 창을 옮기지 않는다
    render(<StrictMode><DailyTable data={DAILY} resetKey={4} {...props} /></StrictMode>);
    expect(scroll).toHaveBeenCalledTimes(1);
  });
});
