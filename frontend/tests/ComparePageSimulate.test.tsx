/**
 * 비교 화면의 투자 시뮬레이션 모달 — 끝에서 끝까지 (013 반복 2026-10-09b T099) — FR-011b, FR-012a, FR-020, SC-011.
 *
 * 실행 → 줄의 "투자 시뮬레이션" → 모달(메뉴 경로를 그 줄의 조건으로) → 닫기 → 비교 화면 그대로. 흐린 동안에도 열리고 그 줄을 낸 실행의 조건으로
 * 부른다. 이력을 쓰지 않고 메뉴 스토어를 건드리지 않는다.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { useCompareDetailStore } from "@/stores/compareDetailStore";
import { useCompareStore } from "@/stores/compareStore";
import { useStockStore } from "@/stores/stockStore";
import { SERIES, STOCK_LUMP } from "./support/compareDetailFixtures";
import { HYNIX_T, SAMSUNG_T, ok, routeCompare } from "./support/compareFixtures";
import { historyStub } from "./support/historyStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
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

// 014 승인 2026-10-10(반복 2026-10-10e T152) — 투자 비교의 주식·가상자산 이름은 이름(티커)다(FR-032) — 아래의 단추 이름
function route() {
  return routeCompare((path) => {
    if (path.startsWith("/api/stocks/search")) return { query: "", results: [], truncated: false, lists: [] };
    if (path.startsWith("/api/comparison/")) return ok(path.includes("000660") ? HYNIX_T : SAMSUNG_T);
    if (path.includes("/series")) return SERIES;
    if (path.startsWith("/api/stocks/simulation?")) return STOCK_LUMP;
    return undefined;
  });
}

const menuCalls = (spy: ReturnType<typeof route>) =>
  spy.mock.calls.map(([p]) => p).filter((p) => p.startsWith("/api/stocks/simulation"));

beforeEach(() => {
  vi.restoreAllMocks();
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02" });
  for (const t of [SAMSUNG_T, HYNIX_T]) useCompareStore.getState().addTarget(t);
});

describe("투자 시뮬레이션 모달", () => {
  it("줄의 단추를 누르면 그 메뉴의 결과가 모달로 뜨고, 닫으면 비교 화면 그대로다", async () => {
    const get = route();
    const menuBefore = useStockStore.getState();
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("table", { name: "비교 표" });

    fireEvent.click(screen.getByRole("button", { name: "삼성전자(005930) 투자 시뮬레이션" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByTestId("simulation-modal-board");
    expect(within(dialog).getByTestId("simulation-modal-table")).toHaveTextContent("2021-08-31");
    expect(menuCalls(get)).toContain("/api/stocks/simulation?market=KRX&symbol=005930.KS&start=2020-01-02"
      + "&principal=10000000&principalCurrency=KRW&reinvest=true");

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("table", { name: "비교 표" })).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "삼성전자(005930) 투자 시뮬레이션" }));

    // 이력을 쓰지 않고 메뉴 스토어를 건드리지 않는다(FR-020).
    expect(historyStub.calls().filter((c) => c.method === "PUT")).toEqual([]);
    const menuAfter = useStockStore.getState();
    expect([menuAfter.input, menuAfter.summary, menuAfter.rows]).toEqual([menuBefore.input, menuBefore.summary, menuBefore.rows]);
  });

  it("열 때 다른 칸에 포커스가 있었어도 닫으면 그 줄의 단추로 돌아온다", async () => {
    // T104 실측 — 검색 칸에 포커스가 남은 채 단추를 누르면(단추가 포커스를 받지 못하는 경우) 닫은 뒤 검색 칸으로 돌아갔다.
    route();
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("table", { name: "비교 표" });
    screen.getByRole("searchbox").focus();
    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스(000660) 투자 시뮬레이션" }));
    await screen.findByRole("dialog");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "SK하이닉스(000660) 투자 시뮬레이션" }));
  });

  it("흐린 동안에도 열리고 그 줄을 낸 실행의 조건으로 부른다", async () => {
    const get = route();
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("table", { name: "비교 표" });
    useCompareStore.getState().setStart("2021-01-04");
    await screen.findByRole("status", { name: "조건이 바뀜" });

    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스(000660) 투자 시뮬레이션" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("simulation-modal-condition")).toHaveTextContent("시작일 2020-01-02");
    const calls = menuCalls(get);
    expect(calls.some((p) => p.includes("symbol=000660.KS") && p.includes("start=2020-01-02"))).toBe(true);
    expect(calls.some((p) => p.includes("start=2021-01-04"))).toBe(false);
  });
});
