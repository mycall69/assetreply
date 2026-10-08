/**
 * 비교 화면의 저장한 비교 — 끝에서 끝까지 (013 T068) — FR-012a, FR-016~FR-019, ui-wireframes F9.
 *
 * 저장 대역(`tests/support/savedComparisonStub` — `tests/setup.ts`가 건다)으로 실행 → 저장(이름 고침) → 목록 → 새로 연 화면에도 목록 → 불러오기(같은 질의)
 * → 삭제를 한 번에 본다. 흐린 동안·막힘이면 저장 단추가 꺼진다.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { apiClient } from "@/lib/apiClient";
import { useCompareStore } from "@/stores/compareStore";
import { HYNIX_T, SAMSUNG_T, XLK_T, apiError, ok } from "./support/compareFixtures";
import { savedComparisonStub } from "./support/savedComparisonStub";

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

function route(answer: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    if (path.startsWith("/api/stocks/search")) return Promise.resolve({ query: "", results: [], truncated: false, lists: [] });
    const result = answer(path);
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  }) as typeof apiClient.get);
}

const comparisonPaths = (spy: ReturnType<typeof route>) =>
  spy.mock.calls.map(([p]) => p).filter((p) => p.startsWith("/api/comparison/")).sort();

function fresh(): void {
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
}

beforeEach(() => {
  vi.restoreAllMocks();
  fresh();
  useCompareStore.setState({ start: "2020-01-02" });
  for (const t of [SAMSUNG_T, HYNIX_T, XLK_T]) useCompareStore.getState().addTarget(t);
});

const saveButton = () => screen.getByRole("button", { name: "저장" });
const savedList = () => screen.getByRole("region", { name: "저장한 비교" });

describe("저장한 비교", () => {
  it("실행 → 저장(이름 고침) → 목록 → 새로 연 화면에도 → 불러오기(같은 질의) → 삭제", async () => {
    const first = route((p) => ok(p.includes("XLK") ? XLK_T : SAMSUNG_T));
    const view = render(<ComparePage />);
    expect(await within(savedList()).findByText("아직 저장한 비교가 없습니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("table", { name: "비교 표" });
    const firstPaths = comparisonPaths(first);

    fireEvent.click(saveButton());
    const box = screen.getByRole("textbox", { name: "비교 이름" });
    expect(box).toHaveValue("주식 3개 · 2020-01-02 · 일시금");
    fireEvent.change(box, { target: { value: "반도체와 기술주" } });
    fireEvent.click(saveButton());
    expect(await within(savedList()).findByText("반도체와 기술주")).toBeInTheDocument();
    expect(savedComparisonStub.entries().map((e) => e.name)).toEqual(["반도체와 기술주"]);

    // 새로 연 화면 — 서버에서 목록을 다시 받는다.
    view.unmount();
    fresh();
    vi.restoreAllMocks();
    const again = route((p) => ok(p.includes("XLK") ? XLK_T : SAMSUNG_T));
    render(<ComparePage />);
    expect(await within(savedList()).findByText("반도체와 기술주")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "비교 표" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "반도체와 기술주 불러오기" }));
    await screen.findByRole("table", { name: "비교 표" });
    await waitFor(() => expect(comparisonPaths(again)).toEqual(firstPaths));
    expect(screen.queryByRole("status", { name: "조건이 바뀜" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "반도체와 기술주 삭제" }));
    expect(await within(savedList()).findByText("아직 저장한 비교가 없습니다.")).toBeInTheDocument();
    expect(savedComparisonStub.entries()).toEqual([]);
  });

  it("흐린 동안 저장 단추가 꺼지고 다시 실행한 뒤 저장할 수 있다", async () => {
    route(() => ok(SAMSUNG_T));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("table", { name: "비교 표" });
    expect(saveButton()).toBeEnabled();
    useCompareStore.getState().setStart("2021-01-04");
    await screen.findByRole("status", { name: "조건이 바뀜" });
    expect(saveButton()).toBeDisabled();
    expect(screen.getByText("다시 실행한 뒤 저장할 수 있습니다")).toBeInTheDocument();
    // 저장한 비교 칸은 흐리지 않는다.
    expect(screen.getByTestId("compare-result")).not.toContainElement(savedList());
  });

  it("막힘이면 저장 단추가 꺼진다", async () => {
    route((p) => (p.includes("XLK")
      ? apiError(400, "before_listing", { startableFrom: "2021-11-29", basis: "listing" }) : ok(SAMSUNG_T)));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByRole("alert", { name: "비교할 수 없습니다" });
    expect(saveButton()).toBeDisabled();
  });

  it("목록 받기 실패는 알림과 다시 시도다", async () => {
    savedComparisonStub.fail("GET");
    route(() => ok(SAMSUNG_T));
    render(<ComparePage />);
    expect(await within(savedList()).findByRole("alert")).toHaveTextContent(/받지 못했습니다/);
    savedComparisonStub.heal();
    fireEvent.click(within(savedList()).getByRole("button", { name: "다시 시도" }));
    expect(await within(savedList()).findByText("아직 저장한 비교가 없습니다.")).toBeInTheDocument();
  });
});
