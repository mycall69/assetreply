/**
 * 종목 검색 (T031) — 005 FR-002a, FR-002b, SC-030, SC-031. 006에서 두 영역으로 바뀌었다(T043).
 *
 * **코드를 직접 입력하게 하지 않는다.** 시장별 코드 체계(6자리 숫자·알파벳 티커·
 * 4자리 숫자)를 사용자가 알아야 하고, **오타와 "없는 종목"을 구별할 수 없다** —
 * 둘 다 "시세를 얻을 수 없음"으로 보이는데 사용자가 할 일은 정반대다.
 *
 * 006 — 고른 결과는 종목 식별이 아니라 **선택**(목록 행 또는 일본 외부 결과)으로 알린다. 식별은
 * 등록 응답이 정한다(FR-030b) — 그 흐름은 `stockSelection.test.ts`가 본다.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import type { StockSearchResult } from "@/lib/types";
import {
  SAMSUNG,
  TOYOTA,
  external,
  local,
  routeGet,
} from "./support/stockSearchFixtures";

const SELECTED: StockSearchResult = {
  market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("종목 검색", () => {
  it("검색어를 입력하면 후보를 보여준다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    expect(await screen.findByRole("option", { name: /삼성전자/ })).toBeInTheDocument();
  });

  it("각 후보에 시장과 통화가 보인다", async () => {
    // FR-002b — 같은 이름이 여러 시장에 있고, 통화가 다르면 환전 여부가 달라진다.
    routeGet({
      local: () => Promise.resolve(local([SAMSUNG])),
      external: () => Promise.resolve(external([TOYOTA])),
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "a");
    const samsung = await screen.findByRole("option", { name: /삼성전자/ });
    const toyota = await screen.findByRole("option", { name: /Toyota/ });
    expect(samsung.textContent).toMatch(/KRX.*KRW/);
    expect(toyota.textContent).toMatch(/TSE.*JPY/);
  });

  it("목록 후보를 고르면 그 선택으로 알린다", async () => {
    const onSelect = vi.fn();
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await userEvent.click(await screen.findByRole("option", { name: /삼성전자/ }));
    expect(onSelect).toHaveBeenCalledWith({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
  });

  it("일본 후보를 고르면 외부 선택으로 알린다", async () => {
    const onSelect = vi.fn();
    routeGet({ external: () => Promise.resolve(external([TOYOTA])) });
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "toyota");
    await userEvent.click(await screen.findByRole("option", { name: /Toyota/ }));
    expect(onSelect).toHaveBeenCalledWith({ source: "external", result: TOYOTA });
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
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await screen.findByRole("option", { name: /삼성전자/ });
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith({ source: "listing", listingId: 1021,
      preview: SAMSUNG });
  });

  it("고르면 검색어와 후보를 닫는다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await userEvent.click(await screen.findByRole("option", { name: /삼성전자/ }));
    await waitFor(() => expect(screen.queryByRole("option")).toBeNull());
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("고른 종목이 있으면 그것을 보여준다", () => {
    render(<StockSearch value={SELECTED} onSelect={vi.fn()} />);
    // 006 FR-025(반복 2026-10-03) — 종목명(코드)로 보인다.
    expect(screen.getByText("삼성전자(005930)")).toBeInTheDocument();
  });
});
