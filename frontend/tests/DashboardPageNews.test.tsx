/**
 * 대시보드의 뉴스 칸 (014 T071) — FR-024, SC-001, SC-007.
 *
 * - 뉴스 응답을 붙잡아 둔 채(풀지 않은 Promise)여도 카드 15개가 먼저 보인다 — 가장 느린 뉴스 출처만큼 대시보드가 늦게 뜨지 않는다
 * - 세 칸이 응답이 온 차례대로 채워진다. 한 칸이 실패해도 다른 칸·카드는 그대로다
 */
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/dashboard/page";
import { apiClient } from "@/lib/apiClient";
import type { NewsListResponse, NewsSourceKey } from "@/lib/types";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { initialColumns, useNewsStore } from "@/stores/newsStore";
import { quotesOf } from "./support/dashboardFixtures";
import { failedOf, newsOf } from "./support/newsFixtures";

type Resolve = (v: NewsListResponse) => void;

function holdNews() {
  const resolvers: Partial<Record<NewsSourceKey, Resolve>> = {};
  const get = vi.spyOn(apiClient, "get").mockImplementation((path: string) => {
    if (path === "/api/dashboard/quotes") return Promise.resolve(quotesOf());
    if (path.startsWith("/api/dashboard/news/")) {
      const source = path.split("/").pop() as NewsSourceKey;
      return new Promise((resolve) => { resolvers[source] = resolve as Resolve; });
    }
    return Promise.reject(new Error(`예상하지 못한 요청 ${path}`));
  });
  return { get, resolvers };
}

const columnOf = (source: NewsSourceKey) =>
  screen.getAllByTestId("news-column").find((c) => c.getAttribute("data-source") === source) as HTMLElement;

beforeEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
  useNewsStore.setState({ columns: initialColumns() });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  vi.restoreAllMocks();
});

describe("뉴스를 기다리지 않는다", () => {
  it("뉴스가 오지 않아도 카드 15개가 먼저 보인다", async () => {
    holdNews();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("indicator-card")).toHaveLength(15));
    expect(screen.getAllByText("받는 중…")).toHaveLength(3);
  });
});

describe("칸마다 따로", () => {
  it("온 차례대로 채워지고 한 칸이 실패해도 다른 칸·카드는 그대로", async () => {
    const { resolvers } = holdNews();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId("indicator-card")).toHaveLength(15));
    await waitFor(() => expect(resolvers.jp).toBeDefined());

    resolvers.jp?.(newsOf("jp"));
    await waitFor(() => expect(columnOf("jp").querySelectorAll("[data-testid=news-row]")).toHaveLength(10));
    expect(columnOf("kr")).toHaveTextContent("받는 중…");

    resolvers.us?.(failedOf("us", { reason: "blocked", message: "접근을 막았습니다(403).", retryAfterSeconds: 60 }));
    await waitFor(() => expect(columnOf("us")).toHaveTextContent("받지 못했습니다 — 차단"));
    expect(columnOf("jp").querySelectorAll("[data-testid=news-row]")).toHaveLength(10);

    resolvers.kr?.(newsOf("kr"));
    await waitFor(() => expect(columnOf("kr").querySelectorAll("[data-testid=news-row]")).toHaveLength(10));
    expect(screen.getAllByTestId("indicator-card")).toHaveLength(15);
  });
});
