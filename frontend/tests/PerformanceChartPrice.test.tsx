/**
 * 성과 차트의 가격 선 (010 T012) — FR-001, FR-003~FR-006, FR-008, research R10-4·R10-7, ui-wireframes F1.
 *
 * - 가격 선은 **눈금 없는 겹침 축**이다 — `priceScaleId "price"`(left·right가 아니다), 가격 표지·마지막 값 표지 없음(FR-004). 여백은 `createChart`
 *   옵션 `overlayPriceScales`로 준다(모의 객체에 `priceScale()`이 없다)
 * - 가격이 `null`인 점에서 **가격 선만** 끊긴다 — 잔고·수익률 선은 그 달에도 값이 있어 끊기지 않는다(FR-003)
 * - 점 하나뿐인 가격 구간은 점으로 그린다(선은 두 점이 있어야 보인다). 부동산(`apt_average`)은 달마다 거래가 드물어 모든 구간에 점 표식
 * - 잠정 구간(`provisionalFrom` 뒤)은 가격 선도 연한 색이다(FR-006). 부동산 추정 표식은 평가액 축에만 있다
 * - 분할 표식은 가격 축 위에 점만 그리는 시리즈다 — 그린 점 중 효력일 이상인 첫 점(FR-008)
 * - 범례가 이름과 단위를 밝힌다(FR-005)
 * - **점에 `price` 키가 없으면 지금과 같은 시리즈다** — 005~009의 차트 테스트가 그대로 통과해야 한다
 *
 * 모의 객체에 `createSeriesMarkers`·`subscribeClick`·`priceScale`이 없다 — 구현이 부르면 이 테스트가 실패한다(기존 테스트도 같다).
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

interface Added {
  options: Record<string, unknown>;
  data: { time: string; value?: number }[];
}

const added: Added[] = [];
const chartOptions: Record<string, unknown>[] = [];

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: (_el: unknown, options: Record<string, unknown>) => {
    chartOptions.push(options);
    return {
      addSeries: (_kind: unknown, options: Record<string, unknown>) => {
        const entry: Added = { options, data: [] };
        added.push(entry);
        return { setData: (data: { time: string; value?: number }[]) => { entry.data = data; } };
      },
      subscribeCrosshairMove: () => undefined,
      timeScale: () => ({ fitContent: () => undefined }),
      remove: () => undefined,
    };
  },
}));

const pt = (date: string, price: string | null, over: Partial<SimulationPoint> = {}): SimulationPoint => ({
  date, balance: "1000000", returnRate: "0.010000", price,
  ...(price === null ? { priceMissing: "unpublished" as const } : {}), ...over,
});

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse>): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

const STOCK = series([
  pt("2020-08-03", "432.80"), pt("2020-09-01", "132.76"), pt("2020-10-01", "116.79"), pt("2020-11-02", "109.11"),
], { priceKind: "stock_open", priceCurrency: "USD", splits: [{ date: "2020-08-31", numerator: 4, denominator: 1 }] });

const CRYPTO = series([pt("2024-01-15", "42511.10"), pt("2024-01-16", "42800.00"), pt("2024-01-17", "43100.50")],
  { priceKind: "crypto_open", priceCurrency: "USD" });

/** 2020-06은 발표 기간 안의 빈 달(결측), 2026-09부터 미발표 — 금리 선만 끊긴다. 2020-07부터 잠정(연한 색). */
const DEPOSIT = series([
  pt("2020-05-01", "1.50"), pt("2020-06-01", null, { priceMissing: "missing" }), pt("2020-07-01", "1.60"),
  pt("2020-08-01", "1.70"), pt("2020-09-01", "1.65"),
], { priceKind: "deposit_rate", priceCurrency: null, provisionalFrom: "2020-08-01" });

/** 2021-05·07은 거래 없음(추정 평가) — 2021-06은 앞뒤가 비어 점 하나뿐인 구간이다. */
const APT = series([
  pt("2021-03-15", "2023166667", { estimated: false }), pt("2021-04-01", "2031250000", { estimated: false }),
  pt("2021-05-01", null, { priceMissing: "no_trades", estimated: true }),
  pt("2021-06-01", "2045000000", { estimated: false }),
  pt("2021-07-01", null, { priceMissing: "no_trades", estimated: true }),
  pt("2021-08-01", "2093333333", { estimated: false }), pt("2021-09-01", "2100000000", { estimated: false }),
], { priceKind: "apt_average", priceCurrency: "KRW" });

const onPrice = (e: Added) => e.options.priceScaleId === "price";
const priceLines = () => added.filter((e) => onPrice(e) && e.options.lineVisible !== false && e.data.some((d) => d.value !== undefined));
const splitMarkers = () => added.filter((e) => onPrice(e) && e.options.lineVisible === false);
const balanceLines = () => added.filter((e) => e.options.priceScaleId === "left" && e.options.lineVisible !== false);
const times = (e: Added) => e.data.map((d) => d.time);
const legend = () => screen.getByTestId("chart-legend").textContent ?? "";
/** 가격 키를 지운다 — 005~009의 응답 모양. */
const strip = (s: SimulationSeriesResponse): SimulationSeriesResponse => {
  const points = s.points.map((p) => {
    const copy = { ...p };
    delete copy.price;
    delete copy.priceMissing;
    return copy;
  });
  const out = { ...s, points };
  delete out.priceKind;
  delete out.priceCurrency;
  delete out.splits;
  return out;
};

