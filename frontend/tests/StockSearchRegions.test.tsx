/**
 * 국내·미국 / 일본 두 영역 (T028) — 006 FR-027, SC-001, SC-015, research R6-5, R6-12.
 *
 * **로컬 결과가 외부 검색을 기다리면 안 된다.** 한꺼번에 내려고 일본 응답을 기다리는 순간 로컬
 * 목록을 둔 이유(속도)가 사라지고, 외부 출처가 막히면 국내·미국 종목까지 찾을 수 없게 된다.
 */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  EXTERNAL_DEBOUNCE_MS,
  LOCAL_DEBOUNCE_MS,
  StockSearch,
} from "@/components/stock/StockSearch";
import { ApiError } from "@/lib/apiClient";
import {
  SAMSUNG,
  TOYOTA,
  external,
  local,
  pending,
  routeGet,
} from "./support/stockSearchFixtures";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

const localRegion = () => screen.getByRole("region", { name: "국내·미국" });
const japanRegion = () => screen.getByRole("region", { name: "일본" });

async function typeAndWait(text: string, ms: number) {
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: text } });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("입력 대기", () => {
  it("로컬은 150ms, 일본은 300ms 뒤에 부른다", async () => {
    // SC-001의 0.5초는 입력 대기를 포함한다. 005의 300ms는 예산의 60%를 쓴다 (R6-5).
    expect(LOCAL_DEBOUNCE_MS).toBe(150);
    expect(EXTERNAL_DEBOUNCE_MS).toBe(300);

    const get = routeGet({});
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("삼성", LOCAL_DEBOUNCE_MS - 1);
    expect(get).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(get).toHaveBeenCalledTimes(1);
    expect(get.mock.calls[0][0]).toBe(`/api/stocks/search?q=${encodeURIComponent("삼성")}`);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EXTERNAL_DEBOUNCE_MS - LOCAL_DEBOUNCE_MS);
    });
    expect(get).toHaveBeenCalledTimes(2);
    expect(get.mock.calls[1][0]).toBe(
      `/api/stocks/search/external?q=${encodeURIComponent("삼성")}`);
  });
});

describe("영역 분리", () => {
  it("로컬 결과는 일본 검색을 기다리지 않고 먼저 그려진다", async () => {
    // FR-027.
    routeGet({
      local: () => Promise.resolve(local([SAMSUNG])),
      external: () => pending(),
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("삼성", EXTERNAL_DEBOUNCE_MS + 10);

    expect(within(localRegion()).getByRole("option", { name: /삼성전자/ })).toBeInTheDocument();
    expect(within(japanRegion()).getByText(/검색 중/)).toBeInTheDocument();
  });

  it("일본 검색이 실패해도 로컬 영역은 그대로이고 실패는 일본 영역에만 보인다", async () => {
    // SC-015.
    routeGet({
      local: () => Promise.resolve(local([SAMSUNG])),
      external: () => Promise.reject(
        new ApiError(502, "source_unavailable", "시세 출처가 응답하지 않습니다.")),
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("삼성", EXTERNAL_DEBOUNCE_MS + 10);

    expect(within(japanRegion()).getByRole("alert").textContent)
      .toContain("시세 출처가 응답하지 않습니다");
    expect(within(localRegion()).queryByRole("alert")).toBeNull();
    expect(within(localRegion()).getByRole("option", { name: /삼성전자/ })).toBeInTheDocument();
  });

  it("로컬이 실패해도 일본 결과는 보인다", async () => {
    routeGet({
      local: () => Promise.reject(new Error("연결 실패")),
      external: () => Promise.resolve(external([TOYOTA])),
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("toyota", EXTERNAL_DEBOUNCE_MS + 10);

    expect(within(japanRegion()).getByRole("option", { name: /Toyota/ })).toBeInTheDocument();
    expect(within(japanRegion()).queryByRole("alert")).toBeNull();
    expect(within(localRegion()).getByRole("alert")).toBeInTheDocument();
  });

  it("일본 결과에도 시장과 통화를 보인다", async () => {
    routeGet({ external: () => Promise.resolve(external([TOYOTA])) });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("toyota", EXTERNAL_DEBOUNCE_MS + 10);
    const option = within(japanRegion()).getByRole("option", { name: /Toyota/ });
    expect(option.textContent).toContain("TSE");
    expect(option.textContent).toContain("JPY");
  });

  it("검색어를 지우면 두 영역을 함께 닫는다", async () => {
    routeGet({
      local: () => Promise.resolve(local([SAMSUNG])),
      external: () => Promise.resolve(external([TOYOTA])),
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await typeAndWait("삼성", EXTERNAL_DEBOUNCE_MS + 10);
    await typeAndWait("", EXTERNAL_DEBOUNCE_MS + 10);
    expect(screen.queryByRole("region", { name: "국내·미국" })).toBeNull();
    expect(screen.queryByRole("region", { name: "일본" })).toBeNull();
  });
});
