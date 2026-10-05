/**
 * 시세 없음에서 선을 끊는다 (T046) — 009 FR-026, FR-031, SC-006, ui-wireframes E6, contracts/rest-api `simulation/series`.
 *
 * 부동산의 시세 없음 달(36개월 안에 거래 없음)은 점이 없고 `gaps`(`no_price`)로 온다. **끊는다** — 앞뒤를 이으면 그 사이에 시세가 있었던
 * 것처럼 그려진다(헌법 원칙 V). 점은 매달이다 — 첫 점은 매입일, 그 뒤 매달 1일, 끝점은 계산 끝. 결측 구간의 `from`·`to`는 비어 있는 첫
 * 달·마지막 달의 1일이다(양끝 포함). 휴장(`no_quote`)은 여전히 잇는다 — 규칙이 바뀌면 주식·외환의 주말마다 선이 쪼개진다.
 *
 * ## 이 테스트가 전제하는 형식 (T048이 따른다)
 *
 * `@/lib/types`: `SeriesGap.reason`에 `"no_price"`를 더한다. `SimulationPoint`에 선택 키 `estimated?: boolean`·`provisional?: boolean`
 * (부동산만 싣는다 — 다른 자산군에는 이 키가 없고 시리즈는 지금과 같다).
 */
import { describe, expect, it } from "vitest";
import { splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import type { SeriesGap, SimulationPoint } from "@/lib/types";

const dates = (segments: { date: string }[][]) => segments.map((s) => s.map((p) => p.date));
const point = (date: string) => ({ date });

/** 2023-12 ~ 2025-01이 시세 없음 — 헬리오시티 50평대의 예(contracts/rest-api). */
const NO_PRICE: SeriesGap = { from: "2023-12-01", to: "2025-01-01", reason: "no_price" };

describe("splitSeriesAtGaps — no_price", () => {
  it("시세 없음 구간에서 끊는다 — 앞뒤를 잇지 않는다", () => {
    const points = ["2023-10-01", "2023-11-01", "2025-02-01", "2025-03-01"].map(point);
    expect(dates(splitSeriesAtGaps(points, [NO_PRICE]))).toEqual([
      ["2023-10-01", "2023-11-01"], ["2025-02-01", "2025-03-01"]]);
  });

  it("한 달만 비어도 끊는다 — from과 to가 같은 달", () => {
    const points = ["2024-04-01", "2024-06-01"].map(point);
    expect(dates(splitSeriesAtGaps(points, [{ from: "2024-05-01", to: "2024-05-01", reason: "no_price" }])))
      .toEqual([["2024-04-01"], ["2024-06-01"]]);
  });

  it("시세 없음 구간이 둘이면 셋으로 나뉜다", () => {
    const points = ["2022-01-01", "2022-04-01", "2023-01-01"].map(point);
    const gaps: SeriesGap[] = [
      { from: "2022-02-01", to: "2022-03-01", reason: "no_price" },
      { from: "2022-05-01", to: "2022-12-01", reason: "no_price" },
    ];
    expect(dates(splitSeriesAtGaps(points, gaps))).toEqual([["2022-01-01"], ["2022-04-01"], ["2023-01-01"]]);
  });

  it("매입일(그 달 중간)의 첫 점 뒤에 시세 없음이 오면 첫 점만 따로다", () => {
    const points = ["2021-03-15", "2021-06-01", "2021-07-01"].map(point);
    expect(dates(splitSeriesAtGaps(points, [{ from: "2021-04-01", to: "2021-05-01", reason: "no_price" }])))
      .toEqual([["2021-03-15"], ["2021-06-01", "2021-07-01"]]);
  });

  it("끝(이번 달)이 시세 없음이면 마지막으로 시세가 있던 달에서 끝난다 — 뒤에 빈 구간을 만들지 않는다", () => {
    const points = ["2024-01-01", "2024-02-01"].map(point);
    const segments = splitSeriesAtGaps(points, [{ from: "2024-03-01", to: "2026-10-01", reason: "no_price" }]);
    expect(dates(segments)).toEqual([["2024-01-01", "2024-02-01"]]);
  });

  it("처음부터 시세 없음이었으면 앞에 빈 구간을 만들지 않는다", () => {
    const points = ["2025-02-01", "2025-03-01"].map(point);
    const segments = splitSeriesAtGaps(points, [{ from: "2024-11-01", to: "2025-01-01", reason: "no_price" }]);
    expect(dates(segments)).toEqual([["2025-02-01", "2025-03-01"]]);
  });

  it("휴장은 여전히 잇는다 — 규칙이 섞이지 않는다", () => {
    const points = ["2023-10-01", "2023-11-01", "2025-02-01"].map(point);
    const segments = splitSeriesAtGaps(points, [{ ...NO_PRICE, reason: "no_quote" }]);
    expect(segments).toHaveLength(1);
  });
});

describe("toPerformanceData — 선택 키", () => {
  const plain: SimulationPoint[] = [
    { date: "2021-03-15", balance: "2023166667", returnRate: "-0.040307" },
    { date: "2021-04-01", balance: "2031250000", returnRate: "-0.036473" },
  ];
  const marked: SimulationPoint[] = plain.map((p, i) => ({ ...p, estimated: i === 1, provisional: false }));

  it("estimated·provisional 키가 있어도 그리는 값은 같다", () => {
    expect(toPerformanceData(marked, "balance")).toEqual(toPerformanceData(plain, "balance"));
    expect(toPerformanceData(marked, "returnRate")).toEqual(toPerformanceData(plain, "returnRate"));
  });
});
