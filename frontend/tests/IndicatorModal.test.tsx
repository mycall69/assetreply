/**
 * 지표 모달 (014 반복 2026-10-10b T106) — FR-010, FR-016, contracts D3·D4.
 *
 * - 대시보드 위에 `role="dialog"` 모달로 열린다. 머리 값은 대시보드와 같은 스토어다
 * - 닫기: Esc·바깥 누름·닫기 단추 — 가로챈 모달(대시보드 안에서 연)은 `router.back()`, 직접 연 모달은 `router.replace("/dashboard")`
 * - 닫으면(뒤로 가기로 사라져도) 포커스가 그 카드의 링크로 돌아온다 — 돌려주지 않으면 키보드 사용자가 자리를 잃는다
 * - 기간 단추는 주소의 `range`를 바꾼다 — `window.history.replaceState`다(014 승인 2026-10-10 — T137 실측: `router.replace`는 페이지 조각의
 *   질의가 바뀌어 모달 내용을 통째로 다시 붙였다 — 그래프·표를 다시 받았다)
 * - 없는 지표는 안내와 닫기다
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorModal } from "@/components/dashboard/IndicatorModal";
import { ApiError, apiClient } from "@/lib/apiClient";
import { useIndicatorCommentaryStore } from "@/stores/indicatorCommentaryStore";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { useIndicatorTableStore } from "@/stores/indicatorTableStore";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { quoteOf, quotesOf } from "./support/dashboardFixtures";
import { commentaryOf, rangeSeriesOf, tableOf } from "./support/indicatorModalFixtures";

const router = vi.hoisted(() => ({ replace: vi.fn(), back: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/components/dashboard/IndicatorChart", () => ({
  IndicatorChart: () => <div data-testid="indicator-chart" />,
}));
vi.mock("@/lib/dashboardProgressStream", () => ({ subscribeIndicatorProgress: () => () => undefined }));

function mockGet(series: unknown = rangeSeriesOf()) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") {
      return quotesOf({ sp500: { quote: quoteOf({ value: "7765.360000", state: "closed", sessionDate: "2026-10-08" }) } });
    }
    if (path.includes("/series")) {
      if (series instanceof Error) throw series;
      return series;
    }
    if (path.includes("/table")) return tableOf();
    if (path.includes("/commentary")) return commentaryOf();
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

function resetStores() {
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
  useIndicatorSeriesStore.getState().close();
  useIndicatorTableStore.getState().close();
  useIndicatorCommentaryStore.setState({ entries: {} });
}

beforeEach(() => {
  router.replace.mockReset();
  router.back.mockReset();
  resetStores();
});

afterEach(() => {
  resetStores();
  vi.restoreAllMocks();
});

describe("열기", () => {
  it("대화 상자에 머리·까닭·기간·그래프·표가 보인다", async () => {
    mockGet();
    render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "S&P 500" })).toBeInTheDocument();
    expect(screen.getByTestId("header-value")).toHaveTextContent("7,765.36");
    await waitFor(() => expect(screen.getByTestId("indicator-commentary")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("indicator-table")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "1년" })).toHaveAttribute("aria-pressed", "true");
  });

  it("머리 값을 열려 있는 동안 다시 받는다", async () => {
    mockGet();
    const start = vi.spyOn(useMarketQuotesStore.getState(), "startPolling");
    const { unmount } = render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    expect(start).toHaveBeenCalled();
    unmount();
  });

  it("기간 단추는 주소의 range를 바꾼다", async () => {
    mockGet();
    render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    const replaceState = vi.spyOn(window.history, "replaceState");
    fireEvent.click(screen.getByRole("button", { name: "5년" }));
    // 014 승인 2026-10-10 — router.replace → history.replaceState(모달을 다시 붙이지 않는다)
    expect(replaceState).toHaveBeenCalledWith(null, "", "?range=5y");
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("닫기", () => {
  it.each(["intercepted", "direct"] as const)("Esc — %s", async (mode) => {
    mockGet();
    render(<IndicatorModal id="sp500" range="1y" mode={mode} />);
    fireEvent.keyDown(document, { key: "Escape" });
    if (mode === "intercepted") expect(router.back).toHaveBeenCalledTimes(1);
    else expect(router.replace).toHaveBeenCalledWith("/dashboard", { scroll: false });
  });

  it("바깥 누름과 닫기 단추", async () => {
    mockGet();
    render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    fireEvent.mouseDown(screen.getByTestId("indicator-modal-backdrop"));
    fireEvent.click(screen.getByRole("button", { name: "지표 닫기" }));
    expect(router.back).toHaveBeenCalledTimes(2);
  });

  it("안쪽 누름은 닫지 않는다", async () => {
    mockGet();
    render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    fireEvent.mouseDown(screen.getByRole("dialog"));
    expect(router.back).not.toHaveBeenCalled();
  });

  it("사라지면 포커스가 그 카드의 링크로 돌아온다", async () => {
    mockGet();
    const card = document.createElement("li");
    card.setAttribute("data-indicator", "sp500");
    const link = document.createElement("a");
    link.href = "/dashboard/sp500";
    link.textContent = "S&P 500";
    card.appendChild(link);
    document.body.appendChild(card);
    const { unmount } = render(<IndicatorModal id="sp500" range="1y" mode="intercepted" />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    unmount();
    await waitFor(() => expect(document.activeElement).toBe(link));
    card.remove();
  });
});

describe("없는 지표", () => {
  it("안내와 닫기", async () => {
    mockGet(new ApiError(404, "unknown_indicator", "없는 지표입니다: nope"));
    render(<IndicatorModal id="nope" range="1y" mode="direct" />);
    await waitFor(() => expect(screen.getByText(/없는 지표입니다/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "지표 닫기" }));
    expect(router.replace).toHaveBeenCalledWith("/dashboard", { scroll: false });
  });
});
