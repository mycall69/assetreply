/**
 * 지표 화면 (014 T050) — FR-010, FR-011, FR-015, FR-016, FR-018, FR-019, contracts D3·D4.
 *
 * - 머리 값은 대시보드와 같은 스토어(`marketQuotesStore`)다 — 다른 경로로 받으면 같은 지표의 값이 두 화면에서 다르다
 * - 단위 단추는 주소를 바꾼다(`router.replace("?unit=…", { scroll: false })`) — 남기지 않으면 새로고침할 때마다 "일"로 돌아간다
 * - 받는 중이면 그래프 없음 + 진행, 실패면 까닭 + 다시 시도, 없는 지표면 안내
 * - 머리 값도 열려 있는 동안 다시 받는다(U1)
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IndicatorView } from "@/components/dashboard/IndicatorView";
import { ApiError, apiClient } from "@/lib/apiClient";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { indicatorOf, quoteOf, quotesOf } from "./support/dashboardFixtures";
import { collectingOf, seriesOf } from "./support/indicatorSeriesFixtures";

const router = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/components/dashboard/IndicatorChart", () => ({
  IndicatorChart: () => <div data-testid="indicator-chart" />,
}));
vi.mock("@/lib/dashboardProgressStream", () => ({ subscribeIndicatorProgress: () => () => undefined }));

function mockGet(series: unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") {
      return quotesOf({ sp500: { quote: quoteOf({ value: "7765.360000", state: "closed", sessionDate: "2026-10-08" }) } });
    }
    if (path.startsWith("/api/dashboard/indicators/")) {
      if (series instanceof Error) throw series;
      return series;
    }
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

beforeEach(() => {
  router.replace.mockReset();
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
  useIndicatorSeriesStore.getState().close();
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  useIndicatorSeriesStore.getState().close();
  vi.restoreAllMocks();
});

describe("머리", () => {
  it("대시보드와 같은 스토어의 값과 저장된 기간", async () => {
    mockGet(seriesOf());
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "S&P 500" })).toBeInTheDocument();
    expect(screen.getByTestId("header-value")).toHaveTextContent("7,765.36");
    expect(screen.getByText(/저장된 기간 1927-12-30 ~ 2026-10-08/)).toBeInTheDocument();
    expect(screen.getByText(/출처 Yahoo Finance/)).toBeInTheDocument();
    expect(screen.getByText(/마지막 수집 13:30/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← 대시보드로" })).toHaveAttribute("href", "/dashboard");
  });

  it("머리 값도 열려 있는 동안 다시 받는다", async () => {
    mockGet(seriesOf());
    const start = vi.spyOn(useMarketQuotesStore.getState(), "startPolling");
    const stop = vi.spyOn(useMarketQuotesStore.getState(), "stopPolling");
    const { unmount } = render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(start).toHaveBeenCalled());
    unmount();
    expect(stop).toHaveBeenCalled();
  });

  it("환율은 다른 계열임을 밝힌다", async () => {
    mockGet(seriesOf({
      indicator: { ...seriesOf().indicator, id: "usd", name: "달러", kind: "fx", group: "fx", notes: ["market_fx"] },
      history: { ...seriesOf().history, source: "ecos" },
    }));
    render(<IndicatorView id="usd" unit="daily" />);
    await waitFor(() => expect(screen.getByText("ECOS 매매기준율 — 카드의 시장 환율과 다른 계열")).toBeInTheDocument());
    expect(screen.getByText(/출처 한국은행 ECOS/)).toBeInTheDocument();
  });

  it("선물은 근월물 주석", async () => {
    mockGet(seriesOf({ indicator: { ...seriesOf().indicator, id: "wti", name: "WTI 원유", kind: "future", notes: ["future_roll"] } }));
    render(<IndicatorView id="wti" unit="daily" />);
    await waitFor(() => expect(screen.getByText("선물 근월물 연속 — 만기 교체로 끊김이 있을 수 있음")).toBeInTheDocument());
  });

  it("최근 구간 받는 중과 이어 받기 실패", async () => {
    mockGet(seriesOf({
      history: { ...seriesOf().history, tailPending: true,
        lastFailure: { kind: "rate_limited", message: "한도", at: "2026-10-09T05:00:00Z" } },
    }));
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: "queued" });
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByText("최근 구간 받는 중")).toBeInTheDocument());
    expect(screen.getByTestId("indicator-chart")).toBeInTheDocument();
    expect(screen.getByText(/최근 이어 받기 실패 — 출처 응답 제한 · 14:00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/dashboard/indicators/sp500/collect", {}));
  });
});

describe("단위", () => {
  it("단위 단추는 주소를 바꾼다", async () => {
    mockGet(seriesOf());
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByTestId("indicator-chart")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "일" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "월" }));
    expect(router.replace).toHaveBeenCalledWith("?unit=monthly", { scroll: false });
    await waitFor(() => expect(screen.getByRole("button", { name: "월" })).toHaveAttribute("aria-pressed", "true"));
  });
});

describe("받는 중·실패·없는 지표", () => {
  it("받는 중이면 그래프 없이 진행", async () => {
    mockGet(collectingOf());
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByText(/S&P 500 이력을 받는 중입니다/)).toBeInTheDocument());
    expect(screen.getByText(/2010-01-04 ~ 2026-10-08 받음 \(첫 날 1927-12-30\)/)).toBeInTheDocument();
    expect(screen.queryByTestId("indicator-chart")).toBeNull();
  });

  it("실패면 까닭과 다시 시도", async () => {
    mockGet(collectingOf({ status: "failed", failure: { kind: "rate_limited", message: "한도", at: "2026-10-09T04:05:00Z" } }));
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByText(/이력을 받지 못했습니다 — 출처 응답 제한/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it("환율 그래프의 외환 수집 실패는 그 까닭과 외환 수집 기록의 문구(반복 2026-10-10 T090)", async () => {
    // 외환 수집이 실패하면 "받는 중"에 머물지 않는다. 문구는 외환 수집 기록의 것이다 — 종류 글자만으로는 무엇을 고칠지 모른다(FR-018).
    mockGet(collectingOf({
      status: "failed",
      indicator: { id: "jpy", name: "엔(100엔)" },
      failure: { kind: "fx_collection", message: "ECOS 인증키가 유효하지 않습니다.", at: "2026-10-09T13:00:00Z" },
      progressUrl: "/api/dashboard/indicators/jpy/progress",
    }));
    render(<IndicatorView id="jpy" unit="daily" />);
    await waitFor(() => expect(screen.getByText(/이력을 받지 못했습니다 — 외환 수집 실패/)).toBeInTheDocument());
    expect(screen.getByText("ECOS 인증키가 유효하지 않습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
    expect(screen.queryByText(/이력을 받는 중입니다/)).toBeNull();
  });

  it("없는 지표는 안내와 대시보드 링크", async () => {
    mockGet(new ApiError(404, "unknown_indicator", "없는 지표입니다"));
    render(<IndicatorView id="kospii" unit="daily" />);
    await waitFor(() => expect(screen.getByText("없는 지표입니다: \"kospii\"")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "대시보드로" })).toHaveAttribute("href", "/dashboard");
  });

  it("머리의 카드 값이 아직 없으면 —", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path === "/api/dashboard/quotes") return quotesOf({ sp500: indicatorOf("sp500", { status: "failed", quote: null }) });
      return seriesOf();
    });
    render(<IndicatorView id="sp500" unit="daily" />);
    await waitFor(() => expect(screen.getByTestId("header-value")).toHaveTextContent("—"));
  });
});
