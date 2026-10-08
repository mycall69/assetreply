/**
 * 화면의 그래프 (013 T054) — FR-012a, FR-013, FR-015.
 *
 * 수익률 추이와 최종 지표 막대에는 계산된(`ok`) 대상만 있다 — 수집 중 대상은 끝난 뒤 더해진다. 막대 차례는 표의 지금 정렬이다.
 * 흐린 동안(조건이 바뀜) 그래프도 흐리다.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { apiClient } from "@/lib/apiClient";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import { useCompareStore } from "@/stores/compareStore";
import { HYNIX_T, SAMSUNG_T, XLK_T, collectingStock, ok } from "./support/compareFixtures";

const streams = vi.hoisted(() => ({ stock: [] as StockProgressHandlers[] }));
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (_jobId: number, handlers: StockProgressHandlers) => {
    streams.stock.push(handlers);
    return () => undefined;
  },
}));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

function route(answer: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    if (path.startsWith("/api/stocks/search")) return Promise.resolve({ query: "", results: [], truncated: false, lists: [] });
    return Promise.resolve(answer(path));
  }) as typeof apiClient.get);
}

beforeEach(() => {
  vi.restoreAllMocks();
  streams.stock.length = 0;
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02" });
  for (const t of [SAMSUNG_T, HYNIX_T, XLK_T]) useCompareStore.getState().addTarget(t);
});

const legend = () => screen.getByTestId("compare-legend").textContent ?? "";
const barNames = () => within(screen.getByRole("group", { name: "수익률" })).getAllByRole("listitem")
  .map((li) => li.textContent?.split(/[+\-—]/)[0].trim());

describe("그래프", () => {
  it("계산된 대상만 있고 수집 중 대상은 끝난 뒤 더해진다", async () => {
    let hynix = 0;
    route((path) => (path.includes("000660") ? ((hynix += 1) === 1 ? collectingStock(41) : ok(HYNIX_T))
      : ok(path.includes("XLK") ? XLK_T : SAMSUNG_T)));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByTestId("compare-chart");
    expect(legend()).not.toContain("SK하이닉스");
    expect(barNames()).not.toContain("SK하이닉스");
    streams.stock[0].onCompleted();
    await waitFor(() => expect(legend()).toContain("SK하이닉스"));
  });

  it("막대 차례는 표의 지금 정렬이다", async () => {
    route((path) => ok(path.includes("XLK") ? XLK_T : SAMSUNG_T,
      { returnRate: path.includes("XLK") ? "3" : path.includes("000660") ? "1" : "2" }));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByTestId("compare-chart");
    // 처음 차례는 더한 차례다.
    expect(barNames()).toEqual(["삼성전자", "SK하이닉스", "Technology Select Sector SPDR Fund"]);
    // 수익률 머리를 누르면 내림차순 — XLK 3 · 삼성전자 2 · SK하이닉스 1.
    fireEvent.click(screen.getByRole("button", { name: /^수익률/ }));
    await waitFor(() => expect(barNames()).toEqual(["Technology Select Sector SPDR Fund", "삼성전자", "SK하이닉스"]));
  });

  it("흐린 동안 그래프도 흐리다", async () => {
    route(() => ok(SAMSUNG_T));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByTestId("compare-chart");
    useCompareStore.getState().setStart("2021-01-04");
    await screen.findByRole("status", { name: "조건이 바뀜" });
    const dimmed = screen.getByTestId("compare-result");
    expect(dimmed.className).toContain("opacity-50");
    expect(within(dimmed).getByTestId("compare-chart")).toBeInTheDocument();
    expect(within(dimmed).getByRole("group", { name: "수익률" })).toBeInTheDocument();
  });
});
