/**
 * 출처 결측에서 선을 끊는다 (T040) — 007 FR-023, FR-043, research R7-9.
 *
 * 가상자산은 24시간 거래라 휴장이 없다. 받은 구간 안의 빈 날은 **출처 결측**(`source_missing`)이다 — 이으면 없는 값을 있는
 * 것처럼 그린다(헌법 원칙 V). 주식·외환의 휴장(`no_quote`)은 여전히 잇는다 — 규칙이 바뀌면 주말마다 선이 쪼개진다.
 */
import { describe, expect, it } from "vitest";
import { splitSeriesAtGaps } from "@/lib/chartSeries";

const POINTS = [
  { date: "2021-02-27" }, { date: "2021-02-28" }, { date: "2021-03-03" }, { date: "2021-03-04" },
];

describe("splitSeriesAtGaps", () => {
  it("출처 결측에서 끊는다", () => {
    const segments = splitSeriesAtGaps(POINTS, [
      { from: "2021-03-01", to: "2021-03-02", reason: "source_missing" }]);
    expect(segments.map((s) => s.map((p) => p.date))).toEqual([
      ["2021-02-27", "2021-02-28"], ["2021-03-03", "2021-03-04"]]);
  });

  it("휴장은 여전히 잇는다", () => {
    const segments = splitSeriesAtGaps(POINTS, [
      { from: "2021-03-01", to: "2021-03-02", reason: "no_quote" }]);
    expect(segments).toHaveLength(1);
  });

  it("미수집도 여전히 끊는다", () => {
    const segments = splitSeriesAtGaps(POINTS, [
      { from: "2021-03-01", to: "2021-03-02", reason: "not_collected" }]);
    expect(segments).toHaveLength(2);
  });
});
