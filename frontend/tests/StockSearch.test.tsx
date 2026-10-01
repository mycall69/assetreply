/**
 * 종목 검색 (T031) — 005 FR-002a, FR-002b, SC-030, SC-031.
 *
 * **코드를 직접 입력하게 하지 않는다.** 시장별 코드 체계(6자리 숫자·알파벳 티커·
 * 4자리 숫자)를 사용자가 알아야 하고, **오타와 "없는 종목"을 구별할 수 없다** —
 * 둘 다 "시세를 얻을 수 없음"으로 보이는데 사용자가 할 일은 정반대다.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import { apiClient } from "@/lib/apiClient";
import type { StockSearchResult } from "@/lib/types";

const SAMSUNG: StockSearchResult = {
  market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW",
};
const APPLE: StockSearchResult = {
  market: "NASDAQ", symbol: "AAPL", name: "Apple Inc.", currency: "USD",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("종목 검색", () => {
  it("검색어를 입력하면 후보를 보여준다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({
      query: "삼성", results: [SAMSUNG],
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await waitFor(() => {
      expect(screen.getByText("삼성전자")).toBeInTheDocument();
    });
  });

  it("각 후보에 시장과 통화가 보인다", async () => {
    // FR-002b — 같은 이름이 여러 시장에 있고, 통화가 다르면 환전 여부가 달라진다.
    vi.spyOn(apiClient, "get").mockResolvedValue({
      query: "a", results: [SAMSUNG, APPLE],
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "a");
    await waitFor(() => {
      expect(screen.getByText(/KRX/)).toBeInTheDocument();
    });
    expect(screen.getByText(/KRW/)).toBeInTheDocument();
    expect(screen.getByText(/NASDAQ/)).toBeInTheDocument();
    expect(screen.getByText(/USD/)).toBeInTheDocument();
  });

  it("후보를 고르면 그 종목으로 알린다", async () => {
    const onSelect = vi.fn();
    vi.spyOn(apiClient, "get").mockResolvedValue({
      query: "삼성", results: [SAMSUNG],
    });
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await waitFor(() => screen.getByRole("option", { name: /삼성전자/ }));
    await userEvent.click(screen.getByRole("option", { name: /삼성전자/ }));
    expect(onSelect).toHaveBeenCalledWith(SAMSUNG);
  });

  it("코드를 직접 넣는 칸이 없다", () => {
    // SC-031 — 입력 칸은 검색어를 받는 자리이고, 확정은 목록에서만 이루어진다.
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    const boxes = screen.getAllByRole("searchbox");
    expect(boxes).toHaveLength(1);
    expect(screen.queryByLabelText(/종목 코드/)).toBeNull();
  });

  it("키보드로 후보를 고를 수 있다", async () => {
    const onSelect = vi.fn();
    vi.spyOn(apiClient, "get").mockResolvedValue({
      query: "삼성", results: [SAMSUNG],
    });
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await waitFor(() => screen.getByRole("option", { name: /삼성전자/ }));
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith(SAMSUNG);
  });

  it("결과가 없으면 그 사실을 알린다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ query: "zzz", results: [] });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "zzz");
    await waitFor(() => {
      expect(screen.getByText(/찾지 못했습니다/)).toBeInTheDocument();
    });
  });

  it("검색이 실패하면 결과 없음과 다르게 말한다", async () => {
    // 출처가 죽었는데 "없습니다"라고 하면 사용자는 그 종목이 존재하지 않는다고 읽는다.
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("출처 장애"));
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.queryByText(/찾지 못했습니다/)).toBeNull();
  });

  it("고른 종목이 있으면 그것을 보여준다", () => {
    render(<StockSearch value={SAMSUNG} onSelect={vi.fn()} />);
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
  });
});
