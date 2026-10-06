/**
 * 007 가상자산 시뮬레이션 테스트 공용 응답 — contracts/rest-api `GET /api/crypto/simulation`.
 *
 * 매수 행의 값은 research R7-7의 손계산 사례다(BTC 2020-01-01, 원금 10,000달러, 수수료 0.1%).
 *
 * 012 승인 2026-10-06 — 행의 종류는 `buy`(매수)·`period`(기간 행)다. `MISSING_ROW`는 이름만 남은 3-02 기간 행이다 — ◇(1일 결측) 칸이
 * 없어졌다(FR-008). 결측은 결측 구간 행(`kind: "missing"`)이 드러낸다.
 */
import type { CryptoRow, CryptoSimulationResponse } from "@/lib/types";
import { BTC } from "./coinSearchFixtures";

export const BUY_ROW: CryptoRow = {
  date: "2020-01-01", kind: "buy", openPrice: "7196.39111328125000",
  boughtQuantity: "1.38819719", heldQuantity: "1.38819719",
  tradeFee: "9.9900099215980029296875", cash: "0.0000684803990673828125",
  principal: "10000", balance: "9990.0099215980029296875", balanceKrw: "11557841",
  profit: "-12159", returnRate: "-0.001051", fxRate: "1156.400000", fxRateDate: "2019-12-31",
};

export const MISSING_ROW: CryptoRow = {
  ...BUY_ROW, date: "2021-03-02", kind: "period", openPrice: "49612.30000000000000", boughtQuantity: "0.00000000",
  tradeFee: undefined, balance: "68872.15", balanceKrw: "77888123", profit: "66318123",
  returnRate: "5.733905", fxRate: "1131.100000", fxRateDate: "2021-03-02",
};
delete MISSING_ROW.tradeFee;

export const LATEST_ROW: CryptoRow = {
  ...MISSING_ROW, date: "2021-12-01", openPrice: "57230.10000000000000", balance: "79446.15",
  balanceKrw: "93745123", profit: "82175123", returnRate: "7.103341", fxRate: "1180.000000",
  fxRateDate: "2021-12-01",
};

export const TINY_ROW: CryptoRow = {
  ...LATEST_ROW, date: "2026-09-13", openPrice: "0.00000529999988",
  heldQuantity: "1886792452.83018868",
};

export const RESULT: CryptoSimulationResponse = {
  coin: { coinId: BTC.coinId, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", currency: "USD" },
  condition: { start: "2020-01-15", principal: "10000", principalCurrency: "USD",
    tradeFeeRate: "0.001000" },
  summary: { principal: "10000", principalKrw: "11564000", profit: "82175123",
    returnRate: "7.106116", asOf: "2021-12-31", isFinal: true, boughtOn: "2020-01-01" },
  rows: [LATEST_ROW, MISSING_ROW, BUY_ROW],
  hasMore: false,
  oldestReturned: "2020-01-01",
};
