/**
 * 투자 시뮬레이션 모달 테스트의 고정 데이터 (013 반복 2026-10-09b T096·T097·T099) — 일곱 방식의 줄 조건과 그 메뉴 표 경로 응답.
 *
 * 메뉴 응답은 각 메뉴 화면 테스트의 고정 데이터를 그대로 쓴다(가상자산 `cryptoFixtures`, 예금 `depositFixtures`·`installmentFixtures`, 부동산
 * `realEstateSimulationFixtures`). 주식 일시금·적립식과 가상자산 적립식은 메뉴 화면 테스트(`TableWithHistoryPages`·`StocksPageRecurring`·
 * `CryptoPageRecurring`)와 같은 모양이다.
 */
import type { CompareCondition } from "@/lib/compareCondition";
import type {
  CompareTarget,
  RecurringCryptoResponse,
  RecurringStockResponse,
  SimulationResponse,
  SimulationSeriesResponse,
} from "@/lib/types";
import type { MenuBody } from "@/stores/compareDetailStore";
import { BTC_T, ETH_T, HELIO_T, HYNIX_T, SAMSUNG_T } from "./compareFixtures";
import { RESULT as CRYPTO_LUMP } from "./cryptoFixtures";
import { RESULT as DEPOSIT_LUMP } from "./depositFixtures";
import { INSTALLMENT_RESULT } from "./installmentFixtures";
import { SIM_RESULT } from "./realEstateSimulationFixtures";

export const STOCK_LUMP: SimulationResponse = {
  stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  condition: { start: "2021-08-02", principal: "1000000", principalCurrency: "KRW", reinvest: true,
    tradeFeeRate: "0", dividendTaxRate: "0" },
  summary: { principal: "1000000", profit: "1000", returnRate: "0.001", asOf: "2021-08-31", isFinal: true },
  rows: [{ date: "2021-08-31", kind: "month", openPrice: "79000", closePrice: "79500", boughtShares: 0, heldShares: 12,
    cash: "52000", principal: "1000000", balance: "954000", profit: "1000", returnRate: "0.001" } as never],
  hasMore: true, oldestReturned: "2021-08-31",
};

export const STOCK_RECURRING: RecurringStockResponse = {
  stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
  condition: { mode: "recurring", start: "2024-01-15", amount: "500000", principalCurrency: "KRW", frequency: "weekly",
    reinvest: true, tradeFeeRate: "0.000150", dividendTaxRate: "0.154000" },
  summary: {
    contributed: "1000000", contributedKrw: "1000000", contributions: 2, pendingAfterEnd: 0, heldShares: 14,
    pending: "26854", dividendCash: "0", totalKrw: "999854", buyFeeTotal: "145", dividendTaxTotal: "0",
    saleCost: { fee: "145", tax: "1946", total: "2091", taxKind: "transaction_tax", taxRate: "0.0020", gain: null,
      deduction: null },
    feeTotal: "290", taxTotal: "1946", profit: "-146", returnRate: "-0.000146", profitAfterSale: "-2237",
    returnRateAfterSale: "-0.002237", asOf: "2024-01-22", isFinal: true,
  },
  rows: [{ date: "2024-01-22", kind: "contribution", openPrice: "69000", closePrice: "69500", contribution: "500000",
    boughtShares: 7, heldShares: 14, pending: "26854", dividendCash: "0", contributed: "1000000",
    contributedKrw: "1000000", balance: "973000", profit: "-146", returnRate: "-0.000146", tradeFee: "72" }],
  hasMore: false, oldestReturned: "2024-01-22",
};

