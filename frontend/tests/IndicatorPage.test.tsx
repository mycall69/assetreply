/**
 * 지표 모달의 내용 (014 T050 → 반복 2026-10-10b) — FR-010, FR-011, FR-015, FR-016, FR-018, FR-019, contracts D3·D4.
 *
 * 014 승인 2026-10-10(T111): 지표 화면이 모달로 바뀌었다 — 대상은 모달 내용 `IndicatorView`(`range`·`onClose`)다. 닫기·포커스·머리 값 갱신
 * 주기는 `IndicatorModal.test.tsx`가 본다(모달이 닫혀도 뒤의 대시보드가 갱신을 지므로 `stopPolling`을 부르지 않는다).
 *
 * - 머리 값은 대시보드와 같은 스토어(`marketQuotesStore`)다 — 다른 경로로 받으면 같은 지표의 값이 두 화면에서 다르다
 * - 기간 단추는 주소를 바꾼다(`window.history.replaceState(…, "?range=…")` — 014 승인 2026-10-10, T137: `router.replace`는 모달 내용을 다시 붙였다)
 *   — 남기지 않으면 새로고침할 때마다 처음 기간으로 돌아간다
 * - 받는 중이면 그래프 없음 + 진행(표 자리도 같은 글), 실패면 까닭 + 다시 시도, 없는 지표면 안내와 [닫기]
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorView } from "@/components/dashboard/IndicatorView";
import { ApiError, apiClient } from "@/lib/apiClient";
import { useIndicatorCommentaryStore } from "@/stores/indicatorCommentaryStore";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { useIndicatorTableStore } from "@/stores/indicatorTableStore";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { indicatorOf, quoteOf, quotesOf } from "./support/dashboardFixtures";
import { commentaryOf, tableOf } from "./support/indicatorModalFixtures";
import { collectingOf, seriesOf } from "./support/indicatorSeriesFixtures";

const router = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/components/dashboard/IndicatorChart", () => ({
  IndicatorChart: () => <div data-testid="indicator-chart" />,
}));
vi.mock("@/lib/dashboardProgressStream", () => ({ subscribeIndicatorProgress: () => () => undefined }));

// 014 승인 2026-10-10 — 모달은 표·까닭도 받는다. 받는 중·실패(202)는 그래프와 표가 같은 본문이다
function mockGet(series: unknown) {
  const pending = typeof series === "object" && series !== null && "progressUrl" in series;
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") {
      return quotesOf({ sp500: { quote: quoteOf({ value: "7765.360000", state: "closed", sessionDate: "2026-10-08" }) } });
    }
    if (path.includes("/commentary")) return commentaryOf();
    if (path.includes("/table")) return pending ? series : tableOf();
    if (path.startsWith("/api/dashboard/indicators/")) {
      if (series instanceof Error) throw series;
      return series;
    }
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

const onClose = vi.fn();

beforeEach(() => {
  router.replace.mockReset();
  onClose.mockReset();
  useMarketQuotesStore.getState().stopPolling();
  // 014 승인 2026-10-10 — 내용은 시세를 부르지 않는다(모달이 부른다) — 시세 응답을 미리 둔다
  useMarketQuotesStore.setState({
    status: "ready", error: null, seq: 0,
    data: quotesOf({ sp500: { quote: quoteOf({ value: "7765.360000", state: "closed", sessionDate: "2026-10-08" }) } }),
  });
  useIndicatorSeriesStore.getState().close();
  useIndicatorTableStore.getState().close();
  useIndicatorCommentaryStore.setState({ entries: {} });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  useIndicatorSeriesStore.getState().close();
  useIndicatorTableStore.getState().close();
  vi.restoreAllMocks();
});

describe("머리", () => {
  it("대시보드와 같은 스토어의 값과 저장된 기간", async () => {
    mockGet(seriesOf());
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "S&P 500" })).toBeInTheDocument();
    expect(screen.getByTestId("header-value")).toHaveTextContent("7,765.36");
    expect(screen.getByText(/저장된 기간 1927-12-30 ~ 2026-10-08/)).toBeInTheDocument();
    expect(screen.getByText(/출처 Yahoo Finance/)).toBeInTheDocument();
    expect(screen.getByText(/마지막 수집 13:30/)).toBeInTheDocument();
    // 014 승인 2026-10-10 — "← 대시보드로" 링크는 모달의 닫기로 바뀌었다(IndicatorModal.test). 머리 값 갱신도 그 파일이 본다
  });

  it("환율은 다른 계열임을 밝힌다", async () => {
    mockGet(seriesOf({
      indicator: { ...seriesOf().indicator, id: "usd", name: "달러", kind: "fx", group: "fx", notes: ["market_fx"] },
      history: { ...seriesOf().history, source: "ecos" },
    }));
    render(<IndicatorView id="usd" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText("ECOS 매매기준율 — 카드의 시장 환율과 다른 계열")).toBeInTheDocument());
    expect(screen.getByText(/출처 한국은행 ECOS/)).toBeInTheDocument();
  });

  it("선물은 근월물 주석", async () => {
    mockGet(seriesOf({ indicator: { ...seriesOf().indicator, id: "wti", name: "WTI 원유", kind: "future", notes: ["future_roll"] } }));
    render(<IndicatorView id="wti" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText("선물 근월물 연속 — 만기 교체로 끊김이 있을 수 있음")).toBeInTheDocument());
  });

  it("최근 구간 받는 중과 이어 받기 실패", async () => {
    mockGet(seriesOf({
      history: { ...seriesOf().history, tailPending: true,
        lastFailure: { kind: "rate_limited", message: "한도", at: "2026-10-09T05:00:00Z" } },
    }));
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: "queued" });
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText("최근 구간 받는 중")).toBeInTheDocument());
    expect(screen.getByTestId("indicator-chart")).toBeInTheDocument();
    expect(screen.getByText(/최근 이어 받기 실패 — 출처 응답 제한 · 14:00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/collect", {}));
  });
});

describe("기간", () => {
  it("기간 단추는 주소를 바꾼다", async () => {
    // 014 승인 2026-10-10 — 단위 단추(`?unit=`) → 보는 기간 단추(`?range=`)
    mockGet(seriesOf());
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    const group = screen.getByRole("group", { name: "보는 기간" });
    expect(within(group).getByRole("button", { name: "1년" })).toHaveAttribute("aria-pressed", "true");
    const replaceState = vi.spyOn(window.history, "replaceState");
    fireEvent.click(within(group).getByRole("button", { name: "5년" }));
    // 014 승인 2026-10-10 — router.replace → history.replaceState(T137 실측 — 모달 내용을 다시 붙이지 않는다)
    expect(replaceState).toHaveBeenCalledWith(null, "", "?range=5y");
    expect(router.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(within(group).getByRole("button", { name: "5년" })).toHaveAttribute("aria-pressed", "true"));
  });
});

describe("받는 중·실패·없는 지표", () => {
  it("받는 중이면 그래프 없이 진행", async () => {
    // 014 승인 2026-10-10 — 그래프 자리와 표 자리에 같은 글이다(D4)
    mockGet(collectingOf());
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getAllByText(/S&P 500 이력을 받는 중입니다/)).toHaveLength(2));
    expect(screen.getAllByText(/2010-01-04 ~ 2026-10-08 받음 \(첫 날 1927-12-30\)/)).toHaveLength(2);
    expect(screen.queryByTestId("indicator-chart")).toBeNull();
    expect(screen.queryByTestId("indicator-table")).toBeNull();
  });

  it("실패면 까닭과 다시 시도", async () => {
    mockGet(collectingOf({ status: "failed", failure: { kind: "rate_limited", message: "한도", at: "2026-10-09T04:05:00Z" } }));
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    // 014 승인 2026-10-10 — 그래프 자리와 표 자리에 같은 글·같은 다시 시도다
    await waitFor(() => expect(screen.getAllByText(/이력을 받지 못했습니다 — 출처 응답 제한/)).toHaveLength(2));
    expect(screen.getAllByRole("button", { name: "다시 시도" })).toHaveLength(2);
  });

  it("환율 그래프의 외환 수집 실패는 그 까닭과 외환 수집 기록의 문구(반복 2026-10-10 T090)", async () => {
    // 외환 수집이 실패하면 "받는 중"에 머물지 않는다. 문구는 외환 수집 기록의 것이다 — 종류 글자만으로는 무엇을 고칠지 모른다(FR-018).
    mockGet(collectingOf({
      status: "failed",
      indicator: { id: "jpy", name: "엔(100엔)" },
      failure: { kind: "fx_collection", message: "ECOS 인증키가 유효하지 않습니다.", at: "2026-10-09T13:00:00Z" },
      progressUrl: "/api/dashboard/indicators/jpy/progress",
    }));
    render(<IndicatorView id="jpy" range="1y" onClose={onClose} />);
    // 014 승인 2026-10-10 — 그래프 자리와 표 자리에 같은 글이다
    await waitFor(() => expect(screen.getAllByText(/이력을 받지 못했습니다 — 외환 수집 실패/)).toHaveLength(2));
    expect(screen.getAllByText("ECOS 인증키가 유효하지 않습니다.")).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "다시 시도" })).toHaveLength(2);
    expect(screen.queryByText(/이력을 받는 중입니다/)).toBeNull();
  });

  it("없는 지표는 안내와 닫기", async () => {
    // 014 승인 2026-10-10 — "대시보드로" 링크 → 모달의 [닫기]
    mockGet(new ApiError(404, "unknown_indicator", "없는 지표입니다"));
    render(<IndicatorView id="kospii" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText("없는 지표입니다: \"kospii\"")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "닫기" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("머리의 카드 값이 아직 없으면 —", async () => {
    // 014 승인 2026-10-10 — 내용은 시세를 부르지 않는다 — 카드 값이 없는 시세를 둔다. 표·까닭에는 그 응답을 준다
    useMarketQuotesStore.setState({ data: quotesOf({ sp500: indicatorOf("sp500", { status: "failed", quote: null }) }) });
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.includes("/commentary")) return commentaryOf();
      if (path.includes("/table")) return tableOf();
      return seriesOf();
    });
    render(<IndicatorView id="sp500" range="1y" onClose={onClose} />);
    await waitFor(() => expect(screen.getByTestId("header-value")).toHaveTextContent("—"));
  });
});
