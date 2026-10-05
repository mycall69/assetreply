/**
 * 성과 차트의 커서 가까이 상자 (010 T021) — FR-009~FR-014, SC-003, research R10-8·R10-9, ui-wireframes F2.
 *
 * - `subscribeCrosshairMove`의 `time`·`point`로 상자(`role="tooltip"`, `data-testid="performance-hover"`)를 연다 — 내용은 `hoverView`, 자리는
 *   `placeHover`(차트 칸과 상자의 크기는 `getBoundingClientRect`). 커서가 벗어나면(`time`·`point` 없음) 상자가 없다 — 마지막 값이 남지
 *   않는다(FR-012)
 * - 차트 아래 한 줄 표시(`performance-tooltip`)는 어떤 경우에도 없다(FR-013)
 * - 가격이 있고 점 범위 안에 출처 결측·시세 없음 구간이 있으면 **값 없는 자리 시리즈**(데이터가 `{ time }`뿐, 구간마다 하나)를 둔다 — 그
 *   자리에 커서가 오면 구간과 사유(R10-8). 가격 키가 없는 응답이면 만들지 않는다(기존 시리즈 수 그대로)
 * - 터치는 라이브러리 기본 추적 모드가 같은 콜백을 부른다 — 모의 객체에 `subscribeClick`이 없다(부르면 실패한다)
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

interface Added {
  options: Record<string, unknown>;
  data: { time: string; value?: number }[];
}

type Move = (param: { time?: string; point?: { x: number; y: number } }) => void;

const added: Added[] = [];
let move: Move = () => undefined;

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry: Added = { options, data: [] };
      added.push(entry);
      return { setData: (data: { time: string; value?: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: (handler: Move) => { move = handler; },
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse>): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

const STOCK = series([
  { date: "2020-08-03", balance: "14210345", returnRate: "0.4210", price: "432.800000" },
  { date: "2020-09-01", balance: "15342210", returnRate: "0.534221", price: "132.759995" },
  { date: "2020-10-01", balance: "15100000", returnRate: "0.510000", price: "116.790000" },
], { priceKind: "stock_open", priceCurrency: "USD", splits: [{ date: "2020-08-31", numerator: 4, denominator: 1 }] });

const CRYPTO = series([
  { date: "2024-03-01", balance: "1000000", returnRate: "0", price: "62000.10000000" },
  { date: "2024-03-04", balance: "1100000", returnRate: "0.1", price: "63000.00000000" },
  { date: "2024-03-08", balance: "1150000", returnRate: "0.15", price: "64000.00000000" },
], {
  priceKind: "crypto_open", priceCurrency: "USD",
  gaps: [{ from: "2024-03-02", to: "2024-03-03", reason: "source_missing" },
    { from: "2024-03-05", to: "2024-03-07", reason: "source_missing" }],
});

const DEPOSIT = series([
  { date: "2026-08-01", balance: "10520000", returnRate: "0.0520", price: "3.60" },
  { date: "2026-09-01", balance: "10530000", returnRate: "0.0530", price: null, priceMissing: "unpublished" },
], { priceKind: "deposit_rate", priceCurrency: null });

const APT = series([
  { date: "2021-03-15", balance: "2023166667", returnRate: "-0.040307", profit: "-85000000", price: "2023166667", estimated: false },
  { date: "2021-04-01", balance: "2031250000", returnRate: "-0.036473", profit: "-77000000", price: null, priceMissing: "no_trades", estimated: true },
  { date: "2021-05-01", balance: "2040000000", returnRate: "-0.032322", profit: "-68000000", price: "2040000000", estimated: false },
], { priceKind: "apt_average", priceCurrency: "KRW" });

const box = () => screen.queryByTestId("performance-hover");
const slotSeries = () => added.filter((e) => e.data.length > 0 && e.data.every((d) => d.value === undefined));
const strip = (s: SimulationSeriesResponse): SimulationSeriesResponse => {
  const points = s.points.map((p) => {
    const copy = { ...p };
    delete copy.price;
    delete copy.priceMissing;
    delete copy.profit;
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

function hoverAt(time: string | undefined, point?: { x: number; y: number }) {
  act(() => move(time === undefined ? {} : { time, point }));
}

beforeEach(() => {
  added.length = 0;
  move = () => undefined;
  // 차트 칸 800×360, 상자 200×100 — jsdom에는 배치가 없어 크기를 흉내 낸다.
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const testid = this.getAttribute("data-testid");
    const [width, height] = testid === "performance-hover" ? [200, 100] : [800, 360];
    return { width, height, top: 0, left: 0, right: width, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("상자를 열고 닫는다", () => {
  it("커서가 붙은 점의 값을 커서 가까이 보인다", () => {
    draw(STOCK);
    hoverAt("2020-09-01", { x: 100, y: 50 });
    const tip = screen.getByRole("tooltip");
    expect(tip).toBe(box());
    for (const text of ["2020-09-01", "주가", "$132.75", "잔고", "₩15,342,210", "수익률", "+53.42%", "분할 1→4 (2020-08-31 효력)"]) {
      expect(tip.textContent).toContain(text);
    }
    expect(tip.style.left).toBe("112px");
    expect(tip.style.top).toBe("62px");
  });

  it("오른쪽 아래 끝이면 커서 반대쪽으로 비켜 칸 안에 뜬다", () => {
    draw(STOCK);
    hoverAt("2020-10-01", { x: 700, y: 300 });
    expect(box()?.style.left).toBe("488px");
    expect(box()?.style.top).toBe("188px");
  });

  it("차트를 벗어나면 상자가 없다 — 마지막 값이 남지 않는다", () => {
    draw(STOCK);
    hoverAt("2020-09-01", { x: 100, y: 50 });
    expect(box()).not.toBeNull();
    hoverAt(undefined);
    expect(box()).toBeNull();
  });

  it("차트 아래 한 줄 표시는 어떤 경우에도 없다", () => {
    draw(STOCK);
    expect(screen.queryByTestId("performance-tooltip")).toBeNull();
    hoverAt("2020-09-01", { x: 100, y: 50 });
    expect(screen.queryByTestId("performance-tooltip")).toBeNull();
  });

  it("다운샘플된 점이면 그 점의 날짜와 값이다", () => {
    draw({ ...STOCK, downsampled: true, sourcePointCount: 95 });
    hoverAt("2020-10-01", { x: 100, y: 50 });
    expect(box()?.textContent).toContain("2020-10-01");
    expect(box()?.textContent).toContain("$116.79");
  });
});

describe("값이 없는 칸", () => {
  it("예금 미발표 달 — 금리 — 미발표", () => {
    draw(DEPOSIT);
    hoverAt("2026-09-01", { x: 100, y: 50 });
    expect(box()?.textContent).toContain("금리");
    expect(box()?.textContent).toContain("—");
    expect(box()?.textContent).toContain("미발표");
    expect(box()?.textContent).toContain("₩10,530,000");
  });

  it("부동산 거래 없는 달 — 실거래가 평균만 — 거래 없음, 평가액·투자 수익은 그대로", () => {
    draw(APT);
    hoverAt("2021-04-01", { x: 100, y: 50 });
    const text = box()?.textContent ?? "";
    for (const part of ["2021-04", "평가액", "₩2,031,250,000", "투자 수익", "-₩77,000,000", "실거래가 평균", "거래 없음"]) {
      expect(text).toContain(part);
    }
  });
});

describe("값 없는 자리", () => {
  it("가격이 있으면 점 범위 안의 결측 구간마다 자리 하나 — 데이터가 time뿐", () => {
    draw(CRYPTO);
    const [slots, ...rest] = slotSeries();
    expect(rest).toEqual([]);
    expect(slots.data).toEqual([{ time: "2024-03-02" }, { time: "2024-03-05" }]);
  });

  it("자리에 커서가 오면 구간과 사유", () => {
    draw(CRYPTO);
    hoverAt("2024-03-05", { x: 100, y: 50 });
    const text = box()?.textContent ?? "";
    expect(text).toContain("2024-03-05 ~ 2024-03-07");
    expect(text).toContain("출처 결측");
  });

  it("가격 키가 없는 응답이면 자리 시리즈가 없다", () => {
    draw(strip(CRYPTO));
    expect(slotSeries()).toEqual([]);
  });
});