export const CRYPTO_RECURRING: RecurringCryptoResponse = {
  coin: { coinId: 17, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" },
  condition: { mode: "recurring", start: "2024-01-15", amount: "10000", principalCurrency: "KRW", frequency: "daily",
    tradeFeeRate: "0.001000" },
  summary: {
    contributed: "20000", contributedKrw: "20000", contributions: 2, pendingAfterEnd: 0, heldQuantity: "0.00036332",
    pending: "0.00029518", totalKrw: "20400", buyFeeTotal: "20", saleCost: { fee: "20", tax: "0", total: "20",
      taxKind: "not_yet_taxed" },
    feeTotal: "40", taxTotal: "0", profit: "400", returnRate: "0.020000", profitAfterSale: "380",
    returnRateAfterSale: "0.019000", asOf: "2024-01-16", isFinal: true,
  },
  rows: [{ date: "2024-01-16", kind: "contribution", openPrice: "42000", contribution: "10000",
    boughtQuantity: "0.00017601", heldQuantity: "0.00036332", pending: "0.00029518", contributed: "20000",
    contributedKrw: "20000", balance: "15.25944", balanceKrw: "20399", profit: "400", returnRate: "0.020000",
    tradeFee: "0.00739242", fxRate: "1336.8", fxRateDate: "2024-01-16", exchangeRate: "1339.2", exchangeRateDate: "2024-01-16" }],
  hasMore: false, oldestReturned: "2024-01-16",
};

export const SERIES: SimulationSeriesResponse = {
  from: "2021-08-02", to: "2021-08-31", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1,
  points: [{ date: "2021-08-31", balance: "1001000", returnRate: "0.001" }], gaps: [],
};

const condition = (over: Partial<CompareCondition>): CompareCondition => ({
  v: 1, asset: "stock", method: "lump_sum", frequency: null, start: "2021-08-02", amount: "1000000",
  principalCurrency: "KRW", reinvest: true, targets: [SAMSUNG_T, HYNIX_T], ...over,
});

export interface DetailCase {
  label: string;
  condition: CompareCondition;
  target: CompareTarget;
  name: string;
  menu: MenuBody;
  /** 그 메뉴 경로의 앞부분 — 질의 전까지. */
  prefix: string;
  /** 모달에 보여야 할 글자(보드·표) 하나씩. */
  boardText: string;
  tableText: string;
}

export const CASES: DetailCase[] = [
  { label: "주식 일시금", condition: condition({}), target: SAMSUNG_T, name: "삼성전자", menu: STOCK_LUMP,
    prefix: "/api/stocks/simulation?", boardText: "투자 원금", tableText: "2021-08-31" },
  { label: "주식 적립식", condition: condition({ method: "recurring", frequency: "weekly", start: "2024-01-15", amount: "500000" }),
    target: SAMSUNG_T, name: "삼성전자", menu: STOCK_RECURRING, prefix: "/api/stocks/recurring-simulation?",
    boardText: "총 납입 원금", tableText: "2024-01-22" },
  { label: "가상자산 일시금", condition: condition({ asset: "crypto", start: "2020-01-15", amount: "10000",
    principalCurrency: "USD", reinvest: null, targets: [BTC_T, ETH_T] }), target: BTC_T, name: "비트코인", menu: CRYPTO_LUMP,
    prefix: "/api/crypto/simulation?", boardText: "매수일 2020-01-01", tableText: "2020-01-01" },
  { label: "가상자산 적립식", condition: condition({ asset: "crypto", method: "recurring", frequency: "daily", start: "2024-01-15",
    amount: "10000", reinvest: null, targets: [BTC_T, ETH_T] }), target: BTC_T, name: "비트코인", menu: CRYPTO_RECURRING,
    prefix: "/api/crypto/recurring-simulation?", boardText: "총 납입 원금", tableText: "2024-01-16" },
  { label: "정기예금", condition: condition({ asset: "deposit", method: "deposit", start: "2020-01-15", amount: "10000000",
    reinvest: null, targets: [{ institution: "commercial_bank" }, { institution: "mutual_finance" }] }),
    target: { institution: "commercial_bank" }, name: "시중은행", menu: DEPOSIT_LUMP,
    prefix: "/api/deposit/simulation?", boardText: "세율 15.4%", tableText: "2026-01-15" },
  { label: "정기 적금", condition: condition({ asset: "deposit", method: "installment", start: "2015-01-15", amount: "1000000",
    reinvest: null, targets: [{ institution: "commercial_bank" }, { institution: "mutual_finance" }] }),
    target: { institution: "commercial_bank" }, name: "시중은행", menu: INSTALLMENT_RESULT,
    prefix: "/api/deposit/installment-simulation?", boardText: "시중은행", tableText: "적금" },
  { label: "부동산", condition: condition({ asset: "realestate", method: "hold", start: "2021-03-15", amount: null,
    reinvest: null, targets: [HELIO_T, { ...HELIO_T, area: "20", areaLabel: "20평대" }] }), target: HELIO_T,
    name: "헬리오시티아파트 30평대(국평)", menu: SIM_RESULT, prefix: "/api/realestate/simulation?", boardText: "취득",
    tableText: "2026-10" },
];