function draw(s: SimulationSeriesResponse) {
  render(<PerformanceChart series={s} collecting={null} loading={false} />);
}

beforeEach(() => {
  added.length = 0;
  chartOptions.length = 0;
});

describe("가격 선 — 겹침 축", () => {
  it("가격 축은 left·right가 아니고 눈금 표지가 없으며 값은 점의 가격이다", () => {
    draw(STOCK);
    const [line, ...rest] = priceLines();
    expect(rest).toEqual([]);
    expect(line.options).toMatchObject({ priceScaleId: "price", priceLineVisible: false, lastValueVisible: false });
    expect(line.data).toEqual(STOCK.points.map((p) => ({ time: p.date, value: Number(p.price) })));
  });

  it("겹침 축 여백은 차트 옵션으로 준다", () => {
    draw(CRYPTO);
    expect(chartOptions[0]).toHaveProperty("overlayPriceScales");
  });

  it("가격이 null인 점에서 가격 선만 끊긴다 — 잔고 선은 이어진다", () => {
    draw({ ...DEPOSIT, provisionalFrom: null });
    expect(priceLines().map(times)).toEqual([["2020-05-01"], ["2020-07-01", "2020-08-01", "2020-09-01"]]);
    expect(balanceLines().map(times)).toEqual([DEPOSIT.points.map((p) => p.date)]);
  });

  it("점 하나뿐인 구간은 점으로 그린다 — 여러 점의 주가 선에는 점 표식이 없다", () => {
    draw({ ...DEPOSIT, provisionalFrom: null });
    const [single, multi] = priceLines();
    expect(single.options.pointMarkersVisible).toBe(true);
    expect(multi.options.pointMarkersVisible ?? false).toBe(false);
  });

  it("부동산 실거래가 평균은 모든 구간에 점 표식", () => {
    draw(APT);
    const lines = priceLines();
    expect(lines.map(times)).toEqual([["2021-03-15", "2021-04-01"], ["2021-06-01"], ["2021-08-01", "2021-09-01"]]);
    expect(lines.every((e) => e.options.pointMarkersVisible === true)).toBe(true);
  });

  it("잠정 구간은 가격 선도 연한 색이다", () => {
    draw(DEPOSIT);
    const lines = priceLines();
    const confirmed = lines.find((e) => times(e).includes("2020-07-01"));
    const provisional = lines.find((e) => times(e).includes("2020-09-01"));
    expect(confirmed && provisional).toBeTruthy();
    expect(provisional?.options.color).not.toBe(confirmed?.options.color);
  });

  it("부동산 추정 표식은 평가액 축에만 있다 — 실거래가 평균에는 붙지 않는다", () => {
    draw(APT);
    const markers = added.filter((e) => e.options.lineVisible === false);
    expect(markers.length).toBeGreaterThan(0);
    expect(markers.every((e) => e.options.priceScaleId === "left")).toBe(true);
  });
});

describe("분할 표식", () => {
  it("효력일 뒤 첫 점에 가격 축의 점으로 단다", () => {
    draw(STOCK);
    const markers = splitMarkers();
    expect(markers.length).toBeGreaterThan(0);
    for (const marker of markers) {
      expect(marker.options.pointMarkersVisible).toBe(true);
      expect(marker.data).toEqual([{ time: "2020-09-01", value: 132.76 }]);
    }
  });

  it("분할이 없으면 표식 시리즈가 없다", () => {
    draw({ ...STOCK, splits: [] });
    expect(splitMarkers()).toEqual([]);
  });
});

describe("범례", () => {
  it.each([
    [STOCK, "주가 (USD)"], [CRYPTO, "시세 (USD)"], [DEPOSIT, "금리 (연 %)"], [APT, "실거래가 평균 (KRW)"],
  ])("이름과 단위를 밝힌다 — %#", (s, text) => {
    draw(s);
    expect(legend()).toContain(text);
  });

  it("분할이 있으면 ● 분할", () => {
    draw(STOCK);
    expect(legend()).toContain("● 분할");
  });

  it("분할이 없으면 분할 범례가 없다", () => {
    draw(CRYPTO);
    expect(legend()).not.toContain("분할");
  });
});

describe("가격 키가 없는 응답 — 지금과 같다", () => {
  it.each([STOCK, CRYPTO, DEPOSIT, APT].map((s) => [s.priceKind, s] as const))("%s — 가격 시리즈가 없고 범례에 가격이 없다", (_kind, s) => {
    draw(strip(s));
    expect(added.filter(onPrice)).toEqual([]);
    expect(chartOptions[0]).not.toHaveProperty("overlayPriceScales");
    for (const word of ["주가", "시세 (", "금리", "실거래가 평균", "분할"]) expect(legend()).not.toContain(word);
  });
});
