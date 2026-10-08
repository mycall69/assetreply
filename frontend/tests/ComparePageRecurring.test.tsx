/**
 * 방식 칸과 적립식·정기 적금 표 (013 T045) — FR-006, FR-007, FR-011, ui-wireframes F3·F5.
 *
 * 주식·가상자산은 메뉴의 `InvestmentModeFields`(일시금·적립식 + 납입 주기), 예금은 `ProductPicker`(정기예금·정기 적금), 부동산은
 * "매입 후 보유" 하나다. 금액 칸의 이름이 방식을 따른다. 적립식 표의 투자 원금은 총 납입 원금과 납입 횟수다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { apiClient } from "@/lib/apiClient";
import { useCompareStore } from "@/stores/compareStore";
import { useCompareRealEstatePicker } from "@/stores/compareRealEstatePicker";
import { BTC_T, ETH_T, HYNIX_T, SAMSUNG_T, ok } from "./support/compareFixtures";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
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
    if (path === "/api/deposit/institutions") return Promise.resolve({ institutions: [], source: "", basis: "" });
    if (path.startsWith("/api/realestate/regions")) return Promise.resolve({ level: "sido", items: [] });
    const result = answer(path);
    return result === undefined ? Promise.reject(new Error(`처리기가 없는 경로: ${path}`)) : Promise.resolve(result);
  }) as typeof apiClient.get);
}

beforeEach(() => {
  vi.restoreAllMocks();
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareRealEstatePicker.getState().dispose();
  useCompareRealEstatePicker.setState(useCompareRealEstatePicker.getInitialState(), true);
});

const amountLabel = () => screen.queryByText(/^(투자 원금|한 번 납입액|월 납입액)$/)?.textContent ?? null;

describe("방식 칸", () => {
  it("주식은 일시금·적립식과 납입 주기다", () => {
    route(() => undefined);
    render(<ComparePage />);
    expect(screen.getByRole("radio", { name: "일시금" })).toBeChecked();
    expect(amountLabel()).toBe("투자 원금");
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(screen.getByRole("combobox", { name: "납입 주기" })).toBeInTheDocument();
    expect(amountLabel()).toBe("한 번 납입액");
    expect(useCompareStore.getState().method).toBe("recurring");
    fireEvent.change(screen.getByRole("combobox", { name: "납입 주기" }), { target: { value: "weekly" } });
    expect(useCompareStore.getState().frequency).toBe("weekly");
  });

  it("예금은 정기예금·정기 적금이고 적금이면 월 납입액이다", () => {
    route(() => undefined);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("radio", { name: "예금" }));
    expect(screen.getByRole("radio", { name: "정기예금" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: "정기 적금" }));
    expect(useCompareStore.getState().method).toBe("installment");
    expect(amountLabel()).toBe("월 납입액");
  });

  it("부동산은 매입 후 보유 하나다", () => {
    route(() => undefined);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("radio", { name: "부동산" }));
    expect(screen.getByText("매입 후 보유")).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "적립식" })).toBeNull();
  });
});

describe("적립식 표", () => {
  it("투자 원금은 총 납입 원금과 납입 횟수다", async () => {
    route(() => ({ ...ok(SAMSUNG_T, { principal: { amount: "6000000", currency: "KRW", krw: "6000000" } }),
      summary: { contributions: 12 } }));
    useCompareStore.setState({ method: "recurring" });
    useCompareStore.getState().addTarget(SAMSUNG_T);
    useCompareStore.getState().addTarget(HYNIX_T);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    const table = await screen.findByRole("table", { name: "비교 표" });
    const cell = within(within(table).getAllByRole("row")[1]).getAllByRole("cell")[2];
    expect(cell.textContent).toContain("₩6,000,000");
    expect(cell.textContent).toContain("총 납입 원금 · 12회 납입");
  });

  it("가상자산 적립식의 시행일 뒤 세금은 —와 까닭이고 투자 수익·수익률도 —다", async () => {
    const costs = { total: null, reflected: { total: "1200", items: [{ kind: "buy_fee", amount: "1200", inPrincipal: false }] },
      sale: { total: null, blank: "outside_rules", items: [
        { kind: "sale_fee", amount: "300", inPrincipal: false }, { kind: "crypto_tax", amount: null, inPrincipal: false }] } };
    route(() => ok(BTC_T, { costs, mainBasis: "unavailable", profit: null, returnRate: null } as never));
    useCompareStore.getState().setAsset("crypto");
    useCompareStore.setState({ method: "recurring" });
    useCompareStore.getState().addTarget(BTC_T);
    useCompareStore.getState().addTarget(ETH_T);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    const table = await screen.findByRole("table", { name: "비교 표" });
    const cells = within(within(table).getAllByRole("row")[1]).getAllByRole("cell");
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    expect(cells[7].textContent).toContain("과세 시행일 뒤");
    expect(cells[8].textContent).toContain("—");
    expect(cells[9].textContent).toContain("—");
  });
});
