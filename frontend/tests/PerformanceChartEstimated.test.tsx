/**
 * 성과 차트의 추정 시세·시세 없음 (T046) — 009 FR-017, FR-026, FR-031, SC-006, ui-wireframes E6.
 *
 * `PerformanceChart`를 그대로 쓴다(research R9-10).
 * - **추정 점은 표식**이다 — 시계열 점의 선택 키 `estimated`가 참인 점에만, 평가액 선 위에. 범례 "○ 추정 시세(1개월 밖의 창)". 표식이
 *   없으면 3년 전 거래 평균이 그 달의 실거래처럼 보인다(FR-017)
 * - **시세 없음**(`no_price`)은 선을 끊고(앞뒤를 잇지 않는다) 범례가 "시세 없음"이라고 그 뜻을 밝힌다(FR-026)
 * - 잠정은 008의 `provisionalFrom`(연한 색) 그대로다
 * - 주식·가상자산·예금은 `estimated` 키가 없다 — **지금과 같은 시리즈**다(005~008의 `PerformanceChart*.test.tsx`가 그대로 통과한다)
 * - 부동산 실행의 202(`RealEstateTradeCollecting`)면 차트 대신 수집 안내다
 *
 * ## 이 테스트가 전제하는 구현 (T048이 따른다)
 *
 * - 추정 표식은 **점만 그리는 선 시리즈**다 — `addSeries(LineSeries, { lineVisible: false, pointMarkersVisible: true, ... })`, 평가액 축
 *   (`priceScaleId`가 평가액 선과 같다), 데이터는 추정 점의 날짜와 평가액뿐이다. 속이 빈 원은 같은 날짜의 점 시리즈를 겹쳐 그려도 된다
 *   (테두리 색 원 위에 배경색 작은 원) — 모양 자체는 캔버스가 없는 jsdom에서 볼 수 없어 브라우저 확인(T051)이 본다
 * - 추정 점이 하나도 없으면 표식 시리즈를 만들지 않는다 — 시리즈 수가 지금과 같다
 * - `@/lib/types`: `SimulationPoint.estimated?`·`provisional?`, `SeriesGap.reason`에 `"no_price"`. `collecting` 속성에
 *   `RealEstateTradeCollecting`을 더한다
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";
import { SIM_COLLECTING } from "./support/realEstateSimulationFixtures";

interface Added {
  options: Record<string, unknown>;
  data: { time: string; value: number }[];
}

const added: Added[] = [];

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: (_kind: unknown, options: Record<string, unknown>) => {
      const entry: Added = { options, data: [] };
      added.push(entry);
      return { setData: (data: { time: string; value: number }[]) => { entry.data = data; } };
    },
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const point = (date: string, balance: string, returnRate: string, estimated: boolean, provisional = false):
  SimulationPoint => ({ date, balance, returnRate, estimated, provisional });

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

/** 첫 점은 매입일, 그 뒤 매달 1일. 2021-05·06은 넓힌 창의 추정이다. */
const ESTIMATED = series([
  point("2021-03-15", "2023166667", "-0.040307", false),
  point("2021-04-01", "2031250000", "-0.036473", false),
  point("2021-05-01", "2040000000", "-0.032322", true),
  point("2021-06-01", "2045000000", "-0.029950", true),
  point("2021-07-01", "2093333333", "-0.007019", false),
]);

/** 2023-12 ~ 2025-01 시세 없음 — 헬리오시티 50평대의 예. 점을 줄였다. */
const NO_PRICE = series([
  point("2023-09-15", "3100000000", "-0.060000", false),
  point("2023-10-01", "3080000000", "-0.066000", true),
  point("2023-11-01", "3090000000", "-0.063000", true),
  point("2025-02-01", "3250000000", "-0.015000", true),
  point("2025-03-01", "3300000000", "0.000000", false),
], { gaps: [{ from: "2023-12-01", to: "2025-01-01", reason: "no_price" }] });

/** 시세 없음 + 잠정(2025-11부터) + 추정이 함께 있다. */
const COMBINED = series([
  ...NO_PRICE.points,
  point("2025-11-01", "3400000000", "0.030000", false, true),
  point("2026-10-05", "3450000000", "0.045000", true, true),
], { gaps: NO_PRICE.gaps, provisionalFrom: "2025-11-01" });

const isMarker = (e: Added) => e.options.lineVisible === false;
const lines = () => added.filter((e) => !isMarker(e));
const markers = () => added.filter(isMarker);
const times = (e: Added) => e.data.map((d) => d.time);
const estimatedDates = (s: SimulationSeriesResponse) => s.points.filter((p) => p.estimated === true).map((p) => p.date);
const legend = () => screen.getByTestId("chart-legend").textContent ?? "";

function draw(s: SimulationSeriesResponse) {
  render(<PerformanceChart series={s} collecting={null} loading={false} />);
}

