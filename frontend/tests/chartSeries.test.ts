/**
 * 차트 시리즈 구성 테스트 (T076) — contracts/ui-chart.md.
 *
 * **결측 구간에서 시리즈를 분리해야 한다.** Lightweight Charts는 포인트 사이를 기본적으로
 * 직선 연결하므로, 값을 넣지 않는 것만으로는 부족하다 (헌법 원칙 V, FR-032).
 *
 * 캔버스 렌더링 대신 데이터 준비 로직을 검증한다 — 원칙 위반이 발생하는 지점이 여기다.
 */
import { describe, expect, it } from "vitest";
import { splitSeriesAtGaps, toChartData } from "@/lib/chartSeries";
import type { SeriesGap, SeriesPoint } from "@/lib/types";

const POINTS: SeriesPoint[] = [
  { date: "2005-03-15", baseRate: "1012.30" },
  { date: "2005-03-16", baseRate: "1008.70" },
  { date: "2005-03-17", baseRate: "1015.55" },
  { date: "2005-03-20", baseRate: "1011.00" },
];

const GAPS: SeriesGap[] = [{ from: "2005-03-18", to: "2005-03-19", reason: "no_quote" }];

describe("결측 구간 분리", () => {
  it("gap을 경계로 시리즈를 나눈다", () => {
    const segments = splitSeriesAtGaps(POINTS, GAPS);
    expect(segments).toHaveLength(2);
    expect(segments[0].map((p) => p.date)).toEqual([
      "2005-03-15", "2005-03-16", "2005-03-17",
    ]);
    expect(segments[1].map((p) => p.date)).toEqual(["2005-03-20"]);
  });

  it("gap이 없으면 한 덩어리다", () => {
    expect(splitSeriesAtGaps(POINTS, [])).toHaveLength(1);
  });

  it("여러 gap을 모두 반영한다", () => {
    // 포인트 3개(15·17·20)를 gap 2개가 가르므로 3구간이 된다
    const gaps: SeriesGap[] = [
      { from: "2005-03-16", to: "2005-03-16", reason: "no_quote" },
      { from: "2005-03-18", to: "2005-03-19", reason: "not_collected" },
    ];
    const points = POINTS.filter((p) => p.date !== "2005-03-16");
    const segments = splitSeriesAtGaps(points, gaps);
    expect(segments).toHaveLength(3);
    expect(segments.map((s) => s.map((p) => p.date))).toEqual([
      ["2005-03-15"], ["2005-03-17"], ["2005-03-20"],
    ]);
  });

  it("결측 구간에 포인트를 만들어내지 않는다", () => {
    const all = splitSeriesAtGaps(POINTS, GAPS).flat();
    expect(all).toHaveLength(POINTS.length);
    expect(all.map((p) => p.date)).not.toContain("2005-03-18");
  });

  it("빈 입력은 빈 결과다", () => {
    expect(splitSeriesAtGaps([], GAPS)).toEqual([]);
  });
});

describe("차트 데이터 변환", () => {
  it("값을 숫자로 바꾸되 원본 문자열을 함께 보존한다", () => {
    const data = toChartData(POINTS);
    expect(data[0].value).toBeCloseTo(1012.3, 2);
    expect(data[0].raw).toBe("1012.30");
  });

  it("시간이 오름차순이다", () => {
    const times = toChartData(POINTS).map((d) => d.time);
    expect(times).toEqual([...times].sort());
  });

  it("툴팁은 원본 문자열을 쓴다", () => {
    /** 화면 표시에는 원본을 쓴다 — 렌더링용 number 변환이 값의 진실이 되면 안 된다. */
    const data = toChartData(POINTS);
    expect(data.every((d) => typeof d.raw === "string")).toBe(true);
  });
});
