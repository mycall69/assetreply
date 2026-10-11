/**
 * 대시보드 기준금리 칸 (014 반복 2026-10-11d T205) — FR-040, SC-025, contracts A14·A17·D18.
 *
 * - "환율" 묶음 바로 뒤·"원자재·변동성" 묶음 앞의 표다(지표 카드가 아니다 — 묶음 이름표 `data-group`이 없다)
 * - 다섯 행: 국기·이름·금리(`4.00%`)·전회대비(▲ 빨강·▼ 파랑·`0.00` 회색, 첫 결정 `—`)·기준 일자(한국 날짜 `09. 17.`). 글자는 서버 그대로 — 계산하지 않는다
 * - 칸은 보이는 동안 서버가 정한 주기(기본 60초)로 다시 읽고, 받는 중인 은행이 있으면 5초 뒤 다시 읽는다
 * - 은행마다 따로 실패한다 — 받아 둔 값이 있으면 그 값과 "최근 갱신 실패", 없으면 까닭과 [다시 시도](수집 깨우기 → 5초 뒤 다시 읽기)
 * - 행을 누르면 그 은행의 금리 모달 주소(`/dashboard/{은행}?range=1y`)다
 * - 지표 시세가 통째로 실패해도 칸은 보인다
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/dashboard/page";
import { apiClient } from "@/lib/apiClient";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";
import { usePolicyRateStore } from "@/stores/policyRateStore";
import { quotesOf } from "./support/dashboardFixtures";
import { BANK_ORDER, COLLECTING, ratesOf } from "./support/policyRateFixtures";

type Body = ReturnType<typeof ratesOf>;

function mockGet(rates: Body | (() => Body) = ratesOf(), quotes: unknown = quotesOf()) {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
    if (path === "/api/dashboard/quotes") {
      if (quotes instanceof Error) throw quotes;
      return quotes;
    }
    if (path === "/api/dashboard/rates") return typeof rates === "function" ? rates() : rates;
    if (path.startsWith("/api/dashboard/news/")) return new Promise(() => undefined);
    throw new Error(`예상하지 못한 요청 ${path}`);
  });
}

const rateCalls = (get: { mock: { calls: unknown[][] } }) => get.mock.calls.filter(([p]) => p === "/api/dashboard/rates").length;
const rows = () => screen.getAllByTestId("rate-row");
const row = (bank: string) => rows().find((r) => r.getAttribute("data-rate") === bank) as HTMLElement;

// 기준 일자의 "올해"는 한국 날짜다 — 시계를 2026-10-11 18:40(한국)에 둔다(날짜만 — 타이머는 진짜다)
const NOW = new Date("2026-10-11T09:40:00Z");

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  useMarketQuotesStore.getState().stopPolling();
  useMarketQuotesStore.setState({ status: "idle", data: null, error: null, seq: 0 });
  usePolicyRateStore.getState().stopPolling();
  usePolicyRateStore.setState({ status: "idle", data: null, error: null, seq: 0 });
});

afterEach(() => {
  useMarketQuotesStore.getState().stopPolling();
  usePolicyRateStore.getState().stopPolling();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("자리와 행", () => {
  it("환율 묶음 바로 뒤·원자재·변동성 앞이다", async () => {
    mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    const labels = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    const at = labels.indexOf("기준금리");
    expect(labels[at - 1]).toBe("환율");
    expect(labels[at + 1]).toBe("원자재·변동성");
    // 지표 묶음이 아니다 — 묶음 다섯은 그대로다
    expect(screen.getByRole("region", { name: "기준금리" })).not.toHaveAttribute("data-group");
  });

  it("다섯 행이 차례대로 국기·이름·금리·전회대비·기준 일자", async () => {
    mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(rows().map((r) => r.getAttribute("data-rate"))).toEqual(BANK_ORDER);
    const fed = row("fed");
    expect(within(fed).getByText("미국연방준비은행")).toBeInTheDocument();
    expect(within(fed).getByText("🇺🇸")).toHaveAttribute("aria-hidden", "true");
    expect(within(fed).getByTestId("rate-value")).toHaveTextContent("4.00%");
    expect(within(fed).getByTestId("rate-change")).toHaveTextContent("▲ 0.25");
    expect(within(fed).getByTestId("rate-change")).toHaveClass("text-red-700");
    expect(within(fed).getByTestId("rate-date")).toHaveTextContent("09. 17.");
    expect(within(row("ecb")).getByTestId("rate-change")).toHaveTextContent("▼ 0.25");
    expect(within(row("ecb")).getByTestId("rate-change")).toHaveClass("text-blue-700");
    expect(within(row("boe")).getByTestId("rate-change")).toHaveTextContent(/^0\.00$/);
    expect(within(row("boe")).getByTestId("rate-change")).toHaveClass("text-gray-500");
    expect(screen.getByText("결정일은 한국 시간 · 출처 네이버 증권")).toBeInTheDocument();
  });

  it("첫 결정이면 전회대비가 —, 마이너스 금리는 그대로", async () => {
    mockGet(ratesOf({ boj: { rate: "-0.10", change: null, direction: null } }));
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(within(row("boj")).getByTestId("rate-value")).toHaveTextContent("-0.10%");
    expect(within(row("boj")).getByTestId("rate-change")).toHaveTextContent("—");
  });

  it("올해가 아닌 결정일은 연도를 붙인다", async () => {
    mockGet(ratesOf({ boe: { decidedOn: "2025-12-18" } }));
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(within(row("boe")).getByTestId("rate-date")).toHaveTextContent("25. 12. 18.");
    expect(within(row("boe")).getByTestId("rate-date")).toHaveAttribute("title", "2025. 12. 18.");
  });

  it("행을 누르면 그 은행의 금리 모달 주소", async () => {
    mockGet();
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    const link = within(row("bok")).getByRole("link", { name: "한국은행 금리 추이 보기" });
    expect(link).toHaveAttribute("href", "/dashboard/bok?range=1y");
  });

  it("지표 시세가 통째로 실패해도 칸은 보인다", async () => {
    mockGet(ratesOf(), new Error("시세 경로 실패"));
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(screen.getByRole("region", { name: "기준금리" })).toBeInTheDocument();
  });
});

describe("받는 중·실패", () => {
  it("받는 중인 행", async () => {
    mockGet(ratesOf({ bok: COLLECTING }));
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(within(row("bok")).getByTestId("rate-value")).toHaveTextContent("받는 중…");
    expect(within(row("bok")).getByTestId("rate-change")).toHaveTextContent("—");
  });

  it("받아 둔 값이 있으면 그 값과 최근 갱신 실패", async () => {
    mockGet(ratesOf({ fed: { failure: { kind: "connection", message: "연결 실패", at: "2026-10-11T09:40:00Z" } } }));
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(within(row("fed")).getByTestId("rate-value")).toHaveTextContent("4.00%");
    expect(screen.getByTestId("rate-stale-fed")).toHaveTextContent("최근 갱신 실패 — 연결 실패 · 18:40");
  });

  it("받아 둔 값이 없으면 까닭과 [다시 시도] — 수집을 깨운다", async () => {
    mockGet(ratesOf({
      boe: { ...COLLECTING, state: "failed", failure: { kind: "blocked", message: "막힘", at: "2026-10-11T09:40:00Z" } },
    }));
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ accepted: true });
    render(<DashboardPage />);
    await waitFor(() => expect(rows()).toHaveLength(5));
    expect(within(row("boe")).getByTestId("rate-value")).toHaveTextContent("출처가 막음");
    fireEvent.click(within(row("boe")).getByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/dashboard/rates/collect", {}));
  });
});

describe("다시 읽기", () => {
  it("모두 받았으면 서버가 정한 주기, 받는 중이 있으면 5초", async () => {
    vi.useFakeTimers({ now: NOW });
    let body = ratesOf({ bok: COLLECTING }, 60);
    const get = mockGet(() => body);
    const store = usePolicyRateStore.getState();
    await act(async () => {
      await store.load();
      store.startPolling();
    });
    expect(rateCalls(get)).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(4_999); });
    expect(rateCalls(get)).toBe(1);
    body = ratesOf({}, 60);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(rateCalls(get)).toBe(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(59_999); });
    expect(rateCalls(get)).toBe(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(rateCalls(get)).toBe(3);
  });

  it("보이지 않는 동안은 읽지 않는다", async () => {
    vi.useFakeTimers({ now: NOW });
    const get = mockGet(ratesOf({}, 60));
    const store = usePolicyRateStore.getState();
    await act(async () => {
      await store.load();
      store.startPolling();
    });
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(rateCalls(get)).toBe(1);
    visibility.mockReturnValue("visible");
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(rateCalls(get)).toBe(2);
  });

  it("[다시 시도]는 깨운 뒤 5초 뒤에 다시 읽는다", async () => {
    vi.useFakeTimers({ now: NOW });
    const get = mockGet(ratesOf({}, 60));
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ accepted: true });
    const store = usePolicyRateStore.getState();
    await act(async () => { await store.load(); });
    await act(async () => { await store.retry(); });
    expect(post).toHaveBeenCalledTimes(1);
    expect(rateCalls(get)).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(rateCalls(get)).toBe(2);
  });

  it("늦게 온 옛 응답은 버린다", async () => {
    let release: (b: Body) => void = () => undefined;
    let first = true;
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path !== "/api/dashboard/rates") throw new Error(path);
      if (first) {
        first = false;
        return new Promise<Body>((resolve) => { release = resolve; });
      }
      return ratesOf({ fed: { rate: "4.25" } });
    });
    const store = usePolicyRateStore.getState();
    const slow = store.load();
    await act(async () => { await store.load(); });
    release(ratesOf({ fed: { rate: "3.00" } }));
    await act(async () => { await slow; });
    expect(usePolicyRateStore.getState().data?.banks[0].rate).toBe("4.25");
  });
});

describe("계산하지 않는다", () => {
  it.each(["src/stores/policyRateStore.ts", "src/components/dashboard/PolicyRateTable.tsx"])("%s 에 숫자 변환이 없다", (file) => {
    const body = readFileSync(resolve(__dirname, "..", file), "utf-8");
    expect(body).not.toMatch(/\b(Number|parseFloat|parseInt)\(/);
  });
});