beforeEach(() => {
  added.length = 0;
});

describe("추정 시세 표식", () => {
  it("평가액·수익률 선은 지금처럼 모든 점을 지난다", () => {
    draw(ESTIMATED);
    expect(lines()).toHaveLength(2);
    for (const line of lines()) expect(times(line)).toEqual(ESTIMATED.points.map((p) => p.date));
  });

  it("추정 점에만 표식 — 점만 그리는 시리즈다", () => {
    draw(ESTIMATED);
    expect(markers().length).toBeGreaterThan(0);
    for (const marker of markers()) {
      expect(marker.options.pointMarkersVisible).toBe(true);
      expect(times(marker).every((t) => estimatedDates(ESTIMATED).includes(t))).toBe(true);
    }
    const marked = [...new Set(markers().flatMap(times))].sort();
    expect(marked).toEqual(["2021-05-01", "2021-06-01"]);
  });

  it("표식은 평가액 선 위에 있다 — 같은 축, 같은 값", () => {
    draw(ESTIMATED);
    const balance = lines()[0];
    for (const marker of markers()) {
      expect(marker.options.priceScaleId).toBe(balance.options.priceScaleId);
      for (const d of marker.data) {
        expect(d.value).toBe(balance.data.find((b) => b.time === d.time)?.value);
      }
    }
  });

  it("범례가 표식의 뜻을 말한다", () => {
    draw(ESTIMATED);
    expect(legend()).toContain("○ 추정 시세(1개월 밖의 창)");
  });

  it("추정 점이 없으면 표식 시리즈도 범례도 없다", () => {
    draw(series(ESTIMATED.points.map((p) => ({ ...p, estimated: false }))));
    expect(markers()).toHaveLength(0);
    expect(added).toHaveLength(2);
    expect(legend()).not.toContain("추정");
  });

  it("estimated 키가 없으면(주식·가상자산·예금) 지금과 같은 시리즈다", () => {
    const plain = series(ESTIMATED.points.map(({ date, balance, returnRate }) => ({ date, balance, returnRate })));
    draw(plain);
    expect(added).toHaveLength(2);
    expect(markers()).toHaveLength(0);
    expect(legend()).not.toContain("추정");
  });
});

describe("시세 없음 (no_price)", () => {
  it("선을 끊는다 — 앞뒤를 잇지 않는다", () => {
    draw(NO_PRICE);
    expect(lines()).toHaveLength(4);
    const [balance, profit, balanceLater, profitLater] = lines();
    expect(times(balance)).toEqual(["2023-09-15", "2023-10-01", "2023-11-01"]);
    expect(times(profit)).toEqual(["2023-09-15", "2023-10-01", "2023-11-01"]);
    expect(times(balanceLater)).toEqual(["2025-02-01", "2025-03-01"]);
    expect(times(profitLater)).toEqual(["2025-02-01", "2025-03-01"]);
  });

  it("범례가 시세 없음을 말한다 — 미수집·결측과 섞지 않는다", () => {
    draw(NO_PRICE);
    expect(legend()).toContain("시세 없음");
    expect(legend()).not.toContain("미수집");
    expect(legend()).not.toContain("결측");
  });

  it("시세 없음이 없으면 범례에도 없다", () => {
    draw(ESTIMATED);
    expect(legend()).not.toContain("시세 없음");
  });

  it("끊긴 양쪽의 추정 점에 모두 표식", () => {
    draw(NO_PRICE);
    expect([...new Set(markers().flatMap(times))].sort()).toEqual(["2023-10-01", "2023-11-01", "2025-02-01"]);
  });
});

describe("잠정과 함께", () => {
  it("잠정은 provisionalFrom 그대로 — 연한 두 선이 더해지고 범례가 시작일을 말한다", () => {
    draw(COMBINED);
    // 끊긴 앞 구간(확정 두 선) + 뒤 구간의 확정 두 선 + 잠정 두 선.
    expect(lines()).toHaveLength(6);
    const later = lines().slice(4);
    for (const line of later) expect(times(line)).toEqual(["2025-11-01", "2026-10-05"]);
    expect(legend()).toContain("잠정(2025-11-01부터)");
  });

  it("표식은 확정·잠정 구간을 가리지 않고 추정 점에만", () => {
    draw(COMBINED);
    expect([...new Set(markers().flatMap(times))].sort()).toEqual(estimatedDates(COMBINED));
  });
});

describe("수집 중", () => {
  it("부동산 실행이 실거래를 기다리면(202) 차트 대신 안내를 보인다", () => {
    render(<PerformanceChart series={null} collecting={SIM_COLLECTING} loading={false} />);
    expect(screen.getByRole("status").textContent).toContain("완료되면 차트가 표시됩니다");
    expect(added).toHaveLength(0);
  });
});
