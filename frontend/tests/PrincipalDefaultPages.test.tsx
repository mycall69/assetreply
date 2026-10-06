/**
 * 투자 원금 칸의 처음 값 — 세 화면 (012 T062) — FR-016, SC-008, contracts/ui-wireframes.md F8.
 *
 * **화면을 거쳐야만 통과한다**: 스토어의 처음 값이 칸에 그려지지 않거나, 실행이 칸의 값이 아닌 다른 값을 보내면 실패한다.
 * - 처음 열면 칸이 "10,000,000"이다(쉼표는 표시에만 — 요청은 `principal=10000000`)
 * - 이름표만 방식·상품을 따른다("투자 원금" · "한 번 납입액" · "월 납입액"). 값은 그대로다. 원금 통화를 바꿔도 숫자는 그대로다
 * - 종목·코인만 고르면(예금은 투자처가 처음부터 골라져 있다) 실행 단추가 켜지고 그 값으로 실행된다
 * - 부동산 화면은 바뀌지 않는다 — 매입가 칸은 비어 있다(비우면 그 달 시세)
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import DepositPage from "@/app/deposit/page";
import RealEstatePage from "@/app/realestate/page";
import StocksPage from "@/app/stocks/page";
import { apiClient } from "@/lib/apiClient";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useDepositStore } from "@/stores/depositStore";
import { useStockStore } from "@/stores/stockStore";
import { INSTITUTIONS } from "./support/depositFixtures";
import { realEstateRoutes, resetRealEstateStore, routeRealEstate } from "./support/realEstateFixtures";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
// 실제 차트는 jsdom에서 그릴 수 없다(011 T036 — 처리되지 않은 오류로 실행이 실패한다).
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const STOCK = { market: "KRX" as const, symbol: "005930.KS", name: "삼성전자", currency: "KRW" };
const APPLE = { market: "NASDAQ" as const, symbol: "AAPL", name: "Apple Inc.", currency: "USD" };
const COIN = { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin", currency: "USD" };

/** 시뮬레이션 요청은 끝나지 않게 둔다 — 보낸 경로만 본다. 예금 투자처 목록은 준다. */
function answer() {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) =>
    path.startsWith("/api/deposit/institutions") ? Promise.resolve(INSTITUTIONS)
      : new Promise(() => undefined)) as typeof apiClient.get);
}

/** 예금 칸의 이름표에는 뒤의 "원"까지 들어간다 — 앞부분으로 찾는다. */
const amountBox = (label: string) => screen.getByLabelText(new RegExp(`^${label}`)) as HTMLInputElement;

beforeEach(() => {
  vi.restoreAllMocks();
  useStockStore.setState(useStockStore.getInitialState(), true);
  useCryptoStore.setState(useCryptoStore.getInitialState(), true);
  useDepositStore.setState(useDepositStore.getInitialState(), true);
});

describe("주식 화면", () => {
  it("칸이 10,000,000이고 방식·통화를 바꿔도 값은 그대로다", () => {
    answer();
    render(<StocksPage />);
    expect(amountBox("투자 원금").value).toBe("10,000,000");
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(amountBox("한 번 납입액").value).toBe("10,000,000");
    fireEvent.click(screen.getByRole("radio", { name: "일시금" }));
    // 미국 종목이면 원화·달러 원금을 고를 수 있다(006) — 통화만 바뀐다
    act(() => useStockStore.getState().setInput({ stock: APPLE }));
    fireEvent.change(screen.getByRole("combobox", { name: "통화" }), { target: { value: "USD" } });
    expect(useStockStore.getState().input.principalCurrency).toBe("USD");
    expect(amountBox("투자 원금").value).toBe("10,000,000");
  });

  it("종목만 고르면 실행되고 원금은 쉼표 없이 간다", async () => {
    const get = answer();
    render(<StocksPage />);
    expect(screen.getByRole("button", { name: "시뮬레이션" })).toBeDisabled();
    act(() => useStockStore.getState().setInput({ stock: STOCK }));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(get.mock.calls.map(([p]) => String(p))
      .some((p) => p.startsWith("/api/stocks/simulation?") && p.includes("principal=10000000"))).toBe(true));
  });
});

describe("가상자산 화면", () => {
  it("칸이 10,000,000이고 적립식으로 바꿔도 값은 그대로다", () => {
    answer();
    render(<CryptoPage />);
    expect(amountBox("투자 원금").value).toBe("10,000,000");
    fireEvent.click(screen.getByRole("radio", { name: "적립식" }));
    expect(amountBox("한 번 납입액").value).toBe("10,000,000");
  });

  it("코인만 고르면 실행되고 원금은 쉼표 없이 간다", async () => {
    const get = answer();
    render(<CryptoPage />);
    expect(screen.getByRole("button", { name: "시뮬레이션" })).toBeDisabled();
    act(() => useCryptoStore.getState().selectCoin(COIN));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(get.mock.calls.map(([p]) => String(p))
      .some((p) => p.startsWith("/api/crypto/simulation?") && p.includes("principal=10000000"))).toBe(true));
  });
});

describe("예금 화면", () => {
  it("칸이 10,000,000이고 적금으로 바꿔도 값은 그대로다", () => {
    answer();
    render(<DepositPage />);
    expect(amountBox("투자 원금").value).toBe("10,000,000");
    fireEvent.click(screen.getByRole("radio", { name: "정기 적금" }));
    expect(amountBox("월 납입액").value).toBe("10,000,000");
  });

  it("투자처가 골라져 있어 곧바로 실행되고 원금은 쉼표 없이 간다", async () => {
    const get = answer();
    render(<DepositPage />);
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(get.mock.calls.map(([p]) => String(p))
      .some((p) => p.startsWith("/api/deposit/simulation?") && p.includes("principal=10000000"))).toBe(true));
  });
});

describe("부동산 화면", () => {
  it("매입가 칸은 지금처럼 비어 있다", () => {
    resetRealEstateStore();
    routeRealEstate(realEstateRoutes);
    render(<RealEstatePage />);
    const box = screen.getByText("매입가").closest("label")?.querySelector("input");
    expect(box?.value).toBe("");
  });
});
