/**
 * 차트 위 상자의 내용·자리 (010 T020) — FR-009~FR-012, SC-003, research R10-8·R10-9, data-model 4절.
 *
 * - `hoverView(series, time)` — 커서가 붙은 시각의 **그 점**의 원본 문자열을 **표와 같은 형식 함수**로 보인다(FR-010). 주식 가격은
 *   `formatRate`(표의 시작가), 가상자산은 `formatPrice`(표의 시가), 예금 금리는 `formatAnnualRate`, 금액은 기호를 앞에
 *   (`formatMoneyWithSymbol`), 수익률은 표와 같은 `formatPercent`. 값이 없는 칸은 0이 아니라 "—"와 사유(FR-011). 주식 분할 표식 점은
 *   비율·효력일을 밝힌다(FR-008). 값 없는 자리(구간마다 하나)는 구간과 사유
 * - `gapSlots(points, gaps)` — 점 범위 안의 출처 결측·시세 없음 **구간마다 자리 하나**(`from`). 날마다 두면 줄인 차트에서 구간이
 *   과장된다(R10-8)
 * - `placeHover(point, box, area)` — 커서 오른쪽 아래 12px, 넘치면 반대쪽. 차트 칸 밖으로 나가지 않는다(FR-012)
 */
import { describe, expect, it } from "vitest";
import { hoverView, placeHover } from "@/lib/chartHover";
import { gapSlots } from "@/lib/chartSeries";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse>): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

const STOCK = series([
  { date: "2020-08-03", balance: "14210345", returnRate: "0.4210", price: "432.800000" },
  { date: "2020-09-01", balance: "15342210", returnRate: "0.534221", price: "132.759995" },
], { priceKind: "stock_open", priceCurrency: "USD", splits: [{ date: "2020-08-31", numerator: 4, denominator: 1 }] });

const KRX = series([{ date: "2021-08-02", balance: "86997", returnRate: "-0.0123", price: "70000.000000" }],
  { priceKind: "stock_open", priceCurrency: "KRW" });

const CRYPTO = series([
  { date: "2024-03-01", balance: "1000000", returnRate: "0", price: "0.00000530" },
  { date: "2024-03-04", balance: "1100000", returnRate: "0.1", price: "0.00000610" },
], { priceKind: "crypto_open", priceCurrency: "USD", gaps: [{ from: "2024-03-02", to: "2024-03-03", reason: "source_missing" }] });

const DEPOSIT = series([
  { date: "2026-07-01", balance: "10512345", returnRate: "0.0512", price: "3.71" },
  { date: "2026-08-01", balance: "10520000", returnRate: "0.0520", price: null, priceMissing: "missing" },
  { date: "2026-09-01", balance: "10530000", returnRate: "0.0530", price: null, priceMissing: "unpublished" },
], { priceKind: "deposit_rate", priceCurrency: null });

const APT = series([
  { date: "2021-03-15", balance: "2023166667", returnRate: "-0.040307", profit: "-85000000", price: "2023166667", estimated: false },
  { date: "2021-04-01", balance: "2031250000", returnRate: "-0.036473", profit: "-77000000", price: null, priceMissing: "no_trades", estimated: true },
  { date: "2023-06-01", balance: "2200000000", returnRate: "0.050000", profit: "105000000", price: "2210000000", estimated: false },
  { date: "2023-10-05", balance: "2250000000", returnRate: "0.070000", profit: "150000000", price: null, priceMissing: "no_trades", estimated: true },
], { priceKind: "apt_average", priceCurrency: "KRW", gaps: [{ from: "2023-01-01", to: "2023-05-01", reason: "no_price" }] });

