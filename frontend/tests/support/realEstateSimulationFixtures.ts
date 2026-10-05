/**
 * 부동산 시뮬레이션 테스트 공용 응답 (009 T034) — contracts/rest-api `GET /api/realestate/simulation`의 모양.
 *
 * 보드·안내의 값은 계약의 예(헬리오시티 30평대(국평), 2021-03-15 매입, 오늘 2026-10-05)다. **표의 행은 여러 경우를 한 결과에 모았다** —
 * 시세 없음 달(2022-05)·보유세 계산 불가 해(2023)·재산세 일괄(2024-07)·6월 시세 추정(2025)은 실제 헬리오시티 30평대(국평)에서는 나오지
 * 않는다(ui-wireframes E5의 다른 단지·평형의 예).
 *
 * **이 파일이 전제하는 형식**(`@/lib/types`, T039가 더한다) — 필드는 계약의 JSON 그대로다.
 * - `RealEstateSimulationResponse { complex: { complexId, name, umdName }; area: { key: RealEstateAreaKey; label };
 *   condition: RealEstateCondition; acquisition: RealEstateAcquisition; summary: RealEstateSummary; rows: RealEstateRow[] }`
 * - `RealEstateCondition { buyDate; buyPrice; buyPriceSource: "market" | "input"; buyPriceWindow: { months; trades; estimated } | null;
 *   holdingTaxBaseRatio; assumptions: string[] }`
 * - `RealEstateAcquisition { acquisitionTax; educationTax; ruralTax; brokerageFee; total; rules: { acquisition; brokerage } }`
 * - `RealEstateSummary { buyPrice; invested; propertyTaxTotal; comprehensiveTaxTotal; holdingTaxTotal; value: string | null;
 *   valueMonth: string | null; valueWindow: { months; trades } | null; estimated; provisional; profit: string | null;
 *   returnRate: string | null; asOf; taxGaps: number[]; lastPricedMonth: string | null; provisionalFrom: string;
 *   recheckFailed?: { kind: RealEstateFailureKind; reason } }` — `provisionalFrom`은 잠정 기간(설정
 *   `APT_TRADE_PROVISIONAL_MONTHS`, 기본 12개월)의 첫 달 1일(`"2025-11-01"`)이다. 시계열의 같은 키와 같다
 * - `RealEstateTax { amount; rule; installment: "1/1" | "1/2" | "2/2"; basis: RealEstateTaxBasis }`,
 *   `RealEstateTaxBasis { month; price; window; windowTrades; estimated; provisional }`
 * - `RealEstateRow { month; trades; monthAverage: string | null; price: string | null; window: number | null;
 *   windowTrades: number | null; estimated; provisional; acquisition: RealEstateAcquisition | null; propertyTax: RealEstateTax | null;
 *   comprehensiveTax: RealEstateTax | null; cumulativeCost; value: string | null; profit: string | null; returnRate: string | null }`
 */
import type {
  RealEstateAcquisition,
  RealEstateRow,
  RealEstateSimulationResponse,
  RealEstateSummary,
  RealEstateTax,
  RealEstateTaxBasis,
  RealEstateTradeCollecting,
  RealEstateTrades,
} from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";
import {
  COLLECTED_TRADES,
  GARAK,
  HELIO_AREAS,
  HELIO_ID,
  SEOUL,
  SEOUL_SGGS,
  SIDOS,
  SONGPA,
  SONGPA_UMDS,
  complexesWith,
} from "./realEstateFixtures";

export const ACQUISITION: RealEstateAcquisition = {
  acquisitionTax: "60695000", educationTax: "6069500", ruralTax: "0", brokerageFee: "18208500", total: "84973000",
  rules: { acquisition: "2020-01-01", brokerage: "2015-04-01" },
};

const basis = (over: Partial<RealEstateTaxBasis>): RealEstateTaxBasis => ({
  month: "2026-06", price: "2400000000", window: 1, windowTrades: 9, estimated: false, provisional: true, ...over,
});

const tax = (amount: string, installment: RealEstateTax["installment"], rule: string,
  over: Partial<RealEstateTaxBasis> = {}): RealEstateTax => ({ amount, rule, installment, basis: basis(over) });

const row = (over: Partial<RealEstateRow>): RealEstateRow => ({
  month: "2026-10", trades: 0, monthAverage: null, price: "2450000000", window: 3, windowTrades: 41,
  estimated: true, provisional: true, acquisition: null, propertyTax: null, comprehensiveTax: null,
  cumulativeCost: "117401400", value: "2450000000", profit: "309431933", returnRate: "0.146780", ...over,
});

