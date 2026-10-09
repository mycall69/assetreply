/**
 * 대시보드 화면 (014 T028) — FR-001, FR-003, FR-008, FR-009, contracts D1·D6.
 *
 * - 카드 15개가 묶음 다섯의 이름표와 함께 `order` 차례로 보인다
 * - 한 지표가 실패해도 나머지 14개는 그대로다(FR-009)
 * - [새로고침]은 시세 경로만 다시 부른다 — 뉴스는 다시 부르지 않는다(U3)
 * - 사이드바의 "대시보드"는 `/dashboard` 링크이고, 대시보드·지표 화면에서 선택된 상태다
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/dashboard/page";
import { Sidebar } from "@/components/shell/Sidebar";
import { screenTitle } from "@/components/shell/TopBar";
import { apiClient } from "@/lib/apiClient";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { BASES, quotesOf } from "./support/dashboardFixtures";

const quoteCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.filter(([p]) => p === "/api/dashboard/quotes").length;

function mockGet(body = quotesOf()) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") return body;
    if (path.startsWith("/api/dashboard/news/")) return new Promise(() => undefined); // 뉴스는 붙잡아 둔다
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

beforeEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  vi.restoreAllMocks();
});

describe("카드", () => {
  it("묶음 다섯과 카드 15개가 차례대로", async () => {
    mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("indicator-card")).toHaveLength(15));
    const groups = screen.getAllByRole("region").filter((r) => r.getAttribute("data-group"));
    expect(groups.map((g) => within(g).getByRole("heading").textContent)).toEqual(
      ["한국", "미국", "일본·중국", "환율", "원자재·변동성"]);
    const names = screen.getAllByTestId("indicator-card").map((c) => c.getAttribute("data-indicator"));
    expect(names).toEqual(BASES.map((b) => b.id));
  });

  it("한 지표가 실패해도 나머지 14개", async () => {
    mockGet(quotesOf({ shanghai: { status: "failed", quote: null, failure: { kind: "connection", message: "연결 실패" } } }));
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("card-value")).toHaveLength(15));
    const values = screen.getAllByTestId("card-value").map((v) => v.textContent);
    expect(values.filter((v) => v === "—")).toHaveLength(1);
    expect(screen.getByText("연결 실패")).toBeInTheDocument();
  });

  it("출처를 밝힌다", async () => {
    mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("indicator-card")).toHaveLength(15));
    expect(screen.getByText(/출처: Yahoo Finance\(지수·원자재·VIX·시장 환율\) · 한국은행 ECOS\(환율 추이\)/)).toBeInTheDocument();
  });

  it("[새로고침]은 시세만 다시 부른다", async () => {
    const get = mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("indicator-card")).toHaveLength(15));
    const before = quoteCalls(get);
    const newsBefore = get.mock.calls.filter(([p]) => String(p).startsWith("/api/dashboard/news/")).length;
    fireEvent.click(screen.getByRole("button", { name: "새로고침" }));
    await waitFor(() => expect(quoteCalls(get)).toBe(before + 1));
    expect(get.mock.calls.filter(([p]) => String(p).startsWith("/api/dashboard/news/")).length).toBe(newsBefore);
  });
});

describe("셸", () => {
  it("사이드바의 대시보드는 /dashboard 링크이고 선택된 상태", () => {
    render(<Sidebar current="/dashboard" />);
    const item = screen.getByText("대시보드").closest("li") as HTMLElement;
    expect(within(item).getByRole("link")).toHaveAttribute("href", "/dashboard");
    expect(item).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText("준비중")).toBeNull();
  });

  it("지표 화면에서도 대시보드만 선택된 상태", () => {
    render(<Sidebar current="/dashboard/sp500" />);
    const current = screen.getAllByRole("listitem").filter((li) => li.getAttribute("aria-current") === "page");
    expect(current.map((li) => li.textContent)).toEqual(["대시보드"]);
  });

  it("상단 바 제목", () => {
    expect(screenTitle("/dashboard")).toBe("대시보드");
    expect(screenTitle("/dashboard/sp500")).toBe("대시보드");
  });
});