describe("hoverView — 자산군별 줄과 형식", () => {
  it("주식 — 주가(표의 시작가 형식)·잔고·수익률, 분할 표식 점은 비율과 효력일", () => {
    expect(hoverView(STOCK, "2020-09-01")).toEqual({
      title: "2020-09-01",
      lines: [{ label: "주가", value: "$132.75" }, { label: "잔고", value: "₩15,342,210" }, { label: "수익률", value: "+53.42%" }],
      notes: ["분할 1→4 (2020-08-31 효력)"],
      reason: null,
    });
    expect(hoverView(STOCK, "2020-08-03")?.notes).toEqual([]);
  });

  it("국내 주식 — 원화 기호, 표와 같은 소수 2자리", () => {
    expect(hoverView(KRX, "2021-08-02")?.lines).toEqual([
      { label: "주가", value: "₩70,000.00" }, { label: "잔고", value: "₩86,997" }, { label: "수익률", value: "-1.23%" }]);
  });

  it("가상자산 — 시세(표의 시가 형식 — 작은 값을 0.00으로 깎지 않는다)", () => {
    expect(hoverView(CRYPTO, "2024-03-01")?.lines[0]).toEqual({ label: "시세", value: "$0.0000053" });
  });

  it("예금 — 잔고·수익률·금리(연 %), 없는 금리는 — 와 사유", () => {
    expect(hoverView(DEPOSIT, "2026-07-01")?.lines).toEqual([
      { label: "잔고", value: "₩10,512,345" }, { label: "수익률", value: "+5.12%" }, { label: "금리", value: "연 3.71%" }]);
    expect(hoverView(DEPOSIT, "2026-08-01")?.lines[2]).toEqual({ label: "금리", value: "—", missing: "결측" });
    expect(hoverView(DEPOSIT, "2026-09-01")?.lines[2]).toEqual({ label: "금리", value: "—", missing: "미발표" });
  });

  it("부동산 — 달·평가액·투자 수익·수익률·실거래가 평균, 첫 점·끝 점은 날짜", () => {
    expect(hoverView(APT, "2023-06-01")).toEqual({
      title: "2023-06",
      lines: [
        { label: "평가액", value: "₩2,200,000,000" }, { label: "투자 수익", value: "₩105,000,000" },
        { label: "수익률", value: "+5.00%" }, { label: "실거래가 평균", value: "₩2,210,000,000" },
      ],
      notes: [],
      reason: null,
    });
    expect(hoverView(APT, "2021-03-15")?.title).toBe("2021-03-15");
    expect(hoverView(APT, "2023-10-05")?.title).toBe("2023-10-05");
  });

  it("부동산 거래 없는 달 — 실거래가 평균만 — 와 사유, 평가액·투자 수익·수익률은 그대로", () => {
    expect(hoverView(APT, "2021-04-01")?.lines).toEqual([
      { label: "평가액", value: "₩2,031,250,000" }, { label: "투자 수익", value: "-₩77,000,000" },
      { label: "수익률", value: "-3.64%" }, { label: "실거래가 평균", value: "—", missing: "거래 없음" },
    ]);
  });

  it("값 없는 자리 — 구간과 모든 값 —, 사유", () => {
    expect(hoverView(CRYPTO, "2024-03-02")).toEqual({
      title: "2024-03-02 ~ 2024-03-03",
      lines: [{ label: "시세", value: "—" }, { label: "잔고", value: "—" }, { label: "수익률", value: "—" }],
      notes: [],
      reason: "출처 결측",
    });
    expect(hoverView(APT, "2023-01-01")).toEqual({
      title: "2023-01 ~ 2023-05",
      lines: [
        { label: "평가액", value: "—" }, { label: "투자 수익", value: "—" }, { label: "수익률", value: "—" },
        { label: "실거래가 평균", value: "—" },
      ],
      notes: [],
      reason: "시세 없음",
    });
  });

  it("점도 자리도 아닌 시각이면 없다", () => {
    expect(hoverView(CRYPTO, "2024-03-03")).toBeNull();
    expect(hoverView(STOCK, "2019-01-01")).toBeNull();
  });

  it("가격이 없는 응답(005~009) — 잔고·수익률만", () => {
    const plain = series([{ date: "2021-01-04", balance: "100000", returnRate: "0.1" }], {});
    expect(hoverView(plain, "2021-01-04")?.lines).toEqual([
      { label: "잔고", value: "₩100,000" }, { label: "수익률", value: "+10.00%" }]);
  });
});

describe("gapSlots — 구간마다 자리 하나", () => {
  it("점 범위 안의 출처 결측·시세 없음 구간마다 from 하나", () => {
    expect(gapSlots(CRYPTO.points, CRYPTO.gaps)).toEqual([
      { time: "2024-03-02", from: "2024-03-02", to: "2024-03-03", reason: "source_missing" }]);
    expect(gapSlots(APT.points, APT.gaps)).toEqual([
      { time: "2023-01-01", from: "2023-01-01", to: "2023-05-01", reason: "no_price" }]);
  });

  it("휴장·미수집과 점 범위 밖 구간은 자리를 두지 않는다", () => {
    const points = [{ date: "2024-01-15" }, { date: "2024-02-01" }];
    expect(gapSlots(points, [
      { from: "2024-01-01", to: "2024-01-14", reason: "source_missing" },
      { from: "2024-01-20", to: "2024-01-21", reason: "no_quote" },
      { from: "2024-01-22", to: "2024-01-23", reason: "not_collected" },
      { from: "2024-02-02", to: "2024-02-03", reason: "source_missing" },
    ])).toEqual([]);
  });
});

describe("placeHover — 차트 칸 안에", () => {
  const box = { width: 200, height: 100 };
  const area = { width: 800, height: 360 };

  it("기본은 커서 오른쪽 아래 12px", () => {
    expect(placeHover({ x: 100, y: 50 }, box, area)).toEqual({ left: 112, top: 62 });
  });

  it("오른쪽이 넘치면 커서 왼쪽, 아래가 넘치면 위", () => {
    expect(placeHover({ x: 700, y: 300 }, box, area)).toEqual({ left: 488, top: 188 });
  });

  it("어느 쪽으로도 넘치면 칸 안으로 붙인다", () => {
    const place = placeHover({ x: 150, y: 80 }, { width: 400, height: 300 }, { width: 420, height: 320 });
    expect(place.left).toBeGreaterThanOrEqual(0);
    expect(place.left).toBeLessThanOrEqual(20);
    expect(place.top).toBeGreaterThanOrEqual(0);
    expect(place.top).toBeLessThanOrEqual(20);
  });
});
