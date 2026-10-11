/**
 * 금리 모달 (014 반복 2026-10-11d T205) — FR-041, FR-042, SC-026, contracts A15·A16·D18.
 *
 * 지표 모달과 같은 주소 있는 모달(`/dashboard/{은행}?range=`)이다 — 껍데기(`IndicatorModal`)를 함께 쓰고 은행이면 금리 화면을 그린다.
 *
 * - 머리: 이름·금리 종류·현재 금리·전회대비·결정일(실제 시각이면 한국 시각)·다음 결정 예정·저장된 기간·출처
 * - 변화 까닭: 지표 까닭과 같은 줄 — 없으면 "최근 결정을 다룬 기사를 찾지 못했습니다"
 * - 그래프: **계단선**(`lineType: 1`)·결정 점, 점은 옛것부터. 기간 넷(1년·5년·10년·모두 — 처음 1년)은 마지막 결정에서 거꾸로 센 처음 보이는 범위다.
 *   두 지점 확대·[리셋] = 그 기간의 처음 범위, 기간을 바꾸면 주소의 `range`(`history.replaceState`)
 * - 표 "금리 추이": 맨 위 다음 결정 예정 행(— · —), 그 아래 결정 전부(최신부터), 전회대비 색
 * - 닫으면 그 은행 행으로 포커스가 돌아온다. 금리에 없는 기간(`20y` 등)은 1년이다
 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorModal } from "@/components/dashboard/IndicatorModal";
import { apiClient } from "@/lib/apiClient";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { usePolicyRateStore } from "@/stores/policyRateStore";
import { useThemeStore } from "@/stores/themeStore";
import { quotesOf } from "./support/dashboardFixtures";
import { BOK_DECISIONS, detailOf, rateCommentaryOf, ratesOf } from "./support/policyRateFixtures";

const router = vi.hoisted(() => ({ replace: vi.fn(), back: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const chart = vi.hoisted(() => ({
  created: 0,
  options: [] as Record<string, unknown>[],
  data: [] as unknown[][],
  move: null as null | ((param: unknown) => void),
  logical: [] as { from: number; to: number }[],
  visible: [] as { from: unknown; to: unknown }[],
  fit: 0,
}));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => {
    chart.created += 1;
    return {
      addSeries: (_: unknown, options: Record<string, unknown>) => {
        chart.options.push(options);
        return { setData: (d: unknown[]) => { chart.data.push(d); } };
      },
      subscribeCrosshairMove: (handler: (param: unknown) => void) => { chart.move = handler; },
      timeScale: () => ({
        fitContent: () => { chart.fit += 1; },
        setVisibleLogicalRange: (r: { from: number; to: number }) => { chart.logical.push(r); },
        setVisibleRange: (r: { from: unknown; to: unknown }) => { chart.visible.push(r); },
        coordinateToTime: () => null,
      }),
      priceScale: () => ({ width: () => 50 }),
      remove: () => undefined,
    };
  },
}));

function mockGet(detail: unknown = detailOf(), commentary: unknown = rateCommentaryOf()) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") return quotesOf();
    if (path === "/api/dashboard/rates") return ratesOf();
    if (path === "/api/dashboard/rates/bok") return detail;
    if (path === "/api/dashboard/rates/bok/commentary") return commentary;
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

beforeEach(() => {
  router.replace.mockReset();
  router.back.mockReset();
  Object.assign(chart, { created: 0, options: [], data: [], move: null, logical: [], visible: [], fit: 0 });
  useThemeStore.setState({ theme: "light" });
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
  usePolicyRateStore.getState().stopPolling();
  usePolicyRateStore.setState({ status: "idle", data: null, error: null, seq: 0, details: {}, commentary: {} });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  usePolicyRateStore.getState().stopPolling();
  vi.restoreAllMocks();
});

async function open(range: "1y" | "5y" | "10y" | "all" | "20y" = "1y") {
  render(<IndicatorModal id="bok" range={range as "1y"} mode="intercepted" />);
  await waitFor(() => expect(screen.getAllByTestId("rate-table-row").length).toBeGreaterThan(1));
}

describe("머리", () => {
  it("이름·금리 종류·금리·전회대비·결정·다음 결정·저장된 기간·출처", async () => {
    mockGet();
    await open();
    expect(screen.getByRole("dialog", { name: "한국은행" })).toBeInTheDocument();
    const head = screen.getByTestId("rate-header");
    expect(within(head).getByText("기준금리")).toBeInTheDocument();
    expect(within(head).getByTestId("rate-header-value")).toHaveTextContent("3.00%");
    expect(within(head).getByTestId("rate-header-change")).toHaveTextContent("▲ 0.25");
    expect(within(head).getByTestId("rate-header-change")).toHaveClass("text-red-700");
    expect(head).toHaveTextContent("결정 2026. 08. 27. 10:00(한국)");
    expect(head).toHaveTextContent("다음 결정 예정 2026. 10. 22.");
    expect(head).toHaveTextContent("저장된 기간 2016. 01. 14. ~ 2026. 08. 27. · 출처 네이버 증권");
  });

  it("발표 시각이 자리 표시면 날짜만, 다음 결정이 없으면 뺀다", async () => {
    mockGet(detailOf({ announcedAt: null, nextMeetingOn: null }));
    await open();
    const head = screen.getByTestId("rate-header");
    expect(head).toHaveTextContent("결정 2026. 08. 27.");
    expect(head).not.toHaveTextContent("(한국)");
    expect(head).not.toHaveTextContent("다음 결정 예정");
  });

  it("받는 중이면 그래프·표 대신 받는 중", async () => {
    mockGet(detailOf({ state: "collecting", rate: null, change: null, direction: null, decidedOn: null, decisions: [],
      firstDecidedOn: null, lastDecidedOn: null }));
    render(<IndicatorModal id="bok" range="1y" mode="intercepted" />);
    await waitFor(() => expect(screen.getByText("결정 이력을 받는 중…")).toBeInTheDocument());
    expect(screen.queryByTestId("rate-chart")).toBeNull();
  });
});

describe("변화 까닭", () => {
  it("기사 줄 — 새 탭", async () => {
    mockGet();
    await open();
    const section = screen.getByTestId("indicator-commentary");
    const link = within(section).getByRole("link", { name: "[속보]한은 금리 인상 결정에 찬물…7000피 탈환 다음으로" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("없으면 최근 결정을 다룬 기사를 찾지 못했습니다", async () => {
    mockGet(detailOf(), rateCommentaryOf({ status: "none", items: [] }));
    await open();
    await waitFor(() => expect(screen.getByText("최근 결정을 다룬 기사를 찾지 못했습니다")).toBeInTheDocument());
  });
});

describe("그래프", () => {
  it("계단선·결정 점, 점은 옛것부터", async () => {
    mockGet();
    await open();
    expect(chart.options[0]).toMatchObject({ lineType: 1, pointMarkersVisible: true });
    const points = chart.data[0] as { time: string; value: number }[];
    expect(points.map((p) => p.time)).toEqual([...BOK_DECISIONS].reverse().map((d) => d.decidedOn));
    expect(points.at(-1)?.value).toBe(3);
  });

  it("처음 1년 — 마지막 결정에서 1년 거꾸로", async () => {
    mockGet();
    await open();
    // 옛것부터 [2016-01-14, 2020-05-28, 2025-05-29, 2025-10-23, 2026-05-28, 2026-07-16, 2026-08-27] — 2025-08-27 이상 첫 점은 차례 3
    expect(chart.logical.at(-1)).toEqual({ from: 3, to: 6 });
  });

  it("기간 넷 — 바꾸면 주소의 range와 처음 범위, 모두는 전체", async () => {
    mockGet();
    const replaceState = vi.spyOn(window.history, "replaceState");
    await open();
    const group = screen.getByRole("group", { name: "보는 기간" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["1년", "5년", "10년", "모두"]);
    expect(within(group).getByRole("button", { name: "1년" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(group).getByRole("button", { name: "5년" }));
    expect(replaceState).toHaveBeenCalledWith(null, "", "?range=5y");
    expect(chart.logical.at(-1)).toEqual({ from: 2, to: 6 });
    const fitted = chart.fit;
    fireEvent.click(within(group).getByRole("button", { name: "모두" }));
    expect(chart.fit).toBe(fitted + 1);
  });

  it("금리에 없는 기간은 1년이다", async () => {
    mockGet();
    await open("20y");
    expect(within(screen.getByRole("group", { name: "보는 기간" })).getByRole("button", { name: "1년" }))
      .toHaveAttribute("aria-pressed", "true");
  });

  it("두 지점 확대·[리셋]은 그 기간의 처음 범위", async () => {
    mockGet();
    await open();
    const canvas = screen.getByTestId("rate-canvas");
    for (const time of ["2025-10-23", "2026-07-16"]) {
      act(() => chart.move?.({ time, point: { x: 10, y: 10 } }));
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 40 });
      fireEvent.click(canvas, { clientX: 100, clientY: 40 });
    }
    expect(chart.visible).toEqual([{ from: "2025-10-23", to: "2026-07-16" }]);
    const fitted = chart.fit;
    fireEvent.click(screen.getByRole("button", { name: "리셋" }));
    expect(chart.logical.at(-1)).toEqual({ from: 3, to: 6 });
    expect(chart.fit).toBe(fitted);
  });

  it("커서 상자 — 결정일·금리·전회대비", async () => {
    mockGet();
    await open();
    act(() => chart.move?.({ time: "2025-05-29", point: { x: 10, y: 10 } }));
    const tip = screen.getByTestId("rate-tooltip");
    expect(tip).toHaveTextContent("2025. 05. 29.");
    expect(tip).toHaveTextContent("2.50%");
    expect(tip).toHaveTextContent("▼ 0.25");
  });

  it("블랙 배경으로 바꾸면 다시 그린다", async () => {
    mockGet();
    await open();
    const before = chart.created;
    act(() => useThemeStore.setState({ theme: "dark" }));
    expect(chart.created).toBe(before + 1);
  });
});

describe("금리 추이 표", () => {
  it("맨 위 다음 결정 예정, 그 아래 결정 전부(최신부터)", async () => {
    mockGet();
    await open();
    const lines = screen.getAllByTestId("rate-table-row");
    expect(lines).toHaveLength(BOK_DECISIONS.length + 1);
    expect(lines[0]).toHaveTextContent("2026. 10. 22.");
    expect(lines[0]).toHaveTextContent("다음 결정 예정");
    expect(within(lines[0]).getAllByText("—")).toHaveLength(2);
    expect(lines[1]).toHaveTextContent("2026. 08. 27.");
    expect(within(lines[1]).getByText("3.00")).toBeInTheDocument();
    expect(within(lines[1]).getByTestId("rate-table-change")).toHaveTextContent("▲ 0.25");
    expect(within(lines[1]).getByTestId("rate-table-change")).toHaveClass("text-red-700");
    expect(within(lines[3]).getByTestId("rate-table-change")).toHaveClass("text-gray-500");
    expect(within(lines[5]).getByTestId("rate-table-change")).toHaveClass("text-blue-700");
    expect(within(lines.at(-1) as HTMLElement).getByTestId("rate-table-change")).toHaveTextContent("—");
  });

  it("다음 결정 예정이 없으면 그 행이 없다", async () => {
    mockGet(detailOf({ nextMeetingOn: null }));
    await open();
    expect(screen.getAllByTestId("rate-table-row")).toHaveLength(BOK_DECISIONS.length);
  });
});

describe("닫기", () => {
  it("닫으면 그 은행 행으로 포커스가 돌아온다", async () => {
    mockGet();
    const view = render(
      <>
        <div data-rate="bok"><a href="#bok">한국은행</a></div>
        <IndicatorModal id="bok" range="1y" mode="intercepted" />
      </>,
    );
    await waitFor(() => expect(screen.getAllByTestId("rate-table-row").length).toBeGreaterThan(1));
    fireEvent.click(screen.getByRole("button", { name: "지표 닫기" }));
    expect(router.back).toHaveBeenCalledTimes(1);
    view.rerender(<div data-rate="bok"><a href="#bok">한국은행</a></div>);
    expect(document.activeElement).toBe(screen.getByRole("link", { name: "한국은행" }));
  });
});
