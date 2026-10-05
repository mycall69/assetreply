/**
 * 네 화면이 실제로 표와 이력을 `TableWithHistory`에 둔다 (010 T033) — FR-015, FR-017, 006 D1.
 *
 * 공유 배치 부품이 있어도 화면이 쓰지 않으면 이 기능이 일어나지 않는다 — 그 화면만 표 아래에 이력이 남는다. 결과가 있는 상태로 네 화면을
 * 그려 성과 표와 최근 시뮬레이션이 **같은 `table-with-history` 안에 표 → 이력 순서**인지, 이력 비교 차트·출처 줄은 그 밖·뒤인지 본다.
 * 결과가 없으면 이력만 그 안이다.
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import DepositPage from "@/app/deposit/page";
import RealEstatePage from "@/app/realestate/page";
import StocksPage from "@/app/stocks/page";
import { apiClient } from "@/lib/apiClient";
import type { SimulationResponse } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { useDepositStore } from "@/stores/depositStore";
import { useRealEstateStore } from "@/stores/realEstateStore";
import { useStockStore } from "@/stores/stockStore";
import { RESULT as CRYPTO_RESULT } from "./support/cryptoFixtures";
import { INSTITUTIONS, RESULT as DEPOSIT_RESULT } from "./support/depositFixtures";
import { realEstateRoutes, resetRealEstateStore, routeRealEstate } from "./support/realEstateFixtures";
import { SIM_RESULT } from "./support/realEstateSimulationFixtures";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));

const STOCK_RESULT: SimulationResponse = {
  stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  condition: { start: "2021-08-02", principal: "1000000", principalCurrency: "KRW", reinvest: true,
    tradeFeeRate: "0", dividendTaxRate: "0" },
  summary: { principal: "1000000", profit: "1000", returnRate: "0.001", asOf: "2021-08-31", isFinal: true },
  rows: [], hasMore: false, oldestReturned: null,
};

const noop = async () => undefined;

/** 성과 표 제목이 든 칸과 최근 시뮬레이션이 든 칸이 같은 바깥 안에 이 순서로 있다. */
function expectSideBySide(tableTitle: string) {
  const outer = screen.getByTestId("table-with-history");
  const table = within(outer).getByText(tableTitle);
  const history = within(outer).getByText("최근 시뮬레이션");
  expect(table.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  return outer;
}

function expectAfter(outer: HTMLElement, text: RegExp) {
  const node = screen.getByText(text);
  expect(outer.contains(node)).toBe(false);
  expect(outer.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("네 화면 — 표 옆 최근 시뮬레이션", () => {
  it("주식", () => {
    useStockStore.setState({
      input: { stock: STOCK_RESULT.stock, start: "2021-08-02", principal: "1000000", principalCurrency: "KRW",
        reinvest: true },
      summary: STOCK_RESULT.summary, rows: [], condition: STOCK_RESULT.condition, series: null, collecting: null,
      loading: false, error: null, history: [], refreshIfRan: noop,
    });
    render(<StocksPage />);
    expectSideBySide("일자별 투자 성과");
  });

  it("가상자산", () => {
    useCryptoStore.setState({
      summary: CRYPTO_RESULT.summary, rows: CRYPTO_RESULT.rows, condition: CRYPTO_RESULT.condition, series: null,
      collecting: null, loading: false, error: null, history: [], refreshIfRan: noop,
    });
    render(<CryptoPage />);
    expectSideBySide("일자별 투자 성과");
  });

  it("예금 — 출처 줄은 그 밖·뒤", () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(INSTITUTIONS);
    useDepositStore.setState({
      summary: DEPOSIT_RESULT.summary, rows: DEPOSIT_RESULT.rows, condition: DEPOSIT_RESULT.condition, series: null,
      collecting: null, loading: false, error: null, history: [], refreshIfRan: noop,
    });
    render(<DepositPage />);
    expectAfter(expectSideBySide("일자별 투자 성과"), /^출처: 한국은행/);
  });

  it("부동산 — 출처 줄은 그 밖·뒤", () => {
    resetRealEstateStore();
    routeRealEstate(realEstateRoutes);
    useRealEstateStore.setState({
      summary: SIM_RESULT.summary, rows: SIM_RESULT.rows, condition: SIM_RESULT.condition,
      acquisition: SIM_RESULT.acquisition, resultTarget: { complex: SIM_RESULT.complex, area: SIM_RESULT.area },
      series: null, collecting: null, loading: false, error: null, history: [], refreshIfRan: noop,
    });
    render(<RealEstatePage />);
    expectAfter(expectSideBySide("월별 투자 성과"), /^출처: 국토교통부/);
  });

  it("결과가 없으면 이력만 그 안이다", () => {
    useStockStore.setState({ summary: null, rows: [], history: [], refreshIfRan: noop });
    render(<StocksPage />);
    const outer = screen.getByTestId("table-with-history");
    expect(within(outer).getByText("최근 시뮬레이션")).toBeInTheDocument();
    expect(within(outer).queryByText("일자별 투자 성과")).toBeNull();
  });
});
