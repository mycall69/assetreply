/**
 * 외환 화면 — 왼쪽 정렬, 통화를 바꿔도 화면 그대로 (010 반복 1, T046) — FR-022, FR-023, SC-008, research R10-16·R10-17.
 *
 * - 본문이 가운데 정렬(`mx-auto`)이 아니다 — 넓은 창에서 다른 네 화면처럼 왼쪽에서 시작한다
 * - **통화를 바꾸면 화면이 튀던 원인은 높이 무너짐이다**(실측 — R10-16): 바꾸는 순간 일자별 표·트렌드 차트가 "불러오는 중"으로 바뀌어 문서가 창보다
 *   짧아지고 브라우저가 스크롤을 끌어내린다. 그래서 바꾸기 **직전** 본문 높이를 최소 높이로 붙잡고, 새 통화가 다 오면 놓는다
 * - 개발 모드에서는 StrictMode가 효과를 두 번 실행해 `DailyTable`의 "첫 렌더에서는 움직이지 않음" 장치가 무력해졌다 — 다시 붙은 표가 창을 표로
 *   옮겼다. `DailyTable`은 `resetKey`가 정말 바뀌었을 때만 표의 처음으로 간다(004 FR-005b — 기간 단위 전환·먼 날짜 고르기는 그대로)
 * - **기간 단위를 바꾸면 표가 떨어졌다 새로 붙는다**(T051 실측 — 창이 맨 위로 끌려가고 표의 처음으로 가지 않았다). 새로 붙은 표는 직전 `resetKey`를
 *   모르므로 화면이 마지막으로 그린 표의 차례를 기억해 표의 처음으로 옮긴다(FR-023 — 기간 단위 전환은 004 FR-005b 그대로). 바꾸는 동안 높이도 붙잡는다 —
 *   무너진 문서에 창이 맨 위로 튀었다 내려오지 않게
 * - **012 FR-001** — 기간 단위를 바꿔도 창이 움직이지 않는다(004 FR-005b를 기간 전환에 한해 대체 — 사용자 승인 2026-10-06). 단위 탭이 누른 자리에
 *   남는다. 먼 날짜를 골라 표를 새로 받는 경우(FR-005a)만 지금처럼 표의 처음으로 간다. 새 표가 짧아 지금 스크롤을 받치지 못하면 놓을 때 바닥을 남긴다
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
  if (path.startsWith("/api/fx/daily")) {
    // 스토어는 도착한 응답의 단위를 지금 선택과 대조한다(004 FR-011) — 요청한 단위로 답한다.
    const period = (/period=([a-z]+)/.exec(path)?.[1] ?? "daily") as DailyResponse["period"];
    return { ...DAILY, currency, period };
  }
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

describe("기간 단위 전환은 창을 옮기지 않는다 (012 FR-001 — 004 FR-005b를 기간 전환에 한해 대체)", () => {
  const gated = () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      await gate;
      return answer(path) as never;
    });
    return () => release();
  };

  it("StrictMode — 통화 전환도 기간 단위 전환도 창을 옮기지 않는다", async () => {
    // 012 승인 2026-10-06 — 기간 전환 뒤 "표의 처음으로"(004 FR-005b)를 하지 않는다. 단위 탭이 누른 자리에 남는다.
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    render(<StrictMode><FxPage /></StrictMode>);
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("tab", { name: /JPY/ }));
    await screen.findByRole("table");
    expect(scroll).not.toHaveBeenCalled();

    for (const unit of ["주", "월", "일"]) {
      const release = gated();
      await userEvent.click(screen.getByRole("tab", { name: unit }));
      expect(screen.queryByRole("table")).toBeNull();  // 이전 단위의 행은 남지 않는다(004 FR-010 그대로)
      await act(async () => { release(); });
      await screen.findByRole("table");
      await act(async () => { await Promise.resolve(); });
      expect(scroll).not.toHaveBeenCalled();
    }
  });

  it("먼 날짜를 골라 표를 새로 받으면 지금처럼 표의 처음으로 간다 (004 FR-005a 그대로)", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    render(<StrictMode><FxPage /></StrictMode>);
    await screen.findByRole("table");
    await act(async () => { await useFxWorkspaceStore.getState().selectDate("2020-01-02"); });
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    const target = scroll.mock.contexts.at(-1) as Element;
    expect(target.contains(screen.getByRole("table"))).toBe(true);  // 표의 처음 — 표를 품은 자리
  });

  it("새 표가 짧아 지금 스크롤을 받치지 못하면 놓은 뒤에도 바닥 높이를 남긴다", async () => {
    // FR-001 실패 양상 *다른 곳에서 일어남* — 놓는 순간 짧아진 문서를 브라우저가 당겨 창이 올라간다.
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      // 창이 본문 위 끝에서 1,000px 아래에 있다. 새 표의 칸(마지막 자식)은 본문 위 끝에서 1,300px에서 끝난다 — 창 아래 끝(1,800px)보다 위
      const isWorkspace = this.querySelector?.("h2")?.textContent === "외환 데이터 분석";
      const isTableSection = !isWorkspace && this.querySelector?.("h3")?.textContent === "일자별 환율 상세";
      const [top, height] = isWorkspace ? [-1000, 2186] : isTableSection ? [-200, 500] : [0, 0];
      return { width: 1000, height, top, left: 0, right: 1000, bottom: top + height, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
    });
    Element.prototype.scrollIntoView = vi.fn();
    render(<FxPage />);
    await screen.findByRole("table");
    const release = gated();
    await userEvent.click(screen.getByRole("tab", { name: "월" }));
    expect(workspace().style.minHeight).toBe("2186px");
    await act(async () => { release(); });
    await screen.findByRole("table");
    await waitFor(() => expect(workspace().style.minHeight).toBe("1800px"));
  });

  it("기간 단위를 바꾸는 동안 바꾸기 직전 높이를 붙잡고, 새 표가 오면 놓는다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => answer(path) as never);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const height = this.querySelector?.("h2")?.textContent === "외환 데이터 분석" ? 2186 : 0;
      return { width: 1000, height, top: 0, left: 0, right: 1000, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    Element.prototype.scrollIntoView = vi.fn();
    render(<FxPage />);
    await screen.findByRole("table");
    const release = gated();
    await userEvent.click(screen.getByRole("tab", { name: "월" }));
    expect(workspace().style.minHeight).toBe("2186px");
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