/** 최신순 — 매입 달(2021-03)이 마지막이다. */
export const SIM_ROWS: RealEstateRow[] = [
  // 이번 달 — 아직 거래가 없어 8~10월 3개월 창의 추정이다.
  row({}),
  row({ month: "2026-09", trades: 14, monthAverage: "2441428571", price: "2441428571", window: 1, windowTrades: 14,
    estimated: false, propertyTax: tax("3104390", "2/2", "2026-06-01"),
    value: "2441428571", profit: "300860504", returnRate: "0.142714" }),
  row({ month: "2026-07", trades: 11, monthAverage: "2430000000", price: "2430000000", window: 1, windowTrades: 11,
    estimated: false, propertyTax: tax("3104390", "1/2", "2026-06-01"), cumulativeCost: "114297010",
    value: "2430000000", profit: "292536323", returnRate: "0.138770" }),
  // 종부세는 12월에만. 그해 6월 시세가 3개월 창의 추정이다.
  row({ month: "2025-12", trades: 8, monthAverage: "2350000000", price: "2350000000", window: 1, windowTrades: 8,
    estimated: false, provisional: false,
    comprehensiveTax: tax("1234560", "1/1", "2025-06-01",
      { month: "2025-06", price: "2300000000", window: 3, windowTrades: 7, estimated: true, provisional: false }),
    cumulativeCost: "111192620", value: "2350000000", profit: "215640713", returnRate: "0.102289" }),
  // 재산세가 소액이라 7월에 한 번에 냈다.
  row({ month: "2024-07", trades: 5, monthAverage: "1950000000", price: "1950000000", window: 1, windowTrades: 5,
    estimated: false, provisional: false,
    propertyTax: tax("180000", "1/1", "2024-06-01",
      { month: "2024-06", price: "1900000000", window: 1, windowTrades: 4, estimated: false, provisional: false }),
    cumulativeCost: "100000000", value: "1950000000", profit: "-173166667", returnRate: "-0.082142" }),
  // 2023년은 6월 시세가 없어 보유세를 계산하지 못했다(`summary.taxGaps`).
  row({ month: "2023-12", trades: 2, monthAverage: "1800000000", price: "1800000000", window: 1, windowTrades: 2,
    estimated: false, provisional: false, cumulativeCost: "99820000", value: "1800000000", profit: "-322986667",
    returnRate: "-0.153214" }),
  row({ month: "2023-09", trades: 1, monthAverage: "1790000000", price: "1790000000", window: 1, windowTrades: 1,
    estimated: false, provisional: false, cumulativeCost: "99820000", value: "1790000000", profit: "-332986667",
    returnRate: "-0.157957" }),
  row({ month: "2023-07", trades: 3, monthAverage: "1780000000", price: "1780000000", window: 1, windowTrades: 3,
    estimated: false, provisional: false, cumulativeCost: "99820000", value: "1780000000", profit: "-342986667",
    returnRate: "-0.162700" }),
  // 시세 없음 — 36개월 안에 거래가 없다. 0이 아니라 비운다.
  row({ month: "2022-05", trades: 0, monthAverage: null, price: null, window: null, windowTrades: null,
    estimated: false, provisional: false, cumulativeCost: "95000000", value: null, profit: null, returnRate: null }),
  // 매입 달 — 취득 비용이 이 행에만 있다.
  row({ month: "2021-03", trades: 6, monthAverage: "2023166667", price: "2023166667", window: 1, windowTrades: 6,
    estimated: false, provisional: false, acquisition: ACQUISITION, cumulativeCost: "84973000",
    value: "2023166667", profit: "-84973000", returnRate: "-0.042000" }),
];

export const SIM_SUMMARY: RealEstateSummary = {
  buyPrice: "2023166667", invested: "2108139667",
  propertyTaxTotal: "28111520", comprehensiveTaxTotal: "4316880", holdingTaxTotal: "32428400",
  value: "2450000000", valueMonth: "2026-10", valueWindow: { months: 3, trades: 41 },
  estimated: true, provisional: true,
  profit: "309431933", returnRate: "0.146780", asOf: "2026-10-05",
  taxGaps: [], lastPricedMonth: null, provisionalFrom: "2025-11-01",
};

export const SIM_RESULT: RealEstateSimulationResponse = {
  complex: { complexId: HELIO_ID, name: "헬리오시티", umdName: "가락동" },
  area: { key: "30k", label: "30평대(국평)" },
  condition: {
    buyDate: "2021-03-15", buyPrice: "2023166667", buyPriceSource: "market",
    buyPriceWindow: { months: 1, trades: 6, estimated: false },
    holdingTaxBaseRatio: "0.600000",
    assumptions: ["부부 5:5 공동 소유", "1세대 1주택", "세법: 시행일별 표"],
  },
  acquisition: ACQUISITION,
  summary: SIM_SUMMARY,
  rows: SIM_ROWS,
};

/** 오늘 실거래 확인만 실패했다 — 받아 둔 시·군·구라 200이다. */
export const SIM_RECHECK_FAILED: RealEstateSimulationResponse = {
  ...SIM_RESULT,
  summary: { ...SIM_SUMMARY, recheckFailed: { kind: "auth", reason: "공공데이터포털 인증 실패" } },
};

/** 그 시·군·구의 실거래를 받는 중(202). */
export const SIM_COLLECTING: RealEstateTradeCollecting = {
  status: "collecting", kind: "trade", lawdCd: "11710", jobId: 9, monthsDone: 120, monthsTotal: 250,
  progressUrl: "/api/realestate/progress?jobId=9",
};

/** 실행 상태의 처음 값 — Phase 3의 `resetRealEstateStore` 뒤에 부른다. **이 필드 목록이 T039가 더할 상태다.** */
export function resetSimulation(): void {
  useRealEstateStore.setState({
    input: { buyDate: "2021-03-15", buyPrice: "" },
    condition: null, acquisition: null, resultTarget: null,
    collecting: null, progress: null, startable: null, rejection: null, loading: false,
  });
}

/** 서울특별시 → 송파구 → 가락동 → 헬리오시티 → 30평대(국평)까지 골랐고 결과는 없다. 시·군·구의 실거래 상태를 고른다. */
export function chooseForRun(trades: RealEstateTrades = COLLECTED_TRADES): void {
  useRealEstateStore.setState({
    regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
    selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: HELIO_ID, area: "30k" },
    complexes: complexesWith({ trades }), areas: HELIO_AREAS,
  });
}
