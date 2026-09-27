/**
 * 차트 시리즈 구성 테스트 (T076, T121, T122) — contracts/ui-chart.md.
 *
 * **`reason`에 따라 다르게 그린다** (2026-09-27 반복으로 개정된 FR-032·FR-032b).
 *
 * | `reason` | 뜻 | 선 |
 * |----------|-----|-----|
 * | `no_quote` | 휴장일·주말 — 그날은 시장이 열리지 않아 **값이 존재하지 않는다** | 잇는다 |
 * | `not_collected` | 아직 수집 안 함 — 값이 존재할 수 있는데 받지 않았다 | 끊는다 |
 *
 * 미수집을 이으면 **구멍 위에 온전한 선**이 그려져 사용자가 데이터를 다 가졌다고 믿는다.
 * 반대로 휴장일마다 끊으면 1년 보기에서 50구간 넘게 쪼개져 추세가 읽히지 않는다.
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

/** 2005-03-18(금)·19(토)는 휴장 — 주말이 그대로 이 모양이다. */
const HOLIDAY: SeriesGap[] = [
  { from: "2005-03-18", to: "2005-03-19", reason: "no_quote" },
];

const UNCOLLECTED: SeriesGap[] = [
  { from: "2005-03-18", to: "2005-03-19", reason: "not_collected" },
];

describe("결측 구간 분리", () => {
  it("휴장일에서는 나누지 않는다", () => {
    // FR-032 — 그날은 시장이 열리지 않아 값이 존재하지 않는다. 실제로 존재하는 두
    // 고시일을 잇는 것은 값을 만들어내는 것이 아니다.
    const segments = splitSeriesAtGaps(POINTS, HOLIDAY);
    expect(segments).toHaveLength(1);
    expect(segments[0].map((p) => p.date)).toEqual(POINTS.map((p) => p.date));
  });

  it("미수집 구간에서는 나눈다", () => {
    // FR-032 — 이으면 아직 받지 않은 구간 위에 온전한 선이 그려진다.
    const segments = splitSeriesAtGaps(POINTS, UNCOLLECTED);
    expect(segments).toHaveLength(2);
    expect(segments[0].map((p) => p.date)).toEqual([
      "2005-03-15", "2005-03-16", "2005-03-17",
    ]);
    expect(segments[1].map((p) => p.date)).toEqual(["2005-03-20"]);
  });

  it("gap이 없으면 한 덩어리다", () => {
    expect(splitSeriesAtGaps(POINTS, [])).toHaveLength(1);
  });

  it("두 사유가 섞이면 미수집에서만 끊는다", () => {
    // T122 — 섞이지 않은 픽스처만 두면 `reason`을 아예 안 보는 구현도 절반은 통과한다.
    // 포인트 3개(15·17·20) 중 16일은 휴장, 18~19일은 미수집이므로 2구간이 된다.
    const gaps: SeriesGap[] = [
      { from: "2005-03-16", to: "2005-03-16", reason: "no_quote" },
      { from: "2005-03-18", to: "2005-03-19", reason: "not_collected" },
    ];
    const points = POINTS.filter((p) => p.date !== "2005-03-16");
    const segments = splitSeriesAtGaps(points, gaps);
    expect(segments.map((s) => s.map((p) => p.date))).toEqual([
      ["2005-03-15", "2005-03-17"], ["2005-03-20"],
    ]);
  });

  it("휴장일만 여럿이면 끝까지 한 덩어리다", () => {
    // 1년 보기에서 주말만 50구간 넘게 잡힌다. 그때마다 끊으면 추세가 읽히지 않는다.
    const weekends: SeriesGap[] = [
      { from: "2005-03-16", to: "2005-03-16", reason: "no_quote" },
      { from: "2005-03-18", to: "2005-03-19", reason: "no_quote" },
    ];
    expect(splitSeriesAtGaps(POINTS, weekends)).toHaveLength(1);
  });

  it("결측 구간에 포인트를 만들어내지 않는다", () => {
    // 헌법 원칙 V — 잇는 것과 값을 만드는 것은 다르다. 포인트 수는 그대로다.
    const all = splitSeriesAtGaps(POINTS, UNCOLLECTED).flat();
    expect(all).toHaveLength(POINTS.length);
    expect(all.map((p) => p.date)).not.toContain("2005-03-18");

    const joined = splitSeriesAtGaps(POINTS, HOLIDAY).flat();
    expect(joined).toHaveLength(POINTS.length);
    expect(joined.map((p) => p.date)).not.toContain("2005-03-18");
  });

  it("빈 입력은 빈 결과다", () => {
    expect(splitSeriesAtGaps([], UNCOLLECTED)).toEqual([]);
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
